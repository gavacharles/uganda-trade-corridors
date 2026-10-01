"""Figures for the regional paper: study area, region-wide comparisons, and one sheet per country.

    python scripts/figures.py          # after run.py ... 26 and scripts/compare.py

Writes to figures/:
  r01_study_area.png            all 54 arteries out of 12 hubs, trade corridors drawn full length
  r02_delay_by_cause.png        truck minutes lost per 100 km, by cause, per hub
  r03_bottlenecks_east.png      worst 2 km stretches pinned, East Africa
  r03_bottlenecks_southern.png  the same, Southern Africa
  r04_safety.png                exposure per km, where it sits, schools beside fast trucks
  r05_fuel_co2.png              extra diesel and CO2 per 100 km, by cause, per hub
  r06_trade_corridors.png       the main freight routes side by side, full length
  r10_country_<iso>.png         one sheet per country: map with bottlenecks, causes per road
Every rate is per 100 km of road (or per km), so long and short roads compare. Light traffic,
dry day, the Uganda study's model and assumptions everywhere. Controls (signals, crossings,
humps, police posts, weighbridges) come from OSM, whose mapping is far denser in South Africa.
"""
import json, os, sys
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "..", "scripts")]
import config as C  # noqa: E402

INK, INK2, SURF, GRID = "#1d2321", "#5d6764", "#fcfcfb", "#e6e4de"
LAND, NEIGH, WATER, BORDER = "#f6f4ef", "#e9e6df", "#c9dbe6", "#a8a49b"
EAST, SOUTH = "#c4532d", "#3d7f8f"
DELAY_BOUNDS = [0, 0.25, 0.5, 1, 2, 4, 100]
DELAY_CMAP = ListedColormap(["#e3ded3", "#fde6da", "#f6b596", "#eb6834", "#b8491c", "#7c2e0f"])
DELAY_NORM = BoundaryNorm(DELAY_BOUNDS, DELAY_CMAP.N)
CAUSE_COL = {"roadside activity": "#c4532d", "hills (trucks)": "#8a6b4e", "weighbridge": "#17252a",
             "speed humps (assumed)": "#d9a441", "police posts": "#4e7c8a", "joining roads": "#3a7d5c",
             "signals and crossings": "#9fb3b0", "town speed limit": "#e89a7a", "curves": "#c9c2b8"}
HUB_NAME = {"dar_es_salaam": "Dar es Salaam"}
ISO = {"Uganda": "uga", "Kenya": "ken", "Rwanda": "rwa", "United Republic of Tanzania": "tza",
       "South Africa": "zaf", "Botswana": "bwa", "Zimbabwe": "zwe", "Zambia": "zmb", "Mozambique": "moz",
       "Namibia": "nam"}
COUNTRY_SHORT = {"United Republic of Tanzania": "Tanzania"}
FIG = C.FIGURES
O = lambda f: pd.read_csv(os.path.join(C.OUTPUTS, f))  # noqa: E731

# ---------------------------------------------------------------- data
ART = pd.DataFrame(json.load(open(os.path.join(C.DATA, "arteries.json"))))
ART["hub_name"] = ART.hub.map(lambda h: HUB_NAME.get(h, h.replace("_", " ").title()))
ART = ART.set_index("name")
pieces = gpd.read_file(os.path.join(C.DATA, "pieces.gpkg"))
reg = ART.groupby("hub").region.first()
# One line per artery (the pieces merged), for clean drawing at small scales
LINES = pieces.dissolve(by="corridor").geometry
tt = O("travel_time_pieces.csv")
pieces = pieces.merge(tt[["corridor", "piece", "truck_excess_min"]], on=["corridor", "piece"], how="left")
pieces["length_km"] = pieces.to_crs(C.UTM).length / 1000
pieces["per_km"] = pieces.truck_excess_min / pieces.length_km.clip(lower=0.05)
km = pieces.groupby("corridor").length_km.sum()
countries = gpd.read_file(os.path.join(C.DATA, "ne_admin0", "ne_10m_admin_0_countries.shp")).to_crs(4326)
lakes = gpd.read_file(os.path.join(C.ROOT, "..", "data", "ne_lakes", "ne_10m_lakes.shp")).to_crs(4326)
STUDY = set(ART.country)
causes = O("travel_time_causes.csv")
causes = causes[(causes.vehicle == "truck") & (causes.direction == "outbound") & causes.cause.isin(CAUSE_COL)]

# Bottlenecks: the worst 2 km stretches (10_travel_time.py), placed at their midpoint piece
H = O("hotspots.csv")
mid = (H.km_from + H.km_to) / 2
loc = []
for c, k in zip(H.corridor, mid):
    d = pieces[pieces.corridor == c]
    r = d.iloc[(d.km_mid - k).abs().argmin()]
    loc.append((r.lon, r.lat))
H["lon"], H["lat"] = zip(*loc)
H["hub"] = H.corridor.map(ART.hub)
H["region"] = H.corridor.map(ART.region)
H["country"] = H.corridor.map(ART.country)
H["lead"] = H.main_causes.str.split(";").str[0].str.rsplit(" ", n=1).str[0]


PLACES = gpd.read_file(os.path.join(C.DATA, "osm_features.gpkg"), layer="points", where="kind = 'place'")
PLACES = PLACES[PLACES.name.notna() & ~PLACES.name.str.contains("/", na=False)].to_crs(C.UTM)


def nearest_place(lon, lat):
    """The nearest named OSM settlement: its name within 5 km, "near <name>" within 20 km."""
    pt = gpd.GeoSeries(gpd.points_from_xy([lon], [lat]), crs=4326).to_crs(C.UTM).iloc[0]
    d = PLACES.distance(pt)
    if not len(d) or d.min() > 20000:
        return None
    return PLACES.name[d.idxmin()] if d.min() < 5000 else f"near {PLACES.name[d.idxmin()]}"


def label_of(r):
    lead = {"weighbridge": "weighbridge", "police posts": "police post", "signals and crossings": "signals"}.get(r.lead)
    place = r.place if isinstance(r.place, str) else (nearest_place(r.lon, r.lat) or "unnamed place")
    return f"{place}" + (f" ({lead})" if lead else "")


H["label"] = [label_of(r) for r in H.itertuples()]


def toward_name(a):
    """Discovery names an artery by the town at its end, or by its length when none is near
    ("326 km"); name those after the nearest settlement to the end point instead."""
    if not str(a.toward).endswith(" km"):
        return a.toward
    pt = gpd.GeoSeries(gpd.points_from_xy([a.end[0]], [a.end[1]]), crs=4326).to_crs(C.UTM).iloc[0]
    d = PLACES.distance(pt)
    if len(d) and d.min() < 60000:
        return ("" if d.min() < 5000 else "towards ") + PLACES.name[d.idxmin()]
    dx, dy = a.end[0] - a.start[0], a.end[1] - a.start[1]
    compass = ["east", "north-east", "north", "north-west", "west", "south-west", "south", "south-east"]
    return f"{compass[int(((np.degrees(np.arctan2(dy, dx)) + 22.5) % 360) // 45)]}, {a.toward}"


ART["toward"] = [toward_name(a) for a in ART.itertuples()]
ART["road"] = ART.apply(lambda a: f"{a.hub_name} → {a.toward}" + (f" ({a.ref})" if a.ref else ""), axis=1)


def distinct(h, n, min_km=4):
    """The n worst stretches, skipping any within min_km of one already chosen (overlapping roads)."""
    keep = []
    for r in h.sort_values("truck_excess_min", ascending=False).itertuples():
        if all(np.hypot((r.lon - k.lon) * 111 * np.cos(np.radians(r.lat)), (r.lat - k.lat) * 111) > min_km for k in keep):
            keep.append(r)
        if len(keep) == n:
            break
    return pd.DataFrame(keep)


# ---------------------------------------------------------------- helpers
def style(ax, grid="x"):
    ax.set_facecolor(SURF)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    if grid:
        ax.grid(axis=grid, color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)
    ax.tick_params(length=0, labelsize=10)
    ax.tick_params(axis="x", colors=INK2)


def region_divider(ax, hubs):
    """A rule between the East and Southern groups of a per-hub chart (y = 0..n-1, inverted)."""
    r = [reg[h] for h in hubs]
    k = next((i for i in range(1, len(r)) if r[i] != r[i - 1]), None)
    if k is None:
        return
    ax.axhline(k - 0.5, color=INK2, lw=0.8, ls=(0, (4, 3)))
    for lab, y0, col in (("EAST AFRICA", 0, EAST), ("SOUTHERN AFRICA", k, SOUTH)):
        ax.annotate(lab, (1, y0 - 0.45), xycoords=("axes fraction", "data"), ha="right", va="top",
                    fontsize=8.5, color=col, fontweight="bold")


def basemap(ax, extent, country_labels=True):
    x0, x1, y0, y1 = extent
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
    ax.set_aspect(1 / np.cos(np.radians((y0 + y1) / 2)))
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_facecolor(WATER)
    cc = countries.cx[x0 - 5:x1 + 5, y0 - 5:y1 + 5]
    for layer, kw in ((cc, dict(color=NEIGH, edgecolor=BORDER, linewidth=0.6, zorder=1)),
                      (cc[cc.ADMIN.isin(STUDY)], dict(color=LAND, edgecolor=BORDER, linewidth=0.7, zorder=2)),
                      (lakes.cx[x0:x1, y0:y1], dict(color=WATER, linewidth=0, zorder=3))):
        if not layer.empty:
            layer.plot(ax=ax, aspect=None, **kw)
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
    ax.set_aspect(1 / np.cos(np.radians((y0 + y1) / 2)))
    if country_labels:
        for r in cc.itertuples():
            p = r.geometry.representative_point()
            if x0 < p.x < x1 and y0 < p.y < y1:
                name = COUNTRY_SHORT.get(r.ADMIN, r.ADMIN)
                ax.text(p.x, p.y, name.upper(), fontsize=7.5, color="#8d8980" if r.ADMIN in STUDY else "#a9a59c",
                        ha="center", va="center", zorder=4, clip_on=True)


def delay_lines(ax, sel, lw=2.2):
    d = pieces[pieces.corridor.isin(sel)]
    d.plot(ax=ax, aspect=None, color=INK, linewidth=lw + 1.4, zorder=5)
    d.sort_values("per_km").plot(ax=ax, aspect=None, column="per_km", cmap=DELAY_CMAP, norm=DELAY_NORM, linewidth=lw, zorder=6)


def delay_key(fig, rect):
    k = fig.add_axes(rect)
    k.imshow(np.arange(6)[None, :], cmap=DELAY_CMAP, aspect="auto", extent=(0, 6, 0, 1))
    k.set_yticks([]); k.set_xticks(np.arange(6) + 0.5)
    k.set_xticklabels(["< 0.25", "0.25–0.5", "0.5–1", "1–2", "2–4", "> 4"], fontsize=8, color=INK2)
    k.tick_params(length=0)
    for s in k.spines.values():
        s.set_visible(False)
    k.set_title("truck minutes lost per km vs open road", fontsize=8.5, color=INK2, loc="left")


WB_PIN, ROAD_PIN = "#17252a", "#eb6834"


PIN_TEXTS = []


def pins(ax, b, size=9, start=1, face="white", text=INK):
    """A dot at the true place and a numbered circle, which spread_pins() moves clear of its neighbours."""
    for i, r in enumerate(b.itertuples(), start):
        ax.scatter([r.lon], [r.lat], s=22, color=face, edgecolor=INK, linewidth=0.8, zorder=19)
        PIN_TEXTS.append((ax, r.lon, r.lat, ax.text(r.lon, r.lat, str(i), ha="center", va="center", fontsize=size,
                                                     fontweight="bold", color=text, zorder=21,
                                                     bbox=dict(boxstyle="circle,pad=0.3", fc=face, ec=INK, lw=1.3))))


HUB_TEXTS = []


def hub_label(ax, x, y, name, fs=9.5):
    """Hub names join the pins in spread_pins(), so neither covers the other."""
    HUB_TEXTS.append((ax, x, y, ax.text(x, y, name, fontsize=fs, color=INK, fontweight="bold", zorder=22, ha="center",
                                        va="center", bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none",
                                                               alpha=0.9))))


def spread_pins(ax):
    from adjustText import adjust_text
    mine = [(x, y, t) for a, x, y, t in PIN_TEXTS + HUB_TEXTS if a is ax]
    if mine:
        adjust_text([t for _, _, t in mine], x=[x for x, _, _ in mine], y=[y for _, y, _ in mine], ax=ax,
                    expand=(1.5, 1.7), only_move={"text": "xy"}, arrowprops=dict(arrowstyle="-", color=INK, lw=0.9))


def pin_list(fig, b, x, y, dy=0.035, size=9.5, start=1, color=INK):
    for i, r in enumerate(b.itertuples(), start):
        j = i - start
        fig.text(x, y - j * dy, f"{i:>2}", fontsize=size, color=color, fontweight="bold", family="monospace")
        fig.text(x + 0.025, y - j * dy, f"{r.label}", fontsize=size, color=INK)
        fig.text(x + 0.025, y - j * dy - dy * 0.45,
                 f"{ART.road[r.corridor]} · km {r.km_from:.0f} · +{r.truck_excess_min:.1f} truck min",
                 fontsize=size - 2, color=INK2)


def title(fig, t, sub, y=0.965):
    fig.text(0.03, y, t, fontsize=19, color=INK, fontweight="bold")
    fig.text(0.03, y - 0.035, sub, fontsize=10.5, color=INK2)


def save(fig, name):
    fig.savefig(os.path.join(FIG, name), dpi=150, facecolor=SURF, bbox_inches="tight")
    plt.close(fig)
    print("wrote", name, flush=True)


# ---------------------------------------------------------------- r01 study area
def draw_arteries(ax, lw_trade=3.2, lw_other=1.2, labels=True, extent=None, hub_size=70, fs=10.5):
    for name, a in ART.iterrows():
        col = EAST if a.region == "East" else SOUTH
        lw = lw_trade if a.trade else lw_other
        gpd.GeoSeries([LINES[name]], crs=4326).plot(ax=ax, aspect=None, color=INK, linewidth=lw + 1.0, zorder=6)
        gpd.GeoSeries([LINES[name]], crs=4326).plot(ax=ax, aspect=None, color=col, linewidth=lw, zorder=7)
    for h, g in ART.groupby("hub"):
        x, y = g.start.iloc[0]
        if extent and not (extent[0] < x < extent[1] and extent[2] < y < extent[3]):
            continue
        ax.scatter([x], [y], s=hub_size, color=INK, edgecolor="white", linewidth=1.2, zorder=10)
        if labels:
            off = {"pretoria": (8, 6), "johannesburg": (-8, -12), "dodoma": (8, 0), "dar_es_salaam": (8, -4)}.get(h, (8, 2))
            ax.annotate(f"{g.hub_name.iloc[0]}  ({len(g)})", (x, y), xytext=off, textcoords="offset points",
                        ha="right" if off[0] < 0 else "left", fontsize=fs, color=INK, fontweight="bold", zorder=11,
                        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))


fig = plt.figure(figsize=(12, 14), facecolor=SURF)
ax = fig.add_axes([0.02, 0.02, 0.96, 0.86])
EXT_ALL = (13.5, 42.0, -35.2, 5.2)
basemap(ax, EXT_ALL)
draw_arteries(ax)
GAUT = (26.9, 29.6, -27.2, -24.9)
ax.add_patch(Rectangle((GAUT[0], GAUT[2]), GAUT[1] - GAUT[0], GAUT[3] - GAUT[2], fill=False, ec=INK, lw=1.1, zorder=12))
ins = fig.add_axes([0.70, 0.03, 0.27, 0.215])
basemap(ins, GAUT, country_labels=False)
draw_arteries(ins, lw_trade=3.4, lw_other=2.2, extent=GAUT, hub_size=90, fs=10)
for s_ in ins.spines.values():
    s_.set_visible(True); s_.set_color(INK); s_.set_linewidth(1.1)
ins.set_title("Gauteng: Pretoria and Johannesburg (13 roads)", fontsize=9.5, color=INK, loc="left")
tot_km = km.sum()
ax.legend(handles=[Line2D([], [], color=EAST, lw=3.2, label="East Africa: trade corridor, full length"),
                   Line2D([], [], color=EAST, lw=1.2, label="East Africa: other artery, first 200 km"),
                   Line2D([], [], color=SOUTH, lw=3.2, label="Southern Africa: trade corridor, full length"),
                   Line2D([], [], color=SOUTH, lw=1.2, label="Southern Africa: other artery, first 200 km"),
                   Line2D([], [], marker="o", ls="none", color=INK, label="hub (number of arteries)")],
          loc="upper left", bbox_to_anchor=(0.01, 0.80), frameon=True, facecolor="white", edgecolor=GRID, fontsize=10)
title(fig, f"Study area: {len(ART)} roads out of {ART.hub.nunique()} capitals and trade hubs",
      f"Every national route leaving each hub, cut at the border; {tot_km:,.0f} km in ten countries. "
      "Trade corridors run their full length.", y=0.93)
save(fig, "r01_study_area.png")

# ---------------------------------------------------------------- r02 delay by cause, per hub
cz = causes.merge(ART[["hub", "hub_name", "region"]], left_on="corridor", right_index=True)
hub_km = km.groupby(ART.hub).sum()
hc = cz.groupby(["hub", "cause"]).minutes.sum().unstack(fill_value=0).div(hub_km, axis=0) * 100
hc = hc.loc[:, [c for c in CAUSE_COL if c in hc]]
order = list(hc.assign(t=hc.sum(axis=1), r=reg).sort_values(["r", "t"], ascending=[True, False]).index)
fig, ax = plt.subplots(figsize=(13, 8.5), facecolor=SURF)
y = np.arange(len(order))
left = np.zeros(len(order))
for c in hc.columns:
    v = hc.loc[order, c].to_numpy()
    ax.barh(y, v, left=left, color=CAUSE_COL[c], height=0.66, label=c, linewidth=0)
    left += v
for yi, h in zip(y, order):
    ax.text(left[yi] + 0.6, yi, f"{left[yi]:.0f}", va="center", fontsize=10, color=INK, fontweight="bold")
ax.set_yticks(y)
ax.set_yticklabels([f"{ART[ART.hub == h].hub_name.iloc[0]}" for h in order], fontsize=11, color=INK)
for lab, h in zip(ax.get_yticklabels(), order):
    lab.set_color(EAST if reg[h] == "East" else SOUTH)
ax.invert_yaxis()
ax.set_xlim(0, left.max() * 1.13)
style(ax)
region_divider(ax, order)
ax.set_xlabel("truck minutes lost per 100 km vs open road (all arteries of the hub, full length)", fontsize=10, color=INK2)
ax.legend(loc="lower right", frameon=False, fontsize=9.5, labelcolor=INK2, ncol=2)
title(fig, "What slows trucks leaving each hub", "East African hubs in red, Southern in teal. Signals and crossings "
      "in South Africa reflect denser OSM mapping as well as real controls.", y=0.99)
save(fig, "r02_delay_by_cause.png")

# ---------------------------------------------------------------- r03 bottlenecks, East and Southern
# Weighbridges (an assumed ~10 min stop each) and the worst stretches caused by the road itself
# (roadside activity, junctions, signals, humps, police posts) are pinned as two sets.
for region, ext, fs, fname in (("East", (28.3, 40.6, -11.6, 4.6), (17, 11.5), "r03_bottlenecks_east.png"),
                               ("Southern", (13.0, 36.0, -34.9, -8.0), (17, 12.5), "r03_bottlenecks_southern.png")):
    hr = H[H.region == region]
    bw = distinct(hr[hr.lead == "weighbridge"], 6)
    bo = distinct(hr[hr.lead != "weighbridge"], 8)
    fig = plt.figure(figsize=fs, facecolor=SURF)
    ax = fig.add_axes([0.0, 0.04, 0.6, 0.86])
    basemap(ax, ext)
    delay_lines(ax, ART[ART.region == region].index, lw=3.0)
    for h, g in ART[ART.region == region].groupby("hub"):
        x, y = g.start.iloc[0]
        ax.scatter([x], [y], s=40, color=INK, edgecolor="white", zorder=18)
        hub_label(ax, x, y, g.hub_name.iloc[0])
    pins(ax, bo, start=1, face=ROAD_PIN, text="white")
    pins(ax, bw, start=len(bo) + 1, face=WB_PIN, text="white")
    spread_pins(ax)
    if region == "Southern":   # Gauteng zoom: Pretoria, Johannesburg and their crowded pins
        G = (27.0, 29.2, -26.95, -25.15)
        ax.add_patch(Rectangle((G[0], G[2]), G[1] - G[0], G[3] - G[2], fill=False, ec=INK, lw=1.0, zorder=23))
        ins = fig.add_axes([0.035, 0.07, 0.24, 0.27])
        basemap(ins, G, country_labels=False)
        delay_lines(ins, ART[ART.region == region].index, lw=3.4)
        for s_ in ins.spines.values():
            s_.set_visible(True); s_.set_color(INK)
        for h in ("pretoria", "johannesburg"):
            x, y = ART[ART.hub == h].start.iloc[0]
            ins.scatter([x], [y], s=50, color=INK, edgecolor="white", zorder=18)
            hub_label(ins, x, y, ART[ART.hub == h].hub_name.iloc[0], fs=9)
        nb = len(bo)
        for d, face, base in ((bo, ROAD_PIN, 1), (bw, WB_PIN, nb + 1)):
            for i, r in enumerate(d.itertuples(), base):
                if G[0] < r.lon < G[1] and G[2] < r.lat < G[3]:
                    ins.scatter([r.lon], [r.lat], s=22, color=face, edgecolor=INK, linewidth=0.8, zorder=19)
                    PIN_TEXTS.append((ins, r.lon, r.lat, ins.text(r.lon, r.lat, str(i), ha="center", va="center",
                                     fontsize=9, fontweight="bold", color="white", zorder=21,
                                     bbox=dict(boxstyle="circle,pad=0.3", fc=face, ec=INK, lw=1.3))))
        spread_pins(ins)
        ins.set_title("Gauteng", fontsize=10, color=INK, loc="left")
    x0 = 0.585
    fig.text(x0, 0.86, "Where the road itself costs most", fontsize=12, color=ROAD_PIN, fontweight="bold")
    fig.text(x0, 0.84, "roadside activity, junctions, signals, humps, police posts", fontsize=9, color=INK2)
    pin_list(fig, bo, x0, 0.8, dy=0.043, start=1, color=ROAD_PIN)
    yw = 0.8 - len(bo) * 0.043 - 0.03
    fig.text(x0, yw, "Weighbridges", fontsize=12, color=WB_PIN, fontweight="bold")
    fig.text(x0, yw - 0.02, "each stop assumed about 10 minutes (5–30)", fontsize=9, color=INK2)
    pin_list(fig, bw, x0, yw - 0.06, dy=0.043, start=len(bo) + 1, color=WB_PIN)
    delay_key(fig, [x0, 0.035, 0.3, 0.018])
    title(fig, f"Bottlenecks: the worst 2 km stretches, {region} Africa",
          "Truck minutes lost in 2 km against open road, light traffic. Overlapping roads counted once.", y=0.96)
    save(fig, fname)

# ---------------------------------------------------------------- r04 road safety
SP = O("safety_pieces.csv")
SB = O("safety_by_type.csv")
SS = O("safety_schools.csv")
SP["hub"] = SP.corridor.map(ART.hub)
SP["length_km"] = SP.merge(pieces[["corridor", "piece", "length_km"]], on=["corridor", "piece"], how="left").length_km
hs = SP.groupby("hub").agg(exposure=("exposure", "sum"), people=("people_300m", "sum"), km=("length_km", "sum"))
hs["exposure_per_km"] = hs.exposure / hs.km
hs["people_per_km"] = hs.people / hs.km
sett = SB[SB.road_type == "roadside settlement"].assign(hub=lambda d: d.corridor.map(ART.hub))
sett = sett.groupby("hub").agg(people=("people", "sum"), exposure=("exposure", "sum"))
tot = SB.assign(hub=lambda d: d.corridor.map(ART.hub)).groupby("hub")[["people", "exposure"]].sum()
hs["settle_people_share"] = sett.people / tot.people
hs["settle_exposure_share"] = sett.exposure / tot.exposure
hs["schools_per_100km"] = SS.assign(hub=SS.corridor.map(ART.hub)).groupby("hub").size().reindex(hs.index).fillna(0) / hs.km * 100
o2 = list(hs.assign(r=reg).sort_values(["r", "exposure_per_km"], ascending=[True, False]).index)
names = [ART[ART.hub == h].hub_name.iloc[0] for h in o2]
cols = [EAST if reg[h] == "East" else SOUTH for h in o2]
fig, axs = plt.subplots(1, 3, figsize=(17, 8.5), facecolor=SURF, gridspec_kw=dict(wspace=0.12), sharey=True)
y = np.arange(len(o2))
ax = axs[0]
ax.barh(y, hs.loc[o2, "exposure_per_km"], color=cols, height=0.62)
for yi, v in zip(y, hs.loc[o2, "exposure_per_km"]):
    ax.text(v * 1.02, yi, f"{v:.2f}", va="center", fontsize=9.5, color=INK)
ax.set_title("Exposure per km of road\n(people × trucks × speed⁴, assumed trucks)", fontsize=11, color=INK, loc="left")
ax = axs[1]
ax.hlines(y, hs.loc[o2, "settle_people_share"] * 100, hs.loc[o2, "settle_exposure_share"] * 100, color=GRID, lw=3)
ax.scatter(hs.loc[o2, "settle_people_share"] * 100, y, color="#d9a441", s=55, zorder=3, label="share of people")
ax.scatter(hs.loc[o2, "settle_exposure_share"] * 100, y, color=cols, s=70, zorder=4, label="share of exposure")
ax.set_xlim(0, 100)
ax.set_title("Roadside settlements between towns:\nshare of people vs share of exposure (%)", fontsize=11, color=INK, loc="left")
ax.legend(handles=[Line2D([], [], marker="o", ls="none", color="#d9a441", label="share of people living by the road"),
                   Line2D([], [], marker="o", ls="none", color=INK2, label="share of the exposure")],
          loc="lower center", bbox_to_anchor=(0.5, -0.16), ncol=2, frameon=False, fontsize=9.5)
ax = axs[2]
ax.barh(y, hs.loc[o2, "schools_per_100km"], color=cols, height=0.62)
for yi, v in zip(y, hs.loc[o2, "schools_per_100km"]):
    ax.text(v + 0.3, yi, f"{v:.1f}", va="center", fontsize=9.5, color=INK)
ax.set_title("Half-km stretches with a school, trucks\nabove 50 km/h and no mapped crossing, per 100 km",
             fontsize=11, color=INK, loc="left")
axs[0].set_xlim(0, hs.exposure_per_km.max() * 1.18)
axs[2].set_xlim(0, hs.schools_per_100km.max() * 1.18)
axs[0].set_yticks(y)
axs[0].set_yticklabels(names, fontsize=10.5)
axs[0].invert_yaxis()
for a in axs:
    style(a)
for lab, c in zip(axs[0].get_yticklabels(), cols):
    lab.set_color(c)
for a in axs:
    region_divider(a, o2)
title(fig, "Where fast trucks meet people", "Trucks per day are one assumed figure for every artery, so exposure "
      "compares people and speed, not traffic. Schools and crossings come from OSM, mapped far more fully in "
      "some countries (Uganda's schools especially).", y=1.02)
save(fig, "r04_safety.png")

# ---------------------------------------------------------------- r05 fuel and CO2
FP = O("fuel_co2_pieces.csv")
FC = O("fuel_co2_by_cause.csv")
FP["hub"] = FP.corridor.map(ART.hub)
FP = FP.merge(pieces[["corridor", "piece", "length_km"]], on=["corridor", "piece"], how="left")
fh = FP.groupby("hub").agg(litres=("litres", "sum"), open=("litres_open", "sum"), fr=("friction_litres", "sum"),
                           km=("length_km", "sum"))
fh["extra_per_100km"] = fh.fr / fh.km * 100
fh["share"] = fh.fr / fh.litres * 100
fh["co2_per_100km"] = fh.extra_per_100km * 2.68
fcz = FC.assign(hub=FC.corridor.map(ART.hub)).groupby(["hub", "cause"]).litres.sum().unstack(fill_value=0).clip(lower=0)
fcz = fcz.div(fh.km, axis=0) * 100
fcz = fcz.loc[:, [c for c in CAUSE_COL if c in fcz]]
o3 = list(fh.assign(r=reg).sort_values(["r", "extra_per_100km"], ascending=[True, False]).index)
fig, (ax, ax2) = plt.subplots(1, 2, figsize=(16, 8.5), facecolor=SURF, gridspec_kw=dict(width_ratios=[1.6, 1], wspace=0.3))
y = np.arange(len(o3))
left = np.zeros(len(o3))
for c in fcz.columns:
    v = fcz.loc[o3, c].to_numpy()
    ax.barh(y, v, left=left, color=CAUSE_COL[c], height=0.64, label=c, linewidth=0)
    left += v
for yi, h in zip(y, o3):
    ax.text(left[yi] + 0.2, yi, f"{fh.extra_per_100km[h]:.1f} L · {fh.co2_per_100km[h]:.0f} kg CO₂", va="center",
            fontsize=9.5, color=INK)
ax.set_xlabel("extra litres of diesel per 100 km for one loaded truck, by cause", fontsize=10, color=INK2)
ax.set_xlim(0, left.max() * 1.35)
ax.legend(loc="lower right", frameon=False, fontsize=9, labelcolor=INK2, ncol=2)
ax2.barh(y, fh.loc[o3, "share"], color=[EAST if reg[h] == "East" else SOUTH for h in o3], height=0.64)
for yi, v in zip(y, fh.loc[o3, "share"]):
    ax2.text(v + 0.4, yi, f"{v:.0f}%", va="center", fontsize=9.5, color=INK)
ax2.set_xlabel("share of the trip's diesel burnt by stop-and-go", fontsize=10, color=INK2)
ax2.set_xlim(0, fh.share.max() * 1.25)
for a in (ax, ax2):
    style(a)
    a.set_yticks(y)
    a.set_yticklabels([ART[ART.hub == h].hub_name.iloc[0] for h in o3] if a is ax else [], fontsize=11, color=INK)
    a.invert_yaxis()
for lab, h in zip(ax.get_yticklabels(), o3):
    lab.set_color(EAST if reg[h] == "East" else SOUTH)
for a in (ax, ax2):
    region_divider(a, o3)
title(fig, "The diesel and carbon cost of stop-and-go", "Physical fuel model on each road's speed profile "
      "(rolling, air, re-acceleration, idling), against the same truck on open road; CO₂ 2.68 kg per litre.\n"
      "Speed humps are assumed (one per town piece), so the hump share is the least certain part.", y=1.0)
save(fig, "r05_fuel_co2.png")

# ---------------------------------------------------------------- r06 trade corridors, full length
TR = ART[ART.trade].copy()
TR["min_per_100km"] = [causes[causes.corridor == c].minutes.sum() / km[c] * 100 for c in TR.index]
TR["fuel_per_100km"] = [FP[FP.corridor == c].friction_litres.sum() / km[c] * 100 for c in TR.index]
TR["exposure_per_km"] = [SP[SP.corridor == c].exposure.sum() / km[c] for c in TR.index]
TR["km_"] = km.reindex(TR.index)
TR = TR.sort_values("min_per_100km", ascending=True)
fig, axs = plt.subplots(1, 3, figsize=(17, 0.42 * len(TR) + 2.5), facecolor=SURF, gridspec_kw=dict(wspace=0.08),
                        sharey=True)
y = np.arange(len(TR))
cl = [EAST if r == "East" else SOUTH for r in TR.region]
for a, col, lab, fmt in ((axs[0], "min_per_100km", "truck minutes lost per 100 km", "{:.0f}"),
                         (axs[1], "fuel_per_100km", "extra diesel per 100 km (L)", "{:.1f}"),
                         (axs[2], "exposure_per_km", "safety exposure per km", "{:.2f}")):
    a.barh(y, TR[col], color=cl, height=0.62)
    for yi, v in zip(y, TR[col]):
        a.text(v, yi, " " + fmt.format(v), va="center", fontsize=9, color=INK)
    a.set_xlabel(lab, fontsize=10, color=INK2)
    style(a)
axs[0].set_yticks(y)
axs[0].set_yticklabels([f"{r.road} · {r.km_:.0f} km" for r in TR.itertuples()], fontsize=10, color=INK)
for lab, c in zip(axs[0].get_yticklabels(), cl):
    lab.set_color(c)
title(fig, "The trade corridors side by side", "Main freight routes from each hub, full length inside the country. "
      "East in red, Southern in teal.", y=1.0)
save(fig, "r06_trade_corridors.png")

# ---------------------------------------------------------------- r10 one sheet per country
for country, iso in ISO.items():
    arts = ART[ART.country == country]
    if arts.empty:
        continue
    g = pieces[pieces.corridor.isin(arts.index)]
    x0, y0, x1, y1 = g.total_bounds   # framed on the roads (a country outline can include far islands)
    pad = 0.12 * max(x1 - x0, y1 - y0)
    ext = (x0 - pad, x1 + pad, y0 - pad, y1 + pad)
    b = distinct(H[H.corridor.isin(arts.index)], 8)
    fig = plt.figure(figsize=(17, 9.5), facecolor=SURF)
    ax = fig.add_axes([0.0, 0.1, 0.47, 0.77])
    basemap(ax, ext)
    delay_lines(ax, arts.index, lw=2.6)
    for h, gg in arts.groupby("hub"):
        hx, hy = gg.start.iloc[0]
        ax.scatter([hx], [hy], s=60, color=INK, edgecolor="white", zorder=19)
        hub_label(ax, hx, hy, gg.hub_name.iloc[0], fs=10)
    for name, a in arts.iterrows():
        ex, ey = a.end
        HUB_TEXTS.append((ax, ex, ey, ax.text(ex, ey, a.toward, fontsize=8.5, color=INK2, zorder=18,
                                              bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.7))))
    pins(ax, b, size=8.5)
    spread_pins(ax)
    if country == "South Africa":   # Gauteng zoom, as on the Southern bottleneck map
        G = (27.0, 29.2, -26.95, -25.15)
        ax.add_patch(Rectangle((G[0], G[2]), G[1] - G[0], G[3] - G[2], fill=False, ec=INK, lw=1.0, zorder=23))
        ins = fig.add_axes([0.395, 0.12, 0.205, 0.33])
        basemap(ins, G, country_labels=False)
        delay_lines(ins, arts.index, lw=3.2)
        for s_ in ins.spines.values():
            s_.set_visible(True); s_.set_color(INK)
        for h in ("pretoria", "johannesburg"):
            x, y = ART[ART.hub == h].start.iloc[0]
            ins.scatter([x], [y], s=45, color=INK, edgecolor="white", zorder=18)
            hub_label(ins, x, y, ART[ART.hub == h].hub_name.iloc[0], fs=8.5)
        for i, r in enumerate(b.itertuples(), 1):
            if G[0] < r.lon < G[1] and G[2] < r.lat < G[3]:
                ins.scatter([r.lon], [r.lat], s=20, color="white", edgecolor=INK, linewidth=0.8, zorder=19)
                PIN_TEXTS.append((ins, r.lon, r.lat, ins.text(r.lon, r.lat, str(i), ha="center", va="center",
                                  fontsize=8.5, fontweight="bold", color=INK, zorder=21,
                                  bbox=dict(boxstyle="circle,pad=0.3", fc="white", ec=INK, lw=1.3))))
        spread_pins(ins)
        ins.set_title("Gauteng", fontsize=9.5, color=INK, loc="left")
    delay_key(fig, [0.05, 0.035, 0.3, 0.018])
    # Causes per road
    cc = causes[causes.corridor.isin(arts.index)].pivot_table(index="corridor", columns="cause", values="minutes",
                                                              aggfunc="sum").fillna(0)
    cc = cc.div(km.reindex(cc.index), axis=0) * 100
    cc = cc.loc[cc.sum(axis=1).sort_values(ascending=False).index, [c for c in CAUSE_COL if c in cc]]
    axb = fig.add_axes([0.62, 0.52, 0.35, 0.35])
    yy = np.arange(len(cc))
    lf = np.zeros(len(cc))
    for c in cc.columns:
        v = cc[c].to_numpy()
        if v.max() <= 0.05:
            continue
        axb.barh(yy, v, left=lf, color=CAUSE_COL[c], height=0.6, label=c, linewidth=0)
        lf += v
    for yi, v in zip(yy, lf):
        axb.text(v + 0.5, yi, f"{v:.0f}", va="center", fontsize=9.5, color=INK, fontweight="bold")
    axb.set_yticks(yy)
    axb.set_yticklabels([f"→ {ART.toward[c]}" + (f" ({ART.ref[c]})" if ART.ref[c] else "") +
                         ("  ★" if ART.trade[c] else "") for c in cc.index], fontsize=10, color=INK)
    axb.invert_yaxis()
    style(axb)
    axb.set_xlabel("truck minutes lost per 100 km, by cause   (★ trade corridor)", fontsize=9.5, color=INK2)
    axb.legend(loc="upper center", bbox_to_anchor=(0.45, -0.13), ncol=3, frameon=False, fontsize=8.5,
               labelcolor=INK2)
    fig.text(0.62, 0.33, "Worst 2 km stretches (numbered on the map)", fontsize=11, color=INK, fontweight="bold")
    pin_list(fig, b, 0.62, 0.295, dy=0.034, size=9)
    cname = COUNTRY_SHORT.get(country, country)
    fh_c = FP[FP.corridor.isin(arts.index)]
    title(fig, f"{cname}: {len(arts)} roads out of {', '.join(arts.hub_name.unique())}",
          f"{km.reindex(arts.index).sum():,.0f} km · truck minutes lost "
          f"{causes[causes.corridor.isin(arts.index)].minutes.sum() / km.reindex(arts.index).sum() * 100:.0f} per 100 km · "
          f"extra diesel {fh_c.friction_litres.sum() / km.reindex(arts.index).sum() * 100:.1f} L per 100 km per truck",
          y=0.95)
    save(fig, f"r10_country_{iso}.png")
