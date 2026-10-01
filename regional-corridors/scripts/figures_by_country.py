"""The paper-1 figure families, redrawn one country at a time, and the comparisons between countries.

    python scripts/figures_by_country.py

figures/countries/<iso>/ (the roads leaving that country's hubs; Tanzania and South Africa have two):
  01_typology   share of each road by type, and buildings within 100 m per km of each type
  02_growth     built-up land within 300 m per km, 2000-2020 (and 2026 projection); growth by road type
  03_causes     truck and car minutes per 100 km, by cause
  04_hotspots   the country's roads coloured by delay, the ten worst 2 km stretches numbered and listed
  05_scenarios  truck minutes and dollars a year saved by each fix, with 5-95% ranges
  06_costs      cost of lost time per truck trip, and per year by cause
  07_reliability truck trip time by month (mean and bad day) and the buffer index
  08_safety     who lives beside the road, where the exposure is, and the worst stretches
  09_fuel_co2   extra diesel per trip by cause; litres, CO2 and dollars a year
  10_waterfall  how a truck trip grows cause by cause, one panel per road, one scale
  11_rank_stability which cause is the largest across 1,000 draws
  12_strip_maps every road as a line: new building, road type, delay, controls
figures/compare/:
  k01-k09       one dot per road, grouped by country (East then Southern), with the country median
"""
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import matplotlib.ticker as mtick

from regional_common import (ART, C, CAUSE_COL, EAST, GRID, H, INK, INK2, KM, O, SOUTH, SURF, TYPE_COL, distinct,
                             pieces, save, style)
import cartography as K

ISO = {"Uganda": "uga", "Kenya": "ken", "Rwanda": "rwa", "United Republic of Tanzania": "tza",
       "South Africa": "zaf", "Botswana": "bwa", "Zimbabwe": "zwe", "Zambia": "zmb", "Mozambique": "moz",
       "Namibia": "nam"}
SHORT = {"United Republic of Tanzania": "Tanzania"}
CAUSES = list(CAUSE_COL)
DARK_TEXT = ("speed humps (assumed)", "signals and crossings", "curves", "town speed limit")
FIX = {"wim": "Weigh-in-motion", "no_police": "No police stops", "bypass_2": "Bypass 2 worst towns",
       "service_20km": "Service roads, worst 20 km", "service_all": "Service roads, all settlements",
       "all": "All together"}
FIX_COL = dict(zip(FIX, ["#3a7d5c", "#4e7c8a", "#d9a441", "#e8c77e", "#c4532d", INK]))
DELAY_BOUNDS = [0, 0.25, 0.5, 1, 2, 4, 100]
DELAY_LABELS = ["< 0.25", "0.25–0.5", "0.5–1", "1–2", "2–4", "> 4"]
DCMAP = ListedColormap(["#f3eee6", "#fde6da", "#f6b596", "#eb6834", "#b8491c", "#7c2e0f"])
DNORM = BoundaryNorm(DELAY_BOUNDS, DCMAP.N)

TOT = O("travel_time_totals.csv")
CA = O("travel_time_causes.csv")
TY = O("typology_summary.csv")
GS = O("growth_summary.csv")
GP = O("growth_pieces.csv")
SC = O("scenarios.csv")
CS = O("costs_scenarios.csv")
CO = O("costs.csv")
CBC = O("costs_by_cause.csv")
RM = O("reliability_monthly.csv")
RE = O("reliability.csv")
SBT = O("safety_by_type.csv")
SST = O("safety_stretches.csv")
SP = O("safety_pieces.csv")
FU = O("fuel_co2.csv")
FBC = O("fuel_co2_by_cause.csv")
RS = O("rank_stability.csv")
PT = O("pieces_typed.csv")
TTP = O("travel_time_pieces.csv")
CMP = O("compare_arteries.csv")
H["road"] = H.corridor.map(ART.road)
ADM = gpd.read_file(os.path.join(C.DATA, "ne_admin0", "ne_10m_admin_0_countries.shp"), columns=["ADMIN"])
pieces4326 = pieces.to_crs(4326)


def roads_in(country):
    """Roads leaving the country's hubs, by hub then longest first. Labels name the hub only when
    the country has two."""
    a = ART[ART.country == country].copy()
    a["km_"] = KM.reindex(a.index)
    a = a.sort_values(["hub", "km_"], ascending=[True, False])
    two = a.hub.nunique() > 1
    a["lab"] = [f"{r.hub_name} {r.short}" if two else r.short for r in a.itertuples()]
    a["lab"] = a.lab + np.where(a.trade, " ★", "")
    return a


def header(fig, country, what, sub):
    h = fig.get_figheight()
    fig.text(0.01, 1 - 0.15 / h, f"{SHORT.get(country, country)}: {what}", fontsize=16, fontweight="bold",
             color=INK, va="top")
    fig.text(0.01, 1 - 0.5 / h, sub, fontsize=9.5, color=INK2, va="top")


def top(fig, extra=0.0):
    return 1 - (0.85 + extra) / fig.get_figheight()


def ylabels(ax, roads):
    ax.set_yticks(range(len(roads)))
    ax.set_yticklabels(roads.lab, fontsize=9.5, color=INK)
    ax.set_ylim(len(roads) - 0.5, -0.5)


def stacked(ax, M, colors, roads, fmt="{:.0f}", min_label=None, height=0.62):
    """Horizontal stacked bars with negatives stacked leftwards from zero."""
    pos, neg = np.zeros(len(M)), np.zeros(len(M))
    tot = M.clip(lower=0).sum(axis=1).max()
    for k in M.columns:
        v = M[k].fillna(0).to_numpy()
        base = np.where(v >= 0, pos, neg)
        ax.barh(range(len(M)), v, left=base, color=colors[k], height=height, linewidth=0.6, edgecolor=SURF,
                label=k)
        for i, (b, w) in enumerate(zip(base, v)):
            if min_label is not None and abs(w) >= min_label * tot:
                ax.text(b + w / 2, i, fmt.format(w), ha="center", va="center", fontsize=8,
                        color=INK if k in DARK_TEXT or k in ("open road", "roadside settlement") else "white")
        pos, neg = np.where(v >= 0, pos + v, pos), np.where(v < 0, neg + v, neg)
    ylabels(ax, roads)
    return pos


# ====================================================================== per-country sheets
def f01_typology(country, iso, roads):
    n = len(roads)
    fig, axs = plt.subplots(1, 2, figsize=(14, 0.5 * n + 2.6), facecolor=SURF,
                            gridspec_kw=dict(wspace=0.08))
    t = TY[TY.corridor.isin(roads.index)]
    sh = t.pivot(index="corridor", columns="road_type", values="share").reindex(roads.index)[list(TYPE_COL)]
    stacked(axs[0], sh, TYPE_COL, roads, fmt="{:.0%}", min_label=0.07)
    axs[0].xaxis.set_major_formatter(mtick.PercentFormatter(1))
    axs[0].set_xlim(0, 1)
    style(axs[0], grid=None)
    axs[0].set_title("Share of each road by type", loc="left", fontsize=11, color=INK)
    b = t.pivot(index="corridor", columns="road_type", values="buildings_100m").reindex(roads.index)
    y = np.arange(n)
    for j, k in enumerate(TYPE_COL):
        axs[1].barh(y + (j - 1) * 0.26, b[k], height=0.25, color=TYPE_COL[k], linewidth=0, label=k)
    axs[1].set_yticks([])
    axs[1].set_ylim(n - 0.5, -0.5)
    style(axs[1])
    axs[1].set_title("Buildings within 100 m, per km of each type", loc="left", fontsize=11, color=INK)
    fig.legend(handles=[Patch(color=c, label=k) for k, c in TYPE_COL.items()], loc="lower center", ncol=3,
               frameon=False, fontsize=9.5, bbox_to_anchor=(0.5, -0.02))
    fig.subplots_adjust(top=top(fig, 0.2), bottom=0.9 / fig.get_figheight())
    header(fig, country, "what kind of road is it?", "Each 500 m piece is open road, roadside settlement or town "
           "from the buildings, joining roads and roadside activity around it (08_typology.py). ★ trade corridor.")
    save(fig, "01_typology.png", f"countries/{iso}")


def f02_growth(country, iso, roads):
    n = len(roads)
    wide = roads.lab.str.len().max() > 24
    fig, axs = plt.subplots(1, 2, figsize=(16 if wide else 14, max(0.5 * n + 2.6, 4.8)), facecolor=SURF,
                            gridspec_kw=dict(wspace=0.75 if wide else 0.4, width_ratios=[1, 1.1]))
    g = GS[(GS.road_type == "all") & GS.corridor.isin(roads.index)].set_index("corridor").reindex(roads.index)
    yrs = [2000, 2005, 2010, 2015, 2020, 2026]
    cols = [f"built_ha_{y}" for y in yrs[:-1]] + ["built_ha_2026_proj"]
    cmap = plt.get_cmap("tab20" if n > 10 else "tab10")
    ends = []
    for i, (name, r) in enumerate(g.iterrows()):
        v = r[cols].to_numpy(float) / roads.km_[name]
        axs[0].plot(yrs[:-1], v[:-1], color=cmap(i % 20), lw=1.8, marker="o", ms=3.5)
        axs[0].plot(yrs[-2:], v[-2:], color=cmap(i % 20), lw=1.4, ls=":")
        ends.append((v[-1], (roads.short[name] + (" ★" if roads.trade[name] else "")).replace("→ ", ""),
                     cmap(i % 20)))
    lo, hi = axs[0].get_ylim()
    gap = (hi - lo) * 0.055   # labels at the line ends, nudged apart
    ends.sort(key=lambda e: e[0])
    ys = []
    for y, _, _ in ends:
        ys.append(max(y, ys[-1] + gap) if ys else y)
    for (y, lab, col), y2 in zip(ends, ys):
        axs[0].annotate(lab, (2026, y), xytext=(2026.6, y2), fontsize=8.5, color=col, va="center",
                        arrowprops=dict(arrowstyle="-", color=col, lw=0.5) if abs(y2 - y) > gap * 0.3 else None)
    axs[0].set_ylim(lo, max(hi, ys[-1] + gap))
    axs[0].set_xlim(1999, 2033)
    style(axs[0], grid="y")
    axs[0].tick_params(axis="y", colors=INK2)
    axs[0].set_ylabel("built-up ha within 300 m, per km", fontsize=9, color=INK2)
    axs[0].set_title("Built-up land beside each road (dotted: 2026 projection)", loc="left", fontsize=11, color=INK)
    gt = GS[(GS.road_type != "all") & GS.corridor.isin(roads.index)].pivot(
        index="corridor", columns="road_type", values="growth_pct").reindex(roads.index)
    y = np.arange(n)
    for j, k in enumerate(TYPE_COL):
        if k in gt:
            axs[1].barh(y + (j - 1) * 0.26, gt[k], height=0.25, color=TYPE_COL[k], linewidth=0, label=k)
    ga = g.growth_2000_2020_pct
    axs[1].scatter(ga, y, marker="|", s=260, color=INK, zorder=4, label="whole road")
    ylabels(axs[1], roads)
    style(axs[1])
    axs[1].xaxis.set_major_formatter(mtick.PercentFormatter(100))
    axs[1].set_title("Growth of built-up land, 2000–2020, by road type", loc="left", fontsize=11, color=INK)
    axs[1].legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=4, frameon=False, fontsize=8.5)
    fig.subplots_adjust(top=top(fig, 0.2), bottom=0.9 / fig.get_figheight())
    header(fig, country, "how fast the roadside is building up", "GHSL built-up surface within 300 m of the road "
           "(09_growth.py); the 2026 value extends each road's 2015–2020 trend.")
    save(fig, "02_growth.png", f"countries/{iso}")


def cause_matrix(roads, veh):
    c = CA[(CA.vehicle == veh) & (CA.direction == "outbound") & CA.corridor.isin(roads.index)]
    m = c.pivot(index="corridor", columns="cause", values="minutes").reindex(roads.index)
    return m[[k for k in CAUSES if k in m]].div(roads.km_, axis=0) * 100


def f03_causes(country, iso, roads):
    n = len(roads)
    fig, axs = plt.subplots(1, 2, figsize=(15, 0.5 * n + 2.8), facecolor=SURF, sharey=True,
                            gridspec_kw=dict(wspace=0.06))
    xmax = 0
    for ax, veh in zip(axs, ("truck", "car")):
        m = cause_matrix(roads, veh)
        tot = stacked(ax, m, CAUSE_COL, roads, min_label=0.06)
        for i, t in enumerate(tot):
            ax.text(t + 0.6, i, f"{t:.0f}", va="center", fontsize=9, color=INK, fontweight="bold")
        xmax = max(xmax, tot.max())
        style(ax)
        ax.set_title(f"{veh}: minutes per 100 km", loc="left", fontsize=11, color=INK)
    for ax in axs:
        ax.set_xlim(0, xmax * 1.12)
    fig.legend(handles=[Patch(color=c, label=k) for k, c in CAUSE_COL.items()], loc="lower center", ncol=5,
               frameon=False, fontsize=9, bbox_to_anchor=(0.5, -0.02))
    fig.subplots_adjust(top=top(fig, 0.2), bottom=1.0 / fig.get_figheight())
    header(fig, country, "minutes lost, by cause", "Leaving the hub on a dry day in light traffic, per 100 km so "
           "roads of any length compare; one scale for car and truck. Causes are run one at a time, so their sum can "
           "differ by a few minutes from the totals in the comparisons (k01). Controls as mapped in OSM.")
    save(fig, "03_causes.png", f"countries/{iso}")


def f04_hotspots(country, iso, roads):
    pc = pieces4326[pieces4326.corridor.isin(roads.index)]
    x0, y0, x1, y1 = pc.total_bounds
    pad = max(x1 - x0, y1 - y0) * 0.06
    x0, x1, y0, y1 = x0 - pad, x1 + pad, y0 - pad, y1 + pad
    asp = (y1 - y0) / ((x1 - x0) * np.cos(np.radians((y0 + y1) / 2)))
    w = 9.0
    sel = distinct(H[H.corridor.isin(roads.index)], 10, min_km=5).reset_index(drop=True)
    fig = plt.figure(figsize=(w + 5.6, max(w * asp, 6.5) + 1.0), facecolor=SURF)
    ax = fig.add_axes([0.0, 0.03, w / (w + 5.6), top(fig, 0.1) - 0.03])
    K.frame(ax, (x0, x1, y0, y1))
    ADM.cx[x0:x1, y0:y1].plot(ax=ax, aspect=None, color="#efede8", edgecolor="#bdb8ae", linewidth=0.6)
    ADM[ADM.ADMIN == country].plot(ax=ax, aspect=None, color="#fbfaf7", edgecolor=INK2, linewidth=0.9)
    pc.plot(ax=ax, aspect=None, color=INK, linewidth=3.4, zorder=3)
    pc.plot(ax=ax, aspect=None, column="per_km", cmap=DCMAP, norm=DNORM, linewidth=2.2, zorder=4)
    for hub, a in roads.groupby("hub"):
        s = a.iloc[0].start
        ax.scatter(*s, s=60, color=INK, zorder=6)
        ax.annotate(a.hub_name.iloc[0], s, xytext=(6, 6), textcoords="offset points", fontsize=11,
                    fontweight="bold", color=INK, zorder=7)
    for r in roads.itertuples():
        ax.annotate(r.toward, r.end, xytext=(4, -4), textcoords="offset points", fontsize=8.5, color=INK2,
                    style="italic", zorder=7)
    xs, ys = sel.lon.to_list(), sel.lat.to_list()
    ax.scatter(xs, ys, s=14, color=INK, zorder=8)
    ts = [ax.text(x, y, str(i + 1), ha="center", va="center", fontsize=8.5, color=INK, fontweight="bold",
                  zorder=9, bbox=dict(boxstyle="circle,pad=0.25", fc="white", ec=INK, lw=1.1))
          for i, (x, y) in enumerate(zip(xs, ys))]
    K.adjust_text(ts, x=xs, y=ys, ax=ax, expand=(1.6, 1.7), arrowprops=dict(arrowstyle="-", color=INK, lw=0.7))
    K.scalebar(ax, loc="lower left")
    K.key(fig, ax, DCMAP, DNORM, DELAY_BOUNDS, "truck min lost per km", labels=DELAY_LABELS)
    lines = [f"{i + 1}. {r.place_name} — {r.road}, km {r.km_from:.0f}–{r.km_to:.0f}\n"
             f"    truck +{r.truck_excess_min:.1f} min, car +{r.car_excess_min:.1f} min · {r.road_type}\n"
             f"    {r.main_causes.replace('; ', ', ')}" for i, r in enumerate(sel.itertuples())]
    fig.text(w / (w + 5.6) + 0.06, top(fig, 0.3), "\n".join(lines), fontsize=8, color=INK, va="top",
             linespacing=1.4, wrap=True)
    header(fig, country, "where the roads lose time", "Minutes a loaded truck loses per km against open road. "
           "Numbered: the ten worst 2 km stretches (at least 5 km apart); close-ups in figures/closeups.")
    save(fig, "04_hotspots.png", f"countries/{iso}")


def f05_scenarios(country, iso, roads):
    n = len(roads)
    fig, axs = plt.subplots(1, 2, figsize=(15, 0.62 * n + 2.8), facecolor=SURF, sharey=True,
                            gridspec_kw=dict(wspace=0.06))
    for ax, (tab, col, lab) in zip(axs, ((SC[SC.vehicle == "truck"], "minutes_saved", "truck minutes saved per trip"),
                                         (CS, "saving_per_year_usd_m", "US$ million saved a year (all vehicles)"))):
        d = tab[tab.corridor.isin(roads.index)]
        ks = [k for k in FIX if k in set(d.scenario)]
        hgt = 0.82 / len(ks)
        for j, k in enumerate(ks):
            v = d[d.scenario == k].set_index("corridor").reindex(roads.index)
            yy = np.arange(n) - 0.41 + (j + 0.5) * hgt
            ax.barh(yy, v[col], height=hgt * 0.9, color=FIX_COL[k], linewidth=0, label=FIX[k])
            ax.errorbar(v[col], yy, xerr=[(v[col] - v.p5).clip(lower=0), (v.p95 - v[col]).clip(lower=0)], fmt="none",
                        ecolor=INK2, elinewidth=0.6, capsize=1.2)
        ylabels(ax, roads)
        style(ax)
        ax.set_xlabel(lab, fontsize=9.5, color=INK2)
        ax.set_title(lab[0].upper() + lab[1:], loc="left", fontsize=11, color=INK)
    fig.legend(handles=[Patch(color=FIX_COL[k], label=v) for k, v in FIX.items()], loc="lower center", ncol=6,
               frameon=False, fontsize=9, bbox_to_anchor=(0.5, -0.02))
    fig.subplots_adjust(top=top(fig, 0.2), bottom=1.0 / fig.get_figheight())
    header(fig, country, "what each fix would save", "Travel-time model with each fix applied (16_scenarios.py); "
           "whiskers 5–95% of 1,000 draws. Dollars use one assumed traffic level per road; congestion relief "
           "is not counted.")
    save(fig, "05_scenarios.png", f"countries/{iso}")


def f06_costs(country, iso, roads):
    n = len(roads)
    fig, axs = plt.subplots(1, 2, figsize=(15, 0.5 * n + 2.8), facecolor=SURF, sharey=True,
                            gridspec_kw=dict(wspace=0.06, width_ratios=[0.8, 1.2]))
    c = CO[(CO.vehicle == "truck") & CO.corridor.isin(roads.index)].set_index("corridor").reindex(roads.index)
    per100 = c.cost_per_trip_usd / roads.km_ * 100
    axs[0].barh(range(n), per100, color="#b8491c", height=0.6, linewidth=0)
    axs[0].errorbar(per100, range(n), xerr=[(per100 - c.cost_per_trip_usd_p5 / roads.km_ * 100).clip(lower=0),
                                            (c.cost_per_trip_usd_p95 / roads.km_ * 100 - per100).clip(lower=0)],
                    fmt="none", ecolor=INK2, elinewidth=0.7, capsize=2)
    for i, (v, t) in enumerate(zip(per100, c.cost_per_trip_usd)):
        axs[0].text(0.02 * per100.max(), i, f"${t:.0f}/trip", va="center", fontsize=8.5, color="white")
    ylabels(axs[0], roads)
    style(axs[0])
    axs[0].set_title("Loaded truck: US$ per 100 km of lost time", loc="left", fontsize=11, color=INK)
    m = CBC[CBC.corridor.isin(roads.index)].pivot(index="corridor", columns="cause",
                                                  values="cost_per_year_usd_m").reindex(roads.index)
    m = m[[k for k in CAUSES if k in m]]
    tot = stacked(axs[1], m, CAUSE_COL, roads, fmt="{:.1f}", min_label=0.07)
    for i, t in enumerate(tot):
        axs[1].text(t + 0.01 * tot.max(), i, f"${t:.1f} M", va="center", fontsize=9, color=INK, fontweight="bold")
    axs[1].set_xlim(0, tot.max() * 1.15)
    style(axs[1])
    axs[1].set_title("US$ million a year, by cause (all vehicles)", loc="left", fontsize=11, color=INK)
    fig.legend(handles=[Patch(color=c_, label=k) for k, c_ in CAUSE_COL.items()], loc="lower center", ncol=5,
               frameon=False, fontsize=9, bbox_to_anchor=(0.5, -0.02))
    fig.subplots_adjust(top=top(fig, 0.2), bottom=1.0 / fig.get_figheight())
    header(fig, country, "what the lost time costs", "Value of time and vehicle operating cost per minute "
           "(17_costs.py); yearly totals use one assumed traffic level for every road, so compare roads, not "
           "absolute sums.")
    save(fig, "06_costs.png", f"countries/{iso}")


def f07_reliability(country, iso, roads):
    n = len(roads)
    cols = 3 if n > 4 else 2
    rows = int(np.ceil(n / cols)) + 1
    fig = plt.figure(figsize=(15, 2.5 * rows + 1.2), facecolor=SURF)
    gs = fig.add_gridspec(rows, cols, hspace=0.75, wspace=0.25, top=top(fig, 0.15), bottom=0.05)
    for i, (name, a) in enumerate(roads.iterrows()):
        ax = fig.add_subplot(gs[i // cols, i % cols])
        m = RM[(RM.corridor == name) & (RM.vehicle == "truck")].sort_values("month")
        ax.fill_between(m.month, m.mean_min / 60, m.p95_min / 60, color="#e8c77e", alpha=0.6, lw=0)
        ax.plot(m.month, m.mean_min / 60, color=INK, lw=1.4)
        ax.plot(m.month, m.p95_min / 60, color="#b8491c", lw=1.0, ls="--")
        ax.set_xticks(range(1, 13))
        ax.set_xticklabels(list("JFMAMJJASOND"), fontsize=8)
        style(ax, grid="y")
        ax.tick_params(axis="y", colors=INK2, labelsize=8)
        ax.set_title(a.lab, loc="left", fontsize=10, color=INK)
        if i % cols == 0:
            ax.set_ylabel("truck hours", fontsize=8.5, color=INK2)
    ax = fig.add_subplot(gs[rows - 1, :])
    r = RE[(RE.vehicle == "truck") & RE.corridor.isin(roads.index)].set_index("corridor").reindex(roads.index)
    ax.bar(range(n), r.buffer_index * 100, color="#4e7c8a", width=0.6)
    for i, (b, d) in enumerate(zip(r.buffer_index, r.days_over_2pct_slower)):
        ax.text(i, b * 100, f"{b:.1%}\n{d:.0f} days/yr >2% slower", ha="center", va="bottom", fontsize=8, color=INK)
    ax.set_xticks(range(n))
    ax.set_xticklabels(roads.lab, fontsize=9, color=INK)
    ax.set_ylim(0, r.buffer_index.max() * 100 * 1.6)
    style(ax, grid="y")
    ax.tick_params(axis="y", colors=INK2)
    ax.set_ylabel("buffer index, %", fontsize=8.5, color=INK2)
    ax.set_title("Buffer index: extra time to plan for so a truck is late on only 1 day in 20", loc="left",
                 fontsize=10.5, color=INK)
    fig.legend(handles=[Line2D([], [], color=INK, lw=1.4, label="mean"),
                        Line2D([], [], color="#b8491c", lw=1, ls="--", label="bad day (95th percentile)")],
               loc="upper right", ncol=2, frameon=False, fontsize=9, bbox_to_anchor=(0.99, top(fig, -0.1)))
    header(fig, country, "how rain changes the trip", "Every day 2006–2025 replayed with the rain that fell on each "
           "piece (CHIRPS; 18_reliability.py). Wet roads slow traffic; floods that close a road are not modelled.")
    save(fig, "07_reliability.png", f"countries/{iso}")


def f08_safety(country, iso, roads):
    n = len(roads)
    fig = plt.figure(figsize=(15, 0.5 * n + 7.5), facecolor=SURF)
    gs = fig.add_gridspec(2, 2, height_ratios=[0.5 * n + 1.2, 4.6], hspace=0.45, wspace=0.08, top=top(fig, 0.15),
                          bottom=0.04)
    ax = fig.add_subplot(gs[0, 0])
    s = SBT[SBT.corridor.isin(roads.index)]
    m = s.pivot(index="corridor", columns="road_type", values="exposure_share").reindex(roads.index)[list(TYPE_COL)]
    stacked(ax, m, TYPE_COL, roads, fmt="{:.0%}", min_label=0.08)
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(1))
    style(ax, grid=None)
    ax.set_title("Where the exposure is, by road type", loc="left", fontsize=11, color=INK)
    ax = fig.add_subplot(gs[0, 1])
    c = CMP.set_index("corridor").reindex(roads.index)
    ax.barh(np.arange(n) - 0.17, c.people_per_km, height=0.32, color="#d9a441", label="people within 300 m per km")
    ax2 = ax.twiny()
    ax2.barh(np.arange(n) + 0.17, c.exposure_per_km, height=0.32, color="#b8491c", label="exposure per km")
    ax.set_yticks([])
    ax.set_ylim(n - 0.5, -0.5)
    style(ax)
    ax2.tick_params(colors="#b8491c", labelsize=8.5, length=0)
    for s_ in ax2.spines.values():
        s_.set_visible(False)
    ax.set_xlabel("people within 300 m per km", fontsize=9, color="#a07a2c")
    ax2.set_xlabel("exposure per km", fontsize=9, color="#b8491c")
    ax = fig.add_subplot(gs[1, :])
    st = SST[SST.corridor.isin(roads.index)].nlargest(12, "exposure").iloc[::-1]
    lab = [f"{p if isinstance(p, str) else 'unnamed'} · {roads.lab[c_].replace('→ ', 'to ')}, km {a:.0f}–{b:.0f}"
           for p, c_, a, b in zip(st.place, st.corridor, st.km_from, st.km_to)]
    ax.barh(range(len(st)), st.exposure, color=[TYPE_COL.get(t, GRID) for t in st.road_type], edgecolor=INK2,
            linewidth=0.4)
    for i, r in enumerate(st.itertuples()):
        ax.text(r.exposure, i, f"  {r.people_300m:,.0f} people · trucks {r.truck_kmh:.0f} km/h · {r.schools} schools",
                va="center", fontsize=8.5, color=INK)
    ax.set_yticks(range(len(st)))
    ax.set_yticklabels(lab, fontsize=9, color=INK)
    ax.set_xlim(0, st.exposure.max() * 1.6)
    style(ax)
    ax.set_title("The twelve 2 km stretches with the most exposure (colour: road type)", loc="left", fontsize=11,
                 color=INK)
    ax.legend(handles=[Patch(color=c_, label=k) for k, c_ in TYPE_COL.items()], loc="lower right", frameon=False,
              fontsize=9)
    header(fig, country, "where fast trucks pass people", "Exposure = people within 300 m × trucks × (truck speed/50)⁴ "
           "(19_safety.py); population GHS-POP 2025; one assumed truck count for every road.")
    save(fig, "08_safety.png", f"countries/{iso}")


def f09_fuel(country, iso, roads):
    n = len(roads)
    fig, axs = plt.subplots(1, 2, figsize=(15, 0.5 * n + 2.8), facecolor=SURF, sharey=True,
                            gridspec_kw=dict(wspace=0.06))
    m = FBC[FBC.corridor.isin(roads.index)].pivot(index="corridor", columns="cause", values="litres").reindex(roads.index)
    m = m[[k for k in CAUSES if k in m]].div(roads.km_, axis=0) * 100
    tot = stacked(axs[0], m, CAUSE_COL, roads, fmt="{:.1f}", min_label=0.08)
    net = m.sum(axis=1)
    axs[0].scatter(net, range(n), marker="|", s=250, color=INK, zorder=5)
    for i, v in enumerate(net):
        axs[0].text(tot[i] + 0.2, i, f"{v:.1f} L", va="center", fontsize=9, color=INK, fontweight="bold")
    style(axs[0])
    axs[0].axvline(0, color=INK2, lw=0.6)
    axs[0].set_title("Extra diesel per 100 km per loaded truck, by cause (| net)", loc="left", fontsize=11, color=INK)
    f = FU[(FU.direction == "outbound") & FU.corridor.isin(roads.index)].set_index("corridor").reindex(roads.index)
    axs[1].barh(range(n), f.friction_co2_kt_year, color="#5d6764", height=0.6)
    axs[1].errorbar(f.friction_co2_kt_year, range(n), xerr=[f.friction_co2_kt_year - f.friction_co2_kt_year_p5,
                                                            f.friction_co2_kt_year_p95 - f.friction_co2_kt_year],
                    fmt="none", ecolor=INK2, elinewidth=0.7, capsize=2)
    for i, r in enumerate(f.itertuples()):
        axs[1].text(r.friction_co2_kt_year_p95 * 1.02, i, f" {r.friction_litres_year_m:.1f} M L · "
                    f"${r.friction_fuel_usd_year_m:.1f} M · {r.friction_pct_of_trip_fuel:.0f}% of trip fuel",
                    va="center", fontsize=8.5, color=INK)
    axs[1].set_xlim(0, f.friction_co2_kt_year_p95.max() * 1.9)
    style(axs[1])
    axs[1].set_title("Extra CO₂ a year, kt (5–95%), with litres and fuel bill", loc="left", fontsize=11, color=INK)
    fig.legend(handles=[Patch(color=c_, label=k) for k, c_ in CAUSE_COL.items()], loc="lower center", ncol=5,
               frameon=False, fontsize=9, bbox_to_anchor=(0.5, -0.02))
    fig.subplots_adjust(top=top(fig, 0.2), bottom=1.0 / fig.get_figheight())
    header(fig, country, "the diesel and carbon the roadside costs", "Physical fuel model of every slow-down and "
           "re-acceleration against open road (26_fuel_co2.py). Hills and curves can be negative: slower is "
           "thriftier. Yearly totals use one assumed truck count.")
    save(fig, "09_fuel_co2.png", f"countries/{iso}")


def f10_waterfall(country, iso, roads):
    n = len(roads)
    cols = 2 if n > 3 else 1
    rows = int(np.ceil(n / cols))
    fig, axs = plt.subplots(rows, cols, figsize=(15, 3.3 * rows + 1.4), facecolor=SURF, squeeze=False,
                            gridspec_kw=dict(hspace=0.55, wspace=0.45))
    t_all = TOT[(TOT.vehicle == "truck") & (TOT.direction == "outbound")].set_index("corridor")
    xmax = t_all.minutes.reindex(roads.index).max() * 1.12
    for ax, (name, a) in zip(axs.ravel(), roads.iterrows()):
        t = t_all.loc[name]
        c = CA[(CA.corridor == name) & (CA.vehicle == "truck") & (CA.direction == "outbound")
               & (CA.cause != "rain (wet day)")].set_index("cause").minutes
        c = c[c >= 0.5].sort_values(ascending=False)
        overlap = t.minutes - t.open_road_minutes - c.sum()
        steps = [("open road", t.open_road_minutes, "#b8c7c4")] + [(k, v, CAUSE_COL[k]) for k, v in c.items()]
        if abs(overlap) >= 0.5:
            steps.append(("overlap", overlap, "#e4e3df"))
        left, labels = 0.0, []
        for i, (k, v, col) in enumerate(steps):
            ax.barh(i, v, left=left if i else 0, color=col, height=0.7, linewidth=0)
            ax.text((left if i else 0) + max(v, 0) + xmax * 0.01, i, f"+{v:.0f}" if i else f"{v:.0f}", va="center",
                    fontsize=8, color=INK)
            left = left + v if i else v
            labels.append(k)
        ax.barh(len(steps), t.minutes, color="#17252a", height=0.7)
        ax.text(t.minutes + xmax * 0.01, len(steps), f"{t.minutes:.0f} min", va="center", fontsize=8.5, color=INK,
                fontweight="bold")
        labels.append("modelled trip")
        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels, fontsize=8, color=INK)
        ax.invert_yaxis()
        ax.set_xlim(0, xmax)
        style(ax)
        ax.set_title(f"{a.lab} · {a.km_:.0f} km: +{t.minutes - t.open_road_minutes:.0f} min "
                     f"(+{t.minutes / t.open_road_minutes - 1:.0%})", loc="left", fontsize=10, color=INK)
    for ax in axs.ravel()[n:]:
        ax.set_visible(False)
    fig.subplots_adjust(top=top(fig, 0.1), bottom=0.04)
    header(fig, country, "how a truck trip grows, cause by cause", "Each bar starts where the one above ends; "
           "causes are measured one at a time, so the grey bar balances the overlap. One scale for all roads.")
    save(fig, "10_waterfall.png", f"countries/{iso}")


def f11_rank(country, iso, roads):
    n = len(roads)
    fig, axs = plt.subplots(1, 2, figsize=(15, 0.5 * n + 2.6), facecolor=SURF, sharey=True,
                            gridspec_kw=dict(wspace=0.06))
    for ax, veh in zip(axs, ("truck", "car")):
        d = RS[(RS.vehicle == veh)].pivot_table(index="corridor", columns="cause",
                                                values="share_first").reindex(roads.index).fillna(0)
        d = d[[k for k in CAUSES if k in d and d[k].max() > 0]]
        stacked(ax, d, CAUSE_COL, roads, fmt="{:.0%}", min_label=0.1)
        ax.set_xlim(0, 1)
        ax.xaxis.set_major_formatter(mtick.PercentFormatter(1))
        style(ax, grid=None)
        ax.set_title(f"{veh}: which cause adds the most minutes?", loc="left", fontsize=11, color=INK)
    fig.legend(handles=[Patch(color=c_, label=k) for k, c_ in CAUSE_COL.items()], loc="lower center", ncol=5,
               frameon=False, fontsize=9, bbox_to_anchor=(0.5, -0.02))
    fig.subplots_adjust(top=top(fig, 0.2), bottom=1.0 / fig.get_figheight())
    header(fig, country, "how sure is the ranking of causes?", "Share of 1,000 Monte Carlo draws of every assumption "
           "in which each cause is the largest.")
    save(fig, "11_rank_stability.png", f"countries/{iso}")


def f12_strips(country, iso, roads):
    n = len(roads)
    P = PT[PT.corridor.isin(roads.index)].merge(TTP[["corridor", "piece", "truck_excess_min"]]).merge(
        GP[["corridor", "piece", "built_ha_2000", "built_ha_2020"]], how="left")
    kmax = roads.km_.max()
    own = kmax > 2.5 * roads.km_.median()   # one very long road: give each its own scale
    fig, axs = plt.subplots(n, 1, figsize=(15, 1.9 * n + 1.8), facecolor=SURF, sharex=not own, squeeze=False)
    axs = axs[:, 0]
    for ax, (name, a) in zip(axs, roads.iterrows()):
        d = P[P.corridor == name].sort_values("km_start")
        x = d.km_start.to_numpy()
        g = (d.built_ha_2020 - d.built_ha_2000).groupby(np.floor(x / 2) * 2).sum()
        ax.bar(g.index + 1, g / g.max() * 0.9 if g.max() > 0 else g, bottom=2.3, width=2, color="#8a6b4e",
               linewidth=0)
        for k, col in TYPE_COL.items():
            m = (d.road_type == k).to_numpy()
            ax.bar(x[m] + 0.25, np.full(m.sum(), 0.45), bottom=1.65, width=0.5, color=col, linewidth=0)
        ax.bar(x + 0.25, np.full(len(x), 0.55), bottom=0.9, width=0.5,
               color=DCMAP(DNORM(d.truck_excess_min / 0.5)), linewidth=0)
        for col_, mk, c_ in (("weighbridges", "s", "#17252a"), ("police_posts", "v", "#4e7c8a"),
                             ("signals", "o", "#9fb3b0")):
            m = (d[col_] > 0).to_numpy()
            ax.scatter(x[m] + 0.25, np.full(m.sum(), 0.55), marker=mk, s=28 if mk == "s" else 16, color=c_,
                       edgecolor="white", linewidth=0.4, zorder=3)
        kx = a.km_ if own else kmax
        hs = H[H.corridor == name].sort_values("truck_excess_min", ascending=False)
        chosen = []
        for r in hs.itertuples():
            if all(abs(r.km_from - c.km_from) > kx * 0.12 for c in chosen):
                chosen.append(r)
            if len(chosen) == 4:
                break
        for r in chosen:
            k = (r.km_from + r.km_to) / 2
            ax.text(k, 0.12, r.place_name, fontsize=7.5, color=INK, ha="center", va="center")
            ax.plot([k, k], [0.25, 0.88], color=INK2, linewidth=0.5)
        ax.set_ylim(-0.1, 3.3)
        ax.set_xlim(-kx * 0.01, kx * 1.01)
        ax.set_yticks([0.55, 1.175, 1.875, 2.75])
        ax.set_yticklabels(["controls", "truck delay", "road type", "new building"], fontsize=8, color=INK2)
        style(ax, grid=None)
        if not own:
            ax.spines["bottom"].set_visible(False)
        ax.set_title(f"{a.lab} · {a.km_:.0f} km", loc="left", fontsize=10.5, color=INK)
    axs[-1].set_xlabel("km from the hub", fontsize=9, color=INK2)
    axs[-1].spines["bottom"].set_visible(True)
    leg = [Line2D([], [], color=c, linewidth=8, label=k) for k, c in TYPE_COL.items()]
    leg += [Line2D([], [], color=DCMAP(i), linewidth=8, label=f"{l} min/km") for i, l in enumerate(DELAY_LABELS)]
    leg += [Line2D([], [], marker=m, color="w", markerfacecolor=c, markersize=7, label=lab)
            for m, c, lab in (("s", "#17252a", "weighbridge"), ("v", "#4e7c8a", "police post"),
                              ("o", "#9fb3b0", "signals"))]
    fig.legend(handles=leg, loc="lower center", ncol=6, frameon=False, fontsize=8.5, labelcolor=INK2,
               bbox_to_anchor=(0.5, 0.0))
    fig.subplots_adjust(top=top(fig, 0.1), bottom=1.3 / fig.get_figheight(), hspace=0.45)
    header(fig, country, "the roads as lines", ("Each road on its own km scale (lengths differ widely). " if own
           else "One km scale for all roads. ") + "Top band: new built-up land within 300 m, "
           "2000–2020, scaled per road. Truck delay: minutes lost per km against open road. Named: worst stretches.")
    save(fig, "12_strip_maps.png", f"countries/{iso}")


for country, iso in ISO.items():
    roads = roads_in(country)
    for f in (f01_typology, f02_growth, f03_causes, f04_hotspots, f05_scenarios, f06_costs, f07_reliability,
              f08_safety, f09_fuel, f10_waterfall, f11_rank, f12_strips):
        f(country, iso, roads)


# ====================================================================== comparisons between countries
ORDER = [c for c in ISO if c in set(ART.country)]
ORDER = sorted(ORDER, key=lambda c: (ART[ART.country == c].region.iloc[0] != "East", c))
CMP["country_"] = CMP.country.map(lambda c: SHORT.get(c, c))
LAB = [SHORT.get(c, c) for c in ORDER]
FU_O = FU[FU.direction == "outbound"].set_index("corridor")
REL = RE[RE.vehicle == "truck"].set_index("corridor")
CMP = CMP.set_index("corridor")
CMP["fuel_l_100km"] = FBC.groupby("corridor").litres.sum() / KM * 100
CMP["co2_t_per_km_year"] = FU_O.friction_co2_kt_year * 1000 / KM
CMP["buffer_pct"] = REL.buffer_index * 100
CMP["cost_usd_100km"] = CO[CO.vehicle == "truck"].set_index("corridor").cost_per_trip_usd / KM * 100
sv = SC[(SC.vehicle == "truck") & (SC.scenario == "all")].set_index("corridor").minutes_saved
CMP["fix_share"] = sv / (CMP.truck_min_per_100km * KM / 100) * 100
CMP = CMP.reset_index()


def dots(ax, col, xlabel, fmt="{:.0f}"):
    rng = np.random.default_rng(1)
    for i, c in enumerate(ORDER):
        d = CMP[CMP.country == c]
        col_ = EAST if d.region.iloc[0] == "East" else SOUTH
        med = d[col].median()
        ax.barh(i, med, color=col_, alpha=0.18, height=0.7, linewidth=0)
        ax.scatter(d[col], i + rng.uniform(-0.22, 0.22, len(d)), s=np.where(d.trade, 70, 34), color=col_,
                   edgecolor=np.where(d.trade, INK, "white"), linewidth=np.where(d.trade, 1.1, 0.5), zorder=3)
        ax.text(med, i - 0.42, fmt.format(med), ha="center", va="bottom", fontsize=8, color=INK)
    ax.set_yticks(range(len(ORDER)))
    ax.set_yticklabels(LAB, fontsize=10, color=INK)
    ax.set_ylim(len(ORDER) - 0.5, -0.6)
    style(ax)
    ax.set_xlabel(xlabel, fontsize=9.5, color=INK2)


KEY = [Line2D([], [], marker="o", ls="none", color=EAST, markersize=7, label="East African road"),
       Line2D([], [], marker="o", ls="none", color=SOUTH, markersize=7, label="Southern African road"),
       Line2D([], [], marker="o", ls="none", color="white", markeredgecolor=INK, markersize=9, label="trade corridor"),
       Patch(color=INK2, alpha=0.25, label="country median (value printed)")]
SPECS = [
    ("k01_delay", [("truck_min_per_100km", "truck minutes lost per 100 km", "{:.0f}"),
                   ("car_min_per_100km", "car minutes lost per 100 km", "{:.0f}")],
     "Time lost, country by country"),
    ("k02_roadside", [("settlement_share", "share in roadside settlement or town", "{:.0%}"),
                      ("buildings_100m_per_km", "buildings within 100 m per km", "{:.0f}")],
     "How built-up the roadside is"),
    ("k03_growth", [("growth_2000_2020", "growth of built-up land within 300 m, 2000–2020", "{:.0%}"),
                    ("controls_per_100km", "controls mapped in OSM per 100 km", "{:.0f}")],
     "Growth, and controls as mapped"),
    ("k04_safety", [("people_per_km", "people within 300 m per km", "{:,.0f}"),
                    ("exposure_per_km", "exposure per km", "{:.2f}")],
     "Road safety exposure"),
    ("k05_fuel_co2", [("fuel_l_100km", "extra diesel, L per 100 km per loaded truck", "{:.1f}"),
                      ("co2_t_per_km_year", "extra CO₂, t per km of road a year", "{:.0f}")],
     "Extra fuel and carbon"),
    ("k06_cost_reliability", [("cost_usd_100km", "lost-time cost, US$ per 100 km per truck", "{:.0f}"),
                              ("buffer_pct", "buffer index for rain, %", "{:.1f}")],
     "Cost and reliability"),
    ("k07_fixes", [("fix_share", "share of truck delay removed by all fixes together, %", "{:.0f}"),
                   ("dual_share", "share of road that is dual carriageway", "{:.0%}")],
     "How much the fixes could recover"),
]
for name, panels, title in SPECS:
    fig, axs = plt.subplots(1, 2, figsize=(15, 6.2), facecolor=SURF, sharey=True, gridspec_kw=dict(wspace=0.08))
    for ax, (col, xl, fmt) in zip(axs, panels):
        dots(ax, col, xl, fmt)
        if "%}" in fmt:
            ax.xaxis.set_major_formatter(mtick.PercentFormatter(1))
    fig.legend(handles=KEY, loc="lower center", ncol=4, frameon=False, fontsize=9.5, bbox_to_anchor=(0.5, -0.03))
    fig.subplots_adjust(top=0.86, bottom=0.17)
    fig.text(0.01, 0.97, title, fontsize=16, fontweight="bold", color=INK, va="top")
    fig.text(0.01, 0.915, "One dot per road leaving the country's hubs; East African countries first. Caveats: OSM "
             "mapping of controls is far denser in South Africa; truck counts are one assumed level.", fontsize=9.5,
             color=INK2, va="top")
    save(fig, f"{name}.png", "compare")

# k08 cause mix per country: share of truck minutes by cause
fig, ax = plt.subplots(figsize=(15, 6.0), facecolor=SURF)
c = CA[(CA.vehicle == "truck") & (CA.direction == "outbound") & (CA.cause != "rain (wet day)")].copy()
c["country"] = c.corridor.map(ART.country)
m = c.groupby(["country", "cause"]).minutes.sum().unstack().reindex(ORDER)
m = m[[k for k in CAUSES if k in m]].clip(lower=0)
m = m.div(m.sum(axis=1), axis=0)
roads_ = pd.DataFrame({"lab": LAB}, index=ORDER)
stacked(ax, m, CAUSE_COL, roads_, fmt="{:.0%}", min_label=0.06)
ax.set_xlim(0, 1)
ax.xaxis.set_major_formatter(mtick.PercentFormatter(1))
style(ax, grid=None)
fig.legend(handles=[Patch(color=c_, label=k) for k, c_ in CAUSE_COL.items()], loc="lower center", ncol=5,
           frameon=False, fontsize=9.5, bbox_to_anchor=(0.5, -0.03))
fig.subplots_adjust(top=0.86, bottom=0.17)
fig.text(0.01, 0.97, "What slows trucks, country by country", fontsize=16, fontweight="bold", color=INK, va="top")
fig.text(0.01, 0.915, "Share of all truck minutes lost on the country's roads, by cause (dry day, leaving the hubs).",
         fontsize=9.5, color=INK2, va="top")
save(fig, "k08_cause_mix.png", "compare")

# k09 road type mix per country (km-weighted)
fig, ax = plt.subplots(figsize=(15, 5.2), facecolor=SURF)
t = TY.assign(country=TY.corridor.map(ART.country)).groupby(["country", "road_type"]).km.sum().unstack().reindex(ORDER)
t = t[list(TYPE_COL)].div(t.sum(axis=1), axis=0)
stacked(ax, t, TYPE_COL, roads_, fmt="{:.0%}", min_label=0.05)
ax.set_xlim(0, 1)
ax.xaxis.set_major_formatter(mtick.PercentFormatter(1))
style(ax, grid=None)
fig.legend(handles=[Patch(color=c_, label=k) for k, c_ in TYPE_COL.items()], loc="lower center", ncol=3,
           frameon=False, fontsize=9.5, bbox_to_anchor=(0.5, -0.03))
fig.subplots_adjust(top=0.84, bottom=0.17)
fig.text(0.01, 0.97, "How much of each country's roads runs through settlement", fontsize=16, fontweight="bold",
         color=INK, va="top")
fig.text(0.01, 0.905, "Share of road length by type, all roads leaving the country's hubs.", fontsize=9.5, color=INK2,
         va="top")
save(fig, "k09_road_types.png", "compare")
