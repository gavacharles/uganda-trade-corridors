"""How much has the roadside been built up, 2000-2020?

GHSL GHS-BUILT-S R2023A (built-up surface, m2 per 100 m cell, Mollweide tiles R9_C22
and R10_C22, which together cover all corridors) for 2000, 2005, 2010, 2015 and 2020 (observed), and the 2025 and 2030 epochs, which GHSL
projects from the observed trend. End-2026 is interpolated between them and reported only
as a projection. The original note: later epochs are
projections and are not used. For each 500 m piece, sums the built-up surface of
cells whose centre lies within 300 m of the road.

Writes outputs/growth_pieces.csv, outputs/growth_summary.csv, figures/f03_growth.png.
Source: Pesaresi & Politis (2023), GHS-BUILT-S R2023A, European Commission JRC.
"""
import io, os, sys, zipfile
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
import requests
from rasterio.windows import from_bounds
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config as C

from cartography import INK, INK2, SURF  # noqa: E402

YEARS = [2000, 2005, 2010, 2015, 2020, 2025, 2030]  # 2025 and 2030 are GHSL projections
OBSERVED = [2000, 2005, 2010, 2015, 2020]
URL = ("https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_BUILT_S_GLOBE_R2023A/"
       "GHS_BUILT_S_E{y}_GLOBE_R2023A_54009_100/V1-0/tiles/GHS_BUILT_S_E{y}_GLOBE_R2023A_54009_100_V1_0_{t}.zip")
TILES = C.GHSL_TILES  # 1000 km Mollweide tiles
GDIR = os.path.join(C.DATA, "ghsl")
BUF_M = 300
MOLL = "ESRI:54009"
YEAR_RAMP = ["#c6dbf2", "#8fb8e6", "#5690d6", "#2a66b3", "#0d3a75"]  # light (2000) -> dark (2020), observed
os.makedirs(GDIR, exist_ok=True)


def tile(year, t):
    path = os.path.join(GDIR, f"built_s_{year}_{t}.tif")
    if not os.path.exists(path):
        for attempt in range(4):  # the JRC server sometimes stalls
            try:
                z = zipfile.ZipFile(io.BytesIO(requests.get(URL.format(y=year, t=t), timeout=300).content))
                break
            except requests.exceptions.RequestException:
                if attempt == 3:
                    raise
                print("retrying", year, t)
        name = [n for n in z.namelist() if n.endswith(".tif")][0]
        with open(path, "wb") as f:
            f.write(z.read(name))
        print("downloaded", year, t)
    return path


P = pd.read_csv(os.path.join(C.OUTPUTS, "pieces_typed.csv"))
pieces = gpd.read_file(os.path.join(C.DATA, "pieces.gpkg")).merge(P[["corridor", "piece", "road_type", "type_rank"]])
buf = pieces.to_crs(C.UTM).buffer(BUF_M)
bounds = gpd.GeoSeries(buf, crs=C.UTM).to_crs(MOLL).total_bounds

# Only cells near a road are kept: each tile window is first rasterised with the 300 m zones
# (all_touched, a superset; the nearest-piece join below applies the exact 300 m), then each
# epoch is read and only those cells extracted. Whole 1000 km tiles never sit in memory as
# tables, which matters for the regional study's dozens of tiles.
from rasterio.features import rasterize
buf_moll = gpd.GeoSeries(buf, crs=C.UTM).to_crs(MOLL)
parts = []
for t in TILES:
    cells = None
    for y in YEARS:
        with rasterio.open(tile(y, t)) as src:
            b = src.bounds
            clipped = (max(bounds[0], b.left), max(bounds[1], b.bottom), min(bounds[2], b.right), min(bounds[3], b.top))
            if clipped[0] >= clipped[2] or clipped[1] >= clipped[3]:
                break
            w = from_bounds(*clipped, transform=src.transform).round_offsets().round_lengths()
            if cells is None:
                tf = src.window_transform(w)
                shp = buf_moll.cx[clipped[0]:clipped[2], clipped[1]:clipped[3]]
                if shp.empty:
                    break
                mask = rasterize(((g, 1) for g in shp), out_shape=(int(w.height), int(w.width)), transform=tf,
                                 all_touched=True, dtype="uint8").ravel().astype(bool)
                idx = np.flatnonzero(mask)
                del mask
                if not len(idx):
                    break
                xs, ys = rasterio.transform.xy(tf, idx // int(w.width), idx % int(w.width))
                cells = pd.DataFrame({"x": xs, "y": ys})
            a = src.read(1, window=w).ravel()[idx].astype(float)
            if src.nodata is not None:
                a[a == src.nodata] = 0
            cells[f"b{y}"] = a
    if cells is not None:
        parts.append(cells)
cells = pd.concat(parts, ignore_index=True)
cells = cells[cells[[f"b{y}" for y in YEARS]].sum(axis=1) > 0]
pts = gpd.GeoDataFrame(cells, geometry=gpd.points_from_xy(cells.x, cells.y), crs=MOLL).to_crs(C.UTM)

# Each cell goes to its nearest piece only, so overlapping 300 m zones are not double counted
lines = pieces.to_crs(C.UTM)[["geometry"]].reset_index().rename(columns={"index": "row"})
joined = gpd.sjoin_nearest(pts, lines, max_distance=BUF_M, how="inner").drop_duplicates(subset=["x", "y"])
per = joined.groupby("row")[[f"b{y}" for y in YEARS]].sum() / 1e4  # hectares
G = pieces.drop(columns="geometry").copy()
for y in YEARS:
    G[f"built_ha_{y}"] = per[f"b{y}"].reindex(range(len(G))).fillna(0).round(2).to_numpy()
G["built_ha_2026_proj"] = (G.built_ha_2025 + 0.2 * (G.built_ha_2030 - G.built_ha_2025)).round(2)
G["growth_ha_2000_2020"] = G.built_ha_2020 - G.built_ha_2000
G[["corridor", "piece", "km_mid", "road_type"] + [f"built_ha_{y}" for y in YEARS] + ["built_ha_2026_proj", "growth_ha_2000_2020"]].to_csv(
    os.path.join(C.OUTPUTS, "growth_pieces.csv"), index=False)

S = G.groupby(["corridor"])[[f"built_ha_{y}" for y in OBSERVED] + ["built_ha_2026_proj"]].sum().round(0)
S["growth_2000_2020_pct"] = (100 * (S.built_ha_2020 / S.built_ha_2000 - 1)).round(0)
S["growth_2020_2026_proj_pct"] = (100 * (S.built_ha_2026_proj / S.built_ha_2020 - 1)).round(0)
T = G.groupby(["corridor", "road_type"])[["built_ha_2000", "built_ha_2020"]].sum().round(0)
T["growth_pct"] = (100 * (T.built_ha_2020 / T.built_ha_2000 - 1)).round(0)
pd.concat([S.reset_index().assign(road_type="all"), T.reset_index()]).to_csv(
    os.path.join(C.OUTPUTS, "growth_summary.csv"), index=False)
print(S.to_string())
print(T.to_string())

# Figure: built-up hectares per km along each corridor, one line per epoch
fig, axs = plt.subplots(len(C.CORRIDORS), 1, figsize=(13, 3.6 * len(C.CORRIDORS)), facecolor=SURF,
                        gridspec_kw=dict(hspace=0.6))
for ax, (corridor, cfg) in zip(axs, C.CORRIDORS.items()):
    title = cfg["label"]
    d = G[G.corridor == corridor].sort_values("km_mid")
    km = np.floor(d.km_mid).astype(int)
    s26 = d.groupby(km)["built_ha_2026_proj"].sum()
    ax.plot(s26.index + 0.5, s26.to_numpy(), color="#eb6834", linewidth=1.2, linestyle=(0, (3, 2)),
            label="end-2026 (projected)")
    for y, col in zip(OBSERVED, YEAR_RAMP):
        s = d.groupby(km)[f"built_ha_{y}"].sum()
        ax.plot(s.index + 0.5, s.to_numpy(), color=col, linewidth=1.6 if y in (2000, 2020) else 1.1, label=str(y))
    ax.set_facecolor(SURF)
    for s_ in ("top", "right", "left"):
        ax.spines[s_].set_visible(False)
    ax.spines["bottom"].set_color("#e4e3df")
    ax.grid(axis="y", color="#e4e3df", linewidth=0.6)
    ax.tick_params(colors=INK2, labelsize=8, length=0)
    ax.set_xlim(0, d.km_mid.max())
    ax.set_xlabel("km from Kampala", fontsize=8.5, color=INK2)
    g = S.loc[corridor]
    ax.text(0, 1.1, title, transform=ax.transAxes, fontsize=11.5, color=INK)
    ax.text(0, 1.02, f"built-up land within 300 m of the road, hectares per km · "
            f"{g.built_ha_2000:,.0f} ha in 2000 → {g.built_ha_2020:,.0f} ha in 2020 (+{g.growth_2000_2020_pct:.0f}%)",
            transform=ax.transAxes, fontsize=9, color=INK2)
    if ax is axs[0]:
        ax.legend(loc="upper right", frameon=False, fontsize=8.5, labelcolor=INK2, ncol=6)
fig.text(0.125, 0.955, "The roadside keeps filling in, 2000–2020", fontsize=15, color=INK)
fig.text(0.125, 0.02, "Source: GHSL GHS-BUILT-S R2023A (EC JRC), 100 m.", fontsize=8, color=INK2)
out = os.path.join(C.FIGURES, "f03_growth.png")
fig.savefig(out, dpi=150, facecolor=SURF, bbox_inches="tight")
print("wrote", out)
