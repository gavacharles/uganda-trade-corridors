"""The transit gap: observed truck transit times against the model's driving time.

The travel-time model (10_travel_time.py) gives the minutes a loaded truck spends moving along
each corridor, open road plus the friction of the roadside and controls, in light traffic.
The Northern Corridor Transport Observatory publishes what trucks actually take between Kampala
and the borders, from GPS trackers and the regional electronic cargo tracking system (RECTS),
for 2025 and January-June 2026 (inputs/nc_observatory_transit.csv). The difference between the
two is time spent stopped: rest and meals, border queues, customs, company and security checks,
breakdowns. The same reports give the mix of driver stops and their median duration, and
the crossing time at the Malaba and Busia borders (inputs/nc_observatory_stops.csv).

Three uses:
  1. The gap per corridor and direction: observed hours = model driving (open road + friction)
     + stopped time. Road friction is then a share of the observed trip, not of driving alone.
  2. A check of the model's weighbridge stop (travel_model.py, 600 s, 300-1800 s) against the
     Observatory's median weighbridge stop.
  3. The border crossing at Malaba against the minutes lost to friction inside Uganda.

The RECTS and GPS samples differ (RECTS follows transit cargo under bond, GPS a fleet sample),
so both are kept. Kampala-Hoima is not reported. The stop mix is a share of stops, not of trips,
so "share of stopped time" is approximated as share of stops x median duration, renormalised.

Writes outputs/transit_gap.csv, outputs/transit_stop_mix.csv, figures/f14_transit_gap.png.
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config as C
from cartography import INK, INK2, SURF
from travel_model import PARAMS

INPUTS = os.path.join(C.ROOT, "inputs")
obs = pd.read_csv(os.path.join(INPUTS, "nc_observatory_transit.csv"))
stops = pd.read_csv(os.path.join(INPUTS, "nc_observatory_stops.csv"))
tot = pd.read_csv(os.path.join(C.OUTPUTS, "travel_time_totals.csv"))
tot = tot[tot.vehicle == "truck"].set_index(["corridor", "direction"])

# 1. The gap
rows = []
for r in obs.itertuples():
    if (r.corridor, r.direction) not in tot.index:
        continue
    m = tot.loc[(r.corridor, r.direction)]
    drive_h, open_h = m.minutes / 60, m.open_road_minutes / 60
    rows.append(dict(corridor=r.corridor, origin=r.origin, destination=r.destination, direction=r.direction,
                     method=r.method, period=r.period, observed_h=r.hours, model_open_road_h=round(open_h, 1),
                     model_friction_h=round(drive_h - open_h, 1), model_driving_h=round(drive_h, 1),
                     stopped_h=round(r.hours - drive_h, 1), driving_share_pct=round(100 * drive_h / r.hours),
                     friction_share_pct=round(100 * (drive_h - open_h) / r.hours, 1), source=r.source))
gap = pd.DataFrame(rows)
gap.to_csv(os.path.join(C.OUTPUTS, "transit_gap.csv"), index=False)
print(gap[["corridor", "direction", "method", "period", "observed_h", "model_driving_h", "stopped_h",
           "friction_share_pct"]].to_string(index=False))

# 2. Stop mix, and the weighbridge check
mix = stops[stops.kind == "stop"].copy()
mix["stopped_time_share_pct"] = (100 * mix.share_of_stops_pct * mix.median_hours
                                 / (mix.share_of_stops_pct * mix.median_hours).sum()).round(1)
mix.to_csv(os.path.join(C.OUTPUTS, "transit_stop_mix.csv"), index=False)
wb_obs = float(mix.loc[mix.item == "Weighbridge", "median_hours"].iloc[0]) * 60
wb_c, wb_lo, wb_hi = (s / 60 for s in PARAMS["weighbridge_truck_s"])
print(f"weighbridge stop: Observatory median {wb_obs:.0f} min; model {wb_c:.0f} min ({wb_lo:.0f}-{wb_hi:.0f})")

# 3. Malaba border against friction inside Uganda
border = stops[stops.kind == "border"].set_index("item").minutes
fr = gap[(gap.corridor == "kampala_malaba") & (gap.direction == "outbound")].model_friction_h.iloc[0] * 60
print(f"Malaba border crossing {border['Malaba']:.0f} min, Busia {border['Busia']:.0f} min; "
      f"friction on the Kampala-Malaba road {fr:.0f} min")

# Figure: latest RECTS record per corridor and direction, plus 2025 GPS where published
sel = gap.sort_values("period").groupby(["corridor", "direction", "method"]).tail(1)
order = [c for c in C.CORRIDORS if c in set(sel.corridor)]
sel = sel.assign(o=sel.corridor.map(order.index), d=sel.direction != "outbound").sort_values(["o", "d", "method"])
labels = [f"{C.CORRIDORS[r.corridor]['short']} {'out' if r.direction == 'outbound' else 'in'} · "
          f"{r.method} {r.period}" for r in sel.itertuples()]
fig, (ax, ax2) = plt.subplots(1, 2, figsize=(14, 0.42 * len(sel) + 2.2), facecolor=SURF,
                              gridspec_kw=dict(width_ratios=[2.2, 1], wspace=0.55))
y = np.arange(len(sel))
parts = [("model_open_road_h", "driving, open road", "#9fb3b0"), ("model_friction_h", "road friction (model)", "#c4532d"),
         ("stopped_h", "stopped (observed − model)", "#e4e3df")]
left = np.zeros(len(sel))
for col, lab, c in parts:
    v = sel[col].clip(lower=0).to_numpy()
    ax.barh(y, v, left=left, color=c, height=0.62, label=lab, linewidth=0)
    left += v
for yi, r in zip(y, sel.itertuples()):
    ax.text(r.observed_h + 0.8, yi, f"{r.observed_h:.0f} h  (friction {r.friction_share_pct:.0f}%)",
            va="center", fontsize=8.5, color=INK)
ax.set_yticks(y)
ax.set_yticklabels(labels, fontsize=9, color=INK)
ax.invert_yaxis()
ax.set_xlabel("hours, Kampala ↔ border", fontsize=9, color=INK2)
ax.set_xlim(0, sel.observed_h.max() * 1.3)
ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=3, frameon=False, fontsize=8.5, labelcolor=INK2)

m2 = mix.sort_values("stopped_time_share_pct")
ax2.barh(m2.item, m2.stopped_time_share_pct, color="#4e7c8a", height=0.62, linewidth=0)
for yi, r in enumerate(m2.itertuples()):
    ax2.text(r.stopped_time_share_pct + 0.8, yi, f"{r.stopped_time_share_pct:.0f}%  (median {r.median_hours:g} h)",
             va="center", fontsize=8, color=INK2)
ax2.set_xlim(0, m2.stopped_time_share_pct.max() * 1.7)
ax2.tick_params(axis="y", labelsize=8.5, labelcolor=INK)
ax2.set_xlabel("approx. share of stopped time, %", fontsize=9, color=INK2)
ax2.set_title("Why trucks stop (Northern Corridor, 2025)", fontsize=10, color=INK, loc="left")
for a in (ax, ax2):
    a.set_facecolor(SURF)
    for s_ in ("top", "right", "left"):
        a.spines[s_].set_visible(False)
    a.spines["bottom"].set_color("#e4e3df")
    a.grid(axis="x", color="#e4e3df", linewidth=0.6)
    a.set_axisbelow(True)
    a.tick_params(colors=INK2, length=0)
fig.text(0.01, 1.04, "Trucks spend most of the trip standing still", fontsize=15, color=INK)
fig.text(0.01, 0.995, "Observed truck transit (NCTTCA Transport Observatory, GPS and RECTS) against the model's "
         "driving time for a loaded truck in light traffic.", fontsize=9, color=INK2)
fig.savefig(os.path.join(C.FIGURES, "f14_transit_gap.png"), dpi=150, facecolor=SURF, bbox_inches="tight")
print("wrote outputs/transit_gap.csv, outputs/transit_stop_mix.csv, figures/f14_transit_gap.png")
