"""Build each corridor's centreline, in both directions, and the TomTom probe points.

The centreline is the shortest path from the corridor's start to its end along the
OSM ways in data/corridors.gpkg, respecting one-way tags so that on the dual
carriageway "outbound" follows the carriageway leaving Kampala and "inbound" the
one entering it. Where the route number is missing from a stretch of OSM, the path
may use other main roads within 300 m (the _fill layer) at a 50% length penalty, so
tagged ways are always preferred. As a last resort, dead ends less than 100 m apart
are joined.

Writes data/probes.gpkg with layers:
  centrelines  corridor, direction, km, geometry
  probes       corridor, direction, probe_id, km_from_kampala, lon, lat, geometry
"""
import os
import numpy as np
import geopandas as gpd
import networkx as nx
from shapely.geometry import LineString, Point
from scipy.spatial import cKDTree

import config as C

GAP_M = 100
FILL_PENALTY = 1.5


def graph(ways_utm, G=None, penalty=1.0):
    G = G if G is not None else nx.DiGraph()
    for _, w in ways_utm.iterrows():
        xy = [(round(x, 1), round(y, 1)) for x, y in w.geometry.coords]
        ow = str(w.get("oneway") or "")
        for a, b in zip(xy[:-1], xy[1:]):
            d = penalty * float(np.hypot(b[0] - a[0], b[1] - a[1]))
            if ow == "-1":
                G.add_edge(b, a, w=d)
            else:
                G.add_edge(a, b, w=d)
                if ow not in ("yes", "true", "1"):
                    G.add_edge(b, a, w=d)
    return G


def bridge_gaps(G):
    """Join dead ends (nodes with a single neighbour) to any node within GAP_M."""
    ends = [n for n in G.nodes if len(set(G.successors(n)) | set(G.predecessors(n))) == 1]
    nodes = list(G.nodes)
    tree = cKDTree(np.array(nodes))
    added = 0
    for a in ends:
        for j in tree.query_ball_point(a, GAP_M):
            b = nodes[j]
            if b == a or G.has_edge(a, b):
                continue
            d = 3 * float(np.hypot(a[0] - b[0], a[1] - b[1]))
            G.add_edge(a, b, w=d)
            G.add_edge(b, a, w=d)
            added += 1
    return added


def nearest(G, lonlat):
    """Nearest node on the largest connected part of the network (not an isolated stub)."""
    p = gpd.GeoSeries([Point(lonlat)], crs=4326).to_crs(C.UTM).iloc[0]
    nodes = np.array(list(max(nx.weakly_connected_components(G), key=len)))
    return tuple(nodes[np.argmin(np.hypot(nodes[:, 0] - p.x, nodes[:, 1] - p.y))])


def path_line(G, a, b):
    return LineString(nx.shortest_path(G, a, b, weight="w"))


lines, probes = [], []
for name, ends in C.CORRIDORS.items():
    ways = gpd.read_file(C.CORRIDORS_GPKG, layer=name).explode(index_parts=False).to_crs(C.UTM)
    G = graph(ways)
    fill = gpd.read_file(C.CORRIDORS_GPKG, layer=name + "_fill").explode(index_parts=False).to_crs(C.UTM)
    graph(fill, G, FILL_PENALTY)
    a, b = nearest(G, ends["start"]), nearest(G, ends["end"])
    try:
        out, inn = path_line(G, a, b), path_line(G, b, a)
    except nx.NetworkXNoPath:
        print(f"{name}: route has gaps, joined {bridge_gaps(G)} dead ends within {GAP_M} m")
        try:
            out, inn = path_line(G, a, b), path_line(G, b, a)
        except nx.NetworkXNoPath:
            # One-way ways with no way back (e.g. around a border post): ignore direction
            print(f"{name}: no directed route; one-way tags ignored for this corridor")
            G = G.to_undirected().to_directed()
            out, inn = path_line(G, a, b), path_line(G, b, a)
    total = out.length / 1000
    on_fill = sum(1 for p, q in zip(out.coords[:-1], out.coords[1:])
                  if G[tuple(np.round(p, 1))][tuple(np.round(q, 1))]["w"] > 1.01 * np.hypot(q[0] - p[0], q[1] - p[1]))
    print(f"{name}: outbound {total:.1f} km, inbound {inn.length / 1000:.1f} km, "
          f"{on_fill} outbound steps off the tagged route")
    spec = C.TOMTOM_PROBES.get(name, dict(spacing_km=10.0, directions=("outbound",)))
    for direction, line in (("outbound", out), ("inbound", inn)):
        lines.append(dict(corridor=name, direction=direction, km=line.length / 1000, geometry=line))
        if direction not in spec["directions"]:
            continue
        L = line.length / 1000
        # Probes at the middle of each spacing interval, so none sits on a city-centre end.
        for k, d in enumerate(np.arange(spec["spacing_km"] / 2, L, spec["spacing_km"])):
            pt = line.interpolate(d * 1000)
            km_from_kampala = d if direction == "outbound" else L - d
            probes.append(dict(corridor=name, direction=direction,
                               probe_id=f"{name}_{direction[0]}{k:03d}",
                               km_from_kampala=round(km_from_kampala, 2), geometry=pt))

cl = gpd.GeoDataFrame(lines, crs=C.UTM).to_crs(4326)
pr = gpd.GeoDataFrame(probes, crs=C.UTM).to_crs(4326)
pr["lon"], pr["lat"] = pr.geometry.x.round(6), pr.geometry.y.round(6)
if os.path.exists(C.PROBES_GPKG):
    os.remove(C.PROBES_GPKG)
cl.to_file(C.PROBES_GPKG, layer="centrelines", driver="GPKG")
pr.to_file(C.PROBES_GPKG, layer="probes", driver="GPKG")
print(pr.groupby(["corridor", "direction"]).size().to_string())
print(f"{len(pr)} TomTom probes per poll; budget {C.TOMTOM_DAILY_REQUESTS}/day allows "
      f"{C.TOMTOM_DAILY_REQUESTS // len(pr)} polls/day "
      f"(every {24 * 60 / (C.TOMTOM_DAILY_REQUESTS // len(pr)):.0f} min)")
print("wrote", C.PROBES_GPKG)
