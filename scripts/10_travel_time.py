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

N_DRAWS = 1000
RNG = np.random.default_rng(42)

# name: (central, low, high). Speeds km/h, delays seconds.
PARAMS = {
    "car_open_single": (90, 80, 100),      # open road, single carriageway
    "car_open_dual": (100, 90, 110),
    "truck_open": (70, 60, 80),            # loaded heavy goods vehicle
    "town_limit": (50, 40, 60),            # urban speed limit applied in "town" pieces
    "side_friction_max": (0.35, 0.20, 0.50),   # largest speed loss from roadside activity
    "side_friction_b0": (300, 200, 400),   # buildings within 100 m at which that loss is reached
    "access_max": (0.15, 0.05, 0.25),      # speed loss at 10+ joining roads per piece
    "truck_grade_k": (0.25, 0.15, 0.35),   # truck speed = open / (1 + k * (grade - 1)) uphill
    "curve_threshold": (150, 120, 200),    # deg/km above which a curve cap applies
    "curve_cap_car": (60, 50, 70),
    "curve_cap_truck": (50, 40, 60),
    "signal_s": (30, 15, 45),
    "ped_crossing_s": (5, 2, 10),
    "level_crossing_s": (15, 5, 30),
    "hump_s": (8, 5, 12),
    "humps_per_town_piece": (1.0, 0.0, 2.0),   # OSM under-records humps; assumed per town piece
    "police_car_s": (10, 0, 30),           # OSM police posts on the road: possible checks
    "police_truck_s": (60, 0, 300),
    "weighbridge_truck_s": (600, 300, 1800),   # queue and weighing; cars pass
    "wet_factor": (0.90, 0.85, 0.95),      # speed multiplier on a wet day (>= 10 mm)
}
CAUSES = ["town speed limit", "roadside activity", "joining roads", "signals and crossings",
          "speed humps (assumed)", "police posts", "weighbridge", "hills (trucks)", "curves"]


P = pd.read_csv(os.path.join(C.OUTPUTS, "pieces_typed.csv")).sort_values(["corridor", "piece"])
P["length_km"] = P.groupby("corridor").km_start.shift(-1).sub(P.km_start).fillna(0.5).clip(upper=0.5)
P["place"] = P.place.where(~P.place.fillna("").str.contains("/"))  # drop malformed OSM names


def piece_minutes(p, vehicle, direction, off=(), wet=False):
    """Minutes to cross each piece. `off` lists causes switched off."""
    with np.errstate(all="ignore"):
        return _piece_minutes(p, vehicle, direction, off, wet)


def _piece_minutes(p, vehicle, direction, off, wet):
    d = P
    car = vehicle == "car"
    v = np.where(d.dual, p["car_open_dual"], p["car_open_single"]) if car else np.full(len(d), p["truck_open"], float)
    if "roadside activity" not in off:
        v = v * (1 - p["side_friction_max"] * np.minimum(1, d.buildings_100m / p["side_friction_b0"]))
    if "joining roads" not in off:
        v = v * (1 - p["access_max"] * np.minimum(1, (d.junctions_major + d.junctions_minor) / 10))
    if "town speed limit" not in off:
        v = np.where(d.road_type == "town", np.minimum(v, p["town_limit"]), v)
    if "curves" not in off:
        cap = p["curve_cap_car"] if car else p["curve_cap_truck"]
        v = np.where(d.curvature_deg_per_km > p["curve_threshold"], np.minimum(v, cap), v)
    if not car and "hills (trucks)" not in off:
        g = d.grade_pct.to_numpy() * (1 if direction == "outbound" else -1)
        v = np.where(g > 1, np.minimum(v, p["truck_open"] / (1 + p["truck_grade_k"] * (g - 1))), v)
    if wet:
        v = v * p["wet_factor"]
    t = d.length_km / v * 60
    if "signals and crossings" not in off:
        t = t + (d.signals * p["signal_s"] + d.ped_crossings * p["ped_crossing_s"]
                 + d.level_crossings * p["level_crossing_s"] + d.humps * p["hump_s"]) / 60
    if "speed humps (assumed)" not in off:
        humps = np.where(d.road_type == "town", p["humps_per_town_piece"], 0)
        t = t + humps * p["hump_s"] * (1 if car else 1.5) / 60
    if "police posts" not in off:
        t = t + d.police_posts * (p["police_car_s"] if car else p["police_truck_s"]) / 60
    if "weighbridge" not in off and not car:  # weighbridges found by name in OSM (05_osm_features.py)
        t = t + np.minimum(d.weighbridges, 1) * p["weighbridge_truck_s"] / 60
    return np.asarray(t)


def totals(p):
    """Corridor minutes for every vehicle/direction, all causes on, each cause off, and wet."""
    rows = []
    for veh in ("car", "truck"):
        for direction in ("outbound", "inbound"):
            base = piece_minutes(p, veh, direction)
            ideal = piece_minutes(p, veh, direction, off=CAUSES)
            wet = piece_minutes(p, veh, direction, wet=True)
            for corridor in P.corridor.unique():
                m = (P.corridor == corridor).to_numpy()
                r = dict(corridor=corridor, vehicle=veh, direction=direction,
                         minutes=base[m].sum(), open_road_minutes=ideal[m].sum(),
                         wet_extra=wet[m].sum() - base[m].sum())
                for c in CAUSES:
                    r[c] = base[m].sum() - piece_minutes(p, veh, direction, off=(c,))[m].sum()
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

VALID = {  # (label, low minutes, high minutes, kind, compare up to (lon, lat) or None for the whole corridor)
    ("kampala_malaba", "car"): [("Rome2rio routing estimate, Kampala–Njeru", 66, 66, "estimate", (33.17, 0.44)),
                                ("Reported typical trip Kampala–Jinja, press and project sources", 120, 180,
                                 "observed", (33.204, 0.439))],
    ("kampala_elegu", "car"): [("Rome2rio routing estimate, Kampala–Gulu", 286, 286, "estimate", (32.299, 2.774)),
                               ("Scheduled buses Kampala–Gulu incl. stops (Bookaway, Friends Coach)", 300, 495,
                                "observed", (32.299, 2.774))],
    ("kampala_katuna", "car"): [("Rome2rio routing estimate, Kampala–Kabale", 345, 345, "estimate", (29.9856, -1.2486)),
                                ("Scheduled bus, Kampala–Kabale (Rome2rio)", 480, 480, "observed", (29.9856, -1.2486))],
    ("kampala_hoima", "car"): [("Rome2rio routing estimate", 172, 172, "estimate", None),
                               ("Scheduled bus (Rome2rio)", 206, 206, "observed", None)],
}
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
fig, axs = plt.subplots(2, 2, figsize=(13, 11), facecolor=SURF, gridspec_kw=dict(wspace=0.55, hspace=0.45))
axs = axs.ravel()
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
    ax.set_xlabel("minutes added, leaving Kampala", fontsize=9, color=INK2)
    t = T0[(T0.corridor == corridor) & (T0.direction == "outbound")].set_index("vehicle")
    ax.set_title(f"{title}\ncar {t.loc['car', 'minutes']:.0f} min (open road {t.loc['car', 'open_road_minutes']:.0f}) · "
                 f"truck {t.loc['truck', 'minutes']:.0f} min (open road {t.loc['truck', 'open_road_minutes']:.0f})",
                 loc="left", fontsize=10, color=INK)
axs[0].legend(loc="lower right", frameon=False, fontsize=9, labelcolor=INK2)
fig.text(0.02, 1.02, "What each cause adds to the trip, in light traffic", fontsize=15, color=INK)
fig.text(0.02, 0.965, "Central estimate; whiskers show the 5th–95th percentile over 1,000 draws of all assumptions. "
         "Rain is a wet-day scenario, not an annual average. Congestion is not modelled.", fontsize=9, color=INK2)
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
