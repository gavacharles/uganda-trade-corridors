# Substack: Leaving the capital

**Cover:** media/cover_regional.png (1200 × 630)
**Subtitle:** I followed 54 main roads out of 12 African capitals and trade hubs. East Africa's have become linear towns, and they cost a truck twice the time.

---

A truck leaving Nairobi for the Ugandan border at Malaba loses about 197 minutes to the roadside over the first 440 km. That is three and a quarter hours spent braking for markets, humps, junctions, weighbridges and police posts, and climbing hills, compared with the same trip on an empty open road. A truck leaving Pretoria for the Zimbabwean border at Beitbridge, over the same distance, loses 82.

[media: rx1_two_corridors.mp4]

Both are paved trunk roads, both carry heavy freight, and both cross borders at the end. The difference is what has been built along them. Over those 440 km, the Kenyan truck passes about 73,000 buildings within 100 m of the road. The South African truck passes about 8,900.

Earlier this year I measured this on Uganda's five trade corridors out of Kampala ([link to the Uganda piece]). The obvious next question was whether Uganda is unusual. So I ran the same method on every main road leaving twelve hubs in ten countries.

## The roads

The hubs are five in East Africa (Kampala, Nairobi, Kigali, Dodoma and Dar es Salaam) and seven in Southern Africa (Pretoria, Johannesburg, Gaborone, Harare, Lusaka, Maputo and Windhoek). I didn't choose the roads by hand. A script follows every numbered national route that passes within 8 km of each hub's centre to its end or to the border. That gives 54 roads and about 15,000 km. For a fair comparison I use the first 200 km of every road; the main freight routes I also follow their whole length.

Each road is cut into 500 m pieces, about 30,700 in all. For every piece I measured, from open data:

- the buildings beside it (Google's Open Buildings);
- the junctions, signals, crossings, humps, police posts and weighbridges (OpenStreetMap);
- the hills (satellite elevation);
- the rain (20 years of daily satellite rainfall);
- the people living within 300 m (GHS-POP).

A travel-time model, the same one I used for Uganda, turns all of this into minutes for a loaded truck. It is run a thousand times over the range of every assumption.

## Twice the delay

[media: rx3_country_ranking.mp4]

The median East African road costs a loaded truck 35 minutes per 100 km. The median Southern African road costs 18. By country, Rwanda (47), Mozambique (42), Kenya (38) and Uganda (35) are slowest, and Namibia (15) and Zimbabwe (12) fastest.

The worst trade corridors are the two roads to Malaba from either side of the Kenya–Uganda border: Kampala–Malaba at 58 minutes per 100 km and Nairobi–Malaba at 45. These are the heart of the Northern Corridor, the busiest transit route in East Africa. The fastest are Harare–Beitbridge (6) and Windhoek–Walvis Bay (7).

## Linear towns

[media: rm01_road_types.png]

The reason is not the asphalt. It is that East Africa's main roads have become linear towns. About two-thirds of their length now runs through roadside settlement or town: continuous roofs, markets, taxi stages and a side road every few hundred metres. In Southern Africa it is about a third, and outside the cities most roads still cross open country.

East African roads have a median of 155 buildings within 100 m per km of road; Southern African ones have 34. Across all 54 roads, roadside building alone tracks lost time closely (a correlation of 0.73). Where a Southern African road does run through dense settlement, as from Maputo to the border or from Lusaka to Chirundu, it loses time like an East African one.

And it is getting more so:

[media: rx2_roadside_growth.mp4]

Built-up land within 300 m of the East African roads grew by about half between 2000 and 2020; in Southern Africa, by about a third. Most of it is in the villages between towns, not in the towns.

## What slows the trucks

The mix of causes differs too. In the East it is roadside activity, speed humps, weighbridges and hills. Kenya's weighbridges stand out, and in Rwanda it is the hills. In the South, signals and crossings account for a third of the delay. Johannesburg's road to Rustenburg is the slowest single road in the study, a signalised urban road for most of its first 200 km.

There is a catch here, and I want to be upfront about it. OpenStreetMap, the open map I use for signals, crossings and checkpoints, is mapped in great detail in South Africa and patchily in East Africa. Ugandan and Tanzanian towns have traffic lights and zebra crossings too; far fewer of them are on the map.

[media: rm06_controls.png]

So part of the "signals" story in the South is a mapping story. That is why the headline comparison leans on buildings, junctions and hills, which come from satellite imagery the same way everywhere.

## Fuel, carbon and people

Every slow-down costs diesel to speed back up. The friction costs a loaded truck about 11 extra litres per 100 km on East African roads and 9 in the South. That is between a fifth and a third of its fuel.

The roadside is also where people are. About 1,200 people live within 300 m of every km of East African main road, against 270 in Southern Africa. Most of the risk is not in the towns, where the speed limit and the crowds slow trucks down. It is in the villages between them, where trucks still run at close to open-road speed past homes, schools and markets. Per km, East African roads carry about 2.5 times the road-safety exposure.

[media: rm03_exposure.png]

## What it means

Most investment in African trade corridors goes to borders, ports and pavements. Those matter: a truck still spends far longer waiting at a border or in a rest stop than it loses on the road. But the moving part of the trip is not free, and in East Africa it is getting slower as the roadside fills in.

Three things would help:

1. **Treat the worst stretches.** Service roads, bus and taxi bays and protected crossings near schools take local life off the through lane without raising truck speed through villages.
2. **Plan the frontage.** Bypasses and new roads attract the same settlement unless land along them is planned.
3. **Fix the control points.** Weigh-in-motion at weighbridges and an end to routine police stops save as much time per trip as long lengths of new road, at a fraction of the cost.

Southern Africa's problem is different: its slow roads are its metropolitan exits. There, freight routing around the cities and signal priority on freight routes would do more.

## The fine print

- The travel-time model was built and checked in Uganda. Its assumptions are applied everywhere, so absolute minutes may be off elsewhere; the comparisons are what I would trust.
- Congestion is not modelled. These are light-traffic numbers.
- Speed humps are assumed in towns, because almost none are mapped.
- One truck count is used for every road, so I don't compare yearly totals.

The full paper, with maps of every country, and all the code and data are open: https://github.com/gavacharles/uganda-trade-corridors.

If you work on any of these corridors and have traffic counts, hump inventories or checkpoint stop times, I'd love to hear from you: they would sharpen the numbers for your country.
