"""The regional street-level map, web/regional.html (template web/map_template.html, builder
../scripts/webmap.py).

    python scripts/build_regional_web.py

Every road in 2 km stretches with its road type and the measures the maps show; hubs with their
summary; the worst stretches (four per country, at least 5 km apart) with their causes; the
fly-through stops (the worst stretch per country, weighbridge stops left aside, as in rx15); and
street detail around every stop and hotspot in web/detail/.
"""
import os, re
import pyarrow.parquet as pq

from regional_common import ART, C, H, O, distinct, pieces
import webmap

SHORT = {"United Republic of Tanzania": "Tanzania"}

P = pieces.to_crs(4326).copy()
T = O("pieces_typed.csv")
P = P.merge(T[["corridor", "piece", "road_type", "place", "buildings_100m", "wet_days_per_year"] + webmap.CONTROLS],
            how="left")
P = P.merge(O("safety_pieces.csv")[["corridor", "piece", "people_300m", "exposure"]], how="left")
P = P.merge(O("fuel_co2_pieces.csv")[["corridor", "piece", "friction_litres"]], how="left")
P = P.merge(O("growth_pieces.csv")[["corridor", "piece", "built_ha_2000", "built_ha_2020"]], how="left")
segs = webmap.stretches(P, list(ART.index))

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

HH = H.copy()
wbm = HH.main_causes.map(lambda t: float(m.group(1)) if (m := re.search(r"weighbridge ([\d.]+)", t)) else 0.0)
HH["other"] = HH.truck_excess_min - wbm
ORDER = ["Rwanda", "Uganda", "Kenya", "United Republic of Tanzania", "Zambia", "Zimbabwe", "Mozambique",
         "South Africa", "Botswana", "Namibia"]
pick = HH.loc[HH.groupby("country").other.idxmax()].set_index("country").loc[ORDER].reset_index()
tour = [dict(lon=round(r.lon, 4), lat=round(r.lat, 4), place=r.place_name, country=SHORT.get(r.country, r.country),
             region=r.region, road=ART.road[r.corridor], km=f"{r.km_from:.0f}–{r.km_to:.0f}",
             truck=round(r.truck_excess_min, 1), car=round(r.car_excess_min, 1), type=r.road_type,
             causes=r.main_causes) for r in pick.itertuples()]

B = pq.read_table(os.path.join(C.DATA, "buildings.parquet"), columns=["latitude", "longitude", "area_in_meters"]).to_pandas()
win = webmap.detail(webmap.centres_of(tour + hot), B, os.path.join(C.DATA, "osm_features.gpkg"),
                    os.path.join(webmap.WEB, "detail"))

META = dict(
    LW="1", HOTZ="5", TITLE="Leaving the Capital", H1="Leaving the capital", OGTITLE="Leaving the capital: 54 African trade roads, every 2 km",
    OGDESC="Time lost, safety, diesel and roadside growth on the main roads out of 12 East and Southern African hubs, "
           "every 2 km, down to street level. Open data.",
    SUB="54 main roads out of 12 East and Southern African hubs, every 2 km. Tap a road or a ● for details. "
        "Press ▶ Fly-through to visit each country's worst bottleneck at street level.",
    ALLROADS="All 54 roads", HUBHEAD="Fly to a hub", HOTHEAD="Worst stretches, by country", HOMETITLE="Whole region",
    TYPENOTE="clustered jointly across all 54 roads", HUBNOTE="First 200 km of each road.", DETDIR="detail",
    FOOT='Open data: OpenStreetMap, Google Open Buildings, GHSL, GHS-POP 2025, CHIRPS; travel-time and fuel models as '
         'in the paper. Light traffic, dry day. Controls are as mapped in OSM, far more completely in South Africa. '
         'Code, data and paper: <a href="https://github.com/gavacharles/uganda-trade-corridors">'
         'github.com/gavacharles/uganda-trade-corridors</a> · Uganda in detail: <a href="uganda_map.html">the Uganda '
         'street-level map</a> and <a href="./">the Uganda explorer</a>')
webmap.write_page(dict(segs=segs, corr=corr, hubs=hub, hot=hot, tour=tour, win=win), META, "regional.html")
