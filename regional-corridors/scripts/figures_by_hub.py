"""Per-hub sheets for the regional paper: every road in its own panel, so none is lost in a crowd.

    python scripts/figures_by_hub.py

For each of the 12 hubs, in figures/by_hub/:
  <hub>_1_profiles.png     each road from km 0: road type, truck minutes lost per km, built-up land
                           within 300 m in 2000 and 2020, weighbridges, police posts, signals, and
                           its three worst 2 km stretches named
  <hub>_2_causes.png       minutes each cause adds, car and truck, 5-95% whiskers, and a wet day
  <hub>_3_safety_fuel.png  people within 300 m and truck speed along each road; extra diesel per km
  <hub>_4_rain_fixes.png   monthly truck time on each road (mean and bad day), and what each fix saves
These replace the shared scripts' all-roads figures (f02-f10, g01-g03, f16), which cannot be read
with 54 roads.
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from regional_common import (ART, CAUSE_COL, GRID, H, INK, INK2, KM, O, SURF, TYPE_COL, distinct, pieces,
                             save, style)

PT = O("pieces_typed.csv")
GP = O("growth_pieces.csv")
SP = O("safety_pieces.csv")
FP = O("fuel_co2_pieces.csv")
CA = O("travel_time_causes.csv")
RM = O("reliability_monthly.csv")
SC = O("scenarios.csv")
P = (PT.merge(pieces[["corridor", "piece", "per_km", "length_km"]], on=["corridor", "piece"], how="left")
       .merge(GP[["corridor", "piece", "built_ha_2000", "built_ha_2020"]], on=["corridor", "piece"], how="left")
       .merge(SP[["corridor", "piece", "people_300m", "truck_kmh"]], on=["corridor", "piece"], how="left")
       .merge(FP[["corridor", "piece", "friction_litres"]], on=["corridor", "piece"], how="left"))
SUB = "by_hub"
MONTHS = "JFMAMJJASOND"
FIX = {"wim": "Weigh-in-motion", "no_police": "No police stops", "bypass_2": "Bypass 2 worst towns",
       "service_20km": "Service roads, worst 20 km", "service_all": "Service roads, all settlements",
       "all": "All together"}


def roads_of(hub):
    a = ART[ART.hub == hub].copy()
    a["km_"] = KM.reindex(a.index)
    return a.sort_values("km_", ascending=False)


def binned(d, km):
    """Sum the 500 m pieces into km-long steps so long roads stay readable."""
    b = (d.km_mid // km).astype(int)
    g = d.assign(mins=d.per_km * d.length_km).groupby(b)
    out = g[["mins", "length_km", "built_ha_2000", "built_ha_2020", "people_300m"]].sum()
    out["km_mid"] = (out.index + 0.5) * km
    out["road_type"] = g.road_type.agg(lambda t: t.mode().iloc[0])
    out["truck_kmh"] = g.truck_kmh.mean()
    L = out.length_km.clip(lower=0.1)
    out["per_km"], out["built"], out["people"] = out.mins / L, out.built_ha_2000 / L, out.people_300m / L
    out["built20"] = out.built_ha_2020 / L
    return out


def spaced(h, n, gap):
    """The n worst stretches on one road, at least gap km apart so the labels do not collide."""
    keep = []
    for r in h.sort_values("truck_excess_min", ascending=False).itertuples():
        if all(abs(r.km_from - k.km_from) > gap for k in keep):
            keep.append(r)
        if len(keep) == n:
            break
    return keep


def header(fig, hub, what, sub):
    a = ART[ART.hub == hub]
    h = fig.get_figheight()
    fig.text(0.01, 1 - 0.18 / h, f"{a.hub_name.iloc[0]} ({a.country.iloc[0].replace('United Republic of ', '')}): "
             f"{what}", fontsize=16, fontweight="bold", color=INK, va="top")
    fig.text(0.01, 1 - 0.55 / h, sub, fontsize=10, color=INK2, va="top")


def top_rect(fig, bottom=0.0):
    return (0, bottom, 1, 1 - 0.85 / fig.get_figheight())


for hub in ART.hub.unique():
    roads = roads_of(hub)
    n = len(roads)

    # ---------------------------------------------------------------- 1 profiles
    fig, axs = plt.subplots(n, 1, figsize=(15, 2.25 * n + 1.4), facecolor=SURF, squeeze=False)
    for ax, (name, a) in zip(axs[:, 0], roads.iterrows()):
        d = P[P.corridor == name].sort_values("km_mid")
        step = 2 if a.km_ > 150 else 1
        b = binned(d, step)
        top = max(b.per_km.max() * 1.25, 1)
        for t, col in TYPE_COL.items():   # road type as a band under the bars
            m = b.road_type == t
            ax.bar(b.km_mid[m], top * 0.08, bottom=-top * 0.12, width=step, color=col, linewidth=0)
        ax.bar(b.km_mid, b.per_km, width=step * 0.9, color="#b8491c", linewidth=0, alpha=0.85, zorder=2)
        ax2 = ax.twinx()
        hi = max(b.built20.max() * 1.6, 1)
        ax2.set_ylim(-hi * 0.13 / 1.07, hi)   # zero level with the bars' zero, above the road-type band
        ax2.set_yticks([t for t in ax2.get_yticks() if 0 <= t <= hi])
        ax.set_zorder(ax2.get_zorder() + 1)   # draw everything in ax, built-up on ax2's scale
        ax.patch.set_visible(False)
        ax.fill_between(b.km_mid, b.built, color="#9aa7a3", alpha=0.35, lw=0, step="mid", transform=ax2.transData,
                        zorder=1)
        ax.step(b.km_mid, b.built20, where="mid", color="#3d7f8f", lw=1.0, transform=ax2.transData, zorder=3)
        ax2.tick_params(colors=INK2, labelsize=8, length=0)
        for s_ in ax2.spines.values():
            s_.set_visible(False)
        for col_, mk, c in (("weighbridges", "s", "#17252a"), ("police_posts", "D", "#4e7c8a"), ("signals", "|", INK)):
            k = d.km_mid[d[col_] > 0]
            ax.scatter(k, np.full(len(k), top * 1.0), marker=mk, s=28 if mk != "|" else 60, color=c, zorder=5,
                       linewidths=1.2)
        for r in spaced(H[H.corridor == name], 3, a.km_ * 0.14):
            ax.annotate(r.label, ((r.km_from + r.km_to) / 2, top * 0.86), fontsize=8, color=INK, ha="center",
                        va="top", bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=GRID, alpha=0.9))
        ax.set_ylim(-top * 0.13, top * 1.07)
        ax.set_xlim(0, d.km_mid.max() + 1)
        style(ax, grid="y")
        ax.tick_params(axis="y", colors=INK2)
        ax.set_title(f"{a.short}{'  ★ trade corridor' if a.trade else ''} · {a.km_:.0f} km · "
                     f"{(d.per_km * d.length_km).sum() / a.km_ * 100:.0f} truck min lost per 100 km",
                     loc="left", fontsize=11, color=INK)
        ax.set_ylabel("truck min/km", fontsize=8.5, color=INK2)
        ax2.set_ylabel("built ha/km", fontsize=8.5, color=INK2)
    axs[-1, 0].set_xlabel("km from the hub", fontsize=10, color=INK2)
    handles = ([Patch(color="#b8491c", label="truck minutes lost per km")] +
               [Patch(color=c, label=t) for t, c in TYPE_COL.items()] +
               [Patch(color="#9aa7a3", alpha=0.35, label="built-up within 300 m, 2000"),
                Line2D([], [], color="#3d7f8f", lw=1.2, label="2020"),
                Line2D([], [], marker="s", ls="none", color="#17252a", label="weighbridge"),
                Line2D([], [], marker="D", ls="none", color="#4e7c8a", label="police post"),
                Line2D([], [], marker="|", ls="none", color=INK, markersize=9, label="signals")])
    fig.legend(handles=handles, loc="lower center", ncol=5, frameon=False, fontsize=9, bbox_to_anchor=(0.5, -0.01))
    fig.tight_layout(rect=top_rect(fig, 0.6 / fig.get_figheight()))
    header(fig, hub, "every road, km by km", "Bars: truck minutes lost per km against open road (light traffic), in 2 km steps (1 km on roads under 150 km). "
           "Band: road type. Shading and line: built-up land within 300 m (ha per km). Labels: the worst 2 km stretches.")
    save(fig, f"{hub}_1_profiles.png", SUB)

    # ---------------------------------------------------------------- 2 causes
    cols = 2 if n > 1 else 1
    rows = int(np.ceil(n / cols))
    fig, axs = plt.subplots(rows, cols, figsize=(15, 3.3 * rows + 1.2), facecolor=SURF, squeeze=False,
                            sharex=True)
    labels = list(CAUSE_COL) + ["rain (wet day)"]
    vmax = 0
    for ax, (name, a) in zip(axs.ravel(), roads.iterrows()):
        c = CA[(CA.corridor == name) & (CA.direction == "outbound")]
        y = np.arange(len(labels))
        for j, (veh, col) in enumerate((("car", "#86b6ef"), ("truck", "#1c5cab"))):
            v = c[c.vehicle == veh].set_index("cause").reindex(labels)
            ax.barh(y + (j - 0.5) * 0.38, v.minutes, height=0.36, color=col, label=veh, linewidth=0)
            ax.errorbar(v.minutes, y + (j - 0.5) * 0.38, xerr=[(v.minutes - v.p5).clip(lower=0), (v.p95 - v.minutes).clip(lower=0)],
                        fmt="none", ecolor=INK2, elinewidth=0.7, capsize=1.5)
            vmax = max(vmax, np.nanmax(v.p95.to_numpy()))
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=8.5, color=INK)
        ax.invert_yaxis()
        style(ax)
        ax.set_title(f"{a.short}{'  ★' if a.trade else ''} · {a.km_:.0f} km", loc="left", fontsize=10.5, color=INK)
    for ax in axs.ravel()[n:]:
        ax.set_visible(False)
    for ax in axs.ravel()[:n]:
        ax.set_xlim(0, vmax * 1.05)
    fig.legend(*axs.ravel()[0].get_legend_handles_labels(), loc="lower center", ncol=2, frameon=False, fontsize=10,
               bbox_to_anchor=(0.5, -0.005))
    for ax in axs[-1, :]:
        ax.set_xlabel("minutes added leaving the hub (one scale for all panels)", fontsize=9, color=INK2)
    fig.tight_layout(rect=top_rect(fig, 0.35 / fig.get_figheight()))
    header(fig, hub, "what each cause adds", "Central estimate; whiskers 5th–95th percentile of 1,000 draws. "
           "Rain is a wet-day scenario. Controls come from OSM; speed humps are assumed in towns.")
    save(fig, f"{hub}_2_causes.png", SUB)

    # ---------------------------------------------------------------- 3 safety and fuel
    fig, axs = plt.subplots(n, 1, figsize=(15, 2.0 * n + 1.4), facecolor=SURF, squeeze=False)
    for ax, (name, a) in zip(axs[:, 0], roads.iterrows()):
        d = P[P.corridor == name].sort_values("km_mid")
        step = 2 if a.km_ > 150 else 1
        b = binned(d, step)
        ax.bar(b.km_mid, b.people / 1000, width=step * 0.9, color="#d9a441", linewidth=0)
        ax.set_ylim(0, max(b.people.max() / 1000 * 1.15, 0.5))
        ax2 = ax.twinx()
        ax2.step(b.km_mid, b.truck_kmh, where="mid", color=INK, lw=1.0)
        ax2.set_ylim(0, 90)
        ax2.axhline(50, color="#b8491c", lw=0.7, ls=":")
        ax2.tick_params(colors=INK2, labelsize=8, length=0)
        for s_ in ax2.spines.values():
            s_.set_visible(False)
        ex = SP[SP.corridor == name].exposure.sum() / a.km_
        fuel = d.friction_litres.sum() / a.km_ * 100
        ax.set_xlim(0, d.km_mid.max() + 1)
        style(ax, grid="y")
        ax.tick_params(axis="y", colors=INK2)
        ax.set_title(f"{a.short}{'  ★' if a.trade else ''} · {a.km_:.0f} km · exposure {ex:.2f} per km · "
                     f"extra diesel {fuel:.1f} L per 100 km per loaded truck", loc="left", fontsize=10.5, color=INK)
        ax.set_ylabel("'000 people/km", fontsize=8.5, color=INK2)
        ax2.set_ylabel("truck km/h", fontsize=8.5, color=INK2)
    axs[-1, 0].set_xlabel("km from the hub", fontsize=10, color=INK2)
    fig.legend(handles=[Patch(color="#d9a441", label="people living within 300 m (thousands per km)"),
                        Line2D([], [], color=INK, lw=1.2, label="truck running speed (km/h)"),
                        Line2D([], [], color="#b8491c", lw=0.9, ls=":", label="50 km/h")],
               loc="lower center", ncol=3, frameon=False, fontsize=9.5, bbox_to_anchor=(0.5, -0.01))
    fig.tight_layout(rect=top_rect(fig, 0.6 / fig.get_figheight()))
    header(fig, hub, "where fast trucks meet people", "Exposure = people × trucks × (speed/50)⁴ (one assumed truck "
           "count for every road); extra diesel from the physical fuel model against open road.")
    save(fig, f"{hub}_3_safety_fuel.png", SUB)

    # ---------------------------------------------------------------- 4 rain and fixes
    fig, axs = plt.subplots(1, 2, figsize=(15, 0.55 * n + 3.6), facecolor=SURF,
                            gridspec_kw=dict(width_ratios=[1, 1.1], wspace=0.45, top=1 - 1.6 / (0.55 * n + 3.6)))
    ax = axs[0]
    grid_ = np.full((n, 12), np.nan)
    for i, name in enumerate(roads.index):
        m = RM[(RM.corridor == name) & (RM.vehicle == "truck")].set_index("month")
        base = m.mean_min.min()
        grid_[i] = ((m.p95_min.reindex(range(1, 13)) / base - 1) * 100).clip(lower=0)
    im = ax.imshow(grid_, cmap="YlOrBr", aspect="auto", vmin=0, vmax=max(np.nanmax(grid_), 5))
    for i in range(n):
        for j in range(12):
            if not np.isnan(grid_[i, j]):
                ax.text(j, i, f"{grid_[i, j]:.0f}", ha="center", va="center", fontsize=8,
                        color="white" if grid_[i, j] > np.nanmax(grid_) * 0.6 else INK)
    ax.set_xticks(range(12)); ax.set_xticklabels(list(MONTHS), fontsize=9, color=INK2)
    ax.set_yticks(range(n)); ax.set_yticklabels(roads.short, fontsize=9.5, color=INK)
    ax.tick_params(length=0)
    for s_ in ax.spines.values():
        s_.set_visible(False)
    ax.set_title("Bad-rain day (95th percentile) slower than the\nroad's best month, % — truck, 2006–2025",
                 loc="left", fontsize=10.5, color=INK)
    ax = axs[1]
    sc = SC[(SC.vehicle == "truck") & SC.corridor.isin(roads.index)].pivot(index="corridor", columns="scenario",
                                                                           values="minutes_saved")
    sc = sc.reindex(roads.index)[[k for k in FIX if k in sc]]
    y = np.arange(n)
    hgt = 0.8 / len(sc.columns)
    pal = ["#3a7d5c", "#4e7c8a", "#d9a441", "#e8c77e", "#c4532d", INK]
    for j, k in enumerate(sc.columns):
        ax.barh(y - 0.4 + (j + 0.5) * hgt, sc[k], height=hgt * 0.92, color=pal[j % len(pal)], label=FIX[k],
                linewidth=0)
    ax.set_yticks(y); ax.set_yticklabels(roads.short, fontsize=9.5, color=INK)
    ax.invert_yaxis()
    style(ax)
    ax.set_xlabel("truck minutes saved per trip (central estimate)", fontsize=9.5, color=INK2)
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.09 - 0.6 / fig.get_figheight()), ncol=3, frameon=False,
              fontsize=8.5)
    ax.set_title("What each fix saves, leaving the hub", loc="left", fontsize=10.5, color=INK)
    header(fig, hub, "rain and fixes", "Left: from where rain actually fell each day, 2006–2025 (CHIRPS). "
           "Right: the travel-time model with each fix applied; congestion relief is not counted.")
    save(fig, f"{hub}_4_rain_fixes.png", SUB)
