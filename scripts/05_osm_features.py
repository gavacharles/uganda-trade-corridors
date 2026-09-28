"""OpenStreetMap features within 1 km of either corridor, into data/osm_features.gpkg.

Layers:
  points     traffic calming, signals, crossings, level crossings, toll/police/
             weighbridge points, fuel, markets, schools, bus/taxi stops, shops, places
  roads      every road (any class) that touches the 1 km zone, for counting junctions
  waterways  rivers, streams, drains and canals
  areas      markets, retail/commercial land, wetlands
"""
import os, re
import geopandas as gpd
import pandas as pd
import pyogrio

import config as C

PBF = C.PBF
OUT = os.path.join(C.DATA, "osm_features.gpkg")
BUFFER_M = 1000


def tag(df, key):
    return df.other_tags.fillna("").str.extract(rf'"{re.escape(key)}"=>"([^"]+)"', expand=False)


def classify_point(r):
    """One label per point, most traffic-relevant first."""
    if isinstance(r.traffic_calming, str):
        return "rumble_strip" if r.traffic_calming == "rumble_strip" else "speed_hump"
    if r.highway == "traffic_signals":
        return "traffic_signals"
    if r.railway == "level_crossing":
        return "level_crossing"
    if r.highway == "crossing":
        return "pedestrian_crossing"
    if r.amenity == "weighbridge" or r.man_made == "weighbridge":
        return "weighbridge"
    if r.barrier in ("toll_booth", "checkpoint", "border_control") or r.amenity == "police":
        return "checkpoint_or_police"
    if r.amenity == "fuel":
        return "fuel"
    if r.amenity == "marketplace":
        return "market"
    if r.amenity in ("school", "college", "university", "kindergarten"):
        return "school"
    if r.highway == "bus_stop" or r.amenity in ("bus_station", "taxi") or isinstance(r.public_transport, str):
        return "bus_or_taxi_stop"
    if isinstance(r.shop, str):
        return "shop"
    if r.place in ("city", "town", "village", "hamlet", "suburb", "neighbourhood", "locality"):
        return "place"
    return None


cl = gpd.read_file(C.PROBES_GPKG, layer="centrelines")
zone_utm = cl.to_crs(C.UTM).buffer(BUFFER_M).union_all()
zone = gpd.GeoSeries([zone_utm], crs=C.UTM).to_crs(4326)
bbox = tuple(zone.total_bounds)


def clip(df):
    df = df.set_crs(4326, allow_override=True)
    df["geometry"] = df.geometry.make_valid()  # a few OSM multipolygons are malformed
    return df[df.intersects(zone.iloc[0])].copy()


# Points
pts = clip(pyogrio.read_dataframe(PBF, layer="points", bbox=bbox))
for k in ("traffic_calming", "railway", "amenity", "shop", "public_transport"):
    pts[k] = tag(pts, k)
pts["kind"] = pts.apply(classify_point, axis=1)
# Weighbridges are rarely tagged; find them by name ("Weigh Bridge", "Weighing Station", typos)
WEIGH = r"(?i)weigh ?(bridge|station|staion)|weighing"
pts.loc[pts.name.fillna("").str.contains(WEIGH), "kind"] = "weighbridge"
pts = pts[pts.kind.notna()][["osm_id", "name", "kind", "place", "geometry"]]

# Roads (all classes) for junctions
roads = clip(pyogrio.read_dataframe(PBF, layer="lines", bbox=bbox, where="highway IS NOT NULL"))
roads = roads[["osm_id", "name", "highway", "geometry"]]

# Waterways
water = clip(pyogrio.read_dataframe(PBF, layer="lines", bbox=bbox, where="waterway IS NOT NULL"))
water = water[["osm_id", "name", "waterway", "geometry"]]

# Areas
areas = clip(pyogrio.read_dataframe(
    PBF, layer="multipolygons", bbox=bbox,
    where="amenity = 'marketplace' OR landuse IN ('retail','commercial') OR natural = 'wetland'"))
areas["kind"] = areas.apply(lambda r: "wetland" if r.natural == "wetland" else
                            ("market" if r.amenity == "marketplace" else "commercial"), axis=1)
areas = areas[["osm_id", "osm_way_id", "name", "kind", "geometry"]]
wb = clip(pyogrio.read_dataframe(PBF, layer="multipolygons", bbox=bbox, where="name IS NOT NULL"))
wb = wb[wb.name.str.contains(WEIGH)]
wb = gpd.GeoDataFrame(dict(osm_id=wb.osm_way_id.fillna(wb.osm_id), name=wb.name, kind="weighbridge", place=None),
                      geometry=wb.geometry.representative_point(), crs=4326)
pts = pd.concat([pts, wb], ignore_index=True)

if os.path.exists(OUT):
    os.remove(OUT)
for name, df in (("points", pts), ("roads", roads), ("waterways", water), ("areas", areas)):
    df.to_file(OUT, layer=name, driver="GPKG")
print(pts.kind.value_counts().to_string())
print(f"roads {len(roads):,}; waterways {len(water):,}; areas", areas.kind.value_counts().to_dict())
print("wrote", OUT)
