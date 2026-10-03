"""The Uganda street-level map, web/uganda_map.html, from the same template and builder as the
regional map (web/map_template.html, webmap.py).

    python scripts/34_web_map.py

The five corridors in 2 km stretches; towns to fly to; the ten worst 2 km on each corridor
(outputs/hotspots.csv) with their causes; the fly-through stops of 33_flythrough.py (the worst
stretch on each corridor that is not a weighbridge, and the two worst weighbridges, round Kampala);
street detail around every stop and hotspot in web/detail_ug/.
"""
import os
import numpy as np
import pandas as pd
import geopandas as gpd

import config as C
import webmap

O = lambda f: pd.read_csv(os.path.join(C.OUTPUTS, f))  # noqa: E731
P = gpd.read_file(os.path.join(C.DATA, "pieces.gpkg")).to_crs(4326)
P["length_km"] = P.to_crs(C.UTM).length / 1000
T = O("pieces_typed.csv")
P = P.merge(T[["corridor", "piece", "km_start", "km_mid", "road_type", "place", "buildings_100m", "wet_days_per_year"]
              + webmap.CONTROLS], how="left", suffixes=("_x", ""))
P = P.merge(O("travel_time_pieces.csv")[["corridor", "piece", "truck_excess_min"]], how="left")
P = P.merge(O("safety_pieces.csv")[["corridor", "piece", "people_300m", "exposure"]], how="left")
P = P.merge(O("fuel_co2_pieces.csv")[["corridor", "piece", "friction_litres"]], how="left")
P = P.merge(O("growth_pieces.csv")[["corridor", "piece", "built_ha_2000", "built_ha_2020"]], how="left")
P = P.loc[:, ~P.columns.str.endswith("_x")]
ORDER = list(C.CORRIDORS)
segs = webmap.stretches(P, ORDER)

corr = []
for c in ORDER:
    cfg, d = C.CORRIDORS[c], P[P.corridor == c]
    L = d.length_km.sum()
    corr.append(dict(id=c, road=f"Kampala → {cfg['short']} ({cfg['ref']})", hub="Kampala", country=f"{cfg['ref']} {cfg['short']} road",
                     region="East", trade=True, km=round(float(L)),
                     tm=round(float(d.truck_excess_min.sum() / L * 100), 1),
                     set=round(float(d.road_type.isin(["roadside settlement", "town"]).mean()), 2),
                     bld=round(float(d.buildings_100m.sum() / L)), exp=round(float(d.exposure.sum() / L), 2)))

TOWNS = {"Kampala": (32.5825, 0.3136), "Jinja": (33.2040, 0.4390), "Tororo": (34.1810, 0.6930),
         "Gulu": (32.2990, 2.7740), "Hoima": (31.3520, 1.4320), "Masaka": (31.7350, -0.3330),
         "Mbarara": (30.6550, -0.6070), "Kabale": (29.9856, -1.2486), "Fort Portal": (30.2750, 0.6710),
         "Kasese": (30.0880, 0.1830), "Mityana": (32.0420, 0.4170), "Luweero": (32.4730, 0.8490)}
hub = [dict(name=n, country="Uganda", region="East", lon=x, lat=y, z=12) for n, (x, y) in TOWNS.items()]

cen = P.geometry.centroid


def locate(r):
    d = P[P.corridor == r.corridor]
    i = (d.km_mid - (r.km_from + r.km_to) / 2).abs().idxmin()
    return round(cen.x[i], 4), round(cen.y[i], 4)


H = O("hotspots.csv")
hot = []
for r in H.itertuples():
    lon, lat = locate(r)
    cfg = C.CORRIDORS[r.corridor]
    hot.append(dict(id=len(hot), lon=lon, lat=lat, place=r.place if isinstance(r.place, str) else "unnamed place",
                    country=f"{cfg['ref']} {cfg['short']} road", road=f"Kampala → {cfg['short']} ({cfg['ref']})",
                    km=f"{r.km_from:.0f}–{r.km_to:.0f}", truck=round(r.truck_excess_min, 1),
                    car=round(r.car_excess_min, 1), type=r.road_type, causes=r.main_causes))

# fly-through stops, as 33_flythrough.py
wb = H.main_causes.str.split(";").str[0].str.startswith("weighbridge")
picks = pd.concat([H[~wb].loc[H[~wb].groupby("corridor").truck_excess_min.idxmax()],
                   H[wb].nlargest(2, "truck_excess_min")])
xy = [locate(r) for r in picks.itertuples()]
picks = picks.assign(lon=[a for a, _ in xy], lat=[b for _, b in xy])
picks = picks.assign(ang=np.arctan2(picks.lat - 0.3136, picks.lon - 32.5825)).sort_values("ang", ascending=False)
tour = []
for r in picks.itertuples():
    cfg = C.CORRIDORS[r.corridor]
    tour.append(dict(lon=r.lon, lat=r.lat, place=r.place if isinstance(r.place, str) else "unnamed place",
                     country=f"{cfg['ref']} · Kampala → {cfg['short']}", region="East",
                     road=f"Kampala → {cfg['short']} ({cfg['ref']})", km=f"{r.km_from:.0f}–{r.km_to:.0f}",
                     truck=round(r.truck_excess_min, 1), car=round(r.car_excess_min, 1), type=r.road_type,
                     causes=r.main_causes))

B = pd.read_parquet(os.path.join(C.DATA, "buildings.parquet"), columns=["latitude", "longitude", "area_in_meters"])
win = webmap.detail(webmap.centres_of(tour + hot), B, os.path.join(C.DATA, "osm_features.gpkg"),
                    os.path.join(webmap.WEB, "detail_ug"))

META = dict(
    LW="1.7", HOTZ="8", TITLE="Uganda Corridors, Street Level", H1="Uganda's trade corridors", OGTITLE="Uganda's five trade corridors, every 2 km, down to street level",
    OGDESC="Time lost, safety, diesel and roadside growth on Uganda's five trade corridors out of Kampala, every 2 km, "
           "with every building at the bottlenecks. Open data.",
    SUB="The five trade corridors out of Kampala, every 2 km. Tap a road or a ● for details. Press ▶ Fly-through to "
        "visit the worst bottlenecks at street level.",
    ALLROADS="All five corridors", HUBHEAD="Fly to a town", HOTHEAD="Ten worst stretches, by corridor",
    HOMETITLE="Whole country", TYPENOTE="clustered on the five corridors (paper 1)", HUBNOTE="", DETDIR="detail_ug",
    FOOT='Open data: OpenStreetMap, Google Open Buildings, GHSL, WorldPop 2025, CHIRPS; travel-time and fuel models as '
         'in the paper. Light traffic, dry day; speed humps assumed in towns. Code, data and paper: '
         '<a href="https://github.com/gavacharles/uganda-trade-corridors">github.com/gavacharles/uganda-trade-corridors</a>'
         ' · <a href="./">The Uganda explorer</a> · <a href="regional.html">The regional map (54 roads, 12 hubs)</a>')
webmap.write_page(dict(segs=segs, corr=corr, hubs=hub, hot=hot, tour=tour, win=win), META, "uganda_map.html")
