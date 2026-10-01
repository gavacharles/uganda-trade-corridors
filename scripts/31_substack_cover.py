"""Cover image for the Substack article (1456 x 1048 px, Substack's 14:10 header and preview size).

Uganda at night: every Google Open Buildings footprint within 1 km of the five corridors drawn as
a glowing density field, so the towns and trading centres lining each highway light up. Title on
the left.
Writes figures/cover_substack.png.
"""
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm

import config as C

NIGHT, LAND, EDGE, LIGHT = "#0f1a1e", "#16252a", "#3a4f55", "#ffd9a8"
INK, MUTED, ACCENT = "#f4efe6", "#a9b8b5", "#f28a52"
EXT = (29.45, 35.15, -1.62, 4.85)

b = pd.read_parquet(os.path.join(C.DATA, "buildings.parquet"), columns=["longitude", "latitude", "area_in_meters"])
districts = gpd.read_file(C.DISTRICTS).to_crs(4326)
country = districts.union_all()
lakes = gpd.read_file(os.path.join(C.DATA, "ne_lakes", "ne_10m_lakes.shp")).to_crs(4326).cx[28.5:36, -3:5.5]
cl = gpd.read_file(C.PROBES_GPKG, layer="centrelines")
cl = cl[cl.direction == "outbound"] if "direction" in cl else cl
P = gpd.read_file(os.path.join(C.DATA, "pieces.gpkg"))
tt = pd.read_csv(os.path.join(C.OUTPUTS, "travel_time_pieces.csv"))
P = P.merge(tt[["corridor", "piece", "truck_excess_min"]], on=["corridor", "piece"], how="left")
P["per_km"] = P.truck_excess_min / 0.5
ramp = ListedColormap(["#4b6a70", "#8c7a5c", "#d08a4e", "#f28a52", "#ff6a3d", "#ffd2b8"])
norm = BoundaryNorm([0, 0.25, 0.5, 1, 2, 4, 100], ramp.N)

W, H = 14.56, 10.48
fig = plt.figure(figsize=(W, H), dpi=100, facecolor=NIGHT)
ax = fig.add_axes([0.355, 0.0, 0.645, 1.0])
x0, x1, y0, y1 = EXT
ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect("equal"); ax.axis("off")
ax.set_facecolor(NIGHT)
gpd.GeoSeries([country], crs=4326).plot(ax=ax, color=LAND, edgecolor=EDGE, linewidth=0.8, zorder=1)
lakes.plot(ax=ax, color="#13303a", linewidth=0, zorder=2)
# Buildings as a glowing density field: brighter where more buildings crowd the road
from scipy.ndimage import gaussian_filter
from matplotlib.colors import LinearSegmentedColormap
res = 0.0045
nx, ny = int((x1 - x0) / res), int((y1 - y0) / res)
Hh, _, _ = np.histogram2d(b.latitude, b.longitude, bins=[ny, nx], range=[[y0, y1], [x0, x1]])
core = np.log1p(gaussian_filter(Hh, 0.7))
halo = np.log1p(gaussian_filter(Hh, 4.0)) * 0.8
glow = np.clip((core + halo) / np.percentile(core + halo, 99.95), 0, 1) ** 1.7
glowmap = LinearSegmentedColormap.from_list("glow", [(0, (1, 0.6, 0.3, 0)), (0.15, (0.95, 0.45, 0.2, 0.35)),
                                                     (0.5, (1, 0.7, 0.4, 0.85)), (1, (1, 0.95, 0.85, 1))])
ax.imshow(glow, extent=(x0, x1, y0, y1), origin="lower", cmap=glowmap, interpolation="bilinear", zorder=4)
k = ax.scatter([32.5825], [0.3136], s=40, color=INK, zorder=6, linewidths=0)
ax.annotate("Kampala", (32.5825, 0.3136), xytext=(-8, -12), textcoords="offset points", ha="right", va="top",
            fontsize=12, color=INK, zorder=7)
for name, (x, y), off in [("Malaba", (34.279, 0.638), (6, 4)), ("Elegu", (32.08, 3.575), (6, 0)),
                          ("Katuna", (30.0, -1.42), (6, 0)), ("Hoima", (31.352, 1.432), (-6, 6)),
                          ("Bwera", (29.72, 0.041), (-8, 8))]:
    ax.annotate(name, (x, y), xytext=off, textcoords="offset points", fontsize=10.5, color=MUTED, zorder=7,
                ha="right" if off[0] < 0 else "left")

fig.text(0.05, 0.86, "UGANDA'S TRADE CORRIDORS", fontsize=13, color=ACCENT, fontweight="bold")
fig.text(0.05, 0.835, "Highways\nthat became\nhigh streets", fontsize=46, color=INK, fontweight="bold",
         va="top", linespacing=1.05)
fig.text(0.05, 0.53, "1.5 million buildings beside\nfive roads out of Kampala,\nand what they cost a truck.",
         fontsize=16, color=MUTED, va="top", linespacing=1.4)
fig.text(0.05, 0.2, "Each glow is a building footprint within\n1 km of the road: towns and trading\ncentres light up along every corridor.",
         fontsize=12, color=MUTED, va="top", linespacing=1.45)
fig.text(0.05, 0.03, "Charles Gava · Open data: Google Open Buildings, OpenStreetMap", fontsize=10, color=MUTED)
out = os.path.join(C.FIGURES, "cover_substack.png")
fig.savefig(out, dpi=100, facecolor=NIGHT)
print("wrote", out)
