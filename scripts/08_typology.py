"""Group the 500 m pieces into road types by what lines the road.

K-means on four standardised measures of roadside activity: log buildings within
100 m and within 300 m, joining roads, and log shops/markets/fuel/stops. Terrain and
water are left out on purpose: they are separate causes, not types of roadside.
The number of types is chosen by silhouette score (3 to 6), and types are named in
order of roadside building density, so names are stable between runs.

Writes outputs/pieces_typed.csv, outputs/typology_summary.csv and
figures/f02_typology.png.
"""
import os, sys
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

import config as C

from cartography import INK, INK2, SURF  # noqa: E402

NAMES = {3: ["open road", "roadside settlement", "town"],
         4: ["open road", "scattered roadside", "trading centre", "town"],
         5: ["open road", "scattered roadside", "roadside settlement", "trading centre", "town"],
         6: ["open road", "scattered roadside", "roadside settlement", "trading centre", "busy town",
             "city edge"]}
RAMP = ["#dfe9f5", "#a9c8ec", "#6aa2e0", "#3574c4", "#1c4f8f", "#0d2d57"]  # light -> dark

P = pd.read_csv(os.path.join(C.OUTPUTS, "pieces.csv"))
X = pd.DataFrame({
    "log_buildings_100m": np.log1p(P.buildings_100m),
    "log_buildings_300m": np.log1p(P.buildings_300m),
    "joining_roads": P.junctions_major + P.junctions_minor,
    "log_activity": np.log1p(P.shops_200m + P.markets_200m + P.fuel_200m + P.stops_100m),
})
Z = StandardScaler().fit_transform(X)
scores = {k: silhouette_score(Z, KMeans(k, n_init=20, random_state=0).fit_predict(Z)) for k in range(3, 7)}
k = max(scores, key=scores.get)
print("silhouette by k:", {kk: round(v, 3) for kk, v in scores.items()}, "-> k =", k)
km = KMeans(k, n_init=20, random_state=0).fit(Z)
order = np.argsort(pd.Series(km.labels_).groupby(km.labels_).apply(lambda i: P.buildings_100m[i.index].mean()).to_numpy())
rank = {int(c): r for r, c in enumerate(order)}
P["type_rank"] = [rank[int(c)] for c in km.labels_]
COL = [RAMP[int(i)] for i in np.round(np.linspace(1, 5, k))]  # spread across the ramp
P["road_type"] = [NAMES[k][r] for r in P.type_rank]
P.to_csv(os.path.join(C.OUTPUTS, "pieces_typed.csv"), index=False)

summ = (P.groupby(["corridor", "type_rank", "road_type"])
        .agg(km=("piece", lambda s: len(s) * 0.5), buildings_100m=("buildings_100m", "mean"),
             joining_roads=("junctions_minor", lambda s: (s + P.loc[s.index, "junctions_major"]).mean()),
             activity=("shops_200m", lambda s: (s + P.loc[s.index, ["markets_200m", "fuel_200m", "stops_100m"]]
                                                .sum(axis=1)).mean()))
        .round(1).reset_index())
summ["share"] = (summ.km / summ.groupby("corridor").km.transform("sum")).round(3)
summ.to_csv(os.path.join(C.OUTPUTS, "typology_summary.csv"), index=False)
print(summ.to_string(index=False))

# Figure: each corridor as a ribbon of types along its length, plus a map
pieces = gpd.read_file(os.path.join(C.DATA, "pieces.gpkg")).merge(P[["corridor", "piece", "type_rank"]])
n = len(C.CORRIDORS)
fig = plt.figure(figsize=(13, 3.2 + 1.6 * n), facecolor=SURF)
axm = fig.add_axes([0.02, 0.05, 0.36, 0.84])
for r in range(k):
    pieces[pieces.type_rank == r].plot(ax=axm, color=COL[r], linewidth=3.2)
axm.set_axis_off()
axm.set_aspect(1 / np.cos(np.radians(1.5)))
ends = [("Kampala", (32.58, 0.31), "right")] + [(c["short"], c["end"], "left") for c in C.CORRIDORS.values()]
for name, (lon, lat), ha in ends:
    axm.plot(lon, lat, "o", color=INK, markersize=4)
    axm.text(lon + (0.04 if ha == "left" else -0.04), lat, name, ha=ha, va="center", fontsize=9, color=INK)

step = 0.70 / n
for i, (corridor, cfg) in enumerate(C.CORRIDORS.items()):
    title = cfg["label"]
    d = P[P.corridor == corridor]
    ax = fig.add_axes([0.44, 0.83 - (i + 1) * step + 0.03, 0.54, step * 0.32])
    for r in range(k):
        s = d[d.type_rank == r]
        ax.bar(s.km_mid, 1, width=0.5, color=COL[r], linewidth=0)
    ax.set_xlim(0, d.km_mid.max() + 0.25)
    ax.set_ylim(0, 1)
    ax.set_yticks([])
    for s_ in ("top", "right", "left"):
        ax.spines[s_].set_visible(False)
    ax.tick_params(colors=INK2, labelsize=8, length=0)
    ax.set_xlabel("km from Kampala", fontsize=8.5, color=INK2)
    sh = summ[summ.corridor == corridor].set_index("road_type").share
    ax.text(0, 1.25, title, transform=ax.transAxes, fontsize=11, color=INK, va="bottom")
    ax.text(0, 1.08, " · ".join(f"{t} {sh.get(t, 0):.0%}" for t in NAMES[k]), transform=ax.transAxes,
            fontsize=8.5, color=INK2, va="bottom")

# Legend with what each type means
lx, ly = 0.44, 0.06
for r, name in enumerate(NAMES[k]):
    row = summ[summ.type_rank == r]
    b = (row.buildings_100m * row.km).sum() / row.km.sum()
    fig.patches.append(plt.Rectangle((lx + r * 0.108, ly), 0.02, 0.025, transform=fig.transFigure,
                                     color=COL[r]))
    fig.text(lx + r * 0.108 + 0.025, ly + 0.0125, f"{name}\n~{b:.0f} buildings\nper 500 m", fontsize=8,
             color=INK2, va="center")
fig.text(0.02, 0.95, "Road types along the corridors", fontsize=15, color=INK)
fig.text(0.02, 0.915, f"500 m pieces grouped by roadside buildings, joining roads and roadside businesses "
         f"(k-means, k = {k} by silhouette)", fontsize=9.5, color=INK2)
fig.text(0.44, 0.015, "Sources: OpenStreetMap; Google Open Buildings v3.", fontsize=8, color=INK2)
out = os.path.join(C.FIGURES, "f02_typology.png")
fig.savefig(out, dpi=150, facecolor=SURF)
print("wrote", out)
