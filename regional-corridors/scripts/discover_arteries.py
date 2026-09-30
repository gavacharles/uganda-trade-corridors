"""Find every major road leaving each capital, from OpenStreetMap, and prepare it for the
shared pipeline (02_segments.py onwards).

For each hub city:
  1. Graph of motorway, trunk and primary roads (and their links) in the country's OSM
     extract. Countries tag their national roads differently (Uganda's A roads are mostly
     "primary", Kenya's B roads "trunk"), so all three classes count as arteries.
  2. Shortest network distance from the city centre (every road node within 4 km of it is
     a source, starting at its straight-line distance from the centre).
  3. An artery is a motorway, trunk or primary road that crosses the RING_KM ring of network
     distance. Crossings within 5 km of each other (the two carriageways of one road, or
     a road and its link) are one artery.
  4. Each artery is followed outward along the shortest-path tree to its farthest point
     (the longest branch, where it forks after the ring), then cut where it first leaves
     the country (Natural Earth borders) and at MAX_KM unless it is a trade corridor
     (PINNED, run to the border or port). Arteries shorter than MIN_KM are dropped.
  5. The artery's roads (every motorway, trunk or primary way within 300 m of its path) go
     to data/corridors.gpkg, one layer per artery, with an empty _fill layer, which is what
     02_segments.py reads; data/arteries.json lists start, end, route number and length.

config.py builds CORRIDORS from data/arteries.json, so the rest of the pipeline runs as usual:
    python scripts/discover_arteries.py && python run.py 02 03 04 05 06 08 09 10 ...
"""
import json, os, sys
import numpy as np
import geopandas as gpd
import networkx as nx
import pyogrio
from shapely.geometry import LineString, Point
from shapely.ops import substring

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from config import pbf_path  # noqa: E402
DATA = os.path.join(HERE, "..", "data")
RING_KM, MIN_KM, MAX_KM, SRC_KM, HUB_KM, GAP_PENALTY = 60, 100, 200, 4, 8, 3.0
# hub: (region, country as in Natural Earth ADMIN, Geofabrik extract, lon, lat of the centre)
HUBS = {
    "kampala": ("East", "Uganda", "uganda", 32.5825, 0.3136),
    "nairobi": ("East", "Kenya", "kenya", 36.8219, -1.2921),
    "kigali": ("East", "Rwanda", "rwanda", 30.0619, -1.9441),
    "dodoma": ("East", "United Republic of Tanzania", "tanzania", 35.7516, -6.1630),
    "dar_es_salaam": ("East", "United Republic of Tanzania", "tanzania", 39.2803, -6.8161),
    "pretoria": ("Southern", "South Africa", "south-africa", 28.1881, -25.7461),
    "johannesburg": ("Southern", "South Africa", "south-africa", 28.0473, -26.2041),
    "gaborone": ("Southern", "Botswana", "botswana", 25.9086, -24.6282),
    "harare": ("Southern", "Zimbabwe", "zimbabwe", 31.0530, -17.8292),
    "lusaka": ("Southern", "Zambia", "zambia", 28.2871, -15.4167),
    "maputo": ("Southern", "Mozambique", "mozambique", 32.5732, -25.9692),
    "windhoek": ("Southern", "Namibia", "namibia", 17.0832, -22.5609),
}
# Trade corridors: pinned by hub, preferred route number and end point (a border post, port or
# hub), run their full length inside the country. A discovered artery that leaves the hub the
# same way (its point 60 km out lies within 5 km of a pinned corridor) is dropped. A wrong or
# missing route number only removes the preference: the path is then the shortest by road.
# Kampala's four match the Uganda study's corridors (../scripts/config.py).
PINNED = [
    ("kampala", "A1", "Malaba", (34.2790, 0.6380)), ("kampala", "A6", "Elegu", (32.0800, 3.5750)),
    ("kampala", "A2", "Katuna", (30.0000, -1.4200)), ("kampala", "A9", "Hoima", (31.3520, 1.4320)),
    ("nairobi", "A8", "Mombasa", (39.6726, -4.0584)), ("nairobi", "A8", "Malaba", (34.2706, 0.6360)),
    ("kigali", "NR3", "Gatuna", (30.0117, -1.4248)), ("kigali", "", "Rusumo", (30.7830, -2.3800)),
    ("dar_es_salaam", "T1", "Tunduma", (32.7700, -9.3000)), ("dar_es_salaam", "", "Dodoma", (35.7516, -6.1630)),
    ("johannesburg", "N3", "Durban", (31.0000, -29.8600)), ("pretoria", "N1", "Beitbridge", (30.0000, -22.2200)),
    ("pretoria", "N4", "Lebombo", (31.9500, -25.4400)), ("harare", "A4", "Beitbridge", (30.0000, -22.2100)),
    ("harare", "A1", "Chirundu", (28.8500, -16.0300)), ("lusaka", "T2", "Chirundu", (28.8500, -16.0400)),
    ("lusaka", "T2", "Nakonde", (32.7500, -9.3300)), ("lusaka", "T1", "Livingstone", (25.8500, -17.8500)),
    ("windhoek", "B2", "Walvis Bay", (14.5100, -22.9500)), ("windhoek", "B6", "Buitepos", (19.9500, -22.2800)),
    ("maputo", "EN4", "Ressano Garcia", (31.9900, -25.4400)), ("gaborone", "A1", "Ramokgwebana", (27.6000, -20.6000)),
]
LIST_ONLY = "--list" in sys.argv   # print the arteries, write nothing
ONLY = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--hubs=")), None)
if ONLY:
    HUBS = {k: v for k, v in HUBS.items() if k in ONLY}

countries = gpd.read_file(os.path.join(DATA, "ne_admin0", "ne_10m_admin_0_countries.shp"))
out_json, layers = [], {}
cache = {}
for hub, (region, admin, extract, lon, lat) in HUBS.items():
    aeqd = f"+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m +no_defs"
    if extract not in cache:
        pbf = pbf_path(extract)
        r = pyogrio.read_dataframe(pbf, layer="lines", columns=["osm_id", "name", "highway", "other_tags"],
                                   where="highway IN ('motorway','motorway_link','trunk','trunk_link',"
                                         "'primary','primary_link')")
        tags = r.other_tags.fillna("")
        r["ref"] = tags.str.extract(r'"ref"=>"([^"]+)"', expand=False)
        r["oneway"] = tags.str.extract(r'"oneway"=>"([^"]+)"', expand=False)
        for t in ("lanes", "maxspeed", "surface"):
            r[t] = tags.str.extract(rf'"{t}"=>"([^"]+)"', expand=False)
        pl = pyogrio.read_dataframe(pbf, layer="points", columns=["name", "place"],
                                    where="place IN ('city','town')")
        cache[extract] = (r.drop(columns="other_tags"), pl)
    roads, places = cache[extract]
    border = countries[countries.ADMIN == admin].to_crs(aeqd).geometry.union_all()
    R = roads.to_crs(aeqd).explode(index_parts=False)
    G = nx.Graph()
    for w in R.itertuples():
        xy = [(round(x, 1), round(y, 1)) for x, y in w.geometry.coords]
        for a, b in zip(xy[:-1], xy[1:]):
            G.add_edge(a, b, w=float(np.hypot(b[0] - a[0], b[1] - a[1])), ref=w.ref if isinstance(w.ref, str) else None)
    nodes = np.array([n for n in G.nodes])
    d0 = np.hypot(nodes[:, 0], nodes[:, 1])
    src = [(tuple(n), float(d)) for n, d in zip(nodes[d0 < SRC_KM * 1000], d0[d0 < SRC_KM * 1000])]
    # route numbers that reach the city: on a road within HUB_KM of the centre
    near_refs = set()
    for u, v, e in G.edges(data=True):
        if e["ref"] and min(np.hypot(*u), np.hypot(*v)) < HUB_KM * 1000:
            near_refs |= {r.strip() for r in e["ref"].split(";")}
    # route length in the country, so short local numbers are skipped
    ref_len = {}
    for u, v, e in G.edges(data=True):
        e["refs"] = frozenset(x.strip() for x in e["ref"].split(";")) if e["ref"] else frozenset()
        for x in e["refs"]:
            ref_len[x] = ref_len.get(x, 0) + e["w"]
    for n, d in src:
        G.add_edge("SRC", n, w=d, ref=None, refs=frozenset())
    found = []
    for r in sorted(x for x in near_refs if ref_len.get(x, 0) >= MIN_KM * 1000):
        # follow route r; other roads only bridge untagged gaps, at GAP_PENALTY (weights set on the fly)
        wfun = lambda u, v, e, r=r: e["w"] if r in e["refs"] else e["w"] * GAP_PENALTY  # noqa: E731
        H = G
        dist, paths = nx.single_source_dijkstra(H, "SRC", weight=wfun, cutoff=6e6)
        on_nodes = {n for u, v, e in H.edges(data=True) if r in e["refs"] for n in (u, v)}
        ends = [n for n in on_nodes if n in dist and np.hypot(*n) > RING_KM * 1000]
        # branches: group ends by where their path crosses 30 km from the centre
        branch = {}
        for n in ends:
            pth = paths[n]
            k = next((p for p in pth[1:] if np.hypot(*p) > 30000), pth[-1])
            branch.setdefault(k, []).append(n)
        heads = []
        for k, ns in branch.items():
            far = max(ns, key=lambda n: dist[n])
            if any(np.hypot(k[0] - h[0], k[1] - h[1]) < 5000 and dist[far] <= dist[hf] for h, hf in heads):
                continue
            heads = [(h, hf) for h, hf in heads if not (np.hypot(k[0] - h[0], k[1] - h[1]) < 5000)] + [(k, far)]
        for _, far in heads:
            path = [p for p in paths[far] if p != "SRC"]
            on_len = sum(H[a][b]["w"] for a, b in zip(path[:-1], path[1:]) if r in H[a][b]["refs"])
            tot = sum(H[a][b]["w"] for a, b in zip(path[:-1], path[1:]))
            if tot == 0 or on_len / tot < 0.7:
                continue   # mostly on other roads: not this route
            line = LineString(path)
            if not border.contains(Point(path[-1])):   # cut where the route first leaves the country
                inside = [border.contains(Point(p)) for p in path]
                kk = inside.index(False) if False in inside else len(path)
                if kk >= 2:
                    line = LineString(path[:kk])
            full_km = line.length / 1000
            if full_km < MIN_KM:
                continue
            end_pt = Point(line.coords[-1])
            pls = places.to_crs(aeqd)
            dd = pls.distance(end_pt)
            toward = pls.name[dd.idxmin()] if len(pls) and dd.min() < 40000 else f"{int(full_km)} km"
            ref = r
            trade = False
            use = line if full_km <= MAX_KM else substring(line, 0, MAX_KM * 1000)
            found.append(dict(hub=hub, region=region, country=admin, ref=ref, toward=toward, full_km=round(full_km, 1),
                              km=round(use.length / 1000, 1), trade=trade, line=use))
    # pinned trade corridors
    pinned = []
    for ph, pref, ptoward, pend in PINNED:
        if ph != hub:
            continue
        e = gpd.GeoSeries([Point(pend)], crs=4326).to_crs(aeqd).iloc[0]
        cand = [n for n in G.nodes if n != "SRC"]
        arr = np.array(cand)
        tgt = cand[int(np.argmin(np.hypot(arr[:, 0] - e.x, arr[:, 1] - e.y)))]
        wfun = lambda u, v, ed, r=pref: ed["w"] if r and r in ed["refs"] else ed["w"] * (GAP_PENALTY if r else 1)  # noqa: E731
        try:
            path = [p for p in nx.dijkstra_path(G, "SRC", tgt, weight=wfun) if p != "SRC"]
        except nx.NetworkXNoPath:
            print(f"{hub}: no road path to {ptoward}", flush=True)
            continue
        line = LineString(path)
        if not border.contains(Point(path[-1])):
            inside = [border.contains(Point(p)) for p in path]
            kk = inside.index(False) if False in inside else len(path)
            if kk >= 2:
                line = LineString(path[:kk])
        pinned.append(dict(hub=hub, region=region, country=admin, ref=pref, toward=ptoward,
                           full_km=round(line.length / 1000, 1), km=round(line.length / 1000, 1), trade=True, line=line))
    at60 = lambda f: f["line"].interpolate(min(60000, f["line"].length))  # noqa: E731
    found = [f for f in found if all(at60(f).distance(at60(pf)) > 5000 for pf in pinned)]
    # de-duplicate: two routes that end at the same place (concurrent numbers) are one artery
    found = pinned + sorted(found, key=lambda f: -f["full_km"])
    keep = []
    for f in found:
        if all(Point(f["line"].coords[-1]).distance(Point(k["line"].coords[-1])) > 10000 for k in keep):
            keep.append(f)
    for f in keep:
        name = f"{hub}_{(f['ref'] or 'road').lower().replace(' ', '')}_{f['toward'].lower().replace(' ', '_')}"
        name = "".join(ch for ch in name if ch.isalnum() or ch == "_")
        while name in layers:
            name += "_b"
        g = gpd.GeoSeries([f["line"]], crs=aeqd).to_crs(4326).iloc[0]
        ways = R[R.intersects(f["line"].buffer(300))].to_crs(4326)
        layers[name] = ways
        x0, y0, x1, y1 = g.bounds
        out_json.append(dict(name=name, hub=hub, region=f["region"], country=f["country"], ref=f["ref"],
                             toward=f["toward"], km=f["km"], full_km=f["full_km"], trade=f["trade"],
                             start=list(g.coords[0]), end=list(g.coords[-1]),
                             bbox=[x0 - 0.05, y0 - 0.05, x1 + 0.05, y1 + 0.05]))
        print(f"{hub:14s} {f['ref']:8s} → {f['toward']:22s} full {f['full_km']:6.0f} km, used {f['km']:5.0f}"
              f"{'  TRADE' if f['trade'] else ''}", flush=True)

if LIST_ONLY:
    raise SystemExit
json.dump(out_json, open(os.path.join(DATA, "arteries.json"), "w"), indent=1)
gpkg = os.path.join(DATA, "corridors.gpkg")
if os.path.exists(gpkg):
    os.remove(gpkg)
for name, ways in layers.items():
    cols = ["osm_id", "name", "highway", "ref", "lanes", "maxspeed", "surface", "oneway", "geometry"]
    ways[cols].to_file(gpkg, layer=name, driver="GPKG")
    ways[cols].iloc[:0].to_file(gpkg, layer=name + "_fill", driver="GPKG")
print(f"wrote {len(out_json)} arteries to data/arteries.json and data/corridors.gpkg "
      f"({sum(a['km'] for a in out_json):,.0f} km)")
