"""Ten more animations for the regional posts (1280 x 720 MP4 at 12 fps, plus a GIF).

    python scripts/social_animations2.py            # all
    python scripts/social_animations2.py 4 7 13     # some

figures/social/:
  rx4_street_growth     GHSL built-up cells filling in, 2000-2020, at the fastest-growing stretch in
                        East and in Southern Africa (6 km windows)
  rx5_flythrough        from the region down to street level, leaving Nairobi and leaving Pretoria
  rx6_fuel_meter        extra diesel and CO2 as one loaded truck drives Nairobi-Malaba and Pretoria-Beitbridge
  rx7_safety_sweep      people passed at more than 50 km/h, and school stretches, on the same two roads
  rx8_cause_waterfall   how a truck's 100 km grows cause by cause, East against Southern
  rx9_road_type_reveal  the 54 roads turn town, settlement or open road, hub by hub
  rx10_mapping_gap      controls recorded in OpenStreetMap appearing, East against Southern
  rx11_rain_year        a year of rain: how much slower each road is, month by month
  rx12_fixes            the share of truck delay each fix removes, East against Southern
  rx13_bottleneck_tour  the worst stretch in each of the ten countries, at street level
Frames are streamed to the MP4 and only every other frame is kept, small, for the GIF, so memory
stays low.
"""
import glob, os, sys
import numpy as np
import pandas as pd
import geopandas as gpd
import imageio.v2 as imageio
import pyarrow.parquet as pq
import rasterio
from rasterio.windows import from_bounds
from pyproj import Transformer
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
from PIL import Image

from regional_common import ART, C, EAST, H, INK, INK2, O, SOUTH, SURF, distinct, nearest_place, pieces
import cartography as K

OUT = os.path.join(C.FIGURES, "social")
os.makedirs(OUT, exist_ok=True)
FPS = 12
LAND, NEIGH, WATER, BORDER = "#f6f4ef", "#e9e6df", "#c9dbe6", "#a8a49b"
TYPE_COL = {"open road": "#cfe0d6", "roadside settlement": "#e8c77e", "town": "#c4532d"}
SHORT = {"United Republic of Tanzania": "Tanzania"}
FOOT = "Open data · github.com/gavacharles/uganda-trade-corridors"
DCMAP = ListedColormap(["#e3ded3", "#fde6da", "#f6b596", "#eb6834", "#b8491c", "#7c2e0f"])
DNORM = BoundaryNorm([-1, 0.25, 0.5, 1, 2, 4, 1000], DCMAP.N)
countries = gpd.read_file(os.path.join(C.DATA, "ne_admin0", "ne_10m_admin_0_countries.shp"), columns=["ADMIN"])
lakes = gpd.read_file(os.path.join(C.ROOT, "..", "data", "ne_lakes", "ne_10m_lakes.shp")).to_crs(4326)
STUDY = set(ART.country)

P = pieces.to_crs(4326).copy()
T = O("pieces_typed.csv")
P = P.merge(T[["corridor", "piece", "road_type", "place", "buildings_100m"]], how="left")
P["region"] = P.corridor.map(ART.region)
P["country"] = P.corridor.map(ART.country)
P["hub"] = P.corridor.map(ART.hub)
CEN = P.geometry.centroid
EXT = {}
for reg, d in P.groupby("region"):
    x0, y0, x1, y1 = d.total_bounds
    EXT[reg] = (x0 - 0.6, x1 + 0.6, y0 - 0.6, y1 + 0.6)
PAIR = [("nairobi_a8_malaba", "Nairobi → Malaba (A8), Kenya", EAST),
        ("pretoria_n1_beitbridge", "Pretoria → Beitbridge (N1), South Africa", SOUTH)]


# ====================================================================== helpers
class Writer:
    """Stream frames to an MP4; keep every other frame, downsized, for the GIF."""

    def __init__(self, name, gif_fps=6, gif_w=800):
        self.name, self.gif_fps, self.gif_w = name, gif_fps, gif_w
        self.w = imageio.get_writer(os.path.join(OUT, name + ".mp4"), fps=FPS, codec="libx264", quality=8,
                                    macro_block_size=16)
        self.small, self.n = [], 0

    def add(self, fig, repeat=1):
        fig.canvas.draw()
        f = np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy()
        for _ in range(repeat):
            self.w.append_data(f)
            if self.n % (FPS // self.gif_fps) == 0:
                self.small.append(Image.fromarray(f).resize((self.gif_w, int(f.shape[0] * self.gif_w / f.shape[1])),
                                                            Image.LANCZOS).convert("P", palette=Image.ADAPTIVE, colors=256))
            self.n += 1

    def close(self):
        self.w.close()
        gif = os.path.join(OUT, self.name + ".gif")
        self.small[0].save(gif, save_all=True, append_images=self.small[1:], duration=int(1000 / self.gif_fps),
                           loop=0, optimize=True)
        print(f"wrote {self.name}: {self.n} frames, gif {os.path.getsize(gif) / 1e6:.1f} MB", flush=True)


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def new_fig(title, sub, dark=False):
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100, facecolor=SURF)
    fig.text(0.03, 0.94, title, fontsize=23, fontweight="bold", color=INK)
    fig.text(0.03, 0.897, sub, fontsize=12, color=INK2)
    fig.text(0.97, 0.015, FOOT, fontsize=8.5, color=INK2, ha="right")
    return fig


def basemap(ax, extent, labels=True):
    x0, x1, y0, y1 = extent
    cc = countries.cx[x0 - 5:x1 + 5, y0 - 5:y1 + 5]
    cc.plot(ax=ax, aspect=None, color=NEIGH, edgecolor=BORDER, linewidth=0.5, zorder=1)
    cc[cc.ADMIN.isin(STUDY)].plot(ax=ax, aspect=None, color=LAND, edgecolor=BORDER, linewidth=0.6, zorder=2)
    lk = lakes.cx[x0 - 3:x1 + 3, y0 - 3:y1 + 3]
    if len(lk):
        lk.plot(ax=ax, aspect=None, color=WATER, linewidth=0, zorder=3)
    K.frame(ax, extent)
    ax.set_facecolor(WATER)


def segs(d):
    out = []
    for g in d.geometry:
        if g is None:
            out.append(np.zeros((2, 2)))
        elif g.geom_type == "MultiLineString":
            out.append(np.vstack([np.asarray(p.coords) for p in g.geoms]))
        else:
            out.append(np.asarray(g.coords))
    return out


def region_label(ax, reg, y=0.97):
    ax.text(0.03, y, f"{reg} Africa", transform=ax.transAxes, fontsize=14, fontweight="bold", va="top", zorder=20,
            color=EAST if reg == "East" else SOUTH, bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.85))


def hub_dots(ax, reg=None, fs=8.5, label=True):
    for h, g in ART.groupby("hub"):
        if reg and g.region.iloc[0] != reg:
            continue
        x, y = g.start.iloc[0]
        ax.scatter([x], [y], s=26, color=INK, edgecolor="white", linewidth=0.8, zorder=12)
        if label and h != "johannesburg":
            ax.annotate(g.hub_name.iloc[0], (x, y), xytext=(5, 2), textcoords="offset points", fontsize=fs,
                        color=INK, fontweight="bold", zorder=13,
                        bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.75))


def two_axes(fig, top=0.86):
    return (fig.add_axes([0.02, 0.05, 0.42, top - 0.06]), fig.add_axes([0.47, 0.05, 0.42, top - 0.06]))


# street-level close-up, as in maps_regional.py
_BLD = None
FEAT = os.path.join(C.DATA, "osm_features.gpkg")
ROAD_W = {"motorway": 2.2, "trunk": 2.2, "primary": 2.0, "secondary": 1.5, "tertiary": 1.2,
          "residential": 0.7, "unclassified": 0.7, "service": 0.45, "track": 0.45}
MARK = {"police_post": "D", "weighbridge": "s", "traffic_signals": "P", "pedestrian_crossing": "o", "market": "^",
        "fuel": "v", "speed_hump": "X", "level_crossing": "*"}


def bld():
    global _BLD
    if _BLD is None:
        _BLD = pq.read_table(os.path.join(C.DATA, "buildings.parquet"),
                             columns=["latitude", "longitude", "area_in_meters"]).to_pandas().astype("float32")
    return _BLD


def street(ax, lon, lat, half, inch_per_deg, values=None, cmap=DCMAP, norm=DNORM):
    x0, x1, y0, y1 = lon - half, lon + half, lat - half, lat + half
    K.frame(ax, (x0, x1, y0, y1))
    ax.set_facecolor(LAND)
    rd = lambda layer: gpd.read_file(FEAT, layer=layer, bbox=(x0, y0, x1, y1))  # noqa: E731
    wa = rd("areas")
    for k, c_ in (("wetland", "#dcebf5"), ("market", "#f6e3c8")):
        if len(wa) and (wa.kind == k).any():
            wa[wa.kind == k].plot(ax=ax, aspect=None, color=c_, linewidth=0, zorder=1)
    ww = rd("waterways")
    if len(ww):
        ww.plot(ax=ax, aspect=None, color="#7fa9cf", linewidth=0.9, zorder=2)
    B = bld()
    bb = B[B.longitude.between(x0, x1) & B.latitude.between(y0, y1)]
    side = np.sqrt(bb.area_in_meters) / 111_320 * inch_per_deg * 72
    ax.scatter(bb.longitude, bb.latitude, s=np.maximum(side, 0.9) ** 2, marker="s", color="#9d988c", linewidths=0,
               zorder=3)
    rr = rd("roads")
    for hw, g in rr.groupby("highway"):
        if hw in ROAD_W:
            g.plot(ax=ax, aspect=None, color="#6f6c66", linewidth=ROAD_W[hw] * 0.8, zorder=4)
    pc = P.assign(v=P.per_km if values is None else values).cx[x0:x1, y0:y1]
    pc.plot(ax=ax, aspect=None, color=INK, linewidth=6.2, zorder=5)
    pc.dropna(subset=["v"]).plot(ax=ax, aspect=None, column="v", cmap=cmap, norm=norm, linewidth=4.2, zorder=6)
    pp = rd("points")
    pp["mkind"] = pp.kind.replace({"checkpoint_or_police": "police_post", "rumble_strip": "speed_hump"})
    for k, m in MARK.items():
        q = pp[pp.mkind == k]
        ax.scatter(q.geometry.x, q.geometry.y, marker=m, s=40, color="white", edgecolor=INK, linewidth=1.0, zorder=8)
    K.scalebar(ax, km=1)
    for s_ in ax.spines.values():
        s_.set_visible(True); s_.set_color(INK)


# ====================================================================== 4 street growth
_to_moll = Transformer.from_crs(4326, "ESRI:54009", always_xy=True)
_to_ll = Transformer.from_crs("ESRI:54009", 4326, always_xy=True)


def ghsl(year, x0, y0, x1, y1):
    mx0, my0 = _to_moll.transform(x0, y0)
    mx1, my1 = _to_moll.transform(x1, y1)
    out = []
    for path in sorted(glob.glob(os.path.join(C.DATA, "ghsl", f"built_s_{year}_*.tif"))):
        with rasterio.open(path) as src:
            b = src.bounds
            c = (max(mx0, b.left), max(my0, b.bottom), min(mx1, b.right), min(my1, b.top))
            if c[0] >= c[2] or c[1] >= c[3]:
                continue
            w = from_bounds(*c, transform=src.transform).round_offsets().round_lengths()
            a = src.read(1, window=w).astype(float)
            if src.nodata is not None:
                a[a == src.nodata] = 0
            rr, cc = np.meshgrid(np.arange(a.shape[0]), np.arange(a.shape[1]), indexing="ij")
            xs, ys = rasterio.transform.xy(src.window_transform(w), rr.ravel(), cc.ravel())
            lon, lat = _to_ll.transform(np.array(xs), np.array(ys))
            out.append(pd.DataFrame({"lon": lon, "lat": lat, "v": a.ravel()}))
    return pd.concat(out, ignore_index=True)


def rx4():
    G = O("growth_pieces.csv")
    d = P.merge(G[["corridor", "piece", "built_ha_2000", "built_ha_2020"]], how="left")
    grp = d.corridor + "_" + (d.piece // 4).astype(str)
    d["add2"] = (d.built_ha_2020 - d.built_ha_2000).groupby(grp).transform("sum")
    YEARS = [2000, 2005, 2010, 2015, 2020]
    HALF = 0.03
    fig = new_fig("Watching the roadside fill in", "Built-up land in 100 m cells (GHSL), 2000 to 2020, at the "
                  "fastest-growing stretch of road in each region; 6 km across")
    cmap = plt.get_cmap("YlOrBr")
    panels = []
    for k, reg in enumerate(("East", "Southern")):
        i = d[d.region == reg].add2.idxmax()
        lon, lat = CEN.x[i], CEN.y[i]
        x0, x1, y0, y1 = lon - HALF, lon + HALF, lat - HALF, lat + HALF
        ax = fig.add_axes([0.03 + k * 0.47, 0.05, 0.44, 0.74])
        K.frame(ax, (x0, x1, y0, y1))
        ax.set_facecolor(LAND)
        cells = [ghsl(y, x0, y0, x1, y1) for y in YEARS]
        inch = 0.44 * 12.8 / (2 * HALF)
        sq = (100 / 111_320 * inch * 72) ** 2
        sc = ax.scatter(cells[0].lon, cells[0].lat, c=cells[0].v, cmap=cmap, vmin=0, vmax=6000, s=sq * 1.15,
                        marker="s", linewidths=0, zorder=2)
        rr = gpd.read_file(FEAT, layer="roads", bbox=(x0, y0, x1, y1))
        for hw, g in rr.groupby("highway"):
            if hw in ROAD_W:
                g.plot(ax=ax, aspect=None, color="#4f4c46", linewidth=ROAD_W[hw] * 0.7, zorder=4)
        pc = P.cx[x0:x1, y0:y1]
        pc.plot(ax=ax, aspect=None, color=INK, linewidth=5, zorder=5)
        pc.plot(ax=ax, aspect=None, color=EAST if reg == "East" else SOUTH, linewidth=3.2, zorder=6)
        K.scalebar(ax, km=1)
        for s_ in ax.spines.values():
            s_.set_visible(True); s_.set_color(INK)
        place = d.place[i] if isinstance(d.place[i], str) else (nearest_place(lon, lat) or "unnamed place")
        ax.set_title(f"{reg} Africa: {place} ({SHORT.get(d.country[i], d.country[i])})\n{ART.road[d.corridor[i]]}",
                     fontsize=11, loc="left", color=EAST if reg == "East" else SOUTH, fontweight="bold")
        txt = ax.text(0.03, 0.96, "", transform=ax.transAxes, fontsize=13, fontweight="bold", va="top", zorder=20,
                      bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="none", alpha=0.9))
        panels.append((sc, cells, txt))
    yr = fig.text(0.97, 0.94, "", fontsize=30, fontweight="bold", color=INK, ha="right", va="top")
    W = Writer("rx4_street_growth")
    STEP = 2 * FPS
    timeline = [0.0] * FPS + [j / STEP for j in range(STEP * 4 + 1)] + [4.0] * (4 * FPS)
    for t in timeline:
        j = min(int(t), 3)
        w = ease(t - j) if t < 4 else 1.0
        for sc, cells, txt in panels:
            v = cells[j].v.to_numpy() + (cells[j + 1].v.to_numpy() - cells[j].v.to_numpy()) * w
            sc.set_array(v)
            ha = v.sum() / 1e4
            txt.set_text(f"{ha:,.0f} ha built up\n+{(ha / (cells[0].v.sum() / 1e4) - 1) * 100:.0f}% since 2000")
        yr.set_text(f"{YEARS[j] + (YEARS[j + 1] - YEARS[j]) * w:.0f}")
        W.add(fig)
    plt.close(fig)
    W.close()


# ====================================================================== 5 fly-through
def rx5():
    fig = new_fig("Leaving the capital, from space to street",
                  "Every road coloured by the minutes a loaded truck loses per km; zooming to the worst stretch "
                  "near each hub")
    B = bld()
    setups = []
    for k, (hub, reg) in enumerate((("nairobi", "East"), ("pretoria", "Southern"))):
        ax = fig.add_axes([0.03 + k * 0.47, 0.06, 0.44, 0.78])
        hx, hy = ART[ART.hub == hub].start.iloc[0]
        near = P[(P.hub == hub) & (np.hypot(CEN.x - hx, CEN.y - hy) < 0.25)]
        i = near.per_km.idxmax()
        sx, sy = CEN.x[i], CEN.y[i]
        basemap(ax, EXT[reg])
        d = P[P.region == reg]
        lc = LineCollection(segs(d), cmap=DCMAP, norm=DNORM, linewidths=1.6, zorder=6)
        lc.set_array(d.per_km.to_numpy())
        under = LineCollection(segs(d), colors=INK, linewidths=2.4, zorder=5)
        ax.add_collection(under); ax.add_collection(lc)
        win = 0.12
        bb = B[B.longitude.between(sx - win, sx + win) & B.latitude.between(sy - win, sy + win)]
        bsc = ax.scatter(bb.longitude, bb.latitude, s=1, marker="s", color="#9d988c", linewidths=0, zorder=4)
        rr = gpd.read_file(FEAT, layer="roads", bbox=(sx - win, sy - win, sx + win, sy + win))
        rr = rr[rr.highway.isin(ROAD_W)]
        rlc = LineCollection(segs(rr), colors="#6f6c66", linewidths=0.6, zorder=4.5)
        ax.add_collection(rlc)
        hub_dots(ax, reg, fs=9)
        region_label(ax, reg)
        place = P.place[i] if isinstance(P.place[i], str) else (nearest_place(sx, sy) or "unnamed place")
        lab = ax.text(0.03, 0.04, "", transform=ax.transAxes, fontsize=11, zorder=20, color=INK,
                      bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="none", alpha=0.9))
        ext0 = EXT[reg]
        setups.append(dict(ax=ax, lc=lc, under=under, bsc=bsc, area=np.sqrt(bb.area_in_meters.to_numpy()),
                           rlc=rlc, c0=((ext0[0] + ext0[1]) / 2, (ext0[2] + ext0[3]) / 2), w0=ext0[1] - ext0[0],
                           h0=ext0[3] - ext0[2], hub=(hx, hy), site=(sx, sy), lab=lab,
                           text=f"{place}, {ART.road[P.corridor[i]]}: {P.per_km[i]:.1f} truck min lost per km"))
    W = Writer("rx5_flythrough")
    HOLD0, Z1, Z2, HOLD1 = int(1.5 * FPS), 4 * FPS, 5 * FPS, 4 * FPS
    axw_in = 0.44 * 12.8
    for f in range(HOLD0 + Z1 + Z2 + HOLD1):
        for s_ in setups:
            if f < HOLD0:
                c, w = s_["c0"], s_["w0"]
            elif f < HOLD0 + Z1:   # to the hub, 1.2 degrees across
                t = ease((f - HOLD0) / Z1)
                c = (s_["c0"][0] + (s_["hub"][0] - s_["c0"][0]) * t, s_["c0"][1] + (s_["hub"][1] - s_["c0"][1]) * t)
                w = np.exp(np.log(s_["w0"]) + (np.log(1.2) - np.log(s_["w0"])) * t)
            else:                  # to the street, 0.04 degrees across
                t = ease((f - HOLD0 - Z1) / Z2)
                c = (s_["hub"][0] + (s_["site"][0] - s_["hub"][0]) * t, s_["hub"][1] + (s_["site"][1] - s_["hub"][1]) * t)
                w = np.exp(np.log(1.2) + (np.log(0.04) - np.log(1.2)) * t)
            h = w * s_["h0"] / s_["w0"]
            ax = s_["ax"]
            ax.set_xlim(c[0] - w / 2, c[0] + w / 2)
            ax.set_ylim(c[1] - h / 2, c[1] + h / 2)
            inch = axw_in / w
            lw = float(np.clip(1.6 * (s_["w0"] / w) ** 0.35, 1.6, 9))
            s_["lc"].set_linewidths(lw); s_["under"].set_linewidths(lw + 1.2)
            s_["bsc"].set_sizes(np.maximum(s_["area"] / 111_320 * inch * 72, 0.3) ** 2)
            s_["rlc"].set_linewidths(min(0.6 * (1.2 / w) ** 0.5, 2.0))
            s_["lab"].set_text(s_["text"] if f >= HOLD0 + Z1 + Z2 - FPS else f"{w * 111:,.0f} km across")
        W.add(fig)
    plt.close(fig)
    W.close()


# ====================================================================== 6 fuel meter
def rx6():
    F = O("fuel_co2_pieces.csv")
    D = {c: F[F.corridor == c].sort_values("piece").reset_index(drop=True) for c, _, _ in PAIR}
    KMAX = min(D[c].km_start.max() for c, _, _ in PAIR)
    fig = new_fig("The diesel the roadside burns", "One loaded truck on each trade corridor: extra litres from "
                  "braking and re-accelerating, against the same trip on open road")
    ax = fig.add_axes([0.07, 0.12, 0.58, 0.68])
    ymax = max(D[c][D[c].km_start <= KMAX].friction_litres.sum() for c, _, _ in PAIR) * 1.15
    ax.set_xlim(0, KMAX); ax.set_ylim(0, ymax)
    for s_ in ("top", "right"):
        ax.spines[s_].set_visible(False)
    ax.grid(axis="y", color="#e9e6df"); ax.tick_params(colors=INK2, labelsize=11, length=0)
    ax.set_xlabel("km from the hub", fontsize=11, color=INK2); ax.set_ylabel("extra litres of diesel", fontsize=11, color=INK2)
    rows = []
    for k, (c, lab, col) in enumerate(PAIR):
        d = D[c][D[c].km_start <= KMAX]
        x, y = d.km_start.to_numpy() + 0.5, d.friction_litres.cumsum().to_numpy()
        ln, = ax.plot([], [], color=col, lw=3)
        dot = ax.scatter([], [], s=90, color=col, zorder=5)
        fig.text(0.69, 0.72 - k * 0.3, lab, fontsize=12, color=col, fontweight="bold")
        big = fig.text(0.69, 0.62 - k * 0.3, "", fontsize=30, fontweight="bold", color=col)
        sub = fig.text(0.69, 0.555 - k * 0.3, "", fontsize=12, color=INK2)
        rows.append((x, y, ln, dot, big, sub))
    W = Writer("rx6_fuel_meter")
    DRIVE, HOLD = 12 * FPS, 4 * FPS
    for f in range(DRIVE + HOLD):
        k = KMAX * ease(f / DRIVE)
        for x, y, ln, dot, big, sub in rows:
            m = x <= k
            ln.set_data(x[m], y[m])
            yy = y[m][-1] if m.any() else 0
            dot.set_offsets([[k, yy]])
            big.set_text(f"+{yy:.0f} L")
            sub.set_text(f"{yy * 2.68:,.0f} kg CO₂ · {k:.0f} km")
        W.add(fig)
    plt.close(fig)
    W.close()


# ====================================================================== 7 safety sweep
def rx7():
    S = O("safety_pieces.csv")
    SCH = O("safety_schools.csv")
    D = {c: S[S.corridor == c].sort_values("piece").reset_index(drop=True) for c, _, _ in PAIR}
    KMAX = min(D[c].km_start.max() for c, _, _ in PAIR)
    fig = new_fig("Fast trucks past people", "People living within 300 m of the road, and the trucks' speed, "
                  "km by km; school stretches with fast trucks and no crossing marked ●")
    rows = []
    for k, (c, lab, col) in enumerate(PAIR):
        y0 = 0.50 - k * 0.38
        ax = fig.add_axes([0.04, y0, 0.64, 0.28])
        d = D[c][D[c].km_start <= KMAX]
        ax.set_xlim(0, KMAX); ax.axis("off")
        top = max(D[p].people_300m.quantile(0.995) for p, _, _ in PAIR)
        fast = d.truck_kmh > 50
        bars = ax.bar(d.km_start + 0.25, d.people_300m.clip(upper=top), width=0.5,
                      color=np.where(fast, col, "#cfc9bd"), linewidth=0)
        for b in bars:
            b.set_visible(False)
        ax.set_ylim(-top * 0.25, top * 1.15)
        ax.text(0, top * 1.12, lab, fontsize=13, color=col, fontweight="bold", va="top")
        sch = SCH[(SCH.corridor == c) & (SCH.km_start <= KMAX)].km_start.to_numpy()
        ss = ax.scatter(sch + 0.25, np.full(len(sch), -top * 0.12), s=30, color="#d9a441", edgecolor=INK,
                        linewidth=0.5, zorder=5)
        ss.set_visible(False)
        truck = ax.scatter([0], [-top * 0.12], marker=">", s=200, color=INK, zorder=6)
        big = fig.text(0.71, y0 + 0.16, "", fontsize=26, fontweight="bold", color=col)
        sub = fig.text(0.71, y0 + 0.05, "", fontsize=11.5, color=INK2)
        rows.append(dict(d=d.reset_index(drop=True), bars=bars, sch=sch, ss=ss, truck=truck, big=big, sub=sub, top=top))
    fig.text(0.04, 0.06, "Bars: people within 300 m per 500 m, coloured where trucks run above 50 km/h.",
             fontsize=10.5, color=INK2)
    W = Writer("rx7_safety_sweep")
    DRIVE, HOLD = 13 * FPS, 5 * FPS
    for f in range(DRIVE + HOLD):
        k = KMAX * ease(f / DRIVE)
        for r in rows:
            on = (r["d"].km_start <= k).to_numpy()
            for j in np.flatnonzero(on):
                r["bars"][j].set_visible(True)
            m = r["sch"] <= k
            r["ss"].set_offsets(np.c_[r["sch"][m] + 0.25, np.full(m.sum(), -r["top"] * 0.12)])
            r["ss"].set_visible(m.any())
            r["truck"].set_offsets([[k, -r["top"] * 0.12]])
            dd = r["d"][on]
            ppl = dd.people_300m[dd.truck_kmh > 50].sum()
            r["big"].set_text(f"{ppl:,.0f}")
            r["sub"].set_text(f"people passed at > 50 km/h\n{int(m.sum())} school stretches · {k:.0f} km")
        W.add(fig)
    plt.close(fig)
    W.close()


# ====================================================================== 8 cause waterfall
CAUSE_COL = {"roadside activity": "#c4532d", "hills (trucks)": "#8a6b4e", "weighbridge": "#17252a",
             "speed humps (assumed)": "#d9a441", "police posts": "#4e7c8a", "joining roads": "#3a7d5c",
             "signals and crossings": "#9fb3b0", "town speed limit": "#e89a7a", "curves": "#c9c2b8"}


def rx8():
    CA = O("travel_time_causes.csv")
    CA = CA[(CA.vehicle == "truck") & (CA.direction == "outbound") & CA.cause.isin(CAUSE_COL)]
    TOT = O("travel_time_totals.csv")
    TOT = TOT[(TOT.vehicle == "truck") & (TOT.direction == "outbound")].set_index("corridor")
    km = P.groupby("corridor").length_km.sum()
    reg = ART.region
    vals = {}
    for r in ("East", "Southern"):
        cs = [c for c in ART.index if reg[c] == r]
        kk = km[cs].sum() / 100
        by = CA[CA.corridor.isin(cs)].groupby("cause").minutes.sum().clip(lower=0) / kk
        vals[r] = (TOT.loc[cs, "open_road_minutes"].sum() / kk, by.reindex(list(CAUSE_COL)).fillna(0))
    fig = new_fig("How a truck's 100 km grows", "All roads pooled: open-road minutes per 100 km, then what each "
                  "cause adds (switched off one at a time)")
    axs = [fig.add_axes([0.20, 0.47, 0.75, 0.33]), fig.add_axes([0.20, 0.09, 0.75, 0.33])]
    xmax = max(v[0] + v[1].sum() for v in vals.values()) * 1.25
    objs = []
    for ax, r in zip(axs, ("East", "Southern")):
        col = EAST if r == "East" else SOUTH
        base, by = vals[r]
        ax.set_xlim(0, xmax); ax.set_ylim(-0.6, 1.0)
        ax.axis("off")
        ax.text(-0.01, 0.2, f"{r}\nAfrica", transform=ax.get_yaxis_transform(), ha="right", va="center",
                fontsize=15, fontweight="bold", color=col)
        b0 = ax.barh(0.2, 0, height=0.55, color="#b8c7c4")
        segs_ = [ax.barh(0.2, 0, left=0, height=0.55, color=CAUSE_COL[c]) for c in by.index]
        tot = ax.text(0, 0.2, "", va="center", fontsize=14, fontweight="bold", color=INK)
        cap = ax.text(0, -0.35, "", fontsize=11, color=INK2)
        objs.append((base, by, b0, segs_, tot, cap))
    fig.legend(handles=[Patch(color="#b8c7c4", label="open road")] +
               [Patch(color=c, label=k) for k, c in CAUSE_COL.items()], loc="lower left", ncol=5, frameon=False,
               fontsize=9, bbox_to_anchor=(0.02, 0.02))
    W = Writer("rx8_cause_waterfall")
    n = len(CAUSE_COL)
    STEP = int(0.8 * FPS)
    total = FPS + STEP * (n + 1) + 5 * FPS
    for f in range(total):
        for base, by, b0, segs_, tot, cap in objs:
            t0 = ease((f - FPS * 0.5) / STEP)
            b0[0].set_width(base * t0)
            left, lastc = base, None
            for j, (c, v) in enumerate(by.items()):
                t = ease((f - FPS - STEP * (j + 1)) / STEP)
                segs_[j][0].set_x(left); segs_[j][0].set_width(v * t)
                if t > 0:
                    lastc = (c, v)
                left += v * t
            tot.set_position((left + xmax * 0.01, 0.2))
            tot.set_text(f"{left:.0f} min" + (f"  (+{left - base:.0f})" if left > base + 0.5 else ""))
            cap.set_text(f"+ {lastc[0]}: {lastc[1]:.1f} min" if lastc and f < total - 5 * FPS else
                         ("" if not lastc else f"friction adds {left / base * 100 - 100:.0f}% to open-road time"))
        W.add(fig)
    plt.close(fig)
    W.close()


# ====================================================================== 9 road-type reveal
def rx9():
    fig = new_fig("Linear towns", "Every road out of 12 hubs, coloured by what lines it, one hub at a time "
                  "(road types clustered jointly across the region)")
    axE, axS = two_axes(fig)
    tc = P.road_type.map(TYPE_COL).fillna("#d9d4c7")
    LC, TX = {}, {}
    for ax, reg in ((axE, "East"), (axS, "Southern")):
        basemap(ax, EXT[reg])
        d = P[P.region == reg]
        ax.add_collection(LineCollection(segs(d), colors=INK, linewidths=3.0, zorder=5))
        lc = LineCollection(segs(d), colors=["#9a978f"] * len(d), linewidths=2.2, zorder=6)
        ax.add_collection(lc)
        hub_dots(ax, reg)
        region_label(ax, reg)
        TX[reg] = ax.text(0.03, 0.88, "", transform=ax.transAxes, fontsize=12.5, va="top", zorder=20, color=INK,
                          bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="none", alpha=0.9))
        LC[reg] = (lc, d)
    fig.legend(handles=[Patch(color=c, label=k) for k, c in TYPE_COL.items()], loc="upper left", frameon=False,
               fontsize=11, bbox_to_anchor=(0.895, 0.80))
    order = [h for r in ("East", "Southern") for h in ART[ART.region == r].hub.unique()]
    W = Writer("rx9_road_type_reveal")
    STEP = FPS
    done = set()
    for f in range(FPS + STEP * len(order) + 5 * FPS):
        k = (f - FPS) // STEP
        if 0 <= k < len(order):
            done.add(order[k])
        for reg, (lc, d) in LC.items():
            on = d.hub.isin(done).to_numpy()
            lc.set_color(np.where(on, tc[d.index], "#9a978f"))
            if on.any():
                dd = d[on]
                L = dd.length_km.sum()
                sh = dd[dd.road_type.isin(["roadside settlement", "town"])].length_km.sum() / L
                cur = order[min(max(k, 0), len(order) - 1)]
                name = ART[ART.hub == cur].hub_name.iloc[0] if ART[ART.hub == cur].region.iloc[0] == reg else None
                TX[reg].set_text((f"now: {name}\n" if name and f < FPS + STEP * len(order) else "") +
                                 f"settlement or town: {sh:.0%}\nof {L:,.0f} km shown")
        W.add(fig)
    plt.close(fig)
    W.close()


# ====================================================================== 10 mapping gap
def rx10():
    kinds = ["traffic_signals", "pedestrian_crossing", "speed_hump", "rumble_strip", "checkpoint_or_police",
             "weighbridge", "level_crossing"]
    pts = gpd.read_file(FEAT, layer="points")
    pts = pts[pts.kind.isin(kinds)].to_crs(C.UTM)
    pp = P.to_crs(C.UTM)[["region", "geometry"]]
    j = gpd.sjoin_nearest(pts, pp, max_distance=150, how="inner").drop_duplicates("osm_id").to_crs(4326)
    rng = np.random.default_rng(3)
    j = j.iloc[rng.permutation(len(j))]
    km = P.groupby("region").length_km.sum()
    fig = new_fig("The mapping gap", "Signals, crossings, humps, police posts and weighbridges recorded in "
                  "OpenStreetMap along the 54 roads, appearing in random order")
    axE, axS = two_axes(fig)
    SC, TX, N = {}, {}, {}
    for ax, reg in ((axE, "East"), (axS, "Southern")):
        basemap(ax, EXT[reg])
        d = P[P.region == reg]
        ax.add_collection(LineCollection(segs(d), colors="#cfc9bd", linewidths=1.8, zorder=5))
        hub_dots(ax, reg)
        region_label(ax, reg)
        q = j[j.region == reg]
        SC[reg] = (ax.scatter([], [], s=9, color=EAST if reg == "East" else SOUTH, zorder=8, linewidths=0), q)
        TX[reg] = ax.text(0.03, 0.88, "", transform=ax.transAxes, fontsize=13, va="top", zorder=20, color=INK,
                          bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="none", alpha=0.9))
        N[reg] = len(q)
    fig.text(0.03, 0.015, "Part of the gap is real (Gauteng's signalised roads); much of it is mapping.",
             fontsize=11, color=INK2)
    W = Writer("rx10_mapping_gap")
    GROW, HOLD = 9 * FPS, 5 * FPS
    for f in range(FPS + GROW + HOLD):
        t = ease((f - FPS) / GROW)
        for reg, (sc, q) in SC.items():
            n = int(len(q) * t)
            sc.set_offsets(np.c_[q.geometry.x.to_numpy()[:n], q.geometry.y.to_numpy()[:n]] if n else np.zeros((0, 2)))
            TX[reg].set_text(f"{n:,} controls mapped\n{n / km[reg] * 100:.1f} per 100 km of road")
        W.add(fig)
    plt.close(fig)
    W.close()


# ====================================================================== 11 rain year
def rx11():
    RM = O("reliability_monthly.csv")
    RM = RM[RM.vehicle == "truck"]
    best = RM.groupby("corridor").mean_min.transform("min")
    RM = RM.assign(slow=(RM.mean_min / best - 1) * 100)
    piv = RM.pivot(index="corridor", columns="month", values="slow")
    fig = new_fig("A year of rain on the roads", "How much slower the average truck trip is each month than in "
                  "that road's driest month (CHIRPS 2006–2025)")
    axE = fig.add_axes([0.02, 0.05, 0.36, 0.80])
    axS = fig.add_axes([0.39, 0.05, 0.36, 0.80])
    cmap = ListedColormap(["#f2efe6", "#cfe0ec", "#9fc2db", "#6a9dc4", "#3c74a6", "#1b4a78"])
    norm = BoundaryNorm([-1, 0.5, 1, 2, 3, 4, 100], cmap.N)
    LC = {}
    for ax, reg in ((axE, "East"), (axS, "Southern")):
        basemap(ax, EXT[reg])
        d = P[P.region == reg]
        ax.add_collection(LineCollection(segs(d), colors=INK, linewidths=3.2, zorder=5))
        lc = LineCollection(segs(d), cmap=cmap, norm=norm, linewidths=2.4, zorder=6)
        ax.add_collection(lc)
        hub_dots(ax, reg, fs=7.5)
        region_label(ax, reg)
        LC[reg] = (lc, d.corridor.to_numpy())
    cax = fig.add_axes([0.79, 0.52, 0.18, 0.30])
    reg_of = ART.region.reindex(piv.index)
    for r, col in (("East", EAST), ("Southern", SOUTH)):
        cax.plot(range(1, 13), piv[reg_of == r].mean(), color=col, lw=2.5, label=f"{r} average")
    dots = [cax.scatter([], [], s=60, color=c, zorder=5) for c in (EAST, SOUTH)]
    cax.set_xticks(range(1, 13)); cax.set_xticklabels(list("JFMAMJJASOND"), fontsize=9)
    cax.tick_params(colors=INK2, labelsize=9, length=0)
    for s_ in ("top", "right"):
        cax.spines[s_].set_visible(False)
    cax.set_ylabel("% slower", fontsize=9, color=INK2)
    cax.legend(frameon=False, fontsize=9, loc="upper left")
    kax = fig.add_axes([0.80, 0.10, 0.15, 0.025])
    kax.imshow(np.arange(6)[None, :], cmap=cmap, aspect="auto", extent=(0, 6, 0, 1))
    kax.set_yticks([]); kax.set_xticks(np.arange(6) + 0.5)
    kax.set_xticklabels(["<0.5", "0.5–1", "1–2", "2–3", "3–4", ">4"], fontsize=8)
    kax.tick_params(length=0)
    kax.set_title("% slower than the driest month", fontsize=9, color=INK2, loc="left")
    mon = fig.text(0.79, 0.88, "", fontsize=26, fontweight="bold", color=INK)
    MN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
    W = Writer("rx11_rain_year")
    STEP = int(1.1 * FPS)
    for f in range(STEP * 12 + 3 * FPS):
        t = min(f / STEP, 11.999)
        m0 = int(t); w = ease(t - m0)
        m1 = (m0 + 1) % 12
        vm = piv[m0 + 1] + (piv[m1 + 1] - piv[m0 + 1]) * w
        for reg, (lc, cor) in LC.items():
            lc.set_array(vm.reindex(cor).to_numpy())
        for dot, r in zip(dots, ("East", "Southern")):
            a = piv[reg_of == r].mean()
            dot.set_offsets([[m0 + 1 + w, a[m0 + 1] + (a[m1 + 1] - a[m0 + 1]) * w]])
        mon.set_text(MN[m0 if w < 0.5 else m1])
        W.add(fig)
    plt.close(fig)
    W.close()


# ====================================================================== 12 fixes
def rx12():
    SC = O("scenarios.csv")
    SC = SC[SC.vehicle == "truck"]
    TOT = O("travel_time_totals.csv")
    TOT = TOT[(TOT.vehicle == "truck") & (TOT.direction == "outbound")].set_index("corridor")
    exc = TOT.minutes - TOT.open_road_minutes
    FIX = {"wim": "Weigh-in-motion at weighbridges", "no_police": "No routine police stops",
           "bypass_2": "Bypass the 2 worst towns", "service_20km": "Service roads, worst 20 km",
           "service_all": "Service roads, every settlement", "all": "All together (WIM, police, bypasses, 20 km)"}
    share = {}
    for r in ("East", "Southern"):
        cs = [c for c in ART.index if ART.region[c] == r]
        e = exc[cs].sum()
        share[r] = {k: SC[(SC.scenario == k) & SC.corridor.isin(cs)].minutes_saved.sum() / e * 100 for k in FIX}
    fig = new_fig("What would fixing it save?", "Share of all truck delay (light traffic) each fix removes, "
                  "all roads pooled; travel-time model with the fix applied")
    ax = fig.add_axes([0.33, 0.10, 0.60, 0.72])
    y = np.arange(len(FIX))
    bE = ax.barh(y - 0.2, 0, height=0.38, color=EAST, label="East Africa")
    bS = ax.barh(y + 0.2, 0, height=0.38, color=SOUTH, label="Southern Africa")
    tE = [ax.text(0, yy - 0.2, "", va="center", fontsize=11, color=INK) for yy in y]
    tS = [ax.text(0, yy + 0.2, "", va="center", fontsize=11, color=INK) for yy in y]
    ax.set_yticks(y); ax.set_yticklabels(list(FIX.values()), fontsize=12, color=INK)
    ax.invert_yaxis()
    xm = max(max(v.values()) for v in share.values()) * 1.2
    ax.set_xlim(0, xm)
    for s_ in ("top", "right", "left"):
        ax.spines[s_].set_visible(False)
    ax.grid(axis="x", color="#e9e6df"); ax.tick_params(length=0, colors=INK2, labelsize=10)
    ax.set_xlabel("% of truck delay removed", fontsize=11, color=INK2)
    ax.legend(frameon=False, fontsize=11, loc="upper right")
    W = Writer("rx12_fixes")
    STEP = int(0.9 * FPS)
    for f in range(FPS + STEP * len(FIX) + 5 * FPS):
        for j, k in enumerate(FIX):
            t = ease((f - FPS - j * STEP) / STEP)
            for bars, txts, r, dy in ((bE, tE, "East", -0.2), (bS, tS, "Southern", 0.2)):
                v = share[r][k] * t
                bars[j].set_width(v)
                txts[j].set_position((v + xm * 0.01, j + dy))
                txts[j].set_text(f"{share[r][k]:.0f}%" if t >= 1 else "")
        W.add(fig)
    plt.close(fig)
    W.close()


# ====================================================================== 13 bottleneck tour
def rx13():
    import re
    HH = H.copy()
    wb = HH.main_causes.map(lambda s: float(m.group(1)) if (m := re.search(r"weighbridge ([\d.]+)", s)) else 0.0)
    HH["other"] = HH.truck_excess_min - wb
    pick = HH.loc[HH.groupby("country").other.idxmax()].sort_values(["region", "other"], ascending=[True, False])
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100, facecolor=SURF)
    W = Writer("rx13_bottleneck_tour")
    for n, r in enumerate(pick.itertuples(), 1):
        fig.clf()
        fig.text(0.03, 0.94, "Ten countries, ten bottlenecks", fontsize=23, fontweight="bold", color=INK)
        fig.text(0.03, 0.897, "The 2 km stretch in each country where the roadside itself costs a loaded truck most "
                 "(weighbridge stops left out)", fontsize=12, color=INK2)
        fig.text(0.97, 0.015, FOOT, fontsize=8.5, color=INK2, ha="right")
        reg = r.region
        ov = fig.add_axes([0.02, 0.06, 0.36, 0.78])
        basemap(ov, EXT[reg])
        d = P[P.region == reg]
        ov.add_collection(LineCollection(segs(d), colors="#b8b2a6", linewidths=1.4, zorder=5))
        hub_dots(ov, reg, fs=7.5)
        ov.scatter([r.lon], [r.lat], s=240, facecolor="none", edgecolor=EAST if reg == "East" else SOUTH, lw=3,
                   zorder=15)
        ov.scatter([r.lon], [r.lat], s=30, color=INK, zorder=16)
        region_label(ov, reg)
        ax = fig.add_axes([0.40, 0.10, 0.36, 0.74])
        street(ax, r.lon, r.lat, 0.018, 0.36 * 12.8 / 0.036)
        col = EAST if reg == "East" else SOUTH
        fig.text(0.78, 0.80, f"{n} / {len(pick)}", fontsize=14, color=INK2)
        fig.text(0.78, 0.72, SHORT.get(r.country, r.country), fontsize=24, fontweight="bold", color=col)
        fig.text(0.78, 0.655, r.place_name, fontsize=15, color=INK)
        fig.text(0.78, 0.585, f"{ART.road[r.corridor]}\nkm {r.km_from:.0f}–{r.km_to:.0f} · {r.road_type}",
                 fontsize=11, color=INK2, linespacing=1.4)
        fig.text(0.78, 0.47, f"+{r.truck_excess_min:.1f} min", fontsize=28, fontweight="bold", color=col)
        fig.text(0.78, 0.43, "for a loaded truck over 2 km", fontsize=11, color=INK2)
        causes = "\n".join("· " + c for c in r.main_causes.split("; "))
        fig.text(0.78, 0.38, "main causes (min):\n" + causes, fontsize=11, color=INK, va="top", linespacing=1.45)
        fig.legend(handles=[Patch(color=DCMAP(i), label=l) for i, l in
                            enumerate(["< 0.25", "0.25–0.5", "0.5–1", "1–2", "2–4", "> 4"])],
                   title="truck min lost per km", loc="lower left", bbox_to_anchor=(0.775, 0.06), ncol=2,
                   frameon=False, fontsize=8.5, title_fontsize=9)
        W.add(fig, repeat=int(3.2 * FPS))
        print("slide", n, r.country, flush=True)
    plt.close(fig)
    W.close()


RUN = {4: rx4, 5: rx5, 6: rx6, 7: rx7, 8: rx8, 9: rx9, 10: rx10, 11: rx11, 12: rx12, 13: rx13}
for k in ([int(a) for a in sys.argv[1:]] or sorted(RUN)):
    RUN[k]()
