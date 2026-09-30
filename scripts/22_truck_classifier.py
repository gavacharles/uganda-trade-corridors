"""Train a classifier that separates moving trucks from clutter among the candidates of
21_truck_candidates.py, and turn it into a calibrated truck index per 5 km.

  python 22_truck_classifier.py sheets   draws a random order of candidates and renders numbered contact sheets for
                                         labelling by eye, figures/trucks_check/label_sheet_NN.png
  python 22_truck_classifier.py          trains on outputs/truck_labels.csv and applies

Labels (outputs/truck_labels.csv: cand, label) were set by eye on the sheets: 1 = a moving
truck (a short blue, green and red streak in sequence along the road, brighter than the
road), 0 = not a truck (roof, car-sized speck, road edge, cloud edge, field boundary),
unsure chips left out. Labels are single-rater and at 10 m resolution; treat them as noisy.

Model: gradient-boosted trees on the threshold features (blue and red z-scores, sizes,
offset, reflectances, road brightness) plus simple patch statistics (centre-pixel colour
contrasts, NIR, local variance). Evaluated by stratified 5-fold cross-validation; reports
precision, recall and ROC AUC. The fitted model scores every candidate; trucks per km per
chunk = sum of probabilities / road km, averaged over scenes (an expected count, so no
threshold is needed).

Writes outputs/truck_classifier_cv.csv, outputs/trucks_chunks_classified.csv,
figures/f11_trucks_classified.png.
"""
import os, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config as C
from cartography import INK, INK2, SURF

T = os.path.join(C.DATA, "trucks")
CHECK = os.path.join(C.FIGURES, "trucks_check")
LABELS = os.path.join(C.OUTPUTS, "truck_labels.csv")
cand = pd.read_parquet(os.path.join(T, "candidates.parquet"))
cand["cand"] = np.arange(len(cand))
patches = np.load(os.path.join(T, "patches.npy")).astype(np.float32)   # (n, 4, 15, 15): B2 B3 B4 B8
H = patches.shape[-1] // 2

if len(sys.argv) > 1 and sys.argv[1] == "sheets":
    rng = np.random.default_rng(3)
    order = rng.permutation(cand.cand.to_numpy())
    per, n_sheets = 24, int(sys.argv[2]) if len(sys.argv) > 2 else 16
    os.makedirs(CHECK, exist_ok=True)
    for s in range(n_sheets):
        ids = order[s * per:(s + 1) * per]
        fig, axs = plt.subplots(4, 6, figsize=(15, 10.8), facecolor="white")
        for ax, i in zip(axs.ravel(), ids):
            rgb = np.dstack([patches[i, 2], patches[i, 1], patches[i, 0]])[H - 5:H + 6, H - 5:H + 6]
            lo, hi = np.percentile(rgb, 2), np.percentile(rgb, 99.5)
            ax.imshow(np.clip((rgb - lo) / max(hi - lo, 1e-3), 0, 1), interpolation="nearest")
            for xy in ((5, -0.9), (5, 10.9), (-0.9, 5), (10.9, 5)):   # ticks pointing at the candidate pixel
                ax.plot(*xy, marker="s", color="yellow", markersize=4, clip_on=False)
            ax.set_title(f"#{i}", fontsize=11)
            ax.set_axis_off()
        fig.suptitle(f"Truck candidates, sheet {s + 1}: 11 x 11 px (110 m), true colour stretched per chip; "
                     f"ticks mark the candidate pixel", fontsize=11)
        fig.savefig(os.path.join(CHECK, f"label_sheet_{s + 1:02d}.png"), dpi=80, bbox_inches="tight")
        plt.close(fig)
    print(f"wrote {n_sheets} sheets of {per}")
    raise SystemExit

from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: E402
from sklearn.model_selection import StratifiedKFold, cross_val_predict  # noqa: E402
from sklearn.metrics import precision_score, recall_score, roc_auc_score  # noqa: E402


def features(c, p):
    ctr = p[:, :, H, H]
    ring = p[:, :, H - 2:H + 3, H - 2:H + 3].reshape(len(p), 4, -1)
    f = pd.DataFrame({
        "blue_z": c.blue_z, "red_z": c.red_z, "blue_px": c.blue_px, "red_px": c.red_px, "offset_px": c.offset_px,
        "b2": c.b2, "b3": c.b3, "b4": c.b4, "b8": c.b8, "road_bright": c.road_bright, "road_mad": c.road_mad,
        "ctr_minus_road": ctr[:, :3].mean(1) - c.road_bright.to_numpy(),
        "ndvi_ctr": (ctr[:, 3] - ctr[:, 2]) / np.maximum(ctr[:, 3] + ctr[:, 2], 1e-3),
        "ring_blue_range": ring[:, 0].max(1) - ring[:, 0].min(1),
        "ring_red_range": ring[:, 2].max(1) - ring[:, 2].min(1),
        "patch_std": p[:, :3].reshape(len(p), -1).std(1),
        "patch_ndvi": ((p[:, 3] - p[:, 2]) / np.maximum(p[:, 3] + p[:, 2], 1e-3)).reshape(len(p), -1).mean(1),
    })
    return f.to_numpy(dtype=float), list(f.columns)


X, names = features(cand, patches)
lab = pd.read_csv(LABELS)
lab = lab[lab.label.isin([0, 1])]
y = lab.label.to_numpy()
Xl = X[lab.cand.to_numpy()]
print(f"{len(lab)} labelled: {y.sum()} trucks, {len(y) - y.sum()} not")
clf = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=300, l2_regularization=1.0,
                                     class_weight="balanced", random_state=0)
cv = StratifiedKFold(5, shuffle=True, random_state=0)
prob = cross_val_predict(clf, Xl, y, cv=cv, method="predict_proba")[:, 1]
pred = prob >= 0.5
base = (lab.cand.map(cand.set_index("cand").blue_z) > 2.5).to_numpy()   # the fixed threshold of 14_trucks.py
res = pd.DataFrame([
    dict(model="classifier (5-fold CV)", precision=precision_score(y, pred), recall=recall_score(y, pred),
         roc_auc=roc_auc_score(y, prob), n=len(y)),
    dict(model="fixed threshold K=2.5 (14_trucks.py)", precision=precision_score(y, base), recall=recall_score(y, base),
         roc_auc=roc_auc_score(y, lab.cand.map(cand.set_index("cand").blue_z)), n=len(y)),
]).round(3)
res.to_csv(os.path.join(C.OUTPUTS, "truck_classifier_cv.csv"), index=False)
print(res.to_string(index=False))

clf.fit(Xl, y)
cand["p_truck"] = clf.predict_proba(X)[:, 1]
cand.loc[lab.cand.to_numpy(), "p_truck"] = y   # labelled candidates keep their label
cs = pd.read_csv(os.path.join(T, "chunk_scenes.csv"))
e = cand.groupby(["corridor", "chunk_km", "scene"]).p_truck.sum().rename("expected").reset_index()
cs = cs.merge(e, how="left", on=["corridor", "chunk_km", "scene"]).fillna({"expected": 0})
cs["per_km"] = cs.expected / cs.road_km
cs["raw_per_km"] = cs.n_candidates / cs.road_km
ch = cs.groupby(["corridor", "chunk_km"]).agg(scenes=("scene", "size"), trucks_per_km=("per_km", "mean"),
                                              candidates_per_km=("raw_per_km", "mean")).reset_index()
ch.round(4).to_csv(os.path.join(C.OUTPUTS, "trucks_chunks_classified.csv"), index=False)
summ = ch.groupby("corridor")[["trucks_per_km", "candidates_per_km"]].mean().round(3)
print(summ.to_string())

fig, axs = plt.subplots(len(C.CORRIDORS), 1, figsize=(13, 2.8 * len(C.CORRIDORS)), facecolor=SURF,
                        gridspec_kw=dict(hspace=0.8), sharex=True, sharey=True)
for ax, corridor in zip(axs, C.CORRIDORS):
    d = ch[ch.corridor == corridor]
    ax.bar(d.chunk_km + 2.5, d.candidates_per_km, width=4.5, color="#e4e3df", linewidth=0, label="all candidates")
    ax.bar(d.chunk_km + 2.5, d.trucks_per_km, width=4.5, color="#17252a", linewidth=0, label="expected trucks (classifier)")
    for s_ in ("top", "right", "left"):
        ax.spines[s_].set_visible(False)
    ax.grid(axis="y", color="#e4e3df", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(colors=INK2, labelsize=8, length=0)
    ax.set_title(f"{C.CORRIDORS[corridor]['label']}: {d.trucks_per_km.mean():.3f} moving trucks per km on average "
                 f"({d.candidates_per_km.mean():.3f} candidates)", loc="left", fontsize=9.5, color=INK)
axs[0].legend(loc="upper right", frameon=False, fontsize=8.5, labelcolor=INK2)
axs[-1].set_xlabel("km from Kampala", fontsize=8.5, color=INK2)
r = res.iloc[0]
fig.suptitle(f"Moving trucks seen from Sentinel-2, after a trained classifier (cross-validated precision "
             f"{r.precision:.0%}, recall {r.recall:.0%}, {int(r.n)} labelled chips)", x=0.125, ha="left", fontsize=12,
             color=INK)
fig.savefig(os.path.join(C.FIGURES, "f11_trucks_classified.png"), dpi=150, facecolor=SURF, bbox_inches="tight")
print("wrote outputs/truck_classifier_cv.csv, outputs/trucks_chunks_classified.csv, figures/f11_trucks_classified.png")
