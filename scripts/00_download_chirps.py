"""Download CHIRPS v2.0 daily rainfall (0.25 deg), clip to the study area (config.CHIRPS_BOX),
save one file per year.

Global yearly files (~83 MB) are streamed to a temp file, clipped, and deleted,
so disk use stays small. Re-running skips years already downloaded.
"""
import os, sys, subprocess, tempfile
import xarray as xr

import config as C

BASE = "https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_daily/netcdf/p25"
OUT = C.CHIRPS_DIR
LON = slice(C.CHIRPS_BOX[0], C.CHIRPS_BOX[1])
LAT = slice(C.CHIRPS_BOX[2], C.CHIRPS_BOX[3])
os.makedirs(OUT, exist_ok=True)

years = range(int(sys.argv[1]), int(sys.argv[2]) + 1)
for y in years:
    out = os.path.join(OUT, f"{C.CHIRPS_PREFIX}_{y}.nc")
    if os.path.exists(out):
        continue
    with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as tmp:
        path = tmp.name
    try:
        subprocess.run(["curl", "-sSf", "--retry", "3", "-o", path,
                        f"{BASE}/chirps-v2.0.{y}.days_p25.nc"], check=True)
        with xr.open_dataset(path) as ds:
            ds.sel(longitude=LON, latitude=LAT).load().to_netcdf(out)
        print(y, "ok", flush=True)
    finally:
        os.remove(path)
