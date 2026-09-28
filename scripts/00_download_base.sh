#!/bin/sh
# Base inputs shared by every step: the Geofabrik OpenStreetMap extract for Uganda, HDX COD-AB
# district boundaries, CHIRPS daily rainfall 2006-2025 (clipped to Uganda) and Natural Earth
# 1:10m lakes. Skips files already present. Other inputs are fetched by 03 and 04 (buildings,
# elevation) and 09 (GHSL).
set -e
cd "$(dirname "$0")/../data"
get() { [ -s "$2" ] || curl -sSfL --retry 3 -o "$2" "$1"; echo "$2 ok"; }
get https://download.geofabrik.de/africa/uganda-latest.osm.pbf uganda-latest.osm.pbf
if [ ! -s uga_districts.geojson ]; then
  get https://data.humdata.org/dataset/6d6d1495-196b-49d0-86b9-dc9022cde8e7/resource/4a409743-e1b7-40d7-ad05-e08920f4b099/download/uga_admin_boundaries.geojson.zip admin.zip
  unzip -o -q -j admin.zip uga_admin2.geojson && mv uga_admin2.geojson uga_districts.geojson && rm admin.zip
fi
if [ ! -s ne_lakes/ne_10m_lakes.shp ]; then
  get https://naciscdn.org/naturalearth/10m/physical/ne_10m_lakes.zip ne_lakes.zip
  unzip -o -q ne_lakes.zip -d ne_lakes && rm ne_lakes.zip
fi
python3 ../scripts/00_download_chirps.py 2006 2025
