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
from housetracker.enrich.enrich import enrich_house
from housetracker.enrich.geocode import AddressGeocoder
from housetracker.enrich.route import ORSRouter
from housetracker.lifecycle.boligsiden import BoligsidenClient
from housetracker.lifecycle.lifecycle import run_lifecycle
from housetracker.lifecycle.notify import from_env
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


@router.post("/anchors", status_code=201)
def add_anchor(body: AnchorIn, store: HouseStore = Depends(get_store)) -> dict:
    try:
        return store.add_anchor(body.model_dump(exclude_none=True)).to_dict()
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


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
    hook = from_env()
    return run_lifecycle(store, HttpProber(), BoligsidenClient(), now=today(),
                         geocoder=AddressGeocoder(), notify=hook,
                         notify_open=hook and hook.open_houses)


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
