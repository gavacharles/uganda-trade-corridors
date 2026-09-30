"""Which fixes would save the most time? Scenarios run through the travel-time model.

Each scenario changes the pieces (or the model's parameters) the way a fix would, and the
minutes saved are the corridor time before minus after, for a car and a loaded truck,
leaving Kampala. Every scenario runs over the same Monte Carlo draws as the base model
(travel_model.PARAMS) plus draws of the scenario's own assumptions, so savings carry
intervals. Traffic is light, as in the base model: fixes that relieve congestion (the
Kampala end) are not captured.

Scenarios:
  wim            Weigh-in-motion screening at weighbridges: only trucks flagged as possibly
                 overloaded are pulled in (WIM_STOPPED of trucks); the rest pass at speed.
  no_police      No stops at police posts on the road.
  bypass_2       Bypasses around the two towns per corridor where trucks lose the most time
                 (towns more than 15 km from Kampala and 5 km from the corridor's end, at least
                 1.5 km of "town" pieces, gaps up to 1 km bridged).
                 Through traffic runs at open-road speed over the town's length times a
                 detour factor, with a junction at each end.
  service_all    Service roads and access management through every roadside settlement:
                 roadside activity felt on the carriageway and joining roads both reduced.
  service_20km   The same, on only the 20 km of settlement with the most roadside activity
                 on each corridor.
  all            wim + no_police + bypass_2 + service_20km together.

Also each town bypassed on its own, ranked (outputs/scenario_bypass_towns.csv).

Writes outputs/scenarios.csv (minutes saved, p5-p95, km treated, minutes saved per km
treated), outputs/scenario_bypass_towns.csv, data/scenario_draws.parquet (per draw, for
17_costs.py), figures/f07_scenarios.png.
"""
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config as C
from cartography import INK, INK2, SURF
from travel_model import CAUSES, CENTRAL, P, draw, piece_minutes

N_DRAWS = 500
RNG = np.random.default_rng(7)
# Scenario assumptions: (central, low, high)
SPARAMS = {
    "wim_stopped": (0.2, 0.1, 0.4),       # share of trucks still pulled in to the static scale
    "detour": (1.2, 1.05, 1.4),           # bypass length / town length
    "bypass_junction_s": (30, 10, 60),    # delay at each end of a bypass
    "service_friction_cut": (0.5, 0.3, 0.7),   # share of roadside friction removed by service roads
    "service_access_cut": (0.5, 0.3, 0.7),     # share of joining roads closed or moved to the service road
}
MIN_TOWN_KM, KAMPALA_KM, BORDER_KM, SERVICE_KM = 1.5, 15, 5, 20
SCEN_LABEL = {"wim": "Weigh-in-motion screening", "no_police": "No stops at police posts",
              "bypass_2": "Bypass the 2 worst towns", "service_all": "Service roads, all settlements",
              "service_20km": "Service roads, worst 20 km", "all": "All four (with worst 20 km)"}
CORR = list(C.CORRIDORS)

# ---- Town clusters: runs of "town" pieces (gaps of one piece bridged), away from Kampala
pl = gpd.read_file(os.path.join(C.DATA, "osm_features.gpkg"), layer="points")
pl = pl[pl.place.isin(["city", "town"]) & pl.name.notna()].to_crs(C.UTM)
towns = []
for corridor, d in P.groupby("corridor", sort=False):
    t = (d.road_type == "town").to_numpy()
    t[1:-1] |= t[:-2] & t[2:]   # bridge gaps of one piece
    t[1:-2] |= t[:-3] & t[3:]   # and of two
    t[2:-1] |= t[:-3] & t[3:]
    run, start = 0, None
    for i, flag in enumerate(np.append(t, False)):
        if flag and start is None:
            start = i
        if not flag and start is not None:
            seg = d.iloc[start:i]
            if (seg.length_km.sum() >= MIN_TOWN_KM and seg.km_start.iloc[0] >= KAMPALA_KM
                    and seg.km_start.iloc[-1] <= d.km_start.max() - BORDER_KM):  # a border town cannot be bypassed
                c = gpd.GeoSeries(gpd.points_from_xy([seg.lon.mean()], [seg.lat.mean()]), crs=4326).to_crs(C.UTM).iloc[0]
                dist = pl.distance(c)
                name = pl.name[dist.idxmin()] if dist.min() < 5000 else (seg.place.dropna().mode().iloc[0]
                                                                         if seg.place.notna().any() else f"km {seg.km_start.iloc[0]:.0f}")
                towns.append(dict(corridor=corridor, town=name, km_from=seg.km_start.iloc[0],
                                  km_to=seg.km_start.iloc[-1] + 0.5, km=seg.length_km.sum(), idx=seg.index.to_numpy()))
            start = None
towns = pd.DataFrame(towns)
print(f"{len(towns)} towns eligible for a bypass")


FLOAT_COLS = ["buildings_100m", "junctions_major", "junctions_minor"]
P[FLOAT_COLS] = P[FLOAT_COLS].astype(float)


def bypassed(d, idx, p):
    """Pieces idx replaced by a bypass: open road, no roadside, no controls except weighbridges."""
    d = d.copy()
    d.loc[idx, "length_km"] = d.loc[idx, "length_km"] * p["detour"]
    for col in ["buildings_100m", "junctions_major", "junctions_minor", "signals", "ped_crossings",
                "level_crossings", "humps", "police_posts"]:
        d.loc[idx, col] = 0
    d.loc[idx, "curvature_deg_per_km"] = 0
    d.loc[idx, "road_type"] = "bypass"
    return d


def serviced(d, idx, p):
    d = d.copy()
    d.loc[idx, "buildings_100m"] = d.loc[idx, "buildings_100m"] * (1 - p["service_friction_cut"])
    for col in ["junctions_major", "junctions_minor"]:
        d.loc[idx, col] = d.loc[idx, col] * (1 - p["service_access_cut"])
    return d


settle = P.road_type == "roadside settlement"
worst_settle = np.concatenate([
    d[settle[d.index]].sort_values("buildings_100m", ascending=False).index[:int(SERVICE_KM / 0.5)].to_numpy()
    for _, d in P.groupby("corridor", sort=False)])
all_settle = P.index[settle].to_numpy()
# Towns to bypass: the two per corridor where trucks lose the most (central case)
truck0 = piece_minutes(CENTRAL, "truck", "outbound")
truck_open = piece_minutes(CENTRAL, "truck", "outbound", off=CAUSES)
towns["truck_excess_central"] = [(truck0[P.index.get_indexer(ix)] - truck_open[P.index.get_indexer(ix)]).sum()
                                 for ix in towns.idx]
top2 = towns.sort_values("truck_excess_central", ascending=False).groupby("corridor").head(2)
top2_idx = np.concatenate(top2.idx.to_list())
cmask = {c: (P.corridor == c).to_numpy() for c in CORR}


def corridor_sums(t):
    return {c: t[cmask[c]].sum() for c in CORR}


def scenario_times(p, veh):
    """Corridor minutes (outbound) for the base and every scenario, one parameter draw."""
    out = {"base": corridor_sums(piece_minutes(p, veh, "outbound")),
           "open": corridor_sums(piece_minutes(p, veh, "outbound", off=CAUSES))}
    pw = dict(p, weighbridge_truck_s=p["weighbridge_truck_s"] * p["wim_stopped"])
    out["wim"] = corridor_sums(piece_minutes(pw, veh, "outbound"))
    out["no_police"] = corridor_sums(piece_minutes(p, veh, "outbound", off=("police posts",)))
    junction = {c: 2 * p["bypass_junction_s"] / 60 * (top2.corridor == c).sum() for c in CORR}
    b = corridor_sums(piece_minutes(p, veh, "outbound", d=bypassed(P, top2_idx, p)))
    out["bypass_2"] = {c: b[c] + junction[c] for c in CORR}
    out["service_all"] = corridor_sums(piece_minutes(p, veh, "outbound", d=serviced(P, all_settle, p)))
    out["service_20km"] = corridor_sums(piece_minutes(p, veh, "outbound", d=serviced(P, worst_settle, p)))
    dall = serviced(bypassed(P, top2_idx, p), np.setdiff1d(worst_settle, top2_idx), p)
    a = corridor_sums(piece_minutes(pw, veh, "outbound", off=("police posts",), d=dall))
    out["all"] = {c: a[c] + junction[c] for c in CORR}
    rows = []
    for s, v in out.items():
        for c in CORR:
            rows.append(dict(corridor=c, vehicle=veh, scenario=s, minutes=v[c]))
    return rows


def with_scen(p, rng=None):
    q = {k: (v[0] if rng is None else rng.uniform(v[1], v[2])) for k, v in SPARAMS.items()}
    return dict(p, **q)


rows = []
for i in range(N_DRAWS + 1):
    p = with_scen(CENTRAL) if i == 0 else with_scen(draw(RNG), RNG)
    for veh in ("car", "truck"):
        rows += [dict(r, draw=i) for r in scenario_times(p, veh)]
    if i % 100 == 0:
        print("draw", i, flush=True)
S = pd.DataFrame(rows)
W = S.pivot_table(index=["corridor", "vehicle", "draw"], columns="scenario", values="minutes")
saved = W[list(SCEN_LABEL)].rsub(W["base"], axis=0)
saved["excess"] = W["base"] - W["open"]
saved["base"] = W["base"]
saved.reset_index().to_parquet(os.path.join(C.DATA, "scenario_draws.parquet"))

km_treated = {"wim": None, "no_police": None,
              "bypass_2": top2.groupby("corridor").km.sum(),
              "service_all": P[settle].groupby("corridor").length_km.sum(),
              "service_20km": P.loc[worst_settle].groupby("corridor").length_km.sum()}
out = []
for (corridor, veh), g in saved.groupby(level=[0, 1]):
    cen, mc = g.xs(0, level="draw"), g.drop(0, level="draw")
    for s in SCEN_LABEL:
        kt = km_treated.get(s)
        kt = None if kt is None else float(kt.get(corridor, 0))
        v = float(cen[s].iloc[0])
        out.append(dict(corridor=corridor, vehicle=veh, scenario=s, label=SCEN_LABEL[s],
                        minutes_saved=round(v, 1), p5=round(mc[s].quantile(0.05), 1), p95=round(mc[s].quantile(0.95), 1),
                        share_of_excess=round(v / float(cen["excess"].iloc[0]), 3),
                        km_treated=kt, min_saved_per_km=round(v / kt, 2) if kt else None))
out = pd.DataFrame(out)
out.to_csv(os.path.join(C.OUTPUTS, "scenarios.csv"), index=False)
print(out[out.vehicle == "truck"].to_string(index=False))

# ---- Each town bypassed on its own (central case plus interval)
bt = []
for t in towns.itertuples():
    for veh in ("car", "truck"):
        vals = []
        for i in range(101):
            p = with_scen(CENTRAL) if i == 0 else with_scen(draw(RNG), RNG)
            m = cmask[t.corridor]
            before = piece_minutes(p, veh, "outbound")[m].sum()
            after = piece_minutes(p, veh, "outbound", d=bypassed(P, t.idx, p))[m].sum() + 2 * p["bypass_junction_s"] / 60
            vals.append(before - after)
        bt.append(dict(corridor=t.corridor, town=t.town, km_from=t.km_from, km_to=t.km_to, town_km=t.km,
                       vehicle=veh, minutes_saved=round(vals[0], 2), p5=round(np.quantile(vals[1:], 0.05), 2),
                       p95=round(np.quantile(vals[1:], 0.95), 2)))
bt = pd.DataFrame(bt).sort_values(["vehicle", "minutes_saved"], ascending=[False, False])
bt.to_csv(os.path.join(C.OUTPUTS, "scenario_bypass_towns.csv"), index=False)
print(bt[bt.vehicle == "truck"].head(12).to_string(index=False))

# ---- Figure: minutes saved per truck trip by scenario and corridor, with intervals
fig, axs = plt.subplots(1, len(CORR), figsize=(15, 5.2), facecolor=SURF, sharex=True)
order = list(SCEN_LABEL)
col = {"wim": "#3a7d5c", "no_police": "#4e7c8a", "bypass_2": "#d9a441", "service_all": "#c4532d",
       "service_20km": "#e89a7a", "all": "#17252a"}
for ax, corridor in zip(axs, CORR):
    d = out[(out.corridor == corridor) & (out.vehicle == "truck")].set_index("scenario").reindex(order)
    y = np.arange(len(order))
    ax.barh(y, d.minutes_saved, color=[col[s] for s in order], height=0.62, linewidth=0)
    ax.errorbar(d.minutes_saved, y, xerr=[d.minutes_saved - d.p5, d.p95 - d.minutes_saved], fmt="none",
                ecolor=INK2, elinewidth=0.8, capsize=2)
    for yi, v in zip(y, d.minutes_saved):
        ax.text(v + 1, yi - 0.3, f"{v:.0f}", fontsize=8.5, color=INK, va="center")
    ax.set_yticks(y)
    ax.set_yticklabels([SCEN_LABEL[s] for s in order] if ax is axs[0] else [], fontsize=9, color=INK)
    ax.invert_yaxis()
    ax.set_title(f"{C.CORRIDORS[corridor]['short']} ({C.CORRIDORS[corridor]['ref']})", loc="left", fontsize=10,
                 color=INK)
    for s_ in ("top", "right", "left"):
        ax.spines[s_].set_visible(False)
    ax.grid(axis="x", color="#e4e3df", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(colors=INK2, labelsize=8.5, length=0)
    ax.set_xlabel("truck minutes saved, leaving Kampala", fontsize=8.5, color=INK2)
fig.text(0.01, 1.04, "Which fixes save the most time for a loaded truck", fontsize=15, color=INK)
fig.text(0.01, 0.975, "Central estimate; whiskers 5th–95th percentile over 500 draws of the model and scenario "
         "assumptions. Light traffic; congestion relief not captured. One scale for all panels.",
         fontsize=9, color=INK2)
fig.savefig(os.path.join(C.FIGURES, "f07_scenarios.png"), dpi=150, facecolor=SURF, bbox_inches="tight")
print("wrote outputs/scenarios.csv, outputs/scenario_bypass_towns.csv, figures/f07_scenarios.png")
