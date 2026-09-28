"""National GIS maps for the corridors study (per-corridor sheets are in 12_corridor_atlas.py).

  figures/m01_study_area.png   Uganda with the four corridors, towns, borders, weighbridges
  figures/m02_bottlenecks.png  corridors coloured by minutes a truck loses per km, numbered hotspots
  figures/m03_hotspots.png     4 km close-ups of the numbered hotspots; one PNG each in figures/hotspots/
  figures/m04_growth.png       the fastest-growing 5 km on each corridor, built-up 2000 and 2000-2020

Run after 10_travel_time.py.
"""
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

import config as C
import maplib as M
from maplib import INK, INK2, SURF, K

for f in os.listdir(os.path.join(C.FIGURES, "hotspots")) if os.path.isdir(os.path.join(C.FIGURES, "hotspots")) else []:
    os.remove(os.path.join(C.FIGURES, "hotspots", f))
os.makedirs(os.path.join(C.FIGURES, "hotspots"), exist_ok=True)
SOURCES = "Sources: OpenStreetMap contributors (ODbL); districts HDX COD-AB; land and lakes from the WorldPop land mask."

# ---------------------------------------------------------------- m01 study area
fig, ax = plt.subplots(figsize=(10, 10.5), facecolor=SURF)
M.base(ax)
M.context_labels(ax)
handles = []
for corridor, cfg in C.CORRIDORS.items():
    M.corridor_line(ax, corridor, M.COL[corridor])
    handles.append(Line2D([], [], color=M.COL[corridor], linewidth=3.5,
                          label=f"{cfg['label']} · {M.cl.loc[corridor, 'km']:.0f} km"))
wb = M.pieces[M.pieces.weighbridges > 0]
ax.scatter(wb.geometry.centroid.x, wb.geometry.centroid.y, marker="s", s=46, color="white", edgecolor=INK,
           linewidth=1.3, zorder=12)
handles += [Line2D([], [], marker="s", linestyle="none", markersize=7, markerfacecolor="white", markeredgecolor=INK,
                   label="weighbridge (OSM)"),
            Line2D([], [], marker="|", linestyle="none", markersize=12, markeredgewidth=3, color=INK,
                   label="border crossing")]
M.town_labels(ax, ["Kampala", "Jinja", "Tororo", "Gulu", "Masaka", "Mbarara", "Kabale", "Hoima", "Luweero",
                   "Karuma", "Iganga"])
M.border_marks(ax)
K.furniture(ax, km=100)
ax.legend(handles=handles, loc="upper left", frameon=True, facecolor="white", edgecolor="#d8d5ce", framealpha=0.95,
          fontsize=8, labelcolor=INK)
fig.text(0.07, 0.94, "Study area: four trade corridors out of Kampala", fontsize=16, color=INK)
fig.text(0.07, 0.918, "Centrelines built from OpenStreetMap routes A1, A6, A2 and A9, Kampala to the border "
         "(or to Hoima)", fontsize=10, color=INK2)
fig.text(0.07, 0.06, SOURCES, fontsize=8, color=INK2)
fig.savefig(os.path.join(C.FIGURES, "m01_study_area.png"), dpi=170, facecolor=SURF, bbox_inches="tight")
plt.close(fig)
print("wrote m01_study_area.png")

# ---------------------------------------------------------------- hotspot selection
# Each corridor's worst 2 km, plus its two worst at least 15 km from Kampala. Numbered in corridor order.
sel = []
for corridor in C.CORRIDORS:
    h = M.hot[M.hot.corridor == corridor].assign(total=lambda d: d.car_excess_min + d.truck_excess_min)
    sel += [h.sort_values("total", ascending=False).head(1), h[h.km_from >= 15].sort_values("total", ascending=False).head(2)]
sel = pd.concat(sel).drop_duplicates(["corridor", "km_from"]).reset_index(drop=True)
sel["n"] = np.arange(1, len(sel) + 1)
pts = [M.hotspot_point(r.corridor, (r.km_from + r.km_to) / 2) for r in sel.itertuples()]
sel["lon"], sel["lat"] = [p[0] for p in pts], [p[1] for p in pts]
sel.to_csv(os.path.join(C.OUTPUTS, "hotspots_mapped.csv"), index=False)


def place(r):
    return f" · {r.place}" if isinstance(r.place, str) and r.place else ""


# ---------------------------------------------------------------- m02 bottleneck map
fig, ax = plt.subplots(figsize=(10, 10.5), facecolor=SURF)
M.base(ax)
M.context_labels(ax)
for corridor in C.CORRIDORS:
    M.delay_line(ax, corridor)
M.numbered_markers(ax, sel.lon.to_numpy(), sel.lat.to_numpy(), sel.n.to_numpy(), size=7.5)
M.town_labels(ax, ["Kampala", "Jinja", "Tororo", "Gulu", "Masaka", "Mbarara", "Kabale", "Hoima"], size=8)
M.border_marks(ax)
K.furniture(ax, km=100)
M.delay_key(fig, ax)
lines = [f"{r.n}. {C.CORRIDORS[r.corridor]['short']} road, km {r.km_from:.0f}–{r.km_to:.0f}{place(r)}: "
         f"truck +{r.truck_excess_min:.1f} min, car +{r.car_excess_min:.1f} min ({r.main_causes})" for r in sel.itertuples()]
fig.text(0.07, 0.07, "\n".join(lines), fontsize=7.4, color=INK, va="top", linespacing=1.45)
fig.text(0.07, 0.94, "Where the corridors lose time", fontsize=16, color=INK)
fig.text(0.07, 0.918, "Modelled minutes a loaded truck loses per km compared with open road; numbered: the worst "
         "2 km stretches (close-ups in m03, per-road sheets in m05)", fontsize=9.5, color=INK2)
fig.savefig(os.path.join(C.FIGURES, "m02_bottlenecks.png"), dpi=170, facecolor=SURF, bbox_inches="tight")
plt.close(fig)
print("wrote m02_bottlenecks.png")

# ---------------------------------------------------------------- m03 hotspot close-ups
HALF = 0.018  # degrees, about 2 km each way
n, cols, panel = len(sel), 3, 4.3
rows = int(np.ceil(n / cols))
fig, axs = plt.subplots(rows, cols, figsize=(cols * panel, rows * panel + 1.6), facecolor=SURF,
                        gridspec_kw=dict(wspace=0.12, hspace=0.75))
axs = np.atleast_1d(axs).ravel()
for ax, r in zip(axs, sel.itertuples()):
    M.closeup(ax, r.corridor, r.lon, r.lat, HALF, panel / (2 * HALF),
              f"{r.n}. {C.CORRIDORS[r.corridor]['short']} road, km {r.km_from:.0f}–{r.km_to:.0f}{place(r)}",
              M.hotspot_info(r))
for ax in axs[n:]:
    ax.set_axis_off()
fig.legend(handles=M.CLOSEUP_LEGEND, loc="lower center", ncol=7, frameon=False, fontsize=8, labelcolor=INK2,
           bbox_to_anchor=(0.5, -0.005))
M.delay_key(fig, axs[cols - 1], "corridor: truck min lost per km")
fig.suptitle("Bottleneck close-ups: 4 km windows around the worst stretches", x=0.125, ha="left", fontsize=16,
             color=INK, y=0.995)
fig.text(0.125, 0.975, "Numbers match m02. Buildings drawn at footprint area. Sources: OpenStreetMap; Google Open "
         "Buildings v3; travel-time model (10_travel_time.py).", fontsize=9, color=INK2)
fig.savefig(os.path.join(C.FIGURES, "m03_hotspots.png"), dpi=150, facecolor=SURF, bbox_inches="tight")
plt.close(fig)
for r in sel.itertuples():
    fig, ax = plt.subplots(figsize=(7.5, 9.2), facecolor=SURF)
    M.closeup(ax, r.corridor, r.lon, r.lat, HALF, 7.5 / (2 * HALF),
              f"{r.n}. {C.CORRIDORS[r.corridor]['short']} road, km {r.km_from:.0f}–{r.km_to:.0f}{place(r)}",
              M.hotspot_info(r))
    K.north_arrow(ax)
    ax.legend(handles=M.CLOSEUP_LEGEND, loc="upper left", bbox_to_anchor=(0, -0.2), ncol=3, frameon=False,
              fontsize=7.5, labelcolor=INK2)
    fig.savefig(os.path.join(C.FIGURES, "hotspots", f"hotspot_{r.n:02d}_{r.corridor}_km{r.km_from:.0f}.png"),
                dpi=170, facecolor=SURF, bbox_inches="tight")
    plt.close(fig)
print(f"wrote m03_hotspots.png and {n} single close-ups")

# ---------------------------------------------------------------- m04 growth close-ups
GH = 0.03  # half window, about 3.3 km
gsel = []
for corridor in C.CORRIDORS:
    g = M.growth[M.growth.corridor == corridor].sort_values("km_mid").reset_index(drop=True)
    w = g.growth_ha_2000_2020.rolling(10, center=True).sum()
    i = int(w.idxmax())
    km = g.km_mid[i]
    lon, lat = M.hotspot_point(corridor, km)
    near = M.typed[(M.typed.corridor == corridor) & M.typed.km_mid.between(km - 2.5, km + 2.5)].place.dropna()
    gsel.append(dict(corridor=corridor, km=km, lon=lon, lat=lat, added_ha=w[i], place=near.mode().iloc[0] if len(near) else ""))
gsel = pd.DataFrame(gsel)
gsel.to_csv(os.path.join(C.OUTPUTS, "growth_hotspots.csv"), index=False)

fig, axs = plt.subplots(1, len(gsel), figsize=(4.2 * len(gsel), 5.4), facecolor=SURF, gridspec_kw=dict(wspace=0.06))
cell_pt = 100 / 111_320 * (4.2 / (2 * GH)) * 72
for ax, r in zip(axs, gsel.itertuples()):
    x0, x1, y0, y1 = r.lon - GH, r.lon + GH, r.lat - GH, r.lat + GH
    K.frame(ax, (x0, x1, y0, y1))
    ax.set_facecolor(M.LAND)
    m = M.ghsl_cells(2000, x0, y0, x1, y1).merge(M.ghsl_cells(2020, x0, y0, x1, y1), on=["lon", "lat"],
                                                 suffixes=("_2000", "_2020"))
    old, new = m[m.v_2000 >= 500], m[(m.v_2020 >= 500) & (m.v_2000 < 500)]
    ax.scatter(old.lon, old.lat, s=cell_pt ** 2, marker="s", color=M.BUILDING, linewidths=0, zorder=2)
    ax.scatter(new.lon, new.lat, s=cell_pt ** 2, marker="s", color="#eb6834", linewidths=0, zorder=3)
    rr = M.froads.cx[x0:x1, y0:y1]
    rr[rr.highway.isin(["trunk", "primary", "secondary", "tertiary"])].plot(ax=ax, aspect=None, color=M.ROAD,
                                                                           linewidth=0.8, zorder=4)
    M.corridor_line(ax, r.corridor, M.COL[r.corridor], lw=2)
    K.scalebar(ax, km=2)
    ax.set_title(f"{C.CORRIDORS[r.corridor]['short']} road, km {r.km:.0f}{' · ' + r.place if r.place else ''}\n"
                 f"+{r.added_ha:.0f} ha built within 300 m, 2000–2020", loc="left", fontsize=9.5, color=INK)
fig.legend(handles=[Patch(color=M.BUILDING, label="built up by 2000"), Patch(color="#eb6834", label="built up 2000–2020"),
                    Line2D([], [], color=INK, linewidth=2.5, label="corridor")],
           loc="lower center", ncol=3, frameon=False, fontsize=9, labelcolor=INK2, bbox_to_anchor=(0.5, -0.03))
fig.suptitle("Where the roadside grew fastest", x=0.125, ha="left", fontsize=16, color=INK, y=1.05)
fig.text(0.125, 0.985, "The 5 km on each corridor with the most new built-up land within 300 m of the road. "
         "Cells at least 5% built. Source: GHSL GHS-BUILT-S R2023A.", fontsize=9, color=INK2)
fig.savefig(os.path.join(C.FIGURES, "m04_growth.png"), dpi=160, facecolor=SURF, bbox_inches="tight")
plt.close(fig)
print("wrote m04_growth.png")
