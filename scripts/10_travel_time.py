"""From causes to minutes: a transparent travel-time model for each 500 m piece.

For a car and a loaded truck, in both directions, the speed of a piece starts at an
open-road speed and is reduced by each measured cause; fixed delays are added for
point controls. Summing pieces gives the corridor time. Switching one cause off at
a time gives the minutes that cause adds. There are no congestion or queueing terms:
the model describes what the road and its roadside allow when traffic is light, so
the gap to observed peak-hour times is congestion, reported separately.

All assumptions are in PARAMS, each with a central value and a range. A Monte Carlo
run (N_DRAWS) samples every parameter uniformly within its range, so each result has
an interval, and the ranking of causes can be checked for stability.

Writes:
  outputs/travel_time_pieces.csv    central-case time per piece, vehicle, direction
  outputs/travel_time_causes.csv    minutes added by each cause (central, p5, p95)
  outputs/travel_time_totals.csv    corridor totals against the validation targets
  outputs/travel_time_piece_causes.csv  minutes each cause adds in each piece (outbound)
  outputs/hotspots.csv              2 km stretches with the most excess minutes, with main causes
  figures/f04_minutes_by_cause.png, figures/f05_hotspots.png
"""
import os, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

import config as C

from cartography import INK, INK2, SURF  # noqa: E402
from travel_model import PARAMS, CAUSES, P, piece_minutes  # noqa: E402

N_DRAWS = 1000
RNG = np.random.default_rng(42)


CORR_ORDER = P.corridor.unique()
CORR_CODE = pd.Categorical(P.corridor, categories=CORR_ORDER).codes


def by_corridor(x):
    """Sum a per-piece array within each corridor (in CORR_ORDER)."""
    return np.bincount(CORR_CODE, weights=x, minlength=len(CORR_ORDER))


def totals(p):
    """Corridor minutes for every vehicle/direction, all causes on, each cause off, and wet.
    Each cause is evaluated once over all pieces and then summed by corridor, so the cost grows
    with the number of pieces, not pieces x corridors (54 corridors in the regional study)."""
    rows = []
    for veh in ("car", "truck"):
        for direction in ("outbound", "inbound"):
            base = by_corridor(piece_minutes(p, veh, direction))
            ideal = by_corridor(piece_minutes(p, veh, direction, off=CAUSES))
            wet = by_corridor(piece_minutes(p, veh, direction, wet=True))
            off = {c: by_corridor(piece_minutes(p, veh, direction, off=(c,))) for c in CAUSES}
            for j, corridor in enumerate(CORR_ORDER):
                r = dict(corridor=corridor, vehicle=veh, direction=direction,
                         minutes=base[j], open_road_minutes=ideal[j], wet_extra=wet[j] - base[j])
                for c in CAUSES:
                    r[c] = base[j] - off[c][j]
                rows.append(r)
    return pd.DataFrame(rows)


central = {k: v[0] for k, v in PARAMS.items()}
T0 = totals(central)
draws = []
for i in range(N_DRAWS):
    p = {k: RNG.uniform(lo, hi) for k, (_, lo, hi) in PARAMS.items()}
    draws.append(totals(p).assign(draw=i))
D = pd.concat(draws)

keys = ["corridor", "vehicle", "direction"]
q = D.groupby(keys)[["minutes", "wet_extra"] + CAUSES].quantile([0.05, 0.95]).unstack()
out_c = []
for _, r in T0.iterrows():
    k = tuple(r[keys])
    for c in CAUSES + ["wet_extra"]:
        out_c.append(dict(zip(keys, k), cause=("rain (wet day)" if c == "wet_extra" else c),
                          minutes=round(r[c], 1), p5=round(q.loc[k, (c, 0.05)], 1), p95=round(q.loc[k, (c, 0.95)], 1)))
causes = pd.DataFrame(out_c)
causes.to_csv(os.path.join(C.OUTPUTS, "travel_time_causes.csv"), index=False)

# Rank stability: how often is each cause the largest, per corridor and vehicle (outbound)
top = (D[D.direction == "outbound"].set_index(keys + ["draw"])[CAUSES].idxmax(axis=1)
       .groupby(level=[0, 1]).value_counts(normalize=True).round(2))
print("Largest cause across draws (share of draws):\n", top.to_string())
# Share of draws in which each cause adds the most minutes, and ranks in the top three
rk = D[D.direction == "outbound"].set_index(keys + ["draw"])[CAUSES].rank(axis=1, ascending=False, method="first")
stab = pd.concat([(rk == 1).groupby(level=[0, 1]).mean().stack().rename("share_first"),
                  (rk <= 3).groupby(level=[0, 1]).mean().stack().rename("share_top3")], axis=1)
stab.index.names = ["corridor", "vehicle", "cause"]
stab.round(3).reset_index().to_csv(os.path.join(C.OUTPUTS, "rank_stability.csv"), index=False)

VALID = C.VALIDATION
# Model minutes up to each validation end point (car, outbound, central case)
car_out = piece_minutes(central, "car", "outbound")
vrows = []
for (corridor, veh), items in VALID.items():
    m = (P.corridor == corridor).to_numpy()
    for label, lo, hi, kind, to in items:
        cut = m.copy()
        if to is not None:
            d = P[m]
            k_end = d.km_mid[((d.lon - to[0]) ** 2 + (d.lat - to[1]) ** 2).idxmin()]
            cut = m & (P.km_mid <= k_end).to_numpy()
        vrows.append(dict(corridor=corridor, vehicle=veh, source=label, kind=kind, reported_min=lo,
                          reported_max=hi, model_km=round(P.length_km[cut].sum(), 1),
                          model_min=round(car_out[cut].sum(), 0)))
pd.DataFrame(vrows).to_csv(os.path.join(C.OUTPUTS, "validation.csv"), index=False)
print(pd.DataFrame(vrows).to_string(index=False))
tot = T0[keys + ["minutes", "open_road_minutes", "wet_extra"]].copy()
tot = tot.merge(q["minutes"].rename(columns={0.05: "p5", 0.95: "p95"}).reset_index(), on=keys)
tot.round(1).to_csv(os.path.join(C.OUTPUTS, "travel_time_totals.csv"), index=False)
print(tot.round(0).to_string(index=False))

# Per-piece central times and excess over open road (car and truck, outbound)
pp = P[["corridor", "piece", "km_mid", "road_type", "place"]].copy()
for veh in ("car", "truck"):
    for direction in ("outbound", "inbound"):
        pp[f"{veh}_{direction}_min"] = piece_minutes(central, veh, direction).round(3)
    pp[f"{veh}_excess_min"] = (piece_minutes(central, veh, "outbound") -
                               piece_minutes(central, veh, "outbound", off=CAUSES)).round(3)
pp.to_csv(os.path.join(C.OUTPUTS, "travel_time_pieces.csv"), index=False)
pc = P[["corridor", "piece", "km_mid"]].copy()
for veh in ("car", "truck"):
    base_t = piece_minutes(central, veh, "outbound")
    for c in CAUSES:
        pc[f"{veh}|{c}"] = (base_t - piece_minutes(central, veh, "outbound", off=(c,))).round(3)
pc.to_csv(os.path.join(C.OUTPUTS, "travel_time_piece_causes.csv"), index=False)

# Hotspots: 2 km windows (4 pieces) ranked by excess truck + car minutes
hs = []
for corridor, d in pp.groupby("corridor"):
    d = d.reset_index(drop=True)
    w = (d.car_excess_min + d.truck_excess_min).rolling(4).sum()
    used = np.zeros(len(d), bool)
    for i in w.sort_values(ascending=False).index:
        if np.isnan(w[i]) or used[i - 3:i + 1].any():
            continue
        used[i - 3:i + 1] = True
        seg = d.iloc[i - 3:i + 1]
        names = seg.place.dropna()
        cz = pc[(pc.corridor == corridor).to_numpy()].iloc[seg.index]  # pc rows in P order, like d
        tot_c = {c: cz[f"car|{c}"].sum() + cz[f"truck|{c}"].sum() for c in CAUSES}
        main = [f"{c} {v:.1f}" for c, v in sorted(tot_c.items(), key=lambda kv: -kv[1])[:3] if v >= 0.05]
        hs.append(dict(corridor=corridor, km_from=seg.km_mid.min() - 0.25, km_to=seg.km_mid.max() + 0.25,
                       place=names.mode().iloc[0] if len(names) else "", car_excess_min=seg.car_excess_min.sum(),
                       truck_excess_min=seg.truck_excess_min.sum(), road_type=seg.road_type.mode().iloc[0],
                       main_causes="; ".join(main)))
        if sum(h["corridor"] == corridor for h in hs) == 10:
            break
hs = pd.DataFrame(hs).round(2)
hs.to_csv(os.path.join(C.OUTPUTS, "hotspots.csv"), index=False)
print(hs.to_string(index=False))

# Figure 4: minutes added by each cause, car and truck, outbound, with p5-p95 whiskers
# One x scale for all panels, so bar lengths compare across corridors
nrow = -(-len(C.CORRIDORS) // 2)
fig, axs = plt.subplots(nrow, 2, figsize=(13, 5.5 * nrow), facecolor=SURF, sharex=True,
                        gridspec_kw=dict(wspace=0.55, hspace=0.45))
axs = axs.ravel()
for ax in axs[len(C.CORRIDORS):]:
    ax.set_visible(False)
labels = CAUSES + ["rain (wet day)"]
for ax, (corridor, cfg) in zip(axs, C.CORRIDORS.items()):
    title = cfg["label"]
    c = causes[(causes.corridor == corridor) & (causes.direction == "outbound")]
    y = np.arange(len(labels))
    for j, (veh, col) in enumerate((("car", "#3574c4"), ("truck", "#0d2d57"))):
        cv = c[c.vehicle == veh].set_index("cause").reindex(labels)
        ax.barh(y + (j - 0.5) * 0.36, cv.minutes, height=0.34, color=col, label=veh, linewidth=0)
        ax.errorbar(cv.minutes, y + (j - 0.5) * 0.36, xerr=[cv.minutes - cv.p5, cv.p95 - cv.minutes],
                    fmt="none", ecolor=INK2, elinewidth=0.8, capsize=2)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9, color=INK)
    ax.invert_yaxis()
    ax.set_facecolor(SURF)
    for s_ in ("top", "right", "left"):
        ax.spines[s_].set_visible(False)
    ax.spines["bottom"].set_color("#e4e3df")
    ax.grid(axis="x", color="#e4e3df", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(colors=INK2, labelsize=8.5, length=0)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.tick_params(labelbottom=True)
    ax.set_xlabel("minutes added, leaving Kampala", fontsize=9, color=INK2)
    t = T0[(T0.corridor == corridor) & (T0.direction == "outbound")].set_index("vehicle")
    ax.set_title(f"{title}\ncar {t.loc['car', 'minutes']:.0f} min (open road {t.loc['car', 'open_road_minutes']:.0f}) · "
                 f"truck {t.loc['truck', 'minutes']:.0f} min (open road {t.loc['truck', 'open_road_minutes']:.0f})",
                 loc="left", fontsize=10, color=INK)
axs[0].legend(loc="lower right", frameon=False, fontsize=9, labelcolor=INK2)
H = fig.get_figheight()
fig.subplots_adjust(top=1 - 1.0 / H)
fig.text(0.02, 1 - 0.05 / H, "What each cause adds to the trip, in light traffic", fontsize=15, color=INK, va="top")
fig.text(0.02, 1 - 0.42 / H, "Central estimate; whiskers show the 5th–95th percentile over 1,000 draws of all assumptions. "
         "Rain is a wet-day scenario, not an annual average. Congestion is not modelled. All panels share one scale.", fontsize=9, color=INK2,
         va="top")
fig.savefig(os.path.join(C.FIGURES, "f04_minutes_by_cause.png"), dpi=150, facecolor=SURF, bbox_inches="tight")

# Figure 5: excess minutes per km along each corridor, hotspots labelled
fig, axs = plt.subplots(len(C.CORRIDORS), 1, figsize=(13, 3.4 * len(C.CORRIDORS)), facecolor=SURF,
                        gridspec_kw=dict(hspace=0.7))
for ax, (corridor, cfg) in zip(axs, C.CORRIDORS.items()):
    title = cfg["label"]
    d = pp[pp.corridor == corridor]
    km = np.floor(d.km_mid).astype(int)
    s = d.groupby(km)[["car_excess_min", "truck_excess_min"]].sum()
    ax.bar(s.index + 0.5, s.truck_excess_min, width=0.9, color="#0d2d57", linewidth=0, label="truck")
    ax.bar(s.index + 0.5, s.car_excess_min, width=0.5, color="#6aa2e0", linewidth=0, label="car")
    for h in hs[hs.corridor == corridor].head(5).itertuples():
        ax.annotate(h.place or f"km {h.km_from:.0f}", ((h.km_from + h.km_to) / 2, s.truck_excess_min.max() * 1.02),
                    ha="center", va="bottom", fontsize=7.5, color=INK2)
        ax.axvspan(h.km_from, h.km_to, color="#f6b596", alpha=0.35, linewidth=0, zorder=0)
    ax.set_facecolor(SURF)
    for s_ in ("top", "right", "left"):
        ax.spines[s_].set_visible(False)
    ax.spines["bottom"].set_color("#e4e3df")
    ax.grid(axis="y", color="#e4e3df", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(colors=INK2, labelsize=8, length=0)
    ax.set_xlim(0, d.km_mid.max())
    ax.set_ylim(0, s.truck_excess_min.max() * 1.25)
    ax.set_xlabel("km from Kampala", fontsize=8.5, color=INK2)
    ax.text(0, 1.06, f"{title}: minutes lost per km compared with open road, leaving Kampala "
            f"(shaded: the five worst 2 km stretches)", transform=ax.transAxes, fontsize=10, color=INK)
axs[0].legend(loc="upper right", frameon=False, fontsize=8.5, labelcolor=INK2, ncol=2)
fig.text(0.125, 0.965, "Where the time goes", fontsize=15, color=INK)
fig.savefig(os.path.join(C.FIGURES, "f05_hotspots.png"), dpi=150, facecolor=SURF, bbox_inches="tight")
print("wrote figures f04, f05")
