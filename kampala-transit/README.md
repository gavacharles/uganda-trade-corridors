# Kampala mass transit: where would BRT or light rail make sense? (third study, first pass)

A first screening of Greater Kampala's roads for bus rapid transit (BRT) and light rail, from open data, reusing the corridor studies' methods. It is a scoping exercise for a full study, not an appraisal.

## First pass (`scripts/k01_screen.py`, `scripts/k02_maps.py`)

1. **Network:** every motorway, trunk, primary, secondary and tertiary road in the box 32.35–32.90 E, 0.02–0.55 N (OSM; 3,580 segments split at junctions). The tolled Entebbe Expressway (M3) is left out of the public-transport network. The Northern Bypass (M20) runs at a peak 40 km/h.
2. **Speeds:** an assumed peak speed per road class (trunk 32, primary 26, secondary 22, tertiary 18 km/h), lowered by roadside friction where the land within about 150 m is built up (GHSL 2020). This is the form of paper 1's travel-time model.
3. **Demand:** about 1.1 km zones (1,886 origins, 6.6 million residents in WorldPop 2025). Trips go from residents to built-up floor area (a proxy for jobs, schools and markets) in an origin-constrained gravity model on network time. Trips under 6 minutes are treated as walked. All trips are routed on fastest paths, giving a **relative** person-trip load on every road, not a count.
4. **Screening:** named roads within 20 km of the centre, by load, length, residents within an 800 m walk, road width in OSM (dual carriageway or 4+ lanes) and the rail reserve. The thresholds are illustrative.

| File | Shows |
|---|---|
| `figures/k01_load_map.png` | Every road by modelled person-trip load, with the railway |
| `figures/k02_candidates.png` | The screened corridors |
| `figures/k03_closeups.png` | Street level (4 km) at the busiest stretch of the top candidates: building footprints, roads, load, rail |
| `outputs/corridors_core.csv` | The ranking |

## First-pass result

- **Northern Bypass (M20):** the strongest single candidate. It carries the most modelled load, has about 21,500 residents per km within walking distance and is already a dual carriageway, so a busway or light rail fits without demolition. As a ring it serves orbital trips, not the radial trips into the centre.
- **Jinja Road (A1):** the strongest radial. Part of it is dual carriageway, and 60% of its core length lies within 500 m of the metre-gauge railway. That raises the question of rail-based commuter service versus a busway beside it.
- **Masaka (A2), Entebbe (A3), Hoima/Nansana (A9), Gulu/Bombo (A6) and Gayaza roads:** high load and dense catchments, but single carriageways lined with buildings. BRT would need land or would have to take lanes from general traffic. The short Bwaise stretch of Bombo Road has the highest load per km of any road.

## Limits of the first pass

- There is no traffic speed data. Speeds are assumptions shaped by friction, so congestion is not measured.
- Demand is a gravity index from population and built-up land, not a travel survey or a count of minibus-taxi passengers.
- Road width comes from OSM tags. The space between building lines, which decides whether a busway fits, is not yet measured.
- Building footprints exist only within 1 km of the five trade corridors. Gayaza Road and the orbital roads need a download (Earth Engine, Open Buildings).
