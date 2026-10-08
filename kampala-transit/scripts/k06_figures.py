"""Figures for the scenario and clearance results (after k04 and k05).

    python kampala-transit/scripts/k06_figures.py

  figures/k04_breakeven.png   share of all trip time saved by each line as roads get more congested,
                              BRT and light rail, and the five-line BRT network
  figures/k05_access.png      gain in jobs (built-up floor area) reachable in 45 min: everyone, and the
                              40% of residents with the least access today (roads 2x slower than assumed)
  figures/k06_clearance.png   clear width between building lines every 100 m along the candidates, and
                              the buildings inside a 24 m and a 30 m corridor
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

HERE = os.path.dirname(os.path.abspath(__file__))
KT = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(KT, ".."))
import sys; sys.path.insert(0, os.path.join(ROOT, "scripts"))  # noqa: E702
import cartography as K  # noqa: E402

INK, INK2, SURF, GRID, LAND, WATER = "#1d2321", "#5d6764", "#fcfcfb", "#e6e4de", "#f6f4ef", "#c9dbe6"
FIG = os.path.join(KT, "figures")
R = pd.read_csv(os.path.join(KT, "outputs", "scenarios.csv"))
CASES = ["roads as assumed", "roads 1.5x slower", "roads 2x slower", "roads 3x slower"]
XLAB = ["as assumed", "1.5× slower", "2× slower", "3× slower"]
R["short"] = R.name.str.replace("BRT network: .*", "Five-line BRT network", regex=True)


def style(ax):
    ax.set_facecolor(SURF)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(GRID); ax.spines["bottom"].set_color(GRID)
    ax.grid(axis="y", color=GRID); ax.set_axisbelow(True)
    ax.tick_params(colors=INK2, length=0)


# ---------------------------------------------------------------- break-even
top = (R[(R.case == "roads 2x slower") & (R["mode"] != "BRT network")]
       .groupby("short").saving_pct.max().sort_values(ascending=False).head(6).index)
fig, axs = plt.subplots(1, 2, figsize=(14, 6), facecolor=SURF, sharey=True)
cmap = plt.get_cmap("tab10")
for ax, mode in zip(axs, ("BRT", "light rail")):
    for i, nm in enumerate(top):
        d = R[(R.short == nm) & (R["mode"] == mode)].set_index("case").reindex(CASES)
        ax.plot(range(4), d.saving_pct, marker="o", lw=2, color=cmap(i), label=nm)
    net = R[R["mode"] == "BRT network"].set_index("case").reindex(CASES)
    ax.plot(range(4), net.saving_pct, marker="s", lw=3, color=INK, ls="--", label="Five-line BRT network")
    ax.set_xticks(range(4)); ax.set_xticklabels(XLAB, fontsize=10)
    ax.set_xlabel("peak road speeds compared with the assumed (k01)", fontsize=10, color=INK2)
    ax.set_title(mode if mode == "BRT" else "Light rail", loc="left", fontsize=12, color=INK)
    style(ax)
axs[0].set_ylabel("% of all modelled trip time saved", fontsize=10, color=INK2)
axs[1].legend(frameon=False, fontsize=9, loc="upper left")
fig.text(0.01, 1.02, "How congested must the roads be before a line pays off?", fontsize=15, color=INK)
fig.text(0.01, 0.975, "Each line runs in its own lane at its commercial speed (BRT 22, light rail 28 km/h) with a "
         "5–6 minute wait and walk; minibus taxis stay in traffic. Demand held at the baseline.", fontsize=9.5,
         color=INK2)
fig.savefig(os.path.join(FIG, "k04_breakeven.png"), dpi=160, facecolor=SURF, bbox_inches="tight")
plt.close(fig)

# ---------------------------------------------------------------- access
d = R[(R.case == "roads 2x slower")].copy()
d = d[d.short.isin(list(top) + ["Five-line BRT network"])]
d["lab"] = d.short + " · " + d["mode"].str.replace("BRT network", "BRT")
d = d.sort_values("access_gain_low40_pct")
fig, ax = plt.subplots(figsize=(12, 7), facecolor=SURF)
y = np.arange(len(d))
ax.barh(y - 0.2, d.access_gain_pct, height=0.38, color="#9fb3b0", label="all residents")
ax.barh(y + 0.2, d.access_gain_low40_pct, height=0.38, color="#c4532d", label="40% with the least access today")
ax.set_yticks(y); ax.set_yticklabels(d.lab, fontsize=9.5, color=INK)
style(ax); ax.grid(axis="x", color=GRID); ax.grid(axis="y", visible=False)
ax.set_xlabel("% more jobs and services (built-up floor area) reachable within 45 minutes", fontsize=10, color=INK2)
ax.legend(frameon=False, fontsize=10, loc="lower right")
fig.text(0.01, 1.0, "Who gains access? (roads 2× slower than assumed)", fontsize=15, color=INK)
fig.text(0.01, 0.965, "Population-weighted change in reachable floor area; the lower group are the residents "
         "with the least access under today's network.", fontsize=9.5, color=INK2)
fig.savefig(os.path.join(FIG, "k05_access.png"), dpi=160, facecolor=SURF, bbox_inches="tight")
plt.close(fig)

# ---------------------------------------------------------------- clearance
S = gpd.read_file(os.path.join(KT, "outputs", "clearance_sections.gpkg"))
CL = pd.read_csv(os.path.join(KT, "outputs", "clearance.csv"))
E = gpd.read_file(os.path.join(KT, "outputs", "edges.gpkg"))
lakes = gpd.read_file(os.path.join(ROOT, "data", "ne_lakes", "ne_10m_lakes.shp")).to_crs(4326).cx[32.2:33.1, -0.2:0.7]
fig = plt.figure(figsize=(16, 9.5), facecolor=SURF)
ax = fig.add_axes([0.01, 0.04, 0.52, 0.86])
EXT = (32.36, 32.86, 0.06, 0.52)
K.frame(ax, EXT)
lakes.plot(ax=ax, aspect=None, color=WATER, linewidth=0)
K.frame(ax, EXT)
ax.set_facecolor(LAND)
E.plot(ax=ax, aspect=None, color="#d3cdc0", linewidth=0.5)
bins = [0, 20, 24, 30, 40, 1000]
cm = ListedColormap(["#7c2e0f", "#c4532d", "#e8c77e", "#a9c27d", "#3a7d5c"])
nm = BoundaryNorm(bins, cm.N)
ax.scatter(S.geometry.x, S.geometry.y, c=S.width, cmap=cm, norm=nm, s=9, linewidths=0, zorder=4)
K.furniture(ax, km=5)
ax.legend(handles=[Line2D([], [], marker="o", ls="none", color=cm(i), markersize=7, label=l) for i, l in
                   enumerate(["< 20 m", "20–24 m", "24–30 m", "30–40 m", "> 40 m"])],
          title="clear width between building lines", loc="lower left", frameon=True, facecolor="white", fontsize=9)
ax2 = fig.add_axes([0.62, 0.12, 0.36, 0.76])
c = CL[CL.km >= 5].sort_values("demolish_tight_per_km")
yy = np.arange(len(c))
ax2.barh(yy - 0.2, c.demolish_tight_per_km, height=0.38, color="#c4532d", label="24 m corridor")
ax2.barh(yy + 0.2, c.demolish_full_per_km, height=0.38, color="#e8c77e", label="30 m corridor")
ax2.set_yticks(yy); ax2.set_yticklabels(c["name"], fontsize=9.5, color=INK)
style(ax2); ax2.grid(axis="x", color=GRID); ax2.grid(axis="y", visible=False)
ax2.set_xlabel("buildings whose footprint lies inside the corridor, per km", fontsize=10, color=INK2)
ax2.legend(frameon=False, fontsize=10, loc="lower right")
ax2.set_title("What the space would cost", loc="left", fontsize=12, color=INK)
fig.text(0.01, 0.965, "Is there room for a busway or tramway?", fontsize=15, color=INK)
fig.text(0.01, 0.935, "Cross-sections every 100 m on the candidates (Google Open Buildings footprints). A median "
         "busway or double track with stations needs about 24 m at the tightest, 30 m with parking and loading.",
         fontsize=9.5, color=INK2)
fig.savefig(os.path.join(FIG, "k06_clearance.png"), dpi=160, facecolor=SURF, bbox_inches="tight")
plt.close(fig)
print("wrote k04_breakeven.png, k05_access.png, k06_clearance.png")
