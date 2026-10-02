# housetracker/enrich/enrich.py
"""The M4 enrichment flow: geocode -> persist location -> route to fixed anchors ->
build the school map URL -> resolve the district schools. Additive and best-effort — a
None or raising backend degrades to 'did less' and never corrupts a house (mirrors the M2
addability guarantee)."""
from __future__ import annotations

import re

from housetracker.enrich.schools import resolve_schools, school_district_map_url
from housetracker.model import ROUTE_MODES

# BBR counts a lived-in floor under the roof as "udnyttet tagetage", not a floor, so a
# row house with bedrooms upstairs often reads 1; the listing text names the upstairs.
# Not "tre plan": agents count the basement in that ("144 etagemeter over tre plan").
_TWO = re.compile(r"første\s?sal|\b(to|2) plan\b", re.I)
_THREE = re.compile(r"anden\s?sal", re.I)
# BBR lags renovations; "to moderne badeværelser" in the text is newer.
_NUMBERS = {"to": 2, "2": 2, "tre": 3, "3": 3, "fire": 4, "4": 4}
_BATHS = re.compile(r"\b(to|2|tre|3|fire|4)\s+(?:\w+\s+){0,2}badeværelser", re.I)


def floor_count(bbr_floors: int | None, description: str | None) -> int | None:
    """Living floors above ground: BBR's count, raised to what the listing text shows."""
    text = description or ""
    seen = 3 if _THREE.search(text) else 2 if _TWO.search(text) else 0
    return max(bbr_floors or 0, seen) or None


def bathroom_count(bbr_baths: int | None, description: str | None) -> int | None:
    """BBR's count, raised to a number the listing text gives."""
    said = [_NUMBERS[m.group(1).lower()] for m in _BATHS.finditer(description or "")]
    return max([bbr_baths or 0, *said]) or None


def _place(house) -> str:
    """'Street 1, 2800 Town': Adressevask will not guess a town from a bare street."""
    town = " ".join(p for p in (house.postal_code, house.city) if p)
    return f"{house.address}, {town}" if town else house.address


def route_to_anchors(house, store, router, anchors, now: str) -> int:
    """Every ROUTE_MODES commute from a located house to each located anchor; a failed
    route is skipped. Returns how many were stored."""
    n = 0
    for a in anchors:
        if a.lat is None or a.lon is None:
            continue
        for mode in ROUTE_MODES:
            try:
                result = router.route((house.lon, house.lat), (a.lon, a.lat), mode)
            except Exception:
                result = None
            if result is not None:
                minutes, distance_m = result
                store.upsert_commute(house.id, a.id, mode, minutes, distance_m, now)
                n += 1
    return n


def enrich_house(house, store, geocoder, router, now: str, anchors=None) -> dict:
    summary = {"geocoded": False, "commutes": 0, "school_map_url": None, "schools": 0}

    if geocoder is not None:
        try:
            loc = geocoder.geocode(_place(house))
        except Exception:
            loc = None
        if loc and house.postal_code and loc.get("postal_code") != house.postal_code:
            loc = None      # a namesake street in another town: never move the house
        if loc and loc.get("lat") is not None and loc.get("lon") is not None:
            store.update_house_location(
                house.id, lat=loc["lat"], lon=loc["lon"],
                kommune=loc.get("kommune"), postal_code=loc.get("postal_code"),
                city=loc.get("city"), now=now)
            house.lat, house.lon = loc["lat"], loc["lon"]
            if loc.get("kommune"):
                house.kommune = loc["kommune"]
            facts = {"floors": floor_count(loc.get("floors"), house.description),
                     "bathrooms": bathroom_count(loc.get("bathrooms"), house.description),
                     "basement_m2": loc.get("basement_m2")}
            facts = {k: v for k, v in facts.items()          # our own counts win
                     if v is not None and getattr(house, k) is None}
            if facts:
                store.update_house(house.id, facts, now=now)
            summary["geocoded"] = True

    if house.lat is None or house.lon is None:
        return summary                        # nothing to route or map without coords
    summary["school_map_url"] = school_district_map_url(house.lon, house.lat)

    if router is not None:
        if anchors is None:
            anchors = store.list_anchors(kind="fixed")
        summary["commutes"] = route_to_anchors(house, store, router, anchors, now)

    try:
        summary["schools"] = resolve_schools(house, store, router, geocoder, now)
    except Exception:
        pass            # best-effort: the house keeps the schools it had (spec D10)
    return summary
