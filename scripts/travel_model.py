"""The travel-time model shared by 10_travel_time.py and the scenario, cost and reliability
scripts (16-18): assumptions with their ranges, the 500 m pieces, and minutes per piece.

For a car and a loaded truck, the speed of a piece starts at an open-road speed and is
reduced by each measured cause; fixed delays are added for point controls. There are no
congestion or queueing terms. See 10_travel_time.py for how the model is run and checked.
"""
import os
import numpy as np
import pandas as pd

import config as C

# name: (central, low, high). Speeds km/h, delays seconds.
PARAMS = {
    "car_open_single": (90, 80, 100),      # open road, single carriageway
    "car_open_dual": (100, 90, 110),
    "truck_open": (70, 60, 80),            # loaded heavy goods vehicle
    "town_limit": (50, 40, 60),            # urban speed limit applied in "town" pieces
    "side_friction_max": (0.35, 0.20, 0.50),   # largest speed loss from roadside activity
    "side_friction_b0": (300, 200, 400),   # buildings within 100 m at which that loss is reached
    "access_max": (0.15, 0.05, 0.25),      # speed loss at 10+ joining roads per piece
    "truck_grade_k": (0.25, 0.15, 0.35),   # truck speed = open / (1 + k * (grade - 1)) uphill
    "curve_threshold": (150, 120, 200),    # deg/km above which a curve cap applies
    "curve_cap_car": (60, 50, 70),
    "curve_cap_truck": (50, 40, 60),
    "signal_s": (30, 15, 45),
    "ped_crossing_s": (5, 2, 10),
    "level_crossing_s": (15, 5, 30),
    "hump_s": (8, 5, 12),
    "humps_per_town_piece": (1.0, 0.0, 2.0),   # OSM under-records humps; assumed per town piece
    "police_car_s": (10, 0, 30),           # OSM police posts on the road: possible checks
    "police_truck_s": (60, 0, 300),
    "weighbridge_truck_s": (600, 300, 1800),   # queue and weighing; cars pass
    "wet_factor": (0.90, 0.85, 0.95),      # speed multiplier on a wet day (>= 10 mm)
}
CAUSES = ["town speed limit", "roadside activity", "joining roads", "signals and crossings",
          "speed humps (assumed)", "police posts", "weighbridge", "hills (trucks)", "curves"]


P = pd.read_csv(os.path.join(C.OUTPUTS, "pieces_typed.csv")).sort_values(["corridor", "piece"])
P["length_km"] = P.groupby("corridor").km_start.shift(-1).sub(P.km_start).fillna(0.5).clip(upper=0.5)
P["place"] = P.place.where(~P.place.fillna("").str.contains("/"))  # drop malformed OSM names


def piece_minutes(p, vehicle, direction, off=(), wet=False, d=None):
    """Minutes to cross each piece. `off` lists causes switched off; `d` is a changed copy
    of the pieces (a scenario), P by default."""
    with np.errstate(all="ignore"):
        return _piece_minutes(p, vehicle, direction, off, wet, P if d is None else d)


def _piece_minutes(p, vehicle, direction, off, wet, d):
    car = vehicle == "car"
    v = np.where(d.dual, p["car_open_dual"], p["car_open_single"]) if car else np.full(len(d), p["truck_open"], float)
    if "roadside activity" not in off:
        v = v * (1 - p["side_friction_max"] * np.minimum(1, d.buildings_100m / p["side_friction_b0"]))
    if "joining roads" not in off:
        v = v * (1 - p["access_max"] * np.minimum(1, (d.junctions_major + d.junctions_minor) / 10))
    if "town speed limit" not in off:
        v = np.where(d.road_type == "town", np.minimum(v, p["town_limit"]), v)
    if "curves" not in off:
        cap = p["curve_cap_car"] if car else p["curve_cap_truck"]
        v = np.where(d.curvature_deg_per_km > p["curve_threshold"], np.minimum(v, cap), v)
    if not car and "hills (trucks)" not in off:
        g = d.grade_pct.to_numpy() * (1 if direction == "outbound" else -1)
        v = np.where(g > 1, np.minimum(v, p["truck_open"] / (1 + p["truck_grade_k"] * (g - 1))), v)
    if wet:
        v = v * p["wet_factor"]
    t = d.length_km / v * 60
    if "signals and crossings" not in off:
        t = t + (d.signals * p["signal_s"] + d.ped_crossings * p["ped_crossing_s"]
                 + d.level_crossings * p["level_crossing_s"] + d.humps * p["hump_s"]) / 60
    if "speed humps (assumed)" not in off:
        humps = np.where(d.road_type == "town", p["humps_per_town_piece"], 0)
        t = t + humps * p["hump_s"] * (1 if car else 1.5) / 60
    if "police posts" not in off:
        t = t + d.police_posts * (p["police_car_s"] if car else p["police_truck_s"]) / 60
    if "weighbridge" not in off and not car:  # weighbridges found by name in OSM (05_osm_features.py)
        t = t + np.minimum(d.weighbridges, 1) * p["weighbridge_truck_s"] / 60
    return np.asarray(t)


def draw(rng):
    """One Monte Carlo draw: every parameter uniform within its range."""
    return {k: rng.uniform(lo, hi) for k, (_, lo, hi) in PARAMS.items()}


CENTRAL = {k: v[0] for k, v in PARAMS.items()}
