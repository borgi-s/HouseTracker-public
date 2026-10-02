"""Shared FastAPI dependencies. Kept out of app.py so the routers can import them
without an import cycle (app.py imports the routers, the routers import this)."""
from __future__ import annotations

from datetime import date

from fastapi import Depends, HTTPException, Request

from housetracker.model import Person
from housetracker.store import HouseStore

PERSON_COOKIE = "ht_person"


def today() -> str:
    return date.today().isoformat()


def get_store(request: Request):
    """One sqlite connection per request, closed on the way out, so concurrent requests
    never share one. FastAPI enters this generator, runs the route and closes it on
    threadpool threads that can all differ — hence HouseStore's check_same_thread=False;
    within one request the connection is still used by one thread at a time.

    ponytail: connecting per request replays CREATE TABLE IF NOT EXISTS (sub-millisecond).
    Upgrade path: a thread-local store, if a profile ever shows this mattering.
    """
    store = HouseStore(request.app.state.db_path)
    try:
        yield store
    finally:
        store.conn.close()


def current_person(request: Request,
                   store: HouseStore = Depends(get_store)) -> Person:
    """The name-picker identity (spec §10). Tailnet membership is the auth; this cookie
    only says which of us is writing. FastAPI caches `get_store` per request, so this
    shares the route's connection rather than opening a second one."""
    pid = request.cookies.get(PERSON_COOKIE)
    for p in store.list_persons():
        if p.id == pid:
            return p
    raise HTTPException(status_code=401,
                        detail="no person selected — POST /api/session first")
