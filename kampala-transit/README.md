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

## Second pass (`k03`–`k06`)

- **k03_buildings.py:** all 2.39 million Open Buildings footprints in Greater Kampala (kept in `data/`, not committed).
- **k04_clearance.py:** the clear width between building lines every 100 m along the candidates (2,347 cross-sections), and the buildings inside a 24 m or a 30 m corridor. The results are in `outputs/clearance.csv` and `figures/k06_clearance.png`.
- **k05_scenarios.py:** each candidate as a BRT line (22 km/h) or light rail (28 km/h) in its own lane, on the same network. There is no data on peak road speeds, so road congestion is swept: roads at 1×, 1.5×, 2× and 3× the assumed travel time. The script reports trip time saved, and the change in jobs (floor area) reachable in 45 minutes for everyone and for the 40% with the least access. The results are in `outputs/scenarios.csv`, `figures/k04_breakeven.png` and `figures/k05_access.png`.

**What it shows**
- **No single line saves much.** On its own, each radial saves 2–3% of all trip time when roads run at half the assumed speed. **A five-line BRT network** (Northern Bypass with Jinja, Masaka, Entebbe and Hoima roads) saves about 10% at that congestion and 16% at a third of the speed. The gain comes from the network, not from any one corridor.
- **Congestion decides the case.** At the assumed speeds, every line saves under 1%. The case rests on how slow the roads really are at peak, which is the number Kampala lacks.
- **Light rail beats BRT by only 10–20% in time saved** on the same alignment. That is not enough to pay for the difference in cost.
- **There is space, but not everywhere.** Masaka, Jinja and Entebbe roads would lose 10–13 buildings per km for a 24 m corridor, and the Northern Bypass almost none. Bwaise on Bombo Road, Mbogo Road and Kireka would lose 38–95 buildings per km.
- **Equity ranks the lines differently.** Gayaza and Entebbe roads raise access most for the 40% with the least access today. Masaka and Jinja roads raise it most on average.
- **The Northern Bypass:** at 40 km/h, its general lanes are already faster than a BRT line. It earns its place only as part of a network, or if its traffic slows.

## Limits

- There is no traffic speed data. Speeds are assumptions shaped by friction, which is why congestion is swept rather than assumed.
- Demand is a gravity index from population and built-up land, not a travel survey or a count of minibus-taxi passengers. It is held fixed, so no mode shift is modelled.
- Clear width is measured between building footprints. It ignores walls, utilities and land ownership.

## A novel study: proposal

**Working title:** *Where the roadside decides: open-data screening of BRT and light rail for a minibus-taxi city.*

The novelty lies in four things, together:

1. **Ribbon development as a transit design constraint.** Most screening uses demand alone. This study measures the clear width between building lines every 100 m from footprints and turns it into land take and demolitions per km, city-wide, from open data.
2. **Congestion as a swept unknown, not an assumption.** With no speed data, the study reports the congestion level at which each line or network breaks even. A short GPS or taxi-app survey can then confirm or reject it, which makes the question one that can be answered cheaply.
3. **Network over corridor.** Lines appraised one at a time look weak; as a network they save four to five times more. The study would test this with a proper network design rather than single lines.
4. **Access equity for minibus-taxi users.** The study measures the gain for the 40% of residents with the least access, not only the average. Corridors rank differently on the two.

To strengthen it: peak speeds (GPS traces or a few weeks of traffic data), minibus-taxi routes and stages (Digital Transport for Africa GTFS where it exists), KCCA counts or a travel survey for calibration, the metre-gauge commuter-rail plans, and costs per km from Dar es Salaam's DART and Nairobi's BRT.
