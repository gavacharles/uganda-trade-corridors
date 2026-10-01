"""Roadside growth observed to 2023: Google Open Buildings 2.5D Temporal, 2016-2023.

GHSL (09_growth.py) observes built-up land only to 2020; its 2025-2030 layers are projections.
Open Buildings 2.5D Temporal (GOOGLE/Research/open-buildings-temporal/v1, Earth Engine) gives a
yearly raster for 2016-2023 from Sentinel-2, at an effective 4 m resolution (provided at 0.5 m):
  - building_fractional_count: summed over the 0.5 m pixels of an area, the number of buildings
  - building_presence: uncalibrated model confidence that a pixel is part of a building
For every 500 m piece (outputs/pieces_typed.csv), the area within 300 m of the road is built
from the centreline through the piece midpoints. Per year:
  buildings = mean fractional count at 8 m x (area / 0.25 m^2)   (the mean pyramid keeps the sum)
  built_m2  = share of 4 m pixels with presence > 0.5 x area
The 8 m shortcut is checked against a full 0.5 m sum on sample pieces (printed). Pieces next to
each other overlap slightly at bends; growth rates are unaffected, levels are a little high.

A control ring 1-2 km from each road (same years, same method) separates roadside growth from
background growth and from any change in the imagery or model that affects every place alike:
percentage growth from a low base flatters the ring, so buildings added per km2 are compared too.
In the first run the ring grew faster in percent (36-57% against 22-48%) but gained only half to
two thirds as many buildings per km2, and the 2020-2022 rise shows in both: it may be partly a
change in the imagery or model, so the 2016-2023 trend is the result, not that jump.

Year-to-year values carry model noise (different imagery each year), so growth is reported as the
change in a straight-line fit over 2016-2023, as well as 2023 against 2016.

Needs the Earth Engine project in .env (EE_PROJECT=...). Writes outputs/growth_temporal_pieces.csv,
outputs/growth_temporal_summary.csv, figures/f17_growth_temporal.png.
"""
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import ee
from shapely.geometry import LineString
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config as C
from cartography import INK, INK2, SURF

# Corridor colours as in maplib.COL (maplib itself reads data/ on import)
COL = dict(zip(C.CORRIDORS, ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#8a5cc7"]))
C.load_env()
ee.Initialize(project=os.environ["EE_PROJECT"])
YEARS = list(range(2016, 2024))
BUF_M, SCALE_COUNT, SCALE_PRES, THRESH = 300, 8, 4, 0.5

P = pd.read_csv(os.path.join(C.OUTPUTS, "pieces_typed.csv")).sort_values(["corridor", "piece"])
pts = gpd.GeoDataFrame(P, geometry=gpd.points_from_xy(P.lon, P.lat), crs=4326).to_crs(C.UTM)
polys = []
for c, d in pts.groupby("corridor", sort=False):
    xy = np.array([(g.x, g.y) for g in d.geometry])
    mids = (xy[1:] + xy[:-1]) / 2
    for i in range(len(d)):
        a = mids[i - 1] if i > 0 else xy[0]
        b = mids[i] if i < len(mids) else xy[-1]
        line = LineString([a, xy[i], b]) if i not in (0, len(d) - 1) else LineString([a, b])
        polys.append(line.buffer(BUF_M, cap_style=2))
G = gpd.GeoDataFrame(P[["corridor", "piece", "km_start", "road_type"]].reset_index(drop=True),
                     geometry=polys, crs=C.UTM)
G["area_m2"] = G.area
G = G.to_crs(4326)

ic = ee.ImageCollection("GOOGLE/Research/open-buildings-temporal/v1")


def year_image(y):
    im = ic.filterDate(f"{y}-01-01", f"{y + 1}-01-01").mosaic()
    return (im.select("building_fractional_count").rename(f"c{y}"),
            im.select("building_presence").gt(THRESH).rename(f"p{y}"))


COUNT = ee.Image.cat([year_image(y)[0] for y in YEARS])
PRES = ee.Image.cat([year_image(y)[1] for y in YEARS])


def reduce(img, fc, scale):
    return img.reduceRegions(collection=fc, reducer=ee.Reducer.mean(), scale=scale, tileScale=4)


# Check the 8 m shortcut (skipped with --reuse) on three sample pieces against the full 0.5 m sum (2023)
chk = G.sample(0 if "--reuse" in os.sys.argv else 3, random_state=1)
for _, r in chk.iterrows():
    geom = ee.Geometry(r.geometry.__geo_interface__)
    full = COUNT.select("c2023").reduceRegion(ee.Reducer.sum(), geom, 0.5, maxPixels=1e9, tileScale=4).get("c2023")
    fast = COUNT.select("c2023").reduceRegion(ee.Reducer.mean(), geom, SCALE_COUNT, tileScale=4).get("c2023")
    f, m = ee.Number(full).getInfo(), ee.Number(fast).getInfo() * r.area_m2 / 0.25
    print(f"check {r.corridor} piece {r.piece}: 0.5 m sum {f:.1f}, 8 m shortcut {m:.1f}")

PIECES_CSV = os.path.join(C.OUTPUTS, "growth_temporal_pieces.csv")
REUSE = "--reuse" in os.sys.argv and os.path.exists(PIECES_CSV)   # skip the per-piece extraction
rows = []
for c, g in ([] if REUSE else G.groupby("corridor", sort=False)):
    for start in range(0, len(g), 250):
        part = g.iloc[start:start + 250]
        fc = ee.FeatureCollection([ee.Feature(ee.Geometry(geom.__geo_interface__), {"i": int(i)})
                                   for i, geom in zip(part.index, part.geometry)])
        rc = reduce(COUNT, fc, SCALE_COUNT).getInfo()["features"]
        rp = reduce(PRES, fc, SCALE_PRES).getInfo()["features"]
        for fcnt, fpr in zip(rc, rp):
            i = fcnt["properties"]["i"]
            a = G.at[i, "area_m2"]
            for y in YEARS:
                rows.append(dict(corridor=c, piece=G.at[i, "piece"], km_start=G.at[i, "km_start"],
                                 road_type=G.at[i, "road_type"], year=y,
                                 buildings=(fcnt["properties"].get(f"c{y}") or 0) * a / 0.25,
                                 built_m2=(fpr["properties"].get(f"p{y}") or 0) * a))
        print(c, start + len(part), "pieces", flush=True)
T = pd.read_csv(PIECES_CSV) if REUSE else pd.DataFrame(rows)

# Control: a ring 1-2 km from each road, one region per corridor
lines = pts.groupby("corridor", sort=False).geometry.apply(lambda g: LineString([(p.x, p.y) for p in g]))
ring = gpd.GeoSeries([l.buffer(2000).difference(l.buffer(1000)) for l in lines], index=lines.index, crs=C.UTM)
ctrl = []
for c, geom in ring.to_crs(4326).items():   # coarse scale: a ring of 400-900 km2 times out at 16 m
    v = COUNT.reduceRegion(ee.Reducer.mean(), ee.Geometry(geom.simplify(0.001).__geo_interface__), 60,
                           maxPixels=1e10, tileScale=16, bestEffort=True).getInfo()
    a = ring[c].area
    ctrl += [dict(corridor=c, year=y, area_km2=a / 1e6, buildings=(v.get(f"c{y}") or 0) * a / 0.25) for y in YEARS]
    print("control", c, flush=True)
K = pd.DataFrame(ctrl)
K.round(1).to_csv(os.path.join(C.OUTPUTS, "growth_temporal_control.csv"), index=False)
if not REUSE:
    T.round(2).to_csv(PIECES_CSV, index=False)


def summarise(d):
    s = d.groupby("year")[["buildings", "built_m2"]].sum()
    out = {}
    for k in ("buildings", "built_m2"):
        slope, icpt = np.polyfit(s.index, s[k], 1)
        fit16, fit23 = icpt + slope * 2016, icpt + slope * 2023
        out[f"{k}_2016"], out[f"{k}_2023"] = s[k].iloc[0], s[k].iloc[-1]
        out[f"{k}_growth_2016_2023_pct"] = 100 * (s[k].iloc[-1] / s[k].iloc[0] - 1)
        out[f"{k}_trend_growth_pct"] = 100 * (fit23 / fit16 - 1)
        out[f"{k}_trend_pct_a_year"] = 100 * ((fit23 / fit16) ** (1 / 7) - 1)
    return pd.Series(out)


S = pd.concat([T.groupby("corridor").apply(summarise).assign(road_type="all").reset_index(),
               T.groupby(["corridor", "road_type"]).apply(summarise).reset_index()], ignore_index=True)
# GHSL 2015-2020 annual rate for comparison (09_growth.py)
gh = pd.read_csv(os.path.join(C.OUTPUTS, "growth_summary.csv"))
gh = gh[gh.road_type == "all"].set_index("corridor")
S["ghsl_2015_2020_pct_a_year"] = S.corridor.map(100 * ((gh.built_ha_2020 / gh.built_ha_2015) ** (1 / 5) - 1)).where(S.road_type == "all")

def trend(s):
    slope, icpt = np.polyfit(s.index, s.values, 1)
    return 100 * ((icpt + slope * 2023) / (icpt + slope * 2016) - 1)


ck = K.groupby("corridor").apply(lambda d: trend(d.set_index("year").buildings))
S["control_1_2km_trend_growth_pct"] = S.corridor.map(ck).where(S.road_type == "all")
S["excess_over_control_pp"] = S.buildings_trend_growth_pct - S.control_1_2km_trend_growth_pct
road_km2 = G.to_crs(C.UTM).groupby("corridor").geometry.apply(lambda g: g.union_all().area / 1e6)
k16, k23 = (K[K.year == y].set_index("corridor") for y in (2016, 2023))
S["road_added_per_km2"] = S.corridor.map((S.set_index("corridor").buildings_2023 - S.set_index("corridor").buildings_2016)
                                        [lambda x: ~x.index.duplicated()] / road_km2).where(S.road_type == "all")
S["control_added_per_km2"] = S.corridor.map((k23.buildings - k16.buildings) / k16.area_km2).where(S.road_type == "all")
S["added_ratio_road_to_control"] = S.road_added_per_km2 / S.control_added_per_km2
S.round(2).to_csv(os.path.join(C.OUTPUTS, "growth_temporal_summary.csv"), index=False)
print(S[S.road_type == "all"][["corridor", "buildings_2016", "buildings_2023", "buildings_trend_growth_pct",
                               "buildings_trend_pct_a_year", "built_m2_trend_pct_a_year",
                               "ghsl_2015_2020_pct_a_year", "control_1_2km_trend_growth_pct",
                               "excess_over_control_pp", "road_added_per_km2", "control_added_per_km2",
                               "added_ratio_road_to_control"]].round(1).to_string(index=False))

# Figure: buildings within 300 m, indexed to 2016, and trend growth by road type
order = list(C.CORRIDORS)
fig, (ax, ax2) = plt.subplots(1, 2, figsize=(14, 5), facecolor=SURF, gridspec_kw=dict(width_ratios=[1.2, 1], wspace=0.35))
for c in order:
    s = T[T.corridor == c].groupby("year").buildings.sum()
    ax.plot(s.index, 100 * s / s.iloc[0], color=COL[c], lw=2.2, marker="o", ms=4,
            label=f"{C.CORRIDORS[c]['short']} ({C.CORRIDORS[c]['ref']})")
kk = K.groupby("year").buildings.sum()
ax.plot(kk.index, 100 * kk / kk.iloc[0], color=INK2, lw=1.6, ls="--", label="all roads, 1–2 km away (control)")
ax.set_ylabel("buildings within 300 m, 2016 = 100", fontsize=9, color=INK2)
ax.legend(frameon=False, fontsize=9, labelcolor=INK2, loc="upper left")
types = ["open road", "roadside settlement", "town"]
tcol = {"open road": "#a9c8ec", "roadside settlement": "#3574c4", "town": "#0d2d57"}
sub = S[S.road_type.isin(types)].pivot(index="corridor", columns="road_type", values="buildings_trend_growth_pct").reindex(order)
x = np.arange(len(order))
for j, t in enumerate(types):
    ax2.bar(x + (j - 1) * 0.26, sub[t], width=0.25, color=tcol[t], label=t, linewidth=0)
ax2.set_xticks(x)
ax2.set_xticklabels([C.CORRIDORS[c]["short"] for c in order], fontsize=9.5, color=INK)
ax2.set_ylabel("buildings, trend growth 2016–2023, %", fontsize=9, color=INK2)
ax2.axhline(0, color=INK2, lw=0.6)
ax2.legend(frameon=False, fontsize=9, labelcolor=INK2)
for a in (ax, ax2):
    a.set_facecolor(SURF)
    for s_ in ("top", "right"):
        a.spines[s_].set_visible(False)
    a.spines["left"].set_color("#e4e3df")
    a.spines["bottom"].set_color("#e4e3df")
    a.grid(axis="y", color="#e4e3df", linewidth=0.6)
    a.set_axisbelow(True)
    a.tick_params(colors=INK2, length=0)
fig.text(0.01, 1.04, "The roadside kept filling in after 2020", fontsize=15, color=INK)
fig.text(0.01, 0.985, "Buildings within 300 m of each road, Google Open Buildings 2.5D Temporal (yearly, 2016–2023). "
         "Trend growth: change in a straight-line fit, which damps year-to-year model noise.", fontsize=9, color=INK2)
fig.savefig(os.path.join(C.FIGURES, "f17_growth_temporal.png"), dpi=150, facecolor=SURF, bbox_inches="tight")
print("wrote outputs/growth_temporal_*.csv, figures/f17_growth_temporal.png")
