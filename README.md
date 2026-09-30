# Highways that became high streets

What slows Uganda's main trade corridors, how much each cause costs in travel time, how fast the roadside has been built up, and where fixes would save the most time. Open data only.

## Paper summary

**Question.** Uganda's trade corridors double as village and town high streets. Which features of the roadside and the road (trading centres, joining roads, controls, hills, water crossings, rain) slow traffic, by how much, where, and how quickly are they spreading?

**Corridors.**

| Corridor | OSM route | Length | Leads to |
|---|---|---|---|
| Kampala → Jinja → Malaba (Kenya border) | A1 | 216 km | Northern Corridor to Mombasa |
| Kampala → Gulu → Elegu (South Sudan border) | A6 | 431 km | Juba; Gulu logistics hub |
| Kampala → Masaka → Mbarara → Katuna (Rwanda border) | A2 | 426 km | Kigali, Central Corridor |
| Kampala → Hoima | A9 | 194 km | Albertine oil region |

**Data.** OpenStreetMap (routes, junctions, controls, water), 1.25 million Google Open Buildings footprints within 1 km of the roads, GHSL built-up surface 2000–2020 (with its 2025–2030 projection), Copernicus 30 m elevation, CHIRPS rainfall, Sentinel-2 imagery for an experimental truck index, and public trip times for validation. No traffic feeds, project records or surveys.

**Approach.** Each corridor is cut into 500 m pieces with every measurable cause attached. Pieces are grouped into road types (open road, roadside settlement, town) by clustering. A transparent travel-time model for a car and a loaded truck turns causes into minutes, with 1,000 Monte Carlo draws over every assumption; switching one cause off at a time gives the minutes it adds. The model is checked against routing estimates and bus timetables, and the ten worst 2 km stretches on each road are mapped with their causes.

**Main findings (light traffic; congestion not modelled).**
- The model reproduces independent routing estimates of trip time (Kampala to Gulu 266 vs 286 min, to Kabale 344 vs 345, to Hoima 164 vs 172). Observed Kampala–Jinja trips (2–3 h) far exceed the model (about 1.5 h): that gap is congestion at the Kampala end.
- Roadside activity is the largest steady cause of delay for cars on the Gulu, Katuna and Hoima roads. On the Jinja road, signals, crossings and assumed speed humps compete with it, and the ranking depends on assumptions.
- For trucks, the five weighbridges (Magamaga, Busitema/Namutere, Luwero, Lukaya, Mbarara) are the largest single delays, if each stop takes around ten minutes.
- Built-up land within 300 m of the road grew 27–68% between 2000 and 2020 (Elegu road +68%, Hoima +57%, Katuna +43%, Malaba +27%), mostly in roadside settlements between towns, where new friction is appearing.
- Most of each corridor is now roadside settlement (58–76% of its length); open road is only 17–34%, and towns 8–22%.
- Rankings are uncertain for trucks: across 1,000 draws, police posts are the largest truck delay on the Elegu road in 56% of draws and weighbridges on the Malaba road in 47% (`outputs/rank_stability.csv`). For cars, roadside activity comes first in 56–98% of draws.

**Extensions (scripts 16–22).**
- *Fixes* (`16`): per truck trip, weigh-in-motion screening saves 8–16 min where there are weighbridges, and ending police-post stops saves 4–15 min. Service roads through every roadside settlement save 10–17 min, but need 125–270 km each. Bypassing the two worst towns saves only 2–5 min in light traffic (congestion relief is not captured). All four together save 29–34 min on the Malaba, Elegu and Katuna roads.
- *Money* (`17`): delay costs heavy trucks about US$42 M a year across the four roads at central values: $19 M on the Malaba road, $14 M Katuna, $7 M Elegu, $2.5 M Hoima. Ranges are wide, because truck counts are sourced only for the Malaba road and time costs are assumed.
- *Reliability* (`18`): from where rain actually fell on each day in 2006–2025, the 95th-percentile day is 5–9% slower than a typical day (buffer index). The Malaba road is slowed on about 87 days a year. The flood-exposure ranking puts the Busitema–Busabi wetland stretch (A1) and Lukaya–Kyoko (A2) first.
- *Safety exposure* (`19`): roadside settlements hold 50–66% of the ~930,000 people living within 300 m of the roads, but 66–81% of the exposure (people × trucks × (speed/50)⁴), because trucks still run at 55–60 km/h there. 545 half-km pieces have a school, trucks above 50 km/h and no mapped crossing within 500 m (an upper bound, since OSM under-maps crossings).
- *Trucks from space* (`21`, `22`): a classifier trained on 321 hand-labelled Sentinel-2 chips reaches 72% precision and 76% recall (cross-validated, AUC 0.92). The fixed threshold reaches 38% precision at the same recall. Density ranks Malaba > Katuna > Elegu > Hoima, matching the traffic ordering, but the candidate step still misses most trucks, so it remains a relative index. Parked-truck clusters cannot be resolved at 10 m.

**Status.** Analysis, extensions, maps and animations complete; write-up not started. A second paper, comparing the roads out of East and Southern African capitals, is in `regional-corridors/`.

**Related repositories.** Companion papers by the same author: `uganda-seasons-construction-delay` (rain and construction delay) and `uganda-rainy-season-access-study` (seasonal access to health care, schools and markets).

## Why this framing

There is no live or historical traffic data we can use: commercial feeds need caveats and permissions, and the public OSM GPS traces on these roads are few and mostly from 2007–2013. So the paper does not watch traffic. It measures the causes of delay from open data, estimates what each costs in travel time, checks the estimates against published trip times, and ranks the stretches where fixes would matter most. This matches the approach of the companion accessibility study.

## Questions

1. Where on each road is travel slowed, and by which causes?
2. How much has the roadside been built up since 2000?
3. Which stretches and which fixes would save the most time?

## Causes measured per 500 m piece

| Group | Measure | Source |
|---|---|---|
| Roadside activity | Buildings within 100 m and 300 m; shops, markets, fuel, schools, stops | Google Open Buildings v3, OSM |
| Access | Major and minor roads joining the corridor | OSM |
| Point controls | Signals, pedestrian and level crossings, speed humps (OSM), police posts, weighbridges (found by name) | OSM |
| Design | Dual or single carriageway, curvature | OSM |
| Terrain | Climb each way, average grade | Copernicus GLO-30 |
| Water | Waterway crossings, wetland share | OSM |
| Weather | Days a year with ≥10 mm rain, 2006–2025 | CHIRPS |
| Pavement (context) | IRI roughness per section, Jinja road and Karuma–Kamdini only | Northern Corridor Transport Observatory report 2022, annex |
| Growth | Built-up land within 300 m, 2000–2020 | GHSL GHS-BUILT-S R2023A |

Not measurable from open data, and reported as limits: congestion, crashes, breakdowns, police checks that happen away from posts, and the true number of speed humps.

## Method

1. **Corridors.** Centreline in each direction = shortest path along the OSM route, with nearby main roads bridging gaps in the route tagging (`01`, `02`).
2. **Pieces.** 500 m pieces with every cause attached (`03`–`06`).
3. **Road types.** K-means on roadside measures; three types by silhouette: open road, roadside settlement, town (`08`).
4. **Growth.** GHSL built-up surface within 300 m, 2000–2020, each cell counted once (`09`).
5. **Travel time.** For a car and a loaded truck, each piece's speed starts at an open-road speed and is reduced by roadside activity, joining roads, a town speed limit, curves and (trucks) hills; fixed delays are added for signals, crossings, assumed speed humps in towns, police posts and weighbridges. Switching one cause off at a time gives the minutes it adds. 1,000 Monte Carlo draws over every assumption give intervals and test whether the ranking of causes holds (`10`). All assumptions and ranges are at the top of `10_travel_time.py`.
6. **Validation.** Model car times against Rome2rio routing estimates and scheduled bus times (`outputs/validation.csv`). The model sits close to the routing estimates and below bus times, as expected for light traffic without stops. The Kampala–Jinja section is where observed trips (2–3 h) most exceed the model (about 1.5 h): that gap is congestion.
7. **Hotspots.** The ten worst 2 km stretches on each road, with their main causes.

## Maps and animations

| File | Shows |
|---|---|
| `figures/m01_study_area.png` | Study area: the four corridors on Uganda, towns, border crossings, weighbridges |
| `figures/m02_bottlenecks.png` | Truck minutes lost per km on every corridor; numbered national hotspots |
| `figures/m03_hotspots.png`, `figures/hotspots/` | 4 km close-ups of each national hotspot: buildings, all OSM roads, water, controls |
| `figures/m04_growth.png` | Fastest-growing 5 km on each road: built up by 2000, and since |
| `figures/m05_atlas_<corridor>.png` | One sheet per corridor: map with ten numbered hotspots, long profile, three close-ups, table of causes |
| `figures/a1_roadside_growth.gif` | Time-lapse 2000–2020 (observed) of roadside building at each corridor's growth hotspot |
| `figures/a1_roadside_growth_to2026_projected.gif` | The same, continued to end-2026 on GHSL's projection (projected years in violet, labelled) |
| `figures/a2_corridor_race.gif` | A truck leaving Kampala on every corridor vs the same truck on open road; roads colour in with delay |
| `figures/a3_bottleneck_tour.gif` | Slideshow of the national hotspots: location and close-up |
| `figures/a4_growth_<corridor>.gif` | One per road: its three fastest-growing 5 km filling in 2000–2020 (observed), above a profile of built-up land along the whole road |
| `figures/a4_growth_<corridor>_to2026_projected.gif` | The same per road, continued to end-2026 on GHSL's projection |
| `figures/f06_trucks.png`, `figures/trucks_check/` | Moving-truck index from Sentinel-2 (experimental), and image chips of the strongest detections for checking by eye |
| `figures/f01_causes_<corridor>.png` | Strip charts of every cause along each road |
| `figures/f02_typology.png`, `f03_growth.png`, `f04_minutes_by_cause.png`, `f05_hotspots.png` | Road types, growth profiles, minutes by cause with intervals (one scale for all roads), excess minutes along each road |
| `figures/f07_scenarios.png` … `f11_trucks_classified.png` | Fix scenarios, annual cost of delay, rain reliability by month, safety exposure along each road, classified truck index |
| `figures/g01_waterfall.png` | How a truck trip grows from open-road time, cause by cause |
| `figures/g02_rank_stability.png` | Share of Monte Carlo draws in which each cause is the largest |
| `figures/g03_strip_maps.png` | Each road straightened into a line: road type, delay, controls, towns, new building |
| `figures/g04_time_map.png` | The corridors redrawn with length proportional to truck travel time |
| `presentation/highways_high_streets.pptx` | Slide deck: background, problem, method, results, discussion |

## Pipeline

Install the packages in `requirements.txt` (Python 3.9) and run each script from `scripts/` (locally, `../.venv/bin/python`). Start with `00_download_base.sh` (OSM extract, district boundaries, CHIRPS 2006–2025, Natural Earth lakes). Corridors are defined once in `scripts/config.py`; every script loops over them.

| Script | Does |
|---|---|
| `00_download_base.sh` | Base inputs: OSM extract, districts, CHIRPS, lakes → `data/` |
| `01_extract_corridors.py` | OSM route ways (and nearby main roads for bridging gaps) → `data/corridors.gpkg` |
| `02_segments.py` | Centrelines both ways → `data/probes.gpkg` |
| `03_download_buildings.py` | Open Buildings within 1 km (incremental: only new areas on re-runs) → `data/buildings.parquet` |
| `04_download_dem.py` | Copernicus GLO-30 tiles → `data/dem/` |
| `05_osm_features.py` | OSM points, roads, waterways, areas, weighbridges by name → `data/osm_features.gpkg` |
| `06_pieces.py` | 500 m pieces → `outputs/pieces.csv`, `data/pieces.gpkg` |
| `07_first_look.py` | Strip charts |
| `08_typology.py` | Road types |
| `09_growth.py` | GHSL growth |
| `10_travel_time.py` | Travel-time model, causes, validation, hotspots |
| `11_maps.py`, `maplib.py`, `cartography.py` | National maps and close-ups; shared map layers and furniture |
| `12_corridor_atlas.py` | Per-corridor sheets |
| `13_animations.py` | Truck race and bottleneck tour GIFs |
| `15_growth_animations.py` | Roadside growth GIFs, observed (2000–2020) and projected (to end-2026) |
| `travel_model.py` | The travel-time model (assumptions, pieces, minutes per piece) shared by `10` and `16`–`19` |
| `16_scenarios.py` | Fix scenarios through the model: weigh-in-motion, no police stops, bypasses, service roads |
| `17_costs.py` | Delay in money: per trip, and per year for trucks (truck counts in `config.TRUCKS_PER_DAY`) |
| `18_reliability.py` | Daily trip times 2006–2025 from CHIRPS rain; flood-exposure ranking of 2 km stretches |
| `19_safety.py` | People near the road (WorldPop 2025), truck speed and crossings: exposure ranking |
| `20_story_figures.py` | Waterfall, rank stability, strip maps, time map |
| `21_truck_candidates.py`, `22_truck_classifier.py`, `s2lib.py` | Truck candidates with image patches; labelling sheets, classifier and calibrated index (labels in `outputs/truck_labels.csv`) |
| `14_trucks.py` | Moving-truck index from Sentinel-2 L2A (Earth Search), 2023–2025, < 10% cloud (experimental; `debug_trucks.py` tests one chunk) |

`poll.py` (live TomTom/HERE collection) is kept but is not part of the plan.

## Known limits

- Annual costs rest on assumed truck counts and time costs (sourced anchor: 8.7 Mt of cargo on Malaba–Kampala in 2017). Replace them with UNRA counts and HDM-4 values before quoting absolute figures. Per-trip minutes do not depend on them.
- Congestion is not modelled. Results describe light traffic; peak-hour delay near Kampala is larger.
- OSM records few speed humps (under 60 within 1 km of all four roads), far below reality; one hump per town piece is assumed, with a 0–2 range.
- Police posts are OSM police stations within 30 m of the road; whether and how long they stop trucks is an assumption (0–5 min).
- Weighbridges are found by name in OSM and each counted once, in the nearest piece: Magamaga and Busitema/Namutere (A1), Luwero (A6), Lukaya and Mbarara (A2). None is mapped on the A9. The Malaba border weighbridge is not named in OSM.
- Lakes are Natural Earth 1:10m; place names on close-ups are OSM place nodes.
- The classified truck index (`22`) rests on 321 chips labelled by one person at 10 m resolution, so the labels are noisy. It still undercounts, because candidates come from a loose threshold that misses most trucks. The original index, described next, is kept for comparison. The original truck index is unsupervised and unvalidated: a simplified version of the band-offset idea in Fisser et al. (2022), with a threshold set on one test chunk (counts at looser and stricter thresholds are kept as a range). Earth Search COGs read without the documented −1000 reflectance offset, although their metadata says it is not applied; the script checks the data. The index is not used in the travel-time model. First results (2023–2025, about six clear scenes per 5 km): 0.01–0.06 candidates per km on average (0.07–0.21 at the looser threshold), well below the roughly 0.7 trucks per km a busy corridor should hold, so it undercounts. A visual check of the strongest candidates (`figures/trucks_check/`) shows plausible moving trucks on open road but false positives from roofs and clutter in towns. Use it, if at all, as a relative index on open-road stretches (`22` now does this with labelled chips).
- OSM has no A6 route tag between roughly Kafu and Kigumba; the centreline follows the untagged main road there. On the A1 near Malaba, one-way tags are ignored because they leave no directed route.
- Copernicus GLO-30 is a surface model; grades are averaged over 500 m to remove rooftop and canopy noise. FABDEM would be better for the final paper.
- Open Buildings v3 reflects imagery from about 2020–2022; change over time comes from GHSL.
- GHSL's observed epochs end in 2020. Its 2025 and 2030 layers are JRC projections from the past trend, and end-2026 is interpolated between them. The projection is much slower than the observed record (+5–9% for 2020–2026 on each road, against, for example, +13.5% in 2015–2020 alone on the Elegu road), so it probably understates recent roadside building. Treat the projected animations as illustrative. Google's Open Buildings 2.5D Temporal (annual to 2023, via Earth Engine) would be the way to observe beyond 2020.
- The ranking of causes is not stable everywhere: on the Kampala end of the A1 it depends on assumed humps and signal delays. The paper should report rankings with their Monte Carlo shares.
