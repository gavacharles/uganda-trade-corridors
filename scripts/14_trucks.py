"""Moving trucks along the corridors from Sentinel-2 (experimental).

Principle (Fisser et al. 2022, Remote Sensing of Environment): Sentinel-2 records the
blue, green and red bands a fraction of a second apart, so a large moving vehicle shows
up as a blue pixel beside a red one along the road, while stationary objects do not.
This is a simplified, unsupervised version of that idea, not the authors' trained model:

  1. Scenes: Sentinel-2 L2A from Earth Search (AWS open data), 2023-2025, < 10% cloud.
  2. For each 5 km chunk of corridor and up to MAX_SCENES clear scenes, read B02, B04 and
     the scene classification (SCL) for the chunk's bounding box only.
  3. Road mask: centreline buffered by ROAD_M. Pixels flagged cloud/shadow in SCL dropped;
     a chunk-scene is used only if at least 80% of its road pixels are clear.
  4. Candidate: a road pixel whose blue-red index (B02-B04)/(B02+B04) exceeds the chunk's
     road median by K_MAD robust deviations and is bright in blue, with a red-dominant
     pixel (index below median by K_MAD deviations) within 2 pixels. Connected blue
     candidates count as one vehicle. K_MAD = 2.5 was chosen on a test chunk (Malaba road
     km 35-40, 27 Feb 2025) where 2 and 3 gave 5 and 1 vehicles per 5 km; a road carrying
     about 1,000 trucks a day at 60 km/h holds about 0.7 per km at any moment. Counts at
     K = 2 and 3 are reported as a range.
  5. Trucks per km = detections / road km, averaged over the scenes used.

Writes outputs/trucks_chunks.csv (per chunk: scenes used, mean and max trucks per km),
figures/f06_trucks.png and, for checking by eye, figures/trucks_check/ (RGB chips of the
strongest detections). Treat results as a relative index until checked against the chips.
"""
import os
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.features import geometry_mask
from scipy import ndimage
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config as C
from s2lib import CLOUDY, ENV, read, reflect, search

CHUNK_KM = 5
MAX_SCENES = 6
ROAD_M = 12
K_MAD = 2.5    # main threshold (robust deviations); counts at 2 and 3 are kept as a range
K_RANGE = (2.0, 3.0)
MIN_BLUE = 0.06  # minimum B02 reflectance for a candidate
CHECK = os.path.join(C.FIGURES, "trucks_check")
os.makedirs(CHECK, exist_ok=True)


def detect(item, chunk_line_ll):
    """Detections (count, road km, chips) for one scene over one chunk, or None if not usable."""
    a = item["assets"]
    geom = chunk_line_ll.__geo_interface__
    try:
        with rasterio.Env(**ENV):
            b2, tf, crs = read(a["blue"]["href"], geom, None)
            b4, _, _ = read(a["red"]["href"], geom, None)
            b3, _, _ = read(a["green"]["href"], geom, None)
            scl, _, _ = read(a["scl"]["href"], geom, None, out_shape=b2.shape)
    except Exception:
        return None
    if b2.shape != b4.shape or b2.size == 0:
        return None
    road = gpd.GeoSeries([chunk_line_ll], crs=4326).to_crs(crs).buffer(ROAD_M).iloc[0]
    mask = ~geometry_mask([road], out_shape=b2.shape, transform=tf)
    valid = mask & (b2 > 0) & ~np.isin(scl, list(CLOUDY))
    if mask.sum() == 0 or valid.sum() < 0.8 * mask.sum():
        return None
    B2, B3, B4 = reflect(b2, item), reflect(b3, item), reflect(b4, item)
    idx = (B2 - B4) / np.maximum(B2 + B4, 1e-6)
    v = idx[valid]
    med, mad = np.median(v), 1.4826 * np.median(np.abs(v - np.median(v))) + 1e-4
    def count(k):
        blue = valid & (idx > med + k * mad) & (B2 > MIN_BLUE)
        red = valid & (idx < med - k * mad)
        return ndimage.label(blue & ndimage.binary_dilation(red, iterations=2))
    lab, n = count(K_MAD)
    n_lo, n_hi = count(K_RANGE[1])[1], count(K_RANGE[0])[1]
    km = gpd.GeoSeries([chunk_line_ll], crs=4326).to_crs(C.UTM).length.iloc[0] / 1000
    chips = []
    if n:
        strength = ndimage.maximum(idx - med, lab, index=np.arange(1, n + 1))
        for j in np.argsort(strength)[::-1][:2]:
            rr, cc = np.argwhere(lab == j + 1)[0]
            r0, c0 = max(rr - 15, 0), max(cc - 15, 0)
            rgb = np.dstack([B4, B3, B2])[r0:rr + 16, c0:cc + 16]
            chips.append((float(strength[j]), np.clip(rgb / 0.25, 0, 1), rr - r0, cc - c0,
                          item["properties"]["datetime"][:10]))
    return n, km, chips, n_lo, n_hi


rows, all_chips = [], []
cl = gpd.read_file(C.PROBES_GPKG, layer="centrelines")
for corridor in C.CORRIDORS:
    line_ll = cl[(cl.corridor == corridor) & (cl.direction == "outbound")].geometry.iloc[0]
    line_utm = gpd.GeoSeries([line_ll], crs=4326).to_crs(C.UTM).iloc[0]
    items = search(line_ll.bounds)
    print(f"{corridor}: {len(items)} clear scenes", flush=True)
    from shapely.geometry import shape
    from shapely.ops import substring
    jobs = []
    for k0 in np.arange(0, line_utm.length / 1000, CHUNK_KM):
        seg_utm = substring(line_utm, k0 * 1000, min((k0 + CHUNK_KM) * 1000, line_utm.length))
        seg_ll = gpd.GeoSeries([seg_utm], crs=C.UTM).to_crs(4326).iloc[0]
        cover = [it for it in items if shape(it["geometry"]).contains(seg_ll)]
        cover = sorted(cover, key=lambda it: it["properties"]["eo:cloud_cover"])[:MAX_SCENES]
        jobs.append((k0, seg_ll, cover))
    with ThreadPoolExecutor(8) as pool:
        for k0, seg_ll, cover in jobs:
            res = [r for r in pool.map(lambda it: detect(it, seg_ll), cover) if r is not None]
            per_km = [r_[0] / r_[1] for r_ in res]
            rows.append(dict(corridor=corridor, km_from=k0, km_to=k0 + CHUNK_KM, scenes_used=len(res),
                             trucks_per_km_mean=np.mean(per_km) if res else np.nan,
                             trucks_per_km_max=np.max(per_km) if res else np.nan,
                             trucks_per_km_low=np.mean([r_[3] / r_[1] for r_ in res]) if res else np.nan,
                             trucks_per_km_high=np.mean([r_[4] / r_[1] for r_ in res]) if res else np.nan))
            for _, _, chips, _, _ in res:
                all_chips += [(corridor, k0) + c for c in chips]
    done = pd.DataFrame(rows)
    d = done[done.corridor == corridor]
    print(f"  {len(d)} chunks, {int((d.scenes_used > 0).sum())} with data, mean {d.trucks_per_km_mean.mean():.2f} "
          f"trucks/km", flush=True)

T = pd.DataFrame(rows)
T.round(3).to_csv(os.path.join(C.OUTPUTS, "trucks_chunks.csv"), index=False)

# Chips of the strongest detections, for checking by eye
all_chips.sort(key=lambda c: -c[2])
fig, axs = plt.subplots(4, 6, figsize=(12, 8.6), facecolor="white")
for ax, (corridor, k0, s, rgb, r, c, date) in zip(axs.ravel(), all_chips[:24]):
    ax.imshow(rgb, interpolation="nearest")
    ax.add_patch(plt.Circle((c, r), 3, fill=False, color="yellow", linewidth=1.2))
    ax.set_title(f"{C.CORRIDORS[corridor]['short']} km {k0:.0f}\n{date}", fontsize=7)
    ax.set_axis_off()
for ax in axs.ravel()[len(all_chips):]:
    ax.set_axis_off()
fig.suptitle("Strongest truck candidates (Sentinel-2 true colour, 10 m pixels; circle = detection). "
             "Check: a truck shows as a blue-green-red streak along the road.", fontsize=10)
fig.savefig(os.path.join(CHECK, "strongest_candidates.png"), dpi=130, bbox_inches="tight")
plt.close(fig)

# Profile figure
fig, axs = plt.subplots(len(C.CORRIDORS), 1, figsize=(13, 2.8 * len(C.CORRIDORS)), facecolor="#fcfcfb",
                        gridspec_kw=dict(hspace=0.8))
for ax, (corridor, cfg) in zip(axs, C.CORRIDORS.items()):
    d = T[T.corridor == corridor]
    ax.bar(d.km_from + CHUNK_KM / 2, d.trucks_per_km_mean, width=CHUNK_KM * 0.9, color="#0d2d57", linewidth=0)
    miss = d[d.scenes_used == 0]
    ax.bar(miss.km_from + CHUNK_KM / 2, np.full(len(miss), 0.02), width=CHUNK_KM * 0.9, color="#d8d5ce", linewidth=0)
    for s_ in ("top", "right", "left"):
        ax.spines[s_].set_visible(False)
    ax.grid(axis="y", color="#e4e3df", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=8, length=0, colors="#52514e")
    ax.set_xlim(0, d.km_to.max())
    ax.set_title(f"{cfg['label']}: moving-truck candidates per km, mean over clear scenes "
                 f"({int(d.scenes_used.median())} per 5 km, median)", loc="left", fontsize=9.5)
axs[-1].set_xlabel("km from Kampala", fontsize=8.5)
fig.suptitle("Trucks seen from space (experimental index, Sentinel-2 2023–2025)", x=0.125, ha="left", fontsize=14)
fig.savefig(os.path.join(C.FIGURES, "f06_trucks.png"), dpi=150, bbox_inches="tight")
print("wrote outputs/trucks_chunks.csv, figures/f06_trucks.png, trucks_check/strongest_candidates.png")
