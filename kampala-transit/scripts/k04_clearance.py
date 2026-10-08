"""How much room is there for a busway or tramway? Clear width between building lines along the candidates.

    python kampala-transit/scripts/k04_clearance.py      (after k03_buildings.py)

Every 100 m along each candidate corridor's core length, a cross-section is cast 60 m to each side
of the centreline; the clear width is the distance to the first building on the left plus the first
on the right (60 m where there is none). Against two assumed cross-sections:
  FULL 30 m   median busway or double track with stations, one general lane each way plus a
              parking/loading lane, sidewalks
  TIGHT 24 m  median busway or double track with stations, one general lane each way, sidewalks
the share of the corridor where it fits, and the buildings whose footprint lies inside the width
(the demolitions it would take) are counted.

Writes outputs/clearance_sections.gpkg and outputs/clearance.csv.
"""
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import shapely
from shapely import STRtree

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
KT = os.path.join(ROOT, "kampala-transit")
UTM, STEP, REACH = 32636, 100.0, 60.0
WIDTHS = {"full": 30.0, "tight": 24.0}
CBD = (32.5825, 0.3136)

E = gpd.read_file(os.path.join(KT, "outputs", "edges.gpkg"))
C = pd.read_csv(os.path.join(KT, "outputs", "corridors_core.csv"))
cand = C[~C.screen.str.contains("express|priority only")]
c = E.geometry.interpolate(0.5, normalized=True)
E["cbd_km"] = np.hypot((c.x - CBD[0]) * 111.32, (c.y - CBD[1]) * 111.32)
E["route"] = E.ref.fillna(E.name).fillna("")
E = E[(E.cbd_km <= 20) & E.route.isin(cand.route) & E.highway.isin(["motorway", "trunk", "primary", "secondary"])]
E = E.to_crs(UTM)

B = pd.read_parquet(os.path.join(KT, "data", "buildings_road.parquet"))
bg = gpd.GeoSeries(shapely.from_wkt(B.geometry.values), crs=4326).to_crs(UTM)
B = gpd.GeoDataFrame(B.drop(columns="geometry"), geometry=bg.values, crs=UTM)
tree = STRtree(B.geometry.values)
print(len(B), "footprints near main roads")

secs = []
for route, d in E.groupby("route"):
    for g in d.geometry:
        L = g.length
        for s in np.arange(STEP / 2, L, STEP):
            p, q = g.interpolate(s), g.interpolate(min(s + 5, L))
            dx, dy = q.x - p.x, q.y - p.y
            n = np.hypot(dx, dy) or 1
            nx, ny = -dy / n, dx / n
            side = []
            for sgn in (1, -1):
                ray = shapely.LineString([(p.x, p.y), (p.x + sgn * nx * REACH, p.y + sgn * ny * REACH)])
                hit = tree.query(ray, predicate="intersects")
                dist = REACH
                for h in hit:
                    x = ray.intersection(B.geometry.values[h])
                    if not x.is_empty:
                        dist = min(dist, p.distance(x))
                side.append(dist)
            secs.append(dict(route=route, x=p.x, y=p.y, left=side[0], right=side[1], width=side[0] + side[1]))
S = pd.DataFrame(secs)
S = gpd.GeoDataFrame(S, geometry=gpd.points_from_xy(S.x, S.y), crs=UTM)
print(len(S), "cross-sections")

# land use (k07) of every cross-section and of every building inside the corridor
import rasterio  # noqa: E402
with rasterio.open(os.path.join(KT, "outputs", "landuse.tif")) as lu:
    LUA, LUT = lu.read(1), lu.transform
CLS = ["wetland / water", "commercial / industrial", "institutional", "dense small-plot", "planned / larger-plot",
       "peri-urban", "rural / open"]


def lu_of(lon, lat):
    r, c = rasterio.transform.rowcol(LUT, lon, lat)
    r, c = np.clip(np.asarray(r), 0, LUA.shape[0] - 1), np.clip(np.asarray(c), 0, LUA.shape[1] - 1)
    return np.array(CLS)[LUA[r, c]]


S4 = S.to_crs(4326)
S["landuse"] = lu_of(S4.geometry.x.values, S4.geometry.y.values)
B["landuse"] = lu_of(B.longitude.values, B.latitude.values)
demo, demo_pts = [], []
rows = []
for route, s in S.groupby("route"):
    d = E[E.route == route]
    line = d.geometry.union_all()
    r = dict(route=route, km=round(d.length.sum() / 1000, 1), width_median=s.width.median(),
             width_p10=s.width.quantile(0.1))
    for k, w in WIDTHS.items():
        r[f"fits_{k}"] = (s.width >= w).mean()
        band = line.buffer(w / 2)
        idx = tree.query(band, predicate="intersects")
        r[f"demolish_{k}"] = len(idx)
        r[f"demolish_{k}_per_km"] = len(idx) / max(r["km"], 0.1)
        r[f"demolish_{k}_m2"] = float(B.area_in_meters.values[idx].sum())
        if k == "tight":
            demo_pts.append(pd.DataFrame(dict(route=route, lon=B.longitude.values[idx], lat=B.latitude.values[idx],
                                              area_m2=B.area_in_meters.values[idx])))
            for cl, n in pd.Series(B.landuse.values[idx]).value_counts().items():
                demo.append(dict(route=route, landuse=cl, buildings=n,
                                 m2=float(B.area_in_meters.values[idx][B.landuse.values[idx] == cl].sum())))
    for cl, sh in s.landuse.value_counts(normalize=True).items():
        r[f"frontage_{cl}"] = sh
    r["tight_fail_dense"] = ((s.width < WIDTHS["tight"]) & (s.landuse == "dense small-plot")).mean()
    rows.append(r)
R = pd.DataFrame(rows).merge(C[["route", "name", "screen", "load_mean", "catch_pop_per_km"]], on="route")
R = R.sort_values("load_mean", ascending=False)
S.to_crs(4326).to_file(os.path.join(KT, "outputs", "clearance_sections.gpkg"), driver="GPKG")
R.to_csv(os.path.join(KT, "outputs", "clearance.csv"), index=False)
pd.concat(demo_pts).to_csv(os.path.join(KT, "outputs", "demolished_buildings.csv"), index=False)
pd.DataFrame(demo).merge(C[["route", "name"]], on="route").to_csv(os.path.join(KT, "outputs", "demolitions_by_landuse.csv"),
                                                                 index=False)
print(R[["name", "km", "width_median", "width_p10", "fits_full", "fits_tight", "demolish_full", "demolish_tight",
         "demolish_tight_per_km"]].round(2).to_string())
