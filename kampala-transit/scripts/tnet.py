"""The Kampala transit network model, shared by k05 (single lines), k09 (networks) and k10 (equity).

Road network and demand from k01 (edges.gpkg, zones.csv); transit lines are added as their own
layer (in-vehicle time at a commercial speed, a boarding penalty for the wait and walk to the
platform, one minute to alight); transfers between lines go through the road network's nodes and
pay a new boarding penalty. Demand is k01's gravity matrix in the baseline, held fixed.

  times(road_factor, lines)     zone-to-zone fastest times from every origin zone
  baseline(road_factor)         (T, A, low40) for today's network
  evaluate(T, base)             time saved, users, access gains (all, least-access 40%, by group)
  GROUPS                        residents of each origin zone by land-use class (k07)
"""
import os
import numpy as np
import pandas as pd
import geopandas as gpd
from scipy import sparse
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
KT = os.path.abspath(os.path.join(HERE, ".."))
CBD = (32.5825, 0.3136)
TAU, MIN_TRIP, ACC_MIN = 25.0, 6.0, 45.0
MODES = {"BRT": dict(kmh=22.0, board=5.0), "light rail": dict(kmh=28.0, board=6.0)}
ROAD = {"roads as assumed": 1.0, "roads 1.5x slower": 1.5, "roads 2x slower": 2.0, "roads 3x slower": 3.0}
CENTRAL = "roads 2x slower"

E = gpd.read_file(os.path.join(KT, "outputs", "edges.gpkg"))
Z = pd.read_csv(os.path.join(KT, "outputs", "zones.csv"))
C = pd.read_csv(os.path.join(KT, "outputs", "corridors_core.csv"))
CAND = C[~C.screen.str.contains("express|priority only")].reset_index(drop=True)
_ends = np.array([[g.coords[0], g.coords[-1]] for g in E.geometry]).round(6)
_codes, _uniq = pd.factorize(pd.Series(list(map(tuple, _ends.reshape(-1, 2)))))
U, V = _codes[0::2], _codes[1::2]
N = len(_uniq)
NODE_XY = np.array(_uniq.tolist())
_mid = E.geometry.interpolate(0.5, normalized=True)
E["cbd_km"] = np.hypot((_mid.x - CBD[0]) * 111.32, (_mid.y - CBD[1]) * 111.32)
E["route"] = E.ref.fillna(E.name).fillna("")
ORIG = Z[Z["pop"] > 300].index.to_numpy()
ZN, ACC = Z.node.to_numpy(), Z.access_min.to_numpy()
POP = Z["pop"].to_numpy()[ORIG]
BUILT = Z.built_m2.to_numpy()
OZ = Z.iloc[ORIG].reset_index(drop=True)
OZ["cbd_km"] = np.hypot((OZ.lon - CBD[0]) * 111.32, (OZ.lat - CBD[1]) * 111.32)


def route_edges(route):
    return np.flatnonzero((E.route == route).to_numpy() & (E.cbd_km <= 20).to_numpy()
                          & E.highway.isin(["motorway", "trunk", "primary", "secondary"]).to_numpy())


def line(route, mode="BRT"):
    m = MODES[mode]
    return (route_edges(route), m["kmh"], m["board"])


def times(road_factor, lines=()):
    t = E["min"].to_numpy() * road_factor
    keep = U != V
    rows, cols, w = [U[keep], V[keep]], [V[keep], U[keep]], [t[keep], t[keep]]
    n = N
    for idx, kmh, board in lines:
        if not len(idx):
            continue
        nodes = np.unique(np.r_[U[idx], V[idx]])
        tid = dict(zip(nodes, range(n, n + len(nodes))))
        n += len(nodes)
        tt = E.km.to_numpy()[idx] / kmh * 60
        a, b = np.array([tid[x] for x in U[idx]]), np.array([tid[x] for x in V[idx]])
        tn = np.array([tid[x] for x in nodes])
        rows += [a, b, nodes, tn]
        cols += [b, a, tn, nodes]
        w += [tt, tt, np.full(len(nodes), board), np.full(len(nodes), 1.0)]
    G = sparse.coo_matrix((np.concatenate(w), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n)).tocsr()
    G.sum_duplicates()
    D = dijkstra(G, directed=True, indices=ZN[ORIG])[:, ZN]
    return D + ACC[None, :] + ACC[ORIG][:, None]


_Tb = times(1.0)
_W = np.where(np.isfinite(_Tb) & (_Tb >= MIN_TRIP), BUILT[None, :] * np.exp(-_Tb / TAU), 0)
TRIPS = np.nan_to_num(POP[:, None] * _W / _W.sum(axis=1, keepdims=True))
del _Tb, _W


def access(T):
    return np.where(T <= ACC_MIN, BUILT[None, :], 0).sum(axis=1)


# residents of each origin zone by land-use class (k07 cells assigned to the nearest zone centre)
_lu = os.path.join(KT, "outputs", "landuse_cells.parquet")
if os.path.exists(_lu):
    LU = pd.read_parquet(_lu, columns=["lon", "lat", "pop", "cls"])
    LU = LU[LU["pop"] > 0]
    _, j = cKDTree(np.c_[OZ.lon, OZ.lat]).query(np.c_[LU.lon, LU.lat], distance_upper_bound=0.0075)
    LU = LU[j < len(OZ)].assign(z=j[j < len(OZ)])
    GROUPS = LU.pivot_table(index="z", columns="cls", values="pop", aggfunc="sum").reindex(range(len(OZ))).fillna(0)
else:
    GROUPS = None


def baseline(road_factor):
    T = times(road_factor)
    A = access(T)
    order = np.argsort(A / np.maximum(A.max(), 1))
    cum = np.cumsum(POP[order]) / POP.sum()
    low = np.zeros(len(ORIG), bool)
    low[order[cum <= 0.4]] = True
    return dict(T=T, A=A, low=low)


def gini(x, w):
    o = np.argsort(x)
    x, w = x[o], w[o]
    cw = np.cumsum(w) / w.sum()
    cx = np.cumsum(x * w) / (x * w).sum()
    return 1 - np.sum((cw - np.r_[0, cw[:-1]]) * (cx + np.r_[0, cx[:-1]]))


def evaluate(T, base, km=None):
    Tb, Ab, low = base["T"], base["A"], base["low"]
    T = np.where(np.isfinite(T), T, Tb)
    d = np.nan_to_num(Tb - T, nan=0, posinf=0)
    save = (TRIPS * d).sum()
    total = (TRIPS * np.nan_to_num(Tb, posinf=0)).sum()
    A = access(T)
    out = dict(saving_pct=100 * save / total, person_min_saved=save,
               users_pct=100 * (TRIPS * (d > 0.5)).sum() / TRIPS.sum(),
               access_gain_pct=100 * (POP * (A - Ab)).sum() / (POP * Ab).sum(),
               access_gain_low40_pct=100 * (POP[low] * (A[low] - Ab[low])).sum() / (POP[low] * Ab[low]).sum(),
               gini_before=gini(Ab, POP), gini_after=gini(A, POP))
    if GROUPS is not None:
        for g in GROUPS.columns:
            w = GROUPS[g].to_numpy()
            if w.sum() > 0:
                out[f"gain_{g}"] = 100 * (w * (A - Ab)).sum() / max((w * Ab).sum(), 1)
    if km:
        out["km"] = km
        out["saving_per_km"] = save / km
    out["_A"] = A
    return out
