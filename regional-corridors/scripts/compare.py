"""Leaving the capital: East African arteries against Southern African ones.

Reads the pipeline outputs (run.py 06 08 09 10 19) and data/arteries.json, and compares every
artery over its first 200 km (the headline comparison: the same length everywhere), and the
trade corridors over their full length inside the country.

Per artery: truck and car minutes lost per 100 km compared with open road, share of road that
is roadside settlement / town (road types clustered jointly across all hubs), buildings within
100 m per km, dual-carriageway share, controls per 100 km (signals, police posts,
weighbridges), built-up growth within 300 m 2000-2020, people within 300 m per km, safety
exposure per km. Then medians by hub and by region (East, Southern).

Writes outputs/compare_arteries.csv, outputs/compare_hubs.csv, outputs/compare_regions.csv,
outputs/compare_trade.csv, figures/c01_minutes_by_hub.png, c02_types_by_hub.png,
c03_buildings_vs_delay.png, c04_growth_by_hub.png.
"""
import json, os, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "..", "scripts")]
import config as C  # noqa: E402
from cartography import INK, INK2, SURF  # noqa: E402

KM = 200
O = lambda f: pd.read_csv(os.path.join(C.OUTPUTS, f))  # noqa: E731
A = pd.DataFrame(json.load(open(os.path.join(C.DATA, "arteries.json")))).rename(columns={"name": "corridor"})
P = (O("pieces_typed.csv").merge(O("travel_time_pieces.csv")[["corridor", "piece", "car_excess_min", "truck_excess_min"]])
     .merge(O("growth_pieces.csv")[["corridor", "piece", "built_ha_2000", "built_ha_2020"]], how="left"))
sp = os.path.join(C.OUTPUTS, "safety_pieces.csv")
if os.path.exists(sp):
    P = P.merge(pd.read_csv(sp)[["corridor", "piece", "people_300m", "exposure"]], how="left")
P = P.merge(A[["corridor", "hub", "region", "country", "trade"]], on="corridor")
HUB_ORDER = ["kampala", "nairobi", "kigali", "dodoma", "dar_es_salaam", "pretoria", "johannesburg", "gaborone",
             "harare", "lusaka", "maputo", "windhoek"]
HUB_LABEL = {h: h.replace("_", " ").title().replace("Es ", "es ") for h in HUB_ORDER}
REG_COL = {"East": "#c4532d", "Southern": "#4e7c8a"}


def measures(d):
    km = len(d) * 0.5
    b2000, b2020 = d.built_ha_2000.sum(), d.built_ha_2020.sum()
    out = dict(km=km,
               truck_min_per_100km=d.truck_excess_min.sum() / km * 100,
               car_min_per_100km=d.car_excess_min.sum() / km * 100,
               settlement_share=(d.road_type == "roadside settlement").mean(),
               town_share=(d.road_type == "town").mean(),
               open_share=(d.road_type == "open road").mean(),
               buildings_100m_per_km=d.buildings_100m.sum() / km,
               dual_share=d.dual.mean(),
               controls_per_100km=(d.signals + d.police_posts + d.weighbridges).sum() / km * 100,
               growth_2000_2020=(b2020 / b2000 - 1) if b2000 > 0 else np.nan)
    if "people_300m" in d:
        out.update(people_per_km=d.people_300m.sum() / km, exposure_per_km=d.exposure.sum() / km)
    return out


rows = []
for c, d in P.groupby("corridor"):
    first = d[d.km_start < KM]
    meta = A.set_index("corridor").loc[c]
    rows.append(dict(corridor=c, hub=meta.hub, region=meta.region, country=meta.country, ref=meta.ref,
                     toward=meta.toward, trade=meta.trade, **measures(first)))
R = pd.DataFrame(rows)
R.round(3).to_csv(os.path.join(C.OUTPUTS, "compare_arteries.csv"), index=False)
cols = [c for c in R.columns if c not in ("corridor", "hub", "region", "country", "ref", "toward", "trade", "km")]
H = R.groupby(["region", "hub"])[cols].median().join(R.groupby(["region", "hub"]).size().rename("arteries")).reset_index()
H.round(3).to_csv(os.path.join(C.OUTPUTS, "compare_hubs.csv"), index=False)
G = R.groupby("region")[cols].median().join(R.groupby("region").size().rename("arteries"))
G.round(3).to_csv(os.path.join(C.OUTPUTS, "compare_regions.csv"))
print(G.round(2).T.to_string())
T = pd.DataFrame([dict(corridor=c, hub=d.hub.iloc[0], region=d.region.iloc[0], **measures(d))
                  for c, d in P[P.trade].groupby("corridor")])
T.round(3).to_csv(os.path.join(C.OUTPUTS, "compare_trade.csv"), index=False)

hubs = [h for h in HUB_ORDER if h in set(R.hub)]


def style(ax):
    for s_ in ("top", "right", "left"):
        ax.spines[s_].set_visible(False)
    ax.spines["bottom"].set_color("#e4e3df")
    ax.grid(axis="x", color="#e4e3df", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(colors=INK2, labelsize=9, length=0)


# c01: truck minutes lost per 100 km, every artery as a dot, hub median as a bar
fig, ax = plt.subplots(figsize=(11, 0.45 * len(hubs) + 1.6), facecolor=SURF)
for i, h in enumerate(hubs):
    d = R[R.hub == h]
    reg = d.region.iloc[0]
    ax.barh(i, d.truck_min_per_100km.median(), color=REG_COL[reg], alpha=0.25, height=0.6, linewidth=0)
    ax.scatter(d.truck_min_per_100km, np.full(len(d), i), s=26, color=REG_COL[reg], zorder=3,
               edgecolor="white", linewidth=0.6)
ax.set_yticks(range(len(hubs)))
ax.set_yticklabels([f"{HUB_LABEL[h]} ({(R.hub == h).sum()})" for h in hubs], fontsize=10, color=INK)
ax.invert_yaxis()
style(ax)
ax.set_xlabel("truck minutes lost per 100 km vs open road, first 200 km of each artery", fontsize=9, color=INK2)
m = G.truck_min_per_100km
fig.text(0.01, 1.02, f"Roads out of East African capitals lose {m.get('East', np.nan):.0f} truck minutes per 100 km; "
         f"Southern African ones {m.get('Southern', np.nan):.0f} (medians)", fontsize=13, color=INK)
fig.text(0.01, 0.975, "Dots: each artery (count in brackets). Bars: hub median. Light traffic, dry day; same model and "
         "assumptions everywhere.", fontsize=9, color=INK2)
fig.savefig(os.path.join(C.FIGURES, "c01_minutes_by_hub.png"), dpi=150, facecolor=SURF, bbox_inches="tight")

# c02: road type composition by hub (median artery)
fig, ax = plt.subplots(figsize=(11, 0.45 * len(hubs) + 1.6), facecolor=SURF)
hh = H.set_index("hub").reindex(hubs)
left = np.zeros(len(hubs))
for col, lab, c in (("open_share", "open road", "#b9d3c1"), ("settlement_share", "roadside settlement", "#e2bb62"),
                    ("town_share", "town", "#b8491c")):
    v = hh[col].to_numpy()
    ax.barh(range(len(hubs)), v, left=left, color=c, height=0.62, label=lab, linewidth=0)
    for i, (l_, w_) in enumerate(zip(left, v)):
        if w_ > 0.08:
            ax.text(l_ + w_ / 2, i, f"{w_:.0%}", ha="center", va="center", fontsize=8.5,
                    color="white" if col == "town_share" else INK)
    left += v
ax.set_yticks(range(len(hubs)))
ax.set_yticklabels([HUB_LABEL[h] for h in hubs], fontsize=10, color=INK)
ax.invert_yaxis()
ax.set_xlim(0, 1)
style(ax)
ax.legend(loc="lower right", frameon=False, fontsize=8.5, ncol=3, bbox_to_anchor=(1, -0.2))
fig.text(0.01, 1.0, "How much of the first 200 km is still open road", fontsize=13, color=INK)
fig.text(0.01, 0.96, "Median artery per hub; road types clustered jointly across all hubs (shares need not sum to "
         "exactly 100%).", fontsize=9, color=INK2)
fig.savefig(os.path.join(C.FIGURES, "c02_types_by_hub.png"), dpi=150, facecolor=SURF, bbox_inches="tight")

# c03: roadside buildings vs truck delay, every artery
fig, ax = plt.subplots(figsize=(9, 6), facecolor=SURF)
for reg, d in R.groupby("region"):
    ax.scatter(d.buildings_100m_per_km, d.truck_min_per_100km, s=30, color=REG_COL[reg], alpha=0.85, label=reg,
               edgecolor="white", linewidth=0.6)
for s_ in ("top", "right"):
    ax.spines[s_].set_visible(False)
ax.grid(color="#e4e3df", linewidth=0.6)
ax.set_axisbelow(True)
ax.tick_params(colors=INK2, labelsize=9, length=0)
ax.set_xlabel("buildings within 100 m of the road, per km (first 200 km)", fontsize=9, color=INK2)
ax.set_ylabel("truck minutes lost per 100 km", fontsize=9, color=INK2)
ax.legend(frameon=False, fontsize=9)
ax.set_title("More roadside building, more lost time, in both regions", loc="left", fontsize=13, color=INK)
fig.savefig(os.path.join(C.FIGURES, "c03_buildings_vs_delay.png"), dpi=150, facecolor=SURF, bbox_inches="tight")

# c04: growth of roadside built-up land 2000-2020 by hub
fig, ax = plt.subplots(figsize=(11, 0.45 * len(hubs) + 1.6), facecolor=SURF)
for i, h in enumerate(hubs):
    d = R[R.hub == h]
    reg = d.region.iloc[0]
    ax.barh(i, d.growth_2000_2020.median(), color=REG_COL[reg], alpha=0.8, height=0.6, linewidth=0)
    ax.text(d.growth_2000_2020.median() + 0.01, i, f"+{d.growth_2000_2020.median():.0%}", va="center", fontsize=9,
            color=INK)
ax.set_yticks(range(len(hubs)))
ax.set_yticklabels([HUB_LABEL[h] for h in hubs], fontsize=10, color=INK)
ax.invert_yaxis()
style(ax)
ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1))
fig.text(0.01, 1.0, "Roadside building grew fastest out of East African capitals", fontsize=13, color=INK)
fig.text(0.01, 0.96, "Growth of built-up land within 300 m of the road, 2000–2020 (GHSL), median artery, first 200 km.",
         fontsize=9, color=INK2)
fig.savefig(os.path.join(C.FIGURES, "c04_growth_by_hub.png"), dpi=150, facecolor=SURF, bbox_inches="tight")
print("wrote outputs/compare_*.csv, figures/c01-c04")
