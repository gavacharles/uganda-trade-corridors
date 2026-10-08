"""Satellite and GIS maps for the Kampala transit study (after k04, k07, k09, k10).

    python kampala-transit/scripts/k11_satmaps.py

  figures/s01_networks_satellite.png   the two networks (k09) on satellite imagery of Greater Kampala
  figures/s02_landuse.png              land-use classes (k07) with satellite close-ups of each pattern
  figures/s03_pinch_points.png         where a 24 m busway meets dense small-plot settlement: satellite at
                                       street level, footprints, the 24 m corridor, buildings inside it
  figures/s04_access_gain.png          access gained by each zone (efficiency BRT network)
Imagery © Esri, Maxar, Earthstar Geographics.
"""
import os, sys
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
import shapely
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
KT = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(KT, ".."))
sys.path[:0] = [HERE, os.path.join(ROOT, "scripts")]
import cartography as K  # noqa: E402
from satmap import CREDIT, satellite  # noqa: E402

INK, INK2, SURF = "#1d2321", "#5d6764", "#fcfcfb"
FIG, OUT = os.path.join(KT, "figures"), os.path.join(KT, "outputs")
UTM, CBD = 32636, (32.5825, 0.3136)
EXT = (32.38, 32.84, 0.12, 0.50)
E = gpd.read_file(os.path.join(OUT, "edges.gpkg"))
E["route"] = E.ref.fillna(E.name).fillna("")
mid = E.geometry.interpolate(0.5, normalized=True)
E["cbd_km"] = np.hypot((mid.x - CBD[0]) * 111.32, (mid.y - CBD[1]) * 111.32)
core = E[(E.cbd_km <= 20) & E.highway.isin(["motorway", "trunk", "primary", "secondary"])]
rail = gpd.read_file(os.path.join(OUT, "rail.gpkg"))
steps = pd.read_csv(os.path.join(OUT, "network_steps.csv"))
NET = {k: list(steps[steps.network == k].route) for k in ("efficiency", "equity")}
NAME = dict(zip(steps.route, steps.added))
CLS = ["wetland / water", "commercial / industrial", "institutional", "dense small-plot", "planned / larger-plot",
       "peri-urban", "rural / open"]
LUCOL = ["#5dade2", "#8e44ad", "#1f618d", "#c0392b", "#f0b27a", "#f7dc6f", "#d5e8d4"]


def furniture(ax, km):
    K.scalebar(ax, km=km)
    K.north_arrow(ax)
    ax.text(0.995, 0.005, CREDIT, transform=ax.transAxes, ha="right", va="bottom", fontsize=6.5, color="white",
            zorder=30, bbox=dict(boxstyle="square,pad=0.2", fc="black", ec="none", alpha=0.45))


def head(fig, t, s, y=0.97):
    fig.text(0.01, y, t, fontsize=16, color=INK, va="top")
    fig.text(0.01, y - 0.03, s, fontsize=9.5, color=INK2, va="top")


def save(fig, name):
    fig.savefig(os.path.join(FIG, name), dpi=160, facecolor=SURF, bbox_inches="tight")
    plt.close(fig)
    print("wrote", name, flush=True)


# ---------------------------------------------------------------- s01 networks on satellite
fig = plt.figure(figsize=(13, 11.5), facecolor=SURF)
ax = fig.add_axes([0.01, 0.02, 0.98, 0.88])
K.frame(ax, EXT)
satellite(ax, EXT, zoom=12, dim=0.15)
E.plot(ax=ax, aspect=None, color="white", linewidth=0.35, alpha=0.55, zorder=2)
both = set(NET["efficiency"]) & set(NET["equity"])
for r in set(NET["efficiency"]) | set(NET["equity"]):
    col = "#ff7a2f" if r in both else ("#ffd23f" if r in NET["efficiency"] else "#4dd99a")
    d = core[core.route == r]
    d.plot(ax=ax, aspect=None, color="black", linewidth=6, zorder=4)
    d.plot(ax=ax, aspect=None, color=col, linewidth=3.8, zorder=5)
    p = d.loc[d.km.idxmax()].geometry.interpolate(0.5, normalized=True)
    ax.annotate(NAME[r], (p.x, p.y), xytext=(6, 6), textcoords="offset points", fontsize=9, color="white",
                fontweight="bold", zorder=8, bbox=dict(boxstyle="round,pad=0.2", fc="black", ec="none", alpha=0.6))
rail.plot(ax=ax, aspect=None, color="#7fc7ff", linewidth=1.6, linestyle=(0, (4, 2)), zorder=3)
ax.scatter(*CBD, s=110, color="white", edgecolor="black", lw=1.5, zorder=9)
ax.annotate("Kampala CBD", CBD, xytext=(8, -14), textcoords="offset points", fontsize=11, color="white",
            fontweight="bold", zorder=9, bbox=dict(boxstyle="round,pad=0.2", fc="black", ec="none", alpha=0.6))
furniture(ax, 5)
ax.legend(handles=[Line2D([], [], color="#ff7a2f", lw=4, label="in both networks"),
                   Line2D([], [], color="#ffd23f", lw=4, label="efficiency network only"),
                   Line2D([], [], color="#4dd99a", lw=4, label="equity network only"),
                   Line2D([], [], color="#7fc7ff", lw=1.6, ls=(0, (4, 2)), label="railway (OSM)")],
          loc="lower left", frameon=True, facecolor="white", framealpha=0.9, fontsize=9.5,
          title="rapid-transit network (k09)", title_fontsize=10)
head(fig, "Two rapid-transit networks for Greater Kampala",
     "Grown corridor by corridor: for time saved per km (efficiency), or for access gained by residents of "
     "dense small-plot settlement per km (equity). Roads 2× slower than assumed.")
save(fig, "s01_networks_satellite.png")

# ---------------------------------------------------------------- s02 land use with satellite close-ups
LU = pd.read_parquet(os.path.join(OUT, "landuse_cells.parquet"))
with rasterio.open(os.path.join(OUT, "landuse.tif")) as src:
    A, b = src.read(1), src.bounds
fig = plt.figure(figsize=(16, 11), facecolor=SURF)
ax = fig.add_axes([0.01, 0.04, 0.56, 0.86])
K.frame(ax, EXT)
ax.imshow(A, extent=(b.left, b.right, b.bottom, b.top), cmap=ListedColormap(LUCOL),
          norm=BoundaryNorm(np.arange(-0.5, 7.5), 7), interpolation="nearest", zorder=1)
core.plot(ax=ax, aspect=None, color=INK, linewidth=0.9, zorder=3)
K.frame(ax, EXT)
K.scalebar(ax, km=5); K.north_arrow(ax)
share = LU.groupby("cls")["pop"].sum() / LU["pop"].sum()
ax.legend(handles=[Patch(color=c, label=f"{k} ({share.get(k, 0):.0%} of residents)") for k, c in zip(CLS, LUCOL)],
          loc="lower left", frameon=True, facecolor="white", fontsize=9, title="land use (250 m cells)",
          title_fontsize=10)
# one close-up per settlement pattern: the most typical populous cell of each, inside the map
ins = []
for k in ("dense small-plot", "planned / larger-plot", "peri-urban", "commercial / industrial"):
    d = LU[(LU.cls == k) & LU.lon.between(EXT[0] + 0.03, EXT[1] - 0.03) & LU.lat.between(EXT[2] + 0.03, EXT[3] - 0.03)]
    d = d[d.n > d.n.quantile(0.5)] if len(d) > 20 else d
    med = d[["bld_ha", "med_m2"]].median()
    i = ((d.bld_ha - med.bld_ha) / med.bld_ha) ** 2 + ((d.med_m2 - med.med_m2) / med.med_m2) ** 2
    ins.append((k, d.loc[i.idxmin()]))
for j, (k, r) in enumerate(ins):
    h = 0.0055
    w_ = (r.lon - h, r.lon + h, r.lat - h, r.lat + h)
    ax.add_patch(Rectangle((w_[0], w_[2]), 2 * h, 2 * h, fill=False, ec="black", lw=1.6, zorder=6))
    ax.text(w_[1], w_[3], f" {j + 1}", fontsize=11, fontweight="bold", zorder=7,
            bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none"))
    a2 = fig.add_axes([0.59 + (j % 2) * 0.205, 0.49 - (j // 2) * 0.44, 0.195, 0.37])
    K.frame(a2, w_)
    satellite(a2, w_, zoom=17)
    for s_ in a2.spines.values():
        s_.set_visible(True); s_.set_color(LUCOL[CLS.index(k)]); s_.set_linewidth(3)
    K.scalebar(a2, km=0.5)
    a2.set_title(f"{j + 1}. {k}\n{r.bld_ha:.0f} buildings/ha · median footprint {r.med_m2:.0f} m²", loc="left",
                 fontsize=9.5, color=INK)
head(fig, "Land-use patterns of Greater Kampala",
     "250 m cells from 2.4 million building footprints (density, size, coverage) and OpenStreetMap land use; "
     "close-ups 1–4 show a typical cell of each pattern on satellite imagery (about 1.2 km across).")
fig.text(0.59, 0.01, CREDIT, fontsize=7.5, color=INK2)
save(fig, "s02_landuse.png")

# ---------------------------------------------------------------- s03 pinch points
S = gpd.read_file(os.path.join(OUT, "clearance_sections.gpkg"))
netr = set(NET["efficiency"]) | set(NET["equity"])
P = S[S.route.isin(netr) & (S.width < 24) & (S.width >= 8)].copy()   # under 8 m: the line crosses a footprint (data artefact)
P["dense"] = P.landuse == "dense small-plot"
P = P.sort_values(["dense", "width"], ascending=[False, True])
picks = []
for _, r in P.iterrows():
    if all(np.hypot(r.geometry.x - q.geometry.x, r.geometry.y - q.geometry.y) > 0.01 for q in picks):
        if sum(q.route == r.route for q in picks) < 2:
            picks.append(r)
    if len(picks) == 6:
        break
BR = pd.read_parquet(os.path.join(KT, "data", "buildings_road.parquet"))
fig, axs = plt.subplots(2, 3, figsize=(16, 12), facecolor=SURF, gridspec_kw=dict(hspace=0.28, wspace=0.12))
for ax, r in zip(axs.ravel(), picks):
    h = 0.0028
    w_ = (r.geometry.x - h, r.geometry.x + h, r.geometry.y - h, r.geometry.y + h)
    K.frame(ax, w_)
    satellite(ax, w_, zoom=18)
    sel = BR[BR.longitude.between(w_[0] - 0.001, w_[1] + 0.001) & BR.latitude.between(w_[2] - 0.001, w_[3] + 0.001)]
    fp = gpd.GeoSeries(shapely.from_wkt(sel.geometry.values), crs=4326)
    line = core[core.route == r.route].cx[w_[0]:w_[1], w_[2]:w_[3]]
    band = gpd.GeoSeries([line.to_crs(UTM).union_all().buffer(12, cap_style="flat")], crs=UTM).to_crs(4326)
    hit = fp.intersects(band.iloc[0])
    band.plot(ax=ax, aspect=None, color="#ffd23f", alpha=0.28, edgecolor="#ffd23f", linewidth=1.5, zorder=3)
    fp[~hit].plot(ax=ax, aspect=None, facecolor="none", edgecolor="white", linewidth=0.6, zorder=4)
    fp[hit].plot(ax=ax, aspect=None, facecolor="#ff3b30", alpha=0.6, edgecolor="#ff3b30", linewidth=0.8, zorder=5)
    line.plot(ax=ax, aspect=None, color="#ffd23f", linewidth=1.2, linestyle=(0, (5, 3)), zorder=6)
    K.scalebar(ax, km=0.1)
    for s_ in ax.spines.values():
        s_.set_visible(True); s_.set_color(INK)
    ax.set_title(f"{NAME.get(r.route, r.route)}\n{r.width:.0f} m between building lines · {r.landuse}\n"
                 f"{int(hit.sum())} buildings inside the 24 m corridor in this view", loc="left", fontsize=9.5, color=INK)
for ax in axs.ravel()[len(picks):]:
    ax.set_axis_off()
fig.legend(handles=[Patch(facecolor="#ffd23f", alpha=0.4, edgecolor="#ffd23f", label="24 m busway / tramway corridor"),
                    Patch(facecolor="#ff3b30", alpha=0.6, label="building inside it"),
                    Patch(facecolor="none", edgecolor="white", label="other building footprint (Open Buildings)")],
           loc="lower center", ncol=3, frameon=False, fontsize=10, bbox_to_anchor=(0.5, 0.01))
head(fig, "Pinch points: where a busway meets dense settlement",
     "The narrowest stretches of the network corridors (k04 cross-sections under 24 m), dense small-plot land first; "
     "about 620 m across, at street level. " + CREDIT + ".", y=0.995)
save(fig, "s03_pinch_points.png")

# ---------------------------------------------------------------- s04 access gain
ZA = pd.read_parquet(os.path.join(OUT, "network_zone_access.parquet"))
gain = 100 * ZA["efficiency_BRT"] / ZA.base_A.replace(0, np.nan)
fig = plt.figure(figsize=(13, 11.5), facecolor=SURF)
ax = fig.add_axes([0.01, 0.02, 0.9, 0.88])
K.frame(ax, EXT)
satellite(ax, EXT, zoom=12, dim=0.55)
bins = [0, 2, 5, 10, 20, 40, 1e9]
cm = ListedColormap(["#f7f4f9", "#d4b9da", "#c994c7", "#df65b0", "#dd1c77", "#980043"])
nm = BoundaryNorm(bins, cm.N)
sz = (0.01 * ax.get_window_extent().width / (EXT[1] - EXT[0]) * 72 / fig.dpi) ** 2
ok = (ZA["pop"] > 300) & (gain >= 2)
ax.scatter(ZA.lon[ok], ZA.lat[ok], c=gain[ok], cmap=cm, norm=nm, s=sz, marker="s", alpha=0.78, linewidths=0, zorder=2)
for r in NET["efficiency"]:
    d = core[core.route == r]
    d.plot(ax=ax, aspect=None, color="black", linewidth=4, zorder=4)
    d.plot(ax=ax, aspect=None, color="#ffd23f", linewidth=2.4, zorder=5)
furniture(ax, 5)
K.key(fig, ax, cm, nm, bins, "% more jobs and services reachable in 45 min", labels=["< 2", "2–5", "5–10", "10–20",
                                                                                  "20–40", "> 40"])
head(fig, "Where access improves: the efficiency BRT network",
     "Each ~1.1 km zone: change in built-up floor area reachable within 45 minutes door to door; roads 2× slower than "
     "assumed. Yellow: the network. Zones gaining under 2% are left clear.")
save(fig, "s04_access_gain.png")
