# Leaving the capital (second paper, in progress)

How much do the main roads out of East African capitals lose to roadside friction, controls and terrain, and how does that compare with Southern Africa? This paper runs the Uganda study's open-data method (`../scripts`) on every major road leaving eleven capitals and trade hubs.

**Hubs.**

| Region | Hubs |
|---|---|
| East Africa | Kampala, Nairobi, Kigali, Dodoma, Dar es Salaam |
| Southern Africa | Pretoria, Johannesburg, Gaborone, Harare, Lusaka, Maputo, Windhoek |

Dar es Salaam is included next to Dodoma because most Tanzanian trade roads leave from the port city. Pretoria and Johannesburg are treated as separate hubs.

**Which roads.** Every national route (motorway, trunk or primary road with a route number) that passes within 8 km of the hub's centre, followed along that number to its end, bridging short untagged gaps. A route leaving the city in two directions counts as two arteries. Each artery is cut at the national border. Routes shorter than 100 km are left out. Countries tag their roads differently (Uganda's A roads are mostly "primary", Kenya's B roads "trunk"), so all three classes count. Routes whose number starts outside the city are not arteries under this definition; Nairobi–Garissa (A3, which begins at Thika) is one example.

**How far.**
- *Headline comparison*: the first 200 km of every artery, the same length everywhere.
- *Trade corridors*: the main freight routes run their full length inside the country. They are pinned by hub, route number and end point (the `PINNED` list in `scripts/discover_arteries.py`). Examples are Nairobi–Mombasa and Nairobi–Malaba, Dar es Salaam–Tunduma, Johannesburg–Durban, Pretoria–Beitbridge, Lusaka–Nakonde and Windhoek–Walvis Bay. Kampala's five are the Uganda study's corridors.

**Method.** Same pieces, causes, travel-time model, Monte Carlo, scenarios, reliability and safety exposure as the Uganda study. The difference is that road types are clustered jointly across all hubs, so "roadside settlement" means the same thing everywhere.

**How to run.**

```
python scripts/discover_arteries.py --list      # check the arteries found, write nothing
python scripts/discover_arteries.py             # write data/arteries.json and data/corridors.gpkg
python run.py 02 03 04 05                       # centrelines, buildings, elevation, OSM features
python run.py 00 -- 2006 2025                   # CHIRPS rain for the study box
python run.py 06 08 09 10 16 17 18 19 20        # pieces, road types, growth, model, extensions
python scripts/compare.py                       # East against Southern: tables and figures c01-c04
```

`run.py` runs the shared scripts in `../scripts` with this folder's `scripts/config.py`, so every input and output stays under `regional-corridors/`. `data/` is not committed. It holds the Geofabrik extracts for ten countries, Natural Earth borders, Open Buildings, Copernicus DEM, GHSL, CHIRPS and WorldPop.

**Status.** Arteries are discovered for eleven hubs, and the pipeline and comparison (`scripts/compare.py`) are running. Gaborone waits for the Botswana extract: Geofabrik was refusing downloads, and the mirror has no Botswana file. The write-up is still to come.

**Known limits so far.**
- Truck counts per artery are not available across ten countries. Annual costs are therefore not compared; per-truck and per-km measures are.
- No published trip times have been collected yet to validate the model outside Uganda.
- The model's assumptions (speeds, stop times) are the Uganda study's. South Africa's toll plazas are not yet a cause in the model.

## Figures

Made by `scripts/figures.py` (after `run.py ... 26` and `scripts/compare.py`); every rate is per 100 km of road or per km, so long and short roads compare.

| File | Shows |
|---|---|
| `figures/r01_study_area.png` | The 54 arteries out of 12 hubs; trade corridors full length; Gauteng inset |
| `figures/r02_delay_by_cause.png` | Truck minutes lost per 100 km by cause, per hub, East against Southern |
| `figures/r03_bottlenecks_east.png`, `r03_bottlenecks_southern.png` | The worst 2 km stretches: where the road itself costs most, and weighbridges (assumed ~10 min each); Gauteng inset |
| `figures/r04_safety.png` | Exposure per km; settlements' share of people vs share of exposure; school stretches with fast trucks and no mapped crossing |
| `figures/r05_fuel_co2.png` | Extra diesel and CO₂ per 100 km by cause, and the share of trip fuel burnt by stop-and-go |
| `figures/r06_trade_corridors.png` | The main freight routes side by side: minutes, diesel and exposure per km |
| `figures/r10_country_<iso>.png` | One sheet per country: roads coloured by delay, bottlenecks pinned, causes per road |
| `figures/c01`–`c04` | The East–Southern comparison from `compare.py` |
| `figures/countries/<iso>/01`–`12` | The paper-1 figure families one country at a time (`figures_by_country.py`): typology, growth, causes, hotspots map, scenarios, costs, reliability, safety, fuel and CO₂, waterfall, rank stability, strip maps |
| `figures/compare/k01`–`k09` | Country against country, one dot per road with the country median: delay, roadside, growth and controls, safety, fuel and CO₂, cost and reliability, fixes, cause mix, road types |
| `figures/by_hub/<hub>_1`–`_4` | Every road in its own panel (`figures_by_hub.py`): km-by-km profile, causes, safety and fuel along the road, rain by month and fixes |
| `figures/closeups/c_<iso>.png`, `closeups/<iso>/` | 4 km close-ups of the worst stretches per country, as paper 1's m03 (`closeups.py`): buildings at footprint size, joining roads, water, controls; at most two weighbridges per country |

The shared scripts' all-roads figures (`f02`–`f16`, `g01`–`g03`) are deleted by `run_all.sh`: with 54 roads they cannot be read. The country, hub and close-up sheets replace them.

Caveats that the figures carry: signals, crossings, humps, police posts and weighbridges come from OSM, mapped far more densely in South Africa (and schools in Uganda); speed humps and stop times are assumptions; trucks per day are one assumed figure for every artery; population is GHS-POP 2025.
