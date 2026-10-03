"""Shared builder for the street-level web maps (web/map_template.html):
web/regional.html (regional-corridors/scripts/build_regional_web.py) and web/uganda_map.html
(scripts/34_web_map.py).

  stretches(P, order)        2 km stretches from the 500 m pieces, with every measure the map shows
  detail(centres, ...)       one small JSON of street detail per stop (buildings at footprint size,
                             side roads, streams, wetlands and markets, controls, places), loaded on demand
  write_page(data, meta, out) the template with the data inlined and its {{TEXT}} filled in (the text is
                             kept in web/map_text/ so `python scripts/webmap.py <page>` re-renders a page
                             from a changed template without rebuilding its data)
"""
import base64, json, os, re
import numpy as np
import geopandas as gpd
import shapely
from shapely.geometry import MultiLineString
from shapely.ops import linemerge

WEB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "web"))
TYPE = {"open road": 0, "roadside settlement": 1, "town": 2}
CONTROLS = ["signals", "ped_crossings", "humps", "police_posts", "weighbridges", "level_crossings"]


def stretches(P, order):
    """P: pieces (EPSG:4326) with corridor, piece, km_start, length_km, road_type, place, buildings_100m,
    wet_days_per_year, the CONTROLS counts, people_300m, exposure, friction_litres, built_ha_2000/2020,
    truck_excess_min. order: corridor ids in the page's order."""
    P = P.assign(controls=P[CONTROLS].sum(axis=1), seg=P.piece // 4)
    cidx = {c: i for i, c in enumerate(order)}
    out = []
    for (c, s), d in P.groupby(["corridor", "seg"], sort=False):
        L = d.length_km.sum()
        if L <= 0:
            continue
        g = linemerge([x for geom in d.geometry for x in (geom.geoms if isinstance(geom, MultiLineString) else [geom])])
        g = shapely.simplify(g, 0.0003)
        lines = list(g.geoms) if isinstance(g, MultiLineString) else [g]
        pl = d.place.dropna()
        out.append(dict(
            c=cidx[c], km=round(float(d.km_start.min()), 1),
            g=[[[round(y, 4), round(x, 4)] for x, y in ln.coords] for ln in lines],
            t=int(TYPE.get(d.road_type.mode().iloc[0], 0)) if d.road_type.notna().any() else 0,
            pl=pl.iloc[0] if len(pl) else "",
            d=round(float(d.truck_excess_min.sum() / L), 2), b=int(d.buildings_100m.sum() / L),
            p=int(np.nan_to_num(d.people_300m.sum()) / L), e=round(float(np.nan_to_num(d.exposure.sum()) / L), 3),
            f=round(float(np.nan_to_num(d.friction_litres.sum()) / L), 3),
            gr=round(float(np.nan_to_num((d.built_ha_2020 - d.built_ha_2000).sum()) / L), 2),
            w=round(float(np.nan_to_num(d.wet_days_per_year.mean())), 1), k=int(d.controls.sum())))
    return out


HW = ["motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "service", "track"]
CTRL = {"traffic_signals": "s", "pedestrian_crossing": "c", "speed_hump": "h", "rumble_strip": "h",
        "checkpoint_or_police": "p", "weighbridge": "w", "level_crossing": "l", "market": "m", "fuel": "f",
        "school": "k"}
RANK = {"city": 0, "town": 1, "suburb": 2, "village": 3, "neighbourhood": 4, "locality": 5, "hamlet": 6}


def _b64(a):
    return base64.b64encode(a.tobytes()).decode()


def _coords(g, nd=5):
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


def centres_of(points, sep=0.02):
    out = []
    for p in points:
        if all(abs(p["lon"] - c[0]) > sep or abs(p["lat"] - c[1]) > sep for c in out):
            out.append((p["lon"], p["lat"]))
    return out


def detail(centres, buildings, feat, outdir, half=0.03):
    """buildings: DataFrame with longitude, latitude, area_in_meters. Returns the windows' boxes."""
    os.makedirs(outdir, exist_ok=True)
    for f in os.listdir(outdir):
        os.remove(os.path.join(outdir, f))
    wins, total = [], 0
    for i, (lon, lat) in enumerate(centres):
        x0, x1, y0, y1 = lon - half, lon + half, lat - half, lat + half
        bb = buildings[buildings.longitude.between(x0, x1) & buildings.latitude.between(y0, y1)]
        det = dict(o=[round(x0, 5), round(y0, 5)],
                   bx=_b64(np.round((bb.longitude.to_numpy() - x0) / 1e-5).astype("<u2")),
                   by=_b64(np.round((bb.latitude.to_numpy() - y0) / 1e-5).astype("<u2")),
                   bs=_b64(np.clip(np.round(np.sqrt(bb.area_in_meters.to_numpy())), 1, 255).astype("u1")))
        rd = lambda layer: gpd.read_file(feat, layer=layer, bbox=(x0, y0, x1, y1))  # noqa: E731
        rr = rd("roads")
        det["r"] = [[HW.index(h), c] for h, g in zip(rr.highway, rr.geometry) if h in HW for c in _coords(g)]
        det["w"] = [c for g in rd("waterways").geometry for c in _coords(g)]
        aa = rd("areas")
        det["a"] = [[k, c] for k, g in zip(aa.kind, aa.geometry) if k in ("wetland", "market") and g is not None
                    for c in _coords(g if g.is_valid else g.buffer(0))]
        pp = rd("points")
        det["k"] = [[CTRL[k], round(g.x, 5), round(g.y, 5)] for k, g in zip(pp.kind, pp.geometry) if k in CTRL]
        pl = pp[(pp.kind == "place") & pp.name.notna()]
        det["n"] = [[n, round(g.x, 5), round(g.y, 5), RANK.get(r, 9)] for n, g, r in zip(pl.name, pl.geometry, pl.place)
                    if "/" not in n]
        js = json.dumps(det, separators=(",", ":"), ensure_ascii=False)
        open(os.path.join(outdir, f"w{i}.json"), "w", encoding="utf-8").write(js)
        total += len(js)
        wins.append([round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4)])
    print(f"street detail: {len(wins)} windows, {total / 1e6:.1f} MB in {os.path.relpath(outdir, WEB)}/", flush=True)
    return wins


def retemplate(out):
    """Re-render a page from the current template, reusing its inlined data and saved text."""
    old = open(os.path.join(WEB, out), encoding="utf-8").read()
    data = json.loads(re.search(r"/\*DATA\*/(.*?)/\*END\*/", old, re.S).group(1))
    meta = json.load(open(os.path.join(WEB, "map_text", out.replace(".html", ".json")), encoding="utf-8"))
    write_page(data, meta, out)


def write_page(data, meta, out):
    os.makedirs(os.path.join(WEB, "map_text"), exist_ok=True)
    json.dump(meta, open(os.path.join(WEB, "map_text", out.replace(".html", ".json")), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    html = open(os.path.join(WEB, "map_template.html"), encoding="utf-8").read()
    for k, v in meta.items():
        html = html.replace("{{" + k + "}}", v)
    left = re.findall(r"\{\{[A-Z]+\}\}", html)
    if left:
        raise SystemExit(f"template text not filled: {sorted(set(left))}")
    blob = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    html = re.sub(r"/\*DATA\*/.*?/\*END\*/", lambda m: "/*DATA*/" + blob + "/*END*/", html, flags=re.S)
    open(os.path.join(WEB, out), "w", encoding="utf-8").write(html)
    print(f"wrote web/{out}: {len(data['segs'])} stretches, {len(data['hot'])} hotspots, {len(html) / 1e6:.1f} MB")


if __name__ == "__main__":
    import sys
    for page in sys.argv[1:]:
        retemplate(page)
