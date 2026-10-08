"""Building footprints for Greater Kampala (Google Open Buildings v3), streamed tile by tile.

    python kampala-transit/scripts/k03_buildings.py

Keeps, for the study box:
  kampala-transit/data/buildings_pts.parquet   every building: centroid, footprint area, confidence
  kampala-transit/data/buildings_road.parquet  footprint polygons (WKT) of buildings within 80 m of a
                                               trunk, primary, secondary or bypass centreline, for
                                               measuring the clear width between building lines
Tiles are 1-2 GB of gzipped CSV and are read in chunks and not saved.
Source: Google Open Buildings v3 (CC BY-4.0 / ODbL), imagery mostly 2020-2022.
"""
import gzip, os
import numpy as np
import pandas as pd
import geopandas as gpd
import requests
import shapely

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(ROOT, "kampala-transit", "data")
os.makedirs(DATA, exist_ok=True)
BOX = (32.35, 0.02, 32.90, 0.55)
TILES = "https://openbuildings-public-dot-gweb-research.uw.r.appspot.com/public/tiles.geojson"
UTM = 32636

edges = gpd.read_file(os.path.join(ROOT, "kampala-transit", "outputs", "edges.gpkg"))
main = edges[edges.highway.isin(["motorway", "trunk", "primary", "secondary"])]
near = shapely.prepared.prep(main.to_crs(UTM).buffer(80).union_all())

box = shapely.box(*BOX)
tiles = gpd.read_file(TILES)
tiles = tiles[tiles.intersects(box)]
print(f"{len(tiles)} tile(s), {tiles.size_mb.sum():,.0f} MB", flush=True)
pts, polys = [], []
for t in tiles.itertuples():
    with requests.get(t.tile_url, stream=True, timeout=600) as r:
        r.raise_for_status()
        with gzip.open(r.raw) as fh:
            for ch in pd.read_csv(fh, chunksize=250_000,
                                  usecols=["latitude", "longitude", "area_in_meters", "confidence", "geometry"]):
                ch = ch[ch.longitude.between(BOX[0], BOX[2]) & ch.latitude.between(BOX[1], BOX[3])]
                if not len(ch):
                    continue
                pts.append(ch[["latitude", "longitude", "area_in_meters", "confidence"]].astype("float32"))
                xy = gpd.GeoSeries(gpd.points_from_xy(ch.longitude, ch.latitude), crs=4326).to_crs(UTM)
                keep = np.fromiter((near.contains(p) for p in xy), bool, len(xy))
                if keep.any():
                    polys.append(ch.loc[ch.index[keep], ["latitude", "longitude", "area_in_meters", "geometry"]])
                print(f"  tile {t.tile_id}: {sum(len(p) for p in pts):,} buildings, "
                      f"{sum(len(p) for p in polys):,} near main roads", flush=True)
pd.concat(pts).reset_index(drop=True).to_parquet(os.path.join(DATA, "buildings_pts.parquet"))
pd.concat(polys).reset_index(drop=True).to_parquet(os.path.join(DATA, "buildings_road.parquet"))
print("done", flush=True)
