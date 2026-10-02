"""Thematic maps for the regional paper: East and Southern Africa side by side, every road drawn
per 2 km.

    python scripts/maps_regional.py

  figures/maps/rm01_road_types.png   road type (clustered jointly across the region)
  figures/maps/rm02_growth.png       built-up land added within 300 m per km, 2000-2020 (GHSL)
  figures/maps/rm03_exposure.png     people within 300 m per km, and safety exposure per km
  figures/maps/rm04_fuel.png         extra diesel per km per loaded truck from friction
  figures/maps/rm05_rain.png         days a year with >= 10 mm rain (CHIRPS 2006-2025)
  figures/maps/rm06_controls.png     controls mapped in OSM per 10 km (the mapping gap made visible)
  figures/maps/rm07_delay.png        truck minutes lost per km
"""
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

from regional_common import ART, C, INK, INK2, SURF, O, pieces, save
import cartography as K

LAND, NEIGH, WATER, BORDER = "#f6f4ef", "#e9e6df", "#c9dbe6", "#a8a49b"
SHORT = {"United Republic of Tanzania": "Tanzania"}
SUB = "maps"
countries = gpd.read_file(os.path.join(C.DATA, "ne_admin0", "ne_10m_admin_0_countries.shp"), columns=["ADMIN"])
lakes = gpd.read_file(os.path.join(C.ROOT, "..", "data", "ne_lakes", "ne_10m_lakes.shp")).to_crs(4326)
STUDY = set(ART.country)

P = pieces.to_crs(4326)[["corridor", "piece", "geometry", "per_km", "length_km"]].copy()
P["region"] = P.corridor.map(ART.region)
T = O("pieces_typed.csv")
P = P.merge(T[["corridor", "piece", "road_type", "wet_days_per_year", "signals", "ped_crossings", "humps",
               "police_posts", "weighbridges", "level_crossings"]], how="left")
G = O("growth_pieces.csv")
P = P.merge(G[["corridor", "piece", "built_ha_2000", "built_ha_2020"]], how="left")
S = O("safety_pieces.csv")
P = P.merge(S[["corridor", "piece", "people_300m", "exposure"]], how="left")
F = O("fuel_co2_pieces.csv")
P = P.merge(F[["corridor", "piece", "friction_litres"]], how="left")
L = P.length_km.clip(lower=0.1)
P["added_per_km"] = (P.built_ha_2020 - P.built_ha_2000) / L
P["people_per_km"] = P.people_300m / L
P["exposure_per_km"] = P.exposure / L
P["fuel_per_km"] = P.friction_litres / L
P["controls"] = P[["signals", "ped_crossings", "humps", "police_posts", "weighbridges", "level_crossings"]].sum(axis=1)

# 2 km stretches: average each measure over four pieces, keep the pieces' geometry
grp = P.corridor + "_" + (P.piece // 4).astype(str)
for col in ("per_km", "added_per_km", "people_per_km", "exposure_per_km", "fuel_per_km", "wet_days_per_year"):
    P[col + "_2"] = P.groupby(grp)[col].transform("mean")
P["controls_10"] = P.groupby(P.corridor + "_" + (P.piece // 20).astype(str)).controls.transform("sum")

EXT = {}
for reg, d in P.groupby("region"):
    x0, y0, x1, y1 = d.total_bounds
    EXT[reg] = (x0 - 0.8, x1 + 0.8, y0 - 0.8, y1 + 0.8)
GAUT = (26.9, 29.6, -27.2, -24.9)


def basemap(ax, extent):
    x0, x1, y0, y1 = extent
    ax.set_facecolor(WATER)
    cc = countries.cx[x0 - 5:x1 + 5, y0 - 5:y1 + 5]
    cc.plot(ax=ax, aspect=None, color=NEIGH, edgecolor=BORDER, linewidth=0.6, zorder=1)
    cc[cc.ADMIN.isin(STUDY)].plot(ax=ax, aspect=None, color=LAND, edgecolor=BORDER, linewidth=0.7, zorder=2)
    lk = lakes.cx[x0:x1, y0:y1]
    if len(lk):
        lk.plot(ax=ax, aspect=None, color=WATER, linewidth=0, zorder=3)
    K.frame(ax, extent)
    ax.set_facecolor(WATER)
    for r in cc.itertuples():
        p = r.geometry.representative_point()
        if x0 < p.x < x1 and y0 < p.y < y1 and (x1 - x0) > 5:
            ax.text(p.x, p.y, SHORT.get(r.ADMIN, r.ADMIN).upper(), fontsize=7, ha="center", va="center", zorder=4,
                    color="#8d8980" if r.ADMIN in STUDY else "#aaa69d", clip_on=True)


def hubs(ax, extent, fs=8.5):
    x0, x1, y0, y1 = extent
    for h, g in ART.groupby("hub"):
        x, y = g.start.iloc[0]
        if x0 < x < x1 and y0 < y < y1:
            ax.scatter([x], [y], s=34, color=INK, edgecolor="white", linewidth=1, zorder=12)
            off = {"pretoria": (6, 5), "johannesburg": (-6, -9), "dodoma": (6, 0), "dar_es_salaam": (6, -4)}.get(h, (6, 2))
            ax.annotate(g.hub_name.iloc[0], (x, y), xytext=off, textcoords="offset points", fontsize=fs,
                        ha="right" if off[0] < 0 else "left", fontweight="bold", color=INK, zorder=13,
                        bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.8))


def lines(ax, region, col, cmap, norm, lw=3.0, extent=None):
    d = P[P.region == region] if region else P.cx[extent[0]:extent[1], extent[2]:extent[3]]
    d.plot(ax=ax, aspect=None, color=INK, linewidth=lw + 0.9, zorder=5)
    d.plot(ax=ax, aspect=None, color="#d9d4c7", linewidth=lw, zorder=5.5)
    v = d.dropna(subset=[col]).sort_values(col)
    v.plot(ax=ax, aspect=None, column=col, cmap=cmap, norm=norm, linewidth=lw, zorder=6)


import pyarrow.parquet as pq  # noqa: E402
from matplotlib.lines import Line2D as _L  # noqa: E402
from matplotlib.patches import Patch as _Pa  # noqa: E402
BLD = pq.read_table(os.path.join(C.DATA, "buildings.parquet"),
                    columns=["latitude", "longitude", "area_in_meters"]).to_pandas().astype("float32")
FEAT = os.path.join(C.DATA, "osm_features.gpkg")
HALF = 0.018   # 4 km windows, as the bottleneck close-ups
ROAD_W = {"motorway": 2.2, "trunk": 2.2, "primary": 2.0, "secondary": 1.5, "tertiary": 1.2,
          "residential": 0.7, "unclassified": 0.7, "service": 0.45, "track": 0.45}
MARK = {"police_post": ("D", "police post"), "weighbridge": ("s", "weighbridge"), "traffic_signals": ("P", "signals"),
        "pedestrian_crossing": ("o", "pedestrian crossing"), "market": ("^", "market"), "fuel": ("v", "fuel station"),
        "speed_hump": ("X", "speed hump (OSM)"), "level_crossing": ("*", "level crossing")}
CLOSE_KEY = ([_L([], [], marker="s", ls="none", markersize=5, color="#9d988c", label="building (Open Buildings)"),
              _L([], [], color="#6f6c66", lw=1.2, label="other roads (OSM)"),
              _L([], [], color="#7fa9cf", lw=1.2, label="waterway"),
              _Pa(color="#dcebf5", label="wetland"), _Pa(color="#f6e3c8", label="market area")]
             + [_L([], [], marker=m, ls="none", markersize=6, markerfacecolor="white", markeredgecolor=INK, label=l)
                for m, l in MARK.values()])
PLACE_RANK = {"city": 0, "town": 1, "suburb": 2, "village": 3, "neighbourhood": 4, "locality": 5, "hamlet": 6}
P = P.merge(T[["corridor", "piece", "place", "buildings_100m"]], how="left")
P["country"] = P.corridor.map(ART.country)
CEN = P.geometry.centroid


def win_read(layer, x0, x1, y0, y1):
    return gpd.read_file(FEAT, layer=layer, bbox=(x0, y0, x1, y1))


def street(ax, i, col, cmap, norm, inch_per_deg, title):
    """Street-level close-up (4 km) around piece i: footprints, roads, water, controls, the study roads
    coloured by the map's theme."""
    lon, lat = CEN.x[i], CEN.y[i]
    x0, x1, y0, y1 = lon - HALF, lon + HALF, lat - HALF, lat + HALF
    K.frame(ax, (x0, x1, y0, y1))
    ax.set_facecolor(LAND)
    wa = win_read("areas", x0, x1, y0, y1)
    for k, c_ in (("wetland", "#dcebf5"), ("market", "#f6e3c8")):
        if len(wa) and (wa.kind == k).any():
            wa[wa.kind == k].plot(ax=ax, aspect=None, color=c_, linewidth=0, zorder=1)
    ww = win_read("waterways", x0, x1, y0, y1)
    if len(ww):
        ww.plot(ax=ax, aspect=None, color="#7fa9cf", linewidth=0.9, zorder=2)
    bb = BLD[BLD.longitude.between(x0, x1) & BLD.latitude.between(y0, y1)]
    side = np.sqrt(bb.area_in_meters) / 111_320 * inch_per_deg * 72
    ax.scatter(bb.longitude, bb.latitude, s=np.maximum(side, 0.9) ** 2, marker="s", color="#9d988c", linewidths=0,
               zorder=3)
    rr = win_read("roads", x0, x1, y0, y1)
    for hw, g in rr.groupby("highway"):
        if hw in ROAD_W:
            g.plot(ax=ax, aspect=None, color="#6f6c66", linewidth=ROAD_W[hw] * 0.8, zorder=4)
    pc = P.cx[x0:x1, y0:y1]
    pc.plot(ax=ax, aspect=None, color=INK, linewidth=6.2, zorder=5)
    pc.plot(ax=ax, aspect=None, color="#d9d4c7", linewidth=4.2, zorder=5.5)
    v = pc.dropna(subset=[col])
    if len(v):
        v.plot(ax=ax, aspect=None, column=col, cmap=cmap, norm=norm, linewidth=4.2, zorder=6)
    pp = win_read("points", x0, x1, y0, y1)
    pp["mkind"] = pp.kind.replace({"checkpoint_or_police": "police_post", "rumble_strip": "speed_hump"})
    for k, (m, _) in MARK.items():
        q = pp[pp.mkind == k]
        ax.scatter(q.geometry.x, q.geometry.y, marker=m, s=40, color="white", edgecolor=INK, linewidth=1.0, zorder=8)
    pl = pp[(pp.kind == "place") & pp.name.notna()]
    pl = pl[~pl.name.str.contains("/")]
    if len(pl):
        pl = pl.assign(r=pl.place.map(PLACE_RANK).fillna(9)).sort_values("r").drop_duplicates("name").head(6)
        ax.scatter(pl.geometry.x, pl.geometry.y, s=8, color=INK, zorder=14, linewidths=0)
        ts = [ax.text(x, y, t, fontsize=6.5, color=INK, zorder=16, style="italic",
                      bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.8))
              for x, y, t in zip(pl.geometry.x, pl.geometry.y, pl.name)]
        K.adjust_text(ts, x=list(pl.geometry.x), y=list(pl.geometry.y), ax=ax, expand=(1.2, 1.4))
    K.scalebar(ax, km=1)
    for s_ in ax.spines.values():
        s_.set_visible(True); s_.set_color(INK)
    ax.set_title(title, fontsize=8.5, color=INK, loc="left")


def pick_sites(score, mask=None, n_east=3, n_south=2):
    """Where the theme peaks: the top piece in each country, best countries first, three East and two
    Southern, so the close-ups travel across the region."""
    v = pd.Series(score, dtype=float, index=P.index)
    if mask is not None:
        v[~np.asarray(mask)] = np.nan
    v = v.dropna()
    best = v.groupby(P.country[v.index]).idxmax()
    ranked = sorted(best, key=lambda i: -v[i])
    east = [i for i in ranked if P.region[i] == "East"][:n_east]
    south = [i for i in ranked if P.region[i] == "Southern"][:n_south]
    return east + south


def site_title(n, i, extra):
    place = P.place[i] if isinstance(P.place[i], str) else "unnamed place"
    return f"{n}. {place} ({SHORT.get(P.country[i], P.country[i])})\n{ART.road[P.corridor[i]]}, km {P.piece[i] * 0.5:.0f}\n{extra}"


def two_panel(col, colors, bounds, labels, key_label, title, sub, name, cats=None, mask=None, sites=None,
              extra=lambda i: "", score=None):
    cmap = ListedColormap(colors)
    norm = BoundaryNorm(bounds, cmap.N)
    fine = col[:-2] if col.endswith("_2") and col[:-2] in P else col   # close-ups show every 500 m
    fig = plt.figure(figsize=(18, 14.5), facecolor=SURF)
    axE = fig.add_axes([0.01, 0.36, 0.40, 0.56])
    axS = fig.add_axes([0.42, 0.31, 0.49, 0.61])
    for ax, reg in ((axE, "East"), (axS, "Southern")):
        basemap(ax, EXT[reg])
        lines(ax, reg, col, cmap, norm)
        hubs(ax, EXT[reg])
        K.scalebar(ax, km=200)
        ax.text(0.02, 0.98, f"{reg} Africa", transform=ax.transAxes, fontsize=13, fontweight="bold", va="top",
                color=INK, zorder=20, bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.85))
    K.north_arrow(axS)
    idx = pick_sites(P[col] if score is None else score, mask) if sites is None else sites
    for n, i in enumerate(idx, 1):
        ov = axE if P.region[i] == "East" else axS
        ov.text(CEN.x[i], CEN.y[i], str(n), ha="center", va="center", fontsize=9, fontweight="bold", color=INK,
                zorder=30, bbox=dict(boxstyle="circle,pad=0.25", fc="white", ec=INK, lw=1.2))
        ax = fig.add_axes([0.01 + (n - 1) * 0.196, 0.035, 0.18, 0.235])
        street(ax, i, fine, cmap, norm, 0.18 * 18 / (2 * HALF), site_title(n, i, extra(i)))
    fig.legend(handles=CLOSE_KEY, loc="upper center", bbox_to_anchor=(0.5, 0.0), ncol=7, frameon=False, fontsize=8.5,
               labelcolor=INK2)
    kax = fig.add_axes([0.935, 0.42, 0.012, 0.40])
    n = len(bounds) - 1
    kax.imshow(np.arange(n)[:, None], cmap=ListedColormap(colors), aspect="auto", origin="lower", extent=(0, 1, 0, n))
    kax.set_xticks([]); kax.set_yticks(np.arange(n) + 0.5); kax.set_yticklabels(labels, fontsize=8.5)
    kax.yaxis.tick_right(); kax.tick_params(length=0)
    fig.text(0.925, 0.835, key_label, fontsize=9, color=INK, ha="left", va="bottom")
    for s_ in kax.spines.values():
        s_.set_visible(False)
    fig.text(0.01, 0.985, title, fontsize=16, color=INK, va="top")
    fig.text(0.01, 0.96, sub + " Close-ups 1–5 (4 km): where the measure peaks in five countries; buildings at footprint size.", fontsize=10,
             color=INK2, va="top")
    fig.text(0.01, 0.005, "Sources: OpenStreetMap; Google Open Buildings v3; GHSL; GHS-POP 2025; CHIRPS; Natural Earth; "
             "study model.", fontsize=7.5, color=INK2)
    save(fig, name, SUB)


# rm01 road types
P["type_code"] = P.road_type.map({"open road": 0, "roadside settlement": 1, "town": 2})
two_panel("type_code", ["#a9c8ec", "#3574c4", "#0d2d57"], [-0.5, 0.5, 1.5, 2.5],
          ["open road", "roadside\nsettlement", "town"], "road type\n(joint k-means)",
          "What lines the roads: road type along every 500 m",
          "Open road, roadside settlement or town, clustered jointly across all 54 roads so each label means the same everywhere.",
          "rm01_road_types.png", score=P.buildings_100m, mask=(P.road_type == "roadside settlement").to_numpy(),
          extra=lambda i: f"roadside settlement: {P.buildings_100m[i]:.0f} buildings within 100 m")
two_panel("added_per_km_2", ["#f1eee6", "#e6d5b8", "#d2ad74", "#b57d3b", "#8a5420", "#5a3210"],
          [-100, 0.25, 0.5, 1, 2, 4, 1000], ["< 0.25", "0.25–0.5", "0.5–1", "1–2", "2–4", "> 4"],
          "built-up ha added\nwithin 300 m per km,\n2000–2020",
          "Where the roadside built up, 2000–2020",
          "GHSL built-up surface within 300 m of the road, observed 2000 and 2020, per 2 km.", "rm02_growth.png",
          extra=lambda i: f"+{P.added_per_km_2[i]:.1f} ha built up per km, 2000–2020")
two_panel("exposure_per_km_2", ["#f3eee8", "#f3cdbd", "#e89b7f", "#d0613f", "#a6321b", "#6b1408"],
          [-1, 0.1, 0.25, 0.5, 1, 2, 1e9], ["< 0.1", "0.1–0.25", "0.25–0.5", "0.5–1", "1–2", "> 2"],
          "safety exposure\nper km\n(people × trucks\n× (speed/50)⁴)",
          "Where fast trucks pass people",
          "People within 300 m (GHS-POP 2025) × trucks × (truck speed/50)⁴, per 2 km; one assumed truck count on every road.",
          "rm03_exposure.png",
          extra=lambda i: f"exposure {P.exposure_per_km_2[i]:.1f} per km")
two_panel("fuel_per_km_2", ["#dfe8ee", "#f2efe6", "#d9e1c2", "#a9c27d", "#6c9a45", "#355f1f"],
          [-100, 0, 0.05, 0.1, 0.2, 0.4, 100], ["saving", "0–0.05", "0.05–0.1", "0.1–0.2", "0.2–0.4", "> 0.4"],
          "extra diesel per km\nper loaded truck (L)",
          "Where roadside friction burns diesel",
          "Physical fuel model on the travel-time model's speeds, against open road, per 2 km. Climbs held back save fuel.",
          "rm04_fuel.png",
          extra=lambda i: f"{P.fuel_per_km_2[i]:.2f} L extra diesel per km")
two_panel("wet_days_per_year_2", ["#eef3f7", "#cfe0ec", "#9fc2db", "#6a9dc4", "#3c74a6", "#1b4a78"],
          [0, 10, 20, 30, 40, 55, 200], ["< 10", "10–20", "20–30", "30–40", "40–55", "> 55"],
          "days a year with\n≥ 10 mm rain\n(CHIRPS 2006–2025)",
          "How often heavy rain falls on the roads",
          "Mean days a year with at least 10 mm of rain on each piece, 2006–2025, per 2 km.", "rm05_rain.png",
          extra=lambda i: f"{P.wet_days_per_year_2[i]:.0f} days a year with ≥ 10 mm rain")
two_panel("controls_10", ["#f2efe6", "#d6dfe2", "#a9bfc7", "#6f97a6", "#3f6e80", "#173f4f"],
          [-1, 0.5, 2.5, 5, 10, 20, 1e9], ["none", "1–2", "3–5", "6–10", "11–20", "> 20"],
          "controls mapped in\nOSM per 10 km\n(signals, crossings,\nhumps, police posts,\nweighbridges)",
          "The mapping gap: controls recorded in OpenStreetMap",
          "Gauteng's roads are mapped control by control; most East African towns are not. Comparisons of controls are partly comparisons of mapping.",
          "rm06_controls.png",
          extra=lambda i: f"{P.controls_10[i]:.0f} controls mapped within 10 km")
two_panel("per_km_2", ["#e3ded3", "#fde6da", "#f6b596", "#eb6834", "#b8491c", "#7c2e0f"],
          [-1, 0.25, 0.5, 1, 2, 4, 1000], ["< 0.25", "0.25–0.5", "0.5–1", "1–2", "2–4", "> 4"],
          "truck minutes lost\nper km vs open road",
          "Where trucks lose time",
          "Travel-time model, loaded truck leaving the hub, light traffic, dry day; per 2 km.", "rm07_delay.png",
          extra=lambda i: f"{P.per_km_2[i]:.1f} truck min lost per km")
