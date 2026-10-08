"""Machine learning for land use: learn from the cells OpenStreetMap labels, predict the rest.

    python kampala-transit/scripts/k08_ml_landuse.py      (after k07_landuse.py)

Features for every 250 m cell (k07 grid):
  form    buildings per ha, median and mean footprint, ground coverage, share of buildings under 40 m2,
          footprint size spread (Open Buildings v3); residents (WorldPop 2025)
  image   from Esri World Imagery at zoom 15 (about 4.8 m pixels): mean and spread of red, green and blue,
          brightness, excess-green vegetation index and the share of vegetated pixels, share of red/orange
          (iron-sheet and tile) roofs, share of bright (grey metal, concrete) roofs, texture (mean gradient)
Labels: cells where one OSM land-use group covers more than half the cell: residential, commercial /
industrial, institutional, farm / forest / grass, wetland / water.
Model: random forest (400 trees, balanced class weights). Accuracy is measured with spatial
cross-validation: the city is cut into 2.5 km blocks and whole blocks are held out, so that the model
is never tested on a neighbour of a cell it learned from.
Unsupervised check: a Gaussian mixture on form and image features of the residential cells, with the
number of groups chosen by BIC, compared with k07's rule-based residential classes.
The final land use (outputs/landuse_cells.parquet, column `cls`, kept from k07 as `cls_rule`):
  wetland / water, commercial / industrial, institutional  where the model is at least 60% sure
  residential cells are split by building form as in k07 (dense small-plot, planned / larger-plot,
                                                           peri-urban, rural / open)
Writes outputs/ml_landuse_cv.csv, ml_importance.csv, ml_gmm.csv, figures/k08_ml_landuse.png.
Imagery © Esri, Maxar, Earthstar Geographics.
"""
import math, os, sys
import numpy as np
import pandas as pd
import pyogrio
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_origin
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, adjusted_rand_score, classification_report, f1_score
from sklearn.mixture import GaussianMixture
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

HERE = os.path.dirname(os.path.abspath(__file__))
KT = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(KT, ".."))
sys.path.insert(0, HERE)
from satmap import _lonlat, _tile, _tile_xy  # noqa: E402

BOX = (32.35, 0.02, 32.90, 0.55)
CELL, Z = 0.00225, 15
LU = pd.read_parquet(os.path.join(KT, "outputs", "landuse_cells.parquet"))
if "cls_rule" in LU:
    LU["cls"] = LU.cls_rule
W_, H_ = int(round((BOX[2] - BOX[0]) / CELL)), int(round((BOX[3] - BOX[1]) / CELL))
assert len(LU) == W_ * H_

# ---------------------------------------------------------------- footprint form, extra
B = pd.read_parquet(os.path.join(KT, "data", "buildings_pts.parquet"))
B = B[B.confidence >= 0.70]
cell = ((BOX[3] - B.latitude) / CELL).astype(int).clip(0, H_ - 1) * W_ + ((B.longitude - BOX[0]) / CELL).astype(int).clip(0, W_ - 1)
g = B.assign(cell=cell, la=np.log(B.area_in_meters)).groupby("cell")
LU["mean_m2"] = g.area_in_meters.mean().reindex(LU.index)
LU["size_spread"] = g.la.std().reindex(LU.index)
del B

# ---------------------------------------------------------------- image features, tile by tile
x0, y0 = _tile_xy(BOX[0], BOX[3], Z)
x1, y1 = _tile_xy(BOX[2], BOX[1], Z)
acc = {k: np.zeros(W_ * H_) for k in ("n", "r", "g", "b", "r2", "g2", "b2", "exg", "veg", "red", "bright", "grad")}
tiles = [(tx, ty) for tx in range(int(x0), int(x1) + 1) for ty in range(int(y0), int(y1) + 1)]
print(len(tiles), "tiles at zoom", Z, flush=True)
for k, (tx, ty) in enumerate(tiles):
    a = np.asarray(_tile(Z, tx, ty), dtype="float32") / 255
    r, gg, b = a[..., 0], a[..., 1], a[..., 2]
    w, n = _lonlat(tx, ty, Z)
    e, s = _lonlat(tx + 1, ty + 1, Z)
    lon = w + (np.arange(256) + 0.5) / 256 * (e - w)
    lat = n + (np.arange(256) + 0.5) / 256 * (s - n)
    cc = np.floor((lon - BOX[0]) / CELL).astype(int)
    rr = np.floor((BOX[3] - lat) / CELL).astype(int)
    ok_c, ok_r = (cc >= 0) & (cc < W_), (rr >= 0) & (rr < H_)
    if not ok_c.any() or not ok_r.any():
        continue
    idx = (rr[:, None] * W_ + cc[None, :])
    m = ok_r[:, None] & ok_c[None, :]
    idx = idx[m]
    exg = 2 * gg - r - b
    gy, gx = np.gradient(r + gg + b)
    feats = dict(n=np.ones_like(r), r=r, g=gg, b=b, r2=r * r, g2=gg * gg, b2=b * b, exg=exg, veg=(exg > 0.06) * 1.0,
                 red=((r > gg * 1.12) & (r > b * 1.2) & (r > 0.3)) * 1.0, bright=((r + gg + b) / 3 > 0.55) * 1.0,
                 grad=np.hypot(gx, gy))
    for kk, v in feats.items():
        acc[kk] += np.bincount(idx, weights=v[m], minlength=W_ * H_)
    if k % 400 == 0:
        print(f"  {k}/{len(tiles)} tiles", flush=True)
n = np.maximum(acc["n"], 1)
for c in ("r", "g", "b"):
    LU[f"img_{c}"] = acc[c] / n
    LU[f"img_{c}_sd"] = np.sqrt(np.maximum(acc[c + "2"] / n - (acc[c] / n) ** 2, 0))
LU["img_bright"] = (LU.img_r + LU.img_g + LU.img_b) / 3
for c in ("exg", "veg", "red", "bright", "grad"):
    LU[f"img_{c}"] = acc[c] / n

# ---------------------------------------------------------------- labels from OSM
osm = pyogrio.read_dataframe(os.path.join(ROOT, "data", "uganda-latest.osm.pbf"), layer="multipolygons", bbox=BOX,
                             columns=["landuse", "amenity", "natural"],
                             where="landuse IS NOT NULL OR amenity IS NOT NULL OR natural IS NOT NULL")
GROUPS = {
    "residential": osm.landuse.isin(["residential"]),
    "commercial / industrial": osm.landuse.isin(["commercial", "retail", "industrial"]) | osm.amenity.isin(["marketplace"]),
    "institutional": osm.amenity.isin(["school", "university", "college", "hospital", "prison"]) |
                     osm.landuse.isin(["education", "institutional", "military"]),
    "farm / forest / grass": osm.landuse.isin(["farmland", "forest", "orchard", "meadow", "grass", "farmyard"]) |
                             osm.natural.isin(["wood", "grassland", "scrub", "heath"]),
    "wetland / water": osm.natural.isin(["wetland", "water"]),
}
SUB = 5
T2 = from_origin(BOX[0], BOX[3], CELL / SUB, CELL / SUB)
frac = {}
for k, msk in GROUPS.items():
    geoms = [x for x in osm.geometry[msk] if x is not None and not x.is_empty]
    a = rasterize(((x, 1) for x in geoms), out_shape=(H_ * SUB, W_ * SUB), transform=T2, fill=0, dtype="uint8")
    frac[k] = a.reshape(H_, SUB, W_, SUB).mean(axis=(1, 3)).ravel()
F = pd.DataFrame(frac)
LU["osm_label"] = np.where(F.max(axis=1) > 0.5, F.idxmax(axis=1), None)
print(LU.osm_label.value_counts(), flush=True)

FORM = ["bld_ha", "med_m2", "mean_m2", "coverage", "small_share", "size_spread", "pop"]
IMG = ["img_r", "img_g", "img_b", "img_r_sd", "img_g_sd", "img_b_sd", "img_bright", "img_exg", "img_veg", "img_red",
       "img_grad"]
# Google satellite embeddings (k08a), 64 bands averaged per cell
_emb = os.path.join(KT, "data", "embeddings_2022.tif")
EMB = []
if os.path.exists(_emb):
    with rasterio.open(_emb) as src:
        ea = src.read().reshape(src.count, -1)
    EMB = [f"emb_A{i:02d}" for i in range(ea.shape[0])]
    for i, c in enumerate(EMB):
        LU[c] = ea[i]
SETS = {"building form": FORM, "form + image features": FORM + IMG}
if EMB:
    SETS["satellite embeddings"] = EMB
    SETS["form + embeddings"] = FORM + EMB
    SETS["all"] = FORM + IMG + EMB
# open water (no buildings, labelled water) is left out of training and testing: it is trivial and
# would inflate accuracy
openwater = (LU.osm_label == "wetland / water") & (LU.n.fillna(0) == 0) & (F["wetland / water"] > 0.9)
lab = LU.osm_label.notna().to_numpy() & (acc["n"] > 100) & ~openwater.to_numpy()
y = LU.osm_label[lab].to_numpy()
rr_, cc_ = np.divmod(np.arange(W_ * H_), W_)
block = (rr_ // 11) * 1000 + (cc_ // 11)       # 11 cells = about 2.5 km
groups = block[lab]
print(f"{lab.sum():,} labelled cells after removing {int(openwater.sum()):,} open-water cells", flush=True)

# ---------------------------------------------------------------- spatial cross-validation of each feature set
from sklearn.metrics import balanced_accuracy_score  # noqa: E402
RF = dict(n_estimators=400, min_samples_leaf=2, class_weight="balanced", n_jobs=2, random_state=0)
cvrows, preds = [], {}
for name, cols in SETS.items():
    Xs = LU[cols].fillna(0).to_numpy()[lab]
    p_ = np.empty(len(y), dtype=object)
    for tr, te in GroupKFold(n_splits=5).split(Xs, y, groups):
        p_[te] = RandomForestClassifier(**RF).fit(Xs[tr], y[tr]).predict(Xs[te])
    preds[name] = p_
    f1s = f1_score(y, p_, average=None, labels=sorted(set(y)), zero_division=0)
    cvrows.append(dict(features=name, n_features=len(cols), accuracy=accuracy_score(y, p_),
                       balanced_accuracy=balanced_accuracy_score(y, p_), macro_f1=f1_score(y, p_, average="macro"),
                       **{f"f1 {c}": v for c, v in zip(sorted(set(y)), f1s)}))
    print(f"{name:24s} accuracy {cvrows[-1]['accuracy']:.3f}  balanced {cvrows[-1]['balanced_accuracy']:.3f}  "
          f"macro F1 {cvrows[-1]['macro_f1']:.3f}", flush=True)
CVT = pd.DataFrame(cvrows)
CVT.to_csv(os.path.join(KT, "outputs", "ml_landuse_cv.csv"), index=False)
BEST = CVT.sort_values("macro_f1").features.iloc[-1]
FEATS = SETS[BEST]
pred = preds[BEST]
cv = pd.DataFrame(classification_report(y, pred, output_dict=True, zero_division=0)).T
cv.to_csv(os.path.join(KT, "outputs", "ml_landuse_cv_best.csv"))
print(f"best feature set: {BEST}")
print(classification_report(y, pred, zero_division=0), flush=True)

X = LU[FEATS].fillna(0).to_numpy()
rf = RandomForestClassifier(**RF)
rf.fit(X[lab], y)
P = rf.predict_proba(X)
LU["ml_class"] = rf.classes_[P.argmax(axis=1)]
LU["ml_conf"] = P.max(axis=1)
for i, c in enumerate(rf.classes_):
    LU[f"p_{c}"] = P[:, i]

# ---------------------------------------------------------------- SHAP: what drives each class
import shap  # noqa: E402
rs = np.random.default_rng(0)
samp = rs.choice(np.flatnonzero(lab), size=min(1500, lab.sum()), replace=False)
ex = shap.TreeExplainer(rf)
sv = ex.shap_values(X[samp], check_additivity=False)
sv = np.stack(sv, axis=-1) if isinstance(sv, list) else sv           # (n, features, classes)
mabs = np.abs(sv).mean(axis=0)                                        # (features, classes)
IMP = pd.DataFrame(mabs, index=FEATS, columns=rf.classes_)
IMP["all classes"] = IMP.sum(axis=1)
IMP.sort_values("all classes", ascending=False).to_csv(os.path.join(KT, "outputs", "ml_shap.csv"))
pd.DataFrame({"feature": FEATS, "importance": IMP["all classes"].to_numpy()}).sort_values(
    "importance", ascending=False).to_csv(os.path.join(KT, "outputs", "ml_importance.csv"), index=False)
grp = IMP["all classes"].groupby(lambda f: "embedding" if f.startswith("emb_") else "image" if f.startswith("img_")
                                 else "building form").sum()
print("SHAP share by feature group:", (grp / grp.sum()).round(3).to_dict(), flush=True)

# ---------------------------------------------------------------- unsupervised check on residential cells
res = LU.cls.isin(["dense small-plot", "planned / larger-plot", "peri-urban"]).to_numpy()
Xr = StandardScaler().fit_transform(LU.loc[res, ["bld_ha", "med_m2", "coverage", "small_share", "size_spread",
                                                  "img_veg", "img_red", "img_grad"]].fillna(0))
bic = {k: GaussianMixture(k, random_state=0, n_init=2).fit(Xr).bic(Xr) for k in range(2, 8)}
kb = min(bic, key=bic.get)
gm = GaussianMixture(kb, random_state=0, n_init=3).fit(Xr)
lab_g = gm.predict(Xr)
ari = adjusted_rand_score(LU.cls[res], lab_g)
ct = pd.crosstab(LU.cls[res], lab_g, normalize="columns").round(2)
ct.to_csv(os.path.join(KT, "outputs", "ml_gmm.csv"))
print(f"GMM on residential cells: {kb} groups by BIC; adjusted Rand vs rule classes {ari:.2f}")
print(ct.to_string(), flush=True)

# ---------------------------------------------------------------- final land use
LU["cls_rule"] = LU.cls
sure = LU.ml_conf >= 0.6
LU["cls"] = LU.cls_rule
for k in ("wetland / water", "commercial / industrial", "institutional"):
    LU.loc[sure & (LU.ml_class == k) & (LU.bld_ha < 60), "cls"] = k
# a rule cell called wetland/commercial/institutional that the model is sure is residential goes back to its form class
form_cls = np.select([(LU.bld_ha >= 35) & (LU.med_m2 < 70), LU.bld_ha >= 8, LU.bld_ha >= 2],
                     ["dense small-plot", "planned / larger-plot", "peri-urban"], "rural / open")
back = sure & (LU.ml_class == "residential") & LU.cls_rule.isin(["wetland / water", "commercial / industrial",
                                                                 "institutional"]) & (LU.bld_ha >= 8)
LU.loc[back, "cls"] = form_cls[back.to_numpy()]
CLASSES = ["wetland / water", "commercial / industrial", "institutional", "dense small-plot", "planned / larger-plot",
           "peri-urban", "rural / open"]
LU["code"] = LU.cls.map({k: i for i, k in enumerate(CLASSES)}).astype("uint8")
print("changed by the model:", int((LU.cls != LU.cls_rule).sum()), "cells;",
      f"{LU['pop'][LU.cls != LU.cls_rule].sum():,.0f} residents", flush=True)
keep = [c for c in LU.columns if not c.startswith("img_") or c in ("img_veg", "img_red", "img_grad")]
keep = [c for c in keep if not c.startswith("emb_")]
LU[keep].to_parquet(os.path.join(KT, "outputs", "landuse_cells.parquet"))
with rasterio.open(os.path.join(KT, "outputs", "landuse.tif"), "r+") as dst:
    dst.write(LU.code.to_numpy().reshape(H_, W_), 1)
s = LU.groupby("cls")["pop"].sum()
(s / s.sum()).reindex(CLASSES).to_csv(os.path.join(KT, "outputs", "landuse_summary_ml.csv"))
print((s / s.sum()).reindex(CLASSES).round(3).to_string())

# ---------------------------------------------------------------- figure
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402

INK, INK2, SURF = "#1d2321", "#5d6764", "#fcfcfb"
ML = ["residential", "commercial / industrial", "institutional", "farm / forest / grass", "wetland / water"]
MLC = ["#f0b27a", "#8e44ad", "#1f618d", "#82c785", "#5dade2"]
fig = plt.figure(figsize=(16, 9), facecolor=SURF)
ax = fig.add_axes([0.01, 0.06, 0.40, 0.80])
codes = LU.ml_class.map({k: i for i, k in enumerate(ML)}).to_numpy().reshape(H_, W_).astype(float)
alpha = np.clip((LU.ml_conf.to_numpy().reshape(H_, W_) - 0.3) / 0.5, 0.25, 1)
rgba = ListedColormap(MLC)(codes / (len(ML) - 1) * (len(ML) - 1) / len(ML) + 0.5 / len(ML))
rgba[..., 3] = alpha
ax.imshow(rgba, extent=(BOX[0], BOX[2], BOX[1], BOX[3]), interpolation="nearest")
ax.set_xticks([]); ax.set_yticks([])
ax.set_aspect(1 / math.cos(math.radians(0.3)))
ax.set_title("Random forest prediction (paler = less sure)", loc="left", fontsize=11.5, color=INK)
from matplotlib.patches import Patch  # noqa: E402
ax.legend(handles=[Patch(color=c, label=k) for k, c in zip(ML, MLC)], loc="lower left", fontsize=9, frameon=True)
ax2 = fig.add_axes([0.47, 0.52, 0.22, 0.34])
imp = pd.read_csv(os.path.join(KT, "outputs", "ml_importance.csv")).head(12)[::-1]
ax2.barh(imp.feature, imp.importance, color=["#2e86c1" if f.startswith("emb") else "#3a7d5c" if f.startswith("img")
                                             else "#c4532d" for f in imp.feature])
ax2.set_title("SHAP (red: building form, green: imagery)", loc="left", fontsize=10, color=INK)
ax2.tick_params(labelsize=8.5)
for s_ in ("top", "right"):
    ax2.spines[s_].set_visible(False)
ax3 = fig.add_axes([0.76, 0.52, 0.22, 0.34])
cvt = cv.loc[[c for c in ML if c in cv.index], ["precision", "recall", "f1-score"]]
x = np.arange(len(cvt))
for j, (c, col) in enumerate(zip(cvt.columns, ("#9fb3b0", "#4e7c8a", INK))):
    ax3.bar(x + (j - 1) * 0.27, cvt[c], width=0.26, color=col, label=c)
ax3.set_xticks(x); ax3.set_xticklabels([c.replace(" / ", "/\n") for c in cvt.index], fontsize=8)
ax3.set_ylim(0, 1); ax3.legend(frameon=False, fontsize=8.5)
ax3.set_title(f"Spatial CV, {BEST} (macro F1 {f1_score(y, pred, average='macro'):.2f})", loc="left", fontsize=10.5,
              color=INK)
for s_ in ("top", "right"):
    ax3.spines[s_].set_visible(False)
ax4 = fig.add_axes([0.47, 0.06, 0.51, 0.36])
im = ax4.imshow(ct.to_numpy(), cmap="Greys", vmin=0, vmax=1, aspect="auto")
ax4.set_yticks(range(len(ct))); ax4.set_yticklabels(ct.index, fontsize=9.5)
ax4.set_xticks(range(ct.shape[1])); ax4.set_xticklabels([f"group {c + 1}" for c in ct.columns], fontsize=9)
for i in range(ct.shape[0]):
    for j in range(ct.shape[1]):
        ax4.text(j, i, f"{ct.iat[i, j]:.0%}", ha="center", va="center", fontsize=9,
                 color="white" if ct.iat[i, j] > 0.5 else INK)
ax4.set_title(f"Unsupervised check: {kb} groups found by a Gaussian mixture in residential cells, against the rule "
              f"classes (share of each group; adjusted Rand {ari:.2f})", loc="left", fontsize=10.5, color=INK)
fig.text(0.01, 0.96, "Machine learning for land use: building form plus satellite imagery", fontsize=16, color=INK)
fig.text(0.01, 0.925, f"Random forest trained on {lab.sum():,} cells labelled in OpenStreetMap (open water left out), tested "
         "on held-out 2.5 km blocks. Feature sets compared: " + "; ".join(f"{r.features} {r.macro_f1:.2f}" for r in
         CVT.itertuples()) + " (macro F1).",
         fontsize=9.5, color=INK2)
fig.savefig(os.path.join(KT, "figures", "k08_ml_landuse.png"), dpi=160, facecolor=SURF, bbox_inches="tight")
print("wrote k08_ml_landuse.png")
