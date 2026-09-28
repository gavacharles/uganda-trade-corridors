"""Animations (GIF) for the corridors study.

  figures/a2_corridor_race.gif    a loaded truck leaves Kampala on every corridor at once, against
                                  a ghost truck on open road; roads light up with their delay as
                                  the truck passes, with minutes lost so far
  figures/a3_bottleneck_tour.gif  one frame per numbered hotspot: where it is, and the close-up

Roadside growth animations (observed and projected) are in 15_growth_animations.py.

Run after 11_maps.py.
"""
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.collections import LineCollection

import config as C
import maplib as M
from maplib import INK, INK2, SURF, K

OUT = C.FIGURES

# ---------------------------------------------------------------- a2 corridor race
STEP = 5  # minutes per frame
fig, ax = plt.subplots(figsize=(9, 9.6), facecolor=SURF)
M.base(ax)
M.context_labels(ax)
M.town_labels(ax, ["Kampala", "Jinja", "Tororo", "Gulu", "Masaka", "Mbarara", "Kabale", "Hoima"], size=8)
M.border_marks(ax, size=7)
K.furniture(ax, km=100)
M.delay_key(fig, ax)
runs = []
for i, corridor in enumerate(C.CORRIDORS):
    d = M.pieces[M.pieces.corridor == corridor].sort_values("km_mid").reset_index(drop=True)
    M.cl.loc[[corridor]].plot(ax=ax, aspect=None, color="#c9c5bc", linewidth=2.4, zorder=4)
    segs = [np.asarray(g.coords) for g in d.geometry]
    cols = M.DELAY_CMAP(M.DELAY_NORM(d.truck_min_per_km.to_numpy()))
    lc = LineCollection(segs, colors=cols, linewidths=3.6, zorder=6)
    lc.set_alpha(None)
    ax.add_collection(lc)
    t_real = np.concatenate([[0], np.cumsum(d.truck_outbound_min)])
    t_open = np.concatenate([[0], np.cumsum(d.truck_outbound_min - d.truck_excess_min)])
    km = np.concatenate([[0], d.km_start + 0.5]).clip(max=M.cl.loc[corridor, "km"])
    line_utm = gpd.GeoSeries([M.cl.loc[corridor].geometry], crs=4326).to_crs(C.UTM).iloc[0]
    grid_km = np.arange(0, line_utm.length / 1000 + 0.1, 0.1)
    ll = gpd.GeoSeries([line_utm.interpolate(k * 1000) for k in grid_km], crs=C.UTM).to_crs(4326)
    lon, lat = ll.x.to_numpy(), ll.y.to_numpy()
    ghost, = ax.plot([], [], "o", markersize=9, markerfacecolor="white", markeredgecolor="#8d8a82",
                     markeredgewidth=1.5, zorder=13)
    truck, = ax.plot([], [], "o", markersize=10, color=M.COL[corridor], markeredgecolor=INK, markeredgewidth=1.4,
                     zorder=14)
    txt = fig.text(0.1, 0.105 - i * 0.022, "", fontsize=9, color=INK, family="monospace")
    runs.append(dict(corridor=corridor, lc=lc, cols=cols, t_real=t_real, t_open=t_open, km=km, grid_km=grid_km,
                     lon=lon, lat=lat, ghost=ghost, truck=truck, txt=txt, n=len(d)))
tmax = max(r["t_real"][-1] for r in runs)
TT = np.concatenate([np.arange(0, tmax + STEP, STEP), np.full(20, tmax + STEP)])
clock = ax.text(0.97, 0.03, "", transform=ax.transAxes, ha="right", va="bottom", fontsize=18, color=INK, zorder=20,
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#d8d5ce"))
fig.text(0.1, 0.965, "Leaving Kampala: a loaded truck on each corridor", fontsize=15, color=INK)
fig.text(0.1, 0.93, "Coloured dot: modelled truck. White dot: the same truck on open road.\nRoads colour in with "
         "minutes lost per km as the truck passes. Light traffic; congestion not modelled.", fontsize=8.5, color=INK2)


def pos(r, t, key):
    k = np.interp(t, r[key], r["km"])
    j = np.searchsorted(r["grid_km"], k).clip(max=len(r["grid_km"]) - 1)
    return r["lon"][j], r["lat"][j], k


def frame_a2(f):
    t = TT[f]
    clock.set_text(f"{int(t // 60)} h {int(t % 60):02d} min")
    for r in runs:
        x, y, k = pos(r, t, "t_real")
        gx, gy, gk = pos(r, t, "t_open")
        r["truck"].set_data([x], [y])
        r["ghost"].set_data([gx], [gy])
        done = r["t_real"][1:] <= t
        cols = r["cols"].copy()
        cols[~done, 3] = 0
        r["lc"].set_color(cols)
        lost = t - np.interp(k, r["km"], r["t_open"]) if t < r["t_real"][-1] else r["t_real"][-1] - r["t_open"][-1]
        arrived = "arrived" if t >= r["t_real"][-1] else f"km {k:5.0f}"
        r["txt"].set_text(f"{C.CORRIDORS[r['corridor']]['short']:<7} {arrived:<9}  lost so far {lost:4.0f} min")
    return []


FuncAnimation(fig, frame_a2, frames=len(TT)).save(os.path.join(OUT, "a2_corridor_race.gif"),
                                                  writer=PillowWriter(fps=10), dpi=90)
plt.close(fig)
print("wrote a2_corridor_race.gif")

# ---------------------------------------------------------------- a3 bottleneck tour
sel = pd.read_csv(os.path.join(C.OUTPUTS, "hotspots_mapped.csv"))
fig = plt.figure(figsize=(13, 7), facecolor=SURF)


def frame_a3(i):
    fig.clf()
    r = sel.iloc[i]
    axl = fig.add_axes([0.02, 0.08, 0.36, 0.8])
    axr = fig.add_axes([0.42, 0.3, 0.56, 0.6])
    M.base(axl, districts_on=False)
    for corridor in C.CORRIDORS:
        M.delay_line(axl, corridor, lw=2)
    axl.plot(sel.lon, sel.lat, "o", markersize=6, color="white", markeredgecolor=INK, zorder=12)
    axl.plot(r.lon, r.lat, "o", markersize=16, color="#eb6834", markeredgecolor=INK, markeredgewidth=1.5, zorder=13)
    M.town_labels(axl, ["Kampala", "Gulu", "Mbarara", "Hoima", "Tororo"], size=7)
    pl = f" · {r.place}" if isinstance(r.place, str) and r.place else ""
    M.closeup(axr, r.corridor, r.lon, r.lat, 0.018, 7.3 / 0.036,
              f"{r.n}. {C.CORRIDORS[r.corridor]['label']}, km {r.km_from:.0f}–{r.km_to:.0f}{pl}",
              M.hotspot_info(r))
    fig.text(0.02, 0.95, f"Bottleneck tour · {int(r.n)} of {len(sel)}", fontsize=15, color=INK)
    fig.text(0.02, 0.03, "Buildings: Google Open Buildings v3. Roads, controls, water: OpenStreetMap. Corridor colour: "
             "truck minutes lost per km (model).", fontsize=8, color=INK2)
    return []


FuncAnimation(fig, frame_a3, frames=len(sel)).save(os.path.join(OUT, "a3_bottleneck_tour.gif"),
                                                   writer=PillowWriter(fps=0.4), dpi=90)
plt.close(fig)
print("wrote a3_bottleneck_tour.gif")
