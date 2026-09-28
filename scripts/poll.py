"""Poll TomTom and HERE for current traffic on both corridors and archive the results.

Run every 5 minutes by the scheduler (scheduling/). Each run polls a source only if
it is due: the interval is set so a full day's polling stays inside that source's
request budget (config.py), and is never shorter than 15 minutes.

  TomTom  Traffic Flow Segment Data, one request per probe point (data/probes.gpkg).
          Returns the speed on the road segment nearest the point.
  HERE    Traffic API v7 flow, one request per ~50 km stretch of centreline. Returns
          every segment in the stretch; each is matched to km-from-Kampala and to a
          direction of travel.

Every response is kept as received in data/raw/<source>/<date>/, and parsed rows are
appended to data/archive/<source>_<YYYY-MM>.csv. Times are stored in UTC and in
Kampala time (UTC+3).

  python poll.py              poll whatever is due
  python poll.py --force      poll both sources now
  python poll.py --dry-run    show what would be requested, without calling the APIs
"""
import argparse, csv, datetime as dt, fcntl, gzip, json, math, os, sys, time
import geopandas as gpd
import requests
from shapely.geometry import LineString, Point
from shapely.ops import substring

import config as C

TOMTOM_URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
HERE_URL = "https://data.traffic.hereapi.com/v7/flow"
MIN_INTERVAL_MIN = 15
HERE_CHUNK_KM = 50
EAT = dt.timezone(dt.timedelta(hours=3))
STATE = os.path.join(C.LOGS, "last_poll.json")

TOMTOM_FIELDS = ["ts_utc", "ts_kampala", "corridor", "direction", "probe_id", "km_from_kampala",
                 "frc", "current_speed_kmh", "free_flow_speed_kmh", "current_travel_time_s",
                 "free_flow_travel_time_s", "confidence", "road_closure", "segment_length_m",
                 "snap_distance_m"]
HERE_FIELDS = ["ts_utc", "ts_kampala", "source_updated", "corridor", "direction", "km_from_kampala",
               "length_m", "description", "speed_kmh", "speed_uncapped_kmh", "free_flow_kmh",
               "jam_factor", "confidence", "traversability", "distance_to_centreline_m"]


def log(msg):
    os.makedirs(C.LOGS, exist_ok=True)
    line = f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M:%S}Z  {msg}"
    print(line)
    with open(os.path.join(C.LOGS, "poll.log"), "a") as f:
        f.write(line + "\n")


def save_raw(source, now, payload):
    d = os.path.join(C.RAW, source, f"{now:%Y-%m-%d}")
    os.makedirs(d, exist_ok=True)
    with gzip.open(os.path.join(d, f"{now:%H%M%S}.json.gz"), "wt") as f:
        json.dump(payload, f)


def append_rows(source, now, fields, rows):
    os.makedirs(C.ARCHIVE, exist_ok=True)
    path = os.path.join(C.ARCHIVE, f"{source}_{now:%Y-%m}.csv")
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------- HERE polyline

_TABLE = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


def _uvar(v):
    out = []
    while v > 0x1F:
        out.append(_TABLE[(v & 0x1F) | 0x20])
        v >>= 5
    out.append(_TABLE[v])
    return "".join(out)


def flexpolyline(latlngs, precision=5):
    """Encode (lat, lng) pairs as a HERE flexible polyline (format version 1, 2D)."""
    m = 10 ** precision
    out, plat, plng = [_uvar(1), _uvar(precision)], 0, 0
    for lat, lng in latlngs:
        ilat, ilng = int(round(lat * m)), int(round(lng * m))
        for d in (ilat - plat, ilng - plng):
            d <<= 1
            out.append(_uvar(~d if d < 0 else d))
        plat, plng = ilat, ilng
    return "".join(out)


# ---------------------------------------------------------------- geometry

def load_geometry():
    cl = gpd.read_file(C.PROBES_GPKG, layer="centrelines")
    pr = gpd.read_file(C.PROBES_GPKG, layer="probes")
    lines = {(r.corridor, r.direction): r.geometry for r in cl.itertuples()}
    lines_utm = {(r.corridor, r.direction): r.geometry for r in cl.to_crs(C.UTM).itertuples()}
    return lines, lines_utm, pr


def to_utm(geom):
    return gpd.GeoSeries([geom], crs=4326).to_crs(C.UTM).iloc[0]


def bearing(p, q):
    return math.degrees(math.atan2(q[0] - p[0], q[1] - p[1])) % 360


def angle_diff(a, b):
    return abs((a - b + 180) % 360 - 180)


# ---------------------------------------------------------------- sources

def interval_min(source, probes):
    if source == "tomtom":
        per_day = C.TOMTOM_DAILY_REQUESTS / max(len(probes), 1)
    else:
        per_poll = sum(math.ceil(l.length / 1000 / HERE_CHUNK_KM)
                       for (c, d), l in LINES_UTM.items() if d == "outbound")
        per_day = C.HERE_MONTHLY_REQUESTS / 31 / per_poll
    return max(MIN_INTERVAL_MIN, math.ceil(24 * 60 / per_day))


def poll_tomtom(now, probes, dry):
    key = os.environ.get("TOMTOM_API_KEY")
    if not key and not dry:
        log("tomtom: TOMTOM_API_KEY not set, skipped")
        return False
    raw, rows = {}, []
    for p in probes.itertuples():
        params = dict(point=f"{p.lat},{p.lon}", unit="kmph", openLr="false", key=key)
        if dry:
            print("GET", TOMTOM_URL, {k: v for k, v in params.items() if k != "key"})
            continue
        r = requests.get(TOMTOM_URL, params=params, timeout=20)
        if r.status_code != 200:
            log(f"tomtom: HTTP {r.status_code} at {p.probe_id}: {r.text[:200]}")
            if r.status_code in (401, 403, 429):
                break
            continue
        js = r.json()
        raw[p.probe_id] = js
        f = js.get("flowSegmentData", {})
        pts = [(c["longitude"], c["latitude"]) for c in f.get("coordinates", {}).get("coordinate", [])]
        seg = to_utm(LineString(pts)) if len(pts) > 1 else None
        probe_utm = to_utm(Point(p.lon, p.lat))
        rows.append(dict(
            ts_utc=f"{now:%Y-%m-%dT%H:%M:%SZ}", ts_kampala=f"{now.astimezone(EAT):%Y-%m-%dT%H:%M:%S}",
            corridor=p.corridor, direction=p.direction, probe_id=p.probe_id,
            km_from_kampala=p.km_from_kampala, frc=f.get("frc"),
            current_speed_kmh=f.get("currentSpeed"), free_flow_speed_kmh=f.get("freeFlowSpeed"),
            current_travel_time_s=f.get("currentTravelTime"),
            free_flow_travel_time_s=f.get("freeFlowTravelTime"), confidence=f.get("confidence"),
            road_closure=f.get("roadClosure"),
            segment_length_m=round(seg.length) if seg else None,
            snap_distance_m=round(seg.distance(probe_utm), 1) if seg else None))
        time.sleep(0.2)  # stay well under the per-second rate limit
    if dry:
        return False
    save_raw("tomtom", now, raw)
    append_rows("tomtom", now, TOMTOM_FIELDS, rows)
    log(f"tomtom: {len(rows)}/{len(probes)} probes")
    return bool(rows)


def match_here(result, corridor):
    """Place one HERE flow item on the corridor: km from Kampala and direction."""
    pts = [(pt["lng"], pt["lat"]) for link in result["location"]["shape"]["links"]
           for pt in link["points"]]
    if len(pts) < 2:
        return None
    seg = to_utm(LineString(pts))
    out = LINES_UTM[(corridor, "outbound")]
    mid = seg.interpolate(0.5, normalized=True)
    dist = out.distance(mid)
    if dist > C.HERE_MATCH_M:
        return None
    s = out.project(mid)
    a, b = out.interpolate(max(s - 20, 0)), out.interpolate(min(s + 20, out.length))
    seg_b = bearing(seg.coords[0], seg.coords[-1])
    direction = "outbound" if angle_diff(seg_b, bearing(a.coords[0], b.coords[0])) < 90 else "inbound"
    return dict(km_from_kampala=round(s / 1000, 3), direction=direction,
                distance_to_centreline_m=round(dist, 1))


def poll_here(now, dry):
    key = os.environ.get("HERE_API_KEY")
    if not key and not dry:
        log("here: HERE_API_KEY not set, skipped")
        return False
    raw, rows, n_req = {}, [], 0
    for (corridor, direction), line in LINES.items():
        if direction != "outbound":
            continue
        L = LINES_UTM[(corridor, direction)].length
        n = math.ceil(L / 1000 / HERE_CHUNK_KM)
        for i in range(n):
            part = substring(line, i / n, (i + 1) / n, normalized=True).simplify(C.HERE_SIMPLIFY_DEG)
            poly = flexpolyline([(y, x) for x, y in part.coords])
            params = {"in": f"corridor:{poly};r={C.HERE_CORRIDOR_RADIUS_M}",
                      "locationReferencing": "shape", "apiKey": key}
            tag = f"{corridor}_{i}"
            if dry:
                print("GET", HERE_URL, f"{tag}: {len(part.coords)} points, "
                      f"{len(params['in'])} characters")
                continue
            r = requests.get(HERE_URL, params=params, timeout=30)
            n_req += 1
            if r.status_code != 200:
                log(f"here: HTTP {r.status_code} for {tag}: {r.text[:300]}")
                if r.status_code in (401, 403, 429):
                    break
                continue
            js = r.json()
            raw[tag] = js
            for res in js.get("results", []):
                m = match_here(res, corridor)
                if m is None:
                    continue
                f = res.get("currentFlow", {})
                kmh = lambda v: round(v * 3.6, 1) if v is not None else None  # noqa: E731
                rows.append(dict(
                    ts_utc=f"{now:%Y-%m-%dT%H:%M:%SZ}",
                    ts_kampala=f"{now.astimezone(EAT):%Y-%m-%dT%H:%M:%S}",
                    source_updated=js.get("sourceUpdated"), corridor=corridor,
                    length_m=res["location"].get("length"),
                    description=res["location"].get("description"),
                    speed_kmh=kmh(f.get("speed")), speed_uncapped_kmh=kmh(f.get("speedUncapped")),
                    free_flow_kmh=kmh(f.get("freeFlow")), jam_factor=f.get("jamFactor"),
                    confidence=f.get("confidence"), traversability=f.get("traversability"), **m))
    if dry:
        return False
    save_raw("here", now, raw)
    append_rows("here", now, HERE_FIELDS, rows)
    log(f"here: {len(rows)} segments from {n_req} requests")
    return bool(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--source", choices=("tomtom", "here"))
    args = ap.parse_args()
    C.load_env()

    os.makedirs(C.LOGS, exist_ok=True)
    lock = open(os.path.join(C.LOGS, "poll.lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return  # the previous run is still going

    global LINES, LINES_UTM
    LINES, LINES_UTM, probes = load_geometry()
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    for source in ("tomtom", "here"):
        if args.source and source != args.source:
            continue
        every = interval_min(source, probes)
        last = state.get(source)
        due = last is None or (now.timestamp() - last) >= every * 60 - 30
        if args.dry_run:
            print(f"{source}: every {every} min")
        if not (due or args.force or args.dry_run):
            continue
        ok = poll_tomtom(now, probes, args.dry_run) if source == "tomtom" else poll_here(now, args.dry_run)
        if ok:
            state[source] = now.timestamp()
    if not args.dry_run:
        json.dump(state, open(STATE, "w"))


if __name__ == "__main__":
    sys.exit(main())
