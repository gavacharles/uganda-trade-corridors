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
- *Trade corridors*: the main freight routes run their full length inside the country. They are pinned by hub, route number and end point (the `PINNED` list in `scripts/discover_arteries.py`). Examples are Nairobi–Mombasa and Nairobi–Malaba, Dar es Salaam–Tunduma, Johannesburg–Durban, Pretoria–Beitbridge, Lusaka–Nakonde and Windhoek–Walvis Bay. Kampala's four are the Uganda study's corridors.

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
