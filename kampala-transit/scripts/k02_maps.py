"""Maps and corridor ranking for the Kampala transit screening (after k01_screen.py).

    python kampala-transit/scripts/k02_maps.py

Corridors are ranked within the dense core (20 km of the city centre), where mass transit would
run. The tolled Entebbe Expressway (M3) is limited-access, so it is flagged for express buses only.

  figures/k01_load_map.png     every road in Greater Kampala by modelled person-trip load, rail reserve
  figures/k02_candidates.png   the screened corridors: light rail / high-capacity BRT, BRT, bus priority
  figures/k03_closeups.png     street level (4 km) at the busiest stretch of the top candidates:
                               building footprints, the road network, load, rail
  outputs/corridors_core.csv
"""
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import pyarrow.parquet as pq
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
import sys; sys.path.insert(0, os.path.join(ROOT, "scripts"))  # noqa: E702
import cartography as K  # noqa: E402

OUT, FIG, DATA = (os.path.join(ROOT, "kampala-transit", d) for d in ("outputs", "figures", "data"))
os.makedirs(FIG, exist_ok=True)
INK, INK2, SURF, LAND, WATER = "#1d2321", "#5d6764", "#fcfcfb", "#f6f4ef", "#c9dbe6"
CBD = (32.5825, 0.3136)
UTM = 32636
S = gpd.read_file(os.path.join(OUT, "edges.gpkg"))
rail = gpd.read_file(os.path.join(OUT, "rail.gpkg"))
lakes = gpd.read_file(os.path.join(ROOT, "data", "ne_lakes", "ne_10m_lakes.shp")).to_crs(4326).cx[32.2:33.1, -0.2:0.7]
c = S.geometry.interpolate(0.5, normalized=True)
S["cbd_km"] = np.hypot((c.x - CBD[0]) * 111.32 * np.cos(np.radians(0.3)), (c.y - CBD[1]) * 111.32)
S["route"] = S.ref.fillna(S.name).fillna("")
# readable names from OSM: the most common street name on each numbered route
_nm = S[S.ref.notna() & S.name.notna()].groupby("ref").name.agg(lambda x: x.value_counts().index[0])
NAMES = {r: f"{n} ({r})" for r, n in _nm.items()}
NAMES["M20"] = "Northern Bypass (M20)"

# ---------------------------------------------------------------- ranking in the core
core = S[(S.cbd_km <= 20) & S.highway.isin(["motorway", "trunk", "primary", "secondary"]) & (S.route != "")]
rows = []
for r, d in core.groupby("route"):
    L = d.km.sum()
    if L < 3:
        continue
    top = d.loc[d.load_idx.idxmax()]
    p = top.geometry.interpolate(0.5, normalized=True)
    rows.append(dict(route=r, name=NAMES.get(r, r), km_core=round(L, 1), cls=d.highway.mode().iloc[0],
                     load_mean=(d.load_idx * d.km).sum() / L, load_max=d.load_idx.max(),
                     pkm=(d.load * d.km).sum(), catch_pop_per_km=(d.catch_pop * d.km).sum() / L,
                     wide_share=(d.km * d.wide).sum() / L, rail_share=(d.km * (d.rail_m < 500)).sum() / L,
                     kmh=L / (d["min"].sum() / 60), peak_lon=p.x, peak_lat=p.y))
C = pd.DataFrame(rows).sort_values("pkm", ascending=False).reset_index(drop=True)
C["pkm_share"] = C.pkm / (S.load * S.km)[S.cbd_km <= 20].sum()
surf = ~C.route.isin(["M3"])
q90, q70 = C[surf].load_mean.quantile(0.9), C[surf].load_mean.quantile(0.7)
C["screen"] = np.select(
    [C.route == "M3",
     surf & (C.load_mean >= q90) & (C.km_core >= 8) & (C.catch_pop_per_km >= C.catch_pop_per_km.median()),
     surf & (C.load_mean >= q70) & (C.km_core >= 5) & (C.wide_share >= 0.3),
     surf & (C.load_mean >= q70) & (C.km_core >= 5),
     (C.rail_share >= 0.3)],
    ["express bus only (tolled, limited access)", "light rail or high-capacity BRT",
     "BRT (dual carriageway on part)", "BRT with land take, or bus priority", "commuter rail on the reserve"],
    "bus/taxi priority only")
C.to_csv(os.path.join(OUT, "corridors_core.csv"), index=False)
print(C.head(16)[["name", "km_core", "load_mean", "pkm_share", "catch_pop_per_km", "wide_share", "rail_share",
                  "kmh", "screen"]].round(2).to_string())

SCREEN_COL = {"light rail or high-capacity BRT": "#7c2e0f", "BRT (dual carriageway on part)": "#c4532d",
              "BRT with land take, or bus priority": "#e89a7a", "commuter rail on the reserve": "#3d7f8f",
              "express bus only (tolled, limited access)": "#8a6b4e", "bus/taxi priority only": "#c9c2b8"}
EXT = (32.36, 32.86, 0.06, 0.52)


def base(ax, ext=EXT):
    K.frame(ax, ext)
    if len(lakes):
        lakes.plot(ax=ax, aspect=None, color=WATER, linewidth=0, zorder=1)
    K.frame(ax, ext)
    ax.set_facecolor(LAND)


# ---------------------------------------------------------------- k01 load map
bins = [0, 2, 5, 10, 20, 40, 1e9]
cmap = ListedColormap(["#e6e1d6", "#f6c9a8", "#ef9a63", "#d8642e", "#a8401a", "#5e1e08"])
norm = BoundaryNorm(bins, cmap.N)
fig, ax = plt.subplots(figsize=(11, 11), facecolor=SURF)
base(ax)
S.sort_values("load_idx").plot(ax=ax, aspect=None, column="load_idx", cmap=cmap, norm=norm,
                               linewidth=0.6 + 4.5 * np.clip(S.sort_values("load_idx").load_idx / 40, 0, 1), zorder=3)
rail.plot(ax=ax, aspect=None, color="#2a78d6", linewidth=1.6, linestyle=(0, (4, 2)), zorder=4)
ax.scatter(*CBD, s=80, color=INK, zorder=6)
ax.annotate("Kampala CBD", CBD, xytext=(6, 6), textcoords="offset points", fontsize=11, fontweight="bold", zorder=7)
K.furniture(ax, km=5)
K.key(fig, ax, cmap, norm, bins, "modelled person-trip load (index, busiest 0.5% of roads = 100)",
      labels=["< 2", "2–5", "5–10", "10–20", "20–40", "> 40"])
ax.legend(handles=[Line2D([], [], color="#2a78d6", lw=1.6, ls=(0, (4, 2)), label="railway (OSM)")],
          loc="lower left", frameon=True, facecolor="white", fontsize=9)
fig.text(0.04, 0.95, "Where travel demand concentrates on Greater Kampala's roads", fontsize=16, color=INK)
fig.text(0.04, 0.93, "Gravity model from residents (WorldPop 2025) to built-up activity (GHSL 2020), routed on peak "
         "speeds with roadside friction. A relative index, not a count.", fontsize=9.5, color=INK2)
fig.savefig(os.path.join(FIG, "k01_load_map.png"), dpi=160, facecolor=SURF, bbox_inches="tight")
plt.close(fig)

# ---------------------------------------------------------------- k02 candidates
fig, ax = plt.subplots(figsize=(11, 11), facecolor=SURF)
base(ax)
S.plot(ax=ax, aspect=None, color="#d3cdc0", linewidth=0.5, zorder=2)
for _, r in C.iloc[::-1].iterrows():
    d = core[core.route == r.route]
    d.plot(ax=ax, aspect=None, color=SCREEN_COL[r.screen], linewidth=4.2 if "rail" in r.screen or "BRT" in r.screen else 2.2,
           zorder=4)
top8 = C[~C.route.isin(["M3"])].head(8)
K.labels(ax, top8.peak_lon.to_list(), top8.peak_lat.to_list(), top8["name"].to_list(), fontsize=8.5)
rail.plot(ax=ax, aspect=None, color="#2a78d6", linewidth=1.4, linestyle=(0, (4, 2)), zorder=5)
ax.scatter(*CBD, s=80, color=INK, zorder=6)
K.furniture(ax, km=5)
ax.legend(handles=[Line2D([], [], color=c_, lw=4, label=k) for k, c_ in SCREEN_COL.items()]
          + [Line2D([], [], color="#2a78d6", lw=1.6, ls=(0, (4, 2)), label="railway (OSM)")],
          loc="lower left", frameon=True, facecolor="white", fontsize=9, title="first-pass screening",
          title_fontsize=9.5)
fig.text(0.04, 0.95, "Where BRT or light rail might make sense: a first screening", fontsize=16, color=INK)
fig.text(0.04, 0.93, "Named roads within 20 km of the centre, by modelled load, length, walk catchment (800 m), "
         "road width in OSM and the rail reserve. Thresholds are illustrative.", fontsize=9.5, color=INK2)
fig.savefig(os.path.join(FIG, "k02_candidates.png"), dpi=160, facecolor=SURF, bbox_inches="tight")
plt.close(fig)

# ---------------------------------------------------------------- k03 close-ups
B = pq.read_table(os.path.join(ROOT, "data", "buildings.parquet"),
                  columns=["latitude", "longitude", "area_in_meters"]).to_pandas()
osm = gpd.read_file(os.path.join(ROOT, "data", "osm_features.gpkg"), layer="roads", bbox=EXT[0:1] + EXT[2:3] + EXT[1:2] + EXT[3:4])
cand = C[C.screen.str.contains("rail|BRT")]
rows_ = []
for _, r in cand.iterrows():   # busiest stretch of each road at least 3 km from windows already chosen
    d = core[core.route == r.route].sort_values("load_idx", ascending=False)
    for _, e in d.iterrows():
        p = e.geometry.interpolate(0.5, normalized=True)
        if all(np.hypot(p.x - q.peak_lon, p.y - q.peak_lat) > 0.03 for q in rows_):
            rows_.append(r.copy().rename(None))
            rows_[-1]["peak_lon"], rows_[-1]["peak_lat"] = p.x, p.y
            break
    if len(rows_) == 6:
        break
picks = pd.DataFrame(rows_)
HALF = 0.018
fig, axs = plt.subplots(2, 3, figsize=(15, 11.5), facecolor=SURF, gridspec_kw=dict(hspace=0.32, wspace=0.08))
for ax, (_, r) in zip(axs.ravel(), picks.iterrows()):
    x0, x1, y0, y1 = r.peak_lon - HALF, r.peak_lon + HALF, r.peak_lat - HALF, r.peak_lat + HALF
    K.frame(ax, (x0, x1, y0, y1))
    ax.set_facecolor(LAND)
    bb = B[B.longitude.between(x0, x1) & B.latitude.between(y0, y1)]
    inch = 15 / 3 / (2 * HALF)
    ax.scatter(bb.longitude, bb.latitude, s=np.maximum(np.sqrt(bb.area_in_meters) / 111320 * inch * 72, 0.8) ** 2,
               marker="s", color="#9d988c", linewidths=0, zorder=2)
    o = osm.cx[x0:x1, y0:y1]
    if len(o):
        o.plot(ax=ax, aspect=None, color="#8c887f", linewidth=0.5, zorder=3)
    w = S.cx[x0:x1, y0:y1]
    w.plot(ax=ax, aspect=None, color=INK, linewidth=4, zorder=4)
    w.plot(ax=ax, aspect=None, column="load_idx", cmap=cmap, norm=norm, linewidth=2.6, zorder=5)
    rr = rail.cx[x0:x1, y0:y1]
    if len(rr):
        rr.plot(ax=ax, aspect=None, color="#2a78d6", linewidth=2, linestyle=(0, (4, 2)), zorder=6)
    K.scalebar(ax, km=1)
    for s_ in ax.spines.values():
        s_.set_visible(True); s_.set_color(INK)
    note = "" if len(bb) > 2000 else "  [footprints not yet downloaded here]"
    ax.set_title(f"{r['name']}{note}\n{r.screen}\nwalk catchment {r.catch_pop_per_km:,.0f} residents per km",
                 loc="left", fontsize=9.5, color=INK)
for ax in axs.ravel()[len(picks):]:
    ax.set_axis_off()
fig.suptitle("Street level at the busiest stretch of each candidate (4 km windows)", x=0.02, ha="left", fontsize=15,
             color=INK)
fig.text(0.02, 0.935, "Building footprints (Google Open Buildings, available within 1 km of the trade corridors), "
         "the road network (OSM), modelled load, railway. Footprints show the space a busway would have to find.",
         fontsize=9.5, color=INK2)
fig.savefig(os.path.join(FIG, "k03_closeups.png"), dpi=150, facecolor=SURF, bbox_inches="tight")
plt.close(fig)
print("wrote k01_load_map.png, k02_candidates.png, k03_closeups.png")
