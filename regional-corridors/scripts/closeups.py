"""Bottleneck close-ups for every country, as the Uganda paper's m03: 4 km windows around the worst
stretches, showing the buildings that line the road, the roads that join it, water, controls and
the corridor coloured by the minutes a loaded truck loses per km.

    python scripts/closeups.py

Writes, in figures/closeups/:
  c_<iso>.png                         a sheet of up to six close-ups per country
  <iso>/<n>_<corridor>_km<k>.png      each close-up on its own, with its causes
A stretch is filed under the country it lies in (Kampala-Malaba ends in Kenya). Stretches closer than
5 km to one already chosen are skipped, so overlapping roads near a hub do not repeat one place.
Only the layers inside each window are read, to keep memory low.
"""
import os, re, textwrap
import numpy as np
import pandas as pd
import geopandas as gpd
import pyarrow.parquet as pq
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from regional_common import ART, C, H, INK, INK2, SURF, distinct, pieces, save
import cartography as K

ISO = {"Uganda": "uga", "Kenya": "ken", "Rwanda": "rwa", "United Republic of Tanzania": "tza",
       "South Africa": "zaf", "Botswana": "bwa", "Zimbabwe": "zwe", "Zambia": "zmb", "Mozambique": "moz",
       "Namibia": "nam"}
SHORT = {"United Republic of Tanzania": "Tanzania"}
LAND, BUILDING, ROAD, STREAM = "#fbfaf7", "#9d988c", "#6f6c66", "#7fa9cf"
DELAY_BOUNDS = [0, 0.25, 0.5, 1, 2, 4, 100]
DELAY_LABELS = ["< 0.25", "0.25–0.5", "0.5–1", "1–2", "2–4", "> 4"]
DELAY_CMAP = ListedColormap(["#f3eee6", "#fde6da", "#f6b596", "#eb6834", "#b8491c", "#7c2e0f"])
DELAY_NORM = BoundaryNorm(DELAY_BOUNDS, DELAY_CMAP.N)
ROAD_W = {"motorway": 2.2, "trunk": 2.2, "primary": 2.0, "secondary": 1.5, "tertiary": 1.2,
          "residential": 0.7, "unclassified": 0.7, "service": 0.45, "track": 0.45}
MARK = {"police_post": ("D", "police post"), "weighbridge": ("s", "weighbridge"), "traffic_signals": ("P", "signals"),
        "pedestrian_crossing": ("o", "pedestrian crossing"), "market": ("^", "market"), "fuel": ("v", "fuel station"),
        "speed_hump": ("X", "speed hump (OSM)"), "level_crossing": ("*", "level crossing")}
PLACE_RANK = {"city": 0, "town": 1, "suburb": 2, "village": 3, "neighbourhood": 4, "locality": 5, "hamlet": 6}
LEGEND = ([Line2D([], [], marker="s", linestyle="none", markersize=5, color=BUILDING, label="building (Open Buildings)"),
           Line2D([], [], color=ROAD, linewidth=1.2, label="other roads (OSM)"),
           Line2D([], [], color=STREAM, linewidth=1.2, label="waterway"),
           Patch(color="#dcebf5", label="wetland"), Patch(color="#f6e3c8", label="market area")]
          + [Line2D([], [], marker=m, linestyle="none", markersize=6, markerfacecolor="white",
                    markeredgecolor=INK, label=l) for m, l in MARK.values()])
HALF = 0.018   # degrees, about 2 km each way
FEAT = os.path.join(C.DATA, "osm_features.gpkg")
SUB = "closeups"

typed = pd.read_csv(os.path.join(C.OUTPUTS, "pieces_typed.csv"))
pieces = pieces.to_crs(4326)
pieces["truck_min_per_km"] = pieces.per_km
B = pq.read_table(os.path.join(C.DATA, "buildings.parquet"),
                  columns=["latitude", "longitude", "area_in_meters"]).to_pandas()
for c in B:
    B[c] = B[c].astype("float32")

adm = gpd.read_file(os.path.join(C.DATA, "ne_admin0", "ne_10m_admin_0_countries.shp"), columns=["ADMIN"])
pts = gpd.GeoDataFrame(H, geometry=gpd.points_from_xy(H.lon, H.lat), crs=4326)
H["in_country"] = gpd.sjoin(pts, adm, how="left", predicate="within").groupby(level=0).ADMIN.first()
H["in_country"] = H.in_country.fillna(H.country)
H["road"] = H.corridor.map(ART.road)


def window(layer, x0, x1, y0, y1, where=None):
    return gpd.read_file(FEAT, layer=layer, bbox=(x0, y0, x1, y1), where=where)


def place_labels(ax, pl, x0, x1, y0, y1, n=9, size=7):
    pl = pl[(pl.kind == "place") & pl.name.notna()]
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


def info(r, width=None):
    d = typed[(typed.corridor == r.corridor) & typed.km_mid.between(r.km_from, r.km_to)]
    out = (f"{r.road_type} · truck +{r.truck_excess_min:.1f} min · car +{r.car_excess_min:.1f} min\n"
            f"{int(d.buildings_100m.sum()):,} buildings within 100 m · "
            f"{int((d.junctions_major + d.junctions_minor).sum())} joining roads · "
            f"{int(d.police_posts.sum())} police post(s) · {int(d.weighbridges.sum())} weighbridge(s)\n"
            "main causes (min): " + r.main_causes.replace("; ", ", "))
    if width:
        return "\n".join(textwrap.fill(l, width) for l in out.split("\n"))
    return out


def closeup(ax, r, inch_per_deg, title, width=None):
    x0, x1, y0, y1 = r.lon - HALF, r.lon + HALF, r.lat - HALF, r.lat + HALF
    K.frame(ax, (x0, x1, y0, y1))
    ax.set_facecolor(LAND)
    wa = window("areas", x0, x1, y0, y1)
    if len(wa):
        for k, col in (("wetland", "#dcebf5"), ("market", "#f6e3c8")):
            if (wa.kind == k).any():
                wa[wa.kind == k].plot(ax=ax, aspect=None, color=col, linewidth=0, zorder=1)
    ww = window("waterways", x0, x1, y0, y1)
    if len(ww):
        ww.plot(ax=ax, aspect=None, color=STREAM, linewidth=0.9, zorder=2)
    bb = B[B.longitude.between(x0, x1) & B.latitude.between(y0, y1)]
    side_pt = np.sqrt(bb.area_in_meters) / 111_320 * inch_per_deg * 72
    ax.scatter(bb.longitude, bb.latitude, s=np.maximum(side_pt, 0.9) ** 2, marker="s", color=BUILDING,
               linewidths=0, zorder=3)
    rr = window("roads", x0, x1, y0, y1)
    for hw, g in rr.groupby("highway"):
        if hw in ROAD_W:
            g.plot(ax=ax, aspect=None, color=ROAD, linewidth=ROAD_W[hw] * 0.8, zorder=4)
    pc = pieces.cx[x0:x1, y0:y1]   # every study road in the window, not only this one
    if len(pc):
        pc.plot(ax=ax, aspect=None, color=INK, linewidth=6.2, zorder=5)
        pc.plot(ax=ax, aspect=None, column="truck_min_per_km", cmap=DELAY_CMAP, norm=DELAY_NORM, linewidth=4.2,
                zorder=6)
    pp = window("points", x0, x1, y0, y1)
    pp["mkind"] = pp.kind.replace({"checkpoint_or_police": "police_post", "rumble_strip": "speed_hump"})
    for k, (m, _) in MARK.items():
        q = pp[pp.mkind == k]
        ax.scatter(q.geometry.x, q.geometry.y, marker=m, s=46, color="white", edgecolor=INK, linewidth=1.1, zorder=8)
    place_labels(ax, pp, x0, x1, y0, y1)
    K.scalebar(ax, km=1)
    ax.set_title(title, loc="left", fontsize=9.5, color=INK)
    ax.text(0, -0.02, info(r, width), transform=ax.transAxes, fontsize=7.2, color=INK, va="top", ha="left",
            linespacing=1.35, wrap=True)


def title_of(r, i):
    return f"{i}. {r.place_name}\n{r.road}, km {r.km_from:.0f}–{r.km_to:.0f}"


def delay_key(fig, ax):
    return K.key(fig, ax, DELAY_CMAP, DELAY_NORM, DELAY_BOUNDS, "study road: truck min lost per km",
                 labels=DELAY_LABELS)


WB = H.main_causes.map(lambda t: float(m.group(1)) if (m := re.search(r"weighbridge ([\d.]+)", t)) else 0.0)
H["other_min"] = H.truck_excess_min - WB   # minutes from everything but the weighbridge stop


def pick(h):
    """At most two weighbridge stops (a fixed 10 min each), the rest the stretches where the town,
    its humps, junctions and controls cost most."""
    wb = distinct(h[h.lead == "weighbridge"], 2, min_km=5)
    rest = distinct(h.assign(truck_excess_min=h.other_min), 12, min_km=5)
    if len(wb):
        far = [all(np.hypot((r.lon - w.lon) * 111 * np.cos(np.radians(r.lat)), (r.lat - w.lat) * 111) > 5
                   for w in wb.itertuples()) for r in rest.itertuples()]
        rest = rest[far]
    rest = rest.head(6 - len(wb))
    if len(rest):
        rest = rest.assign(truck_excess_min=H.truck_excess_min.reindex(rest.Index).to_numpy())
    return pd.concat([wb, rest]).sort_values("truck_excess_min", ascending=False)


for country, iso in ISO.items():
    sel = pick(H[H.in_country == country])
    if not len(sel):
        continue
    n, cols, panel = len(sel), 3, 4.3
    rows = int(np.ceil(n / cols))
    fig, axs = plt.subplots(rows, cols, figsize=(cols * panel, rows * panel + 1.9), facecolor=SURF,
                            gridspec_kw=dict(wspace=0.12, hspace=0.85), squeeze=False)
    axs = axs.ravel()
    for i, (ax, r) in enumerate(zip(axs, sel.itertuples()), 1):
        closeup(ax, r, panel / (2 * HALF), title_of(r, i), width=60)
    for ax in axs[n:]:
        ax.set_axis_off()
    fig.legend(handles=LEGEND, loc="lower center", ncol=7, frameon=False, fontsize=8, labelcolor=INK2,
               bbox_to_anchor=(0.5, -0.04))
    delay_key(fig, axs[min(cols, n) - 1])
    fig.suptitle(f"{SHORT.get(country, country)}: the worst stretches up close (4 km windows)", x=0.125,
                 ha="left", fontsize=16, color=INK, y=1.0)
    fig.text(0.125, 0.985 - 0.1 / fig.get_figheight(), "Buildings drawn at footprint area. Sources: OpenStreetMap; "
             "Google Open Buildings v3; travel-time model (10_travel_time.py). Controls as mapped in OSM. "
             "At most two weighbridges per sheet; the rest are where the settlement itself costs most.",
             fontsize=9, color=INK2, va="top")
    save(fig, f"c_{iso}.png", SUB)
    for i, r in enumerate(sel.itertuples(), 1):
        fig, ax = plt.subplots(figsize=(7.5, 9.2), facecolor=SURF)
        closeup(ax, r, 7.5 / (2 * HALF), title_of(r, i))
        K.north_arrow(ax)
        delay_key(fig, ax)
        ax.legend(handles=LEGEND, loc="upper left", bbox_to_anchor=(0, -0.14), ncol=3, frameon=False,
                  fontsize=7.5, labelcolor=INK2)
        save(fig, f"{i:02d}_{r.corridor}_km{r.km_from:.0f}.png", os.path.join(SUB, iso))
