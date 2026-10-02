"""Thematic maps for the paper: each result drawn on the corridors themselves.

    python scripts/32_paper_maps.py

  p01_road_types_map.png     road type of every 500 m piece, with a Kampala inset
  p02_growth_map.png         (a) built-up land added within 300 m, 2000-2020 (GHSL); (b) growth in
                             building count within 300 m, 2016-2023 (Open Buildings Temporal), per 2 km
  p03_people_exposure_map.png (a) people within 300 m per km; (b) safety exposure per km, with school
                             stretches and the police black spots located on the roads
  p04_fuel_map.png           extra diesel per km per loaded truck from friction
  p05_rain_fragility_map.png (a) days a year with >= 10 mm rain; (b) the ten most flood-fragile 2 km
                             stretches, and the 2020 Mpondwe flood
  p06_controls_map.png       controls mapped along the corridors: weighbridges, police posts, signals,
                             crossings, humps
  p07_kampala_exit_map.png   the first 40 km out of Kampala: buildings, the road network, delay
"""
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle

import config as C
import maplib as M
import cartography as K
from cartography import INK, INK2, SURF

O = lambda f: pd.read_csv(os.path.join(C.OUTPUTS, f))  # noqa: E731
P = M.pieces.copy()
TOWNS = ["Kampala", "Jinja", "Tororo", "Gulu", "Masaka", "Mbarara", "Kabale", "Hoima", "Fort Portal", "Kasese"]
TOWNS = [t for t in TOWNS if t in M.TOWNS]
SRC = "Sources: OpenStreetMap; Google Open Buildings v3 and 2.5D Temporal; GHSL; WorldPop 2025; CHIRPS; study model."


def seq(colors, bounds):
    cmap = ListedColormap(colors)
    return cmap, BoundaryNorm(bounds, cmap.N)


def by_piece(df, col):
    return P[["corridor", "piece"]].merge(df[["corridor", "piece", col]], how="left")[col].to_numpy()


def binned(values, km=2.0):
    """Average a per-piece value over km-long stretches (smoother at national scale)."""
    s = pd.Series(values)
    grp = P.corridor + "_" + (P.piece // int(km / 0.5)).astype(str)
    return s.groupby(grp.to_numpy()).transform("mean").to_numpy()


def theme(ax, values, cmap, norm, lw=3.4, extent=M.EXT_UG, towns=True):
    M.base(ax, extent)
    M.context_labels(ax)
    d = P.assign(v=values).dropna(subset=["v"])
    for corridor in C.CORRIDORS:
        M.cl.loc[[corridor]].plot(ax=ax, aspect=None, color=INK, linewidth=lw + 1.6, zorder=5)
        M.cl.loc[[corridor]].plot(ax=ax, aspect=None, color="#d9d4c7", linewidth=lw, zorder=5.5)  # no data
    d.sort_values("v").plot(ax=ax, aspect=None, column="v", cmap=cmap, norm=norm, linewidth=lw, zorder=6)
    if towns:
        M.town_labels(ax, TOWNS, size=8, extent=extent)
    K.furniture(ax, km=100 if extent == M.EXT_UG else 10)


def key(fig, ax, cmap, norm, bounds, label, labels=None):
    return K.key(fig, ax, cmap, norm, bounds, label, labels=labels)


def head(fig, t, sub):
    fig.text(0.03, 0.975, t, fontsize=15, color=INK, va="top")
    fig.text(0.03, 0.945, sub, fontsize=9.5, color=INK2, va="top")
    fig.text(0.03, 0.01, SRC, fontsize=7.5, color=INK2)


def save(fig, name):
    fig.savefig(os.path.join(C.FIGURES, name), dpi=170, facecolor=SURF, bbox_inches="tight")
    plt.close(fig)
    print("wrote", name, flush=True)


def panel_label(ax, s):
    ax.text(0.015, 0.985, s, transform=ax.transAxes, fontsize=13, fontweight="bold", color=INK, va="top",
            zorder=30, bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.85))


# ---------------------------------------------------------------- p01 road types
KAMPALA = (32.30, 32.90, 0.10, 0.62)
tcol = list(M.TYPE_COL.values())
tmap = ListedColormap(tcol)
tnorm = BoundaryNorm([-0.5, 0.5, 1.5, 2.5], 3)
tval = P.road_type.map({k: i for i, k in enumerate(M.TYPE_COL)}).to_numpy(float)
fig = plt.figure(figsize=(15, 10.5), facecolor=SURF)
ax = fig.add_axes([0.01, 0.08, 0.62, 0.84])
theme(ax, tval, tmap, tnorm)
ax.add_patch(Rectangle((KAMPALA[0], KAMPALA[2]), KAMPALA[1] - KAMPALA[0], KAMPALA[3] - KAMPALA[2], fill=False,
                       ec=INK, lw=1.2, zorder=20))
ins = fig.add_axes([0.65, 0.30, 0.34, 0.48])
theme(ins, tval, tmap, tnorm, lw=4.5, extent=KAMPALA, towns=False)
M.place_labels(ins, *KAMPALA, n=10, size=7)
for s_ in ins.spines.values():
    s_.set_visible(True); s_.set_color(INK)
ins.set_title("Kampala's exits", fontsize=9.5, color=INK, loc="left")
t = O("typology_summary.csv")
share = t.groupby("road_type").km.sum() / t.km.sum()
ax.legend(handles=[Line2D([], [], color=c, lw=5, label=f"{k} ({share[k]:.0%} of length)") for k, c in M.TYPE_COL.items()],
          loc="upper left", bbox_to_anchor=(1.03, 0.20), frameon=True, facecolor="white", edgecolor="#d8d5ce",
          fontsize=10, title="road type (k-means on roadside measures)", title_fontsize=9)
head(fig, "What the corridors have become: road type along every 500 m",
     "Open road, roadside settlement or town, from buildings within 100 m and 300 m, joining roads and roadside activity.")
save(fig, "p01_road_types_map.png")

# ---------------------------------------------------------------- p02 growth
g = M.growth.copy()
added = by_piece(g.assign(add=(g.built_ha_2020 - g.built_ha_2000) / 0.5), "add")
gt = O("growth_temporal_pieces.csv").pivot_table(index=["corridor", "piece"], columns="year",
                                                  values="buildings").reset_index()
gt["n16"], gt["n23"] = gt[2016], gt[2023]
P2 = P[["corridor", "piece"]].merge(gt[["corridor", "piece", "n16", "n23"]], how="left")
grp = (P.corridor + "_" + (P.piece // 4).astype(str)).to_numpy()
sums = P2.assign(g=grp).groupby("g")[["n16", "n23"]].transform("sum")
pct = np.where(sums.n16 > 50, (sums.n23 / sums.n16 - 1) * 100, np.nan)
fig, axs = plt.subplots(1, 2, figsize=(17, 9.6), facecolor=SURF, gridspec_kw=dict(wspace=0.12))
b1 = [0, 0.5, 1, 2, 4, 8, 100]
c1, n1 = seq(["#f1eee6", "#e6d5b8", "#d2ad74", "#b57d3b", "#8a5420", "#5a3210"], b1)
theme(axs[0], binned(added), c1, n1)
key(fig, axs[0], c1, n1, b1, "built-up ha added within 300 m per km, 2000–2020",
    labels=["< 0.5", "0.5–1", "1–2", "2–4", "4–8", "> 8"])
panel_label(axs[0], "(a)")
b2 = [-100, 10, 20, 30, 45, 60, 1000]
c2, n2 = seq(["#eef1ea", "#cfe3c8", "#9fcf98", "#5fae63", "#2f8743", "#145a2a"], b2)
theme(axs[1], pct, c2, n2)
key(fig, axs[1], c2, n2, b2, "growth in buildings within 300 m, 2016–2023 (per 2 km)",
    labels=["< 10%", "10–20%", "20–30%", "30–45%", "45–60%", "> 60%"])
panel_label(axs[1], "(b)")
head(fig, "How fast the roadside is building up",
     "(a) GHSL built-up surface, observed 2000 and 2020, per 2 km stretch. (b) Google Open Buildings 2.5D Temporal "
     "building counts, 2016 to 2023, per 2 km stretch.")
save(fig, "p02_growth_map.png")

# ---------------------------------------------------------------- p03 people and exposure
S = O("safety_pieces.csv")
people = by_piece(S.assign(v=S.people_300m / 0.5), "v")
expo = by_piece(S.assign(v=S.exposure / 0.5), "v")
fig, axs = plt.subplots(1, 2, figsize=(17, 9.6), facecolor=SURF, gridspec_kw=dict(wspace=0.12))
b1 = [0, 500, 1000, 2000, 4000, 8000, 1e9]
c1, n1 = seq(["#f6efe2", "#f1d9a8", "#e6b765", "#d18f2e", "#a8641b", "#6f3d0f"], b1)
theme(axs[0], binned(people), c1, n1)
key(fig, axs[0], c1, n1, b1, "people living within 300 m, per km",
    labels=["< 500", "500–1k", "1–2k", "2–4k", "4–8k", "> 8k"])
panel_label(axs[0], "(a)")
q = np.nanquantile(expo, [0.5, 0.75, 0.9, 0.97, 0.995])
b2 = [0, *np.round(q, 2), 1e9]
c2, n2 = seq(["#f3eee8", "#f3cdbd", "#e89b7f", "#d0613f", "#a6321b", "#6b1408"], b2)
theme(axs[1], binned(expo), c2, n2)
key(fig, axs[1], c2, n2, b2, "safety exposure per km (people × trucks × (speed/50)⁴)",
    labels=["lowest half", "50–75th pct", "75–90th", "90–97th", "97–99.5th", "top 0.5%"])
sch = O("safety_schools.csv")
pts = P.assign(km=P.piece * 0.5).merge(sch[["corridor", "km_start"]].rename(columns={"km_start": "km"}))
c_ = pts.geometry.centroid
axs[1].scatter(c_.x, c_.y, s=2.2, color="#123f63", zorder=9, linewidths=0)
bs = O("black_spots_matched.csv")
bs = bs[bs.matched]
bpt = [P[(P.corridor == r.corridor)].iloc[(P[P.corridor == r.corridor].piece * 0.5 - r.km).abs().argmin()].geometry.centroid
       for r in bs.itertuples()]
axs[1].scatter([p.x for p in bpt], [p.y for p in bpt], marker="^", s=60, color="white", edgecolor=INK, linewidth=1.2,
               zorder=12)
axs[1].legend(handles=[Line2D([], [], marker="o", ls="none", color="#1b5e8c", markersize=4,
                              label="school, trucks > 50 km/h, no crossing within 500 m"),
                       Line2D([], [], marker="^", ls="none", markerfacecolor="white", markeredgecolor=INK,
                              markersize=8, label=f"police crash black spot (located: {len(bs)})")],
              loc="upper left", bbox_to_anchor=(0.0, 0.93), frameon=True, facecolor="white", edgecolor="#d8d5ce",
              fontsize=8.5)
panel_label(axs[1], "(b)")
head(fig, "Who lives beside the corridors, and where fast trucks pass them",
     "(a) WorldPop 2025 within 300 m of the road. (b) Exposure per 2 km; school stretches and the 2018 police black "
     "spots located by place name.")
save(fig, "p03_people_exposure_map.png")

# ---------------------------------------------------------------- p04 fuel
F = O("fuel_co2_pieces.csv")
fuel = by_piece(F.assign(v=F.friction_litres / 0.5), "v")
fig = plt.figure(figsize=(10.5, 11), facecolor=SURF)
ax = fig.add_axes([0.03, 0.05, 0.94, 0.86])
b = [-100, 0, 0.05, 0.1, 0.2, 0.4, 100]
cm, nm = seq(["#dfe8ee", "#f2efe6", "#d9e1c2", "#a9c27d", "#6c9a45", "#355f1f"], b)
theme(ax, binned(fuel), cm, nm)
key(fig, ax, cm, nm, b, "extra diesel per km per loaded truck (litres)",
    labels=["saving (climbs held back)", "0–0.05", "0.05–0.1", "0.1–0.2", "0.2–0.4", "> 0.4"])
fc = O("fuel_co2.csv")
fc = fc[fc.direction == "outbound"].set_index("corridor")
txt = "\n".join(f"{C.CORRIDORS[c]['short']}: {r.friction_litres_trip:.0f} L per trip · {r.friction_co2_kt_year:.0f} kt CO₂ a year"
                for c, r in fc.iterrows())
ax.text(0.015, 0.84, txt, transform=ax.transAxes, fontsize=8.5, color=INK, va="top", zorder=20,
        bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="#d8d5ce"))
head(fig, "Where roadside friction burns diesel",
     "Physical fuel model on the travel-time model's speeds: slow-downs, re-acceleration and idling against open road; per 2 km.")
save(fig, "p04_fuel_map.png")

# ---------------------------------------------------------------- p05 rain and fragility
T = O("pieces_typed.csv")
wet = by_piece(T, "wet_days_per_year")
fr = O("fragile_stretches.csv").head(10).reset_index(drop=True)
fig, axs = plt.subplots(1, 2, figsize=(17, 9.6), facecolor=SURF, gridspec_kw=dict(wspace=0.12))
b1 = [0, 30, 35, 40, 45, 55, 100]
c1, n1 = seq(["#eef3f7", "#cfe0ec", "#9fc2db", "#6a9dc4", "#3c74a6", "#1b4a78"], b1)
theme(axs[0], binned(wet), c1, n1)
key(fig, axs[0], c1, n1, b1, "days a year with ≥ 10 mm rain (CHIRPS 2006–2025)",
    labels=["< 30", "30–35", "35–40", "40–45", "45–55", "> 55"])
panel_label(axs[0], "(a)")
M.base(axs[1])
M.context_labels(axs[1])
for corridor in C.CORRIDORS:
    M.corridor_line(axs[1], corridor, "#d9d4c7", lw=2.4)
fpt = []
for r in fr.itertuples():
    d = P[P.corridor == r.corridor]
    fpt.append(d.iloc[(d.piece * 0.5 - (r.km_from + r.km_to) / 2).abs().argmin()].geometry.centroid)
M.numbered_markers(axs[1], [p.x for p in fpt], [p.y for p in fpt], list(range(1, len(fr) + 1)), size=7.5)
mx, my = C.CORRIDORS["kampala_bwera"]["end"]
axs[1].scatter([mx], [my], marker="*", s=260, color="#1b4a78", edgecolor="white", zorder=14)
axs[1].annotate("Mpondwe: bridge destroyed\nby flood, May 2020", (mx, my), xytext=(10, -26), textcoords="offset points",
                fontsize=8.5, color=INK, zorder=15, bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.85))
M.town_labels(axs[1], TOWNS, size=8)
K.furniture(axs[1], km=100)
lines = [f"{i + 1}. {r.place if isinstance(r.place, str) else 'unnamed'}, {C.CORRIDORS[r.corridor]['short']} km {r.km_from:.0f}"
         for i, r in fr.iterrows()]
axs[1].text(0.015, 0.90, "Most flood-fragile 2 km\n(water crossings, wetland,\nheavy-rain days, low ground)\n\n" + "\n".join(lines),
            transform=axs[1].transAxes, fontsize=8, color=INK, va="top", zorder=20,
            bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="#d8d5ce"))
panel_label(axs[1], "(b)")
head(fig, "Rain and the places most likely to flood",
     "(a) Heavy-rain days per year along each road, per 2 km. (b) Flood-fragility ranking of 2 km stretches (18_reliability.py).")
save(fig, "p05_rain_fragility_map.png")

# ---------------------------------------------------------------- p06 controls
fig = plt.figure(figsize=(10.5, 11), facecolor=SURF)
ax = fig.add_axes([0.03, 0.05, 0.94, 0.86])
M.base(ax)
M.context_labels(ax)
for corridor in C.CORRIDORS:
    M.corridor_line(ax, corridor, "#e3ddcf", lw=2.6)
c = P.geometry.centroid
CTRL = [("signals", "P", "#5d6764", 26, "traffic signals"), ("ped_crossings", "o", "#9fb3b0", 14, "pedestrian crossings"),
        ("humps", "X", "#d9a441", 30, "speed humps mapped in OSM"), ("level_crossings", "*", "#8a6b4e", 50, "level crossings"),
        ("police_posts", "D", "#4e7c8a", 34, "police posts"), ("weighbridges", "s", "#17252a", 80, "weighbridges")]
hand = []
for col, mk, colr, sz, lab in CTRL:
    m = (by_piece(T, col) > 0)
    ax.scatter(c.x[m], c.y[m], marker=mk, s=sz, color=colr, edgecolor="white", linewidth=0.5, zorder=8 + sz / 100)
    hand.append(Line2D([], [], marker=mk, ls="none", color=colr, markersize=7, label=f"{lab} ({int(m.sum())} pieces)"))
M.town_labels(ax, TOWNS, size=8)
M.border_marks(ax)
K.furniture(ax, km=100)
ax.legend(handles=hand, loc="upper left", bbox_to_anchor=(0.0, 0.66), frameon=True, facecolor="white",
          edgecolor="#d8d5ce", fontsize=9, title="controls on the road (OpenStreetMap)", title_fontsize=8.5)
head(fig, "Controls along the corridors as mapped",
     "Each marker is a 500 m piece with at least one control. OSM records few humps; the model assumes one per town piece.")
save(fig, "p06_controls_map.png")

# ---------------------------------------------------------------- p07 Kampala exit
EX = (32.28, 32.98, 0.16, 0.66)
fig = plt.figure(figsize=(12, 10.5), facecolor=SURF)
ax = fig.add_axes([0.03, 0.05, 0.94, 0.86])
M.base(ax, EX)
bb = M.buildings[M.buildings.longitude.between(EX[0], EX[1]) & M.buildings.latitude.between(EX[2], EX[3])]
ax.scatter(bb.longitude, bb.latitude, s=0.25, color="#a8a296", linewidths=0, zorder=3, rasterized=True)
rr = M.froads.cx[EX[0]:EX[1], EX[2]:EX[3]]
rr = rr[rr.highway.isin(["motorway", "trunk", "primary", "secondary", "tertiary"])]
rr.plot(ax=ax, aspect=None, color="#7d7a72", linewidth=0.7, zorder=4)
for corridor in C.CORRIDORS:
    M.delay_line(ax, corridor, lw=4.0)
for corridor, cfg in C.CORRIDORS.items():
    d = P[(P.corridor == corridor) & (P.piece == 44)]
    if len(d):
        p = d.geometry.iloc[0].centroid
        ax.annotate(f"{cfg['ref']} to {cfg['short']}", (p.x, p.y), xytext=(6, 6), textcoords="offset points",
                    fontsize=9.5, fontweight="bold", color=INK, zorder=20,
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))
M.place_labels(ax, *EX, n=16, size=7.5)
K.furniture(ax, km=10)
M.delay_key(fig, ax)
ax.legend(handles=[Line2D([], [], marker="s", ls="none", color="#a8a296", markersize=4, label="building (Open Buildings)"),
                   Line2D([], [], color="#7d7a72", lw=1, label="main roads (OSM)")],
          loc="lower left", frameon=True, facecolor="white", edgecolor="#d8d5ce", fontsize=8.5)
head(fig, "Leaving Kampala: the first 35 km of every corridor",
     "Every building footprint within 1 km of the corridors, the main road network and truck minutes lost per km.")
save(fig, "p07_kampala_exit_map.png")
