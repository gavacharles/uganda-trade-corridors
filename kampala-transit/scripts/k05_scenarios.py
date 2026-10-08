"""What would BRT or light rail on each candidate corridor do for travel time and access?

    python kampala-transit/scripts/k05_scenarios.py      (after k01, k02)

The road network of k01 (minibus taxis on peak road speeds with friction) gets one transit line
at a time, on the candidate's core length, as a separate layer: boarding costs a wait plus the walk
to the platform, alighting one minute, and the line runs at a commercial speed that includes its
stops. Fastest paths may use it wherever it beats the road. Demand is the baseline gravity matrix
of k01, held fixed. For each scenario:
  saving_pct      total trip time saved, % of all modelled trip time
  users_pct       share of trips whose fastest path now uses the line
  access_gain     change in built-up floor area reachable within 45 minutes, population-weighted,
                  for everyone and for the 40% of residents with the least access today
There is no open data on Kampala's peak road speeds, so congestion is swept instead of assumed:
roads at 100%, 67%, 50% and 33% of the assumed peak speeds (k01). Transit runs in its own lane at
its central speed in every case, so the sweep shows how congested each road must be before the line
pays off: the break-even that a traffic count or a GPS survey would then confirm or rule out.
Also run: the top five candidates together as one BRT network.

Writes outputs/scenarios.csv.
"""
import os
import numpy as np
import pandas as pd
import geopandas as gpd
from scipy import sparse
from scipy.sparse.csgraph import dijkstra

HERE = os.path.dirname(os.path.abspath(__file__))
KT = os.path.abspath(os.path.join(HERE, ".."))
CBD = (32.5825, 0.3136)
TAU, MIN_TRIP, ACC_MIN = 25.0, 6.0, 45.0
MODES = {   # commercial speed km/h (low, central, high; the central one is used), wait + walk to platform, minutes
    "BRT": dict(kmh=(18, 22, 26), board=5.0),
    "light rail": dict(kmh=(24, 28, 32), board=6.0),
}
ROAD = (1.0, 1.5, 2.0, 3.0)     # multiplier on road travel time: roads at 100%, 67%, 50%, 33% of assumed speed
CASES = ("roads as assumed", "roads 1.5x slower", "roads 2x slower", "roads 3x slower")

E = gpd.read_file(os.path.join(KT, "outputs", "edges.gpkg"))
Z = pd.read_csv(os.path.join(KT, "outputs", "zones.csv"))
C = pd.read_csv(os.path.join(KT, "outputs", "corridors_core.csv"))
cand = C[~C.screen.str.contains("express|priority only")].reset_index(drop=True)
ends = np.array([[g.coords[0], g.coords[-1]] for g in E.geometry]).round(6)
codes, uniq = pd.factorize(pd.Series(list(map(tuple, ends.reshape(-1, 2)))))
u, v = codes[0::2], codes[1::2]
N = len(uniq)
mid = E.geometry.interpolate(0.5, normalized=True)
E["cbd_km"] = np.hypot((mid.x - CBD[0]) * 111.32, (mid.y - CBD[1]) * 111.32)
E["route"] = E.ref.fillna(E.name).fillna("")
orig = Z[Z["pop"] > 300].index.to_numpy()
zn, acc = Z.node.to_numpy(), Z.access_min.to_numpy()


def times(road_factor, lines=()):
    """Fastest times from every origin zone to every zone, with the given transit lines.
    lines: list of (edge index array, kmh, board minutes)."""
    t = E["min"].to_numpy() * road_factor
    keep = u != v
    rows, cols, w = [u[keep], v[keep]], [v[keep], u[keep]], [t[keep], t[keep]]
    n = N
    for idx, kmh, board in lines:
        nodes = np.unique(np.r_[u[idx], v[idx]])
        tid = {a: n + i for i, a in enumerate(nodes)}
        n += len(nodes)
        tt = E.km.to_numpy()[idx] / kmh * 60
        a, b = np.array([tid[x] for x in u[idx]]), np.array([tid[x] for x in v[idx]])
        rows += [a, b, nodes, np.array([tid[x] for x in nodes])]
        cols += [b, a, np.array([tid[x] for x in nodes]), nodes]
        w += [tt, tt, np.full(len(nodes), board), np.full(len(nodes), 1.0)]
    G = sparse.coo_matrix((np.concatenate(w), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n))
    G = G.tocsr()
    G.sum_duplicates()
    D = dijkstra(G, directed=True, indices=zn[orig])[:, zn]
    return D + acc[None, :] + acc[orig][:, None]


def route_edges(route):
    return np.flatnonzero((E.route == route).to_numpy() & (E.cbd_km <= 20).to_numpy()
                          & E.highway.isin(["motorway", "trunk", "primary", "secondary"]).to_numpy())


# baseline demand (central case), held fixed
Tb = times(1.0)
W = np.where(np.isfinite(Tb) & (Tb >= MIN_TRIP), Z.built_m2.to_numpy()[None, :] * np.exp(-Tb / TAU), 0)
TRIPS = np.nan_to_num(Z["pop"].to_numpy()[orig][:, None] * W / W.sum(axis=1, keepdims=True))
POP = Z["pop"].to_numpy()[orig]
BUILT = Z.built_m2.to_numpy()


def access(T):
    return (np.where(T <= ACC_MIN, BUILT[None, :], 0)).sum(axis=1)


def evaluate(T, Tbase, Abase, low):
    T = np.where(np.isfinite(T), T, Tbase)
    save = np.nansum(TRIPS * np.nan_to_num(Tbase - T, nan=0, posinf=0))
    total = np.nansum(TRIPS * np.nan_to_num(Tbase, nan=0, posinf=0))
    used = np.nansum(TRIPS * ((Tbase - T) > 0.5)) / np.nansum(TRIPS)
    A = access(T)
    g_all = (POP * (A - Abase)).sum() / (POP * Abase).sum()
    g_low = (POP[low] * (A[low] - Abase[low])).sum() / (POP[low] * Abase[low]).sum()
    return dict(saving_pct=100 * save / total, person_min_saved=save, users_pct=100 * used,
                access_gain_pct=100 * g_all, access_gain_low40_pct=100 * g_low)


rows = []
base = {}
for case, rf in zip(CASES, ROAD):
    Tbase = times(rf)
    Abase = access(Tbase)
    order = np.argsort(Abase)
    cum = np.cumsum(POP[order]) / POP.sum()
    low = np.zeros(len(orig), bool)
    low[order[cum <= 0.4]] = True
    base[case] = (Tbase, Abase, low)
    print(f"{case}: baseline mean trip {np.nansum(TRIPS * np.nan_to_num(Tbase, posinf=0)) / TRIPS.sum():.1f} min", flush=True)

for _, c in cand.iterrows():
    idx = route_edges(c.route)
    if not len(idx):
        continue
    for mode, mp in MODES.items():
        for k, case in enumerate(CASES):
            Tbase, Abase, low = base[case]
            T = times(ROAD[k], [(idx, mp["kmh"][1], mp["board"])])
            rows.append(dict(route=c.route, name=c["name"], mode=mode, case=case, km=round(E.km.to_numpy()[idx].sum(), 1),
                             **evaluate(T, Tbase, Abase, low)))
    print("done", c["name"], flush=True)

net = cand.head(5)
for k, case in enumerate(CASES):
    Tbase, Abase, low = base[case]
    lines = [(route_edges(r), MODES["BRT"]["kmh"][1], MODES["BRT"]["board"]) for r in net.route]
    T = times(ROAD[k], lines)
    rows.append(dict(route="+".join(net.route), name="BRT network: " + ", ".join(net["name"]), mode="BRT network",
                     case=case, km=round(sum(E.km.to_numpy()[l[0]].sum() for l in lines), 1),
                     **evaluate(T, Tbase, Abase, low)))
R = pd.DataFrame(rows)
R["saving_per_km"] = R.person_min_saved / R.km
R.to_csv(os.path.join(KT, "outputs", "scenarios.csv"), index=False)
piv = R[R.case == "roads 2x slower"].sort_values("saving_pct", ascending=False)
print(piv[["name", "mode", "km", "saving_pct", "users_pct", "access_gain_pct", "access_gain_low40_pct"]].round(2).to_string())
