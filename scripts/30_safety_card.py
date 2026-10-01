"""Social card: where the road-safety risk sits (from 19_safety.py and 25_black_spots.py).

For each corridor, the share of people living within 300 m who live in roadside settlements
between towns, against the share of the exposure index (people x trucks x (speed/50)^4) that
falls there: settlements hold more of the risk than of the people, because trucks still run at
55-60 km/h through them. Writes figures/s1_safety_card.png (1600 x 900).
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config as C
from cartography import INK, INK2, SURF

SB = pd.read_csv(os.path.join(C.OUTPUTS, "safety_by_type.csv"))
st = SB[SB.road_type == "roadside settlement"].set_index("corridor").reindex(list(C.CORRIDORS))
people = SB.people.sum()
SS = pd.read_csv(os.path.join(C.OUTPUTS, "safety_schools.csv"))
BM = pd.read_csv(os.path.join(C.OUTPUTS, "black_spots_matched.csv"))

fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=SURF)
fig.text(0.05, 0.89, "The risk sits in the villages between towns", fontsize=30, color=INK, fontweight="bold")
fig.text(0.05, 0.835, f"Five trade roads out of Kampala · {people / 1e6:.1f} million people live within 300 m",
         fontsize=15, color=INK2)
ax = fig.add_axes([0.15, 0.16, 0.45, 0.56])
y = np.arange(len(st))[::-1]
ax.barh(y + 0.2, st.people_share * 100, height=0.36, color="#d9a441", label="share of the people living by the road")
ax.barh(y - 0.2, st.exposure_share * 100, height=0.36, color="#b8491c", label="share of the road-safety exposure")
for yi, (c, r) in zip(y, st.iterrows()):
    ax.text(r.people_share * 100 + 1, yi + 0.2, f"{r.people_share:.0%}", va="center", fontsize=13, color=INK)
    ax.text(r.exposure_share * 100 + 1, yi - 0.2, f"{r.exposure_share:.0%}", va="center", fontsize=13, color=INK,
            fontweight="bold")
ax.set_yticks(y)
ax.set_yticklabels([f"{C.CORRIDORS[c]['short']} road" for c in st.index], fontsize=14, color=INK)
ax.set_xlim(0, 100)
ax.set_xticks([])
for s_ in ax.spines.values():
    s_.set_visible(False)
ax.tick_params(length=0)
ax.set_facecolor(SURF)
ax.legend(loc="lower left", bbox_to_anchor=(-0.22, 1.02), frameon=False, fontsize=12, labelcolor=INK2, ncol=2)
fig.text(0.15, 0.11, "Both bars: the part in roadside settlements between towns", fontsize=12, color=INK2)
x0 = 0.66
facts = [("55–60 km/h", "trucks still run through the\nsettlements between towns"),
         (f"{len(SS)}", "half-km stretches with a school,\ntrucks above 50 km/h, no mapped crossing"),
         (f"{int(BM.matched.sum())}", "police-named crash black spots\nplaced in busy trading centres")]
for i, (big, t) in enumerate(facts):
    yy = 0.7 - i * 0.2
    fig.text(x0, yy, big, fontsize=34, color="#b8491c", fontweight="bold")
    fig.text(x0, yy - 0.075, t, fontsize=13, color=INK, linespacing=1.3)
fig.text(0.05, 0.035, "Exposure = people within 300 m × trucks a day × (truck speed / 50)⁴: a ranking of where crashes "
         "would hurt most, not a crash count. Open data; github.com/gavacharles/uganda-trade-corridors",
         fontsize=10, color=INK2)
out = os.path.join(C.FIGURES, "s1_safety_card.png")
fig.savefig(out, dpi=100, facecolor=SURF)
print("wrote", out)
