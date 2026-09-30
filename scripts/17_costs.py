"""What the delay costs in money: per trip, and per year for heavy trucks.

Minutes come from the travel-time model (per Monte Carlo draw, data/scenario_draws.parquet,
written by 16_scenarios.py): the minutes lost to all causes compared with open road, and the
minutes each fix would save. They are valued with a time cost per vehicle-hour and, for trucks,
scaled to a year with a truck count per corridor. Every money assumption has a range and is
drawn alongside the model's own draws, so costs carry intervals.

The truck counts are the weakest input. The one sourced anchor: 8.684 million tonnes of cargo
moved between Malaba and Kampala in 2017, about 4% of it by rail (Jinja-Kampala-Mpigi Corridor
Physical Development Plan, 2023, ch. 6). At about 25 t per loaded truck that is some 900 loaded
trucks a day plus empty returns. No public counts were found for the other roads, so their
ranges are wide and should be replaced with UNRA traffic counts. The time costs are also
assumptions, to be replaced with UNRA's HDM-4 (RED) road-user cost values. Car costs are given
per trip only: car volumes vary too much along each road to scale to a year.

Fuel and wear from stop-go driving are not counted, nor crash costs, nor congestion: the costs
are a floor, for light traffic on a dry day.

Writes outputs/costs.csv (per corridor), outputs/costs_by_cause.csv, outputs/costs_scenarios.csv,
figures/f08_costs.png.
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config as C
from cartography import INK, INK2, SURF

RNG = np.random.default_rng(11)
UGX_PER_USD = 3700
# (central, low, high); truck counts per corridor are in config.TRUCKS_PER_DAY
TRIP_SHARE = (0.7, 0.5, 0.9)       # average share of the corridor a truck travels
TRUCK_USD_H = (25, 15, 40)         # crew, depreciation, interest, overheads and cargo holding, per truck-hour
CAR_USD_H = (6, 3, 10)             # occupants' time (about two) and time-related car costs, per car-hour
SCEN = ["wim", "no_police", "bypass_2", "service_all", "service_20km", "all"]

D = pd.read_parquet(os.path.join(C.DATA, "scenario_draws.parquet"))
n = D.draw.max() + 1


def u(t, size):
    return np.r_[t[0], RNG.uniform(t[1], t[2], size - 1)]  # draw 0 is the central case


money = pd.DataFrame({"draw": np.arange(n), "truck_usd_h": u(TRUCK_USD_H, n), "car_usd_h": u(CAR_USD_H, n),
                      "trip_share": u(TRIP_SHARE, n)})
vol = pd.concat([pd.DataFrame({"corridor": c, "draw": np.arange(n), "trucks_per_day": u(t, n)})
                 for c, t in C.TRUCKS_PER_DAY.items()])
D = D.merge(money, on="draw").merge(vol, on=["corridor", "draw"])
D["usd_h"] = np.where(D.vehicle == "truck", D.truck_usd_h, D.car_usd_h)
D["trip_usd"] = D.excess / 60 * D.usd_h
D["year_usd_m"] = np.where(D.vehicle == "truck", D.trip_usd * D.trucks_per_day * 365 * D.trip_share / 1e6, np.nan)
for s in SCEN:
    D[f"{s}_year_usd_m"] = np.where(D.vehicle == "truck",
                                    D[s] / 60 * D.usd_h * D.trucks_per_day * 365 * D.trip_share / 1e6, np.nan)


def summ(g, col):
    c, mc = g[g.draw == 0][col].iloc[0], g[g.draw > 0][col]
    return c, mc.quantile(0.05), mc.quantile(0.95)


rows, srows = [], []
for (corridor, veh), g in D.groupby(["corridor", "vehicle"]):
    r = dict(corridor=corridor, vehicle=veh)
    for col, name in (("excess", "minutes_lost"), ("trip_usd", "cost_per_trip_usd"), ("year_usd_m", "cost_per_year_usd_m")):
        if veh == "car" and col == "year_usd_m":
            continue
        c, lo, hi = summ(g, col)
        r.update({name: round(c, 2), f"{name}_p5": round(lo, 2), f"{name}_p95": round(hi, 2)})
    r["cost_per_trip_ugx"] = round(r["cost_per_trip_usd"] * UGX_PER_USD, -2)
    rows.append(r)
    if veh == "truck":
        for s in SCEN:
            c, lo, hi = summ(g, f"{s}_year_usd_m")
            srows.append(dict(corridor=corridor, scenario=s, saving_per_year_usd_m=round(c, 2),
                              p5=round(lo, 2), p95=round(hi, 2)))
costs = pd.DataFrame(rows)
costs.to_csv(os.path.join(C.OUTPUTS, "costs.csv"), index=False)
sc = pd.DataFrame(srows)
sc.to_csv(os.path.join(C.OUTPUTS, "costs_scenarios.csv"), index=False)
print(costs.to_string(index=False))
print(sc.to_string(index=False))

# Split the central truck cost by cause, in proportion to the central minutes of each cause
cause = pd.read_csv(os.path.join(C.OUTPUTS, "travel_time_causes.csv"))
cause = cause[(cause.vehicle == "truck") & (cause.direction == "outbound") & (cause.cause != "rain (wet day)")]
cen = D[(D.draw == 0) & (D.vehicle == "truck")].set_index("corridor")
cause["cost_per_year_usd_m"] = [r.minutes / 60 * cen.loc[r.corridor, "usd_h"] * cen.loc[r.corridor, "trucks_per_day"] * 365
                                * cen.loc[r.corridor, "trip_share"] / 1e6 for r in cause.itertuples()]
cause[["corridor", "cause", "minutes", "cost_per_year_usd_m"]].round(2).to_csv(
    os.path.join(C.OUTPUTS, "costs_by_cause.csv"), index=False)

# Figure: annual cost of delay to heavy trucks, by cause, with the interval on the total
order = list(C.CORRIDORS)
cz = cause.pivot_table(index="corridor", columns="cause", values="cost_per_year_usd_m").reindex(order)
cz = cz[cz.sum().sort_values(ascending=False).index]
cz = cz.loc[:, cz.max() > 0.05]
tr = costs[costs.vehicle == "truck"].set_index("corridor").reindex(order)
# causes are measured one at a time and overlap; the remainder keeps the bar equal to the total
cz["overlap between causes"] = (tr.cost_per_year_usd_m - cz.sum(axis=1)).clip(lower=0)
COL = {"roadside activity": "#c4532d", "hills (trucks)": "#8a6b4e", "weighbridge": "#17252a",
       "speed humps (assumed)": "#d9a441", "police posts": "#4e7c8a", "joining roads": "#3a7d5c",
       "signals and crossings": "#9fb3b0", "town speed limit": "#e89a7a", "curves": "#c9c2b8",
       "overlap between causes": "#e4e3df"}
pal = [COL[c] for c in cz.columns]
fig, ax = plt.subplots(figsize=(11, 4.8), facecolor=SURF)
left = np.zeros(len(order))
y = np.arange(len(order))
for col_, c in zip(cz.columns, pal):
    ax.barh(y, cz[col_], left=left, color=c, height=0.6, label=col_, linewidth=0)
    left += cz[col_].fillna(0).to_numpy()
ax.errorbar(tr.cost_per_year_usd_m, y, xerr=[tr.cost_per_year_usd_m - tr.cost_per_year_usd_m_p5,
                                               tr.cost_per_year_usd_m_p95 - tr.cost_per_year_usd_m],
            fmt="none", ecolor=INK2, elinewidth=0.9, capsize=3)
for yi, r in zip(y, tr.itertuples()):
    ax.text(r.cost_per_year_usd_m_p95 + 0.4, yi, f"${r.cost_per_year_usd_m:.1f} M  "
            f"({r.cost_per_year_usd_m_p5:.1f}–{r.cost_per_year_usd_m_p95:.1f})", va="center", fontsize=9, color=INK)
ax.set_yticks(y)
ax.set_yticklabels([f"{C.CORRIDORS[c]['short']} ({C.CORRIDORS[c]['ref']})" for c in order], fontsize=10, color=INK)
ax.invert_yaxis()
for s_ in ("top", "right", "left"):
    ax.spines[s_].set_visible(False)
ax.grid(axis="x", color="#e4e3df", linewidth=0.6)
ax.set_axisbelow(True)
ax.tick_params(colors=INK2, labelsize=9, length=0)
ax.set_xlabel("US$ million a year, heavy trucks only", fontsize=9, color=INK2)
ax.set_xlim(0, tr.cost_per_year_usd_m_p95.max() * 1.35)
ax.legend(loc="lower right", frameon=False, fontsize=8.5, ncol=2, labelcolor=INK2)
fig.text(0.01, 1.03, "What delay costs truck operators each year", fontsize=15, color=INK)
fig.text(0.01, 0.975, "Time lost to all measured causes vs open road, light traffic, dry day. Truck counts and hourly "
         "costs are assumptions with wide ranges; whiskers 5th–95th percentile.", fontsize=9, color=INK2)
fig.savefig(os.path.join(C.FIGURES, "f08_costs.png"), dpi=150, facecolor=SURF, bbox_inches="tight")
print("wrote outputs/costs*.csv, figures/f08_costs.png")
