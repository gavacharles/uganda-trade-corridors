"""Roadside growth animations, observed and projected.

Observed (GHSL epochs 2000-2020, mapped from satellite imagery):
  figures/a1_roadside_growth.gif              the fastest-growing 5 km on every corridor
  figures/a4_growth_<corridor>.gif            one per corridor: its three fastest-growing 5 km
                                              (at least 30 km apart) above a profile of the whole road
Projected to end-2026 (the same, continuing on GHSL's 2025 and 2030 epochs, which JRC projects
from the observed trend; end-2026 is interpolated between them):
  figures/a1_roadside_growth_to2026_projected.gif
  figures/a4_growth_<corridor>_to2026_projected.gif

Between epochs, each cell's built-up surface is interpolated linearly by year. A cell counts
as built once it is at least 5% built (500 m2 of its 10,000 m2). In the projected versions,
land built in the projected years is drawn in violet and every frame after 2020 is labelled.

Run after 11_maps.py (uses outputs/growth_hotspots.csv and growth_pieces.csv).
"""
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

import config as C
import maplib as M
from maplib import INK, INK2, SURF, K

EPOCHS = [2000, 2005, 2010, 2015, 2020, 2025, 2030]
LAST_OBSERVED = 2020
BUILT = 500  # m2 per 100 m cell
NEW, PROJ = "#eb6834", "#8a63d2"
GH = 0.03  # half window in degrees, about 3.3 km
MODES = {  # name: (last year shown, output suffix)
    "observed": (2020, ""),
    "projected": (2026, "_to2026_projected"),
}


def years_for(end):
    n = int((end - 2000) * 1.6) + 1
    return np.concatenate([np.full(4, 2000.0), np.linspace(2000, end, n), np.full(10, float(end))])


def at_year(df, yr, prefix="v"):
    """Linear interpolation between epoch columns (prefix + epoch) at a fractional year."""
    i = min(int((yr - 2000) // 5), len(EPOCHS) - 2)
    f = (yr - EPOCHS[i]) / 5
    return df[f"{prefix}{EPOCHS[i]}"] * (1 - f) + df[f"{prefix}{EPOCHS[i + 1]}"] * f


def window_cells(ext):
    cells = None
    for y in EPOCHS:
        c = M.ghsl_cells(y, ext[0], ext[2], ext[1], ext[3]).rename(columns={"v": f"v{y}"})
        cells = c if cells is None else cells.merge(c, on=["lon", "lat"])
    return cells[cells[[f"v{y}" for y in EPOCHS]].max(axis=1) >= BUILT].reset_index(drop=True)


def growth_panel(ax, corridor, lon, lat, title, inch, labels=True):
    """Static layers for one window; returns the animated state (new cells, scatter, counter)."""
    ext = (lon - GH, lon + GH, lat - GH, lat + GH)
    K.frame(ax, ext)
    ax.set_facecolor(M.LAND)
    cells = window_cells(ext)
    rr = M.froads.cx[ext[0]:ext[1], ext[2]:ext[3]]
    rr[rr.highway.isin(["trunk", "primary", "secondary", "tertiary"])].plot(ax=ax, aspect=None, color=M.ROAD,
                                                                           linewidth=0.8, zorder=4)
    M.corridor_line(ax, corridor, M.COL[corridor], lw=2)
    if labels:
        M.place_labels(ax, *ext, n=5, size=7)
    K.scalebar(ax, km=2)
    ax.set_title(title, loc="left", fontsize=9.5, color=INK)
    cps = 100 / 111_320 * (inch / (2 * GH)) * 72
    old = cells["v2000"] >= BUILT
    ax.scatter(cells.lon[old], cells.lat[old], s=cps ** 2, marker="s", color=M.BUILDING, linewidths=0, zorder=2)
    new = cells[~old].reset_index(drop=True)
    sc = ax.scatter(new.lon, new.lat, s=cps ** 2, marker="s", c=np.zeros(len(new)),
                    cmap=ListedColormap([(0, 0, 0, 0), NEW, PROJ]), vmin=0, vmax=2, linewidths=0, zorder=3)
    txt = ax.text(0.02, 0.02, "", transform=ax.transAxes, fontsize=9, color=INK, zorder=10,
                  bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#d8d5ce", alpha=0.92))
    return new, sc, txt


def update_panel(state, yr):
    new, sc, txt = state
    v = at_year(new, yr)
    v_obs = at_year(new, min(yr, LAST_OBSERVED))
    code = np.where(v_obs >= BUILT, 1, np.where(v >= BUILT, 2, 0))
    sc.set_array(code.astype(float))
    txt.set_text(f"+{v[v >= BUILT].sum() / 1e4:,.0f} ha since 2000")


def year_label(yr):
    return f"{yr:.0f}" if yr <= LAST_OBSERVED + 1e-9 else f"{yr:.0f} · projected"


def legend(fig, mode, y=0.015):
    h = [Patch(color=M.BUILDING, label="built up by 2000"), Patch(color=NEW, label="built up 2000–2020 (observed)")]
    if mode == "projected":
        h.append(Patch(color=PROJ, label="built up 2020–2026 (GHSL projection)"))
    fig.legend(handles=h, loc="lower center", ncol=len(h), frameon=False, fontsize=9, labelcolor=INK2,
               bbox_to_anchor=(0.5, y))


def source_line(mode):
    return ("Source: GHSL GHS-BUILT-S R2023A, 5-year epochs interpolated by year."
            + (" 2025 and 2030 epochs are JRC projections; end-2026 is interpolated between them." if mode == "projected"
               else " Observed epochs 2000–2020."))


gsel = pd.read_csv(os.path.join(C.OUTPUTS, "growth_hotspots.csv"))
growth = pd.read_csv(os.path.join(C.OUTPUTS, "growth_pieces.csv"))

for mode, (end, suffix) in MODES.items():
    YRS = years_for(end)

    # ------------------------------------------------ a1: one window per corridor
    fig, axs = plt.subplots(1, len(gsel), figsize=(4.0 * len(gsel), 5.6), facecolor=SURF,
                            gridspec_kw=dict(wspace=0.05, bottom=0.12, top=0.8))
    states = [growth_panel(ax, r.corridor, r.lon, r.lat,
                           f"{C.CORRIDORS[r.corridor]['short']} road, km {r.km:.0f}"
                           f"{' · ' + r.place if isinstance(r.place, str) and r.place else ''}", 4.0, labels=False)
              for ax, r in zip(axs, gsel.itertuples())]
    year_txt = fig.text(0.98, 0.975, "", ha="right", va="top", fontsize=24, color=INK)
    fig.text(0.02, 0.975, "The roadside filling in" + (", with GHSL's projection to end-2026" if mode == "projected" else ""),
             fontsize=15, color=INK, va="top")
    fig.text(0.02, 0.925, "Fastest-growing 5 km on each corridor. " + source_line(mode), fontsize=8.5, color=INK2,
             va="top")
    legend(fig, mode)

    def frame_a1(k, states=states, year_txt=year_txt, YRS=YRS):
        yr = YRS[k]
        year_txt.set_text(year_label(yr))
        year_txt.set_color(PROJ if yr > LAST_OBSERVED else INK)
        for st in states:
            update_panel(st, yr)
        return []

    FuncAnimation(fig, frame_a1, frames=len(YRS)).save(os.path.join(C.FIGURES, f"a1_roadside_growth{suffix}.gif"),
                                                       writer=PillowWriter(fps=8), dpi=100)
    plt.close(fig)
    print(f"wrote a1_roadside_growth{suffix}.gif")

    # ------------------------------------------------ a4: one GIF per corridor
    for corridor, cfg in C.CORRIDORS.items():
        g = growth[growth.corridor == corridor].sort_values("km_mid").reset_index(drop=True)
        w = g.growth_ha_2000_2020.rolling(10, center=True).sum()
        picks = []
        for i in w.sort_values(ascending=False).index:
            if np.isnan(w[i]) or any(abs(g.km_mid[i] - g.km_mid[j]) < 30 for j in picks):
                continue
            picks.append(i)
            if len(picks) == 3:
                break
        picks.sort(key=lambda i: g.km_mid[i])
        fig = plt.figure(figsize=(13, 8.8), facecolor=SURF)
        states = []
        for j, i in enumerate(picks):
            km = g.km_mid[i]
            lon, lat = M.hotspot_point(corridor, km)
            near = M.typed[(M.typed.corridor == corridor) & M.typed.km_mid.between(km - 2.5, km + 2.5)].place.dropna()
            ax = fig.add_axes([0.03 + j * 0.325, 0.4, 0.3, 0.47])
            states.append(growth_panel(ax, corridor, lon, lat,
                                       f"km {km:.0f}{' · ' + near.mode().iloc[0] if len(near) else ''}", 4.3))
        axp = fig.add_axes([0.06, 0.12, 0.9, 0.18])
        per_km = g.groupby(np.floor(g.km_mid).astype(int))[[f"built_ha_{y}" for y in EPOCHS]].sum()
        xk = per_km.index.to_numpy() + 0.5
        base0 = per_km["built_ha_2000"].to_numpy()
        axp.fill_between(xk, 0, base0, step="mid", color=M.BUILDING, linewidth=0)
        for i in picks:
            axp.axvspan(g.km_mid[i] - 2.5, g.km_mid[i] + 2.5, color="#f6b596", alpha=0.35, linewidth=0, zorder=0)
        axp.set_xlim(0, g.km_mid.max())
        axp.set_ylim(0, at_year(per_km, end, "built_ha_").max() * 1.1)
        axp.set_facecolor(SURF)
        for s_ in ("top", "right", "left"):
            axp.spines[s_].set_visible(False)
        axp.tick_params(colors=INK2, labelsize=8, length=0)
        axp.grid(axis="y", color="#e4e3df", linewidth=0.6)
        axp.set_xlabel("km from Kampala", fontsize=8.5, color=INK2)
        axp.set_title("Built-up land within 300 m of the road, hectares per km (shaded: the three windows above)",
                      loc="left", fontsize=9.5, color=INK)
        total_txt = fig.text(0.06, 0.325, "", fontsize=10, color=INK)
        year_txt = fig.text(0.98, 0.975, "", ha="right", va="top", fontsize=24, color=INK)
        fig.text(0.03, 0.975, f"The roadside filling in: {cfg['label']}", fontsize=15, color=INK, va="top")
        fig.text(0.03, 0.935, "The three fastest-growing 5 km stretches, at least 30 km apart.\n" + source_line(mode),
                 fontsize=8.5, color=INK2, va="top")
        legend(fig, mode, y=0.0)
        fills = []

        def frame_a4(k, states=states, per_km=per_km, base0=base0, xk=xk, axp=axp, fills=fills, YRS=YRS,
                     year_txt=year_txt, total_txt=total_txt):
            yr = YRS[k]
            year_txt.set_text(year_label(yr))
            year_txt.set_color(PROJ if yr > LAST_OBSERVED else INK)
            for st in states:
                update_panel(st, yr)
            obs = np.maximum(at_year(per_km, min(yr, LAST_OBSERVED), "built_ha_").to_numpy(), base0)
            now = np.maximum(at_year(per_km, yr, "built_ha_").to_numpy(), obs)
            while fills:
                fills.pop().remove()
            fills.append(axp.fill_between(xk, base0, obs, step="mid", color=NEW, linewidth=0))
            if yr > LAST_OBSERVED:
                fills.append(axp.fill_between(xk, obs, now, step="mid", color=PROJ, linewidth=0))
            total_txt.set_text(f"Whole road: {base0.sum():,.0f} ha in 2000 → {now.sum():,.0f} ha in {yr:.0f} "
                               f"(+{100 * (now.sum() / base0.sum() - 1):.0f}%){' · projected' if yr > LAST_OBSERVED else ''}")
            return []

        FuncAnimation(fig, frame_a4, frames=len(YRS)).save(
            os.path.join(C.FIGURES, f"a4_growth_{corridor}{suffix}.gif"), writer=PillowWriter(fps=8), dpi=95)
        plt.close(fig)
        print(f"wrote a4_growth_{corridor}{suffix}.gif")
