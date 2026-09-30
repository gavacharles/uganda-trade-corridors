"""Settings for the regional paper: the same pipeline as the Uganda study (../scripts), run on
the corridors beyond Uganda's borders. run.py puts this folder first on the import path, so
every shared script reads this file as `config`.

Corridors (km 0 at the Ugandan border, so each continues the Uganda study's outbound direction):
  malaba_nairobi   Kenya A8, Malaba border -> Eldoret -> Nakuru -> Nairobi
  nairobi_mombasa  Kenya A8, Nairobi -> Mombasa (port)
  gatuna_kigali    Rwanda NR3, Gatuna border -> Kigali
"""
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
OUTPUTS = os.path.join(ROOT, "outputs")
FIGURES = os.path.join(ROOT, "figures")
for _d in (DATA, OUTPUTS, FIGURES):
    os.makedirs(_d, exist_ok=True)
CORRIDORS_GPKG = os.path.join(DATA, "corridors.gpkg")
PBF = os.path.join(DATA, "kenya-latest.osm.pbf")
PBFS = [PBF, os.path.join(DATA, "rwanda-latest.osm.pbf")]   # Geofabrik extracts
CHIRPS_DIR = os.path.join(DATA, "chirps")
CHIRPS_PREFIX = "chirps_region"
CHIRPS_BOX = (29.6, 40.0, -4.4, 1.2)
PROBES_GPKG = os.path.join(DATA, "probes.gpkg")
GHSL_TILES = ["R9_C22", "R10_C22", "R10_C23"]
WORLDPOP = ["https://data.worldpop.org/GIS/Population/Global_2015_2030/R2024B/2025/KEN/v1/100m/constrained/"
            "ken_pop_2025_CN_100m_R2024B_v1.tif",
            "https://data.worldpop.org/GIS/Population/Global_2015_2030/R2024B/2025/RWA/v1/100m/constrained/"
            "rwa_pop_2025_CN_100m_R2024B_v1.tif"]

CORRIDORS = {
    "malaba_nairobi": dict(label="Malaba → Eldoret → Nakuru → Nairobi, Kenya (A8)", short="Malaba–Nairobi", ref="A8",
                           bbox=(34.20, -1.35, 36.85, 0.75), start=(34.2706, 0.6360), end=(36.8191, -1.2904)),
    "nairobi_mombasa": dict(label="Nairobi → Mombasa, Kenya (A8)", short="Nairobi–Mombasa", ref="A8",
                            bbox=(36.78, -4.10, 39.75, -1.25), start=(36.8191, -1.2904), end=(39.6726, -4.0584)),
    "gatuna_kigali": dict(label="Gatuna → Kigali, Rwanda (NR3)", short="Gatuna–Kigali", ref="NR3",
                          bbox=(29.95, -1.97, 30.20, -1.38), start=(30.0117, -1.4248), end=(30.0443, -1.9420)),
}

# Not used here (no live traffic collection), but 02_segments.py reads them.
TOMTOM_PROBES = {}
TOMTOM_DAILY_REQUESTS = 2400
HERE_MONTHLY_REQUESTS = 25000

# One transverse Mercator for the whole region (central meridian 35 E). Length error stays
# under about 0.4% at Kigali (30 E) and Mombasa (39.7 E); UTM would need two zones.
UTM = "+proj=tmerc +lat_0=0 +lon_0=35 +k=0.9996 +x_0=500000 +y_0=10000000 +datum=WGS84 +units=m +no_defs"

# Published trip times to check the model against. None collected yet: add them in the same
# form as ../scripts/config.py before reading anything into the validation.
VALIDATION = {}

# Heavy goods vehicles a day, both directions: (central, low, high). ASSUMPTIONS, not counts:
# replace with KeNHA and RTDA traffic counts or Northern Corridor Transport Observatory data.
TRUCKS_PER_DAY = {
    "malaba_nairobi": (2000, 1200, 3500),
    "nairobi_mombasa": (4000, 2500, 6000),
    "gatuna_kigali": (500, 250, 1000),
}

# Towns labelled on the strip maps (20_story_figures.py), lon/lat
TOWNS = {"Malaba": (34.2800, 0.6350), "Bungoma": (34.5600, 0.5630), "Webuye": (34.7700, 0.6070),
         "Eldoret": (35.2700, 0.5140), "Nakuru": (36.0700, -0.3030), "Naivasha": (36.4300, -0.7170),
         "Nairobi": (36.8200, -1.2900), "Athi River": (36.9800, -1.4560), "Sultan Hamud": (37.3700, -2.0200),
         "Emali": (37.4700, -2.0800), "Kibwezi": (37.9600, -2.4100), "Mtito Andei": (38.1700, -2.6900),
         "Voi": (38.5600, -3.4000), "Mariakani": (39.4700, -3.8600), "Mombasa": (39.6600, -4.0500),
         "Gatuna": (30.0100, -1.4300), "Gicumbi": (30.0700, -1.5800), "Kigali": (30.0600, -1.9500)}
