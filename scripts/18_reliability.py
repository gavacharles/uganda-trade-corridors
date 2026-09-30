"""How reliable is the trip? Day-to-day travel time from 20 years of rain, and flood-prone stretches.

Traders plan for a bad day, not the average one. For every day in 2006-2025, each piece is
wet if CHIRPS recorded at least 10 mm in its cell that day; wet pieces are driven at the
model's wet-day speed (travel_model.PARAMS["wet_factor"]), dry pieces at the normal speed.
Summing pieces gives one trip time per day, so each corridor has 7,305 daily trip times.
Reported per corridor and vehicle (leaving Kampala, central assumptions):
  median, 95th percentile, days a year at least 2% slower than dry, and the buffer index ((p95 - median) / median: the extra time a
  shipper must allow to arrive on time 19 days in 20), and the same by calendar month.

Only slower driving in rain is modelled. Floods that cut or close the road are not observed
in open data, so stretches are ranked by their exposure instead (outputs/fragile_stretches.csv):
for each 2 km (four pieces), a fragility score is the sum of standardised water crossings,
wetland share, days a year with at least 30 mm of rain, and how low the road sits compared
with the 5 km either side (valleys collect water). It ranks exposure, not observed damage.

Writes outputs/reliability.csv, outputs/reliability_monthly.csv, outputs/fragile_stretches.csv,
figures/f09_reliability.png.
"""
import glob, os
import pandas as pd
import xarray as xr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config as C
from cartography import INK, INK2, SURF, MONTH_NAMES
from travel_model import CENTRAL, P, piece_minutes

WET_MM, HEAVY_MM = 10, 30
files = sorted(p for p in glob.glob(os.path.join(C.CHIRPS_DIR, f"{C.CHIRPS_PREFIX}_20*.nc")) if 2006 <= int(p[-7:-3]) <= 2025)
rain = xr.concat([xr.open_dataset(p).precip for p in files], "time")
lat = xr.DataArray(P.lat.to_numpy(), dims="piece")
lon = xr.DataArray(P.lon.to_numpy(), dims="piece")
R = rain.sel(latitude=lat, longitude=lon, method="nearest").transpose("time", "piece").to_numpy()  # (days, pieces)
days = pd.DatetimeIndex(rain.time.values)
print(f"{len(days)} days x {R.shape[1]} pieces")
wet = R >= WET_MM

rows, mrows = [], []
for veh in ("car", "truck"):
    dry_t = piece_minutes(CENTRAL, veh, "outbound")
    wet_t = piece_minutes(CENTRAL, veh, "outbound", wet=True)
    for corridor in C.CORRIDORS:
        m = (P.corridor == corridor).to_numpy()
        daily = dry_t[m].sum() + (wet[:, m] * (wet_t[m] - dry_t[m])).sum(axis=1)
        s = pd.Series(daily, index=days)
        med, p95 = s.median(), s.quantile(0.95)
        rows.append(dict(corridor=corridor, vehicle=veh, dry_min=round(dry_t[m].sum(), 1), median_min=round(med, 1),
                         p95_min=round(p95, 1), worst_min=round(s.max(), 1), buffer_index=round((p95 - med) / med, 3),
                         days_over_2pct_slower=round((s > dry_t[m].sum() * 1.02).mean() * 365, 1),
                         share_road_wet_mean=round(wet[:, m].mean(), 3)))
        g = s.groupby(s.index.month)
        for mo, v in g:
            mrows.append(dict(corridor=corridor, vehicle=veh, month=mo, mean_min=round(v.mean(), 1),
                              p95_min=round(v.quantile(0.95), 1),
                              share_road_wet=round(wet[days.month == mo][:, m].mean(), 3)))
rel = pd.DataFrame(rows)
rel.to_csv(os.path.join(C.OUTPUTS, "reliability.csv"), index=False)
mon = pd.DataFrame(mrows)
mon.to_csv(os.path.join(C.OUTPUTS, "reliability_monthly.csv"), index=False)
print(rel.to_string(index=False))

# ---- Flood-prone stretches (exposure)
heavy = (R >= HEAVY_MM).sum(axis=0) / (len(days) / 365.25)
Q = P[["corridor", "piece", "km_start", "place", "water_crossings", "wetland_share", "elev_m"]].copy()
Q["heavy_days"] = heavy
Q["low_lying"] = 0.0
for corridor, d in Q.groupby("corridor"):
    local = d.elev_m.rolling(21, center=True, min_periods=5).mean()   # 10 km window
    Q.loc[d.index, "low_lying"] = (local - d.elev_m).clip(lower=0)
w = []
for corridor, d in Q.groupby("corridor", sort=False):
    d = d.reset_index(drop=True)
    agg = pd.DataFrame({"water_crossings": d.water_crossings.rolling(4).sum(),
                        "wetland_share": d.wetland_share.rolling(4).mean(),
                        "heavy_days": d.heavy_days.rolling(4).mean(),
                        "low_lying": d.low_lying.rolling(4).max()})
    agg["corridor"], agg["km_from"] = corridor, d.km_start.shift(3)
    agg["place"] = [d.place.iloc[max(i - 3, 0):i + 1].dropna().mode().iloc[0]
                    if d.place.iloc[max(i - 3, 0):i + 1].notna().any() else "" for i in range(len(d))]
    w.append(agg.iloc[3::4])   # non-overlapping 2 km stretches
W = pd.concat(w, ignore_index=True).dropna(subset=["km_from"])
comp = ["water_crossings", "wetland_share", "heavy_days", "low_lying"]
Z = (W[comp] - W[comp].mean()) / W[comp].std()
W["fragility"] = Z.sum(axis=1)
W["km_to"] = W.km_from + 2
top = W.sort_values("fragility", ascending=False).groupby("corridor").head(10)
top = top[["corridor", "km_from", "km_to", "place", "fragility"] + comp].round(2)
top.to_csv(os.path.join(C.OUTPUTS, "fragile_stretches.csv"), index=False)
print(top.groupby("corridor").head(3).to_string(index=False))

# ---- Figure: month-by-month truck trip time (mean and 95th percentile) and wet share
fig, axs = plt.subplots(1, len(C.CORRIDORS), figsize=(15, 4.6), facecolor=SURF, sharey=True)
for ax, corridor in zip(axs, C.CORRIDORS):
    d = mon[(mon.corridor == corridor) & (mon.vehicle == "truck")]
    base = rel[(rel.corridor == corridor) & (rel.vehicle == "truck")].dry_min.iloc[0]
    x = d.month.to_numpy()
    ax.bar(x, d.p95_min - base, color="#c4532d", width=0.7, linewidth=0, label="95th percentile day")
    ax.bar(x, d.mean_min - base, color="#17252a", width=0.7, linewidth=0, label="average day")
    ax.set_xticks(x)
    ax.set_xticklabels([MONTH_NAMES[i - 1][0] for i in x], fontsize=8.5, color=INK2)
    for s_ in ("top", "right", "left"):
        ax.spines[s_].set_visible(False)
    ax.grid(axis="y", color="#e4e3df", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(colors=INK2, labelsize=8.5, length=0)
    r = rel[(rel.corridor == corridor) & (rel.vehicle == "truck")].iloc[0]
    ax.set_title(f"{C.CORRIDORS[corridor]['short']} ({C.CORRIDORS[corridor]['ref']}): dry trip {base:.0f} min\n"
                 f"buffer index {r.buffer_index:.1%}", loc="left", fontsize=10, color=INK)
axs[0].set_ylabel("truck minutes added by rain", fontsize=9, color=INK2)
axs[0].legend(loc="upper left", frameon=False, fontsize=8.5, labelcolor=INK2)
fig.text(0.01, 1.05, "Rain makes the trip slower and less predictable, by season", fontsize=15, color=INK)
fig.text(0.01, 0.985, "Daily trip times 2006–2025 from where CHIRPS recorded ≥ 10 mm that day; wet pieces driven at the "
         "wet-day speed. Road closures by flooding are not modelled.", fontsize=9, color=INK2)
fig.savefig(os.path.join(C.FIGURES, "f09_reliability.png"), dpi=150, facecolor=SURF, bbox_inches="tight")
print("wrote outputs/reliability*.csv, outputs/fragile_stretches.csv, figures/f09_reliability.png")
