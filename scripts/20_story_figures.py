"""Figures that tell the story more directly than the working charts.

  g01_waterfall.png        per corridor, how a truck trip grows from open-road time to the
                           modelled time, cause by cause (central case, leaving Kampala)
  g02_rank_stability.png   in what share of the 1,000 Monte Carlo draws each cause is the
                           largest, per corridor, car and truck (outputs/rank_stability.csv)
  g03_strip_maps.png       each corridor straightened into a line, like a metro diagram:
                           road type, truck minutes lost per km, controls, towns, and new
                           roadside building 2000-2020, all on one km scale
  g04_time_map.png         the four corridors redrawn so that length is truck travel time
                           instead of distance: slow stretches stretch the line

Reads outputs written by 06-10 and 09. Writes figures/g0*.png.
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

import config as C
from cartography import INK, INK2, SURF

O = lambda f: os.path.join(C.OUTPUTS, f)  # noqa: E731
CORR = list(C.CORRIDORS)
SHORT = {c: f"{C.CORRIDORS[c]['short']} ({C.CORRIDORS[c]['ref']})" for c in CORR}
CAUSE_COL = {"roadside activity": "#c4532d", "hills (trucks)": "#8a6b4e", "weighbridge": "#17252a",
             "speed humps (assumed)": "#d9a441", "police posts": "#4e7c8a", "joining roads": "#3a7d5c",
             "signals and crossings": "#9fb3b0", "town speed limit": "#e89a7a", "curves": "#c9c2b8"}
TYPE_COL = {"open road": "#cfe0d6", "roadside settlement": "#e8c77e", "town": "#c4532d"}
CORR_COL = {"kampala_malaba": "#2a78d6", "kampala_elegu": "#e8643a", "kampala_katuna": "#1aa878", "kampala_bwera": "#8a5cc7",
            "kampala_hoima": "#e89c10"}
for _c, _col in zip([c for c in CORR if c not in CORR_COL], ["#2a78d6", "#e8643a", "#1aa878", "#e89c10", "#7a5bc4"]):
    CORR_COL[_c] = _col   # corridors of another study area
TOWNS = getattr(C, "TOWNS", None) or {"Kampala": (32.5825, 0.3136), "Jinja": (33.2040, 0.4390), "Gulu": (32.2990, 2.7740),
         "Masaka": (31.7350, -0.3330), "Mbarara": (30.6550, -0.6070), "Kabale": (29.9856, -1.2486),
         "Hoima": (31.3520, 1.4320), "Luweero": (32.4730, 0.8490), "Mukono": (32.7550, 0.3530),
         "Lugazi": (32.9420, 0.3700), "Karuma": (32.2380, 2.2480), "Lukaya": (31.8750, -0.1440),
         "Iganga": (33.4690, 0.6090), "Bugiri": (33.7420, 0.5680), "Tororo": (34.1810, 0.6930),
         "Kafu": (32.0560, 1.5700), "Bweyale": (32.1100, 1.8200), "Atiak": (32.1200, 3.2600),
         "Ntungamo": (30.2640, -0.8790), "Lyantonde": (31.1580, -0.4040), "Kiboga": (31.7730, 0.9160),
         "Kakumiro": (31.3230, 0.7810), "Mpigi": (32.3140, 0.2250), "Nakasongola": (32.4650, 1.3090)}


def clean(ax, grid="x"):
    for s_ in ("top", "right", "left"):
        ax.spines[s_].set_visible(False)
    ax.spines["bottom"].set_color("#e4e3df")
    if grid:
        ax.grid(axis=grid, color="#e4e3df", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(colors=INK2, labelsize=8.5, length=0)


def save(fig, name):
    fig.savefig(os.path.join(C.FIGURES, name), dpi=150, facecolor=SURF, bbox_inches="tight")
    plt.close(fig)
    print("wrote", name)


tot = pd.read_csv(O("travel_time_totals.csv"))
cau = pd.read_csv(O("travel_time_causes.csv"))
P = pd.read_csv(O("pieces_typed.csv")).sort_values(["corridor", "piece"])
tt = pd.read_csv(O("travel_time_pieces.csv"))
gr = pd.read_csv(O("growth_pieces.csv"))

# ---------------------------------------------------------------- g01 waterfall
fig, axs = plt.subplots(len(CORR), 1, figsize=(12, 3.0 * len(CORR)), facecolor=SURF, sharex=True,
                        gridspec_kw=dict(hspace=0.55))
xmax = tot[(tot.vehicle == "truck") & (tot.direction == "outbound")].minutes.max() * 1.08
for ax, corridor in zip(axs, CORR):
    t = tot[(tot.corridor == corridor) & (tot.vehicle == "truck") & (tot.direction == "outbound")].iloc[0]
    c = cau[(cau.corridor == corridor) & (cau.vehicle == "truck") & (cau.direction == "outbound")
            & (cau.cause != "rain (wet day)")].set_index("cause").minutes
    c = c[c >= 0.5].sort_values(ascending=False)
    overlap = t.minutes - t.open_road_minutes - c.sum()
    steps = [("open road", t.open_road_minutes, "#b8c7c4")] + [(k, v, CAUSE_COL[k]) for k, v in c.items()]
    if abs(overlap) >= 0.5:
        steps.append(("overlap between causes", overlap, "#e4e3df"))
    left, y = 0.0, 0
    labels = []
    for i, (k, v, col) in enumerate(steps):
        ax.barh(i, v, left=left if i else 0, color=col, height=0.7, linewidth=0)
        ax.text((left if i else 0) + max(v, 0) + 3, i, f"+{v:.0f}" if i else f"{v:.0f}", va="center",
                fontsize=8.5, color=INK)
        left = left + v if i else v
        labels.append(k)
    ax.barh(len(steps), t.minutes, color="#17252a", height=0.7, linewidth=0)
    ax.text(t.minutes + 3, len(steps), f"{t.minutes:.0f} min", va="center", fontsize=9, color=INK, fontweight="bold")
    labels.append("modelled trip")
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8.5, color=INK)
    ax.invert_yaxis()
    ax.set_xlim(0, xmax)
    clean(ax)
    ax.set_title(f"{C.CORRIDORS[corridor]['label']}: +{t.minutes - t.open_road_minutes:.0f} min "
                 f"(+{(t.minutes / t.open_road_minutes - 1):.0%}) over open road", loc="left", fontsize=10, color=INK)
axs[-1].set_xlabel("loaded-truck minutes, leaving Kampala (light traffic, dry day)", fontsize=9, color=INK2)
fig.text(0.125, 0.935, "How a truck trip grows, cause by cause", fontsize=15, color=INK)
fig.text(0.125, 0.92, "Each bar starts where the one above ends. Causes are measured one at a time, so they overlap "
         "slightly; the grey bar balances the total. One scale for all roads.", fontsize=9, color=INK2)
save(fig, "g01_waterfall.png")

# ---------------------------------------------------------------- g02 rank stability
rs = pd.read_csv(O("rank_stability.csv"))
fig, axs = plt.subplots(1, 2, figsize=(13, 4.2), facecolor=SURF, sharey=True, gridspec_kw=dict(wspace=0.08))
for ax, veh in zip(axs, ("car", "truck")):
    d = rs[rs.vehicle == veh].pivot_table(index="corridor", columns="cause", values="share_first").reindex(CORR).fillna(0)
    d = d[[k for k in CAUSE_COL if k in d.columns]]
    left = np.zeros(len(CORR))
    for k in d.columns:
        v = d[k].to_numpy()
        if v.max() == 0:
            continue
        ax.barh(range(len(CORR)), v, left=left, color=CAUSE_COL[k], height=0.62, linewidth=0.6,
                edgecolor=SURF, label=k)
        for i, (l_, w_) in enumerate(zip(left, v)):
            if w_ >= 0.12:
                ax.text(l_ + w_ / 2, i, f"{w_:.0%}", ha="center", va="center", fontsize=8.5,
                        color="white" if k not in ("speed humps (assumed)", "signals and crossings", "curves") else INK)
        left += v
    ax.set_yticks(range(len(CORR)))
    ax.set_yticklabels([SHORT[c] for c in CORR], fontsize=9.5, color=INK)
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1))
    clean(ax, grid=None)
    ax.set_title(f"{veh}: which cause adds the most minutes?", loc="left", fontsize=10.5, color=INK)
h = [Line2D([], [], color=CAUSE_COL[k], linewidth=8) for k in CAUSE_COL]
fig.legend(h, list(CAUSE_COL), loc="lower center", ncol=5, frameon=False, fontsize=8.5, labelcolor=INK2,
           bbox_to_anchor=(0.5, -0.12))
fig.text(0.125, 1.04, "How sure is the ranking of causes?", fontsize=15, color=INK)
fig.text(0.125, 0.975, "Share of 1,000 Monte Carlo draws of every assumption in which each cause is the largest. "
         "For cars, roadside activity wins almost everywhere; for trucks the answer depends on assumed stop times.",
         fontsize=9, color=INK2)
save(fig, "g02_rank_stability.png")

# ---------------------------------------------------------------- g03 strip maps
bounds = [0, 0.25, 0.5, 1, 2, 4, 99]
dcmap = ListedColormap(["#f3eee6", "#fde6da", "#f6b596", "#eb6834", "#b8491c", "#7c2e0f"])
dnorm = BoundaryNorm(bounds, dcmap.N)
kmax = P.groupby("corridor").km_start.max().max() + 0.5
fig, axs = plt.subplots(len(CORR), 1, figsize=(15, 2.7 * len(CORR)), facecolor=SURF, sharex=True,
                        gridspec_kw=dict(hspace=0.35))
for ax, corridor in zip(axs, CORR):
    d = P[P.corridor == corridor].merge(tt[["corridor", "piece", "truck_excess_min"]]).merge(
        gr[["corridor", "piece", "built_ha_2000", "built_ha_2020"]], how="left")
    x = d.km_start.to_numpy()
    # growth sparkline (top band): new built-up ha per km 2000-2020
    g = (d.built_ha_2020 - d.built_ha_2000).groupby(np.floor(x)).sum()
    ax.bar(g.index + 0.5, g / g.max() * 0.9 if g.max() > 0 else g, bottom=2.3, width=1, color="#8a6b4e",
           linewidth=0)
    # road type band
    for k, col in TYPE_COL.items():
        m = d.road_type == k
        ax.bar(x[m] + 0.25, np.full(m.sum(), 0.45), bottom=1.65, width=0.5, color=col, linewidth=0)
    # delay line: truck minutes lost per km
    ax.bar(x + 0.25, np.full(len(x), 0.55), bottom=0.9, width=0.5, color=dcmap(dnorm(d.truck_excess_min / 0.5)),
           linewidth=0)
    # controls
    for col_, mk, yy, lab in (("weighbridges", "s", 0.55, "weighbridge"), ("police_posts", "v", 0.55, "police post"),
                              ("signals", "o", 0.55, "signals")):
        m = d[col_] > 0
        ax.scatter(x[m] + 0.25, np.full(m.sum(), yy), marker=mk, s=28 if mk == "s" else 16,
                   color="#17252a" if mk == "s" else ("#4e7c8a" if mk == "v" else "#9fb3b0"),
                   edgecolor="white", linewidth=0.4, zorder=3, label=lab if corridor == CORR[0] else None)
    # towns
    for name, (lo, la) in TOWNS.items():
        dist = np.hypot(d.lon - lo, (d.lat - la))
        if dist.min() < 0.03:
            k = d.km_start.iloc[int(dist.argmin())]
            ax.text(k, 0.15, name, fontsize=8, color=INK, ha="center", va="center", rotation=0)
            ax.plot([k, k], [0.3, 0.88], color=INK2, linewidth=0.5)
    ax.set_ylim(-0.1, 3.3)
    ax.set_xlim(-2, kmax + 2)
    ax.set_yticks([0.55, 1.175, 1.875, 2.75])
    ax.set_yticklabels(["controls", "truck delay", "road type", "new building"], fontsize=8, color=INK2)
    clean(ax, grid=None)
    ax.spines["bottom"].set_visible(False)
    ax.set_title(C.CORRIDORS[corridor]["label"] + f" · {d.km_start.max() + 0.5:.0f} km", loc="left", fontsize=10.5,
                 color=INK)
axs[-1].set_xlabel("km from Kampala", fontsize=9, color=INK2)
axs[-1].spines["bottom"].set_visible(True)
leg = [Line2D([], [], color=c, linewidth=8, label=k) for k, c in TYPE_COL.items()]
leg += [Line2D([], [], color=dcmap(i), linewidth=8, label=f"{a}–{b} min/km" if b < 99 else f"> {a} min/km")
        for i, (a, b) in enumerate(zip(bounds[:-1], bounds[1:]))]
leg += [Line2D([], [], marker=m, color="w", markerfacecolor=c, markersize=7, label=lab)
        for m, c, lab in (("s", "#17252a", "weighbridge"), ("v", "#4e7c8a", "police post"), ("o", "#9fb3b0", "signals"))]
fig.legend(handles=leg, loc="lower center", ncol=6, frameon=False, fontsize=8.5, labelcolor=INK2,
           bbox_to_anchor=(0.5, 0.0))
fig.text(0.125, 0.95, "The corridors as lines", fontsize=15, color=INK)
fig.text(0.125, 0.935, "Every road on one km scale. Top band: new built-up land within 300 m, 2000–2020 (GHSL), "
         "scaled per road. Truck delay: minutes lost per km vs open road.", fontsize=9, color=INK2)
fig.subplots_adjust(bottom=0.1)
save(fig, "g03_strip_maps.png")

# ---------------------------------------------------------------- g04 time map
# Only meaningful when every corridor leaves the same place (Kampala in the Uganda study)
if len({tuple(c["start"]) for c in C.CORRIDORS.values()}) > 1:
    raise SystemExit("corridors start in different places: g04 skipped")
d = P.merge(tt[["corridor", "piece", "truck_outbound_min"]])
g = gpd.GeoDataFrame(d, geometry=gpd.points_from_xy(d.lon, d.lat), crs=4326).to_crs(C.UTM)
d["x"], d["y"] = g.geometry.x / 1000, g.geometry.y / 1000
x0, y0 = d.x[d.km_start == 0].mean(), d.y[d.km_start == 0].mean()
OPEN_KMH = 70   # truck open-road speed: at this speed, time-km equals real km
fig, axs = plt.subplots(1, 2, figsize=(14, 7.6), facecolor=SURF, sharex=True, sharey=True, gridspec_kw=dict(wspace=0.02))
for ax, warped in zip(axs, (False, True)):
    for corridor in CORR:
        c = d[d.corridor == corridor].sort_values("piece")
        dx, dy = c.x.to_numpy() - x0, c.y.to_numpy() - y0
        if warped:
            real = (c.km_start + 0.5).to_numpy()
            tkm = c.truck_outbound_min.cumsum().to_numpy() / 60 * OPEN_KMH
            r = tkm / real
            ax.plot(dx, dy, color="#d8d5ce", linewidth=1.2, zorder=1)
            dx, dy = dx * r, dy * r
            hours = c.truck_outbound_min.cumsum().to_numpy() / 60
            for h in range(1, int(hours.max()) + 1):
                i = int(np.searchsorted(hours, h))
                ax.scatter(dx[i], dy[i], s=14, color="white", edgecolor=CORR_COL[corridor], linewidth=1.2, zorder=4)
                if np.hypot(dx[i] - dx[-1], dy[i] - dy[-1]) > 25:  # keep clear of the end label
                    ax.text(dx[i] + 6, dy[i], f"{h} h", fontsize=7, color=INK2, zorder=5)
        ax.plot(dx, dy, color=CORR_COL[corridor], linewidth=2.6, zorder=3, solid_capstyle="round")
        ax.text(dx[-1] + 8, dy[-1], C.CORRIDORS[corridor]["short"], fontsize=10, color=CORR_COL[corridor],
                fontweight="bold", va="center")
    ax.scatter([0], [0], s=60, color=INK, zorder=5)
    ax.text(10, -18, "Kampala", fontsize=10, color=INK, fontweight="bold")
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.set_title("Distance: the corridors as mapped" if not warped else
                 f"Time: 1 km drawn per {60 / OPEN_KMH:.2f} min a loaded truck needs (grey: mapped)",
                 loc="left", fontsize=11, color=INK)
fig.text(0.125, 0.97, "When distance becomes time", fontsize=15, color=INK)
fig.text(0.125, 0.94, "Right: each road stretched so that its length is the modelled truck travel time at open-road "
         "speed. Towns, controls and hills make the roads longer. Dots mark each hour.", fontsize=9, color=INK2)
save(fig, "g04_time_map.png")
