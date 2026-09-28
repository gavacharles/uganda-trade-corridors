"""Debug 14_trucks.py on one chunk: print each stage's pixel counts and save the image."""
import importlib.util, os, sys
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.features import geometry_mask
from shapely.ops import substring
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.argv = [sys.argv[0]]
import config as C

src = open(os.path.join(os.path.dirname(__file__), "14_trucks.py")).read().split("rows, all_chips = [], []")[0]
T = {}
exec(compile(src, "14_trucks_head", "exec"), T)  # functions and settings only

cl = gpd.read_file(C.PROBES_GPKG, layer="centrelines")
line = cl[(cl.corridor == "kampala_malaba") & (cl.direction == "outbound")].geometry.iloc[0]
utm = gpd.GeoSeries([line], crs=4326).to_crs(C.UTM).iloc[0]
seg = gpd.GeoSeries([substring(utm, 35000, 40000)], crs=C.UTM).to_crs(4326).iloc[0]  # km 35-40, open-ish road
items = T["search"](seg.bounds)
print("scenes over chunk:", len(items))
from shapely.geometry import shape
items = sorted([i for i in items if shape(i["geometry"]).contains(seg)], key=lambda i: i["properties"]["eo:cloud_cover"])
it = items[0]
print("scene", it["id"], it["properties"]["eo:cloud_cover"], "baseline", it["properties"].get("s2:processing_baseline"))
with rasterio.Env(**T["ENV"]):
    b2, tf, crs = T["read"](it["assets"]["blue"]["href"], seg.__geo_interface__, None)
    b3, _, _ = T["read"](it["assets"]["green"]["href"], seg.__geo_interface__, None)
    b4, _, _ = T["read"](it["assets"]["red"]["href"], seg.__geo_interface__, None)
    scl, _, _ = T["read"](it["assets"]["scl"]["href"], seg.__geo_interface__, None, out_shape=b2.shape)
print("shape", b2.shape, "DN range B02", b2.min(), np.percentile(b2, [5, 50, 95]), "crs", crs)
road = gpd.GeoSeries([seg], crs=4326).to_crs(crs).buffer(T["ROAD_M"]).iloc[0]
mask = ~geometry_mask([road], out_shape=b2.shape, transform=tf)
valid = mask & (b2 > 0) & ~np.isin(scl, list(T["CLOUDY"]))
print("road px", mask.sum(), "valid", valid.sum(), "SCL classes on road", np.unique(scl[mask], return_counts=True))
B2, B3, B4 = T["reflect"](b2, it), T["reflect"](b3, it), T["reflect"](b4, it)
idx = (B2 - B4) / np.maximum(B2 + B4, 1e-6)
v = idx[valid]
med, mad = np.median(v), 1.4826 * np.median(np.abs(v - np.median(v))) + 1e-4
print("road B02 refl pct", np.percentile(B2[valid], [5, 50, 95]).round(3), "idx med", round(med, 3), "mad", round(mad, 4),
      "idx pct", np.percentile(v, [1, 5, 50, 95, 99]).round(3))
for k in (2, 3, 4):
    blue = valid & (idx > med + k * mad) & (B2 > T["MIN_BLUE"])
    red = valid & (idx < med - k * mad)
    from scipy import ndimage
    cand = blue & ndimage.binary_dilation(red, iterations=2)
    print(f"K={k}: blue {blue.sum()}, blue(no min) {(valid & (idx > med + k * mad)).sum()}, red {red.sum()}, "
          f"cand {cand.sum()}, objects {ndimage.label(cand)[1]}")
rgb = np.clip(np.dstack([B4, B3, B2]) / 0.25, 0, 1)
fig, ax = plt.subplots(figsize=(14, 6))
ax.imshow(rgb, interpolation="nearest")
ax.contour(mask, levels=[0.5], colors="yellow", linewidths=0.4)
fig.savefig(os.path.join(C.FIGURES, "trucks_check", "debug_chunk.png"), dpi=110, bbox_inches="tight")
print("saved debug image")
