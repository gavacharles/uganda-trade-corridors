"""Fly-through of the worst stretch in each of the ten countries (weighbridge stops left aside, as
in rx13), from the region down to street level.

    python scripts/flythrough_regional.py      # figures/social/rx15_bottleneck_flythrough.mp4/.gif
"""
import os, re
import geopandas as gpd
import pyarrow.parquet as pq

from regional_common import ART, C, EAST, H, SOUTH, pieces
import flylib

SHORT = {"United Republic of Tanzania": "Tanzania"}
ORDER = ["Rwanda", "Uganda", "Kenya", "United Republic of Tanzania", "Zambia", "Zimbabwe", "Mozambique",
         "South Africa", "Botswana", "Namibia"]
HH = H.copy()
wb = HH.main_causes.map(lambda s: float(m.group(1)) if (m := re.search(r"weighbridge ([\d.]+)", s)) else 0.0)
HH["other"] = HH.truck_excess_min - wb
pick = HH.loc[HH.groupby("country").other.idxmax()].set_index("country").loc[ORDER].reset_index()
sites = [dict(lon=r.lon, lat=r.lat, kicker=f"{SHORT.get(r.country, r.country).upper()} · {r.region} Africa",
              place=r.place_name, road=f"{ART.road[r.corridor]}, km {r.km_from:.0f}–{r.km_to:.0f}",
              minutes=r.truck_excess_min, causes=r.main_causes.split("; ")[:3],
              colour=EAST if r.region == "East" else SOUTH) for r in pick.itertuples()]

P = pieces.to_crs(4326)[["corridor", "geometry", "per_km"]]
countries = gpd.read_file(os.path.join(C.DATA, "ne_admin0", "ne_10m_admin_0_countries.shp"), columns=["ADMIN"])
lakes = gpd.read_file(os.path.join(C.ROOT, "..", "data", "ne_lakes", "ne_10m_lakes.shp")).to_crs(4326)
B = pq.read_table(os.path.join(C.DATA, "buildings.parquet"),
                  columns=["latitude", "longitude", "area_in_meters"]).to_pandas().astype("float32")
flylib.fly("rx15_bottleneck_flythrough", os.path.join(C.FIGURES, "social"), P, sites, countries, lakes,
           set(ART.country), os.path.join(C.DATA, "osm_features.gpkg"), B,
           "Ten countries, ten bottlenecks", "Flying to the 2 km stretch in each country where the roadside costs "
           "a loaded truck most (weighbridge stops left aside)", (29.0, -13.5, 58.0))
