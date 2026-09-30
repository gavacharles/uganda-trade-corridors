"""Settings for the regional paper: the same pipeline as the Uganda study (../scripts), run on
every major road out of eleven East and Southern African capitals and trade hubs. run.py puts
this folder first on the import path, so every shared script reads this file as `config`.

The corridors are not typed here: scripts/discover_arteries.py finds them in OpenStreetMap
and writes data/arteries.json, which this file reads (km 0 = the hub).
"""
import json, math, os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
OUTPUTS = os.path.join(ROOT, "outputs")
FIGURES = os.path.join(ROOT, "figures")
for _d in (DATA, OUTPUTS, FIGURES):
    os.makedirs(_d, exist_ok=True)
CORRIDORS_GPKG = os.path.join(DATA, "corridors.gpkg")
COUNTRIES = ["uganda", "kenya", "rwanda", "tanzania", "south-africa", "botswana", "zimbabwe", "zambia",
             "mozambique", "namibia"]


def pbf_path(country):
    """This paper's extract, or the Uganda study's copy in ../data (not duplicated here)."""
    for d in (DATA, os.path.join(ROOT, "..", "data")):
        p = os.path.join(d, f"{country}-latest.osm.pbf")
        if os.path.exists(p):
            return p
    return None


PBFS = [p for p in map(pbf_path, COUNTRIES) if p]
PBF = PBFS[0] if PBFS else None
CHIRPS_DIR = os.path.join(DATA, "chirps")
CHIRPS_PREFIX = "chirps_region"
CHIRPS_BOX = (11.0, 41.0, -35.0, 5.0)
PROBES_GPKG = os.path.join(DATA, "probes.gpkg")
DISTRICTS = os.path.join(DATA, "ne_admin0", "ne_10m_admin_0_countries.shp")
_ISO = {"uganda": "UGA", "kenya": "KEN", "rwanda": "RWA", "tanzania": "TZA", "south-africa": "ZAF", "botswana": "BWA",
        "zimbabwe": "ZWE", "zambia": "ZMB", "mozambique": "MOZ", "namibia": "NAM"}
WORLDPOP = [f"https://data.worldpop.org/GIS/Population/Global_2015_2030/R2024B/2025/{i}/v1/100m/constrained/"
            f"{i.lower()}_pop_2025_CN_100m_R2024B_v1.tif" for i in _ISO.values()]

_arteries = json.load(open(os.path.join(DATA, "arteries.json"))) if os.path.exists(os.path.join(DATA, "arteries.json")) else []
CORRIDORS = {a["name"]: dict(label=f"{a['hub'].replace('_', ' ').title()} → {a['toward']} ({a['ref'] or 'road'}, {a['country']})",
                             short=f"{a['hub'].replace('_', ' ').title()}–{a['toward']}", ref=a["ref"] or "road",
                             bbox=tuple(a["bbox"]), start=tuple(a["start"]), end=tuple(a["end"]),
                             hub=a["hub"], region=a["region"], trade=a["trade"])
             for a in _arteries}


def _ghsl_tiles():
    """GHSL 1000 km Mollweide tiles under every artery (R = 9 - floor(y / 1000 km),
    C = floor((x + 18,041,000 m) / 1000 km) + 1)."""
    from pyproj import Transformer
    t = Transformer.from_crs(4326, "ESRI:54009", always_xy=True)
    tiles = set()
    for a in _arteries:
        x0, y0, x1, y1 = a["bbox"]
        for lon in (x0, x1, (x0 + x1) / 2):
            for lat in (y0, y1, (y0 + y1) / 2):
                x, y = t.transform(lon, lat)
                tiles.add(f"R{9 - math.floor(y / 1e6)}_C{math.floor((x + 18041000) / 1e6) + 1}")
    return sorted(tiles)


GHSL_TILES = _ghsl_tiles() if _arteries else []

# Not used here (no live traffic collection), but 02_segments.py reads them.
TOMTOM_PROBES = {}
TOMTOM_DAILY_REQUESTS = 2400
HERE_MONTHLY_REQUESTS = 25000

# Lengths: one Lambert azimuthal equal-area projection centred on the region would distort lengths
# too; instead a transverse Mercator on 29 E. Scale error stays under about 1% out to 14 E (Walvis
# Bay) and 39.7 E (Mombasa), acceptable for 500 m pieces; UTM would need five zones.
UTM = "+proj=tmerc +lat_0=0 +lon_0=29 +k=1 +x_0=500000 +y_0=10000000 +datum=WGS84 +units=m +no_defs"

# No published trip times collected yet outside Uganda.
VALIDATION = {}

# Truck counts are not available across ten countries: one wide assumption for every artery,
# used only where a script needs one (17, 19). The comparison uses per-km and per-truck measures.
TRUCKS_PER_DAY = {name: (1000, 300, 3000) for name in CORRIDORS}
