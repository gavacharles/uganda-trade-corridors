"""Shared map layers and helpers for 11_maps.py, 12_corridor_atlas.py and 13_animations.py.

Loads the study data once on import: land and lakes, districts, corridor centrelines,
the 500 m pieces with modelled delay, hotspots, OSM features and buildings.
"""
import glob, os, sys
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
import matplotlib
matplotlib.use("Agg")
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from pyproj import Transformer
from rasterio.windows import from_bounds

import config as C

import cartography as K  # noqa: E402  (map furniture, shared with the accessibility paper)

INK, INK2, SURF = K.INK, K.INK2, K.SURF
WATER, NEIGHBOUR, LAND = "#c9dcee", "#e6e4de", "#fbfaf7"
BUILDING, ROAD, STREAM = "#9d988c", "#6f6c66", "#7fa9cf"
COL = dict(zip(C.CORRIDORS, ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#8a5cc7"]))  # categorical slots 1-5
DELAY_BOUNDS = [0, 0.25, 0.5, 1, 2, 4, 100]  # minutes lost per km
DELAY_LABELS = ["< 0.25", "0.25–0.5", "0.5–1", "1–2", "2–4", "> 4"]
DELAY_CMAP = ListedColormap(["#f3eee6", "#fde6da", "#f6b596", "#eb6834", "#b8491c", "#7c2e0f"])
DELAY_NORM = BoundaryNorm(DELAY_BOUNDS, DELAY_CMAP.N)
TYPE_COL = {"open road": "#a9c8ec", "roadside settlement": "#3574c4", "town": "#0d2d57"}
TOWNS = {"Kampala": (32.5825, 0.3136), "Jinja": (33.2040, 0.4390), "Gulu": (32.2990, 2.7740),
         "Masaka": (31.7350, -0.3330), "Mbarara": (30.6550, -0.6070), "Kabale": (29.9856, -1.2486),
         "Hoima": (31.3520, 1.4320), "Luweero": (32.4730, 0.8490), "Mukono": (32.7550, 0.3530),
         "Lugazi": (32.9420, 0.3700), "Mityana": (32.0420, 0.4170), "Karuma": (32.2380, 2.2480),
         "Lukaya": (31.8750, -0.1440), "Iganga": (33.4690, 0.6090), "Bugiri": (33.7420, 0.5680),
         "Tororo": (34.1810, 0.6930), "Kafu": (32.0560, 1.5700), "Bweyale": (32.1100, 1.8200),
         "Atiak": (32.1200, 3.2600), "Ntungamo": (30.2640, -0.8790), "Lyantonde": (31.1580, -0.4040),
         "Kiboga": (31.7730, 0.9160), "Kakumiro": (31.3230, 0.7810), "Nakasongola": (32.4650, 1.3090),
         "Mpigi": (32.3140, 0.2250), "Kyotera": (31.5400, -0.6200)}
COUNTRIES = {"KENYA": (34.75, 1.9), "SOUTH SUDAN": (31.2, 4.1), "DR CONGO": (29.75, 2.0),
             "RWANDA": (29.8, -1.55), "TANZANIA": (31.2, -1.35)}
LAKES = {"Lake Victoria": (32.9, -0.55), "Lake Albert": (30.95, 1.75), "Lake Kyoga": (33.0, 1.6)}
EXT_UG = (29.45, 35.15, -1.62, 4.85)
PLACE_RANK = {"city": 0, "town": 1, "suburb": 2, "village": 3, "neighbourhood": 4, "locality": 5, "hamlet": 6}

# Lakes: Natural Earth 1:10m (public domain), downloaded to data/ne_lakes/. Land = Uganda minus lakes.
districts = gpd.read_file(C.DISTRICTS).to_crs(4326)
country = gpd.GeoSeries([districts.union_all()], crs=4326)
lakes = gpd.read_file(os.path.join(C.DATA, "ne_lakes", "ne_10m_lakes.shp")).to_crs(4326).cx[28.5:36, -3:5.5].geometry
land = gpd.GeoDataFrame(geometry=country.difference(lakes.union_all()), crs=4326)
cl = gpd.read_file(C.PROBES_GPKG, layer="centrelines")
cl = cl[cl.direction == "outbound"].set_index("corridor")
typed = pd.read_csv(os.path.join(C.OUTPUTS, "pieces_typed.csv"))
tt = pd.read_csv(os.path.join(C.OUTPUTS, "travel_time_pieces.csv"))
pieces = (gpd.read_file(os.path.join(C.DATA, "pieces.gpkg"))
          .merge(tt[["corridor", "piece", "car_excess_min", "truck_excess_min", "truck_outbound_min"]])
          .merge(typed[["corridor", "piece", "road_type"]]))
pieces["truck_min_per_km"] = pieces.truck_excess_min / 0.5
pieces["car_min_per_km"] = pieces.car_excess_min / 0.5
hot = pd.read_csv(os.path.join(C.OUTPUTS, "hotspots.csv"))
growth = pd.read_csv(os.path.join(C.OUTPUTS, "growth_pieces.csv"))
_feat = os.path.join(C.DATA, "osm_features.gpkg")
fpts = gpd.read_file(_feat, layer="points")
fpts["mkind"] = fpts.kind.replace({"checkpoint_or_police": "police_post", "rumble_strip": "speed_hump"})
froads = gpd.read_file(_feat, layer="roads")
fwater = gpd.read_file(_feat, layer="waterways")
fareas = gpd.read_file(_feat, layer="areas")
buildings = pd.read_parquet(os.path.join(C.DATA, "buildings.parquet"))

ROAD_W = {"motorway": 2.2, "trunk": 2.2, "primary": 2.0, "secondary": 1.5, "tertiary": 1.2,
          "residential": 0.7, "unclassified": 0.7, "service": 0.45, "track": 0.45}
MARK = {"police_post": ("D", "police post"), "weighbridge": ("s", "weighbridge"), "traffic_signals": ("P", "signals"),
        "pedestrian_crossing": ("o", "pedestrian crossing"), "market": ("^", "market"), "fuel": ("v", "fuel station"),
        "speed_hump": ("X", "speed hump (OSM)"), "level_crossing": ("*", "level crossing")}
CLOSEUP_LEGEND = ([Line2D([], [], marker="s", linestyle="none", markersize=5, color=BUILDING, label="building (Open Buildings)"),
                   Line2D([], [], color=ROAD, linewidth=1.2, label="other roads (OSM)"),
                   Line2D([], [], color=STREAM, linewidth=1.2, label="waterway"),
                   Patch(color="#dcebf5", label="wetland"), Patch(color="#f6e3c8", label="market area")]
                  + [Line2D([], [], marker=m, linestyle="none", markersize=6, markerfacecolor="white",
                            markeredgecolor=INK, label=l) for m, l in MARK.values()])


def base(ax, extent=EXT_UG, districts_on=True):
    K.frame(ax, extent)
    land.plot(ax=ax, aspect=None, color=LAND, linewidth=0)
    lakes.plot(ax=ax, aspect=None, color=WATER, linewidth=0.3, edgecolor="#a9c3dc")
    if districts_on:
        districts.boundary.plot(ax=ax, aspect=None, color="#dedbd3", linewidth=0.35)
    country.boundary.plot(ax=ax, aspect=None, color="#8d8a82", linewidth=0.9)
    K.frame(ax, extent)
    ax.set_facecolor(NEIGHBOUR)  # outside Uganda; lakes are drawn in WATER


def corridor_line(ax, corridor, color, lw=2.6, z=5):
    g = cl.loc[[corridor]].geometry
    g.plot(ax=ax, aspect=None, color=INK, linewidth=lw + 1.6, zorder=z)
    g.plot(ax=ax, aspect=None, color=color, linewidth=lw, zorder=z + 1)


def delay_line(ax, corridor, lw=3.2, z=6, column="truck_min_per_km"):
    cl.loc[[corridor]].plot(ax=ax, aspect=None, color=INK, linewidth=lw + 1.6, zorder=z)
    p = pieces[pieces.corridor == corridor].sort_values(column)
    p.plot(ax=ax, aspect=None, column=column, cmap=DELAY_CMAP, norm=DELAY_NORM, linewidth=lw, zorder=z + 1)


def town_labels(ax, names, size=8.5, extent=None):
    for n in names:
        x, y = TOWNS[n]
        if extent and not (extent[0] < x < extent[1] and extent[2] < y < extent[3]):
            continue
        big = n == "Kampala"
        ax.plot(x, y, "o", markersize=7 if big else 4.5, color=INK, markeredgecolor="white", markeredgewidth=0.8,
                zorder=10)
        ax.annotate(n, (x, y), xytext=(-7, -9) if big else (5, 4), textcoords="offset points",
                    ha="right" if big else "left", va="top" if big else "bottom",
                    fontsize=size + (2 if big else 0), color=INK, zorder=11, fontweight="bold" if big else "normal",
                    bbox=dict(boxstyle="round,pad=0.12", fc=LAND, ec="none", alpha=0.75))


def border_marks(ax, size=8):
    """A bar across each corridor end that is a border crossing, labelled."""
    for corridor, cfg in C.CORRIDORS.items():
        if "border" not in cfg["label"]:
            continue
        x, y = cfg["end"]
        ax.plot(x, y, marker="|", markersize=14, markeredgewidth=3, color=INK, zorder=12)
        ax.annotate(f"{cfg['short']}\nborder", (x, y), xytext=(6, -2), textcoords="offset points", fontsize=size - 1,
                    color=INK, va="top", zorder=12, bbox=dict(boxstyle="round,pad=0.1", fc=LAND, ec="none", alpha=0.7))


def context_labels(ax):
    for n, (x, y) in COUNTRIES.items():
        ax.text(x, y, n, fontsize=8, color="#9a978f", ha="center", va="center", clip_on=True)
    for n, (x, y) in LAKES.items():
        ax.text(x, y, n, fontsize=7.5, color="#4f7497", ha="center", va="center", style="italic", clip_on=True)


def delay_key(fig, ax, label="truck minutes lost per km\n(vs open road, light traffic)"):
    return K.key(fig, ax, DELAY_CMAP, DELAY_NORM, DELAY_BOUNDS, label, labels=DELAY_LABELS)


def fit_extent(bounds, box_w, box_h, pad=0.08):
    """Lon/lat extent around bounds, padded, with the aspect of a box_w x box_h axes box."""
    x0, y0, x1, y1 = bounds
    w, h = (x1 - x0) * (1 + 2 * pad), (y1 - y0) * (1 + 2 * pad)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    k = 1 / np.cos(np.radians(cy))  # map units: 1 deg lat is k times longer on the page than 1 deg lon
    if h * k / w > box_h / box_w:
        w = h * k * box_w / box_h
    else:
        h = w * box_h / box_w / k
    return (cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2)


def closeup(ax, corridor, lon, lat, half, inch_per_deg, title, info):
    """Street-level view: buildings, OSM roads, water, controls, the corridor coloured by delay."""
    x0, x1, y0, y1 = lon - half, lon + half, lat - half, lat + half
    K.frame(ax, (x0, x1, y0, y1))
    ax.set_facecolor(LAND)
    wa = fareas.cx[x0:x1, y0:y1]
    wa[wa.kind == "wetland"].plot(ax=ax, aspect=None, color="#dcebf5", linewidth=0, zorder=1)
    wa[wa.kind == "market"].plot(ax=ax, aspect=None, color="#f6e3c8", linewidth=0, zorder=1)
    fwater.cx[x0:x1, y0:y1].plot(ax=ax, aspect=None, color=STREAM, linewidth=0.9, zorder=2)
    bb = buildings[buildings.longitude.between(x0, x1) & buildings.latitude.between(y0, y1)]
    side_pt = np.sqrt(bb.area_in_meters) / 111_320 * inch_per_deg * 72
    ax.scatter(bb.longitude, bb.latitude, s=np.maximum(side_pt, 0.9) ** 2, marker="s", color=BUILDING,
               linewidths=0, zorder=3)
    rr = froads.cx[x0:x1, y0:y1]
    for hw, g in rr.groupby("highway"):
        if hw in ROAD_W:
            g.plot(ax=ax, aspect=None, color=ROAD, linewidth=ROAD_W[hw] * 0.8, zorder=4)
    pc = pieces[pieces.corridor == corridor].cx[x0:x1, y0:y1]
    pc.plot(ax=ax, aspect=None, color=INK, linewidth=6.2, zorder=5)
    pc.plot(ax=ax, aspect=None, column="truck_min_per_km", cmap=DELAY_CMAP, norm=DELAY_NORM, linewidth=4.2, zorder=6)
    pp = fpts.cx[x0:x1, y0:y1]
    for k, (m, _) in MARK.items():
        q = pp[pp.mkind == k]
        ax.scatter(q.geometry.x, q.geometry.y, marker=m, s=46, color="white", edgecolor=INK, linewidth=1.1, zorder=8)
    place_labels(ax, x0, x1, y0, y1)
    K.scalebar(ax, km=1)
    ax.set_title(title, loc="left", fontsize=9.5, color=INK)
    if info:
        ax.text(0, -0.02, info, transform=ax.transAxes, fontsize=7.4, color=INK, va="top", ha="left", zorder=15,
                linespacing=1.3)  # below the map, so it hides nothing


def numbered_markers(ax, xs, ys, labels, size=8):
    """Numbered circles for hotspots: a dot at the true place, the number moved clear of
    neighbours with a leader line when they crowd (e.g. at the Kampala end)."""
    ax.scatter(xs, ys, s=16, color=INK, zorder=12, linewidths=0)
    ts = [ax.text(x, y, str(t), ha="center", va="center", fontsize=size, color=INK, fontweight="bold", zorder=13,
                  bbox=dict(boxstyle="circle,pad=0.25", fc="white", ec=INK, lw=1.2))
          for x, y, t in zip(xs, ys, labels)]
    K.adjust_text(ts, x=list(xs), y=list(ys), ax=ax, expand=(1.5, 1.6), only_move={"text": "xy"},
                  arrowprops=dict(arrowstyle="-", color=INK, lw=0.8))


def place_labels(ax, x0, x1, y0, y1, n=9, size=7):
    """Names of nearby settlements (OSM place nodes), largest first, moved apart to avoid overlap."""
    pl = fpts[(fpts.kind == "place") & fpts.name.notna()].cx[x0:x1, y0:y1]
    pl = pl[~pl.name.str.contains("/")]
    if not len(pl):
        return
    pl = pl.assign(rank=pl.place.map(PLACE_RANK).fillna(9)).sort_values("rank").drop_duplicates("name").head(n)
    ax.scatter(pl.geometry.x, pl.geometry.y, s=9, color=INK, zorder=14, linewidths=0)
    ts = [ax.text(x, y, t, fontsize=size + (1 if r <= 1 else 0), color=INK, zorder=16, style="italic",
                  fontweight="bold" if r <= 1 else "normal",
                  bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.8))
          for x, y, t, r in zip(pl.geometry.x, pl.geometry.y, pl.name, pl["rank"])]
    K.adjust_text(ts, x=list(pl.geometry.x), y=list(pl.geometry.y), ax=ax, expand=(1.2, 1.4),
                  arrowprops=dict(arrowstyle="-", color=INK2, lw=0.5))


def hotspot_info(r):
    d = typed[(typed.corridor == r.corridor) & typed.km_mid.between(r.km_from, r.km_to)]
    causes = ("\nmain causes (min):\n  " + r.main_causes.replace("; ", "\n  ")
              if isinstance(getattr(r, "main_causes", None), str) else "")
    return (f"{r.road_type} · truck +{r.truck_excess_min:.1f} min · car +{r.car_excess_min:.1f} min\n"
            f"{int(d.buildings_100m.sum()):,} buildings within 100 m · "
            f"{int((d.junctions_major + d.junctions_minor).sum())} joining roads\n"
            f"{int(d.police_posts.sum())} police post(s) · {int(d.weighbridges.sum())} weighbridge(s){causes}")


def hotspot_point(corridor, km):
    line = gpd.GeoSeries([cl.loc[corridor].geometry], crs=4326).to_crs(C.UTM).iloc[0]
    p = gpd.GeoSeries([line.interpolate(km * 1000)], crs=C.UTM).to_crs(4326).iloc[0]
    return p.x, p.y


_to_moll = Transformer.from_crs(4326, "ESRI:54009", always_xy=True)
_to_ll = Transformer.from_crs("ESRI:54009", 4326, always_xy=True)


def ghsl_cells(year, x0, y0, x1, y1):
    """GHSL built-up (m2 per 100 m cell) for a lon/lat box, as cell-centre lon, lat, v."""
    mx0, my0 = _to_moll.transform(x0, y0)
    mx1, my1 = _to_moll.transform(x1, y1)
    out = []
    for path in glob.glob(os.path.join(C.DATA, "ghsl", f"built_s_{year}_*.tif")):
        with rasterio.open(path) as src:
            bnd = src.bounds
            c = (max(mx0, bnd.left), max(my0, bnd.bottom), min(mx1, bnd.right), min(my1, bnd.top))
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
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=["lon", "lat", "v"])
