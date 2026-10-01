"""Animation for the explorer and social posts: the worst 2 km stretches pinned one by one.

The national map shows each corridor coloured by the minutes a loaded truck loses per km
(10_travel_time.py). The worst stretches by truck minutes (outputs/hotspots_mapped.csv) then
appear in turn with a pulse, and a card names the place, the road and km, the minutes lost and
the main causes. The last frames show all pins and where to explore every 500 m.

Writes figures/a5_bottleneck_pins.mp4 (1280 x 720, 10 fps, for LinkedIn and X) and
figures/a5_bottleneck_pins.gif (smaller, 5 fps).
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
import maplib as M
from cartography import INK, INK2, SURF

N_PINS, FPS, INTRO, PER, OUTRO = 8, 10, 15, 24, 40
EXPLORER = "gavacharles.github.io/uganda-trade-corridors"
H = pd.read_csv(os.path.join(C.OUTPUTS, "hotspots_mapped.csv")).sort_values("truck_excess_min", ascending=False)
H = H.head(N_PINS).reset_index(drop=True)
# Readable names: a weighbridge-led stretch takes its weighbridge's town (OSM names are
# inconsistent), a few OSM neighbourhood names get their better-known place
WEIGHBRIDGES = {"Magamaga": (33.372, 0.523), "Busitema": (33.966, 0.524), "Lukaya": (31.883, -0.141),
                "Luwero": (32.486, 0.862), "Mbarara": (30.697, -0.571)}
RENAME = {"Nakawa Vocation Institute": "Nakawa, Kampala", "Bibia West Lc1": "Bibia, at the Elegu border"}


def display_name(r):
    if r.main_causes.startswith("weighbridge"):
        town, (x, y) = min(WEIGHBRIDGES.items(), key=lambda kv: np.hypot(kv[1][0] - r.lon, kv[1][1] - r.lat))
        if np.hypot(x - r.lon, y - r.lat) < 0.03:
            return f"{town} weighbridge"
    return RENAME.get(r.place, r.place)


H["place"] = [display_name(r) for r in H.itertuples()]
_first = H.main_causes.str.split(";").str[0].str.rsplit(" ", n=1).str[0]
_ctrl = _first.isin(["weighbridge", "police posts", "signals and crossings"]).sum()
LEAD = (f"All {len(H)} are led by a weighbridge,\npolice post or traffic signals." if _ctrl == len(H) else
        f"{_ctrl} of these {len(H)} are led by a weighbridge,\npolice post or traffic signals.")
ROAD = {c: f"{cfg['short']} road ({cfg['ref']})" for c, cfg in C.CORRIDORS.items()}


def causes(s):
    parts = [p.strip() for p in s.split(";")]
    return " · ".join(f"{p.rsplit(' ', 1)[0]} {float(p.rsplit(' ', 1)[1]):.1f}" for p in parts[:3])


fig = plt.figure(figsize=(12.8, 7.2), dpi=100, facecolor=SURF)
ax = fig.add_axes([0.01, 0.02, 0.50, 0.96])
M.base(ax)
M.context_labels(ax)
for c in C.CORRIDORS:
    M.delay_line(ax, c, lw=2.6)
M.town_labels(ax, ["Kampala", "Jinja", "Gulu", "Masaka", "Mbarara", "Hoima", "Fort Portal", "Kasese"]
              if "Fort Portal" in M.TOWNS else ["Kampala", "Jinja", "Gulu", "Masaka", "Mbarara", "Hoima"], size=8)
M.border_marks(ax, size=7.5)

fig.text(0.535, 0.92, "Where Uganda's trade roads lose time", fontsize=18, color=INK, fontweight="bold")
fig.text(0.535, 0.875, "The worst 2 km stretches for a loaded truck, five corridors out of Kampala",
         fontsize=11, color=INK2)
fig.text(0.535, 0.02, "Modelled minutes lost against open road, light traffic, dry day.\n"
         "Open data: OpenStreetMap, Google Open Buildings.", fontsize=8.5, color=INK2)
key = fig.add_axes([0.535, 0.10, 0.30, 0.025])
key.imshow(np.arange(6)[None, :], cmap=M.DELAY_CMAP, aspect="auto", extent=(0, 6, 0, 1))
key.set_yticks([])
key.set_xticks(np.arange(6) + 0.5)
key.set_xticklabels(M.DELAY_LABELS, fontsize=8, color=INK2)
key.tick_params(length=0)
for s_ in key.spines.values():
    s_.set_visible(False)
fig.text(0.535, 0.135, "truck minutes lost per km", fontsize=8.5, color=INK2)

dyn = []


def clear():
    while dyn:
        dyn.pop().remove()


def pin(i, x, y, big=False):
    dyn.append(ax.scatter([x], [y], s=(330 if big else 210), color="white", edgecolor=INK, linewidth=1.6, zorder=20))
    dyn.append(ax.text(x, y, str(i + 1), ha="center", va="center", fontsize=10 if big else 8.5,
                       fontweight="bold", color=INK, zorder=21))


def card(r, i):
    y0 = 0.76
    dyn.append(fig.text(0.535, y0, f"{i + 1}", fontsize=46, color="#b8491c", fontweight="bold", va="top"))
    dyn.append(fig.text(0.60, y0 - 0.005, r.place, fontsize=19, color=INK, fontweight="bold", va="top"))
    dyn.append(fig.text(0.60, y0 - 0.058, f"{ROAD[r.corridor]} · km {r.km_from:.0f}–{r.km_to:.0f} · {r.road_type}",
                        fontsize=11, color=INK2, va="top"))
    dyn.append(fig.text(0.535, y0 - 0.14, f"+{r.truck_excess_min:.1f} truck minutes", fontsize=24, color=INK,
                        va="top", fontweight="bold"))
    dyn.append(fig.text(0.535, y0 - 0.205, f"in 2 km   ·   car +{r.car_excess_min:.1f} min", fontsize=11.5,
                        color=INK2, va="top"))
    dyn.append(fig.text(0.535, y0 - 0.265, "main causes, minutes:\n" + causes(r.main_causes), fontsize=11, color=INK,
                        va="top"))


def history(upto):
    y = 0.36
    if upto:
        dyn.append(fig.text(0.535, y + 0.035, "the worst so far" if upto < len(H) else f"the worst {len(H)}",
                            fontsize=9, color=INK2))
    for j in range(upto):
        r = H.iloc[j]
        dyn.append(fig.text(0.535, y - j * 0.032, f"{j + 1}  {r.place[:26]:26s}  {C.CORRIDORS[r.corridor]['short']:7s} "
                            f"+{r.truck_excess_min:4.1f} min", fontsize=9, color=INK2, family="monospace"))


def grab():
    fig.canvas.draw()
    return np.asarray(fig.canvas.buffer_rgba())[..., :3].copy()


frames = []
for f in range(INTRO):
    frames.append(grab())
for i, r in H.iterrows():
    for f in range(PER):
        clear()
        for j in range(i):
            pin(j, H.lon[j], H.lat[j])
        if f < 12:   # pulse
            a = 1 - f / 12
            dyn.append(ax.scatter([r.lon], [r.lat], s=200 + 2600 * (f / 12), facecolor="none",
                                  edgecolor="#b8491c", linewidth=2.5, alpha=a, zorder=19))
        pin(i, r.lon, r.lat, big=True)
        card(r, i)
        history(i)
        frames.append(grab())
for f in range(OUTRO):
    clear()
    for j in range(len(H)):
        pin(j, H.lon[j], H.lat[j])
    history(len(H))
    dyn.append(fig.text(0.535, 0.74, LEAD, fontsize=17, color=INK, fontweight="bold", va="top"))
    dyn.append(fig.text(0.535, 0.58, f"Explore every 500 m:\n{EXPLORER}", fontsize=14, color="#b8491c",
                        va="top", fontweight="bold"))
    frames.append(grab())
plt.close(fig)

mp4 = os.path.join(C.FIGURES, "a5_bottleneck_pins.mp4")
with imageio.get_writer(mp4, fps=FPS, codec="libx264", quality=8, macro_block_size=16,
                        ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"]) as w:
    for fr in frames:
        w.append_data(fr)
gif = os.path.join(C.FIGURES, "a5_bottleneck_pins.gif")
small = [Image.fromarray(fr).resize((960, 540), Image.LANCZOS).quantize(colors=96, method=Image.MEDIANCUT)
         for fr in frames[::2]]
small[0].save(gif, save_all=True, append_images=small[1:], duration=200, loop=0, optimize=True)
print(f"wrote {mp4} ({len(frames)} frames, {os.path.getsize(mp4) / 1e6:.1f} MB), {gif} "
      f"({os.path.getsize(gif) / 1e6:.1f} MB)")
print(H[["place", "corridor", "km_from", "truck_excess_min", "main_causes"]].to_string(index=False))
