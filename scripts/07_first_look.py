"""First look: every measured cause of delay along each corridor, as stacked strips
sharing one x axis (km from Kampala). One figure per corridor:
figures/f01_causes_<corridor>.png.
"""
import os, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

import config as C

from cartography import INK, INK2, SURF, BLUES, ORANGES  # noqa: E402

GRID = "#e4e3df"
TITLES = {k: v["label"] for k, v in C.CORRIDORS.items()}
P = pd.read_csv(os.path.join(C.OUTPUTS, "pieces.csv"))
os.makedirs(C.FIGURES, exist_ok=True)


def style(ax, label):
    ax.set_facecolor(SURF)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.yaxis.set_major_locator(MaxNLocator(nbins=4, integer=True))
    ax.text(0, 1.02, label, transform=ax.transAxes, fontsize=9.5, color=INK, ha="left", va="bottom")


def label_towns(ax, d, n):
    """Name the n densest trading centres, at least 8% of the route apart."""
    L, taken = d.km_mid.max(), []
    for r in d.sort_values("buildings_100m", ascending=False).itertuples():
        if len(taken) == n:
            break
        if not isinstance(r.place, str) or any(abs(r.km_mid - t) < 0.08 * L for t in taken):
            continue
        taken.append(r.km_mid)
        ax.annotate(r.place, (r.km_mid, r.buildings_100m), xytext=(0, 4), textcoords="offset points",
                    ha="center", va="bottom", fontsize=7.5, color=INK2)


for corridor, d in P.groupby("corridor"):
    x, w = d.km_mid.to_numpy(), 0.5
    fig, axs = plt.subplots(6, 1, figsize=(13, 11), sharex=True, facecolor=SURF,
                            gridspec_kw=dict(height_ratios=[1.4, 1, 1, 0.7, 1.1, 0.7], hspace=0.55))

    ax = axs[0]
    style(ax, "Roadside buildings within 100 m, per 500 m")
    ax.bar(x, d.buildings_100m, width=w * 0.9, color=BLUES[3], linewidth=0)
    ax.set_ylim(0, d.buildings_100m.max() * 1.25)
    label_towns(ax, d, 6 + int(d.km_mid.max() // 100))

    ax = axs[1]
    style(ax, "Roads joining the corridor, per 500 m")
    ax.bar(x, d.junctions_minor, width=w * 0.9, color=BLUES[1], linewidth=0, label="minor (residential, track, service)")
    ax.bar(x, d.junctions_major, bottom=d.junctions_minor, width=w * 0.9, color=BLUES[4], linewidth=0,
           label="major (tertiary and above)")
    ax.legend(loc="upper right", frameon=False, fontsize=8, labelcolor=INK2, ncol=2)

    ax = axs[2]
    style(ax, "Shops, markets, fuel stations and stops within 200 m, per 500 m")
    act = d.shops_200m + d.markets_200m + d.fuel_200m + d.stops_100m
    ax.bar(x, act, width=w * 0.9, color=BLUES[3], linewidth=0)

    ax = axs[3]
    style(ax, "Point controls on the road (OSM; speed humps heavily under-recorded)")
    kinds = [("humps", "speed hump", "^"), ("signals", "signals", "s"), ("ped_crossings", "pedestrian crossing", "o"),
             ("level_crossings", "level crossing", "X"), ("police_posts", "police post", "D"), ("weighbridges", "weighbridge", "P")]
    for i, (col, lab, m) in enumerate(kinds):
        k = d[d[col] > 0]
        ax.scatter(k.km_mid, np.full(len(k), i), marker=m, s=34, color=INK, linewidths=0)
        ax.text(-0.005, i, lab, transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=7.5, color=INK2)
    ax.set_yticks([])
    ax.set_ylim(-0.7, len(kinds) - 0.3)
    ax.grid(False)

    ax = axs[4]
    style(ax, "Elevation (m); orange where the piece averages more than 3% up or down")
    ax.plot(x, d.elev_m, color=INK2, linewidth=1.5)
    steep = d.grade_pct.abs() > 3
    ax.scatter(x[steep], d.elev_m[steep], s=14, color=ORANGES[2], zorder=3, linewidths=0)
    lo, hi = d.elev_m.min(), d.elev_m.max()
    ax.set_ylim(lo - 0.1 * (hi - lo), hi + 0.1 * (hi - lo))

    ax = axs[5]
    style(ax, "Water: waterway crossings per 500 m (bars); shaded where the road crosses wetland")
    for k in d[d.wetland_share > 0].km_mid:
        ax.axvspan(k - w / 2, k + w / 2, color=BLUES[0], linewidth=0, zorder=0)
    ax.bar(x, d.water_crossings, width=w * 0.9, color=BLUES[3], linewidth=0, zorder=2)

    axs[-1].set_xlabel("km from Kampala", color=INK2, fontsize=9)
    axs[-1].set_xlim(0, d.km_mid.max() + 0.5)
    L = d.km_mid.max()
    fig.suptitle(f"What lines the road: {TITLES[corridor]}", x=0.125, ha="left", y=0.965,
                 fontsize=15, color=INK)
    fig.text(0.125, 0.935, f"{L:.0f} km in 500 m pieces · {int(d.buildings_100m.sum()):,} buildings within 100 m "
             f"· {int((d.junctions_major + d.junctions_minor).sum()):,} joining roads "
             f"· wet days (≥10 mm) {d.wet_days_per_year.min():.0f}–{d.wet_days_per_year.max():.0f} a year",
             fontsize=9.5, color=INK2, ha="left")
    fig.text(0.125, 0.04, "Sources: OpenStreetMap; Google Open Buildings v3; Copernicus GLO-30; CHIRPS 2006–2025.",
             fontsize=8, color=INK2, ha="left")
    out = os.path.join(C.FIGURES, f"f01_causes_{corridor}.png")
    fig.savefig(out, dpi=150, facecolor=SURF, bbox_inches="tight")
    print("wrote", out)
