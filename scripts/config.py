"""Shared settings for the corridors study: paths, corridor ends, probe spacing and
the request budget for each traffic source.

API keys are read from corridors/.env (never committed or published):
    TOMTOM_API_KEY=...
    HERE_API_KEY=...
"""
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
OUTPUTS = os.path.join(ROOT, "outputs")
FIGURES = os.path.join(ROOT, "figures")
CORRIDORS_GPKG = os.path.join(DATA, "corridors.gpkg")
# Base inputs, fetched by 00_download_base.sh
PBF = os.path.join(DATA, "uganda-latest.osm.pbf")               # Geofabrik OSM extract
DISTRICTS = os.path.join(DATA, "uga_districts.geojson")         # HDX COD-AB admin 2
CHIRPS_DIR = os.path.join(DATA, "chirps_uganda")                # CHIRPS daily, clipped to Uganda
PROBES_GPKG = os.path.join(DATA, "probes.gpkg")
PBFS = [PBF]                          # every OSM extract the corridors run through
CHIRPS_PREFIX = "chirps_uganda"       # CHIRPS files are <CHIRPS_DIR>/<prefix>_<year>.nc
CHIRPS_BOX = (29.4, 35.1, -1.6, 4.4)  # lon min, lon max, lat min, lat max
GHSL_TILES = ["R9_C22", "R10_C22"]    # GHSL 1000 km Mollweide tiles covering the corridors
WORLDPOP = ["https://data.worldpop.org/GIS/Population/Global_2015_2030/R2024B/2025/UGA/v1/100m/constrained/"
            "uga_pop_2025_CN_100m_R2024B_v1.tif"]  # 2025 constrained population, 100 m
RAW = os.path.join(DATA, "raw")          # every API response, gzipped, as received
ARCHIVE = os.path.join(DATA, "archive")  # parsed rows, one CSV per source per month
LOGS = os.path.join(DATA, "logs")

# The corridors. `ref` is the OSM route number; `bbox` (lon/lat) cuts the route where
# the corridor ends; start and end (lon, lat) are snapped to the route. The centreline
# is the shortest path along the route from start to end; "inbound" is end -> start,
# i.e. towards Kampala. Every script loops over this dict in this order.
CORRIDORS = {
    "kampala_malaba": dict(label="Kampala → Jinja → Malaba, Kenya border (A1)", short="Malaba", ref="A1",
                           bbox=(32.50, 0.20, 34.32, 0.75), start=(32.5900, 0.3150), end=(34.2790, 0.6380)),
    "kampala_elegu": dict(label="Kampala → Gulu → Elegu, South Sudan border (A6)", short="Elegu", ref="A6",
                          bbox=(31.95, 0.30, 32.60, 3.62), start=(32.5700, 0.3500), end=(32.0800, 3.5750)),
    "kampala_katuna": dict(label="Kampala → Masaka → Katuna, Rwanda border (A2)", short="Katuna", ref="A2",
                           bbox=(29.90, -1.50, 32.62, 0.35), start=(32.5650, 0.3000), end=(30.0000, -1.4200)),
    "kampala_hoima": dict(label="Kampala → Hoima (A9)", short="Hoima", ref="A9",
                          bbox=(31.30, 0.28, 32.60, 1.48), start=(32.5550, 0.3250), end=(31.3520, 1.4320)),
}

# TomTom probe points: spacing along the centreline (km) and which directions.
# Dual carriageway (Jinja) is probed both ways; on single carriageway TomTom returns
# the segment nearest the point, so one set of points covers the road.
TOMTOM_PROBES = {
    "kampala_jinja": dict(spacing_km=3.0, directions=("outbound", "inbound")),
    "kampala_gulu": dict(spacing_km=10.0, directions=("outbound",)),
}

# Request budgets. Each TomTom probe is one request; each HERE corridor query is one
# request. Set these to the limits of your own plans. poll.py spaces its polls so a
# full day stays inside the daily budget.
TOMTOM_DAILY_REQUESTS = int(os.environ.get("TOMTOM_DAILY_REQUESTS", 2400))
HERE_MONTHLY_REQUESTS = int(os.environ.get("HERE_MONTHLY_REQUESTS", 25000))

# HERE results are kept only if they lie within this distance of the centreline.
HERE_MATCH_M = 60
# Simplification tolerance (degrees) for the corridor polyline sent to HERE.
HERE_SIMPLIFY_DEG = 0.0002  # about 20 m, well inside the query radius
HERE_CORRIDOR_RADIUS_M = 50

# Published trip times to check the model against (10_travel_time.py), per (corridor, vehicle):
# (label, low minutes, high minutes, kind, compare up to (lon, lat) or None for the whole corridor)
VALIDATION = {
    ("kampala_malaba", "car"): [("Rome2rio routing estimate, Kampala–Njeru", 66, 66, "estimate", (33.17, 0.44)),
                                ("Reported typical trip Kampala–Jinja, press and project sources", 120, 180,
                                 "observed", (33.204, 0.439))],
    ("kampala_elegu", "car"): [("Rome2rio routing estimate, Kampala–Gulu", 286, 286, "estimate", (32.299, 2.774)),
                               ("Scheduled buses Kampala–Gulu incl. stops (Bookaway, Friends Coach)", 300, 495,
                                "observed", (32.299, 2.774))],
    ("kampala_katuna", "car"): [("Rome2rio routing estimate, Kampala–Kabale", 345, 345, "estimate", (29.9856, -1.2486)),
                                ("Scheduled bus, Kampala–Kabale (Rome2rio)", 480, 480, "observed", (29.9856, -1.2486))],
    ("kampala_hoima", "car"): [("Rome2rio routing estimate", 172, 172, "estimate", None),
                               ("Scheduled bus (Rome2rio)", 206, 206, "observed", None)],
}

# Heavy goods vehicles a day, both directions, averaged along each corridor: (central, low, high).
# Used by 17_costs.py and 19_safety.py. Only the Malaba road has a sourced anchor: 8.684 Mt of
# cargo between Malaba and Kampala in 2017, ~4% by rail (Jinja-Kampala-Mpigi Corridor Physical
# Development Plan, 2023, ch. 6), i.e. ~900 loaded trucks a day plus empties. The others are
# assumptions with wide ranges, to be replaced with UNRA traffic counts.
TRUCKS_PER_DAY = {
    "kampala_malaba": (1500, 1000, 2500),
    "kampala_elegu": (600, 300, 1200),
    "kampala_katuna": (800, 400, 1500),
    "kampala_hoima": (400, 200, 900),
}

UTM = 32636  # metres, for lengths and distances


def load_env():
    """Put KEY=value lines from corridors/.env into os.environ (without overriding)."""
    path = os.path.join(ROOT, ".env")
    if not os.path.exists(path):
        return
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
