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


# Close-up windows at hub scale (lon0, lon1, lat0, lat1)
CW = [("Kampala", (32.40, 32.85, 0.13, 0.55)), ("Nairobi", (36.62, 37.10, -1.48, -1.05)),
      ("Dar es Salaam", (38.92, 39.36, -6.98, -6.60)), ("Lusaka", (28.08, 28.52, -15.62, -15.22)),
      ("Gauteng", (27.75, 28.45, -26.35, -25.65))]
import pyarrow.parquet as pq  # noqa: E402
BLD = pq.read_table(os.path.join(C.DATA, "buildings.parquet"), columns=["latitude", "longitude"]).to_pandas()
BLD = BLD.astype("float32")
ROADS = {}


def context(ax, win):
    x0, x1, y0, y1 = win
    bb = BLD[BLD.longitude.between(x0, x1) & BLD.latitude.between(y0, y1)]
    ax.scatter(bb.longitude, bb.latitude, s=0.25, color="#b0aa9f", linewidths=0, zorder=3.5, rasterized=True)
    if win not in ROADS:
        r = gpd.read_file(os.path.join(C.DATA, "osm_features.gpkg"), layer="roads", bbox=(x0, y0, x1, y1))
        ROADS[win] = r[r.highway.isin(["motorway", "trunk", "primary", "secondary", "tertiary"])]
    if len(ROADS[win]):
        ROADS[win].plot(ax=ax, aspect=None, color="#8c887f", linewidth=0.4, zorder=4)


def two_panel(col, colors, bounds, labels, key_label, title, sub, name, cats=None):
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
    for i, (nm, win) in enumerate(CW, 1):
        ov = axE if win[2] > -12 and win[0] > 29 and nm != "Lusaka" else axS
        ov.add_patch(Rectangle((win[0], win[2]), win[1] - win[0], win[3] - win[2], fill=False, ec=INK, lw=1.2, zorder=25))
        ov.text(win[0], win[3], f" {i}", fontsize=10, fontweight="bold", color=INK, va="bottom", zorder=26,
                bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.85))
        ax = fig.add_axes([0.01 + (i - 1) * 0.196, 0.03, 0.18, 0.25])
        basemap(ax, win)
        context(ax, win)
        lines(ax, None, fine, cmap, norm, lw=2.2, extent=win)
        hubs(ax, win, fs=8)
        K.scalebar(ax, km=10)
        for s_ in ax.spines.values():
            s_.set_visible(True); s_.set_color(INK)
        ax.set_title(f"{i}. {nm}", fontsize=10.5, color=INK, loc="left")
    kax = fig.add_axes([0.935, 0.42, 0.012, 0.40])
    n = len(bounds) - 1
    kax.imshow(np.arange(n)[:, None], cmap=ListedColormap(colors), aspect="auto", origin="lower", extent=(0, 1, 0, n))
    kax.set_xticks([]); kax.set_yticks(np.arange(n) + 0.5); kax.set_yticklabels(labels, fontsize=8.5)
    kax.yaxis.tick_right(); kax.tick_params(length=0)
    fig.text(0.925, 0.835, key_label, fontsize=9, color=INK, ha="left", va="bottom")
    for s_ in kax.spines.values():
        s_.set_visible(False)
    fig.text(0.01, 0.985, title, fontsize=16, color=INK, va="top")
    fig.text(0.01, 0.96, sub + " Close-ups 1–5: every 500 m, with building footprints and main roads.", fontsize=10,
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
          "rm01_road_types.png")
two_panel("added_per_km_2", ["#f1eee6", "#e6d5b8", "#d2ad74", "#b57d3b", "#8a5420", "#5a3210"],
          [-100, 0.25, 0.5, 1, 2, 4, 1000], ["< 0.25", "0.25–0.5", "0.5–1", "1–2", "2–4", "> 4"],
          "built-up ha added\nwithin 300 m per km,\n2000–2020",
          "Where the roadside built up, 2000–2020",
          "GHSL built-up surface within 300 m of the road, observed 2000 and 2020, per 2 km.", "rm02_growth.png")
two_panel("exposure_per_km_2", ["#f3eee8", "#f3cdbd", "#e89b7f", "#d0613f", "#a6321b", "#6b1408"],
          [-1, 0.1, 0.25, 0.5, 1, 2, 1e9], ["< 0.1", "0.1–0.25", "0.25–0.5", "0.5–1", "1–2", "> 2"],
          "safety exposure\nper km\n(people × trucks\n× (speed/50)⁴)",
          "Where fast trucks pass people",
          "People within 300 m (GHS-POP 2025) × trucks × (truck speed/50)⁴, per 2 km; one assumed truck count on every road.",
          "rm03_exposure.png")
two_panel("fuel_per_km_2", ["#dfe8ee", "#f2efe6", "#d9e1c2", "#a9c27d", "#6c9a45", "#355f1f"],
          [-100, 0, 0.05, 0.1, 0.2, 0.4, 100], ["saving", "0–0.05", "0.05–0.1", "0.1–0.2", "0.2–0.4", "> 0.4"],
          "extra diesel per km\nper loaded truck (L)",
          "Where roadside friction burns diesel",
          "Physical fuel model on the travel-time model's speeds, against open road, per 2 km. Climbs held back save fuel.",
          "rm04_fuel.png")
two_panel("wet_days_per_year_2", ["#eef3f7", "#cfe0ec", "#9fc2db", "#6a9dc4", "#3c74a6", "#1b4a78"],
          [0, 10, 20, 30, 40, 55, 200], ["< 10", "10–20", "20–30", "30–40", "40–55", "> 55"],
          "days a year with\n≥ 10 mm rain\n(CHIRPS 2006–2025)",
          "How often heavy rain falls on the roads",
          "Mean days a year with at least 10 mm of rain on each piece, 2006–2025, per 2 km.", "rm05_rain.png")
two_panel("controls_10", ["#f2efe6", "#d6dfe2", "#a9bfc7", "#6f97a6", "#3f6e80", "#173f4f"],
          [-1, 0.5, 2.5, 5, 10, 20, 1e9], ["none", "1–2", "3–5", "6–10", "11–20", "> 20"],
          "controls mapped in\nOSM per 10 km\n(signals, crossings,\nhumps, police posts,\nweighbridges)",
          "The mapping gap: controls recorded in OpenStreetMap",
          "Gauteng's roads are mapped control by control; most East African towns are not. Comparisons of controls are partly comparisons of mapping.",
          "rm06_controls.png")
two_panel("per_km_2", ["#e3ded3", "#fde6da", "#f6b596", "#eb6834", "#b8491c", "#7c2e0f"],
          [-1, 0.25, 0.5, 1, 2, 4, 1000], ["< 0.25", "0.25–0.5", "0.5–1", "1–2", "2–4", "> 4"],
          "truck minutes lost\nper km vs open road",
          "Where trucks lose time",
          "Travel-time model, loaded truck leaving the hub, light traffic, dry day; per 2 km.", "rm07_delay.png")
