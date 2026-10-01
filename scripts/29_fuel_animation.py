"""Animation: the diesel meter on one truck trip, Kampala to Malaba (A1), against an open road.

A loaded truck drives the A1. Two meters run as it goes: the litres burnt as modelled (towns,
humps, signals, weighbridges, junctions, hills; 26_fuel_co2.py, central case, outbound) and the
litres the same truck would burn on an open road. The gap between them, shaded, is fuel burnt
slowing down and speeding up again. Counters give litres, CO2 (2.68 kg per litre of diesel) and
diesel cost; the closing card scales to a year on all five roads (outputs/fuel_co2.csv).

Writes figures/a6_fuel_meter.mp4 (1280 x 720, 12 fps) and figures/a6_fuel_meter.gif (5 fps).
"""
import os
import numpy as np
import pandas as pd
import imageio.v2 as imageio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

import config as C
from cartography import INK, INK2, SURF

CORR, FPS, DRIVE_S, END_S = "kampala_malaba", 12, 13, 5
CO2_KG_L, USD_L = 2.68, 1.35            # as in 26_fuel_co2.py (central)
RED, GREY = "#b8491c", "#8a9a93"
P = pd.read_csv(os.path.join(C.OUTPUTS, "fuel_co2_pieces.csv"))
P = P[P.corridor == CORR].sort_values("piece").reset_index(drop=True)
km = np.r_[0, P.km_start.to_numpy() + 0.5]
act = np.r_[0, P.litres.cumsum().to_numpy()]
opn = np.r_[0, P.litres_open.cumsum().to_numpy()]
F = pd.read_csv(os.path.join(C.OUTPUTS, "fuel_co2.csv"))
year_co2_kt = F.groupby("corridor").friction_co2_kt_year.first().sum()
year_usd_m = F.groupby("corridor").friction_fuel_usd_year_m.first().sum()

# Places along the road, placed at the nearest piece
PLACES = {"Kampala": (32.5825, 0.3136), "Mukono": (32.7550, 0.3530), "Lugazi": (32.9420, 0.3700),
          "Jinja": (33.2040, 0.4390), "Magamaga\nweighbridge": (33.372, 0.523), "Iganga": (33.4690, 0.6090),
          "Bugiri": (33.7420, 0.5680), "Busitema\nweighbridge": (33.966, 0.524), "Tororo": (34.1810, 0.6930),
          "Malaba": (34.2790, 0.6380)}
pkm = {n: P.km_start[((P.lon - x) ** 2 + (P.lat - y) ** 2).idxmin()] for n, (x, y) in PLACES.items()}

fig = plt.figure(figsize=(12.8, 7.2), dpi=100, facecolor=SURF)
ax = fig.add_axes([0.065, 0.2, 0.6, 0.6])
ax.set_facecolor(SURF)
ax.set_xlim(0, km[-1] + 2)
ax.set_ylim(0, act[-1] * 1.08)
for s_ in ("top", "right"):
    ax.spines[s_].set_visible(False)
for s_ in ("left", "bottom"):
    ax.spines[s_].set_color("#d9d6cf")
ax.tick_params(colors=INK2, labelsize=10, length=0)
ax.grid(axis="y", color="#e4e3df", linewidth=0.7)
ax.set_ylabel("litres of diesel since Kampala", fontsize=11, color=INK2)
ax.set_xticks([])
last, row = -99, 0
for n, k in sorted(pkm.items(), key=lambda kv: kv[1]):
    row = 1 - row if k - last < 18 else 0   # stagger labels that would touch
    last = k
    ax.axvline(k, color="#ece9e2", lw=1, zorder=0)
    ax.plot([k, k], [0, -act[-1] * (0.02 + 0.075 * row)], color="#d9d6cf", lw=0.8, clip_on=False)
    ax.text(k, -act[-1] * (0.03 + 0.075 * row), n, ha="center", va="top", fontsize=9, color=INK2, linespacing=1.0)
fig.text(0.065, 0.92, "The diesel meter: one truck, Kampala to Malaba", fontsize=21, color=INK, fontweight="bold")
fig.text(0.065, 0.875, "A loaded 40 t truck on the A1, light traffic. Grey: the same truck on an open road. "
         "Red gap: fuel burnt slowing down and speeding up again.", fontsize=11, color=INK2)
fig.text(0.065, 0.03, "Physical fuel model on the travel-time model's speed profile (rolling, air, re-acceleration, idling); "
         "speed humps are assumed. CO₂ 2.68 kg per litre.", fontsize=8.5, color=INK2)

l_act, = ax.plot([], [], color=RED, lw=3, zorder=4)
l_opn, = ax.plot([], [], color=GREY, lw=2.4, ls="--", zorder=3)
truck, = ax.plot([], [], "o", ms=13, color=RED, mec=INK, mew=1.6, zorder=6)
dyn = []


def counters(i):
    while dyn:
        dyn.pop().remove()
    extra = act[i] - opn[i]
    x0 = 0.71
    rows = [("diesel burnt", f"{act[i]:.1f} L", INK), ("on an open road", f"{opn[i]:.1f} L", INK2),
            ("burnt by stop-and-go", f"+{extra:.1f} L", RED), ("extra CO₂", f"+{extra * CO2_KG_L:.0f} kg", RED),
            ("extra diesel cost", f"+US${extra * USD_L:.0f}", RED)]
    for j, (k, v, c) in enumerate(rows):
        y = 0.74 - j * 0.105
        dyn.append(fig.text(x0, y, k, fontsize=11, color=INK2))
        dyn.append(fig.text(x0, y - 0.05, v, fontsize=24, color=c, fontweight="bold", family="monospace"))
    dyn.append(fig.text(x0, 0.2, f"km {km[i]:5.1f} of {km[-1]:.0f}", fontsize=11, color=INK2, family="monospace"))


def grab():
    fig.canvas.draw()
    return np.asarray(fig.canvas.buffer_rgba())[..., :3].copy()


frames, n = [], DRIVE_S * FPS
idx = np.unique(np.linspace(0, len(km) - 1, n).round().astype(int))
fill = None
for i in idx:
    l_act.set_data(km[:i + 1], act[:i + 1])
    l_opn.set_data(km[:i + 1], opn[:i + 1])
    truck.set_data([km[i]], [act[i]])
    if fill is not None:
        fill.remove()
    fill = ax.fill_between(km[:i + 1], opn[:i + 1], act[:i + 1], color=RED, alpha=0.16, lw=0, zorder=2)
    counters(i)
    frames.append(grab())
extra = act[-1] - opn[-1]
box = fig.add_axes([0.08, 0.3, 0.57, 0.36])
box.set_xticks([]); box.set_yticks([])
box.set_facecolor("#fbf3ee")
for s_ in box.spines.values():
    s_.set_color("#ecd3c5")
box.text(0.04, 0.82, f"One trip: +{extra:.0f} L of diesel, +{extra * CO2_KG_L:.0f} kg of CO₂", fontsize=19,
         color=INK, fontweight="bold", transform=box.transAxes, va="top")
box.text(0.04, 0.55, f"All five corridors, a year: about {year_co2_kt:,.0f},000 t of CO₂\n"
         f"and US${year_usd_m:.0f} M of diesel, from stop-and-go alone.", fontsize=14, color=INK,
         transform=box.transAxes, va="top", linespacing=1.35)
box.text(0.04, 0.2, "Fewer stops is cleaner freight: weigh-in-motion, fewer police stops,\n"
         "service roads that keep local traffic off the highway.", fontsize=12, color=RED,
         transform=box.transAxes, va="top", linespacing=1.35)
for _ in range(END_S * FPS):
    frames.append(grab())
plt.close(fig)

mp4 = os.path.join(C.FIGURES, "a6_fuel_meter.mp4")
with imageio.get_writer(mp4, fps=FPS, codec="libx264", quality=8, macro_block_size=16,
                        ffmpeg_params=["-movflags", "+faststart"]) as w:
    for fr in frames:
        w.append_data(fr)
gif = os.path.join(C.FIGURES, "a6_fuel_meter.gif")
small = [Image.fromarray(fr).resize((960, 540), Image.LANCZOS).quantize(colors=96, method=Image.MEDIANCUT)
         for fr in frames[::2]]
small[0].save(gif, save_all=True, append_images=small[1:], duration=int(2000 / FPS), loop=0, optimize=True)
print(f"wrote {mp4} ({len(frames)} frames), {gif} ({os.path.getsize(gif) / 1e6:.1f} MB); "
      f"trip {act[-1]:.1f} L vs open {opn[-1]:.1f} L; year {year_co2_kt:.0f} kt CO2, ${year_usd_m:.0f} M")
