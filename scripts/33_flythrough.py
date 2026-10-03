"""Fly-through of Uganda's bottlenecks, from the country down to street level: the worst 2 km on
each corridor that is not a weighbridge, plus the two worst weighbridges, in a loop round Kampala.

    python scripts/33_flythrough.py      # figures/a7_bottleneck_flythrough.mp4/.gif
"""
import os, re
import numpy as np
import pandas as pd
import geopandas as gpd

import config as C
import flylib

O = lambda f: pd.read_csv(os.path.join(C.OUTPUTS, f))  # noqa: E731
P = gpd.read_file(os.path.join(C.DATA, "pieces.gpkg")).to_crs(4326)
P = P.merge(O("travel_time_pieces.csv")[["corridor", "piece", "truck_excess_min", "km_mid"]])
P["per_km"] = P.truck_excess_min / 0.5
H = O("hotspots.csv")
wb = H.main_causes.str.split(";").str[0].str.startswith("weighbridge")
picks = pd.concat([H[~wb].loc[H[~wb].groupby("corridor").truck_excess_min.idxmax()],
                   H[wb].nlargest(2, "truck_excess_min")])
cen = P.geometry.centroid
lon, lat = [], []
for r in picks.itertuples():
    d = P[P.corridor == r.corridor]
    i = (d.km_mid - (r.km_from + r.km_to) / 2).abs().idxmin()
    lon.append(cen.x[i]); lat.append(cen.y[i])
picks = picks.assign(lon=lon, lat=lat)
# a loop round Kampala: order by bearing from the city
picks["ang"] = np.arctan2(picks.lat - 0.3136, picks.lon - 32.5825)
picks = picks.sort_values("ang", ascending=False)
LEAD = {"weighbridge": "weighbridge", "signals and crossings": "signals", "police posts": "police post",
        "speed humps (assumed)": "humps", "roadside activity": "roadside", "hills (trucks)": "hill"}
sites = []
for r in picks.itertuples():
    cfg = C.CORRIDORS[r.corridor]
    sites.append(dict(lon=r.lon, lat=r.lat, kicker=f"{cfg['ref']} · KAMPALA → {cfg['short'].upper()}",
                      place=r.place if isinstance(r.place, str) else "unnamed place",
                      road=f"km {r.km_from:.0f}–{r.km_to:.0f} · {r.road_type}", minutes=r.truck_excess_min,
                      causes=r.main_causes.split("; ")[:3], colour="#c4532d"))

ne = os.path.join(C.ROOT, "regional-corridors", "data", "ne_admin0", "ne_10m_admin_0_countries.shp")
countries = gpd.read_file(ne, columns=["ADMIN"])
lakes = gpd.read_file(os.path.join(C.DATA, "ne_lakes", "ne_10m_lakes.shp")).to_crs(4326)
B = pd.read_parquet(os.path.join(C.DATA, "buildings.parquet"), columns=["latitude", "longitude", "area_in_meters"])
flylib.fly("a7_bottleneck_flythrough", C.FIGURES, P[["corridor", "geometry", "per_km"]], sites, countries, lakes,
           {"Uganda"}, os.path.join(C.DATA, "osm_features.gpkg"), B,
           "Uganda's bottlenecks, from the air to the street",
           "The worst 2 km on each trade corridor and the two worst weighbridges; truck minutes lost against open road",
           (32.3, 1.4, 6.5))
