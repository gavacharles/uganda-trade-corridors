"""Data for the web pages (web/explorer.html): one compact JSON from the study's outputs.

    python web/build_web_data.py

Writes web/explorer_data.json (every 500 m piece with its causes, people, growth and minutes
lost; corridor summaries, hotspots, fix scenarios; Uganda outline, lakes and railways for the
map, simplified) and inlines it into web/explorer.html between the DATA markers.
"""
import json, os, re, sys
import numpy as np
import pandas as pd
import geopandas as gpd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import config as C  # noqa: E402

O = lambda f: pd.read_csv(os.path.join(C.OUTPUTS, f))  # noqa: E731
P = O("pieces_typed.csv").sort_values(["corridor", "piece"])
tt, pc, sf, gr = O("travel_time_pieces.csv"), O("travel_time_piece_causes.csv"), O("safety_pieces.csv"), O("growth_pieces.csv")
D = (P[["corridor", "piece", "km_start", "lon", "lat", "place", "road_type", "buildings_100m", "junctions_major",
        "junctions_minor", "weighbridges", "police_posts", "signals", "grade_pct"]]
     .merge(tt[["corridor", "piece", "car_excess_min", "truck_excess_min"]])
     .merge(sf[["corridor", "piece", "people_300m", "truck_kmh", "exposure", "schools_300m"]])
     .merge(gr[["corridor", "piece", "built_ha_2000", "built_ha_2020"]], how="left")
     .merge(pc, on=["corridor", "piece"]))
CAUSES = [c.split("|")[1] for c in pc.columns if c.startswith("truck|")]
TYPE = {"open road": 0, "roadside settlement": 1, "town": 2}

corridors = {}
for c, cfg in C.CORRIDORS.items():
    d = D[D.corridor == c]
    rows = []
    for rr in d.to_dict("records"):
        rows.append([round(rr["km_start"], 1), round(rr["lon"], 4), round(rr["lat"], 4), TYPE[rr["road_type"]],
                     rr["place"] if isinstance(rr["place"], str) else "",
                     int(rr["buildings_100m"]), int(rr["junctions_major"] + rr["junctions_minor"]),
                     round(rr["truck_excess_min"], 3), round(rr["car_excess_min"], 3),
                     int(rr["people_300m"]), round(rr["truck_kmh"], 1), round(rr["exposure"], 4),
                     round(float(np.nan_to_num(rr["built_ha_2020"] - rr["built_ha_2000"])), 2),
                     int(rr["weighbridges"]), int(rr["police_posts"]), int(rr["signals"]), int(rr["schools_300m"]),
                     [round(float(rr["truck|" + k]), 3) for k in CAUSES]])
    corridors[c] = dict(label=cfg["label"], short=cfg["short"], ref=cfg["ref"], pieces=rows)
FIELDS = ["km", "lon", "lat", "type", "place", "buildings_100m", "joining_roads", "truck_min", "car_min", "people_300m",
          "truck_kmh", "exposure", "new_built_ha", "weighbridges", "police_posts", "signals", "schools", "causes"]

tot = O("travel_time_totals.csv")
tot = tot[tot.direction == "outbound"]
typ = O("typology_summary.csv")
grs = O("growth_summary.csv")
grs = grs[grs.road_type == "all"]
cost = O("costs.csv")
sc = O("scenarios.csv")
sc = sc[sc.vehicle == "truck"]
hs = O("hotspots.csv")
rel = O("reliability.csv")
summary = {}
for c in C.CORRIDORS:
    t = tot[tot.corridor == c].set_index("vehicle")
    summary[c] = dict(
        car_min=round(t.loc["car", "minutes"]), car_open=round(t.loc["car", "open_road_minutes"]),
        truck_min=round(t.loc["truck", "minutes"]), truck_open=round(t.loc["truck", "open_road_minutes"]),
        truck_p5=round(t.loc["truck", "p5"]), truck_p95=round(t.loc["truck", "p95"]),
        types={r.road_type: round(r.share, 3) for r in typ[typ.corridor == c].itertuples()},
        growth_pct=float(grs[grs.corridor == c].growth_2000_2020_pct.iloc[0]),
        truck_cost_usd_m=float(cost[(cost.corridor == c) & (cost.vehicle == "truck")].cost_per_year_usd_m.iloc[0]),
        buffer_index=float(rel[(rel.corridor == c) & (rel.vehicle == "truck")].buffer_index.iloc[0]),
        fixes=[dict(label=r.label, min=r.minutes_saved, p5=r.p5, p95=r.p95) for r in sc[sc.corridor == c].itertuples()],
        hotspots=[dict(km_from=r.km_from, km_to=r.km_to, place=r.place, truck=r.truck_excess_min, car=r.car_excess_min,
                       causes=r.main_causes) for r in hs[hs.corridor == c].itertuples()])

# map layers, simplified, in lon/lat
dist = gpd.read_file(C.DISTRICTS).to_crs(4326)
uganda = dist.union_all().simplify(0.01)
lakes = gpd.read_file(os.path.join(C.DATA, "ne_lakes", "ne_10m_lakes.shp")).to_crs(4326).cx[29:35.2, -1.8:4.4]
lakes = lakes[lakes.area > 0.02].geometry.simplify(0.01)
rails = gpd.read_file(os.path.join(C.DATA, "railways.gpkg"))
rails = rails[rails.railway.isin(["rail", "disused"])]


def rings(g):
    polys = [g] if g.geom_type == "Polygon" else list(g.geoms)
    return [[[round(x, 3), round(y, 3)] for x, y in p.exterior.coords] for p in polys]


def lines(g):
    parts = [g] if g.geom_type == "LineString" else list(g.geoms)
    return [[[round(x, 3), round(y, 3)] for x, y in p.coords] for p in parts]


railsd = {k: sum((lines(g.simplify(0.005)) for g in grp.geometry), []) for k, grp in rails.groupby("railway")}
data = dict(fields=FIELDS, causes=CAUSES, corridors=corridors, summary=summary,
            map=dict(uganda=rings(uganda), lakes=sum((rings(g) for g in lakes), []), rails=railsd))
js = json.dumps(data, separators=(",", ":"), allow_nan=False)
open(os.path.join(ROOT, "web", "explorer_data.json"), "w").write(js)
html_path = os.path.join(ROOT, "web", "explorer.html")
if os.path.exists(html_path):
    h = open(html_path).read()
    h = re.sub(r"(/\*DATA\*/).*?(/\*END\*/)", lambda m: m.group(1) + js + m.group(2), h, flags=re.S)
    open(html_path, "w").write(h)
print(f"wrote web/explorer_data.json ({len(js) / 1e3:.0f} kB), {sum(len(c['pieces']) for c in corridors.values())} pieces")
