# uganda-trade-corridors

Python pipeline, outputs, figures, paper and web map for measuring what slows Uganda's main trade corridors (roadside building, access roads, controls, design, terrain, water and weather per 500 m piece), what that costs, and where fixes would save the most. Built from open data (OpenStreetMap, Google Open Buildings, GHSL, Copernicus DEM, CHIRPS, Sentinel-2).

Web map: https://gavacharles.github.io/uganda-trade-corridors/ (deployed by `.github/workflows/pages.yml`)

## Layout

| Path | What it is |
|---|---|
| `scripts/` | The pipeline (table below) |
| `inputs/` | Small hand-collected inputs: documented road floods, observatory transit data, police black spots, traffic |
| `outputs/` | Result tables (pieces, causes, costs, scenarios, fuel and CO₂, safety, black spots) |
| `figures/` | Maps, atlases, charts and animations |
| `web/` | Web map data builder (`build_web_data.py`) and generated data |
| `paper/` | Manuscript (Markdown, Word, PDF) |
| `presentation/` | Slide deck and its builder |
| `social/` | Post drafts and media |
| `kampala-transit/`, `regional-corridors/` | Companion analyses, each with its own README |
| `tools/` | Paper builder, tour recorder, screenshot and sync helpers |
| `.env.example` | Environment variables template |

## Setup

```
pip install -r requirements.txt   # Python 3.9
```

Run each script from `scripts/`. Downloaded data goes to `data/` (not tracked).

## Pipeline

| Script | Does |
|---|---|
| `00_download_base.sh`, `00_download_chirps.py` | Base inputs: OSM extract, districts, CHIRPS, lakes → `data/` |
| `01_extract_corridors.py` | OSM route ways → `data/corridors.gpkg` |
| `02_segments.py` | Centrelines both ways → `data/probes.gpkg` |
| `03_download_buildings.py` | Open Buildings within 1 km (incremental) → `data/buildings.parquet` |
| `04_download_dem.py` | Copernicus GLO-30 tiles → `data/dem/` |
| `05_osm_features.py` | OSM points, roads, waterways, areas, weighbridges → `data/osm_features.gpkg` |
| `06_pieces.py` | 500 m pieces → `outputs/pieces.csv`, `data/pieces.gpkg` |
| `07_first_look.py`, `08_typology.py`, `09_growth.py` | Strip charts, road types, GHSL growth |
| `10_travel_time.py`, `travel_model.py` | Travel-time model, causes, validation, hotspots |
| `11_maps.py`, `maplib.py`, `cartography.py`, `12_corridor_atlas.py` | National maps, close-ups and per-corridor atlas sheets |
| `13_animations.py`, `15_growth_animations.py` | Animations |
| `14_trucks.py`, `21_truck_candidates.py`, `22_truck_classifier.py`, `s2lib.py` | Experimental Sentinel-2 moving-truck index and classifier |
| `16_scenarios.py`, `17_costs.py` | Fix scenarios; delay costs |
| `18_reliability.py`, `19_safety.py` | Rain reliability and flood exposure; safety exposure |
| `20_story_figures.py` | Waterfall, rank stability, strip maps, time map |
| `23_rail.py`, `24_transit_gap.py`, `25_black_spots.py`, `26_fuel_co2.py`, `27_growth_temporal.py` | Rail screening, observed transit, black spots, fuel and CO₂, temporal building growth (Earth Engine) |

`poll.py` (live traffic collection) is kept but not used by the pipeline.
