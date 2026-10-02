"""House reads: the list, the assembled detail M7 renders, and the ranking. Assembly
only — every number comes from the M1 store and scoring modules."""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from housetracker import scoring
from housetracker.api.deps import current_person, get_store, today
from housetracker.enrich.schools import school_district_map_url
from housetracker.enrich.skolegang import figure_rows, school_url
from housetracker.model import DuplicateHouse, Person, ValidationError
from housetracker.scrape.openhouse import utc_now
from housetracker.store import HouseStore

router = APIRouter(prefix="/api", tags=["houses"])


class HouseIn(BaseModel):
    address: str
    postal_code: str | None = None
    city: str | None = None
    maegler_chain: str | None = None
    listing_url: str | None = None
    price_dkk: float | None = None
    ejerudgift_dkk: float | None = None
    size_m2: float | None = None
    lot_m2: float | None = None
    rooms: float | None = None
    build_year: int | None = None
    energy_label: str | None = None
    description: str | None = None
    floors: int | None = None
    bathrooms: int | None = None
    basement_m2: float | None = None


class HousePatch(HouseIn):
    """Every HouseIn field, all optional; an explicit null clears it. Keys left out
    stay untouched (model_dump(exclude_unset=True))."""
    address: str | None = None


class StatusIn(BaseModel):
    status: str


class NoteIn(BaseModel):
    body: str
    shared: bool = False          # true -> person_id NULL, i.e. ours not mine


class TagIn(BaseModel):
    label: str
    shared: bool = False


def already_tracked(e: DuplicateHouse) -> HTTPException:
    """409 naming the tracked house, so the add page can link to it."""
    h = e.house
    return HTTPException(status_code=409, detail={
        "message": str(e), "house": {"id": h.id, "address": h.address, "status": h.status}})


def _house_json(house) -> dict:
    """House.to_dict() is asdict(), so the computed property needs adding by hand."""
    return {**house.to_dict(), "price_per_m2": house.price_per_m2}


def _cover_url(media) -> str | None:
    """The grid card's photo: the first scraped photo by sort (list_media orders by
    kind, sort, id), else our own first snap, else none."""
    for kind in ("photo", "user_photo"):
        for m in media:
            if m.kind == kind:
                return f"/api/media/{m.id}/file"
    return None


_LISTING_OUT = ("listed_price_dkk", "listed_date", "days_on_market",
                "total_days_on_market", "realtor", "checked_at")


def _price_history(store: HouseStore, house_id: str) -> dict:
    """The raw parts of the house's price story; the web app lays out the timeline."""
    listing = store.get_listing(house_id)
    return {
        "events": store.price_events(house_id),
        "listing": {k: listing[k] for k in _LISTING_OUT} if listing else None,
        "sales": listing["sales"] if listing else [],
        "original_price_dkk": store.original_price(house_id),
    }


_TRIP = ("rank", "walk_min", "walk_m", "bike_min", "bike_m", "straight_m")


def _schools(store: HouseStore, house_id: str) -> dict | None:
    """The house's district schools, each figure next to its kommune's average (computed
    here, from every folkeskole of that kommune in the store). None before the first
    successful lookup."""
    rows = store.list_house_schools(house_id)
    if not rows:
        return None
    districts: dict[int, dict] = {}
    peers: dict[str, list[dict]] = {}
    for r in rows:
        s = store.get_school(r["inst_nr"])
        if s is None:
            continue
        kommune = peers.setdefault(s["kommune"], store.list_schools(s["kommune"]))
        d = districts.setdefault(r["district_order"], {
            "name": r["district_name"], "grades": r["district_grades"],
            "link": r["district_link"], "fallback": r["fallback"],
            "school_count": r["district_schools"], "schools": []})
        d["schools"].append({
            "inst_nr": s["inst_nr"], "name": s["name"], "address": s["address"],
            "url": school_url(s["slug"]),
            "grades": f"0.–{s['top_grade']}." if s["top_grade"] is not None else None,
            **{k: r[k] for k in _TRIP},
            "figures": figure_rows(s["figures"], kommune),
        })
    return {"checked_at": rows[0]["checked_at"],
            "districts": [districts[k] for k in sorted(districts)]}


def _scored(house, houses, criteria, persons, scores) -> dict:
    """Per-person overalls + the pair's disagreement — shared by list and detail."""
    pair = tuple(p.id for p in persons[:2])
    return {
        "overall": {p.id: scoring.person_overall(house, p.id, houses, criteria, scores)
                    for p in persons},
        "disagreement": (scoring.disagreement(criteria, scores, pair)
                         if len(pair) == 2 else {}),
    }


@router.get("/houses")
def list_houses(store: HouseStore = Depends(get_store)) -> list[dict]:
    # ponytail: O(houses² × criteria) — person_overall re-normalizes each auto criterion
    # across the whole set for every house. Trivial at family scale (tens of houses);
    # precompute scoring.auto_normalized once per request if the grid ever feels slow.
    houses, criteria = store.list_houses(), store.list_criteria()
    persons = store.list_persons()
    now = utc_now()
    return [{**_house_json(h),
             "cover_url": _cover_url(store.list_media(h.id)),
             "original_price_dkk": store.original_price(h.id),
             "open_houses": store.list_open_houses(h.id, upcoming_at=now),
             **_scored(h, houses, criteria, persons, store.get_scores(h.id))}
            for h in houses]


@router.get("/houses/{house_id}")
def get_house(house_id: str, store: HouseStore = Depends(get_store)) -> dict:
    house = store.get_house(house_id)
    if house is None:
        raise HTTPException(status_code=404, detail=f"no house {house_id!r}")

    houses = store.list_houses()          # auto criteria normalize across the whole set
    criteria = store.list_criteria()
    scores = store.get_scores(house_id)
    persons = store.list_persons()

    by_person: dict[str, dict[str, float]] = {}
    for (person_id, criterion_id), value in scores.items():
        by_person.setdefault(person_id, {})[criterion_id] = value

    return {
        "house": _house_json(house),
        "media": [{**m.to_dict(), "url": f"/api/media/{m.id}/file"}
                  for m in store.list_media(house_id)],
        "commutes": [c.to_dict() for c in store.list_commutes(house_id)],
        "status_history": store.status_history(house_id),
        "notes": store.list_notes(house_id),
        "tags": store.list_tags(house_id),
        "school_map_url": (school_district_map_url(house.lon, house.lat)
                           if house.lat is not None and house.lon is not None
                           else None),
        "price_history": _price_history(store, house_id),
        "schools": _schools(store, house_id),
        "open_houses": store.list_open_houses(house_id),
        "scores": by_person,
        **_scored(house, houses, criteria, persons, scores),
    }


@router.get("/rank")
def rank(person_id: str, store: HouseStore = Depends(get_store)) -> list[dict]:
    houses, criteria = store.list_houses(), store.list_criteria()
    ranked = [{"house_id": h.id, "address": h.address,
               "overall": scoring.person_overall(h, person_id, houses, criteria,
                                                 store.get_scores(h.id))}
              for h in houses]
    ranked.sort(key=lambda r: (r["overall"] is None, -(r["overall"] or 0)))
    return ranked


@router.post("/houses", status_code=201)
def create_house(body: HouseIn, store: HouseStore = Depends(get_store)) -> dict:
    """Manual add — the phone quick-add path (§11). Scraping a URL is POST
    /api/houses/scrape."""
    try:
        return _house_json(store.add_house(body.model_dump(exclude_none=True),
                                           now=today()))
    except DuplicateHouse as e:
        raise already_tracked(e) from e
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.patch("/houses/{house_id}")
def update_house(house_id: str, body: HousePatch,
                 store: HouseStore = Depends(get_store)) -> dict:
    if store.get_house(house_id) is None:
        raise HTTPException(status_code=404, detail=f"no house {house_id!r}")
    try:
        return _house_json(store.update_house(
            house_id, body.model_dump(exclude_unset=True), now=today()))
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.delete("/houses/{house_id}")
def delete_house(house_id: str, request: Request,
                 store: HouseStore = Depends(get_store)) -> dict:
    if not store.delete_house(house_id):
        raise HTTPException(status_code=404, detail=f"no house {house_id!r}")
    data_dir = Path(request.app.state.data_dir).resolve()
    folder = (data_dir / "houses" / house_id).resolve()
    if folder.is_relative_to(data_dir / "houses"):  # never touch a file outside the archive
        shutil.rmtree(folder, ignore_errors=True)
    return {"deleted": house_id}


@router.patch("/houses/{house_id}/status")
def set_status(house_id: str, body: StatusIn,
               store: HouseStore = Depends(get_store)) -> dict:
    if store.get_house(house_id) is None:
        raise HTTPException(status_code=404, detail=f"no house {house_id!r}")
    try:
        return _house_json(store.set_status(house_id, body.status, now=today()))
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/houses/{house_id}/notes", status_code=201)
def add_note(house_id: str, body: NoteIn,
             store: HouseStore = Depends(get_store),
             person: Person = Depends(current_person)) -> dict:
    if store.get_house(house_id) is None:
        raise HTTPException(status_code=404, detail=f"no house {house_id!r}")
    try:
        return store.add_note(house_id, None if body.shared else person.id,
                              body.body, now=today())
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/houses/{house_id}/tags", status_code=201)
def add_tag(house_id: str, body: TagIn,
            store: HouseStore = Depends(get_store),
            person: Person = Depends(current_person)) -> dict:
    if store.get_house(house_id) is None:
        raise HTTPException(status_code=404, detail=f"no house {house_id!r}")
    try:
        return store.add_tag(house_id, None if body.shared else person.id, body.label)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.delete("/tags/{tag_id}")
def delete_tag(tag_id: int, store: HouseStore = Depends(get_store)) -> dict:
    if not store.delete_tag(tag_id):
        raise HTTPException(status_code=404, detail=f"no tag {tag_id}")
    return {"deleted": tag_id}


@router.delete("/notes/{note_id}")
def delete_note(note_id: int, store: HouseStore = Depends(get_store)) -> dict:
    if not store.delete_note(note_id):
        raise HTTPException(status_code=404, detail=f"no note {note_id}")
    return {"deleted": note_id}
