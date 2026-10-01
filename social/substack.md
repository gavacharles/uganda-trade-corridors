# Highways that became high streets

*Uganda's five trade roads out of Kampala now run mostly through villages. Here is what that costs, where, and what would help, measured from open data.*

---

Drive out of Kampala on any of the main roads and you know the pattern. Open road, then a trading centre: boda bodas waiting at the junction, a market on both shoulders, a speed hump, children crossing to school. Then open road again, but shorter each year.

These are Uganda's trade corridors: the A1 to Malaba and the Kenyan border, the A6 north to Elegu and South Sudan, the A2 to Katuna and Rwanda, the A9 to Hoima and the oil region, and the A5 west through Fort Portal and Kasese to Mpondwe and the DR Congo border. Almost everything the country imports and exports moves along them. They were built as highways. Along most of their length, they now also serve as village high streets.

I wanted to know how much that costs, where, and whether it is getting worse. There is no corridor-wide traffic data to watch, so I measured the causes instead, every 500 metres along about 1,700 km of road, using only open data: OpenStreetMap, 1.5 million Google building footprints, satellite records of built-up land, elevation and rainfall. A transparent travel-time model then turns what is on the ground into minutes for a car and a loaded truck, with a thousand random draws over every assumption.

## Most of the road is now a street

Grouping every 500 m piece by what sits beside it — buildings, shops, junctions, schools, taxi stops — gives three kinds of road: open road, roadside settlement and town. Open road is now only 18–36% of each corridor's length. **Between 56% and 74% runs through roadside settlement**, the long belts of trading centres between towns.

*[Animation: five_roads_growth.gif — the fastest-growing 5 km on each road filling in, 2000–2020]*

And it is filling in fast. Built-up land within 300 m of the road grew 27–68% between 2000 and 2020. Yearly satellite building counts show no slowdown since: **22–48% more buildings within 300 m of the roads between 2016 and 2023**. Land a kilometre or two back is filling in too, but the roadside gains roughly twice as many new buildings per square kilometre. Today's open road is tomorrow's trading centre.

## What it costs a truck

*[Animation: x1_truck_race.gif — a loaded truck leaving Kampala on every corridor at once, next to the same truck on open road]*

In light traffic on a dry day, the model puts a loaded truck's trip from Kampala to the border (or to Hoima) at **59 to 161 minutes longer than on open road** — 29–64% extra. Malaba loses about two hours, Katuna nearly three, where hills add to the drag.

*[Animation: a5_bottleneck_pins.gif — the worst 2 km stretches for a loaded truck, pinned one by one]*

The causes differ by road. For cars, roadside activity — the slowing, stopping and turning that comes with a trading centre — is the largest single cause on every corridor. For trucks, the worst single points are the weighbridges. The model assumes about ten minutes per stop; the Northern Corridor Transport Observatory's tracking data put the median weighbridge stop at twelve. You can find every one of these stretches, and every 500 m in between, on the interactive map: https://gavacharles.github.io/uganda-trade-corridors/.

The model checks out against independent trip times: Kampala to Gulu 266 minutes modelled against 286 in routing estimates, Kampala to Kabale 343 against 345. It does not include congestion, which is why Kampala–Jinja trips that really take two to three hours come out at about one and a half.

## The road is not the biggest delay

Here is the finding that surprised me most. Trucks fitted with GPS and electronic cargo seals take **17 to 93 hours** between Kampala and a border, according to the Observatory's 2025–26 reports. The model drives the same distances in five to nine hours. Roadside and control friction is only 2–14% of the real trip. The rest is time standing still: rest and meals, border procedures, security and company checks, breakdowns.

*[Image: transit_gap.png]*

So fixing the road matters — for reliability, fuel and safety — but freight time is won mostly at borders and stops. Crossing at Malaba averaged 48 minutes in 2025. Busia, a few kilometres away, took over two and a half hours.

## Fuel, carbon and money

*[Animation: a6_fuel_meter.gif — the diesel meter on one Kampala–Malaba trip, against the same truck on an open road]*

Every hump, junction and village crossing makes a forty-tonne truck brake and accelerate again. A physical fuel model on the same speed profile puts that at **29–75 extra litres of diesel per loaded trip**, a quarter to two fifths of the trip's fuel. Across the five roads that is roughly US$70 million of diesel and 140,000 tonnes of CO₂ a year, on top of about US$41 million a year in truck time. (Truck counts come from 2025 station surveys on three of the five roads and are assumed on the other two, so treat these totals as orders of magnitude.)

## Where people are at risk

*[Image: s1_safety_card.png — where the road-safety risk sits]*

Towns have speed limits, so trucks slow down there. In the settlements between towns they still run at 55–60 km/h, past homes, schools and stalls. About 1.2 million people live within 300 m of these roads. Weighting each stretch by the people beside it, the trucks passing and the speed they pass at, **65–79% of the exposure falls in the settlement belts** — and 688 half-kilometre stretches have a school, fast trucks and no mapped crossing.

The crash black spots that Uganda Police traffic officers have named on these highways tell the same story. They sit in busy trading centres, with dense roadside building and many joining roads, not on fast open bends.

## What would help

The same model can run fixes and report the minutes they save:

- **Weigh-in-motion screening** at the weighbridges, so only suspected overloads stop: 8–16 minutes per truck trip.
- **Ending routine truck stops at roadside police posts:** 4–15 minutes.
- **Service roads and consolidated access through the settlement belts:** 10–23 minutes, and fewer conflicts with people — but 124–281 km of new road per corridor, so start with the worst 20 km.
- **Bypassing the worst towns** saves little in light traffic (2–4 minutes); its case is congestion and safety.

Beyond the road: cutting stopped time at borders and on the way, and controlling building in the road reserve on stretches that are still open, before they become the next trading centre. And rail? Moving freight off these roads does not pay back on today's Ugandan traffic alone; its case rests on regional transit growth.

## How this was done

Everything comes from open sources: OpenStreetMap, Google Open Buildings (and its 2016–2023 yearly series), the EU's GHSL built-up record, WorldPop, Copernicus elevation and CHIRPS rainfall. Published records — routing estimates, bus timetables, the Northern Corridor Transport Observatory and Uganda Police — are used only to check and scale the results. Congestion, the true number of speed humps and the truck counts on two roads are the main gaps.

The interactive map lets you inspect every 500 m of the five roads: https://gavacharles.github.io/uganda-trade-corridors/. Code and data: https://github.com/gavacharles/uganda-trade-corridors

*Charles Gava is a PhD researcher at the University of Johannesburg.*
