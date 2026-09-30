"""Candidate moving trucks with image patches, for training a classifier (22_truck_classifier.py).

14_trucks.py counts candidates with a fixed threshold, and the visual check showed plausible
trucks on open road but false positives from roofs and clutter in towns. This script keeps
every candidate at the loose threshold (K = 2 robust deviations), with the features the
threshold used and a 15 x 15 pixel patch of B02, B03, B04 and B08 around it, so a classifier
trained on labelled patches can separate trucks from clutter.

Same scenes and chunks as 14_trucks.py: 5 km chunks, up to six clear scenes (< 10% cloud,
2023-2025) per chunk, road = centreline buffered by 12 m.

Writes (data/trucks/):
  candidates.parquet   one row per candidate: position, date, features
  patches.npy          float16 array (n, 4, 15, 15): B02, B03, B04, B08 reflectance
  chunk_scenes.csv     one row per usable chunk-scene: road km and candidate count
"""
import os
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.features import geometry_mask
from scipy import ndimage
from shapely.geometry import shape
from shapely.ops import substring
from pyproj import Transformer

import config as C
from s2lib import CLOUDY, ENV, read, reflect, search

CHUNK_KM = 5
MAX_SCENES = 6
ROAD_M = 12
K = 2.0          # loose threshold: the classifier decides, not the threshold
MIN_BLUE = 0.06
HALF = 7         # patch is (2 * HALF + 1) pixels square
OUT = os.path.join(C.DATA, "trucks")
os.makedirs(OUT, exist_ok=True)


def candidates(item, seg_ll, corridor, k0):
    a = item["assets"]
    geom = seg_ll.__geo_interface__
    try:
        with rasterio.Env(**ENV):
            b2, tf, crs = read(a["blue"]["href"], geom, None)
            b3, _, _ = read(a["green"]["href"], geom, None)
            b4, _, _ = read(a["red"]["href"], geom, None)
            b8, _, _ = read(a["nir"]["href"], geom, None)
            scl, _, _ = read(a["scl"]["href"], geom, None, out_shape=b2.shape)
    except Exception:
        return None
    if not (b2.shape == b3.shape == b4.shape == b8.shape) or b2.size == 0:
        return None
    road = gpd.GeoSeries([seg_ll], crs=4326).to_crs(crs).buffer(ROAD_M).iloc[0]
    mask = ~geometry_mask([road], out_shape=b2.shape, transform=tf)
    valid = mask & (b2 > 0) & ~np.isin(scl, list(CLOUDY))
    if mask.sum() == 0 or valid.sum() < 0.8 * mask.sum():
        return None
    B = np.stack([reflect(b, item) for b in (b2, b3, b4, b8)])
    idx = (B[0] - B[2]) / np.maximum(B[0] + B[2], 1e-6)
    v = idx[valid]
    med, mad = np.median(v), 1.4826 * np.median(np.abs(v - np.median(v))) + 1e-4
    blue = valid & (idx > med + K * mad) & (B[0] > MIN_BLUE)
    red = valid & (idx < med - K * mad)
    red_lab, _ = ndimage.label(red)
    lab, n = ndimage.label(blue & ndimage.binary_dilation(red, iterations=2))
    km = gpd.GeoSeries([seg_ll], crs=4326).to_crs(C.UTM).length.iloc[0] / 1000
    to_ll = Transformer.from_crs(crs, 4326, always_xy=True)
    date = item["properties"]["datetime"][:10]
    road_bright = float(np.median(B[:3, valid].mean(axis=0)))
    rows, patches = [], []
    Bp = np.pad(B, ((0, 0), (HALF, HALF), (HALF, HALF)), constant_values=0)
    for j in range(1, n + 1):
        comp = lab == j
        rr, cc = np.argwhere(comp).mean(axis=0)
        peak = np.unravel_index(np.argmax(np.where(comp, idx, -9)), idx.shape)
        # the red partner: red pixels within 2 px of the blue component
        near = ndimage.binary_dilation(comp, iterations=2) & red
        rp = np.argwhere(near)
        red_r, red_c = rp.mean(axis=0) if len(rp) else (rr, cc)
        x, y = tf * (peak[1] + 0.5, peak[0] + 0.5)
        lon, lat = to_ll.transform(x, y)
        r0, c0 = peak
        patches.append(Bp[:, r0:r0 + 2 * HALF + 1, c0:c0 + 2 * HALF + 1].astype(np.float16))
        rows.append(dict(
            corridor=corridor, chunk_km=k0, scene=item["id"], date=date, lon=lon, lat=lat,
            blue_z=float((idx[peak] - med) / mad), red_z=float((idx[near].min() - med) / mad) if len(rp) else 0.0,
            blue_px=int(comp.sum()), red_px=int(near.sum()),
            offset_px=float(np.hypot(red_r - rr, red_c - cc)),
            b2=float(B[0][peak]), b3=float(B[1][peak]), b4=float(B[2][peak]), b8=float(B[3][peak]),
            road_bright=road_bright, road_mad=float(mad), cloud=float(item["properties"]["eo:cloud_cover"])))
    return rows, patches, dict(corridor=corridor, chunk_km=k0, scene=item["id"], date=date, road_km=km,
                               n_candidates=n)


rows, patches, cs = [], [], []
cl = gpd.read_file(C.PROBES_GPKG, layer="centrelines")
for corridor in C.CORRIDORS:
    line_ll = cl[(cl.corridor == corridor) & (cl.direction == "outbound")].geometry.iloc[0]
    line_utm = gpd.GeoSeries([line_ll], crs=4326).to_crs(C.UTM).iloc[0]
    items = search(line_ll.bounds)
    print(f"{corridor}: {len(items)} clear scenes", flush=True)
    jobs = []
    for k0 in np.arange(0, line_utm.length / 1000, CHUNK_KM):
        seg_utm = substring(line_utm, k0 * 1000, min((k0 + CHUNK_KM) * 1000, line_utm.length))
        seg_ll = gpd.GeoSeries([seg_utm], crs=C.UTM).to_crs(4326).iloc[0]
        cover = [it for it in items if shape(it["geometry"]).contains(seg_ll)]
        cover = sorted(cover, key=lambda it: it["properties"]["eo:cloud_cover"])[:MAX_SCENES]
        jobs += [(it, seg_ll, k0) for it in cover]
    with ThreadPoolExecutor(8) as pool:
        for res in pool.map(lambda j: candidates(j[0], j[1], corridor, float(j[2])), jobs):
            if res is None:
                continue
            r, p, c = res
            rows += r
            patches += p
            cs.append(c)
    print(f"  {sum(c['corridor'] == corridor for c in cs)} usable chunk-scenes, "
          f"{sum(r['corridor'] == corridor for r in rows)} candidates so far", flush=True)

pd.DataFrame(rows).to_parquet(os.path.join(OUT, "candidates.parquet"))
np.save(os.path.join(OUT, "patches.npy"), np.stack(patches))
pd.DataFrame(cs).to_csv(os.path.join(OUT, "chunk_scenes.csv"), index=False)
print(f"wrote {len(rows)} candidates from {len(cs)} chunk-scenes to {OUT}")
