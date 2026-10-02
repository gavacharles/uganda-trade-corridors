"""Animations and a cover for the regional social posts.

    python scripts/social_animations.py

figures/social/:
  rx1_two_corridors.mp4/.gif   one loaded truck on each of two trade corridors, Nairobi-Malaba (A8)
                               and Pretoria-Beitbridge (N1), the same km at the same moment; the road
                               type and the minutes lost build up behind each truck
  rx2_roadside_growth.mp4/.gif built-up land beside every road, 2000 to 2020 (GHSL epochs, eased
                               between), East and Southern Africa side by side
  rx3_country_ranking.mp4/.gif truck minutes lost per 100 km, country medians, bars growing in order
  cover_regional.png           1200 x 630 Substack cover
"""
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import imageio.v2 as imageio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import BoundaryNorm, ListedColormap
from PIL import Image

from regional_common import ART, C, EAST, INK, INK2, O, SOUTH, SURF, pieces
import cartography as K

OUT = os.path.join(C.FIGURES, "social")
os.makedirs(OUT, exist_ok=True)
FPS = 12
LAND, NEIGH, WATER, BORDER = "#f6f4ef", "#e9e6df", "#c9dbe6", "#a8a49b"
TYPE_COL = {"open road": "#cfe0d6", "roadside settlement": "#e8c77e", "town": "#c4532d"}
countries = gpd.read_file(os.path.join(C.DATA, "ne_admin0", "ne_10m_admin_0_countries.shp"), columns=["ADMIN"])
lakes = gpd.read_file(os.path.join(C.ROOT, "..", "data", "ne_lakes", "ne_10m_lakes.shp")).to_crs(4326)
STUDY = set(ART.country)


def canvas(fig):
    fig.canvas.draw()
    return np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy()


def write(frames, name, gif_fps=5, gif_w=800):
    mp4 = os.path.join(OUT, name + ".mp4")
    with imageio.get_writer(mp4, fps=FPS, codec="libx264", quality=8, macro_block_size=16) as w:
        for f in frames:
            w.append_data(f)
    step = max(1, FPS // gif_fps)
    small = [Image.fromarray(f).resize((gif_w, int(f.shape[0] * gif_w / f.shape[1])), Image.LANCZOS)
             .convert("P", palette=Image.ADAPTIVE, colors=256) for f in frames[::step]]
    gif = os.path.join(OUT, name + ".gif")
    small[0].save(gif, save_all=True, append_images=small[1:], duration=int(1000 / gif_fps), loop=0, optimize=True)
    print(f"wrote {name}: {len(frames)} frames, gif {os.path.getsize(gif) / 1e6:.1f} MB", flush=True)


def ease(t):
    return t * t * (3 - 2 * t)


# ====================================================================== rx1 two corridors
TT = O("travel_time_pieces.csv")
PT = O("pieces_typed.csv")
PAIR = [("nairobi_a8_malaba", "Nairobi → Malaba (A8), Kenya", EAST),
        ("pretoria_n1_beitbridge", "Pretoria → Beitbridge (N1), South Africa", SOUTH)]
D = {}
for c, _, _ in PAIR:
    d = TT[TT.corridor == c].merge(PT[["corridor", "piece", "buildings_100m"]]).sort_values("piece")
    D[c] = d.reset_index(drop=True)
KMAX = min(D[c].km_mid.max() for c, _, _ in PAIR)
DRIVE, HOLD = 13 * FPS, 5 * FPS
fig = plt.figure(figsize=(12.8, 7.2), dpi=100, facecolor=SURF)
fig.text(0.04, 0.93, "Same truck, same distance, two regions", fontsize=24, fontweight="bold", color=INK)
fig.text(0.04, 0.885, "A loaded truck on two trade corridors, side by side, km by km. Minutes lost against an open road.",
         fontsize=12.5, color=INK2)
rows = []
for i, (c, label, col) in enumerate(PAIR):
    y0 = 0.50 - i * 0.37
    ax = fig.add_axes([0.04, y0, 0.66, 0.27])
    ax.set_xlim(0, KMAX)
    ax.set_ylim(-1.3, 6.5)
    ax.axis("off")
    d = D[c]
    d = d[d.km_mid <= KMAX]
    tcols = d.road_type.map(TYPE_COL).to_numpy()
    band = ax.bar(d.km_mid, np.full(len(d), 1.0), bottom=-1.2, width=0.5, color=tcols, linewidth=0)
    bars = ax.bar(d.km_mid, (d.truck_excess_min / 0.5).clip(upper=6).to_numpy(), width=0.5, color=col, linewidth=0)
    for b in list(band) + list(bars):
        b.set_visible(False)
    truck = ax.scatter([0], [-0.7], marker=">", s=220, color=INK, zorder=5)
    ax.text(0, 6.2, label, fontsize=14, color=col, fontweight="bold", va="top")
    ax.plot([0, KMAX], [-1.25, -1.25], color="#d9d6cf", lw=1)
    for k in range(0, int(KMAX) + 1, 100):
        ax.text(k, -1.9, f"{k} km", fontsize=9, color=INK2, ha="center", va="top")
    cnt = fig.text(0.74, y0 + 0.15, "", fontsize=30, fontweight="bold", color=col, va="center")
    sub = fig.text(0.74, y0 + 0.06, "", fontsize=12, color=INK2, va="center")
    rows.append(dict(d=d.reset_index(drop=True), band=band, bars=bars, truck=truck, cnt=cnt, sub=sub))
fig.text(0.04, 0.06, "Bars: minutes lost per km. Band:  ", fontsize=10.5, color=INK2)
x = 0.245
for k, cl in TYPE_COL.items():
    fig.patches.append(matplotlib.patches.Rectangle((x, 0.058), 0.018, 0.022, transform=fig.transFigure, color=cl))
    fig.text(x + 0.022, 0.06, k, fontsize=10.5, color=INK2)
    x += 0.022 + 0.0085 * len(k) + 0.02
fig.text(0.96, 0.02, "Open data, light traffic, dry day · github.com/gavacharles/uganda-trade-corridors",
         fontsize=8.5, color=INK2, ha="right")
frames = []
for f in range(DRIVE + HOLD):
    k = KMAX * ease(min(f / DRIVE, 1))
    for r in rows:
        on = r["d"].km_mid <= k
        for j in np.flatnonzero(on.to_numpy()):
            r["band"][j].set_visible(True)
            r["bars"][j].set_visible(True)
        r["truck"].set_offsets([[k, -0.7]])
        lost = r["d"].truck_excess_min[on].sum()
        b = r["d"].buildings_100m[on].sum()
        r["cnt"].set_text(f"+{lost:.0f} min")
        r["sub"].set_text(f"after {k:.0f} km · {b:,.0f} buildings\nwithin 100 m of the road")
    frames.append(canvas(fig))
plt.close(fig)
write(frames, "rx1_two_corridors")

# ====================================================================== rx2 roadside growth
G = O("growth_pieces.csv")
P = pieces.to_crs(4326).merge(G, on=["corridor", "piece"], how="left")
P["region"] = P.corridor.map(ART.region)
YEARS = [2000, 2005, 2010, 2015, 2020]
for y in YEARS:
    P[f"v{y}"] = P[f"built_ha_{y}"] / P.length_km.clip(lower=0.1)
grp = P.corridor + "_" + (P.piece // 4).astype(str)
for y in YEARS:
    P[f"v{y}"] = P.groupby(grp)[f"v{y}"].transform("mean")
EXT = {}
for reg, d in P.groupby("region"):
    x0, y0, x1, y1 = d.total_bounds
    EXT[reg] = (x0 - 0.6, x1 + 0.6, y0 - 0.6, y1 + 0.6)
bounds = [0, 1, 2, 4, 8, 16, 1e9]
cmap = ListedColormap(["#efe9dc", "#e6d3ad", "#d6ae6d", "#bb8139", "#8f5520", "#5a3210"])
norm = BoundaryNorm(bounds, cmap.N)


def basemap(ax, extent):
    x0, x1, y0, y1 = extent
    cc = countries.cx[x0 - 5:x1 + 5, y0 - 5:y1 + 5]
    cc.plot(ax=ax, aspect=None, color=NEIGH, edgecolor=BORDER, linewidth=0.5, zorder=1)
    cc[cc.ADMIN.isin(STUDY)].plot(ax=ax, aspect=None, color=LAND, edgecolor=BORDER, linewidth=0.6, zorder=2)
    lk = lakes.cx[x0:x1, y0:y1]
    if len(lk):
        lk.plot(ax=ax, aspect=None, color=WATER, linewidth=0, zorder=3)
    K.frame(ax, extent)
    ax.set_facecolor(WATER)


def segs(d):
    out = []
    for g in d.geometry:
        if g is None:
            out.append(np.zeros((2, 2)))
        elif g.geom_type == "MultiLineString":
            out.append(np.vstack([np.asarray(p.coords) for p in g.geoms]))
        else:
            out.append(np.asarray(g.coords))
    return out


def hub_dots(ax, extent, fs=9):
    x0, x1, y0, y1 = extent
    for h, g in ART.groupby("hub"):
        x, y = g.start.iloc[0]
        if x0 < x < x1 and y0 < y < y1:
            ax.scatter([x], [y], s=26, color=INK, edgecolor="white", linewidth=0.8, zorder=12)
            if h != "johannesburg":
                ax.annotate(g.hub_name.iloc[0], (x, y), xytext=(5, 2), textcoords="offset points", fontsize=fs,
                            color=INK, fontweight="bold", zorder=13,
                            bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.75))


fig = plt.figure(figsize=(12.8, 7.2), dpi=100, facecolor=SURF)
fig.text(0.03, 0.94, "The roadside is filling in", fontsize=24, fontweight="bold", color=INK)
fig.text(0.03, 0.895, "Built-up land within 300 m of every road leaving 12 capitals and trade hubs (GHSL), hectares per km",
         fontsize=12, color=INK2)
LC, TXT = {}, {}
for reg, rect in (("East", [0.02, 0.06, 0.40, 0.80]), ("Southern", [0.44, 0.06, 0.45, 0.80])):
    ax = fig.add_axes(rect)
    basemap(ax, EXT[reg])
    d = P[P.region == reg]
    lc = LineCollection(segs(d), cmap=cmap, norm=norm, linewidths=3.4, zorder=6)
    lc.set_array(d.v2000.to_numpy())
    under = LineCollection(segs(d), colors=INK, linewidths=4.4, zorder=5)
    ax.add_collection(under)
    ax.add_collection(lc)
    hub_dots(ax, EXT[reg])
    ax.text(0.03, 0.97, f"{reg} Africa", transform=ax.transAxes, fontsize=15, fontweight="bold", va="top",
            color=EAST if reg == "East" else SOUTH, zorder=20,
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.85))
    TXT[reg] = ax.text(0.03, 0.87, "", transform=ax.transAxes, fontsize=13, va="top", color=INK, zorder=20,
                       bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="none", alpha=0.85))
    LC[reg] = (lc, d)
kax = fig.add_axes([0.91, 0.25, 0.015, 0.45])
kax.imshow(np.arange(6)[:, None], cmap=cmap, aspect="auto", origin="lower", extent=(0, 1, 0, 6))
kax.set_xticks([]); kax.set_yticks(np.arange(6) + 0.5)
kax.set_yticklabels(["< 1", "1–2", "2–4", "4–8", "8–16", "> 16"], fontsize=10)
kax.yaxis.tick_right(); kax.tick_params(length=0)
fig.text(0.905, 0.72, "ha built up\nper km", fontsize=10, color=INK2)
year_t = fig.text(0.97, 0.94, "2000", fontsize=34, fontweight="bold", color=INK, ha="right", va="top")
fig.text(0.97, 0.02, "GHSL GHS-BUILT-S R2023A · github.com/gavacharles/uganda-trade-corridors", fontsize=8.5,
         color=INK2, ha="right")
tot = {reg: [P[P.region == reg][f"built_ha_{y}"].sum() for y in YEARS] for reg in LC}
frames = []
STEP, HOLD0, HOLD1 = 2 * FPS, FPS, 5 * FPS
timeline = [0.0] * HOLD0 + [i / STEP for i in range(STEP * 4 + 1)] + [4.0] * HOLD1
for t in timeline:
    i = min(int(t), 3)
    w = ease(t - i) if t < 4 else 1.0
    for reg, (lc, d) in LC.items():
        a, b = d[f"v{YEARS[i]}"].to_numpy(), d[f"v{YEARS[i + 1]}"].to_numpy()
        lc.set_array(a + (b - a) * w)
        v = tot[reg][i] + (tot[reg][i + 1] - tot[reg][i]) * w
        TXT[reg].set_text(f"+{(v / tot[reg][0] - 1) * 100:.0f}% since 2000")
    year_t.set_text(f"{YEARS[i] + (YEARS[i + 1] - YEARS[i]) * w:.0f}")
    frames.append(canvas(fig))
plt.close(fig)
write(frames, "rx2_roadside_growth")

# ====================================================================== rx3 country ranking
CMP = O("compare_arteries.csv")
SH = {"United Republic of Tanzania": "Tanzania"}
med = CMP.groupby("country").agg(v=("truck_min_per_100km", "median"), region=("region", "first"),
                                 n=("corridor", "size")).sort_values("v")
labels = [SH.get(c, c) for c in med.index]
GROW, STAG, HOLD = int(1.0 * FPS), int(0.35 * FPS), 6 * FPS
fig = plt.figure(figsize=(12.8, 7.2), dpi=100, facecolor=SURF)
ax = fig.add_axes([0.17, 0.12, 0.62, 0.68])
fig.text(0.04, 0.93, "Leaving the capital: time lost on the main roads", fontsize=23, fontweight="bold", color=INK)
fig.text(0.04, 0.885, "Loaded-truck minutes lost per 100 km against an open road, first 200 km of every road out of the "
         "hubs (country median)", fontsize=12, color=INK2)
y = np.arange(len(med))
cols = [EAST if r == "East" else SOUTH for r in med.region]
bars = ax.barh(y, np.zeros(len(med)), color=cols, height=0.68)
vals = [ax.text(0, yi, "", va="center", fontsize=13, fontweight="bold", color=INK) for yi in y]
ax.set_yticks(y)
ax.set_yticklabels([f"{l} ({n} roads)" for l, n in zip(labels, med.n)], fontsize=13, color=INK)
ax.set_xlim(0, med.v.max() * 1.15)
ax.tick_params(length=0, labelsize=11, colors=INK2)
for s_ in ("top", "right", "left"):
    ax.spines[s_].set_visible(False)
ax.spines["bottom"].set_color("#d9d6cf")
ax.grid(axis="x", color="#e9e6df")
ax.set_axisbelow(True)
rg = O("compare_regions.csv").set_index("region").truck_min_per_100km
card = fig.text(0.81, 0.62, "", fontsize=15, color=INK, va="top", linespacing=1.5)
fig.text(0.81, 0.30, "■ East Africa", fontsize=13, color=EAST, fontweight="bold")
fig.text(0.81, 0.25, "■ Southern Africa", fontsize=13, color=SOUTH, fontweight="bold")
fig.text(0.97, 0.02, "Open data, light traffic, dry day · github.com/gavacharles/uganda-trade-corridors",
         fontsize=8.5, color=INK2, ha="right")
n = len(med)
total = GROW + STAG * (n - 1) + HOLD
frames = []
for f in range(total):
    for j, (b, v) in enumerate(zip(bars, med.v)):
        t = np.clip((f - j * STAG) / GROW, 0, 1)
        b.set_width(v * ease(t))
        vals[j].set_position((v * ease(t) + 0.6, y[j]))
        vals[j].set_text(f"{v:.0f}" if t >= 1 else "")
    if f >= GROW + STAG * (n - 1):
        card.set_text(f"Median road:\n\nEast  {rg['East']:.0f} min\nSouth {rg['Southern']:.0f} min\n\nTwice the delay")
    frames.append(canvas(fig))
plt.close(fig)
write(frames, "rx3_country_ranking")

# ====================================================================== cover 1200 x 630
P["tcol"] = P.road_type.map(TYPE_COL).fillna("#d9d4c7")   # road type came with growth_pieces
fig = plt.figure(figsize=(12, 6.3), dpi=100, facecolor="#17252a")
for reg, rect in (("East", [0.50, 0.06, 0.235, 0.88]), ("Southern", [0.745, 0.06, 0.245, 0.88])):
    ax = fig.add_axes(rect)
    basemap(ax, EXT[reg])
    d = P[P.region == reg]
    ax.add_collection(LineCollection(segs(d), colors=INK, linewidths=2.6, zorder=5))
    ax.add_collection(LineCollection(segs(d), colors=d.tcol.to_list(), linewidths=1.9, zorder=6))
    for h, g in ART[ART.region == reg].groupby("hub"):
        ax.scatter(*g.start.iloc[0], s=14, color="white", edgecolor=INK, linewidth=0.8, zorder=12)
    fig.text(rect[0], rect[1] + rect[3] + 0.01, f"{reg} Africa".upper(), fontsize=11, fontweight="bold",
             color="#d8e1df")
fig.text(0.04, 0.80, "Leaving the capital", fontsize=30, fontweight="bold", color="white", va="top")
fig.text(0.04, 0.66, "54 roads out of 12 African hubs.\nEast African trade roads have\nbecome linear towns, and lose\ntwice the time.", fontsize=16, color="#d8e1df", va="top", linespacing=1.4)
y_ = 0.30
for k, c in TYPE_COL.items():
    fig.patches.append(matplotlib.patches.Rectangle((0.04, y_), 0.025, 0.035, transform=fig.transFigure, color=c))
    fig.text(0.075, y_ + 0.004, k, fontsize=12, color="white")
    y_ -= 0.06
fig.text(0.04, 0.05, "Charles Gava · open data", fontsize=11, color="#9fb3b0")
fig.savefig(os.path.join(OUT, "cover_regional.png"), dpi=100, facecolor=fig.get_facecolor())
plt.close(fig)
print("wrote cover_regional.png", Image.open(os.path.join(OUT, "cover_regional.png")).size)
