"""Fuel and CO2 from roadside friction: the stop-go cost that the time cost misses.

A loaded truck's fuel on each 500 m piece is worked out from physics, using the speed the
travel-time model (travel_model.py) gives that piece:
  - rolling and air resistance over the piece:  (Crr m g + 0.5 rho CdA v^2) x length
  - re-accelerating when the next stretch is faster: 0.5 m (v_next^2 - v^2), on a speed profile
    smoothed over 2 km (drivers anticipate; piece-to-piece noise is not a real speed change)
  - disturbances from the roadside and joining roads: the model's average speed loss there stands
    for repeated slow-downs (boda bodas, minibuses, pedestrians, turning traffic). Each piece gets
    up to `disturb_max` of them at full activity, each slowing to (1 - depth) of the free speed and
    back; at the average speed they would cost nothing, so leaving them out would make the
    roadside look fuel-saving, from lower air resistance alone
  - re-accelerating after every point event (hump, signal, crossing, police post, weighbridge), from the
    speed it slows to back up to the piece's speed; the energy lost in braking is not recovered
  - idling while stopped (signals, police posts, weighbridge queue), at an idle rate
Energy becomes diesel through a tank-to-wheel efficiency. Height gained on a piece adds m g dh and
height lost offsets that piece's resistance (any surplus is braked away). Climbing is nearly the
same with or without friction, so it mostly cancels in the friction litres but is kept in the totals,
which gives litres per 100 km to check against typical loaded-truck consumption (35-55 L/100 km).
The roadside slow-down term is the least certain; its range is set so trip totals stay in that
band, and it is reported separately.

Friction fuel = fuel as modelled - fuel on an open road at the truck's open-road speed (all
causes off). Switching one cause off at a time gives each cause's share, as in 10_travel_time.py.
1,000 Monte Carlo draws cover both the travel-time assumptions and the fuel ones below. A year's
total uses config.TRUCKS_PER_DAY and the same trip share as 17_costs.py; that is the weak input.

Writes outputs/fuel_co2.csv (per corridor), outputs/fuel_co2_by_cause.csv, figures/f16_fuel_co2.png.
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config as C
import travel_model as TM
from cartography import INK, INK2, SURF

RNG = np.random.default_rng(26)
N = 1000
G, LHV_MJ_L, CO2_KG_L = 9.81, 35.9, 2.68   # diesel lower heating value and CO2 per litre (tank-to-wheel)
# (central, low, high)
FUEL = {
    "mass_t": (40, 30, 48),            # loaded heavy goods vehicle, gross
    "crr": (0.006, 0.005, 0.008),      # rolling resistance, worn tyres on asphalt
    "cda_m2": (6.0, 5.0, 7.0),         # drag area
    "rho": (1.05, 1.0, 1.15),          # air density at 1,000-1,500 m altitude
    "eta": (0.36, 0.32, 0.40),         # tank-to-wheel efficiency
    "idle_l_h": (3.0, 2.0, 4.0),       # idling burn
    "hump_kmh": (15, 10, 20),          # speed over a hump
    "crossing_kmh": (30, 20, 40),      # speed through a pedestrian or level crossing
    "p_stop_signal": (0.5, 0.3, 0.7),  # share of trucks stopped at a signal
    "p_stop_police": (0.3, 0.1, 0.6),  # share of trucks stopped at a police post
    "wb_restarts": (3, 1, 6),          # stop-starts in a weighbridge queue
    "disturb_max": (0.5, 0.25, 1.0),   # roadside slow-downs per 500 m at full activity
    "disturb_depth": (0.3, 0.2, 0.4),  # each slows to (1 - depth) of the free speed
    "diesel_usd_l": (1.35, 1.20, 1.60),
    "trip_share": (0.7, 0.5, 0.9),     # as in 17_costs.py
}
POINT = ["signals and crossings", "speed humps (assumed)", "police posts", "weighbridge"]


def fuel_litres(p, f, direction, off=()):
    """Litres per piece for a loaded truck, and litres of that spent idling."""
    d = TM.P
    t_move = TM.piece_minutes(p, "truck", direction, off=tuple(off) + tuple(POINT), d=d)  # minutes, no point delays
    v = (d.length_km.to_numpy() * 1000) / (t_move * 60)                                  # m/s
    v_raw = v
    m = f["mass_t"] * 1000
    up, down = (d.climb_out_m, d.climb_in_m) if direction == "outbound" else (d.climb_in_m, d.climb_out_m)
    resist = (f["crr"] * m * G + 0.5 * f["rho"] * f["cda_m2"] * v_raw ** 2) * d.length_km.to_numpy() * 1000
    resist = np.clip(resist + m * G * (up - down).to_numpy(), 0, None)   # descents offset, surplus braked
    corr = d.corridor.to_numpy()
    v_free = (d.length_km.to_numpy() * 1000) / (60 * TM.piece_minutes(
        p, "truck", direction, off=tuple(off) + tuple(POINT) + ("roadside activity", "joining roads"), d=d))
    v = pd.Series(v).groupby(corr).transform(lambda s: s.rolling(4, center=True, min_periods=1).mean()).to_numpy()
    v_next = np.r_[v[1:], v[-1]]
    v_next[np.r_[corr[1:] != corr[:-1], True]] = v[np.r_[corr[1:] != corr[:-1], True]]
    if direction == "inbound":   # travelling towards Kampala, the next piece is the previous one
        v_next = np.r_[v[0], v[:-1]]
        v_next[np.r_[True, corr[1:] != corr[:-1]]] = v[np.r_[True, corr[1:] != corr[:-1]]]
    accel = 0.5 * m * np.clip(v_next ** 2 - v ** 2, 0, None)

    def reaccel(n, v_low):   # n events per piece, each slowing to v_low and back to the piece's speed
        return n * 0.5 * m * np.clip(v_raw ** 2 - (v_low / 3.6) ** 2, 0, None)
    ev, idle_s = np.zeros(len(d)), np.zeros(len(d))
    intensity = np.zeros(len(d))
    if "roadside activity" not in off:
        intensity += np.minimum(1, d.buildings_100m / p["side_friction_b0"])
    if "joining roads" not in off:
        intensity += np.minimum(1, (d.junctions_major + d.junctions_minor) / 10)
    n_dist = f["disturb_max"] * np.minimum(1, intensity) * d.length_km.to_numpy() / 0.5
    ev += n_dist * 0.5 * m * (v_free ** 2) * (1 - (1 - f["disturb_depth"]) ** 2)
    if "signals and crossings" not in off:
        ev += reaccel(d.signals * f["p_stop_signal"], 0) + reaccel(d.humps, f["hump_kmh"])
        ev += reaccel(d.ped_crossings + d.level_crossings, f["crossing_kmh"])
        idle_s += d.signals * p["signal_s"] + d.level_crossings * p["level_crossing_s"]
    if "speed humps (assumed)" not in off:
        ev += reaccel(np.where(d.road_type == "town", p["humps_per_town_piece"], 0), f["hump_kmh"])
    if "police posts" not in off:
        ev += reaccel(d.police_posts * f["p_stop_police"], 0)
        idle_s += d.police_posts * p["police_truck_s"]
    if "weighbridge" not in off:
        wb = np.minimum(d.weighbridges, 1)
        ev += reaccel(wb, 0) + wb * f["wb_restarts"] * 0.5 * m * (10 / 3.6) ** 2
        idle_s += wb * p["weighbridge_truck_s"]
    idle_l = np.asarray(idle_s, float) / 3600 * f["idle_l_h"]
    litres = (resist + accel + ev) / 1e6 / (f["eta"] * LHV_MJ_L) + idle_l
    return np.asarray(litres), idle_l


def draw_fuel(rng):
    return {k: rng.uniform(lo, hi) for k, (_, lo, hi) in FUEL.items()}


corr = TM.P.corridor.to_numpy()
order = list(C.CORRIDORS)
ALL_OFF = TM.CAUSES
rows, crows = [], []
for i in range(N):
    p = TM.CENTRAL if i == 0 else TM.draw(RNG)
    f = {k: v[0] for k, v in FUEL.items()} if i == 0 else draw_fuel(RNG)
    for direction in ("outbound", "inbound"):
        base, idle = fuel_litres(p, f, direction)
        openr, _ = fuel_litres(p, f, direction, off=ALL_OFF)
        by = {c: base - fuel_litres(p, f, direction, off=(c,))[0] for c in TM.CAUSES}
        for c in order:
            k = corr == c
            tpd = C.TRUCKS_PER_DAY[c][0] if i == 0 else RNG.uniform(*C.TRUCKS_PER_DAY[c][1:])
            extra = base[k].sum() - openr[k].sum()
            year = extra * tpd / 2 * f["trip_share"] * 365   # trucks a day both ways; one direction here
            rows.append(dict(draw=i, corridor=c, direction=direction, litres_trip=base[k].sum(),
                             l_per_100km=100 * base[k].sum() / TM.P.length_km[k].sum() if k.any() else np.nan,
                             litres_open=openr[k].sum(), friction_litres_trip=extra,
                             idle_litres_trip=idle[k].sum(), friction_co2_kg_trip=extra * CO2_KG_L,
                             friction_litres_year_m=year / 1e6, friction_co2_kt_year=year * CO2_KG_L / 1e6,
                             friction_fuel_usd_year_m=year * f["diesel_usd_l"] / 1e6))
            if direction == "outbound":
                crows += [dict(draw=i, corridor=c, cause=cz, litres_trip=by[cz][k].sum()) for cz in TM.CAUSES]
D, DC = pd.DataFrame(rows), pd.DataFrame(crows)

cols = ["litres_trip", "l_per_100km", "litres_open", "friction_litres_trip", "idle_litres_trip", "friction_co2_kg_trip"]
yearly = ["friction_litres_year_m", "friction_co2_kt_year", "friction_fuel_usd_year_m"]
out = []
for (c, dirn), g in D.groupby(["corridor", "direction"]):
    r = dict(corridor=c, direction=dirn)
    for col in cols:
        r[col] = round(g[g.draw == 0][col].iloc[0], 1)
        r[col + "_p5"], r[col + "_p95"] = np.round(np.percentile(g[col], [5, 95]), 1)
    r["friction_pct_of_trip_fuel"] = round(100 * r["friction_litres_trip"] / r["litres_trip"], 1)
    out.append(r)
out = pd.DataFrame(out)
# A year: both directions summed per draw
Y = D.groupby(["corridor", "draw"])[yearly].sum().reset_index()
for col in yearly:
    s = Y.groupby("corridor")[col]
    out = out.merge(pd.DataFrame({col: Y[Y.draw == 0].set_index("corridor")[col].round(2),
                                  col + "_p5": s.quantile(0.05).round(2), col + "_p95": s.quantile(0.95).round(2)})
                    .reset_index(), on="corridor")
out["o"] = out.corridor.map(order.index)
out = out.sort_values(["o", "direction"]).drop(columns="o")
out.to_csv(os.path.join(C.OUTPUTS, "fuel_co2.csv"), index=False)
cz = DC.groupby(["corridor", "cause"]).litres_trip.agg(
    litres=lambda s: s.iloc[0], p5=lambda s: s.quantile(0.05), p95=lambda s: s.quantile(0.95)).round(2).reset_index()
cz.to_csv(os.path.join(C.OUTPUTS, "fuel_co2_by_cause.csv"), index=False)
print(out[out.direction == "outbound"][["corridor", "litres_trip", "l_per_100km", "friction_litres_trip", "friction_litres_trip_p5",
                                        "friction_litres_trip_p95", "friction_pct_of_trip_fuel",
                                        "friction_co2_kt_year", "friction_fuel_usd_year_m"]].to_string(index=False))

# Figure: friction litres per outbound truck trip by cause, and CO2 a year
fig, (ax, ax2) = plt.subplots(1, 2, figsize=(14, 4.8), facecolor=SURF, gridspec_kw=dict(width_ratios=[1.6, 1], wspace=0.4))
COL = {"roadside activity": "#c4532d", "hills (trucks)": "#8a6b4e", "weighbridge": "#17252a",
       "speed humps (assumed)": "#d9a441", "police posts": "#4e7c8a", "joining roads": "#3a7d5c",
       "signals and crossings": "#9fb3b0", "town speed limit": "#e89a7a", "curves": "#c9c2b8"}
pv = cz.pivot(index="corridor", columns="cause", values="litres").reindex(order).clip(lower=0)
pv = pv[pv.sum().sort_values(ascending=False).index]
pv = pv.loc[:, pv.max() > 0.05]
y = np.arange(len(order))
left = np.zeros(len(order))
for c in pv.columns:
    ax.barh(y, pv[c], left=left, color=COL[c], height=0.6, label=c, linewidth=0)
    left += pv[c].to_numpy()
ob = out[out.direction == "outbound"].set_index("corridor").reindex(order)
for yi, r in zip(y, ob.itertuples()):
    ax.text(left[yi] + 0.3, yi, f"{r.friction_litres_trip:.1f} L  ({r.friction_pct_of_trip_fuel:.0f}% of trip fuel)",
            va="center", fontsize=8.5, color=INK)
ax.set_xlim(0, left.max() * 1.45)
ax.set_xlabel("extra litres of diesel per loaded truck trip, outbound", fontsize=9, color=INK2)
ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=3, frameon=False, fontsize=8, labelcolor=INK2)
yr = Y[Y.draw == 0].set_index("corridor").reindex(order)
lo, hi = Y.groupby("corridor").friction_co2_kt_year.quantile(0.05).reindex(order), \
    Y.groupby("corridor").friction_co2_kt_year.quantile(0.95).reindex(order)
ax2.barh(y, yr.friction_co2_kt_year, color="#4e7c8a", height=0.6, linewidth=0)
ax2.errorbar(yr.friction_co2_kt_year, y, xerr=[yr.friction_co2_kt_year - lo, hi - yr.friction_co2_kt_year],
             fmt="none", ecolor=INK2, elinewidth=0.9, capsize=3)
for yi, (c, r) in zip(y, yr.iterrows()):
    ax2.text(hi[c] + hi.max() * 0.03, yi, f"{r.friction_co2_kt_year:.1f} kt  (${r.friction_fuel_usd_year_m:.1f} M fuel)",
             va="center", fontsize=8.5, color=INK)
ax2.set_xlim(0, hi.max() * 1.6)
ax2.set_xlabel("kt CO2 a year from friction, heavy trucks, both directions", fontsize=9, color=INK2)
for a in (ax, ax2):
    a.set_yticks(y)
    a.set_yticklabels([f"{C.CORRIDORS[c]['short']} ({C.CORRIDORS[c]['ref']})" for c in order], fontsize=9.5, color=INK)
    a.invert_yaxis()
    a.set_facecolor(SURF)
    for s_ in ("top", "right", "left"):
        a.spines[s_].set_visible(False)
    a.spines["bottom"].set_color("#e4e3df")
    a.grid(axis="x", color="#e4e3df", linewidth=0.6)
    a.set_axisbelow(True)
    a.tick_params(colors=INK2, length=0)
fig.text(0.01, 1.10, "The fuel burnt slowing down and speeding up again", fontsize=15, color=INK)
fig.text(0.01, 1.05, "Loaded truck, light traffic, dry day, against an open road. Truck counts surveyed on the Malaba, "
         "Katuna and Bwera roads (NCTTCA 2025), assumed on the Elegu and Hoima roads; whiskers 5th–95th percentile "
         "of 1,000 draws.", fontsize=9, color=INK2)
fig.savefig(os.path.join(C.FIGURES, "f16_fuel_co2.png"), dpi=150, facecolor=SURF, bbox_inches="tight")
print("wrote outputs/fuel_co2*.csv, figures/f16_fuel_co2.png")
