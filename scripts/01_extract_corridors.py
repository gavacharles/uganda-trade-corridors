"""Extract every corridor in config.CORRIDORS (route number and cut-off box) from OpenStreetMap.

Reads the OSM extracts in config.PBFS (00_download_base.sh) and writes
data/corridors.gpkg (one layer per corridor, plus a <corridor>_fill layer of the other
main roads within 300 m, used to bridge gaps in the route tagging) and outputs/corridor_tags.csv, which
reports how much of each corridor has lanes, speed limit and surface recorded.

Run from corridors/scripts with ../../.venv/bin/python.
"""
import os
import pyogrio

import config as C

OUT = C.CORRIDORS_GPKG
TAGS = ("ref", "lanes", "maxspeed", "surface", "oneway")


import pandas as pd  # noqa: E402
roads = pd.concat([pyogrio.read_dataframe(
    pbf, layer="lines",
    where="highway IN ('motorway','motorway_link','trunk','trunk_link','primary','primary_link',"
          "'secondary','secondary_link','tertiary','tertiary_link')") for pbf in C.PBFS], ignore_index=True)
tags = roads.other_tags.fillna("")
for t in TAGS:
    roads[t] = tags.str.extract(rf'"{t}"=>"([^"]+)"', expand=False)

rows = []
if os.path.exists(OUT):
    os.remove(OUT)
for name, c in C.CORRIDORS.items():
    x0, y0, x1, y1 = c["bbox"]
    main = roads[roads.highway.str.match("motorway|trunk|primary")]
    sel = main[(main.ref.fillna("").str.split(";").apply(lambda r: c["ref"] in r))].cx[x0:x1, y0:y1]
    sel = sel[["osm_id", "name", "highway"] + list(TAGS) + ["geometry"]].copy()
    km = sel.to_crs(C.UTM).length / 1000
    sel["km"] = km
    sel.to_file(OUT, layer=name, driver="GPKG")
    # Every main road near the corridor, used only to bridge gaps in the route tagging.
    near = sel.to_crs(C.UTM).buffer(300).union_all()
    rs = roads.to_crs(C.UTM)
    fill = roads[rs.intersects(near).values & ~roads.osm_id.isin(sel.osm_id).values]
    fill[["osm_id", "name", "highway"] + list(TAGS) + ["geometry"]].to_file(
        OUT, layer=name + "_fill", driver="GPKG")
    row = dict(corridor=name, segments=len(sel), km_mapped=round(km.sum(), 1))
    for t in ("lanes", "maxspeed", "surface"):
        row[f"{t}_tagged_pct"] = round(100 * km[sel[t].notna()].sum() / km.sum())
    rows.append(row)
    print(row)

pd.DataFrame(rows).to_csv(os.path.join(C.OUTPUTS, "corridor_tags.csv"), index=False)
print("wrote", OUT)
