"""The FastAPI app factory. There is no password layer by design: the service binds to
the Tailscale interface and tailnet membership is the auth (spec §10)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

from housetracker.api import admin, criteria, houses, maps, media
from housetracker.api.deps import PERSON_COOKIE, get_store
from housetracker.store import HouseStore

COOKIE_MAX_AGE = 60 * 60 * 24 * 365      # a year; the picker should survive reboots


class PersonIn(BaseModel):
    name: str


class SessionIn(BaseModel):
    person_id: str


def create_app(db_path, data_dir=None, web_dir=None) -> FastAPI:
    app = FastAPI(title="HouseTracker API", version="0.1.0")
    app.state.db_path = Path(db_path)
    # Same convention as the CLI: media live beside the database.
    app.state.data_dir = Path(data_dir).resolve() if data_dir else Path(db_path).resolve().parent

    @app.get("/api/health")
    def health(store: HouseStore = Depends(get_store)) -> dict:
        return {"ok": True, "houses": len(store.list_houses())}

    @app.get("/api/persons")
    def list_persons(store: HouseStore = Depends(get_store)) -> list[dict]:
        return [p.to_dict() for p in store.list_persons()]

    @app.post("/api/persons", status_code=201)
    def add_person(body: PersonIn,
                   store: HouseStore = Depends(get_store)) -> dict:
        try:
            return store.add_person(body.name).to_dict()
        except sqlite3.IntegrityError as e:
            raise HTTPException(status_code=409,
                                detail=f"person {body.name!r} already exists") from e

    @app.patch("/api/persons/{person_id}")
    def rename_person(person_id: str, body: PersonIn,
                      store: HouseStore = Depends(get_store)) -> dict:
        if not any(p.id == person_id for p in store.list_persons()):
            raise HTTPException(status_code=404, detail=f"no person {person_id!r}")
        try:
            return store.rename_person(person_id, body.name).to_dict()
        except sqlite3.IntegrityError as e:
            raise HTTPException(status_code=409,
                                detail=f"person {body.name!r} already exists") from e

    @app.delete("/api/persons/{person_id}")
    def delete_person(person_id: str, store: HouseStore = Depends(get_store)) -> dict:
        if not store.delete_person(person_id):
            raise HTTPException(status_code=404, detail=f"no person {person_id!r}")
        return {"deleted": person_id}

    @app.get("/api/session")
    def read_session(request: Request,
                     store: HouseStore = Depends(get_store)) -> dict:
        pid = request.cookies.get(PERSON_COOKIE)
        for p in store.list_persons():
            if p.id == pid:
                return {"person": p.to_dict()}
        return {"person": None}          # no cookie, or it names someone deleted

    @app.post("/api/session")
    def pick_person(body: SessionIn, response: Response,
                    store: HouseStore = Depends(get_store)) -> dict:
        for p in store.list_persons():
            if p.id == body.person_id:
                # secure=False: the tailnet serves plain HTTP. httponly keeps the
                # cookie out of JS; the frontend reads GET /api/session instead.
                response.set_cookie(PERSON_COOKIE, p.id, max_age=COOKIE_MAX_AGE,
                                    httponly=True, samesite="lax")
                return {"person": p.to_dict()}
        raise HTTPException(status_code=404, detail=f"no person {body.person_id!r}")

    @app.delete("/api/session")
    def clear_session(response: Response) -> dict:
        response.delete_cookie(PERSON_COOKIE)
        return {"person": None}

    app.include_router(houses.router)
    app.include_router(criteria.router)
    app.include_router(media.router)
    app.include_router(admin.router)
    app.include_router(maps.router)

    if web_dir is not None and (Path(web_dir) / "index.html").is_file():
        _serve_web(app, Path(web_dir).resolve())
    return app


def _serve_web(app: FastAPI, web_dir: Path) -> None:
    """The built M7 frontend. Registered after every /api router, so it only sees what
    they did not match. A real file under web_dir is served as-is; any other path gets
    index.html so client-side routes like /house/<id> survive a reload."""
    index = web_dir / "index.html"
    # Revalidate the shell every load: a cached copy names hashed assets that the next
    # build deletes, and their paths would fall back to this HTML — a blank page.
    no_cache = {"Cache-Control": "no-cache"}

    @app.get("/{path:path}", include_in_schema=False)
    def web(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        f = (web_dir / path).resolve()
        if path and f.is_file() and f.is_relative_to(web_dir):
            return FileResponse(f)
        return FileResponse(index, headers=no_cache)
