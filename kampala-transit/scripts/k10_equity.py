"""Who gains? Equity of the two networks (k09) at the central congestion level.

    python kampala-transit/scripts/k10_equity.py

  figures/k10_equity.png   (a) access gain by the land-use class residents live in; (b) by distance from
                           the centre; (c) Lorenz curves of access before and after; (d) gain against
                           today's access, per zone
  outputs/equity.csv
"""
import os, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tnet  # noqa: E402

INK, INK2, SURF, GRID = "#1d2321", "#5d6764", "#fcfcfb", "#e6e4de"
KT = tnet.KT
R = pd.read_csv(os.path.join(KT, "outputs", "networks.csv"))
ZA = pd.read_parquet(os.path.join(KT, "outputs", "network_zone_access.parquet"))
G = tnet.GROUPS
NETS = [("efficiency_BRT", "Efficiency network, BRT", "#c4532d"), ("equity_BRT", "Equity network, BRT", "#3a7d5c"),
        ("efficiency_light rail", "Efficiency network, light rail", "#7c2e0f")]
CLS = ["dense small-plot", "planned / larger-plot", "peri-urban", "rural / open", "wetland / water",
       "commercial / industrial", "institutional"]
A0 = ZA.base_A.to_numpy()
rows = []
for key, lab, _ in NETS:
    dA = ZA[key].to_numpy()
    for c in CLS:
        w = G[c].to_numpy()
        rows.append(dict(network=lab, group="land use", value=c, residents=w.sum(),
                         gain_pct=100 * (w * dA).sum() / max((w * A0).sum(), 1),
                         reach_before_m2=(w * A0).sum() / w.sum(), reach_gain_m2=(w * dA).sum() / w.sum()))
    for lo, hi in ((0, 5), (5, 10), (10, 15), (15, 20), (20, 40)):
        m = ((ZA.cbd_km >= lo) & (ZA.cbd_km < hi)).to_numpy()
        w = ZA["pop"].to_numpy() * m
        rows.append(dict(network=lab, group="distance", value=f"{lo}–{hi} km", residents=w.sum(),
                         gain_pct=100 * (w * dA).sum() / max((w * A0).sum(), 1),
                         reach_before_m2=(w * A0).sum() / max(w.sum(), 1), reach_gain_m2=(w * dA).sum() / max(w.sum(), 1)))
Q = pd.DataFrame(rows)
Q.to_csv(os.path.join(KT, "outputs", "equity.csv"), index=False)


def style(ax):
    ax.set_facecolor(SURF)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(GRID); ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK2, length=0)
    ax.set_axisbelow(True)


fig, axs = plt.subplots(2, 2, figsize=(15, 11), facecolor=SURF, gridspec_kw=dict(hspace=0.42, wspace=0.28))
# (a) land use
ax = axs[0, 0]
cls = [c for c in CLS if G[c].sum() > 50000]
y = np.arange(len(cls))
for j, (key, lab, col) in enumerate(NETS):
    d = Q[(Q.network == lab) & (Q.group == "land use")].set_index("value").reindex(cls)
    ax.barh(y + (j - 1) * 0.27, d.gain_pct, height=0.26, color=col, label=lab)
ax.set_yticks(y); ax.set_yticklabels([f"{c}\n({G[c].sum() / 1e6:.2f} M residents)" for c in cls], fontsize=9.5, color=INK)
ax.invert_yaxis(); style(ax); ax.grid(axis="x", color=GRID)
ax.set_xlabel("% more jobs and services reachable in 45 min", fontsize=9.5, color=INK2)
ax.set_title("(a) By where residents live (land use, k07)", loc="left", fontsize=11.5, color=INK)
ax.legend(frameon=False, fontsize=9, loc="lower right")
# (b) distance
ax = axs[0, 1]
bands = ["0–5 km", "5–10 km", "10–15 km", "15–20 km", "20–40 km"]
x = np.arange(len(bands))
for j, (key, lab, col) in enumerate(NETS):
    d = Q[(Q.network == lab) & (Q.group == "distance")].set_index("value").reindex(bands)
    ax.bar(x + (j - 1) * 0.27, d.gain_pct, width=0.26, color=col)
ax.set_xticks(x); ax.set_xticklabels(bands, fontsize=10)
style(ax); ax.grid(axis="y", color=GRID)
ax.set_ylabel("% more jobs and services reachable", fontsize=9.5, color=INK2)
ax.set_xlabel("distance of home from the city centre", fontsize=9.5, color=INK2)
ax.set_title("(b) By distance from the centre", loc="left", fontsize=11.5, color=INK)
# (c) Lorenz
ax = axs[1, 0]
w = ZA["pop"].to_numpy()


def lorenz(a):
    o = np.argsort(a)
    return np.r_[0, np.cumsum(w[o]) / w.sum()], np.r_[0, np.cumsum((a * w)[o]) / (a * w).sum()]


xb, yb = lorenz(A0)
ax.plot(xb, yb, color=INK2, lw=2, label=f"today (Gini {tnet.gini(A0, w):.3f})")
for key, lab, col in NETS:
    xa, ya = lorenz(A0 + ZA[key].to_numpy())
    ax.plot(xa, ya, color=col, lw=1.6, label=f"{lab} (Gini {tnet.gini(A0 + ZA[key].to_numpy(), w):.3f})")
ax.plot([0, 1], [0, 1], color=GRID, lw=1)
style(ax)
ax.set_xlabel("share of residents, from least to most access", fontsize=9.5, color=INK2)
ax.set_ylabel("share of all access", fontsize=9.5, color=INK2)
ax.set_title("(c) How evenly access is spread", loc="left", fontsize=11.5, color=INK)
ax.legend(frameon=False, fontsize=9, loc="upper left")
# (d) gain vs today's access
ax = axs[1, 1]
key, lab, col = NETS[0]
dense_sh = (G["dense small-plot"] / G.sum(axis=1).replace(0, np.nan)).fillna(0).to_numpy()
sc = ax.scatter(A0 / 1e6, ZA[key] / 1e6, s=np.clip(w / 400, 2, 60), c=dense_sh, cmap="YlOrRd", vmin=0, vmax=0.6,
                alpha=0.75, linewidths=0)
cb = fig.colorbar(sc, ax=ax, fraction=0.04, pad=0.02)
cb.set_label("share of zone residents in dense small-plot settlement", fontsize=8.5)
style(ax); ax.grid(color=GRID)
ax.set_xlabel("floor area reachable in 45 min today (million m²)", fontsize=9.5, color=INK2)
ax.set_ylabel("added by the efficiency BRT network (million m²)", fontsize=9.5, color=INK2)
ax.set_title("(d) Each zone: today's access and what the network adds", loc="left", fontsize=11.5, color=INK)
fig.text(0.01, 0.975, "Who gains from rapid transit in Kampala?", fontsize=16, color=INK)
fig.text(0.01, 0.95, "Networks of k09 at the central congestion level (roads 2× slower than assumed). Access = built-up "
         "floor area (GHSL 2020) reachable within 45 minutes door to door, weighted by residents (WorldPop 2025).",
         fontsize=9.5, color=INK2)
fig.savefig(os.path.join(KT, "figures", "k10_equity.png"), dpi=160, facecolor=SURF, bbox_inches="tight")
pd.set_option("display.width", 200)
print(Q.pivot_table(index=["group", "value"], columns="network", values="gain_pct").round(1).to_string())
