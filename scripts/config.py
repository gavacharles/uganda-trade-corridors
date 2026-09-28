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
