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

# ---------- the fly-through stops (as rx15): worst stretch per country, weighbridge stops left aside
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

# ---------- street detail around every stop and hotspot, one small file each (loaded on demand)
import base64, pyarrow.parquet as pq  # noqa: E402
import geopandas as gpd  # noqa: E402
DET = os.path.join(WEB, "detail")
os.makedirs(DET, exist_ok=True)
for f in os.listdir(DET):
    os.remove(os.path.join(DET, f))
HALFW = 0.03                       # about 6.6 km windows
centres = []
for p_ in tour + hot:
    if all(abs(p_["lon"] - c[0]) > 0.02 or abs(p_["lat"] - c[1]) > 0.02 for c in centres):
        centres.append((p_["lon"], p_["lat"]))
B = pq.read_table(os.path.join(C.DATA, "buildings.parquet"), columns=["latitude", "longitude", "area_in_meters"]).to_pandas()
FEAT = os.path.join(C.DATA, "osm_features.gpkg")
HW = ["motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "service", "track"]
CTRL = {"traffic_signals": "s", "pedestrian_crossing": "c", "speed_hump": "h", "rumble_strip": "h",
        "checkpoint_or_police": "p", "weighbridge": "w", "level_crossing": "l", "market": "m", "fuel": "f",
        "school": "k"}
RANK = {"city": 0, "town": 1, "suburb": 2, "village": 3, "neighbourhood": 4, "locality": 5, "hamlet": 6}
b64 = lambda a: base64.b64encode(a.tobytes()).decode()  # noqa: E731


def coords(g, nd=5):
    if g is None or g.is_empty:
        return []
    g = shapely.simplify(g, 0.00002)
    out = []
    for q in shapely.get_parts(shapely.get_parts(g)):
        if q.is_empty or q.geom_type not in ("Polygon", "LineString", "LinearRing"):
            continue
        ring = q.exterior.coords if q.geom_type == "Polygon" else q.coords
        out.append([v for xy in ring for v in (round(xy[0], nd), round(xy[1], nd))])
    return out


wins, total = [], 0
for i, (lon, lat) in enumerate(centres):
    x0, x1, y0, y1 = lon - HALFW, lon + HALFW, lat - HALFW, lat + HALFW
    bb = B[B.longitude.between(x0, x1) & B.latitude.between(y0, y1)]
    det = dict(o=[round(x0, 5), round(y0, 5)],
               bx=b64(np.round((bb.longitude.to_numpy() - x0) / 1e-5).astype("<u2")),
               by=b64(np.round((bb.latitude.to_numpy() - y0) / 1e-5).astype("<u2")),
               bs=b64(np.clip(np.round(np.sqrt(bb.area_in_meters.to_numpy())), 1, 255).astype("u1")))
    rr = gpd.read_file(FEAT, layer="roads", bbox=(x0, y0, x1, y1))
    det["r"] = [[HW.index(h), c] for h, g in zip(rr.highway, rr.geometry) if h in HW for c in coords(g)]
    ww = gpd.read_file(FEAT, layer="waterways", bbox=(x0, y0, x1, y1))
    det["w"] = [c for g in ww.geometry for c in coords(g)]
    aa = gpd.read_file(FEAT, layer="areas", bbox=(x0, y0, x1, y1))
    det["a"] = [[k, c] for k, g in zip(aa.kind, aa.geometry) if k in ("wetland", "market") and g is not None
                for c in coords(g.buffer(0) if not g.is_valid else g)]
    pp = gpd.read_file(FEAT, layer="points", bbox=(x0, y0, x1, y1))
    det["k"] = [[CTRL[k], round(g.x, 5), round(g.y, 5)] for k, g in zip(pp.kind, pp.geometry) if k in CTRL]
    pl = pp[(pp.kind == "place") & pp.name.notna()]
    det["n"] = [[n, round(g.x, 5), round(g.y, 5), RANK.get(r, 9)] for n, g, r in zip(pl.name, pl.geometry, pl.place)
                if "/" not in n]
    js = json.dumps(det, separators=(",", ":"), ensure_ascii=False)
    open(os.path.join(DET, f"w{i}.json"), "w", encoding="utf-8").write(js)
    total += len(js)
    wins.append([round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4)])
print(f"street detail: {len(wins)} windows, {total / 1e6:.1f} MB, buildings in view windows written")

data = dict(segs=segs, corr=corr, hubs=hub, hot=hot, tour=tour, win=wins)
blob = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
tpl = open(os.path.join(WEB, "regional_template.html"), encoding="utf-8").read()
html = re.sub(r"/\*DATA\*/.*?/\*END\*/", lambda m: "/*DATA*/" + blob + "/*END*/", tpl, flags=re.S)
open(os.path.join(WEB, "regional.html"), "w", encoding="utf-8").write(html)
print(f"wrote web/regional.html: {len(segs)} stretches, {len(hot)} hotspots, {len(html) / 1e6:.1f} MB")
