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
import shapely

import config as C



def read_osm(layer, **kw):
    """One layer from every extract in config.PBFS, concatenated. Only features meeting the 1 km
    zone are kept as they are read (a spatial mask), so memory holds the corridors' features,
    not whole countries' (the regional study's bounding box covers most of the subcontinent)."""
    return pd.concat([pyogrio.read_dataframe(pbf, layer=layer, mask=MASK, **kw) for pbf in C.PBFS],
                     ignore_index=True)

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
# Read filter: the zone grown 100 m then simplified by about 50 m, so it always covers the zone;
# clip() then keeps exactly what meets the zone
MASK = gpd.GeoSeries([zone_utm.buffer(100)], crs=C.UTM).to_crs(4326).iloc[0].simplify(0.0005)


ZONE = zone.iloc[0]
shapely.prepare(ZONE)   # one prepared shape: fast tests even when the zone runs to 15,000 km of road


def clip(df, repair=False):
    df = df.set_crs(4326, allow_override=True)
    if repair:   # a few OSM multipolygons are malformed
        df["geometry"] = df.geometry.make_valid()
    return df[shapely.intersects(ZONE, df.geometry.values)].copy()


# Points
pts = clip(read_osm("points"))
for k in ("traffic_calming", "railway", "amenity", "shop", "public_transport"):
    pts[k] = tag(pts, k)
pts["kind"] = pts.apply(classify_point, axis=1)
# Weighbridges are rarely tagged; find them by name ("Weigh Bridge", "Weighing Station", typos)
WEIGH = r"(?i)weigh ?(bridge|station|staion)|weighing"
pts.loc[pts.name.fillna("").str.contains(WEIGH), "kind"] = "weighbridge"
pts = pts[pts.kind.notna()][["osm_id", "name", "kind", "place", "geometry"]]

# Roads (all classes) for junctions
roads = clip(read_osm("lines", where="highway IS NOT NULL"))
roads = roads[["osm_id", "name", "highway", "geometry"]]

# Waterways
water = clip(read_osm("lines", where="waterway IS NOT NULL"))
water = water[["osm_id", "name", "waterway", "geometry"]]

# Areas
areas = clip(repair=True, df=read_osm("multipolygons",
    where="amenity = 'marketplace' OR landuse IN ('retail','commercial') OR natural = 'wetland'"))
areas["kind"] = areas.apply(lambda r: "wetland" if r.natural == "wetland" else
                            ("market" if r.amenity == "marketplace" else "commercial"), axis=1)
areas = areas[["osm_id", "osm_way_id", "name", "kind", "geometry"]]
wb = clip(read_osm("multipolygons", where="name IS NOT NULL"), repair=True)
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
