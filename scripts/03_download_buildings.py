"""Buildings within 1 km of either corridor, from Google Open Buildings v3.

Streams every Open Buildings S2 tile that touches the corridors (listed in Google's
tile index; each is 1-2 GB and is not saved) and keeps building centroids within 1 km
of any centreline, with footprint area and detection confidence. Writes
data/buildings.parquet. The area covered is saved in data/buildings_zone.gpkg; a later
run (after corridors are added or extended) fetches only the new area and appends.

Source: Google Open Buildings v3 (CC BY-4.0 / ODbL), imagery mostly 2020-2022.
"""
import gzip, io, os
import pandas as pd
import geopandas as gpd
import requests
from shapely import prepared

import config as C

TILES = "https://openbuildings-public-dot-gweb-research.uw.r.appspot.com/public/tiles.geojson"
BUFFER_M = 1000
OUT = os.path.join(C.DATA, "buildings.parquet")
ZONE = os.path.join(C.DATA, "buildings_zone.gpkg")

cl = gpd.read_file(C.PROBES_GPKG, layer="centrelines")
full_zone = gpd.GeoSeries([cl.to_crs(C.UTM).buffer(BUFFER_M).union_all()], crs=C.UTM).to_crs(4326).iloc[0]
zone = full_zone
if os.path.exists(ZONE) and os.path.exists(OUT):
    done = gpd.read_file(ZONE).union_all()
    zone = full_zone.difference(done)
    print(f"already covered; fetching only the new area ({zone.area / full_zone.area:.0%} of the zone)")
    if zone.is_empty:
        raise SystemExit("nothing new to fetch")
x0, y0, x1, y1 = zone.bounds
pz = prepared.prep(zone)

tiles = gpd.read_file(TILES)
tiles = tiles[tiles.intersects(zone)]
print(f"{len(tiles)} tile(s): {', '.join(tiles.tile_id.astype(str))} ({tiles.size_mb.sum():,.0f} MB)")

keep, seen = [], 0
for url in tiles.tile_url:
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        text = io.TextIOWrapper(gzip.GzipFile(fileobj=r.raw), encoding="utf-8")
        for chunk in pd.read_csv(text, chunksize=500_000,
                                 usecols=["latitude", "longitude", "area_in_meters", "confidence"]):
            seen += len(chunk)
            c = chunk[chunk.longitude.between(x0, x1) & chunk.latitude.between(y0, y1)]
            if len(c):
                pts = gpd.points_from_xy(c.longitude, c.latitude)
                keep.append(c[[pz.contains(p) for p in pts]])
            print(f"{seen / 1e6:.1f} M buildings read, {sum(len(k) for k in keep):,} kept", flush=True)

if os.path.exists(ZONE) and os.path.exists(OUT):
    keep.append(pd.read_parquet(OUT))
out = pd.concat(keep, ignore_index=True).drop_duplicates(["latitude", "longitude"])
out.to_parquet(OUT)
gpd.GeoDataFrame(geometry=[full_zone], crs=4326).to_file(ZONE, driver="GPKG")
print(f"wrote {OUT}: {len(out):,} buildings within {BUFFER_M} m of the corridors")
