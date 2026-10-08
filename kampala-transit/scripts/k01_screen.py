"""First-pass screening of mass-transit corridors for Greater Kampala (BRT, light rail), from open data.

    python kampala-transit/scripts/k01_screen.py

1. Network: every motorway, trunk, primary, secondary and tertiary road in the study box (OSM),
   noded at junctions.
2. Speeds: an assumed peak speed per road class, lowered by roadside friction where the land within
   about 150 m is built up (GHSL 2020), in the form of paper 1's travel-time model.
3. Demand: about 1.1 km zones; trips produced in proportion to residents (WorldPop 2025) and
   attracted in proportion to built-up floor area (GHSL 2020, a proxy for jobs, schools and
   markets); an origin-constrained gravity model on network travel time; trips under 2 km left
   out (walked). All trips are routed on fastest paths, giving a relative person-trip load on
   every road. This is an index of where demand concentrates, not a count.
4. Corridors: loads summed along each named road; screened for demand, length, road width (dual
   carriageway or 4+ lanes from OSM) and the rail reserve (metre-gauge lines in OSM).

Writes kampala-transit/outputs/edges.gpkg, corridors.csv, zones.csv.
"""
import os, sys, time
import numpy as np
import pandas as pd
import geopandas as gpd
import pyogrio
import rasterio
import shapely
from rasterio.enums import Resampling
from rasterio.warp import reproject
from rasterio.windows import from_bounds
from scipy import sparse
from scipy.sparse.csgraph import dijkstra

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "kampala-transit", "outputs")
os.makedirs(OUT, exist_ok=True)
BOX = (32.35, 0.02, 32.90, 0.55)          # lon0, lat0, lon1, lat1: Kampala, Wakiso, Kira, Mukono, Entebbe
UTM = 32636
ZONE = 0.01                               # zone size, degrees (about 1.1 km)
SPEED = {"motorway": 70, "trunk": 32, "primary": 26, "secondary": 22, "tertiary": 18,     # peak, km/h
         "motorway_link": 40, "trunk_link": 25, "primary_link": 22, "secondary_link": 20, "tertiary_link": 18}
FRICTION_MAX, FRICTION_B = 0.35, 0.45      # largest speed loss, and the built-up share at which it is reached
TAU = 25.0                                 # minutes: gravity decay
MIN_TRIP_MIN = 6.0                         # shorter trips are walked
t0 = time.time()
log = lambda *a: print(f"[{time.time() - t0:5.0f} s]", *a, flush=True)  # noqa: E731

# ---------------------------------------------------------------- 1 network
cls = "','".join(SPEED)
roads = pyogrio.read_dataframe(os.path.join(DATA, "uganda-latest.osm.pbf"), layer="lines", bbox=BOX,
                               columns=["name", "highway", "other_tags"], where=f"highway IN ('{cls}')")
roads = roads[roads.geometry.geom_type == "LineString"].reset_index(drop=True)
tags = roads.other_tags.fillna("")
roads["lanes"] = pd.to_numeric(tags.str.extract(r'"lanes"=>"(\d+)"')[0], errors="coerce")
roads["oneway"] = tags.str.contains('"oneway"=>"yes"')
roads["ref"] = tags.str.extract(r'"ref"=>"([^"]+)"')[0]
log(len(roads), "OSM ways")
# node at every junction: split each way where it meets another
merged = shapely.union_all(shapely.get_parts(roads.geometry.values))
parts = shapely.get_parts(merged)
log(len(parts), "noded segments")
seg = gpd.GeoDataFrame(geometry=parts, crs=4326)
# carry each segment's attributes from the way it lies on (the way whose line contains its midpoint)
mid = seg.geometry.interpolate(0.5, normalized=True)
j = gpd.sjoin_nearest(gpd.GeoDataFrame(geometry=mid, crs=4326).to_crs(UTM), roads.to_crs(UTM)[["name", "highway", "lanes", "oneway", "ref", "geometry"]],
                      max_distance=2, how="left").groupby(level=0).first()
seg = seg.join(j[["name", "highway", "lanes", "oneway", "ref"]])
seg = seg[seg.highway.notna()].reset_index(drop=True)
seg["km"] = seg.to_crs(UTM).length / 1000

# ---------------------------------------------------------------- rasters on one grid (WorldPop's)
with rasterio.open(os.path.join(DATA, "worldpop", "uga_pop_2025_CN_100m_R2024B_v1.tif")) as src:
    win = from_bounds(*BOX, transform=src.transform).round_offsets().round_lengths()
    pop = src.read(1, window=win).astype("float64")
    pop[pop < 0] = 0
    T = src.window_transform(win)
    shape = pop.shape
built = np.zeros(shape, "float32")
for path in ("built_s_2020_R9_C22.tif", "built_s_2020_R10_C22.tif"):
    with rasterio.open(os.path.join(DATA, "ghsl", path)) as src:
        tmp = np.zeros(shape, "float32")
        reproject(rasterio.band(src, 1), tmp, dst_transform=T, dst_crs="EPSG:4326", resampling=Resampling.average,
                  src_nodata=src.nodata, dst_nodata=0)
        built = np.maximum(built, tmp)
built_frac = np.clip(built / 10000.0 * (100 * 100) / (92.6 * 92.6), 0, 1)   # share of the cell built over
log("population", f"{pop.sum():,.0f}", "residents in the box")


def sample(arr, xs, ys, k=1):
    """Mean of arr in a (2k+1)^2 window around each lon/lat."""
    r, c = rasterio.transform.rowcol(T, xs, ys)
    r, c = np.clip(np.asarray(r), k, shape[0] - k - 1), np.clip(np.asarray(c), k, shape[1] - k - 1)
    acc = np.zeros(len(r))
    for dr in range(-k, k + 1):
        for dc in range(-k, k + 1):
            acc += arr[r + dr, c + dc]
    return acc / (2 * k + 1) ** 2


# ---------------------------------------------------------------- 2 speeds with roadside friction
m = seg.geometry.interpolate(0.5, normalized=True)
seg["built_side"] = sample(built_frac, m.x.values, m.y.values, k=1)
fric = 1 - FRICTION_MAX * np.minimum(1, seg.built_side / FRICTION_B)
seg["kmh"] = seg.highway.map(SPEED) * np.where(seg.highway.str.startswith("motorway"), 1, fric)
# public-transport network: the tolled Entebbe Expressway (M3) carries few minibus taxis, so it is left
# out; the Northern Bypass (M20) is a dual carriageway with at-grade junctions, run at a peak 40 km/h
toll = seg.ref.fillna("").eq("M3") | seg.name.fillna("").str.contains("Expressway")
seg = seg[~toll].reset_index(drop=True)
seg.loc[seg.ref.fillna("").eq("M20"), "kmh"] = 40.0
seg["min"] = seg.km / seg.kmh * 60

# graph
ends = np.array([[g.coords[0], g.coords[-1]] for g in seg.geometry]).round(6)
keys = pd.Series(list(map(tuple, ends.reshape(-1, 2))))
codes, uniq = pd.factorize(keys)
u, v = codes[0::2], codes[1::2]
N = len(uniq)
nodes_xy = np.array(uniq.tolist())
# one edge per node pair (the faster of parallel segments); no self-loops
E = pd.DataFrame(dict(a=np.minimum(u, v), b=np.maximum(u, v), t=seg["min"].values, e=np.arange(len(seg))))
E = E[E.a != E.b].sort_values("t").drop_duplicates(["a", "b"])
G = sparse.coo_matrix((np.r_[E.t, E.t], (np.r_[E.a, E.b], np.r_[E.b, E.a])), shape=(N, N)).tocsr()
EID = sparse.coo_matrix((np.r_[E.e, E.e] + 1, (np.r_[E.a, E.b], np.r_[E.b, E.a])), shape=(N, N)).tocsr()
log(N, "nodes,", len(seg), "edges")

# ---------------------------------------------------------------- 3 zones and demand
zr, zc = int(round(ZONE / T.a)), int(round(ZONE / -T.e))
H, W = shape[0] // zr, shape[1] // zc
Z = pd.DataFrame([(i, j, pop[i * zr:(i + 1) * zr, j * zc:(j + 1) * zc].sum(),
                   built[i * zr:(i + 1) * zr, j * zc:(j + 1) * zc].sum()) for i in range(H) for j in range(W)],
                 columns=["row", "col", "pop", "built_m2"])
Z["lon"] = T.c + (Z.col * zc + zc / 2) * T.a
Z["lat"] = T.f + (Z.row * zr + zr / 2) * T.e
Z = Z[(Z["pop"] > 50) | (Z.built_m2 > 5000)].reset_index(drop=True)
# connect each zone to its nearest network node (access time at walking-to-taxi speed, 12 km/h)
from scipy.spatial import cKDTree  # noqa: E402
kx = np.cos(np.radians(0.3))
dist, near = cKDTree(np.c_[nodes_xy[:, 0] * kx, nodes_xy[:, 1]]).query(np.c_[Z.lon * kx, Z.lat])
Z["node"], Z["access_min"] = near, dist * 111.32 / 12 * 60
Z = Z[Z.access_min < 25].reset_index(drop=True)
orig = Z[Z["pop"] > 300].index.to_numpy()
log(len(Z), "zones,", len(orig), "origins")

A = Z.built_m2.to_numpy()
flow = np.zeros(len(seg))
trips_out, mean_min = np.zeros(len(Z)), np.zeros(len(Z))
for b0 in range(0, len(orig), 150):
    batch = orig[b0:b0 + 150]
    D, PRED = dijkstra(G, indices=Z.node.values[batch], return_predecessors=True)
    for k, oi in enumerate(batch):
        t = D[k, Z.node.values] + Z.access_min.values + Z.access_min.values[oi]
        ok = np.isfinite(t) & (t >= MIN_TRIP_MIN)
        w = np.where(ok, A * np.exp(-t / TAU), 0.0)
        if w.sum() <= 0:
            continue
        trips = Z["pop"].values[oi] * w / w.sum()        # one motorised trip per resident, distributed
        trips_out[oi], mean_min[oi] = trips.sum(), (trips * np.nan_to_num(t)).sum() / trips.sum()
        dem = np.bincount(Z.node.values, weights=trips, minlength=N)
        pred = PRED[k]
        # push demand up the shortest-path tree, deepest nodes first
        reach = np.isfinite(D[k])
        order = np.argsort(-np.where(reach, D[k], -1))
        order = order[reach[order]]
        sub = dem.copy()
        # depth levels make this vectorisable: a node's subtree is complete once all deeper nodes are added
        depth = np.zeros(N, int)
        p = pred.copy()
        alive = (p >= 0)
        while alive.any():
            depth[alive] += 1
            p = np.where(alive, pred[np.maximum(p, 0)], -9999)
            alive = p >= 0
        for lev in range(depth.max(), 0, -1):
            nd = np.flatnonzero((depth == lev) & reach)
            pn = pred[nd]
            np.add.at(sub, pn, sub[nd])
            e = np.asarray(EID[pn, nd]).ravel() - 1
            np.add.at(flow, e, sub[nd])
    log(f"origins {min(b0 + 150, len(orig))}/{len(orig)}")

seg["load"] = flow
seg["load_idx"] = 100 * seg.load / seg.load.quantile(0.995)
Z["trips_out"], Z["mean_trip_min"] = trips_out, mean_min

# ---------------------------------------------------------------- 4 corridors
rail = gpd.read_file(os.path.join(DATA, "railways.gpkg")).cx[BOX[0]:BOX[2], BOX[1]:BOX[3]]
rail = rail[rail.railway.isin(["rail", "disused", "abandoned"]) & (rail.to_crs(UTM).length > 300)]
seg_u = seg.to_crs(UTM)
seg["rail_m"] = seg_u.geometry.distance(rail.to_crs(UTM).union_all()) if len(rail) else np.inf
seg["wide"] = (seg.lanes >= 4) | seg.oneway | seg.highway.str.startswith("motorway")
# catchment population within 800 m of each segment's midpoint (walk to a stop)
k8 = int(round(800 / 92.6))
yy, xx = np.mgrid[-k8:k8 + 1, -k8:k8 + 1]
disc = (xx ** 2 + yy ** 2) <= k8 ** 2
from scipy.signal import fftconvolve  # noqa: E402
catch = fftconvolve(pop, disc.astype(float), mode="same")
m = seg.geometry.interpolate(0.5, normalized=True)
seg["catch_pop"] = sample(catch, m.x.values, m.y.values, k=0)
main = seg[seg.highway.isin(["motorway", "trunk", "primary", "secondary"])].copy()
main["route"] = main.ref.fillna(main.name).fillna("unnamed " + main.highway)
rows = []
for r, d in main.groupby("route"):
    L = d.km.sum()
    if L < 3 or r.startswith("unnamed"):
        continue
    rows.append(dict(route=r, km=round(L, 1), cls=d.highway.mode().iloc[0],
                     load_mean=(d.load_idx * d.km).sum() / L, load_p90=d.load_idx.quantile(0.9),
                     pkm=(d.load * d.km).sum(), catch_pop_per_km=(d.catch_pop * d.km).sum() / L,
                     wide_share=(d.km * d.wide).sum() / L, rail_share=(d.km * (d.rail_m < 500)).sum() / L,
                     kmh=(d.km).sum() / (d["min"].sum() / 60), built_side=(d.built_side * d.km).sum() / L))
C = pd.DataFrame(rows).sort_values("pkm", ascending=False).reset_index(drop=True)
C["pkm_share"] = C.pkm / seg.eval("load * km").sum()
# screening rule (illustrative thresholds, to be replaced by the full study's appraisal)
q_lrt, q_brt = C.load_mean.quantile(0.9), C.load_mean.quantile(0.7)
C["screen"] = np.select(
    [(C.load_mean >= q_lrt) & (C.km >= 8),
     (C.load_mean >= q_brt) & (C.km >= 5) & (C.wide_share >= 0.3),
     (C.load_mean >= q_brt) & (C.km >= 5),
     (C.rail_share >= 0.4) & (C.catch_pop_per_km > C.catch_pop_per_km.median())],
    ["light rail / high-capacity BRT", "BRT (road wide enough on part)", "BRT with land take, or bus priority",
     "commuter rail on the rail reserve"], "bus/taxi priority only")
seg.to_file(os.path.join(OUT, "edges.gpkg"), driver="GPKG")
C.to_csv(os.path.join(OUT, "corridors.csv"), index=False)
Z.to_csv(os.path.join(OUT, "zones.csv"), index=False)
rail.to_file(os.path.join(OUT, "rail.gpkg"), driver="GPKG")
log("wrote edges.gpkg, corridors.csv, zones.csv")
print(C.head(20)[["route", "km", "cls", "load_mean", "pkm_share", "catch_pop_per_km", "wide_share", "rail_share",
                  "kmh", "screen"]].round(2).to_string())
