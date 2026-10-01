"""Shared data and styling for the regional figure scripts (figures_by_hub.py, closeups.py).

Loads the arteries with readable names, the 500 m pieces with their delay, and the worst 2 km
stretches placed on the map; holds the palette and the axis style.
"""
import json, os, sys
import numpy as np
import pandas as pd
import geopandas as gpd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "..", "scripts")]
import config as C  # noqa: E402

INK, INK2, SURF, GRID = "#1d2321", "#5d6764", "#fcfcfb", "#e6e4de"
EAST, SOUTH = "#c4532d", "#3d7f8f"
TYPE_COL = {"open road": "#cfe0d6", "roadside settlement": "#e8c77e", "town": "#c4532d"}
CAUSE_COL = {"roadside activity": "#c4532d", "hills (trucks)": "#8a6b4e", "weighbridge": "#17252a",
             "speed humps (assumed)": "#d9a441", "police posts": "#4e7c8a", "joining roads": "#3a7d5c",
             "signals and crossings": "#9fb3b0", "town speed limit": "#e89a7a", "curves": "#c9c2b8"}
HUB_NAME = {"dar_es_salaam": "Dar es Salaam"}
O = lambda f: pd.read_csv(os.path.join(C.OUTPUTS, f))  # noqa: E731

ART = pd.DataFrame(json.load(open(os.path.join(C.DATA, "arteries.json"))))
ART["hub_name"] = ART.hub.map(lambda h: HUB_NAME.get(h, h.replace("_", " ").title()))
ART = ART.set_index("name")
REG = ART.groupby("hub").region.first()

pieces = gpd.read_file(os.path.join(C.DATA, "pieces.gpkg"))
pieces = pieces.merge(O("travel_time_pieces.csv")[["corridor", "piece", "truck_excess_min"]],
                      on=["corridor", "piece"], how="left")
pieces["length_km"] = pieces.to_crs(C.UTM).length / 1000
pieces["per_km"] = pieces.truck_excess_min / pieces.length_km.clip(lower=0.05)
KM = pieces.groupby("corridor").length_km.sum()

PLACES = gpd.read_file(os.path.join(C.DATA, "osm_features.gpkg"), layer="points", where="kind = 'place'")
PLACES = PLACES[PLACES.name.notna() & ~PLACES.name.str.contains("/", na=False)].to_crs(C.UTM)


def nearest_place(lon, lat, near_km=5, max_km=20):
    pt = gpd.GeoSeries(gpd.points_from_xy([lon], [lat]), crs=4326).to_crs(C.UTM).iloc[0]
    d = PLACES.distance(pt)
    if not len(d) or d.min() > max_km * 1000:
        return None
    return PLACES.name[d.idxmin()] if d.min() < near_km * 1000 else f"near {PLACES.name[d.idxmin()]}"


def toward_name(a):
    """Discovery names an artery by the town at its end, or by its length when none is near."""
    if not str(a.toward).endswith(" km"):
        return a.toward
    n = nearest_place(a.end[0], a.end[1], max_km=60)
    return n.replace("near ", "towards ") if n else a.toward


ART["toward"] = [toward_name(a) for a in ART.itertuples()]
ART["road"] = ART.apply(lambda a: f"{a.hub_name} → {a.toward}" + (f" ({a.ref})" if a.ref else ""), axis=1)
ART["short"] = ART.apply(lambda a: f"→ {a.toward}" + (f" ({a.ref})" if a.ref else ""), axis=1)

# The worst 2 km stretches (10_travel_time.py), placed at their midpoint
H = O("hotspots.csv")
loc = []
for c, k in zip(H.corridor, (H.km_from + H.km_to) / 2):
    d = pieces[pieces.corridor == c]
    r = d.iloc[(d.km_mid - k).abs().argmin()]
    loc.append((r.lon, r.lat))
H["lon"], H["lat"] = zip(*loc)
H["hub"], H["region"], H["country"] = (H.corridor.map(ART[k]) for k in ("hub", "region", "country"))
H["lead"] = H.main_causes.str.split(";").str[0].str.rsplit(" ", n=1).str[0]
LEAD_WORD = {"weighbridge": "weighbridge", "police posts": "police post", "signals and crossings": "signals",
             "speed humps (assumed)": "humps", "roadside activity": "roadside", "hills (trucks)": "hill"}
H["place_name"] = [p if isinstance(p, str) else (nearest_place(x, y) or "unnamed place")
                   for p, x, y in zip(H.place, H.lon, H.lat)]
H["label"] = [f"{p} ({LEAD_WORD.get(l, l)})" for p, l in zip(H.place_name, H.lead)]


def distinct(h, n, min_km=4):
    """The n worst stretches, skipping any within min_km of one already chosen (overlapping roads)."""
    keep = []
    for r in h.sort_values("truck_excess_min", ascending=False).itertuples():
        if all(np.hypot((r.lon - k.lon) * 111 * np.cos(np.radians(r.lat)), (r.lat - k.lat) * 111) > min_km
               for k in keep):
            keep.append(r)
        if len(keep) == n:
            break
    return pd.DataFrame(keep)


def style(ax, grid="x"):
    ax.set_facecolor(SURF)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    if grid:
        ax.grid(axis=grid, color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)
    ax.tick_params(length=0, labelsize=9.5)
    ax.tick_params(axis="x", colors=INK2)


def save(fig, name, sub=""):
    import matplotlib.pyplot as plt
    out = os.path.join(C.FIGURES, sub)
    os.makedirs(out, exist_ok=True)
    fig.savefig(os.path.join(out, name), dpi=150, facecolor=SURF, bbox_inches="tight")
    plt.close(fig)
    print("wrote", os.path.join(sub, name), flush=True)
