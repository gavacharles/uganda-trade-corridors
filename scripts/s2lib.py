"""Sentinel-2 L2A access shared by the truck scripts (14_trucks.py, 21_truck_candidates.py):
scene search on Earth Search (AWS open data), windowed reads of one band, and conversion to
reflectance.
"""
import numpy as np
import rasterio
import rasterio.features
import requests
from rasterio.warp import transform_geom
from rasterio.windows import from_bounds

STAC = "https://earth-search.aws.element84.com/v1/search"
CLOUDY = {3, 8, 9, 10}  # SCL: cloud shadow, medium and high cloud, cirrus
ENV = dict(AWS_NO_SIGN_REQUEST="YES", GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_MAX_RETRY="4",
           GDAL_HTTP_RETRY_DELAY="2", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif")


def search(bbox):
    """All clear scenes touching a lon/lat bbox (a long line geometry can be rejected)."""
    body = {"collections": ["sentinel-2-l2a"], "bbox": list(bbox), "limit": 200,
            "datetime": "2023-01-01T00:00:00Z/2025-12-31T23:59:59Z", "query": {"eo:cloud_cover": {"lt": 10}}}
    feats, r = [], requests.post(STAC, json=body, timeout=120).json()
    while True:
        if "features" not in r:
            raise RuntimeError(f"STAC search failed: {str(r)[:300]}")
        feats += r["features"]
        nxt = [l for l in r.get("links", []) if l.get("rel") == "next"]
        if not nxt:
            return feats
        l = nxt[0]
        r = (requests.post(l["href"], json=l.get("body", body), timeout=120) if l.get("method", "GET") == "POST"
             else requests.get(l["href"], timeout=120)).json()


def reflect(a, item):
    """L2A digital numbers to reflectance. Baseline >= 04.00 is specified with a -1000 offset,
    but the Earth Search COGs checked here (e.g. S2B_36NVF_20250227, baseline 05.11) read
    about 400 over vegetation, which is only plausible without it. So the offset is applied
    only when the data show it: the darkest 5% of pixels above 1000."""
    off = 1000 if np.percentile(a[a > 0], 5) > 1000 else 0
    return (a.astype(float) - off) / 10000


def read(href, geom_ll, epsg, out_shape=None):
    with rasterio.open(href) as src:
        g = transform_geom("EPSG:4326", src.crs, geom_ll)
        x0, y0, x1, y1 = rasterio.features.bounds(g)
        w = from_bounds(x0 - 60, y0 - 60, x1 + 60, y1 + 60, transform=src.transform).round_offsets().round_lengths()
        a = src.read(1, window=w, out_shape=out_shape, boundless=True, fill_value=0)
        tf = src.window_transform(w)
        if out_shape is not None:
            tf = tf * tf.scale(w.width / out_shape[1], w.height / out_shape[0])
        return a, tf, src.crs

