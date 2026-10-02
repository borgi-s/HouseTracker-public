"""Operator endpoints: the anchors enrichment routes against, and on-demand triggers for
the M4 enrichment flow and the M5 lifecycle sweep (which also runs from the daily
timer). Every backend is a seam imported as a module global, so tests fake them by
monkeypatching housetracker.api.admin.<Name> — the same trick the CLI tests use."""
from __future__ import annotations

import os

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel

from housetracker.api.deps import get_store, today
from housetracker.api.houses import already_tracked
from housetracker.enrich.enrich import enrich_house, route_to_anchors
from housetracker.enrich.geocode import AddressGeocoder
from housetracker.enrich.route import ORSRouter
from housetracker.lifecycle.boligsiden import BoligsidenClient
from housetracker.lifecycle.lifecycle import run_lifecycle
from housetracker.lifecycle.notify import from_env, hooks
from housetracker.lifecycle.sold import HttpProber
from housetracker.model import DuplicateHouse, ValidationError
from housetracker.scrape.autoadapter import resolve
from housetracker.scrape.download import download_media, replace_scraped_media
from housetracker.scrape.fetch import (
    FetchError, PatchrightFetcher, UrllibFetcher, fetch_html,
)
from housetracker.scrape.openhouse import record_page
from housetracker.store import HouseStore

router = APIRouter(prefix="/api", tags=["admin"])


class AnchorIn(BaseModel):
    label: str = ""
    address: str | None = None
    lat: float | None = None
    lon: float | None = None
    kind: str = "fixed"


class ScrapeIn(BaseModel):
    url: str
    use_browser: bool = False      # Lane B is opt-in: a stealth browser per request is
                                   # heavy for a long-lived server process


@router.get("/anchors")
def list_anchors(store: HouseStore = Depends(get_store)) -> list[dict]:
    return [a.to_dict() for a in store.list_anchors()]


class SettingsPatch(BaseModel):
    notify_price_drops: bool | None = None
    notify_open_houses: bool | None = None


class AnchorPatch(BaseModel):
    label: str | None = None
    address: str | None = None


def _locate(address: str) -> dict:
    loc = AddressGeocoder().geocode(address)
    if not loc or loc.get("lat") is None or loc.get("lon") is None:
        raise HTTPException(status_code=422,
                            detail=f"address not found: {address!r} (include the postcode)")
    return {"lat": loc["lat"], "lon": loc["lon"]}


def _route_new_place(a, request: Request, background: BackgroundTasks) -> None:
    """Every located house gets its travel times to `a`, after the response has gone out."""
    key = os.environ.get("HT_ORS_KEY")
    if key and a.kind == "fixed" and a.lat is not None and a.lon is not None:
        background.add_task(_route_later, request.app.state.db_path, a, ORSRouter(key))


@router.post("/anchors", status_code=201)
def add_anchor(body: AnchorIn, request: Request, background: BackgroundTasks,
               store: HouseStore = Depends(get_store)) -> dict:
    """An anchor given only an address is geocoded here."""
    data = body.model_dump(exclude_none=True)
    if body.address and (body.lat is None or body.lon is None):
        data |= _locate(body.address)
    try:
        a = store.add_anchor(data)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    _route_new_place(a, request, background)
    return a.to_dict()


@router.patch("/anchors/{anchor_id}")
def update_anchor(anchor_id: str, body: AnchorPatch, request: Request,
                  background: BackgroundTasks, store: HouseStore = Depends(get_store)) -> dict:
    """A new address is geocoded and the travel times recomputed; a new label is just that."""
    current = store.get_anchor(anchor_id)
    if current is None:
        raise HTTPException(status_code=404, detail=f"no anchor {anchor_id!r}")
    fields = body.model_dump(exclude_none=True)
    moved = body.address is not None and body.address != current.address
    if moved:
        fields |= _locate(body.address)
    try:
        a = store.update_anchor(anchor_id, fields)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    if moved:
        _route_new_place(a, request, background)
    return a.to_dict()


def _route_later(db_path, anchor, ors) -> None:
    """Background, own connection (see _download_later)."""
    store = HouseStore(db_path)
    try:
        for h in store.list_houses():
            if h.lat is not None and h.lon is not None:
                route_to_anchors(h, store, ors, [anchor], now=today())
    finally:
        store.conn.close()


@router.delete("/anchors/{anchor_id}")
def delete_anchor(anchor_id: str, store: HouseStore = Depends(get_store)) -> dict:
    if not store.delete_anchor(anchor_id):
        raise HTTPException(status_code=404, detail=f"no anchor {anchor_id!r}")
    return {"deleted": anchor_id}


_SWITCHES = ("notify_price_drops", "notify_open_houses")


def _settings(store: HouseStore) -> dict:
    return {**{k: store.get_setting(k, "1") == "1" for k in _SWITCHES},
            "discord_configured": from_env() is not None}   # never the URL: it is a secret


@router.get("/settings")
def read_settings(store: HouseStore = Depends(get_store)) -> dict:
    return _settings(store)


@router.patch("/settings")
def update_settings(body: SettingsPatch, store: HouseStore = Depends(get_store)) -> dict:
    for k, v in body.model_dump(exclude_none=True).items():
        store.set_setting(k, "1" if v else "0")
    return _settings(store)


@router.post("/houses/{house_id}/enrich")
def enrich(house_id: str, store: HouseStore = Depends(get_store)) -> dict:
    house = store.get_house(house_id)
    if house is None:
        raise HTTPException(status_code=404, detail=f"no house {house_id!r}")
    key = os.environ.get("HT_ORS_KEY")
    ors = ORSRouter(key) if key else None      # no key -> geocode + school map only
    return enrich_house(house, store, AddressGeocoder(), ors, now=today())


@router.post("/admin/lifecycle")
def lifecycle(store: HouseStore = Depends(get_store)) -> dict:
    """The same sweep the daily timer runs, on demand. Best-effort by construction: a
    failed probe or lookup degrades to 'did less'."""
    notify, notify_open = hooks(store)
    return run_lifecycle(store, HttpProber(), BoligsidenClient(), now=today(),
                         geocoder=AddressGeocoder(), notify=notify,
                         notify_open=notify_open)


def _download_later(db_path, house_id: str, media_refs, data_dir, replace=False) -> None:
    """Background: pull the gallery, floor plan and salgsopstilling after the response
    has gone out (replace=True swaps out the old scraped set). Opens its own store — the
    request's connection is closed by now, and this runs on a different thread than the
    one that created it."""
    store = HouseStore(db_path)
    try:
        (replace_scraped_media if replace else download_media)(
            store, house_id, media_refs, data_dir, now=today())
    finally:
        store.conn.close()


@router.post("/houses/scrape", status_code=201)
def scrape_house(body: ScrapeIn, request: Request, background: BackgroundTasks,
                 store: HouseStore = Depends(get_store)) -> dict:
    lane_b = PatchrightFetcher() if body.use_browser else None
    try:
        html = fetch_html(body.url, UrllibFetcher(), lane_b)
    except FetchError as e:
        raise HTTPException(status_code=502, detail=f"fetch failed: {e}") from e

    # ponytail: synth=None — LLM auto-adapter synthesis needs the tmux relay and a human
    # confirm (M3), which an HTTP request cannot wait on. resolve() still returns an
    # addable result (the M2 guarantee), so the house always lands; teaching a new chain
    # stays a CLI job (`housetracker scrape --url ...`). Upgrade path: a job table and a
    # poll endpoint, if waiting for synthesis from the phone ever matters.
    result = resolve(body.url, html, store, None, now=today())
    if not result.house.get("address"):
        raise HTTPException(status_code=422,
                            detail=f"could not parse an address from {body.url}")

    try:
        house = store.add_house(result.house, now=today())
    except DuplicateHouse as e:
        raise already_tracked(e) from e
    record_page(store, house.id, body.url, html)
    background.add_task(_download_later, request.app.state.db_path, house.id,
                        result.media, request.app.state.data_dir)
    return {**house.to_dict(), "price_per_m2": house.price_per_m2,
            "media_pending": len(result.media)}


@router.post("/houses/{house_id}/rescrape")
def rescrape_house(house_id: str, request: Request, background: BackgroundTasks,
                   store: HouseStore = Depends(get_store)) -> dict:
    """Re-read the listing page of a house we track: its facts and media, keeping our
    status, notes, scores, own photos and the price (the daily sweep owns that)."""
    house = store.get_house(house_id)
    if house is None:
        raise HTTPException(status_code=404, detail=f"no house {house_id!r}")
    if not house.listing_url:
        raise HTTPException(status_code=422, detail="this house has no listing link to re-read")
    try:
        html = fetch_html(house.listing_url, UrllibFetcher(), None)
    except FetchError as e:
        raise HTTPException(status_code=502, detail=f"fetch failed: {e}") from e
    result = resolve(house.listing_url, html, store, None, now=today())
    house = store.refresh_from_scrape(house_id, result.house, now=today())
    record_page(store, house_id, house.listing_url, html)
    background.add_task(_download_later, request.app.state.db_path, house_id,
                        result.media, request.app.state.data_dir, True)
    return {**house.to_dict(), "price_per_m2": house.price_per_m2,
            "media_pending": len(result.media)}
