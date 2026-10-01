"""Population for the regional study: GHSL GHS-POP R2023A, epoch 2025, 100 m Mollweide tiles.

The Uganda study uses WorldPop 2025 (constrained, one raster per country). For eleven hubs in
ten countries, one consistent global product is used instead, from the same JRC server and tile
grid as the built-up surface (09_growth.py): GHS-POP 2025 is GHSL's projection of residential
population from its 2020 baseline. Tiles are those under every artery (config.GHSL_TILES).

    python scripts/download_ghs_pop.py      # writes data/ghs_pop/GHS_POP_E2025_..._<tile>.tif

Source: Schiavina, Freire, Carioli, MacManus (2023), GHS-POP R2023A, European Commission JRC.
"""
import io, os, sys, zipfile
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C  # noqa: E402

URL = ("https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_POP_GLOBE_R2023A/"
       "GHS_POP_E2025_GLOBE_R2023A_54009_100/V1-0/tiles/GHS_POP_E2025_GLOBE_R2023A_54009_100_V1_0_{t}.zip")
os.makedirs(C.POP_DIR, exist_ok=True)
for t in C.GHSL_TILES:
    out = os.path.join(C.POP_DIR, f"GHS_POP_E2025_GLOBE_R2023A_54009_100_V1_0_{t}.tif")
    if os.path.exists(out):
        continue
    for attempt in range(4):   # the JRC server sometimes stalls
        try:
            r = requests.get(URL.format(t=t), timeout=600)
            r.raise_for_status()
            z = zipfile.ZipFile(io.BytesIO(r.content))
            break
        except (requests.exceptions.RequestException, zipfile.BadZipFile):
            if attempt == 3:
                raise
            print("retrying", t, flush=True)
    name = [n for n in z.namelist() if n.endswith(".tif")][0]
    with open(out + ".part", "wb") as f:
        f.write(z.read(name))
    os.replace(out + ".part", out)
    print("downloaded", t, flush=True)
print(f"{len(C.GHSL_TILES)} GHS-POP tiles in {C.POP_DIR}")
