"""Animation of the regional interactive map: a scripted tour of web/regional.html.

    python scripts/map_tour.py

Each stop is a page state set through the URL hash (layer, basemap, view, popup), screenshotted with
headless Chrome (tools/shoot.py), captioned, held and cross-faded into the next.
Writes figures/social/rx14_map_tour.mp4 and .gif.
"""
import os, sys
import numpy as np
import imageio.v2 as imageio
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from shoot import shoot  # noqa: E402
sys.path[:0] = [HERE]
from regional_common import C, H  # noqa: E402

OUT = os.path.join(C.FIGURES, "social")
TMP = os.path.join(C.DATA, "map_tour")
os.makedirs(TMP, exist_ok=True)
PAGE = "file://" + os.path.join(ROOT, "web", "regional.html")
FPS, HOLD, FADE = 12, int(3.0 * 12), int(0.8 * 12)


def hot_id(place):
    """Index of a hotspot in the page's list (same order as build_regional_web.py)."""
    from regional_common import distinct
    i = 0
    for country, h in H.groupby("country"):
        for r in distinct(h, 4, min_km=5).itertuples():
            if r.place_name == place:
                return i
            i += 1
    return None


STOPS = [
    ("layer=type&z=4&lat=-12&lon=31", "54 roads out of 12 African hubs, every 2 km"),
    ("layer=type&z=6&lat=-1.5&lon=33.5", "East Africa: most of the road length is roadside settlement"),
    ("layer=delay&z=6&lat=-1.5&lon=33.5", "Switch the layer: minutes a loaded truck loses per km"),
    ("layer=delay&z=10&lat=-1.22&lon=36.95&base=sat", "Fly to Nairobi: the slowest stretches leave the city"),
    ("layer=exposure&z=10&lat=-1.22&lon=36.95&base=sat", "Safety: where fast trucks pass people"),
    ("layer=delay&z=10&lat=0.33&lon=32.62&base=sat", "Kampala: every road out is a high street"),
    ("layer=delay&z=14&lat=0.335&lon=32.62&base=sat", "Zoom to street level"),
    ("layer=type&z=6&lat=-25.5&lon=28.5", "Southern Africa: open road beyond the cities"),
    ("layer=controls&z=9&lat=-26.0&lon=28.1", "Gauteng: controls mapped one by one in OpenStreetMap"),
    ("layer=growth&z=5&lat=-12&lon=31", "Explore growth, people, diesel and rain for every stretch"),
]


def caption(img, text, n):
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 26)
        f2 = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 16)
    except OSError:
        f = f2 = ImageFont.load_default()
    w, h = img.size
    d.rectangle([340, h - 70, w, h], fill=(29, 35, 33))
    d.text((360, h - 58), text, font=f, fill=(255, 255, 255))
    d.text((w - 330, h - 28), "gavacharles.github.io/uganda-trade-corridors/regional", font=f2, fill=(190, 200, 198))
    return img


frames = []
for n, (hash_, text) in enumerate(STOPS):
    png = os.path.join(TMP, f"stop_{n:02d}.png")
    shoot(f"{PAGE}#{hash_}", png, 12000, 1280, 720)
    frames.append(np.asarray(caption(Image.open(png).convert("RGB"), text, n)))
    print("stop", n, flush=True)

mp4 = os.path.join(OUT, "rx14_map_tour.mp4")
small = []
with imageio.get_writer(mp4, fps=FPS, codec="libx264", quality=8, macro_block_size=16) as w:
    k = 0
    for i, f in enumerate(frames):
        seq = [f] * HOLD
        if i + 1 < len(frames):
            g = frames[i + 1].astype(float)
            seq += [(f * (1 - t) + g * t).astype(np.uint8) for t in np.linspace(0, 1, FADE + 2)[1:-1]]
        for x in seq:
            w.append_data(x)
            if k % 2 == 0:
                small.append(Image.fromarray(x).resize((800, 450), Image.LANCZOS).convert("P", palette=Image.ADAPTIVE))
            k += 1
gif = os.path.join(OUT, "rx14_map_tour.gif")
small[0].save(gif, save_all=True, append_images=small[1:], duration=int(2000 / FPS), loop=0, optimize=True)
print(f"wrote rx14_map_tour: {k} frames, gif {os.path.getsize(gif) / 1e6:.1f} MB")
