"""Fly-through animations: a camera that flies from bottleneck to bottleneck, zooming out between
stops and down to street level (about 5 km across) at each, where an info card gives the causes.

Used by 33_flythrough.py (Uganda) and regional-corridors/scripts/flythrough_regional.py.

    fly(name, out_dir, pieces, sites, countries, lakes, focus, feat_gpkg, buildings, title, sub, start)

pieces    GeoDataFrame (EPSG:4326) of the study's 500 m pieces with a `per_km` column (truck min/km)
sites     list of dicts: lon, lat, kicker, place, road, minutes, causes, colour
countries Natural Earth admin-0 polygons (ADMIN column); focus = names drawn as land
buildings DataFrame of footprints (longitude, latitude, area_in_meters), read only near the sites
start     (lon, lat, width in degrees) of the opening and closing view
"""
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import imageio.v2 as imageio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch
from PIL import Image

INK, INK2, SURF = "#1d2321", "#5d6764", "#fcfcfb"
LAND, NEIGH, WATER, BORDER = "#f6f4ef", "#e9e6df", "#c9dbe6", "#a8a49b"
DCMAP = ListedColormap(["#e3ded3", "#fde6da", "#f6b596", "#eb6834", "#b8491c", "#7c2e0f"])
DNORM = BoundaryNorm([-1, 0.25, 0.5, 1, 2, 4, 1000], DCMAP.N)
DLABELS = ["< 0.25", "0.25–0.5", "0.5–1", "1–2", "2–4", "> 4"]
ROAD_W = {"motorway": 2.2, "trunk": 2.2, "primary": 2.0, "secondary": 1.5, "tertiary": 1.2,
          "residential": 0.7, "unclassified": 0.7, "service": 0.45, "track": 0.45}
MARK = {"checkpoint_or_police": "D", "weighbridge": "s", "traffic_signals": "P", "pedestrian_crossing": "o",
        "market": "^", "fuel": "v", "speed_hump": "X", "rumble_strip": "X", "level_crossing": "*"}
STREET_W = 0.045          # width of the view at a stop, degrees (about 5 km)
NEAR = 0.10               # street detail is read within this many degrees of each stop


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def lines_of(gdf):
    out = []
    for g in gdf.geometry:
        if g is None or g.is_empty:
            continue
        for part in (g.geoms if g.geom_type.startswith("Multi") else [g]):
            out.append(np.asarray(part.coords)[:, :2])
    return out


def path(a, b, n):
    """Camera from view a to view b (lon, lat, width) in n frames, zooming out in between so the
    move never jumps further than the view is wide."""
    dist = np.hypot(b[0] - a[0], b[1] - a[1])
    peak = max(a[2], b[2], dist * 1.4)
    bump = np.log(peak) - max(np.log(a[2]), np.log(b[2]))
    out = []
    for i in range(n):
        u = ease((i + 1) / n)
        lw = (1 - u) * np.log(a[2]) + u * np.log(b[2]) + bump * np.sin(np.pi * u)
        if a[2] > dist * 1.4:          # target already in view: arrive first, then zoom in
            v = ease(min(u / 0.45, 1))
        elif b[2] > dist * 1.4:        # zooming out to a view that holds the start: zoom first, then move
            v = ease(max((u - 0.55) / 0.45, 0))
        else:                          # stop to stop: move while zoomed out
            v = ease(min(max((u - 0.15) / 0.7, 0), 1))
        out.append((a[0] + (b[0] - a[0]) * v, a[1] + (b[1] - a[1]) * v, float(np.exp(lw))))
    return out


def fly(name, out_dir, pieces, sites, countries, lakes, focus, feat_gpkg, buildings, title, sub, start,
        fps=12, fly_s=3.6, hold_s=3.8, foot="Open data · github.com/gavacharles/uganda-trade-corridors"):
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100, facecolor=SURF)
    ax = fig.add_axes([0, 0, 1, 0.885])
    ax.set_axis_off()
    ax.set_facecolor(WATER)
    fig.patches.append(plt.Rectangle((0, 0), 1, 0.885, transform=fig.transFigure, color=WATER, zorder=-10))
    fig.text(0.02, 0.955, title, fontsize=21, fontweight="bold", color=INK, va="center")
    fig.text(0.02, 0.91, sub, fontsize=11.5, color=INK2, va="center")
    counter = fig.text(0.98, 0.955, "", fontsize=15, color=INK2, ha="right", va="center")
    fig.text(0.99, 0.008, foot, fontsize=8, color=INK2, ha="right", zorder=30,
             bbox=dict(boxstyle="square,pad=0.25", fc="white", ec="none", alpha=0.8))
    axw, axh = 12.8, 7.2 * 0.885

    # base: countries and lakes, once
    xs = [s["lon"] for s in sites] + [start[0]]
    ys = [s["lat"] for s in sites] + [start[1]]
    bx0, bx1 = min(xs) - start[2], max(xs) + start[2]
    by0, by1 = min(ys) - start[2], max(ys) + start[2]
    cc = countries.cx[bx0:bx1, by0:by1]
    cc.plot(ax=ax, aspect=None, color=NEIGH, edgecolor=BORDER, linewidth=0.6, zorder=1)
    cc[cc.ADMIN.isin(focus)].plot(ax=ax, aspect=None, color=LAND, edgecolor=BORDER, linewidth=0.7, zorder=2)
    lk = lakes.cx[bx0:bx1, by0:by1]
    if len(lk):
        lk.plot(ax=ax, aspect=None, color=WATER, linewidth=0, zorder=3)
    labels = []
    for r in cc.itertuples():
        p = r.geometry.representative_point()
        labels.append(ax.text(p.x, p.y, r.ADMIN.replace("United Republic of ", "").upper(), fontsize=10,
                              color="#8d8980", ha="center", va="center", zorder=4, clip_on=True))

    # street detail near each stop
    streets = []
    for s in sites:
        x0, x1, y0, y1 = s["lon"] - NEAR, s["lon"] + NEAR, s["lat"] - NEAR, s["lat"] + NEAR
        rd = lambda layer: gpd.read_file(feat_gpkg, layer=layer, bbox=(x0, y0, x1, y1))  # noqa: E731
        rr = rd("roads")
        rr = rr[rr.highway.isin(ROAD_W)]
        rl = LineCollection(lines_of(rr), colors="#6f6c66", zorder=4.5)
        rl.base = np.repeat(rr.highway.map(ROAD_W).to_numpy(), [len(g.geoms) if g.geom_type.startswith("Multi")
                                                                 else 1 for g in rr.geometry])
        ax.add_collection(rl)
        ww = rd("waterways")
        wl = LineCollection(lines_of(ww), colors="#7fa9cf", zorder=4.2)
        ax.add_collection(wl)
        bb = buildings[buildings.longitude.between(x0, x1) & buildings.latitude.between(y0, y1)]
        bs = ax.scatter(bb.longitude, bb.latitude, s=1, marker="s", color="#9d988c", linewidths=0, zorder=4.4)
        bs.side = np.sqrt(bb.area_in_meters.to_numpy())
        pp = rd("points")
        pp = pp[pp.kind.isin(MARK)]
        ms = [ax.scatter(g.geometry.x, g.geometry.y, marker=MARK[k], s=46, color="white", edgecolor=INK,
                         linewidth=1.0, zorder=8) for k, g in pp.groupby("kind")]
        streets.append(dict(lon=s["lon"], lat=s["lat"], roads=rl, water=wl, bld=bs, marks=ms))

    # study roads coloured by delay, with a dark casing
    segs = lines_of(pieces)
    vals = np.concatenate([[v] * (len(g.geoms) if g.geom_type.startswith("Multi") else 1)
                           for v, g in zip(pieces.per_km.to_numpy(), pieces.geometry) if g is not None and not g.is_empty])
    casing = LineCollection(segs, colors=INK, zorder=5)
    road = LineCollection(segs, cmap=DCMAP, norm=DNORM, zorder=6)
    road.set_array(vals)
    ax.add_collection(casing)
    ax.add_collection(road)

    # stop markers and the info card
    pins = [ax.scatter([s["lon"]], [s["lat"]], s=150, facecolor="white", edgecolor=INK, linewidth=1.8, zorder=12)
            for s in sites]
    nums = [ax.text(s["lon"], s["lat"], str(i + 1), fontsize=8, fontweight="bold", ha="center", va="center",
                    color=INK, zorder=13) for i, s in enumerate(sites)]
    card = fig.text(0.02, 0.04, "", fontsize=12, color=INK, va="bottom", zorder=40, linespacing=1.45,
                    bbox=dict(boxstyle="round,pad=0.7", fc="white", ec="#d8d5ce", alpha=0.96))
    fig.legend(handles=[Patch(color=DCMAP(i), label=l) for i, l in enumerate(DLABELS)], ncol=6, loc="lower right",
               bbox_to_anchor=(0.995, 0.035), title="truck minutes lost per km (vs open road)", fontsize=9,
               title_fontsize=9.5, frameon=True, facecolor="white", edgecolor="#d8d5ce", framealpha=0.95)

    def frame(view, k=None, show_card=False):
        lon, lat, w = view
        h = w * axh / axw / np.cos(np.radians(lat))
        ax.set_xlim(lon - w / 2, lon + w / 2)
        ax.set_ylim(lat - h / 2, lat + h / 2)
        inch = axw / w                                   # inches per degree
        lw = float(np.interp(np.log(w), np.log([STREET_W, 1, 20]), [10, 4.5, 1.8]))
        road.set_linewidths(lw)
        casing.set_linewidths(lw + 2)
        street_on = w < 1.2
        for st in streets:
            near = street_on and abs(st["lon"] - lon) < w + NEAR and abs(st["lat"] - lat) < w + NEAR
            for a in (st["roads"], st["water"], st["bld"], *st["marks"]):
                a.set_visible(near)
            if near:
                st["bld"].set_sizes(np.maximum(st["bld"].side / 111_320 * inch * 72, 0.35) ** 2)
                st["roads"].set_linewidths(st["roads"].base * float(np.clip(0.9 * (0.3 / w) ** 0.45, 0.25, 2.2)))
                st["water"].set_linewidths(float(np.clip((0.3 / w) ** 0.4, 0.4, 2.2)))
                for m in st["marks"]:
                    m.set_visible(w < 0.12)
        for p, t in zip(pins, nums):
            p.set_visible(w > 0.35)
            t.set_visible(w > 0.35)
        for t in labels:
            t.set_visible(w > 2.5)
        if show_card:
            s = sites[k]
            card.set_text(f"{s['kicker']}\n{s['place']}\n{s['road']}\n+{s['minutes']:.1f} truck minutes over 2 km\n"
                          + "\n".join("· " + c for c in s["causes"]))
            card.get_bbox_patch().set_edgecolor(s.get("colour", INK))
            card.get_bbox_patch().set_linewidth(2.5)
            card.set_visible(True)
        else:
            card.set_visible(False)
        counter.set_text(f"{k + 1} / {len(sites)}" if k is not None else "")
        fig.canvas.draw()
        return np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy()

    os.makedirs(out_dir, exist_ok=True)
    mp4 = os.path.join(out_dir, name + ".mp4")
    gif_frames, n = [], 0
    with imageio.get_writer(mp4, fps=fps, codec="libx264", quality=8, macro_block_size=16) as wr:
        def put(img, rep=1):
            nonlocal n
            for _ in range(rep):
                wr.append_data(img)
                if n % 2 == 0:
                    gif_frames.append(Image.fromarray(img).resize((800, 450), Image.LANCZOS)
                                      .convert("P", palette=Image.ADAPTIVE, colors=256))
                n += 1
        view = start
        put(frame(view), int(1.5 * fps))
        for k, s in enumerate(sites):
            target = (s["lon"], s["lat"], STREET_W)
            for v in path(view, target, int(fly_s * fps)):
                put(frame(v, k))
            put(frame(target, k, show_card=True), int(hold_s * fps))
            view = target
            print("stop", k + 1, s["place"], flush=True)
        for v in path(view, start, int(fly_s * fps)):
            put(frame(v))
        put(frame(start), int(1.5 * fps))
    plt.close(fig)
    gif = os.path.join(out_dir, name + ".gif")
    gif_frames[0].save(gif, save_all=True, append_images=gif_frames[1:], duration=int(2000 / fps), loop=0,
                       optimize=True)
    print(f"wrote {name}: {n} frames ({n / fps:.0f} s), gif {os.path.getsize(gif) / 1e6:.1f} MB", flush=True)
