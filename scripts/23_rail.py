"""Rail along the bottlenecks: where would it run, what would it change, and what might it save?

Three parts.

A. Where rail already meets the bottlenecks. Uganda's metre-gauge railway (OSM: about 990 km
   in use, 280 km disused) and the planned SGR (the eastern line Malaba-Tororo-Jinja-Kampala,
   273 km, contract signed October 2024; northern, western and southwestern lines planned).
   For each road, the share of truck delay (10_travel_time.py) and of road-safety exposure
   (19_safety.py) that lies within 10 km of a railway in use or disused.

B. Where a line would run. For each road, a least-cost rail alignment between its towns,
   inside 25 km of the road: 250 m grid; each step costs its length times
   (1 + GRADE_K x grade above 1.5%, the usual ruling grade for heavy freight)
   x (1 + BUILT_K x built-up share, GHSL 2020, for demolition and severance), and lakes
   (Natural Earth) are closed. Elevation: Copernicus GLO-30 averaged to 250 m. The eastern
   line is drawn this way too, as a check against the metre-gauge alignment the SGR follows.
   These are screening alignments, not engineering designs.

C. What a shift of freight to rail would do, per line (and, for the eastern line, for transit
   freight on a through rail haul from Mombasa), over 2,000 Monte Carlo draws of every
   assumption (RAIL_PARAMS): tonnes moved (trucks a day from config.TRUCKS_PER_DAY x loaded
   share x payload x shift share), trucks taken off the road, freight cost saved by shippers
   (road rate x road km - rail rate x rail km - terminal and drayage cost), door-to-door
   time by rail (line-haul + terminal time) against the modelled truck time, truck time lost
   to road friction that is avoided, CO2 avoided, and the capital cost (SGR eastern contract,
   EUR 2.7 bn, about US$10.6 M per km) against annual benefits. Transit traffic beyond
   Uganda, passengers and wider economic effects are not counted, and neither is congestion
   relief near Kampala (the road model has no congestion).

Writes outputs/rail_proximity.csv, outputs/rail_alignments.csv, outputs/rail_economics.csv,
outputs/rail_alignments.geojson, figures/f12_rail_map.png, figures/f13_rail_economics.png.
"""
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import pyogrio
import rasterio
from rasterio import features
from rasterio.transform import from_origin
from rasterio.warp import reproject, Resampling
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from shapely.geometry import LineString, Point
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config as C
from cartography import INK, INK2, SURF

RES, BUF_KM = 250, 25
G0, GRADE_K, BUILT_K = 0.015, 100, 4
RNG = np.random.default_rng(23)
N = 2000
TOWNS = {"Kampala": (32.5825, 0.3136), "Mukono": (32.7550, 0.3530), "Lugazi": (32.9420, 0.3700),
         "Jinja": (33.2040, 0.4390), "Iganga": (33.4690, 0.6090), "Bugiri": (33.7420, 0.5680),
         "Tororo": (34.1810, 0.6930), "Malaba": (34.2790, 0.6380), "Mpigi": (32.3140, 0.2250),
         "Lukaya": (31.8750, -0.1440), "Masaka": (31.7350, -0.3330), "Lyantonde": (31.1580, -0.4040),
         "Mbarara": (30.6550, -0.6070), "Ntungamo": (30.2640, -0.8790), "Kabale": (29.9856, -1.2486),
         "Katuna": (30.0000, -1.4200), "Luweero": (32.4730, 0.8490), "Kafu": (32.0560, 1.5700),
         "Bweyale": (32.1100, 1.8200), "Karuma": (32.2380, 2.2480), "Gulu": (32.2990, 2.7740),
         "Atiak": (32.1200, 3.2600), "Elegu": (32.0800, 3.5750), "Kiboga": (31.7730, 0.9160),
         "Kakumiro": (31.3230, 0.7810), "Hoima": (31.3520, 1.4320)}
LINES = {  # name: (road it serves, stations in order, status)
    "Eastern": ("kampala_malaba", ["Kampala", "Mukono", "Lugazi", "Jinja", "Iganga", "Bugiri", "Tororo", "Malaba"],
                "SGR contracted; metre gauge in use"),
    "Southwestern": ("kampala_katuna", ["Kampala", "Mpigi", "Lukaya", "Masaka", "Lyantonde", "Mbarara", "Ntungamo",
                                        "Kabale", "Katuna"], "proposed here (SGR plan reaches Mbarara via Bihanga)"),
    "Northern direct": ("kampala_elegu", ["Kampala", "Luweero", "Kafu", "Bweyale", "Karuma", "Gulu", "Atiak", "Elegu"],
                        "proposed here (SGR plan reaches Gulu from Tororo)"),
    "Albertine": ("kampala_hoima", ["Kampala", "Kiboga", "Kakumiro", "Hoima"], "proposed here (no line planned)"),
}
# (central, low, high)
RAIL_PARAMS = {
    "shift": (0.3, 0.15, 0.5),            # share of the road's truck freight that moves to rail
    "loaded": (0.6, 0.5, 0.7),            # share of trucks that are loaded
    "payload_t": (25, 20, 30),
    "road_usd_tkm": (0.075, 0.06, 0.10),  # ~US$1.79 per container-km, Mombasa-Kampala (NCTTCA), ~24 t
    "rail_usd_tkm": (0.045, 0.03, 0.06),  # typical African rail freight rates
    "terminal_usd_t": (6, 3, 10),         # lift on/off and drayage at both ends
    "rail_kmh": (45, 30, 60),             # average freight train speed including crossing loops
    "terminal_h": (12, 6, 24),            # dwell at both terminals, including drayage
    "truck_usd_h": (25, 15, 40),          # as in 17_costs.py
    "road_kgco2_tkm": (0.08, 0.06, 0.10),
    "rail_kgco2_tkm": (0.01, 0.005, 0.02),   # electric traction, mostly hydro power
    "usd_tco2": (50, 25, 100),
    "capex_usd_km": (10.6e6, 7e6, 14e6),  # EUR 2.7 bn / 273 km (eastern SGR contract)
    "om_share": (0.02, 0.01, 0.03),       # operation and maintenance a year, share of capex
    "discount": (0.08, 0.06, 0.10),
}
LIFE = 40


def draws():
    return {k: np.r_[v[0], RNG.uniform(v[1], v[2], N - 1)] for k, v in RAIL_PARAMS.items()}


P = pd.read_csv(os.path.join(C.OUTPUTS, "pieces_typed.csv")).sort_values(["corridor", "piece"])
tt = pd.read_csv(os.path.join(C.OUTPUTS, "travel_time_pieces.csv"))
sf = pd.read_csv(os.path.join(C.OUTPUTS, "safety_pieces.csv"))
tot = pd.read_csv(os.path.join(C.OUTPUTS, "travel_time_totals.csv"))
P = P.merge(tt[["corridor", "piece", "truck_excess_min"]]).merge(sf[["corridor", "piece", "exposure", "people_300m"]])
cl = gpd.read_file(C.PROBES_GPKG, layer="centrelines")
cl = cl[cl.direction == "outbound"].set_index("corridor")

# ---------------------------------------------------------------- A. rail near the bottlenecks
RAILS = os.path.join(C.DATA, "railways.gpkg")
if not os.path.exists(RAILS):
    r = pyogrio.read_dataframe(C.PBF, layer="lines", columns=["name", "railway", "other_tags"],
                               where="railway IN ('rail','disused','abandoned','construction','proposed')")
    r["gauge"] = r.other_tags.fillna("").str.extract(r'"gauge"=>"([^"]+)"', expand=False)
    r[["name", "railway", "gauge", "geometry"]].to_file(RAILS, driver="GPKG")
rails = gpd.read_file(RAILS)
rails = rails[rails.railway.isin(["rail", "disused"]) & (rails.to_crs(C.UTM).length > 200)].to_crs(C.UTM)
print(rails.assign(km=rails.length / 1000).groupby("railway").km.sum().round(0).to_string())
pts = gpd.GeoSeries(gpd.points_from_xy(P.lon, P.lat), crs=4326).to_crs(C.UTM)
active = rails[rails.railway == "rail"].geometry.union_all()
anyrail = rails.geometry.union_all()
P["km_to_rail_in_use"] = pts.distance(active).to_numpy() / 1000
P["km_to_any_rail"] = pts.distance(anyrail).to_numpy() / 1000
prox = []
for corridor, d in P.groupby("corridor"):
    for col, lab in (("km_to_rail_in_use", "in use"), ("km_to_any_rail", "in use or disused")):
        near = d[col] <= 10
        prox.append(dict(corridor=corridor, railway=lab, road_km_within_10km=near.sum() * 0.5,
                         share_of_road=round(near.mean(), 3),
                         share_of_truck_delay=round(d.truck_excess_min[near].sum() / d.truck_excess_min.sum(), 3),
                         share_of_exposure=round(d.exposure[near].sum() / d.exposure.sum(), 3)))
prox = pd.DataFrame(prox)
prox.to_csv(os.path.join(C.OUTPUTS, "rail_proximity.csv"), index=False)
print(prox.to_string(index=False))

# ---------------------------------------------------------------- B. least-cost alignments
lakes = gpd.read_file(os.path.join(C.DATA, "ne_lakes", "ne_10m_lakes.shp")).to_crs(4326).cx[28.5:36, -3:5.5]
dem_tiles = [os.path.join(C.DATA, "dem", f) for f in sorted(os.listdir(os.path.join(C.DATA, "dem"))) if f.endswith(".tif")]
ghsl = [os.path.join(C.DATA, "ghsl", f"built_s_2020_{t}.tif") for t in C.GHSL_TILES]


def grid_for(corridor):
    zone = gpd.GeoSeries([cl.loc[corridor].geometry], crs=4326).to_crs(C.UTM).buffer(BUF_KM * 1000).iloc[0]
    x0, y0, x1, y1 = zone.bounds
    w, h = int((x1 - x0) / RES) + 1, int((y1 - y0) / RES) + 1
    tf = from_origin(x0, y1, RES, RES)
    dem = np.full((h, w), np.nan, dtype="float32")
    for t in dem_tiles:
        with rasterio.open(t) as src:
            tmp = np.full((h, w), np.nan, dtype="float32")
            reproject(rasterio.band(src, 1), tmp, dst_transform=tf, dst_crs=C.UTM, resampling=Resampling.average,
                      dst_nodata=np.nan)
            dem = np.where(np.isnan(dem), tmp, dem)
    built = np.zeros((h, w), dtype="float32")
    for t in ghsl:
        with rasterio.open(t) as src:
            tmp = np.full((h, w), np.nan, dtype="float32")
            reproject(rasterio.band(src, 1), tmp, dst_transform=tf, dst_crs=C.UTM, resampling=Resampling.average,
                      src_nodata=src.nodata, dst_nodata=np.nan)
            built = np.where(np.isnan(tmp), built, tmp / 1e4)   # m2 per 100 m cell -> share
    closed = features.rasterize([(g, 1) for g in lakes.to_crs(C.UTM).geometry], out_shape=(h, w), transform=tf) > 0
    inside = features.rasterize([(zone, 1)], out_shape=(h, w), transform=tf) > 0
    closed |= ~inside | np.isnan(dem)
    return dict(tf=tf, h=h, w=w, dem=dem, built=np.clip(built, 0, 1), closed=closed)


def graph(g):
    h, w, dem, built, closed = g["h"], g["w"], g["dem"], g["built"], g["closed"]
    idx = np.arange(h * w).reshape(h, w)
    rows, cols, vals = [], [], []
    for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
        a = idx[max(0, -dr):h - max(0, dr), max(0, -dc):w - max(0, dc)]
        b = idx[max(0, dr):h - max(0, -dr) + (0 if dr >= 0 else 0), max(0, dc):w - max(0, -dc)]
        ra, ca = np.unravel_index(a.ravel(), (h, w))
        rb, cb = np.unravel_index(b.ravel(), (h, w))
        L = RES * np.hypot(dr, dc)
        grade = np.abs(dem[rb, cb] - dem[ra, ca]) / L
        cost = L * (1 + GRADE_K * np.maximum(0, grade - G0)) * (1 + BUILT_K * (built[ra, ca] + built[rb, cb]) / 2)
        ok = ~(closed[ra, ca] | closed[rb, cb]) & np.isfinite(cost)
        for s, t in ((a.ravel()[ok], b.ravel()[ok]), (b.ravel()[ok], a.ravel()[ok])):
            rows.append(s)
            cols.append(t)
            vals.append(cost[ok])
    return coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(h * w, h * w)).tocsr()


def cell(g, lonlat):
    p = gpd.GeoSeries([Point(lonlat)], crs=4326).to_crs(C.UTM).iloc[0]
    c, r = ~g["tf"] * (p.x, p.y)
    r, c = int(r), int(c)
    # nearest open cell
    rr, cc = np.nonzero(~g["closed"])
    k = np.argmin((rr - r) ** 2 + (cc - c) ** 2)
    return rr[k] * g["w"] + cc[k]


align_rows, geoms = [], []
for line, (corridor, stops, status) in LINES.items():
    g = grid_for(corridor)
    A = graph(g)
    path = []
    for s, t in zip(stops[:-1], stops[1:]):
        a, b = cell(g, TOWNS[s]), cell(g, TOWNS[t])
        _, pred = dijkstra(A, indices=a, return_predecessors=True)
        seg, n = [], b
        while n != a and n >= 0:
            seg.append(n)
            n = pred[n]
        seg.append(a)
        path += seg[::-1][(1 if path else 0):]
    r_, c_ = np.unravel_index(np.array(path), (g["h"], g["w"]))
    xs, ys = g["tf"] * (c_ + 0.5, r_ + 0.5)
    geom = LineString(zip(xs, ys))
    z = pd.Series(g["dem"][r_, c_]).rolling(5, center=True, min_periods=1).mean().to_numpy()   # ~1 km smoothing
    step = np.hypot(np.diff(xs), np.diff(ys))
    gr = np.abs(np.diff(z)) / np.maximum(step, 1)
    built_ha = float((g["built"][r_, c_] * step.mean() * 100 / 1e4).sum())   # 100 m wide strip
    road_km = cl.loc[corridor].geometry and gpd.GeoSeries([cl.loc[corridor].geometry], crs=4326).to_crs(C.UTM).length.iloc[0] / 1000
    align_rows.append(dict(line=line, corridor=corridor, status=status, stations=" – ".join(stops),
                           rail_km=round(geom.length / 1000, 1), road_km=round(road_km, 1),
                           share_steeper_than_1_5pct=round(float((gr > G0).mean()), 3),
                           share_steeper_than_2_5pct=round(float((gr > 0.025).mean()), 3),
                           built_ha_in_100m_strip=round(built_ha, 0)))
    geoms.append(dict(line=line, corridor=corridor, geometry=geom))
    print(f"{line}: {geom.length / 1000:.0f} km of rail for {road_km:.0f} km of road", flush=True)
AL = pd.DataFrame(align_rows)
AL.to_csv(os.path.join(C.OUTPUTS, "rail_alignments.csv"), index=False)
GA = gpd.GeoDataFrame(geoms, crs=C.UTM).to_crs(4326)
GA.to_file(os.path.join(C.OUTPUTS, "rail_alignments.geojson"), driver="GeoJSON")
print(AL.to_string(index=False))

# ---------------------------------------------------------------- C. economics of a shift to rail
# Variants: every line carries domestic freight (a terminal at both ends). The eastern line can
# also carry transit freight on a through rail haul from Mombasa (needs Kenya's unbuilt
# Naivasha-Malaba link): then only the Kampala end adds terminal cost and time.
VARIANTS = [(a, "domestic", 1.0) for a in AL.itertuples()] + \
           [(a, "through from Mombasa", 0.5) for a in AL.itertuples() if a.line == "Eastern"]
econ = []
for a, variant, term in VARIANTS:
    q = draws()
    q["terminal_usd_t"] = q["terminal_usd_t"] * term
    q["terminal_h"] = q["terminal_h"] * term
    trucks = np.r_[C.TRUCKS_PER_DAY[a.corridor][0],
                   RNG.uniform(C.TRUCKS_PER_DAY[a.corridor][1], C.TRUCKS_PER_DAY[a.corridor][2], N - 1)]
    t_row = tot[(tot.corridor == a.corridor) & (tot.vehicle == "truck") & (tot.direction == "outbound")].iloc[0]
    tonnes = trucks * 365 * q["loaded"] * q["payload_t"] * q["shift"]
    trucks_off = trucks * q["shift"]
    road_cost = tonnes * a.road_km * q["road_usd_tkm"]
    rail_cost = tonnes * (a.rail_km * q["rail_usd_tkm"] + q["terminal_usd_t"])
    shipper = road_cost - rail_cost
    rail_h = a.rail_km / q["rail_kmh"] + q["terminal_h"]
    road_h = t_row.minutes / 60
    delay_h = trucks_off * 365 * (t_row.minutes - t_row.open_road_minutes) / 60
    co2 = tonnes * (a.road_km * q["road_kgco2_tkm"] - a.rail_km * q["rail_kgco2_tkm"]) / 1000
    capex = q["capex_usd_km"] * a.rail_km
    ann = capex * q["discount"] / (1 - (1 + q["discount"]) ** -LIFE) + capex * q["om_share"]
    benefit = shipper + co2 * q["usd_tco2"]
    # tonnes a year at which benefits pay the annual cost
    per_t = (a.road_km * q["road_usd_tkm"] - a.rail_km * q["rail_usd_tkm"] - q["terminal_usd_t"]
             + (a.road_km * q["road_kgco2_tkm"] - a.rail_km * q["rail_kgco2_tkm"]) / 1000 * q["usd_tco2"])
    breakeven = np.where(per_t > 0, ann / np.maximum(per_t, 1e-9), np.inf)
    for name, v, unit in (("freight moved to rail", tonnes / 1e6, "Mt a year"), ("trucks off the road", trucks_off, "a day"),
                          ("freight cost saved", shipper / 1e6, "US$ M a year"),
                          ("truck time lost to road friction avoided", delay_h / 1e3, "'000 truck-hours a year"),
                          ("value of that truck time", delay_h * q["truck_usd_h"] / 1e6, "US$ M a year"),
                          ("CO2 avoided", co2 / 1e3, "kt a year"),
                          ("door-to-door time by rail", rail_h, "hours"), ("truck time on the road (modelled)", np.full(N, road_h), "hours"),
                          ("capital cost", capex / 1e9, "US$ bn"), ("annual cost of capital and O&M", ann / 1e6, "US$ M a year"),
                          ("benefit / cost", benefit / ann, "ratio"), ("freight needed to break even", breakeven / 1e6, "Mt a year"),
                          ("break-even as a multiple of the road's freight today",
                           breakeven / (trucks * 365 * q["loaded"] * q["payload_t"]), "times")):
        v = np.asarray(v, dtype=float)
        fin = v[1:][np.isfinite(v[1:])]
        econ.append(dict(line=a.line, variant=variant, measure=name, unit=unit, central=round(float(v[0]), 2),
                         p5=round(float(np.quantile(fin, 0.05)), 2) if len(fin) else np.nan,
                         p95=round(float(np.quantile(fin, 0.95)), 2) if len(fin) else np.nan))
E = pd.DataFrame(econ)
E.to_csv(os.path.join(C.OUTPUTS, "rail_economics.csv"), index=False)
print(E.to_string(index=False))

# ---------------------------------------------------------------- figures
pp = gpd.GeoDataFrame(P, geometry=gpd.points_from_xy(P.lon, P.lat), crs=4326)
fig, ax = plt.subplots(figsize=(10, 11), facecolor=SURF)
lakes.plot(ax=ax, color="#d3d6d9", linewidth=0)
r4 = rails.to_crs(4326)
r4[r4.railway == "rail"].plot(ax=ax, color=INK, linewidth=1.4, zorder=3)
r4[r4.railway == "disused"].plot(ax=ax, color=INK2, linewidth=1.0, linestyle=(0, (3, 2)), zorder=3)
v = (pp.truck_excess_min / 0.5).clip(upper=2)
ax.scatter(pp.lon, pp.lat, c=v, cmap="Oranges", s=9, vmin=0, vmax=2, zorder=4, linewidths=0)
cols = {"Eastern": "#2a78d6", "Southwestern": "#1aa878", "Northern direct": "#e8643a", "Albertine": "#7a5bc4"}
for rw in GA.itertuples():
    ax.plot(*rw.geometry.xy, color=cols[rw.line], linewidth=2.2, alpha=0.85, zorder=5, label=f"{rw.line} (screening alignment)")
for n in ("Kampala", "Jinja", "Tororo", "Malaba", "Masaka", "Mbarara", "Kabale", "Gulu", "Karuma", "Elegu", "Hoima", "Luweero"):
    ax.plot(*TOWNS[n], "o", color="white", markeredgecolor=INK, markersize=4, zorder=6)
    ax.text(TOWNS[n][0] + 0.05, TOWNS[n][1] + 0.03, n, fontsize=8.5, color=INK, zorder=7)
ax.plot([], [], color=INK, linewidth=1.4, label="metre-gauge railway in use (OSM)")
ax.plot([], [], color=INK2, linewidth=1.0, linestyle=(0, (3, 2)), label="metre-gauge railway disused (OSM)")
ax.scatter([], [], c="#eb6834", s=12, label="road: truck minutes lost per km (darker = more)")
ax.set_xlim(29.6, 34.6)
ax.set_ylim(-1.6, 3.8)
ax.set_aspect(1 / np.cos(np.radians(1)))
ax.set_axis_off()
ax.legend(loc="lower right", frameon=False, fontsize=8.5, labelcolor=INK2)
ax.set_title("Rail along the bottlenecks: existing lines and least-cost screening alignments", loc="left", fontsize=13, color=INK)
fig.savefig(os.path.join(C.FIGURES, "f12_rail_map.png"), dpi=150, facecolor=SURF, bbox_inches="tight")

fig, axs = plt.subplots(1, 3, figsize=(15, 4.6), facecolor=SURF)
order = ["Eastern", "Eastern (through)"] + list(LINES)[1:]
cols["Eastern (through)"] = "#86b6ef"
for ax, (m, lab) in zip(axs, (("freight cost saved", "US$ M a year saved by shippers"),
                              ("annual cost of capital and O&M", "US$ M a year, capital and O&M"),
                              ("benefit / cost", "benefit / cost ratio"))):
    d = E[E.measure == m].assign(line=lambda x: np.where(x.variant == "domestic", x.line, x.line + " (through)"))
    d = d.set_index("line").reindex(order)
    y = np.arange(len(order))
    ax.barh(y, d.central, color=[cols[l] for l in order], height=0.6, linewidth=0)
    ax.errorbar(d.central, y, xerr=[d.central - d.p5, d.p95 - d.central], fmt="none", ecolor=INK2, elinewidth=0.8, capsize=2)
    if m == "benefit / cost":
        ax.axvline(1, color=INK, linewidth=0.8, linestyle=":")
    ax.set_yticks(y)
    ax.set_yticklabels(order if ax is axs[0] else [], fontsize=9.5, color=INK)
    ax.invert_yaxis()
    for s_ in ("top", "right", "left"):
        ax.spines[s_].set_visible(False)
    ax.grid(axis="x", color="#e4e3df", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(colors=INK2, labelsize=8.5, length=0)
    ax.set_title(lab, loc="left", fontsize=10, color=INK)
fig.text(0.01, 1.04, "What a shift of Uganda's own road freight to rail would pay back", fontsize=14, color=INK)
fig.text(0.01, 0.98, "30% of each road's truck freight moved (15–50% in the draws); whiskers 5th–95th percentile. \"Through\": "
         "transit freight on a continuous rail haul from Mombasa. Passengers and congestion relief not counted.", fontsize=9, color=INK2)
fig.savefig(os.path.join(C.FIGURES, "f13_rail_economics.png"), dpi=150, facecolor=SURF, bbox_inches="tight")
print("wrote outputs/rail_*.csv, outputs/rail_alignments.geojson, figures/f12_rail_map.png, figures/f13_rail_economics.png")
