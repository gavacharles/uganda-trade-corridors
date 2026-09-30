"""Do police crash black spots fall where the safety exposure index is high?

Uganda Police publishes crashes only nationally and by police region, which cannot separate
the corridors from every other road. Traffic officers on each highway did, however, name their
black spots (Daily Monitor, 23 Dec 2018, inputs/police_black_spots_2018.csv): about sixty
places on the Jinja-Iganga, Masaka-Mbarara, Bombo-Gulu and Mityana roads.

Each black spot is located by its name among OSM named points within 2.5 km of its corridor
(nearest match wins; unmatched names are reported). The 2 km stretches holding a black spot are
compared with all stretches of the same roads on the safety exposure index (19_safety.py) and on
the road's design: truck speed, curvature, grade, wetland share, joining roads and roadside
buildings. Each measure is expressed as a within-corridor percentile, so 50 means typical. A
permutation test (black spots placed at random stretches of the same corridors, 5,000 times)
gives how often chance alone would produce a mean percentile as far from 50.

Locating by name favours settlements: villages carry names in OSM, forest and swamp stretches
often do not. A second, stricter test therefore places the black spots at random only among
stretches that also hold a named OSM place (city to hamlet) within 2.5 km, so both sides share
the same bias.

The list is old (2018), selective (officers' judgement, not crash counts) and located by name,
so the test is indicative. It asks whether the index points at the places police already worry
about, and if not, what those places share instead.

Writes outputs/black_spots_matched.csv, outputs/black_spots_test.csv, figures/f15_black_spots.png.
"""
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import pyogrio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config as C
from cartography import INK, INK2, SURF

RNG = np.random.default_rng(25)
N_PERM, MATCH_M, STRETCH_KM = 5000, 2500, 2.0

spots = pd.read_csv(os.path.join(C.ROOT, "inputs", "police_black_spots_2018.csv"))
spots = spots[spots.corridor.isin(C.CORRIDORS)]
P = pd.read_csv(os.path.join(C.OUTPUTS, "pieces_typed.csv"))
S = pd.read_csv(os.path.join(C.OUTPUTS, "safety_pieces.csv"))[["corridor", "piece", "exposure", "truck_kmh",
                                                                  "people_300m"]]
P = P.merge(S, on=["corridor", "piece"], how="left")
P["stretch"] = (P.km_start // STRETCH_KM).astype(int)
P["joining_roads"] = P.junctions_major + P.junctions_minor
pts = gpd.GeoDataFrame(P, geometry=gpd.points_from_xy(P.lon, P.lat), crs=4326).to_crs(C.UTM)

# Named OSM points (places, shops, schools, ...) near the corridors
names = pyogrio.read_dataframe(C.PBF, layer="points", columns=["name", "place"], where="name IS NOT NULL")
names = names.to_crs(C.UTM)
names = names[names.geometry.intersects(pts.buffer(MATCH_M).union_all())]
names["key"] = names.name.str.lower().str.strip()
placed = names[names.place.notna()]
P["near_place"] = pts.distance(placed.union_all()).to_numpy() <= MATCH_M

rows = []
for s in spots.itertuples():
    cp = pts[pts.corridor == s.corridor]
    keys = [k.strip().lower() for k in s.search_names.split(";")]
    cand = names[names.key.isin(keys) | names.key.str.split().str[0].isin(keys)]
    best = None
    for c in cand.itertuples():
        d = cp.distance(c.geometry)
        if d.min() <= MATCH_M and (best is None or d.min() < best[1]):
            best = (d.idxmin(), d.min(), c.name)
    if best is None:
        rows.append(dict(corridor=s.corridor, name=s.name, feature=s.feature, matched=False))
        continue
    p = P.loc[best[0]]
    rows.append(dict(corridor=s.corridor, name=s.name, feature=s.feature, matched=True, osm_name=best[2],
                     distance_m=round(best[1]), km=p.km_mid, stretch=p.stretch, road_type=p.road_type))
M = pd.DataFrame(rows)
M.to_csv(os.path.join(C.OUTPUTS, "black_spots_matched.csv"), index=False)
print(f"{M.matched.sum()} of {len(M)} black spots located; unmatched:",
      ", ".join(M[~M.matched].name) or "none")

# Stretch table, measures as within-corridor percentiles
MEAS = {"exposure": "safety exposure index", "truck_kmh": "truck speed", "curvature_deg_per_km": "curvature",
        "grade_pct": "grade", "wetland_share": "wetland share", "joining_roads": "joining roads",
        "buildings_300m": "buildings within 300 m"}
agg = {k: ("max" if k in ("curvature_deg_per_km", "grade_pct") else "mean") for k in MEAS}
agg.update(joining_roads="sum", buildings_300m="sum", exposure="sum")
agg["near_place"] = "max"
T = P.groupby(["corridor", "stretch"]).agg(agg).reset_index()
for k in MEAS:
    T[k + "_pct"] = T.groupby("corridor")[k].rank(pct=True) * 100
hit = M[M.matched].drop_duplicates(["corridor", "stretch"])[["corridor", "stretch"]].assign(black_spot=True)
T = T.merge(hit, on=["corridor", "stretch"], how="left").fillna({"black_spot": False})
T["black_spot"] = T.black_spot.astype(bool)

# Permutation tests: same number of black-spot stretches per corridor, placed at random among
# all stretches, or only among stretches near a named place
counts = T.groupby("corridor").black_spot.sum()
res = []
for null_name, pool in (("all stretches", np.ones(len(T), bool)), ("stretches near a named place", T.near_place)):
    groups = {c: T.index[(T.corridor == c) & pool].to_numpy() for c in counts.index}
    for k, label in MEAS.items():
        v = T[k + "_pct"].to_numpy()
        obs = v[T.black_spot].mean()
        null = np.array([np.mean(np.concatenate([v[RNG.choice(groups[c], int(n), replace=False)]
                                                 for c, n in counts.items() if n])) for _ in range(N_PERM)])
        p = (np.sum(np.abs(null - null.mean()) >= abs(obs - null.mean())) + 1) / (N_PERM + 1)
        res.append(dict(null=null_name, measure=label, black_spot_mean_pct=round(obs, 1),
                        null_mean=round(null.mean(), 1), null_p5=round(np.percentile(null, 5), 1),
                        null_p95=round(np.percentile(null, 95), 1), p_value=round(p, 4),
                        top_quintile_share_pct=round(100 * np.mean(v[T.black_spot] >= 80)),
                        n_black_spot_stretches=int(T.black_spot.sum()), n_pool=int(pool.sum())))
R = pd.DataFrame(res)
R.to_csv(os.path.join(C.OUTPUTS, "black_spots_test.csv"), index=False)
print(R.to_string(index=False))
print("black spots by road type:\n", M[M.matched].road_type.value_counts(normalize=True).round(2).to_string())

# Figure: mean percentile of black-spot stretches against the stricter chance band
R = R[R.null == "stretches near a named place"].sort_values("black_spot_mean_pct")
fig, ax = plt.subplots(figsize=(10, 4.6), facecolor=SURF)
y = np.arange(len(R))
ax.hlines(y, R.null_p5, R.null_p95, color="#d8d6d0", linewidth=9, label="90% range if placed at random near a named place")
ax.axvline(50, color=INK2, linewidth=0.8, linestyle=":")
ax.scatter(R.black_spot_mean_pct, y, s=60, zorder=3, color=["#c4532d" if p < 0.05 else "#9fb3b0" for p in R.p_value])
for yi, r in zip(y, R.itertuples()):
    ax.text(max(r.black_spot_mean_pct, r.null_p95) + 1.5, yi, f"{r.black_spot_mean_pct:.0f}  (p = {r.p_value:.3f})",
            va="center", fontsize=8.5, color=INK)
ax.set_yticks(y)
ax.set_yticklabels(R.measure, fontsize=9.5, color=INK)
ax.set_xlim(20, 90)
ax.set_xlabel("mean within-corridor percentile of the 2 km stretches holding a police black spot", fontsize=9, color=INK2)
ax.legend(loc="lower right", frameon=False, fontsize=8.5, labelcolor=INK2)
ax.set_facecolor(SURF)
for s_ in ("top", "right", "left"):
    ax.spines[s_].set_visible(False)
ax.spines["bottom"].set_color("#e4e3df")
ax.tick_params(colors=INK2, length=0)
n = int(M.matched.sum())
fig.text(0.01, 1.05, "What police crash black spots have in common", fontsize=15, color=INK)
fig.text(0.01, 0.995, f"{n} black spots named by Uganda Police traffic officers (2018), located by name in OSM. "
         "Orange: outside the chance range (p < 0.05).", fontsize=9, color=INK2)
fig.savefig(os.path.join(C.FIGURES, "f15_black_spots.png"), dpi=150, facecolor=SURF, bbox_inches="tight")
print("wrote outputs/black_spots_*.csv, figures/f15_black_spots.png")
