"""Carry land-use uncertainty through to displacement and equity.

    python kampala-transit/scripts/k13_uncertainty.py     (after k08, k04, k09)

The random forest (k08) gives every cell a probability for each class. In each of 500 draws every
cell's class is sampled from those probabilities; a residential draw is split by building form as in
k07 (dense small-plot, planned / larger-plot, peri-urban, rural), farm/forest becomes rural / open.
For each draw:
  displacement   buildings inside the 24 m corridor (k04) by the land use of their cell, per corridor
                 and for the efficiency network
  residents      share of residents in each class
  equity         access gain of the efficiency BRT network (k09, central congestion) by class
The results are reported as central (the final classification of k08) and 5-95% ranges.
Writes outputs/uncertainty_displacement.csv, uncertainty_equity.csv, figures/k13_uncertainty.png.
"""
import os
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
KT = os.path.abspath(os.path.join(HERE, ".."))
BOX, CELL = (32.35, 0.02, 32.90, 0.55), 0.00225
W_ = int(round((BOX[2] - BOX[0]) / CELL))
H_ = int(round((BOX[3] - BOX[1]) / CELL))
ND = 500
RNG = np.random.default_rng(3)
CLS = ["dense small-plot", "planned / larger-plot", "peri-urban", "rural / open", "wetland / water",
       "commercial / industrial", "institutional"]

LU = pd.read_parquet(os.path.join(KT, "outputs", "landuse_cells.parquet"))
pcols = [c for c in LU.columns if c.startswith("p_")]
mlc = [c[2:] for c in pcols]
Pm = LU[pcols].to_numpy()
Pm = Pm / Pm.sum(axis=1, keepdims=True)
form = np.select([(LU.bld_ha >= 35) & (LU.med_m2 < 70), LU.bld_ha >= 8, LU.bld_ha >= 2],
                 ["dense small-plot", "planned / larger-plot", "peri-urban"], "rural / open")
MAP = {"residential": None, "farm / forest / grass": "rural / open", "wetland / water": "wetland / water",
       "commercial / industrial": "commercial / industrial", "institutional": "institutional"}


def draw():
    u = RNG.random(len(LU))[:, None]
    k = (Pm.cumsum(axis=1) < u).sum(axis=1).clip(0, len(mlc) - 1)
    out = np.array([MAP[mlc[i]] or "" for i in k], dtype=object)
    res = out == ""
    out[res] = form[res]
    return out


# buildings inside the corridor (k04) and the cell each lies in
DB = pd.read_csv(os.path.join(KT, "outputs", "demolished_buildings.csv"))
dcell = (((BOX[3] - DB.lat) / CELL).astype(int).clip(0, H_ - 1) * W_ + ((DB.lon - BOX[0]) / CELL).astype(int).clip(0, W_ - 1)).to_numpy()
steps = pd.read_csv(os.path.join(KT, "outputs", "network_steps.csv"))
eff = set(steps[steps.network == "efficiency"].route)
NAME = dict(pd.read_csv(os.path.join(KT, "outputs", "corridors_core.csv"))[["route", "name"]].itertuples(index=False))
# zones of k09 and the cells' residents
ZA = pd.read_parquet(os.path.join(KT, "outputs", "network_zone_access.parquet"))
live = LU["pop"].to_numpy() > 0
_, zi = cKDTree(np.c_[ZA.lon, ZA.lat]).query(np.c_[LU.lon[live], LU.lat[live]], distance_upper_bound=0.0075)
ok = zi < len(ZA)
cpop = LU["pop"].to_numpy()[live][ok]
czone = zi[ok]
dA, A0 = ZA["efficiency_BRT"].to_numpy(), ZA["base_A"].to_numpy()

disp, eq = [], []
for d in range(ND + 1):
    cls = LU.cls.to_numpy() if d == 0 else draw()            # draw 0: the final classification
    c_b = cls[dcell]
    for r in DB.route.unique():
        m = (DB.route == r).to_numpy()
        for c in CLS:
            disp.append((d, r, c, int((c_b[m] == c).sum())))
    m = DB.route.isin(eff).to_numpy()
    for c in CLS:
        disp.append((d, "efficiency network", c, int((c_b[m] == c).sum())))
    cc = cls[live][ok]
    tot = cpop.sum()
    for c in CLS:
        w = np.bincount(czone[cc == c], weights=cpop[cc == c], minlength=len(ZA))
        eq.append((d, c, 100 * w.sum() / tot, 100 * (w * dA).sum() / max((w * A0).sum(), 1)))
D = pd.DataFrame(disp, columns=["draw", "route", "landuse", "buildings"])
E = pd.DataFrame(eq, columns=["draw", "landuse", "residents_pct", "gain_pct"])


def summ(df, by, val):
    c = df[df.draw == 0].set_index(by)[val].rename("central")
    q = df[df.draw > 0].groupby(by)[val].quantile([0.05, 0.95]).unstack()
    q.columns = ["p5", "p95"]
    return pd.concat([c, q], axis=1).reset_index()


SD = summ(D, ["route", "landuse"], "buildings")
SD["name"] = SD.route.map(NAME).fillna(SD.route)
SD.to_csv(os.path.join(KT, "outputs", "uncertainty_displacement.csv"), index=False)
SE = summ(E, "landuse", "gain_pct").merge(summ(E, "landuse", "residents_pct"), on="landuse",
                                           suffixes=("_gain", "_residents"))
SE.to_csv(os.path.join(KT, "outputs", "uncertainty_equity.csv"), index=False)
pd.set_option("display.width", 200)
print(SE.round(1).to_string())
print(SD[(SD.landuse == "dense small-plot") & (SD.central > 20)].round(0).to_string())

# ---------------------------------------------------------------- figure
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

INK, INK2, SURF, GRID = "#1d2321", "#5d6764", "#fcfcfb", "#e6e4de"
fig, axs = plt.subplots(1, 2, figsize=(15, 6), facecolor=SURF, gridspec_kw=dict(wspace=0.45))
ax = axs[0]
se = SE.set_index("landuse").reindex(CLS[:5])
y = np.arange(len(se))
ax.errorbar(se.central_gain, y, xerr=[(se.central_gain - se.p5_gain).clip(lower=0), (se.p95_gain - se.central_gain).clip(lower=0)], fmt="o", color="#c4532d",
            capsize=4, ms=7)
ax.set_yticks(y); ax.set_yticklabels([f"{c}\n({r:.1f}% of residents; draws {a:.1f}–{b:.1f}%)" for c, r, a, b in
                                      zip(se.index, se.central_residents, se.p5_residents, se.p95_residents)], fontsize=9)
ax.invert_yaxis(); ax.grid(axis="x", color=GRID)
ax.set_xlabel("% more jobs and services reachable (efficiency BRT network, roads 2× slower)", fontsize=9.5, color=INK2)
ax.set_title("Equity gains by land use, with land-use uncertainty (5–95%)", loc="left", fontsize=11.5, color=INK)
ax = axs[1]
dd = SD[(SD.landuse == "dense small-plot") & SD.route.isin(list(eff) + ["efficiency network"])].sort_values("central")
dd = dd[dd.route != "efficiency network"]
y = np.arange(len(dd))
ax.barh(y, dd.central, color="#c0392b", height=0.6)
ax.errorbar(dd.central, y, xerr=[(dd.central - dd.p5).clip(lower=0), (dd.p95 - dd.central).clip(lower=0)], fmt="none", ecolor=INK, capsize=3)
ax.set_yticks(y); ax.set_yticklabels(dd.name, fontsize=9.5)
ax.grid(axis="x", color=GRID)
net = SD[(SD.route == "efficiency network") & (SD.landuse == "dense small-plot")].iloc[0]
ax.set_xlabel("buildings in dense small-plot settlement inside a 24 m corridor", fontsize=9.5, color=INK2)
ax.set_title(f"Displacement in dense settlement (network: {net.central:.0f}, {net.p5:.0f}–{net.p95:.0f})", loc="left",
             fontsize=11.5, color=INK)
for a_ in axs:
    a_.set_facecolor(SURF)
    for s_ in ("top", "right"):
        a_.spines[s_].set_visible(False)
fig.text(0.01, 1.02, "How sure are the land-use results?", fontsize=15, color=INK)
fig.text(0.01, 0.975, f"{ND} draws of every cell's class from the random forest's probabilities (k08); residential draws "
         "split by building form. Dots and bars: final classification (model used where at least 60% sure); whiskers: 5–95% of draws.", fontsize=9.5, color=INK2)
fig.savefig(os.path.join(KT, "figures", "k13_uncertainty.png"), dpi=160, facecolor=SURF, bbox_inches="tight")
print("wrote k13_uncertainty.png")
