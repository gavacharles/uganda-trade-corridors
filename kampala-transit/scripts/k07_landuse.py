"""Land-use patterns of Greater Kampala in 250 m cells, from building footprints and OpenStreetMap.

    python kampala-transit/scripts/k07_landuse.py      (after k03_buildings.py)

Per cell: buildings per hectare, median footprint, share of the ground built over (Open Buildings v3),
residents (WorldPop 2025), and the share of the cell under OSM commercial/retail, industrial,
institutional (schools, hospitals, universities), wetland/water and farm/forest polygons.
Classes, in order of precedence (transparent rules, thresholds in THRESH):
  wetland / water          OSM wetland or water over 40% of the cell
  commercial / industrial  OSM commercial, retail or industrial over 30%, or large buildings (median
                           footprint >= 200 m2) covering >= 20% of the ground
  institutional            OSM schools, hospitals, universities over 30%
  dense small-plot         >= 35 buildings/ha, median footprint < 70 m2: the pattern of unplanned,
                           informal settlement (not a tenure classification)
  planned / larger-plot    >= 8 buildings/ha otherwise
  peri-urban               2-8 buildings/ha
  rural / open             < 2 buildings/ha
Writes kampala-transit/outputs/landuse_cells.parquet (and .tif of the class), figures/k07_landuse.png.
"""
import os, sys
import numpy as np
import pandas as pd
import geopandas as gpd
import pyogrio
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_origin
from rasterio.warp import reproject, Resampling

HERE = os.path.dirname(os.path.abspath(__file__))
KT = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(KT, ".."))
BOX = (32.35, 0.02, 32.90, 0.55)
CELL = 0.00225                       # 250 m
SUB = 5                              # OSM polygons rasterised at 50 m, then averaged
THRESH = dict(water=0.4, comm=0.3, big_med=200, big_cov=0.2, inst=0.3, dense_n=35, dense_med=70, planned_n=8,
              peri_n=2)
CLASSES = ["wetland / water", "commercial / industrial", "institutional", "dense small-plot", "planned / larger-plot",
           "peri-urban", "rural / open"]
COL = ["#7fb3d5", "#7d3c98", "#2e86c1", "#c0392b", "#e59866", "#f4d03f", "#a9cce3"]
COL = dict(zip(CLASSES, ["#5dade2", "#8e44ad", "#1f618d", "#c0392b", "#f0b27a", "#f7dc6f", "#d5e8d4"]))

W_, H_ = int(round((BOX[2] - BOX[0]) / CELL)), int(round((BOX[3] - BOX[1]) / CELL))
T = from_origin(BOX[0], BOX[3], CELL, CELL)
print(f"{W_} x {H_} cells", flush=True)

# ---------------------------------------------------------------- footprints
B = pd.read_parquet(os.path.join(KT, "data", "buildings_pts.parquet"))
B = B[B.confidence >= 0.70]
c = ((B.longitude - BOX[0]) / CELL).astype(int).clip(0, W_ - 1)
r = ((BOX[3] - B.latitude) / CELL).astype(int).clip(0, H_ - 1)
B = B.assign(cell=r * W_ + c)
g = B.groupby("cell").area_in_meters
cells = pd.DataFrame({"n": g.size(), "med_m2": g.median(), "built_m2": g.sum(),
                      "small_share": B.assign(s=B.area_in_meters < 40).groupby("cell").s.mean()})
cells = cells.reindex(np.arange(W_ * H_)).fillna({"n": 0, "built_m2": 0})
area_ha = (CELL * 111.32e3) ** 2 / 1e4
cells["bld_ha"] = cells.n / area_ha
cells["coverage"] = cells.built_m2 / (area_ha * 1e4)

# ---------------------------------------------------------------- residents
with rasterio.open(os.path.join(ROOT, "data", "worldpop", "uga_pop_2025_CN_100m_R2024B_v1.tif")) as src:
    pop = np.zeros((H_, W_), "float64")
    p = src.read(1, window=rasterio.windows.from_bounds(*BOX, transform=src.transform).round_offsets().round_lengths())
    wt = src.window_transform(rasterio.windows.from_bounds(*BOX, transform=src.transform).round_offsets().round_lengths())
    p = np.where(p < 0, 0, p)
    reproject(p, pop, src_transform=wt, src_crs=src.crs, dst_transform=T, dst_crs=src.crs, resampling=Resampling.sum)
cells["pop"] = pop.ravel()

# ---------------------------------------------------------------- OSM land use
osm = pyogrio.read_dataframe(os.path.join(ROOT, "data", "uganda-latest.osm.pbf"), layer="multipolygons", bbox=BOX,
                             columns=["landuse", "amenity", "natural", "leisure"],
                             where="landuse IS NOT NULL OR amenity IS NOT NULL OR natural IS NOT NULL")
groups = {
    "water": (osm.natural.isin(["wetland", "water"])) | osm.landuse.isin(["reservoir", "basin"]),
    "comm": osm.landuse.isin(["commercial", "retail", "industrial"]) | osm.amenity.isin(["marketplace"]),
    "inst": osm.amenity.isin(["school", "university", "college", "hospital", "clinic", "prison"]) |
            osm.landuse.isin(["education", "institutional", "military"]),
    "green": osm.landuse.isin(["farmland", "forest", "orchard", "meadow", "grass", "farmyard", "greenfield"]) |
             osm.natural.isin(["wood", "grassland", "scrub", "heath"]),
}
T2 = from_origin(BOX[0], BOX[3], CELL / SUB, CELL / SUB)
for k, m in groups.items():
    geoms = [gg for gg in osm.geometry[m] if gg is not None and not gg.is_empty]
    if not geoms:
        cells[k] = 0.0
        continue
    a = rasterize(((gg, 1) for gg in geoms), out_shape=(H_ * SUB, W_ * SUB), transform=T2, fill=0, dtype="uint8")
    cells[k] = a.reshape(H_, SUB, W_, SUB).mean(axis=(1, 3)).ravel()
    print(k, int(m.sum()), "polygons", flush=True)

t = THRESH
cond = [cells.water > t["water"],
        (cells.comm > t["comm"]) | ((cells.med_m2 >= t["big_med"]) & (cells.coverage >= t["big_cov"])),
        cells.inst > t["inst"],
        (cells.bld_ha >= t["dense_n"]) & (cells.med_m2 < t["dense_med"]),
        cells.bld_ha >= t["planned_n"],
        cells.bld_ha >= t["peri_n"]]
cells["cls"] = np.select(cond, CLASSES[:-1], CLASSES[-1])
cells["code"] = cells.cls.map({k: i for i, k in enumerate(CLASSES)}).astype("uint8")
rr, cc = np.divmod(np.arange(W_ * H_), W_)
cells["lon"] = BOX[0] + (cc + 0.5) * CELL
cells["lat"] = BOX[3] - (rr + 0.5) * CELL
cells.reset_index(drop=True).to_parquet(os.path.join(KT, "outputs", "landuse_cells.parquet"))
with rasterio.open(os.path.join(KT, "outputs", "landuse.tif"), "w", driver="GTiff", width=W_, height=H_, count=1,
                   dtype="uint8", crs="EPSG:4326", transform=T, compress="deflate") as dst:
    dst.write(cells.code.to_numpy().reshape(H_, W_), 1)
summ = cells.groupby("cls").agg(cells=("n", "size"), residents=("pop", "sum"), buildings=("n", "sum"))
summ["residents_share"] = summ.residents / summ.residents.sum()
summ.reindex(CLASSES).to_csv(os.path.join(KT, "outputs", "landuse_summary.csv"))
print(summ.reindex(CLASSES).round(3).to_string())
