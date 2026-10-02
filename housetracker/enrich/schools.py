"""District schools. Two parts:

- `school_district_map_url`: the official GeoFA webkort (MapCentia Vidi) centred on the
  house with the Børne- og skoledistrikter (5710) layer overlaid. The Vidi state hash is
  <baselayer>/<zoom>/<lon>/<lat>/<layers> (lon before lat).
- `resolve_schools`: which folkeskoler the house belongs to (GeoFA's district polygons +
  skolegang.dk's school list), how far each is on foot and by bike, stored per house.
  See docs/specs/2026-09-26-schools-design.md."""
from __future__ import annotations

import json
import math
import re
import time
import urllib.parse
import urllib.request
from datetime import date

from housetracker.enrich.skolegang import (
    kommune_url, parse_kommune_slugs, parse_school, school_url,
)

GEOFA_WEBKORT_BASE = "https://geofa-kort.geodanmark.dk/app/fkg/"
# ponytail: FKG_CONFIG is a captured constant — GeoFA's published "distrikter" config
# (the district layers, no startup pop-up). Keys carry a hash suffix and change when
# GeoFA republishes; a wrong key loads no layers and Vidi alerts "No schemata". List the
# live keys at https://geofa.geodanmark.dk/api/v2/configuration/fkg and re-check in a
# browser; see docs/geofa-school-district-embed.md.
FKG_CONFIG = "/api/v2/configuration/fkg/configuration_distrikter_69d0c3b971df1242454664.json"
SCHOOL_DISTRICT_LAYER = "fkg.t_5710_born_skole_dis"     # listed in the hash = switched on
BASELAYER = "Basis_kort"
DEFAULT_ZOOM = 14

GEOFA_SQL = "https://geofa.geodanmark.dk/api/v2/sql/fkg"
_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
ROUTE_CANDIDATES = 5          # calibration knob: schools routed per district (ORS calls = 2x)
SHOWN = 3                     # nearest schools kept per district
SCHOOL_MAX_AGE_DAYS = 30      # figures change once a year
PAUSE_S = 0.5                 # between skolegang.dk page fetches
# Folkeskoler whose skolegang.dk page lacks the register facts (no address, geo or
# InstTypeNr) and so are missing from their kommune's list. kommune (DAWA name) ->
# ((slug, address to geocode), ...). Checked 2026-09-26.
EXTRA_SCHOOLS = {
    "Gentofte": (("tranegaardskolen", "Gersonsvej 38, 2900 Hellerup"),),
}


def school_district_map_url(lon: float, lat: float, zoom: int = DEFAULT_ZOOM) -> str:
    return (f"{GEOFA_WEBKORT_BASE}?config={FKG_CONFIG}"
            f"#{BASELAYER}/{zoom}/{lon}/{lat}/{SCHOOL_DISTRICT_LAYER}")


def _get_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def _geofa_rows(sql: str) -> list[dict]:
    """GeoFA's public SQL API (no key). Answers GeoJSON; we only read the properties."""
    data = json.loads(_get_text(f"{GEOFA_SQL}?q={urllib.parse.quote(sql)}"))
    return [f["properties"] for f in data.get("features", [])]


def _pt(lon, lat) -> str:
    return f"ST_Transform(ST_SetSRID(ST_MakePoint({lon}, {lat}), 4326), 25832)"


def districts_sql(lon: float, lat: float, schools: list[dict]) -> str:
    """Every school district holding the house (10.-klasse districts aside), one row per
    school of `schools` inside it (inst NULL when none is). Only digit ids and float
    coordinates reach the SQL; _placed() guarantees both before a school is stored."""
    values = ", ".join(f"('{s['inst_nr']}', {float(s['lon'])}, {float(s['lat'])})"
                       for s in schools)
    return ("SELECT d.udd_distrikt_navn AS name, d.starttrin_kode AS start, "
            "d.sluttrin_kode AS stop, d.link, s.id AS inst "
            "FROM fkg.t_5710_born_skole_dis d "
            f"LEFT JOIN (VALUES {values}) AS s(id, lon, lat) "
            f"ON ST_Contains(d.geometri, {_pt('s.lon', 's.lat')}) "
            "WHERE d.udd_distrikt_type_kode = 5 AND d.starttrin_kode <> 10 "
            f"AND ST_Contains(d.geometri, {_pt(float(lon), float(lat))})")


def _grade(kode) -> int | None:
    """GeoFA trin code -> klassetrin: 11 = 0. klasse, 12 = førskole, 1..10 as is."""
    if kode in (11, 12):
        return 0
    return kode if isinstance(kode, int) and 1 <= kode <= 10 else None


def grades_label(start, stop) -> str:
    a, b = _grade(start), _grade(stop)
    return f"{a}.–{b}." if b is not None else f"{a}."


def _metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance (haversine)."""
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 12_742_000 * math.asin(math.sqrt(a))


def _placed(row: dict) -> bool:
    return (re.fullmatch(r"\d+", row.get("inst_nr") or "") is not None
            and all(isinstance(row.get(k), (int, float)) for k in ("lat", "lon")))


def _fresh(schools: list[dict], now: str) -> bool:
    """Judged by the newest fetch: a school that dropped off the list (or whose page
    failed) keeps its old row without re-crawling the kommune on every enrich."""
    if not schools:
        return False
    newest = max(s["fetched_at"][:10] for s in schools)
    return (date.fromisoformat(now[:10]) - date.fromisoformat(newest)).days < SCHOOL_MAX_AGE_DAYS


def _try(fn, *args):
    try:
        return fn(*args)
    except Exception:
        return None


def kommune_schools(kommune: str, store, geocoder, now: str, fetch, sleep) -> list[dict]:
    """The kommune's folkeskoler with coordinates: the store's when fetched within
    SCHOOL_MAX_AGE_DAYS, else re-read from skolegang.dk. A failed re-read keeps what the
    store has. ponytail: a school that closes stays in the store; delete its row by hand."""
    cached = store.list_schools(kommune)
    if _fresh(cached, now):
        return cached
    try:
        slugs = parse_kommune_slugs(fetch(kommune_url(kommune)))
    except Exception:
        return cached                       # site down: the last list beats none
    extra = dict(EXTRA_SCHOOLS.get(kommune, ()))
    for slug in dict.fromkeys([*slugs, *extra]):
        sleep(PAUSE_S)
        row = _try(lambda: parse_school(fetch(school_url(slug)), slug))
        if row is None or not (row["folkeskole"] or slug in extra):
            continue
        if slug in extra:
            row["address"] = row["address"] or extra[slug]
            if row["lat"] is None and geocoder is not None:
                loc = _try(geocoder.geocode, extra[slug]) or {}
                row["lat"], row["lon"] = loc.get("lat"), loc.get("lon")
        if _placed(row):
            store.upsert_school({**row, "kommune": kommune, "fetched_at": now})
    return store.list_schools(kommune)


def resolve_schools(house, store, router, geocoder, now: str, fetch=None, geofa=None,
                    sleep=time.sleep) -> int:
    """Find the house's district(s), the folkeskoler serving each, and walking + cycling
    distance to the nearest; replace the house's `house_school` rows. Returns the number
    of rows written; 0 = nothing to do (no coords/kommune, no schools, no district), and
    the previous rows stay. A GeoFA failure raises, also leaving the previous rows."""
    if house.lat is None or house.lon is None or not house.kommune:
        return 0
    fetch, geofa = fetch or _get_text, geofa or _geofa_rows
    schools = kommune_schools(house.kommune, store, geocoder, now, fetch, sleep)
    if not schools:
        return 0
    by_inst = {s["inst_nr"]: s for s in schools}
    districts: dict[tuple, dict] = {}
    for r in geofa(districts_sql(house.lon, house.lat, schools)):
        d = districts.setdefault((r["name"], r["start"], r["stop"]), {**r, "inside": []})
        if r.get("inst") in by_inst:
            d["inside"].append(by_inst[r["inst"]])
    if not districts:
        return 0

    def straight(s: dict) -> float:
        return _metres(house.lat, house.lon, s["lat"], s["lon"])

    routes: dict[tuple, tuple | None] = {}

    def route(s: dict, mode: str):
        if router is None:
            return None
        if (s["inst_nr"], mode) not in routes:
            routes[s["inst_nr"], mode] = _try(
                router.route, (house.lon, house.lat), (s["lon"], s["lat"]), mode)
        return routes[s["inst_nr"], mode]

    rows = []
    ordered = sorted(districts.values(), key=lambda d: (_grade(d["start"]) or 0, d["name"]))
    for order, d in enumerate(ordered):
        named = [s for s in d["inside"] if s["name"].casefold() in d["name"].casefold()]
        members = named or d["inside"]
        pool = members or schools                 # empty district: nearest in the kommune
        near = sorted(pool, key=straight)[:ROUTE_CANDIDATES if members else SHOWN]
        trips = [(s, route(s, "foot-walking"), route(s, "cycling-regular")) for s in near]
        trips.sort(key=lambda t: (t[1] is None, t[1][0] if t[1] else straight(t[0])))
        for rank, (s, walk, bike) in enumerate(trips[:SHOWN], 1):
            rows.append({
                "district_order": order, "rank": rank, "district_name": d["name"],
                "district_grades": grades_label(d["start"], d["stop"]),
                "district_link": d.get("link"), "district_schools": len(members),
                "fallback": not members, "inst_nr": s["inst_nr"],
                "walk_min": walk[0] if walk else None, "walk_m": walk[1] if walk else None,
                "bike_min": bike[0] if bike else None, "bike_m": bike[1] if bike else None,
                "straight_m": round(straight(s)),
            })
    had_times = any(r["walk_min"] is not None for r in store.list_house_schools(house.id))
    if had_times and not any(routes.values()):
        return 0            # routing down or off: keep the times we had (spec D10)
    store.replace_house_schools(house.id, rows, now)
    return len(rows)
