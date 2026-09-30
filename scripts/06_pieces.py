"""Cut each corridor into 500 m pieces and attach every measurable cause of delay.

One row per piece, along the outbound centreline (km 0 = Kampala end). Writes
outputs/pieces.csv and data/pieces.gpkg.

Columns, by group:
  roadside activity  buildings_100m, buildings_300m (count within that distance of the
                     centreline, per piece), shops_200m, markets_200m, fuel_200m,
                     schools_300m, stops_100m
  access             junctions_major (trunk to tertiary), junctions_minor (residential,
                     unclassified, service, track): roads joining the corridor
  point controls     humps (speed humps and rumble strips), signals, ped_crossings,
                     level_crossings, police_posts: within 30 m of the centreline;
                     weighbridges: each (duplicates within 300 m merged) counted once, in the
                     nearest piece, if within 150 m (they sit in lay-bys beside the road)
  design             dual (carriageways more than 8 m apart), lanes (OSM tag, where
                     recorded), curvature_deg_per_km
  terrain            elev_m, climb_out_m, climb_in_m (metres climbed within the piece in
                     each direction), grade_pct (average over the piece: net rise
                     outbound / length; negative is downhill leaving Kampala)
  water              water_crossings (waterways crossing the road), wetland_share
  weather            wet_days_per_year (CHIRPS days >= 10 mm, 2006-2025 mean)
  labels             place (nearest named town or village within 2 km)
"""
import glob, os
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
import xarray as xr
from shapely.geometry import Point
from shapely.ops import substring

import config as C

PIECE_M = 500
FEAT = os.path.join(C.DATA, "osm_features.gpkg")
MAJOR = {"motorway", "trunk", "primary", "secondary", "tertiary", "motorway_link",
         "trunk_link", "primary_link", "secondary_link", "tertiary_link"}
MINOR = {"residential", "unclassified", "service", "track", "living_street", "road"}

cl = gpd.read_file(C.PROBES_GPKG, layer="centrelines").to_crs(C.UTM)
pts = gpd.read_file(FEAT, layer="points").to_crs(C.UTM)
roads = gpd.read_file(FEAT, layer="roads").to_crs(C.UTM)
water = gpd.read_file(FEAT, layer="waterways").to_crs(C.UTM)
areas = gpd.read_file(FEAT, layer="areas").to_crs(C.UTM)
b = pd.read_parquet(os.path.join(C.DATA, "buildings.parquet"))
bld = gpd.GeoDataFrame(b, geometry=gpd.points_from_xy(b.longitude, b.latitude), crs=4326).to_crs(C.UTM)

# Elevation tiles (sampled tile by tile) and CHIRPS wet days
dem_src = [rasterio.open(p) for p in sorted(glob.glob(os.path.join(C.DATA, "dem", "*.tif")))]
chirps = sorted(glob.glob(os.path.join(C.CHIRPS_DIR, f"{C.CHIRPS_PREFIX}_20*.nc")))
chirps = [p for p in chirps if 2006 <= int(p[-7:-3]) <= 2025]
wet = sum((xr.open_dataset(p).precip >= 10).sum("time") for p in chirps) / len(chirps)


def elevation(xs_lonlat):
    z = np.full(len(xs_lonlat), np.nan)
    xy = np.array(xs_lonlat)
    for src in dem_src:
        b = src.bounds
        m = (xy[:, 0] >= b.left) & (xy[:, 0] < b.right) & (xy[:, 1] > b.bottom) & (xy[:, 1] <= b.top)
        if m.any():
            z[m] = [v[0] for v in src.sample(xy[m])]
    return z


def near_line(g, line, dist):
    """Rows of g within dist of line, using the spatial index."""
    return g.iloc[g.sindex.query(line, predicate="dwithin", distance=dist)]


def junctions(line, piece, corridor_line):
    """Roads that join or cross the corridor within this piece, by class."""
    buf = corridor_line.intersection(piece.buffer(200)).buffer(15)  # both carriageways, locally
    cand = near_line(roads, piece, 15)
    major = minor = 0
    for r in cand.itertuples():
        inside = r.geometry.intersection(buf)
        if inside.length > 60:  # runs along the corridor: part of it, not a junction
            continue
        if not piece.buffer(15).intersects(inside):
            continue
        if r.highway in MAJOR:
            major += 1
        elif r.highway in MINOR:
            minor += 1
    return major, minor


def curvature(line):
    L = line.length
    if L < 60:
        return 0.0
    xy = np.array([line.interpolate(d).coords[0] for d in np.arange(0, L, 20)])
    h = np.degrees(np.arctan2(np.diff(xy[:, 1]), np.diff(xy[:, 0])))
    dh = np.abs((np.diff(h) + 180) % 360 - 180)
    return float(dh.sum() / (L / 1000))


rows = []
to_ll = lambda geoms: gpd.GeoSeries(geoms, crs=C.UTM).to_crs(4326)  # noqa: E731
places = pts[pts.kind == "place"]
# Weighbridges: features within 150 m of the corridor, nearest first; one within 300 m of a
# kept one is a duplicate (often mapped as both a point and an area). Each counts once, in
# the nearest piece.
wb_all = list(pts[pts.kind == "weighbridge"].geometry)

for corridor in C.CORRIDORS:
    out = cl[(cl.corridor == corridor) & (cl.direction == "outbound")].geometry.iloc[0]
    inn = cl[(cl.corridor == corridor) & (cl.direction == "inbound")].geometry.iloc[0]
    both = out.union(inn)
    # Elevation profile every 25 m, smoothed over 250 m to remove trees and buildings
    ds = np.arange(0, out.length, 25)
    ll = to_ll([out.interpolate(d) for d in ds])
    z = pd.Series(elevation([(p.x, p.y) for p in ll])).rolling(11, center=True, min_periods=1).median()
    z = z.rolling(5, center=True, min_periods=1).mean().to_numpy()
    n = int(np.ceil(out.length / PIECE_M))
    keep_wb = []
    for g in sorted((g for g in wb_all if g.distance(out) <= 150), key=lambda g: g.distance(out)):
        if all(g.distance(k) > 300 for k in keep_wb):
            keep_wb.append(g)
    wb_piece = [int(out.project(g) // PIECE_M) for g in keep_wb]
    for i in range(n):
        a, e = i * PIECE_M, min((i + 1) * PIECE_M, out.length)
        piece = substring(out, a, e)
        mid = out.interpolate((a + e) / 2)
        sel = (ds >= a) & (ds < e)
        dz = np.diff(z[sel]) if sel.sum() > 1 else np.array([0.0])
        lon, lat = to_ll([mid]).iloc[0].coords[0]
        in_piece = lambda g, dist, line=piece: near_line(g, line, dist)  # noqa: E731
        kinds = lambda dist: in_piece(pts, dist).kind.value_counts()  # noqa: E731
        k30, k100, k200, k300 = kinds(30), kinds(100), kinds(200), kinds(300)
        jmaj, jmin = junctions(out, piece, both)
        wl = near_line(areas, piece, 0)
        wl = wl[wl.kind == "wetland"]
        mk_area = in_piece(areas[areas.kind == "market"], 200)
        near_place = near_line(places, mid, 2000)
        rows.append(dict(
            corridor=corridor, piece=i, km_start=a / 1000, km_mid=(a + e) / 2000, lon=lon, lat=lat,
            buildings_100m=len(in_piece(bld, 100)), buildings_300m=len(in_piece(bld, 300)),
            shops_200m=int(k200.get("shop", 0)),
            markets_200m=int(k200.get("market", 0)) + len(mk_area),
            fuel_200m=int(k200.get("fuel", 0)), schools_300m=int(k300.get("school", 0)),
            stops_100m=int(k100.get("bus_or_taxi_stop", 0)),
            junctions_major=jmaj, junctions_minor=jmin,
            humps=int(k30.get("speed_hump", 0) + k30.get("rumble_strip", 0)),
            signals=int(k30.get("traffic_signals", 0)), ped_crossings=int(k30.get("pedestrian_crossing", 0)),
            level_crossings=int(k30.get("level_crossing", 0)),
            police_posts=int(k30.get("checkpoint_or_police", 0)),
            weighbridges=wb_piece.count(i),
            dual=bool(inn.distance(mid) > 8),
            curvature_deg_per_km=round(curvature(piece), 1),
            elev_m=round(float(np.mean(z[sel])) if sel.any() else np.nan, 1),
            climb_out_m=round(float(dz[dz > 0].sum()), 1), climb_in_m=round(float(-dz[dz < 0].sum()), 1),
            grade_pct=round(float((z[sel][-1] - z[sel][0]) / (ds[sel][-1] - ds[sel][0]) * 100)
                            if sel.sum() > 1 else 0.0, 2),
            water_crossings=len(near_line(water, piece, 0)),
            wetland_share=round(float(wl.union_all().intersection(piece).length / piece.length)
                                if len(wl) else 0.0, 2),
            wet_days_per_year=round(float(wet.sel(latitude=lat, longitude=lon, method="nearest")), 1),
            place=(near_place.assign(d=near_place.distance(mid)).sort_values("d").name.dropna().iloc[0]
                   if near_place.name.notna().any() else None),
            geometry=piece))
    print(corridor, n, "pieces")

df = gpd.GeoDataFrame(rows, crs=C.UTM)
df.to_crs(4326).to_file(os.path.join(C.DATA, "pieces.gpkg"), layer="pieces", driver="GPKG")
df.drop(columns="geometry").to_csv(os.path.join(C.OUTPUTS, "pieces.csv"), index=False)
summary = df.drop(columns=["geometry", "lon", "lat", "piece", "km_start", "km_mid", "place"]).groupby("corridor")
print(summary.sum(numeric_only=True).T.round(0).to_string())
print("wrote outputs/pieces.csv")
