# Kampala mass transit: where would BRT or light rail make sense? (third study)

Greater Kampala's roads screened for bus rapid transit (BRT) and light rail from open data. The study combines roadside land use, the space between building lines, network design and access equity, with satellite and GIS cartography. Peak road speeds are unknown and no survey is possible now, so congestion is swept rather than assumed.

## Pipeline (run in order)

| Script | Does | Writes |
|---|---|---|
| `k01_screen.py` | Road network (OSM, 3,580 segments split at junctions); peak speeds lowered by roadside friction (GHSL 2020); gravity demand from residents (WorldPop 2025) to built-up floor area; person-trip load on every road | `outputs/edges.gpkg`, `zones.csv`, `corridors.csv` |
| `k02_maps.py` | Corridor ranking within 20 km of the centre; load map, candidates, street-level close-ups | `outputs/corridors_core.csv`, `figures/k01`–`k03` |
| `k03_buildings.py` | All 2.39 million Open Buildings footprints in Greater Kampala | `data/` (not committed) |
| `k04_clearance.py` | **Option 1:** clear width between building lines every 100 m (2,347 cross-sections); buildings inside a 24 m or 30 m corridor; the land use of the frontage and of every building affected | `outputs/clearance.csv`, `demolitions_by_landuse.csv`, `clearance_sections.gpkg` |
| `k05_scenarios.py` | Each candidate alone as BRT (22 km/h) or light rail (28 km/h), at four congestion levels | `outputs/scenarios.csv` |
| `k06_figures.py` | Break-even, access by line, clearance | `figures/k04`–`k06` |
| `k07_landuse.py` | **Land-use patterns** in 250 m cells from footprints (density, median size, coverage) and OSM land use: wetland/water, commercial/industrial, institutional, dense small-plot, planned/larger-plot, peri-urban, rural | `outputs/landuse_cells.parquet`, `landuse.tif`, `landuse_summary.csv` |
| `k08_ml_landuse.py` | **Machine learning:** a random forest on building form and satellite-image features (Esri, zoom 15), trained on OSM-labelled cells with open water left out, and tested with 2.5 km spatial cross-validation: 84% accuracy, macro F1 0.61 (form alone 0.52). SHAP splits its decisions 48% form, 52% imagery. A Gaussian mixture on residential cells is the unsupervised check; the class probabilities are kept for k13 | `outputs/ml_landuse_cv.csv`, `ml_landuse_cv_best.csv`, `ml_shap.csv`, `figures/k08_ml_landuse.png` |
| `tnet.py` | Shared network model: transit lines as their own layer, transfers through road nodes, access within 45 minutes, Gini, gains by land-use group | |
| `k09_networks.py` | **Networks:** two networks grown corridor by corridor, one for time saved per km (efficiency) and one for access gained by residents of dense small-plot settlement per km (equity); both tested as BRT and light rail at every congestion level | `outputs/network_steps.csv`, `networks.csv`, `network_zone_access.parquet` |
| `k10_equity.py` | **Equity:** gains by land use and distance from the centre, Lorenz curves, gain against today's access | `outputs/equity.csv`, `figures/k10_equity.png` |
| `k12_appraisal.py` | **Costs and benefits:** capital, resettlement per displaced building and O&M against time savings; 2,000 draws, 12% discount rate, 25 years | `outputs/appraisal.csv`, `figures/k12_appraisal.png` |
| `k13_uncertainty.py` | **Land-use uncertainty:** 500 draws of every cell's class from the classifier's probabilities, carried into displacement and equity | `outputs/uncertainty_displacement.csv`, `uncertainty_equity.csv`, `figures/k13_uncertainty.png` |
| `k11_satmaps.py`, `satmap.py` | **Satellite and GIS maps** (Esri World Imagery, cached): networks, land use with satellite close-ups, pinch points at street level, access gain | `figures/s01`–`s04` |

The congestion levels are roads at 1×, 1.5×, 2× and 3× the travel time assumed in k01. "Central" in what follows means 2×.

## Results

**Land use (k07).** 52% of residents live in planned or larger-plot areas, 19% peri-urban, 15% in dense small-plot settlement (the pattern of unplanned, informal settlement: 35 or more buildings per hectare, median footprint under 70 m²), 8% rural and 4% in wetland cells.

**Option 1: room, and who would be moved (k04).**
- The Northern Bypass has room almost everywhere: fewer than 1 building per km lies inside a 24 m corridor.
- Masaka, Jinja, Entebbe and Hoima/Nansana roads would lose 10–14 buildings per km. Most of them stand in planned areas, but 33–87 per road stand in dense small-plot settlement.
- Bwaise on Bombo Road would lose 38 per km, 143 of its 210 in dense small-plot settlement.
- Kireka Road would lose 95 per km, 268 in dense small-plot settlement and 79 in wetland.
- The pinch points (`s03`) show these stretches on satellite imagery.

**Single lines (k05).** At the assumed speeds no line saves time. At central congestion each radial saves about 2–3% of all trip time; Entebbe Road and Nansana–Busunju Road do best. Light rail saves 10–20% more than BRT on the same line.

**Networks (k09).** Greedy growth, at central congestion:
- **Efficiency network:** Bombo Road (Bwaise), Hoima/Nansana Road, Entebbe Road, Ggaba Road, Masaka Road and Gayaza Road, 102 km. As BRT it saves 9.7% of all trip time, rising to 16.4% at 3× congestion.
- **Equity network:** the same corridors, except Kireka Road in place of Entebbe Road, 82 km. It saves 7.3%.
- The two objectives nearly coincide, because the dense settlements lie along the busiest radials.
- **The network is worth more than its lines.** Lines that each save 2–3% together save about 10%, since travellers transfer between them.
- **The Northern Bypass is not chosen.** Its general lanes already run at 40 km/h.

**Equity (k10).** With the efficiency BRT network:
- **By land use:** residents of dense small-plot settlement gain the most reachable jobs and services (+19%). Planned areas gain +18%, peri-urban +14% and rural +11%.
- **By distance:** homes 10–15 km out gain most (+25%), and homes beyond 20 km gain only +5%.
- **Spread of access:** the network does not make access more even. The Gini rises slightly, from 0.470 to 0.477. Central and radial residents gain; the fringe is left out unless the lines reach it.

**Would it pay (k12)?** At central congestion the efficiency BRT network has a benefit–cost ratio of 1.33 (5–95% range 0.65–2.57), above one in 74% of draws, for about US$ 1.1 billion including resettlement. It does not pay at 1.5× congestion (0.48) and pays clearly at 3× (3.3). Entebbe Road and Nansana–Busunju Road alone reach about 1.5 and make natural first phases. Light rail on the network (about US$ 3.6 billion) pays only at 3× congestion (1.1). Benefits are time savings only.

**Paper:** `paper/kampala_transit_paper.docx` (source `paper/kampala_transit_paper.md`, built with `tools/build_paper.py`).

**Uncertainty (k13).** The key results survive the classifier's errors. Dense small-plot settlement holds 15% of residents (draws 14.6–15.1%), and its access gain is +18.6% (18.5–18.8%). The network's 24 m corridors contain 432 buildings in dense settlement (406–436). The split between peri-urban, rural and wetland at the city's edge is uncertain.

Google's satellite embeddings (`k08a_embeddings.py`) were tried but not used: Earth Engine could not average them to the 250 m grid within its memory and time limits. They remain future work.

## Limits

- **No speed data.** Peak speeds are assumptions shaped by friction, which is why congestion is swept rather than assumed.
- **Demand is an index, held fixed.** It is a gravity model from population and built-up floor area, not a travel survey, and no mode shift is modelled.
- **Land-use classes come from building form.** "Dense small-plot" describes the pattern, not tenure; deciding who must be compensated needs cadastral and settlement data.
- **Clear width is measured between footprints.** It ignores walls, utilities, drainage and land ownership.
- **No cost-benefit yet.** Costs per km (DART in Dar es Salaam, Nairobi BRT) are the next input.

## What makes the study novel

1. **Roadside land use as a transit design constraint.** The clear width between buildings is measured every 100 m across a whole African city from open footprints. Each pinch point is classed by land use, so the demolition and resettlement burden of each corridor is known before design.
2. **Congestion as the unknown, not an assumption.** The study reports the congestion level at which each line or network pays off; any future speed data or survey can then confirm or reject it.
3. **Designing networks, not appraising lines.** Greedy network growth under two objectives shows that the network roughly triples what its lines save alone, and that efficiency and equity largely agree in Kampala.
4. **Equity for minibus-taxi users by settlement type.** Gains are measured for residents of dense small-plot settlement, by distance and as a Lorenz/Gini shift. They show who gains and who is left at the fringe.
