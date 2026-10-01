"""Where do fast trucks meet people? Road-safety exposure along the corridors.

Crash records are not open at this detail, so this ranks exposure, not crashes. For each
500 m piece:
  people      WorldPop 2025 (constrained, 100 m; config.WORLDPOP) residents in cells within 300 m of the
              road, each cell counted once, in its nearest piece
  truck speed the model's loaded-truck speed through the piece (central case, leaving
              Kampala): length / minutes, without stops
  crossings   marked pedestrian crossings and signals on the road (OSM)
  schools, markets, stops  within 300, 200 and 100 m (OSM)

Exposure index per 2 km stretch = people x trucks a day (config.TRUCKS_PER_DAY) x (speed/50)^4.
The fourth power is Nilsson's power model for fatal crashes (Nilsson 2004; Elvik et al. 2019
confirm exponents near 4 for fatalities): a truck at 70 km/h carries about 3.8 times the fatal risk
of one at 50. The index compares stretches; it is not a crash rate.

Also lists pieces with a school within 300 m, a modelled truck speed above 50 km/h and no
marked crossing within 500 m either side.

Writes outputs/safety_pieces.csv, outputs/safety_stretches.csv (top 10 per corridor),
outputs/safety_schools.csv, figures/f10_safety.png.
"""
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.windows import from_bounds
import requests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config as C
from cartography import INK, INK2, SURF
from travel_model import CENTRAL, P, piece_minutes

BUF_M = 300
WPS = list(getattr(C, "POP_RASTERS", []))   # a study may supply its own population rasters
for url in ([] if WPS else C.WORLDPOP):   # otherwise WorldPop, one raster per country
    path = os.path.join(C.DATA, "worldpop", os.path.basename(url))
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with requests.get(url, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(path + ".part", "wb") as f:
                for blk in r.iter_content(1 << 20):
                    f.write(blk)
        os.replace(path + ".part", path)
    WPS.append(path)

pieces = gpd.read_file(os.path.join(C.DATA, "pieces.gpkg"))
pieces = P[["corridor", "piece"]].merge(pieces[["corridor", "piece", "geometry"]], how="left")
pieces = gpd.GeoDataFrame(pieces, geometry="geometry", crs=4326).to_crs(C.UTM)
pop = np.zeros(len(P))
for wp in WPS:
    with rasterio.open(wp) as src:
        for corridor in C.CORRIDORS:
            m = (P.corridor == corridor).to_numpy()
            x0, y0, x1, y1 = pieces[m].to_crs(src.crs).total_bounds
            b = src.bounds
            if x1 < b.left or x0 > b.right or y1 < b.bottom or y0 > b.top:
                continue
            pad = 0.01 if src.crs.is_geographic else 1000   # about 1 km, in degrees or metres
            w = from_bounds(x0 - pad, y0 - pad, x1 + pad, y1 + pad, transform=src.transform)
            w = w.round_offsets().round_lengths()
            a = src.read(1, window=w, boundless=True, fill_value=0)
            tf = src.window_transform(w)
            a = np.where(a == src.nodata, 0, a) if src.nodata is not None else a
            rr, cc = np.nonzero(a > 0)
            xs, ys = rasterio.transform.xy(tf, rr, cc)
            cells = gpd.GeoDataFrame({"pop": a[rr, cc]}, geometry=gpd.points_from_xy(xs, ys), crs=src.crs).to_crs(C.UTM)
            j = gpd.sjoin_nearest(cells, pieces[m][["geometry"]], max_distance=BUF_M, how="inner")
            j = j[~j.index.duplicated()]
            s_ = j.groupby("index_right")["pop"].sum()
            pop[s_.index.to_numpy()] += s_.to_numpy()   # index_right is the row position in P order
            print(f"{corridor}: {s_.sum():,.0f} people within {BUF_M} m ({os.path.basename(wp)})", flush=True)

S = P[["corridor", "piece", "km_start", "place", "road_type", "schools_300m", "markets_200m", "stops_100m",
       "ped_crossings", "signals"]].copy()
S["people_300m"] = pop.round(0)
# running speed: fixed stops (signals, humps, police, weighbridges) excluded
nostop = piece_minutes(CENTRAL, "truck", "outbound", off=("signals and crossings", "speed humps (assumed)",
                                                            "police posts", "weighbridge"))
S["truck_kmh"] = (P.length_km / nostop * 60).round(1)
S["trucks_per_day"] = S.corridor.map({c: v[0] for c, v in C.TRUCKS_PER_DAY.items()})
S["crossings"] = S.ped_crossings + S.signals
S["exposure"] = S.people_300m * S.trucks_per_day * (S.truck_kmh / 50) ** 4 / 1e6
S.to_csv(os.path.join(C.OUTPUTS, "safety_pieces.csv"), index=False)

# 2 km stretches, non-overlapping, ranked by exposure
st = []
for corridor, d in S.groupby("corridor", sort=False):
    d = d.reset_index(drop=True)
    for i in range(0, len(d) - 3, 4):
        g = d.iloc[i:i + 4]
        st.append(dict(corridor=corridor, km_from=g.km_start.iloc[0], km_to=g.km_start.iloc[-1] + 0.5,
                       place=g.place.dropna().mode().iloc[0] if g.place.notna().any() else "",
                       road_type=g.road_type.mode().iloc[0], people_300m=g.people_300m.sum(),
                       truck_kmh=g.truck_kmh.mean(), crossings=g.crossings.sum(), schools=g.schools_300m.sum(),
                       markets=g.markets_200m.sum(), exposure=g.exposure.sum()))
st = pd.DataFrame(st)
st["exposure_share_of_corridor"] = st.exposure / st.groupby("corridor").exposure.transform("sum")
top = st.sort_values("exposure", ascending=False).groupby("corridor").head(10).round(2)
top.to_csv(os.path.join(C.OUTPUTS, "safety_stretches.csv"), index=False)
print(top.groupby("corridor").head(3).to_string(index=False))

# Schools near fast, uncrossed road
S["crossings_1km"] = S.groupby("corridor").crossings.transform(lambda x: x.rolling(3, center=True, min_periods=1).sum())
sch = S[(S.schools_300m > 0) & (S.truck_kmh > 50) & (S.crossings_1km == 0)]
sch[["corridor", "km_start", "place", "road_type", "schools_300m", "people_300m", "truck_kmh"]].to_csv(
    os.path.join(C.OUTPUTS, "safety_schools.csv"), index=False)
print(f"{len(sch)} pieces with a school, trucks above 50 km/h and no marked crossing within 500 m")

by_type = S.groupby(["corridor", "road_type"]).agg(people=("people_300m", "sum"), exposure=("exposure", "sum"),
                                                   km=("piece", "size"))
by_type["km"] = by_type.km * 0.5
by_type["exposure_share"] = by_type.exposure / by_type.groupby(level=0).exposure.transform("sum")
by_type["people_share"] = by_type.people / by_type.groupby(level=0).people.transform("sum")
by_type.round(3).to_csv(os.path.join(C.OUTPUTS, "safety_by_type.csv"))
print(by_type.round(2).to_string())

# Figure: along each road, people within 300 m (bars) and truck speed (line); top stretches shaded
fig, axs = plt.subplots(len(C.CORRIDORS), 1, figsize=(13, 3.2 * len(C.CORRIDORS)), facecolor=SURF,
                        gridspec_kw=dict(hspace=0.75))
for ax, corridor in zip(axs, C.CORRIDORS):
    d = S[S.corridor == corridor]
    km = np.floor(d.km_start).astype(int)
    g = d.groupby(km).agg(people=("people_300m", "sum"), v=("truck_kmh", "mean"), e=("exposure", "sum"))
    ax.bar(g.index + 0.5, g.people / 1000, width=0.9, color="#d9a441", linewidth=0, label="people within 300 m ('000 per km)")
    ax2 = ax.twinx()
    ax2.plot(g.index + 0.5, g.v.rolling(3, center=True, min_periods=1).mean(), color="#17252a", linewidth=1.1,
             label="truck speed, km/h")
    ax2.set_ylim(0, 90)
    labelled = []
    for h in top[top.corridor == corridor].head(5).itertuples():
        ax.axvspan(h.km_from, h.km_to, color="#c4532d", alpha=0.25, linewidth=0, zorder=0)
        if any(abs(h.km_from - k) < 0.07 * d.km_start.max() for k in labelled):
            continue   # neighbours share one label
        labelled.append(h.km_from)
        ax.annotate(h.place or f"km {h.km_from:.0f}", ((h.km_from + h.km_to) / 2, ax.get_ylim()[1] * 0.98),
                    ha="center", va="top", fontsize=7.5, color="#c4532d")
    for a_ in (ax, ax2):
        for s_ in ("top", "left", "right"):
            a_.spines[s_].set_visible(False)
        a_.tick_params(colors=INK2, labelsize=8, length=0)
    ax.spines["bottom"].set_color("#e4e3df")
    ax.set_xlim(0, d.km_start.max() + 0.5)
    ax.set_xlabel("km from Kampala", fontsize=8.5, color=INK2)
    ax.text(0, 1.08, f"{C.CORRIDORS[corridor]['label']}", transform=ax.transAxes, fontsize=10, color=INK)
    if corridor == list(C.CORRIDORS)[0]:
        h1, l1 = ax.get_legend_handles_labels()
        h2, l2 = ax2.get_legend_handles_labels()
        ax.legend(h1 + h2, l1 + l2, loc="upper right", frameon=False, fontsize=8, ncol=2, labelcolor=INK2,
                  bbox_to_anchor=(1, 1.3))
fig.text(0.125, 0.94, "Where fast trucks meet people", fontsize=15, color=INK)
fig.text(0.125, 0.925, "Shaded: the five 2 km stretches per road with the highest exposure (people × trucks × "
         "(speed/50)^4). Exposure, not recorded crashes.", fontsize=9, color=INK2)
fig.savefig(os.path.join(C.FIGURES, "f10_safety.png"), dpi=150, facecolor=SURF, bbox_inches="tight")
print("wrote outputs/safety_*.csv, figures/f10_safety.png")
