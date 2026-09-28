"""Copernicus GLO-30 elevation tiles covering every corridor, into data/dem/.

One 1-degree tile (about 30 MB) per degree square that the centrelines touch. Copernicus DEM is a surface model: it includes
trees and buildings, so 05_features.py smooths the profile before computing grades.
Source: Copernicus DEM GLO-30, (c) DLR/Airbus, via the AWS open data registry.
"""
import math, os
import geopandas as gpd
import requests

import config as C

URL = "https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_{t}_DEM/Copernicus_DSM_COG_10_{t}_DEM.tif"

out_dir = os.path.join(C.DATA, "dem")
os.makedirs(out_dir, exist_ok=True)
cl = gpd.read_file(C.PROBES_GPKG, layer="centrelines")
squares = set()
for line in cl.geometry:
    for x, y in line.segmentize(0.01).coords:
        squares.add((math.floor(y), math.floor(x)))
TILES = [f"{'N' if la >= 0 else 'S'}{abs(la):02d}_00_E{lo:03d}_00" for la, lo in sorted(squares)]
print("tiles:", TILES)
for t in TILES:
    path = os.path.join(out_dir, f"{t}.tif")
    if os.path.exists(path):
        continue
    with requests.get(URL.format(t=t), stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(path + ".part", "wb") as f:
            for block in r.iter_content(1 << 20):
                f.write(block)
    os.replace(path + ".part", path)
    print("wrote", path)
