"""Data for the regional interactive map (web/regional.html), inlined into the page.

    python scripts/build_regional_web.py

Every road is cut into 2 km stretches (four 500 m pieces), each with its road type and the
measures the maps show: truck minutes lost per km, people within 300 m, safety exposure, extra
diesel, built-up land added 2000-2020, heavy-rain days and controls mapped in OSM. Hubs carry their
summary; the worst stretches (one list per country) carry their causes. Geometry is simplified to
about 30 m and rounded to 4 decimals. The page is written from web/regional_template.html with the
data between the DATA markers.
"""
import json, os, re
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import LineString, MultiLineString
from shapely.ops import linemerge

from regional_common import ART, C, H, O, distinct, pieces

WEB = os.path.abspath(os.path.join(C.ROOT, "..", "web"))
SHORT = {"United Republic of Tanzania": "Tanzania"}
TYPE = {"open road": 0, "roadside settlement": 1, "town": 2}

P = pieces.to_crs(4326).copy()
T = O("pieces_typed.csv")
P = P.merge(T[["corridor", "piece", "road_type", "place", "buildings_100m", "wet_days_per_year", "signals",
               "ped_crossings", "humps", "police_posts", "weighbridges", "level_crossings"]], how="left")
P = P.merge(O("safety_pieces.csv")[["corridor", "piece", "people_300m", "exposure"]], how="left")
P = P.merge(O("fuel_co2_pieces.csv")[["corridor", "piece", "friction_litres"]], how="left")
P = P.merge(O("growth_pieces.csv")[["corridor", "piece", "built_ha_2000", "built_ha_2020"]], how="left")
P["controls"] = P[["signals", "ped_crossings", "humps", "police_posts", "weighbridges", "level_crossings"]].sum(axis=1)
P["seg"] = P.piece // 4

cidx = {c: i for i, c in enumerate(ART.index)}
segs = []
for (c, s), d in P.groupby(["corridor", "seg"], sort=False):
    L = d.length_km.sum()
    if L <= 0:
        continue
    g = linemerge([x for geom in d.geometry for x in (geom.geoms if isinstance(geom, MultiLineString) else [geom])])
    g = shapely.simplify(g, 0.0003)
    lines = list(g.geoms) if isinstance(g, MultiLineString) else [g]
    coords = [[[round(y, 4), round(x, 4)] for x, y in ln.coords] for ln in lines]
    pl = d.place.dropna()
    segs.append(dict(
        c=cidx[c], km=round(float(d.km_start.min()), 1), g=coords,
        t=int(TYPE.get(d.road_type.mode().iloc[0], 0)) if d.road_type.notna().any() else 0,
        pl=pl.iloc[0] if len(pl) else "",
        d=round(float(d.truck_excess_min.sum() / L), 2),
        b=int(d.buildings_100m.sum() / L),
        p=int(d.people_300m.sum() / L),
        e=round(float(d.exposure.sum() / L), 3),
        f=round(float(d.friction_litres.sum() / L), 3),
        gr=round(float((d.built_ha_2020 - d.built_ha_2000).sum() / L), 2),
        w=round(float(d.wet_days_per_year.mean()), 1),
        k=int(d.controls.sum())))

cmp = O("compare_arteries.csv").set_index("corridor")
trade = O("compare_trade.csv").set_index("corridor")
corr = []
for c, a in ART.iterrows():
    r = trade.loc[c] if c in trade.index else cmp.loc[c]
    corr.append(dict(id=c, road=a.road, hub=a.hub_name, country=SHORT.get(a.country, a.country), region=a.region,
                     trade=bool(a.trade), km=round(float(P[P.corridor == c].length_km.sum())),
                     tm=round(float(r.truck_min_per_100km), 1), set=round(float(r.settlement_share + r.town_share), 2),
                     bld=round(float(r.buildings_100m_per_km)), exp=round(float(r.exposure_per_km), 2)))

hubs = O("compare_hubs.csv").set_index("hub")
hub = []
for h, g in ART.groupby("hub"):
    r = hubs.loc[h]
    hub.append(dict(name=g.hub_name.iloc[0], country=SHORT.get(g.country.iloc[0], g.country.iloc[0]),
                    region=g.region.iloc[0], lon=g.start.iloc[0][0], lat=g.start.iloc[0][1], n=len(g),
                    tm=round(float(r.truck_min_per_100km), 1), set=round(float(r.settlement_share + r.town_share), 2),
                    bld=round(float(r.buildings_100m_per_km)), ppl=round(float(r.people_per_km)),
                    exp=round(float(r.exposure_per_km), 2), gr=round(float(r.growth_2000_2020) * 100)))

hot = []
for country, h in H.groupby("country"):
    for r in distinct(h, 4, min_km=5).itertuples():
        hot.append(dict(id=len(hot), lon=round(r.lon, 4), lat=round(r.lat, 4), place=r.place_name,
                        country=SHORT.get(country, country), road=ART.road[r.corridor],
                        km=f"{r.km_from:.0f}–{r.km_to:.0f}", truck=round(r.truck_excess_min, 1),
                        car=round(r.car_excess_min, 1), type=r.road_type, causes=r.main_causes))

data = dict(segs=segs, corr=corr, hubs=hub, hot=hot)
blob = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
tpl = open(os.path.join(WEB, "regional_template.html"), encoding="utf-8").read()
html = re.sub(r"/\*DATA\*/.*?/\*END\*/", lambda m: "/*DATA*/" + blob + "/*END*/", tpl, flags=re.S)
open(os.path.join(WEB, "regional.html"), "w", encoding="utf-8").write(html)
print(f"wrote web/regional.html: {len(segs)} stretches, {len(hot)} hotspots, {len(html) / 1e6:.1f} MB")
