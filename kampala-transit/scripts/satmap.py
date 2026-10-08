"""Satellite basemaps for matplotlib maps: Esri World Imagery tiles, cached on disk.

    from satmap import satellite
    satellite(ax, (lon0, lon1, lat0, lat1), zoom=None, alpha=1.0, dim=0.0)

Tiles are Web Mercator; near the equator (Kampala, 0.3 N) Mercator y is linear in latitude to well
under a pixel over these extents, so the mosaic is drawn with lon/lat extents on the study's axes.
Zoom is chosen from the axes' width in pixels unless given. Tiles are cached in
kampala-transit/data/tiles/ (not committed).
Imagery © Esri, Maxar, Earthstar Geographics (credit on every figure that uses it).
"""
import io, math, os, time
import numpy as np
import requests
from PIL import Image

CACHE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "tiles"))
URL = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
CREDIT = "Imagery © Esri, Maxar, Earthstar Geographics"
S = requests.Session()
S.headers["User-Agent"] = "uganda-trade-corridors research (github.com/gavacharles/uganda-trade-corridors)"


def _tile_xy(lon, lat, z):
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def _lonlat(x, y, z):
    n = 2 ** z
    return x / n * 360 - 180, math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))


def _tile(z, x, y):
    p = os.path.join(CACHE, str(z), str(x), f"{y}.jpg")
    if not os.path.exists(p):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        for k in range(4):
            try:
                r = S.get(URL.format(z=z, x=x, y=y), timeout=30)
                if r.status_code == 200 and len(r.content) > 500:
                    open(p, "wb").write(r.content)
                    break
            except requests.RequestException:
                pass
            time.sleep(1 + k)
        else:
            return Image.new("RGB", (256, 256), (200, 200, 200))
    return Image.open(p).convert("RGB")


def mosaic(ext, z):
    lon0, lon1, lat0, lat1 = ext
    x0, y0 = _tile_xy(lon0, lat1, z)
    x1, y1 = _tile_xy(lon1, lat0, z)
    tx0, ty0, tx1, ty1 = int(x0), int(y0), int(x1), int(y1)
    img = Image.new("RGB", ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256))
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            img.paste(_tile(z, tx, ty), ((tx - tx0) * 256, (ty - ty0) * 256))
    w, n = _lonlat(tx0, ty0, z)
    e, s = _lonlat(tx1 + 1, ty1 + 1, z)
    return img, (w, e, s, n)


def satellite(ax, ext, zoom=None, alpha=1.0, dim=0.0, max_zoom=18):
    """Draw imagery under everything else on ax (zorder 0). dim: 0-1, fade towards white for legibility."""
    if zoom is None:
        ax.figure.canvas.draw_idle()
        bbox = ax.get_window_extent()
        px = max(bbox.width, 300) * 1.4
        zoom = int(round(math.log2(px * 360 / (256 * (ext[1] - ext[0])))))
    zoom = int(min(max(zoom, 8), max_zoom))
    img, bounds = mosaic(ext, zoom)
    a = np.asarray(img).astype("float32") / 255
    if dim:
        a = a * (1 - dim) + dim
    ax.imshow(a, extent=bounds, origin="upper", zorder=0, alpha=alpha, interpolation="bilinear")
    ax.set_xlim(ext[0], ext[1])
    ax.set_ylim(ext[2], ext[3])
    return zoom
