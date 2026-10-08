"""Designing a network rather than a line: two networks grown corridor by corridor.

    python kampala-transit/scripts/k09_networks.py      (after k01, k02, k07)

From the candidate corridors (k02), a BRT network is grown greedily at the central congestion level
(roads 2x slower than k01 assumed), adding at each step the corridor that most improves:
  efficiency   person-minutes saved per km of busway added
  equity       access gained (jobs reachable in 45 min) by residents of dense small-plot settlement
               per km added
up to MAX_LINES lines. Each finished network is then run at all four congestion levels, as BRT and as
light rail, and the per-zone access gains are kept for the equity maps (k10, k11).

Writes outputs/network_steps.csv, outputs/networks.csv, outputs/network_zone_access.parquet.
"""
import os, sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tnet  # noqa: E402

MAX_LINES = 6
OUT = os.path.join(tnet.KT, "outputs")
t0 = time.time()
cands = [r for r in tnet.CAND.route if len(tnet.route_edges(r)) and tnet.E.km.to_numpy()[tnet.route_edges(r)].sum() >= 4]
KM = {r: tnet.E.km.to_numpy()[tnet.route_edges(r)].sum() for r in cands}
NAME = dict(zip(tnet.CAND.route, tnet.CAND["name"]))
print(len(cands), "candidate corridors:", ", ".join(NAME[r] for r in cands), flush=True)
base = tnet.baseline(tnet.ROAD[tnet.CENTRAL])
DENSE = tnet.GROUPS["dense small-plot"].to_numpy()


def score(res, how):
    if how == "efficiency":
        return res["person_min_saved"]
    return (DENSE * (res["_A"] - base["A"])).sum()


steps, nets = [], {}
for how in ("efficiency", "equity"):
    chosen, prev = [], None
    prev_val = 0.0
    for k in range(MAX_LINES):
        best = None
        for r in cands:
            if r in chosen:
                continue
            T = tnet.times(tnet.ROAD[tnet.CENTRAL], [tnet.line(x) for x in chosen + [r]])
            res = tnet.evaluate(T, base)
            gain = (score(res, how) - prev_val) / KM[r]
            if best is None or gain > best[0]:
                best = (gain, r, res)
        gain, r, res = best
        chosen.append(r)
        prev_val = score(res, how)
        steps.append(dict(network=how, step=k + 1, added=NAME[r], route=r, km_added=round(KM[r], 1),
                          km_total=round(sum(KM[x] for x in chosen), 1), marginal_per_km=gain,
                          **{k_: v for k_, v in res.items() if not k_.startswith("_")}))
        print(f"[{time.time() - t0:5.0f} s] {how} step {k + 1}: + {NAME[r]}  saving {res['saving_pct']:.2f}%  "
              f"dense-plot access +{res.get('gain_dense small-plot', 0):.2f}%", flush=True)
    nets[how] = list(chosen)
pd.DataFrame(steps).to_csv(os.path.join(OUT, "network_steps.csv"), index=False)

# the finished networks at every congestion level, BRT and light rail
rows, zone_A = [], {}
for how, routes in nets.items():
    km = sum(KM[x] for x in routes)
    for case, rf in tnet.ROAD.items():
        b = tnet.baseline(rf)
        for mode in tnet.MODES:
            res = tnet.evaluate(tnet.times(rf, [tnet.line(x, mode) for x in routes]), b, km=km)
            if case == tnet.CENTRAL:
                zone_A[f"{how}_{mode}"] = res["_A"] - b["A"]
                zone_A["base_A"] = b["A"]
            rows.append(dict(network=how, routes=" + ".join(NAME[x] for x in routes), mode=mode, case=case,
                             **{k_: v for k_, v in res.items() if not k_.startswith("_")}))
    print(f"[{time.time() - t0:5.0f} s] evaluated {how} network", flush=True)
R = pd.DataFrame(rows)
R.to_csv(os.path.join(OUT, "networks.csv"), index=False)
ZA = tnet.OZ[["lon", "lat", "pop", "cbd_km"]].copy()
for k, v in zone_A.items():
    ZA[k] = v
ZA.to_parquet(os.path.join(OUT, "network_zone_access.parquet"))
pd.set_option("display.width", 220)
print(R[R.case == tnet.CENTRAL][["network", "mode", "km", "saving_pct", "access_gain_pct", "access_gain_low40_pct",
                                 "gain_dense small-plot", "gini_before", "gini_after"]].round(3).to_string())
