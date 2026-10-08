"""Google satellite embeddings (AlphaEarth Foundations) averaged to the k07 grid of 250 m cells.

    python kampala-transit/scripts/k08a_embeddings.py

GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL: a 64-dimensional embedding for every 10 m pixel, learned by a
geospatial foundation model from optical, radar, elevation and climate time series of one year.
2022 is used, matching the imagery of the building footprints (2020-22). Each band is averaged over
the 625 pixels of a cell (reduceResolution) and downloaded in two halves.
Writes kampala-transit/data/embeddings_2022.tif (64 bands, k07 grid).
Needs the Earth Engine project in .env (EE_PROJECT).
"""
import io, os, sys, warnings
import numpy as np
import requests
import rasterio

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import config as C  # noqa: E402

C.load_env()
import ee  # noqa: E402

ee.Initialize(project=os.environ["EE_PROJECT"])
BOX = (32.35, 0.02, 32.90, 0.55)
CELL = 0.00225
W_, H_ = int(round((BOX[2] - BOX[0]) / CELL)), int(round((BOX[3] - BOX[1]) / CELL))
col = (ee.ImageCollection("GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL")
       .filterDate("2022-01-01", "2023-01-01").filterBounds(ee.Geometry.Rectangle(list(BOX))))
proj10 = col.first().select(0).projection()
img = col.mosaic().setDefaultProjection(proj10)
# averaged over the 10 m pixels of each cell; the output grid is given explicitly to computePixels
# (getDownloadURL with a reprojected image returned scrambled values)
cellmean = img.reduceResolution(ee.Reducer.mean(), maxPixels=1024)
bands = img.bandNames().getInfo()
out = np.zeros((len(bands), H_, W_), "float32")
BLK = 60   # cells per side of a request block (Earth Engine's memory limit)
for k in range(0, len(bands), 16):
    part = bands[k:k + 16]
    for r0 in range(0, H_, BLK):
        for c0 in range(0, W_, BLK):
            h, w = min(BLK, H_ - r0), min(BLK, W_ - c0)
            grid = {"dimensions": {"width": w, "height": h}, "crsCode": "EPSG:4326",
                    "affineTransform": {"scaleX": CELL, "shearX": 0, "translateX": BOX[0] + c0 * CELL, "shearY": 0,
                                        "scaleY": -CELL, "translateY": BOX[3] - r0 * CELL}}
            arr = ee.data.computePixels({"expression": cellmean.select(part), "fileFormat": "NUMPY_NDARRAY",
                                         "grid": grid})
            for j, b in enumerate(part):
                out[k + j, r0:r0 + h, c0:c0 + w] = np.asarray(arr[b], dtype="float32")
    print(f"bands {k + 1}-{k + len(part)} done", flush=True)
os.makedirs(os.path.join(ROOT, "kampala-transit", "data"), exist_ok=True)
with rasterio.open(os.path.join(ROOT, "kampala-transit", "data", "embeddings_2022.tif"), "w", driver="GTiff",
                   width=W_, height=H_, count=len(bands), dtype="float32", crs="EPSG:4326",
                   transform=rasterio.transform.from_origin(BOX[0], BOX[3], CELL, CELL), compress="deflate") as dst:
    dst.write(out)
print("wrote embeddings_2022.tif", out.shape, "nonzero cells", int((np.abs(out).sum(axis=0) > 0).sum()))
