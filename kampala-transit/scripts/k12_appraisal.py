"""Costs and benefits of the lines (k05) and networks (k09), with every uncertain input drawn from a range.

    python kampala-transit/scripts/k12_appraisal.py

Benefits: travel time saved only (operating costs, emissions and safety are left out, so the benefits
are conservative). The model's person-minutes saved per day (one modelled trip per resident) are
scaled by TRIP_RATE public-transport trips per resident per day, valued at VOT US$ per hour, for
DAYS a year, growing at GROWTH a year.
Costs: capital per km (BRT, light rail), resettlement per building inside the 24 m corridor (k04),
operation and maintenance as a share of capital a year.
Appraisal: 12% discount rate (Uganda Ministry of Finance guidance for public projects), 4 years of
construction then 25 years of operation, 2,000 Monte Carlo draws per case.

Ranges (low, central, high) and their sources:
  BRT capital           5, 10, 20  US$ M/km   ITDP BRT Planning Guide (2017) African range; Dar es
                                              Salaam DART phase 1 about US$ 6-7 M/km; Lagos BRT-Lite
                                              about US$ 2 M/km (lower bound, no median busway)
  Light rail capital    15, 35, 60 US$ M/km   Addis Ababa LRT about US$ 14 M/km (2015); at-grade LRT
                                              elsewhere US$ 30-60 M/km (Flyvbjerg et al. 2008; ITDP)
  Resettlement          10, 30, 60 US$ k per building (compensation and relocation; KCCA and UNRA
                                              resettlement action plans report US$ 10-60 k per structure)
  O&M                   3, 5, 8 % of capital a year (BRT); 3, 4, 6 % (light rail)
  Trips                 0.5, 0.8, 1.2 public-transport trips per resident per day (Kampala travel
                                              surveys: about 1.5-2 trips a day, half to two thirds by
                                              minibus taxi or boda boda; JICA 2010, KCCA 2021)
  Value of time         0.4, 0.8, 1.5 US$ per hour (GDP per head about US$ 1,000; value of time
                                              about 30-60% of the wage rate)
  Growth                2, 4, 6 % a year (population and trips)
Writes outputs/appraisal.csv and figures/k12_appraisal.png.
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
KT = os.path.abspath(os.path.join(HERE, ".."))
RNG = np.random.default_rng(7)
ND, RATE, BUILD, LIFE, DAYS = 2000, 0.12, 4, 25, 300
RANGES = {"BRT_cap": (5, 10, 20), "LRT_cap": (15, 35, 60), "resettle_k": (10, 30, 60), "om_BRT": (0.03, 0.05, 0.08),
          "om_LRT": (0.03, 0.04, 0.06), "trips": (0.5, 0.8, 1.2), "vot": (0.4, 0.8, 1.5), "growth": (0.02, 0.04, 0.06)}
INK, INK2, SURF, GRID = "#1d2321", "#5d6764", "#fcfcfb", "#e6e4de"
CASES = ["roads as assumed", "roads 1.5x slower", "roads 2x slower", "roads 3x slower"]


def draws():
    # triangular on (low, central, high); the first draw is the central case
    d = {k: np.r_[c, RNG.triangular(lo, c, hi, ND - 1)] for k, (lo, c, hi) in RANGES.items()}
    return pd.DataFrame(d)


DR = draws()
yrs = np.arange(BUILD + LIFE)
disc = 1 / (1 + RATE) ** yrs
op = yrs >= BUILD


def appraise(min_saved_day, km, buildings, mode):
    """Present values (US$ M) for each draw."""
    cap = (DR.BRT_cap if mode == "BRT" else DR.LRT_cap).to_numpy() * km
    res = DR.resettle_k.to_numpy() * buildings / 1000
    om = (DR.om_BRT if mode == "BRT" else DR.om_LRT).to_numpy() * cap
    capex_pv = (cap + res) * disc[:BUILD].sum() / BUILD
    om_pv = om * disc[op].sum()
    yearly = min_saved_day / 60 * DR.trips.to_numpy() * DR.vot.to_numpy() * DAYS / 1e6
    grow = (1 + DR.growth.to_numpy()[:, None]) ** yrs[None, :]
    ben_pv = yearly * (grow[:, op] * disc[op][None, :]).sum(axis=1)
    cost = capex_pv + om_pv
    return dict(benefit=ben_pv, cost=cost, capex=cap + res, bcr=ben_pv / cost, npv=ben_pv - cost)


CL = pd.read_csv(os.path.join(KT, "outputs", "clearance.csv")).set_index("route")
SC = pd.read_csv(os.path.join(KT, "outputs", "scenarios.csv"))
NW = pd.read_csv(os.path.join(KT, "outputs", "networks.csv"))
ST = pd.read_csv(os.path.join(KT, "outputs", "network_steps.csv"))
rows = []
for _, r in SC[~SC["mode"].str.contains("network")].iterrows():
    if r.route not in CL.index:
        continue
    a = appraise(r.person_min_saved, r.km, CL.loc[r.route, "demolish_tight"], "BRT" if r["mode"] == "BRT" else "LRT")
    rows.append(dict(kind="line", name=r["name"], mode=r["mode"], case=r.case, km=r.km,
                     buildings=CL.loc[r.route, "demolish_tight"], **{f"{k}_{s}": f(v) for k, v in a.items()
                     for s, f in (("central", lambda x: x[0]), ("p5", lambda x: np.percentile(x, 5)),
                                  ("p95", lambda x: np.percentile(x, 95)))}, p_bcr_gt1=(a["bcr"] > 1).mean()))
for net in ("efficiency", "equity"):
    routes = list(ST[ST.network == net].route)
    bld = sum(CL.loc[x, "demolish_tight"] for x in routes if x in CL.index)
    for _, r in NW[NW.network == net].iterrows():
        a = appraise(r.person_min_saved, r.km, bld, "BRT" if r["mode"] == "BRT" else "LRT")
        rows.append(dict(kind="network", name=f"{net} network", mode=r["mode"], case=r.case, km=r.km, buildings=bld,
                         **{f"{k}_{s}": f(v) for k, v in a.items()
                            for s, f in (("central", lambda x: x[0]), ("p5", lambda x: np.percentile(x, 5)),
                                         ("p95", lambda x: np.percentile(x, 95)))}, p_bcr_gt1=(a["bcr"] > 1).mean()))
A = pd.DataFrame(rows)
A.to_csv(os.path.join(KT, "outputs", "appraisal.csv"), index=False)
pd.set_option("display.width", 230)
show = A[(A.kind == "network") | A.name.isin(["Entebbe Road (A3)", "Nansana - Busunju Road (A9)", "Jinja Road (A1)",
                                              "Kampala - Masaka Road (A2)"])]
print(show[["name", "mode", "case", "km", "buildings", "capex_central", "bcr_central", "bcr_p5", "bcr_p95",
            "p_bcr_gt1"]].round(2).to_string())

# ---------------------------------------------------------------- figure
fig, axs = plt.subplots(1, 2, figsize=(15, 6.2), facecolor=SURF, gridspec_kw=dict(wspace=0.22))
xl = ["as assumed", "1.5× slower", "2× slower", "3× slower"]
for ax, mode in zip(axs, ("BRT", "light rail")):
    for net, col in (("efficiency network", "#c4532d"), ("equity network", "#3a7d5c")):
        d = A[(A.name == net) & (A["mode"] == mode)].set_index("case").reindex(CASES)
        x = np.arange(4) + (-0.1 if net.startswith("eff") else 0.1)
        ax.errorbar(x, d.bcr_central, yerr=[d.bcr_central - d.bcr_p5, d.bcr_p95 - d.bcr_central], fmt="o-", lw=2,
                    capsize=4, color=col, label=f"{net} (P(BCR>1) at 2×: {d.loc['roads 2x slower', 'p_bcr_gt1']:.0%})")
    for nm, col in (("Entebbe Road (A3)", "#8a6b4e"), ("Nansana - Busunju Road (A9)", "#4e7c8a")):
        d = A[(A.name == nm) & (A["mode"] == mode)].set_index("case").reindex(CASES)
        ax.plot(np.arange(4), d.bcr_central, ls=":", marker=".", color=col, label=f"{nm} alone")
    ax.axhline(1, color=INK, lw=1)
    ax.set_xticks(range(4)); ax.set_xticklabels(xl)
    ax.set_xlabel("peak road speeds compared with the assumed", fontsize=10, color=INK2)
    ax.set_title("BRT" if mode == "BRT" else "Light rail", loc="left", fontsize=12, color=INK)
    ax.set_facecolor(SURF)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", color=GRID)
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
axs[0].set_ylabel("benefit / cost ratio (time savings only)", fontsize=10, color=INK2)
fig.text(0.01, 1.03, "Would it pay? Benefit–cost ratios with 5–95% ranges", fontsize=15, color=INK)
fig.text(0.01, 0.985, "2,000 draws of capital and resettlement costs, O&M, trip rate, value of time and growth; 12% "
         "discount rate, 4 years building, 25 years running. Time savings only.", fontsize=9.5, color=INK2)
fig.savefig(os.path.join(KT, "figures", "k12_appraisal.png"), dpi=160, facecolor=SURF, bbox_inches="tight")
print("wrote k12_appraisal.png")
