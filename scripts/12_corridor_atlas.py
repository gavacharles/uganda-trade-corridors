"""One detailed sheet per corridor: figures/m05_atlas_<corridor>.png.

  - map: the corridor coloured by minutes a truck loses per km, its ten worst 2 km
    stretches numbered, police posts and weighbridges, towns, km markers, border crossing
  - long profile: minutes lost per km along the road (truck and car), hotspot numbers,
    police posts and weighbridges, and the road-type ribbon underneath
  - close-ups of the three worst stretches (4 km windows: buildings, every OSM road,
    water, controls)
  - table: all ten stretches with their main causes (minutes, car + truck)

Run after 11_maps.py (uses maplib and outputs/hotspots.csv).
"""
import os
import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator

import config as C
import maplib as M
from maplib import INK, INK2, SURF, K

HALF = 0.016
for corridor, cfg in C.CORRIDORS.items():
    L = M.cl.loc[corridor, "km"]
    hs = M.hot[M.hot.corridor == corridor].copy()
    hs["total"] = hs.car_excess_min + hs.truck_excess_min
    hs = hs.sort_values("km_from").reset_index(drop=True)
    hs["n"] = np.arange(1, len(hs) + 1)
    hs[["lon", "lat"]] = [M.hotspot_point(corridor, (a + b) / 2) for a, b in zip(hs.km_from, hs.km_to)]
    d = M.pieces[M.pieces.corridor == corridor].sort_values("km_mid")

    fig = plt.figure(figsize=(17, 14.5), facecolor=SURF)
    gs = GridSpec(3, 2, figure=fig, width_ratios=[2.1, 0.9], height_ratios=[1, 1, 0.62], wspace=0.08, hspace=0.28,
                  left=0.04, right=0.98, top=0.9, bottom=0.2)
    axm = fig.add_subplot(gs[0:2, 0])
    right = gs[0:3, 1].subgridspec(3, 1, hspace=0.95)
    axp = fig.add_subplot(gs[2, 0])

    # ------------------------------------------------ map
    bb = gpd.GeoSeries([M.cl.loc[corridor].geometry], crs=4326).total_bounds
    ext = M.fit_extent(bb, 11.2, 8.4, pad=0.06)
    M.base(axm, ext)
    M.context_labels(axm)
    for other in C.CORRIDORS:
        if other != corridor:
            M.cl.loc[[other]].plot(ax=axm, aspect=None, color="#b9b5ab", linewidth=1.6, zorder=4)
    M.delay_line(axm, corridor, lw=4.4)
    line_utm = gpd.GeoSeries([M.cl.loc[corridor].geometry], crs=4326).to_crs(C.UTM).iloc[0]
    near = M.fpts[M.fpts.mkind.isin(["police_post", "weighbridge"])].to_crs(C.UTM)
    near = near[near.distance(line_utm) <= np.where(near.mkind == "weighbridge", 150, 30)].to_crs(4326)
    for k, (m, _) in M.MARK.items():
        q = near[near.mkind == k]
        axm.scatter(q.geometry.x, q.geometry.y, marker=m, s=38 if k == "police_post" else 70, color="white",
                    edgecolor=INK, linewidth=1.2, zorder=11)
    for km in range(50, int(L), 50):
        x, y = M.hotspot_point(corridor, km)
        axm.plot(x, y, "o", markersize=3, color=INK, zorder=9)
        axm.annotate(f"{km} km", (x, y), xytext=(-4, -4), textcoords="offset points", ha="right", va="top",
                     fontsize=7, color=INK2, zorder=9)
    M.numbered_markers(axm, hs.lon.to_numpy(), hs.lat.to_numpy(), hs.n.to_numpy())
    M.town_labels(axm, list(M.TOWNS), size=8, extent=ext)
    M.border_marks(axm)
    # Arrow and legend go in corners that neither end of the corridor occupies
    ends = [cfg["start"], cfg["end"]]
    def corner(e):
        return ("upper" if e[1] > (ext[2] + ext[3]) / 2 else "lower") + (" right" if e[0] > (ext[0] + ext[1]) / 2 else " left")
    busy = {corner(e) for e in ends}
    free = [c for c in ("upper right", "upper left", "lower left", "lower right") if c not in busy]
    arrow_at = next((c for c in free if c.startswith("upper")), "upper right")
    bar_at = "lower right" if "lower right" not in busy else "lower left"
    legend_at = next((c for c in ("lower left", "upper left", "lower right", "upper right")
                      if c in free and c not in (arrow_at, bar_at)), "upper center")
    K.scalebar(axm, loc=bar_at)
    K.north_arrow(axm, loc=arrow_at)
    M.delay_key(fig, axm)
    axm.legend(handles=[Line2D([], [], marker="o", linestyle="none", markersize=11, markerfacecolor="white",
                               markeredgecolor=INK, label="worst 2 km stretches (numbered along the road)"),
                        Line2D([], [], marker="D", linestyle="none", markersize=6, markerfacecolor="white",
                               markeredgecolor=INK, label="police post"),
                        Line2D([], [], marker="s", linestyle="none", markersize=8, markerfacecolor="white",
                               markeredgecolor=INK, label="weighbridge"),
                        Line2D([], [], color="#b9b5ab", linewidth=1.6, label="other study corridors")],
               loc=legend_at, frameon=True, facecolor="white", edgecolor="#d8d5ce", framealpha=0.95, fontsize=8,
               labelcolor=INK)

    # ------------------------------------------------ profile
    km = np.floor(d.km_mid).astype(int)
    s = d.groupby(km)[["car_excess_min", "truck_excess_min"]].sum()
    axp.bar(s.index + 0.5, s.truck_excess_min, width=0.95, color="#0d2d57", linewidth=0, label="truck")
    axp.bar(s.index + 0.5, s.car_excess_min, width=0.5, color="#6aa2e0", linewidth=0, label="car")
    top = s.truck_excess_min.max()
    for r in hs.itertuples():
        axp.axvspan(r.km_from, r.km_to, color="#f6b596", alpha=0.45, linewidth=0, zorder=0)
        axp.text((r.km_from + r.km_to) / 2, top * 1.12, str(r.n), ha="center", va="bottom", fontsize=8,
                 fontweight="bold", color=INK)
    for col, m, lab in (("police_posts", "D", "police post"), ("weighbridges", "s", "weighbridge")):
        k = d[d[col] > 0]
        axp.scatter(k.km_mid, np.full(len(k), top * 1.02), marker=m, s=26, color="white", edgecolor=INK, zorder=5)
    axp.set_xlim(0, L)
    axp.set_ylim(0, top * 1.3)
    axp.set_facecolor(SURF)
    for s_ in ("top", "right", "left"):
        axp.spines[s_].set_visible(False)
    axp.spines["bottom"].set_color("#e4e3df")
    axp.grid(axis="y", color="#e4e3df", linewidth=0.6)
    axp.set_axisbelow(True)
    axp.tick_params(colors=INK2, labelsize=8, length=0)
    axp.yaxis.set_major_locator(MaxNLocator(4))
    axp.set_ylabel("minutes lost per km", fontsize=8.5, color=INK2)
    axp.legend(loc="upper right", frameon=False, fontsize=8, labelcolor=INK2, ncol=2, bbox_to_anchor=(1, 1.22))
    axp.set_title("Along the road, from Kampala: minutes lost per km compared with open road (shaded: numbered "
                  "stretches; markers: police posts ◇ and weighbridges □)", loc="left", fontsize=9.5, color=INK)
    rib = axp.inset_axes([0, -0.3, 1, 0.09])
    for t, col in M.TYPE_COL.items():
        q = d[d.road_type == t]
        rib.bar(q.km_mid, 1, width=0.5, color=col, linewidth=0)
    rib.set_xlim(0, L)
    rib.set_yticks([])
    rib.set_xticks([])
    for s_ in rib.spines.values():
        s_.set_visible(False)
    axp.set_xticks(np.arange(0, L, 25 if L < 250 else 50))
    rib.legend(handles=[Patch(color=col, label=t) for t, col in M.TYPE_COL.items()], title="road type",
               title_fontsize=8, loc="center left", bbox_to_anchor=(1.005, 0.5), ncol=1, frameon=False, fontsize=7.5,
               labelcolor=INK2, alignment="left")

    # ------------------------------------------------ close-ups of the three worst
    worst = hs.sort_values("total", ascending=False).head(3)
    for j, r in enumerate(worst.itertuples()):
        ax = fig.add_subplot(right[j])
        pl = f" · {r.place}" if isinstance(r.place, str) and r.place else ""
        M.closeup(ax, corridor, r.lon, r.lat, HALF, 4.6 / (2 * HALF),
                  f"{r.n}. km {r.km_from:.0f}–{r.km_to:.0f}{pl}", M.hotspot_info(r))

    # ------------------------------------------------ table
    rows = [f"{r.n:>2}. km {r.km_from:5.1f}–{r.km_to:5.1f}  {(r.place if isinstance(r.place, str) else '')[:24]:<24}  "
            f"{r.road_type:<19}  truck +{r.truck_excess_min:4.1f}  car +{r.car_excess_min:4.1f}   {r.main_causes}"
            for r in hs.itertuples()]
    fig.text(0.04, 0.135, "The ten worst 2 km stretches (minutes added in light traffic; causes: car + truck minutes)",
             fontsize=10, color=INK)
    fig.text(0.04, 0.122, "\n".join(rows), fontsize=7.6, color=INK, va="top", family="monospace", linespacing=1.4)
    fig.legend(handles=M.CLOSEUP_LEGEND, loc="lower right", ncol=2, frameon=False, fontsize=7.5, labelcolor=INK2,
               bbox_to_anchor=(0.985, 0.02), title="close-ups", title_fontsize=8)

    tot = M.tt[M.tt.corridor == corridor]
    fig.text(0.04, 0.965, cfg["label"], fontsize=18, color=INK)
    fig.text(0.04, 0.94, f"{L:.0f} km · modelled light-traffic time: car {tot.car_outbound_min.sum() / 60:.1f} h, "
             f"truck {tot.truck_outbound_min.sum() / 60:.1f} h · minutes lost to roadside friction, junctions, "
             f"controls and hills: car {tot.car_excess_min.sum():.0f}, truck {tot.truck_excess_min.sum():.0f}",
             fontsize=10.5, color=INK2)
    fig.text(0.04, 0.005, "Sources: OpenStreetMap; Google Open Buildings v3; Copernicus GLO-30; CHIRPS; "
             "travel-time model 10_travel_time.py (assumptions and ranges in the script).", fontsize=8, color=INK2)
    out = os.path.join(C.FIGURES, f"m05_atlas_{corridor}.png")
    fig.savefig(out, dpi=150, facecolor=SURF)
    plt.close(fig)
    print("wrote", out)
