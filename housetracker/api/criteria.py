"""Criteria are rows, not code (spec §5) — this is the runtime editor for them, plus
the per-person score write. A score belongs to whoever the session cookie names."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from housetracker.api.deps import current_person, get_store, today
from housetracker.model import Person, ValidationError
from housetracker.store import HouseStore

router = APIRouter(prefix="/api", tags=["criteria"])


class CriterionIn(BaseModel):
    key: str
    label: str
    kind: str
    weight: float = 1.0
    auto_source: str | None = None
    higher_is_better: bool = True
    active: bool = True
    sort: int = 0


class CriterionPatch(BaseModel):
    label: str | None = None
    weight: float | None = None
    sort: int | None = None
    active: bool | None = None


class ScoreIn(BaseModel):
    value: float


@router.get("/criteria")
def list_criteria(active_only: bool = True,
                  store: HouseStore = Depends(get_store)) -> list[dict]:
    return [c.to_dict() for c in store.list_criteria(active_only=active_only)]


@router.post("/criteria", status_code=201)
def add_criterion(body: CriterionIn,
                  store: HouseStore = Depends(get_store)) -> dict:
    try:
        return store.add_criterion(body.model_dump(), now=today()).to_dict()
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except sqlite3.IntegrityError as e:
        raise HTTPException(status_code=409,
                            detail=f"criterion key {body.key!r} already exists") from e


@router.patch("/criteria/{criterion_id}")
def update_criterion(criterion_id: str, body: CriterionPatch,
                     store: HouseStore = Depends(get_store)) -> dict:
    if not any(c.id == criterion_id
               for c in store.list_criteria(active_only=False)):
        raise HTTPException(status_code=404,
                            detail=f"no criterion {criterion_id!r}")
    try:
        return store.update_criterion(
            criterion_id, body.model_dump(exclude_none=True)).to_dict()
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.delete("/criteria/{criterion_id}")
def delete_criterion(criterion_id: str, store: HouseStore = Depends(get_store)) -> dict:
    """Gone with every score given on it; deactivating keeps them."""
    if not store.delete_criterion(criterion_id):
        raise HTTPException(status_code=404, detail=f"no criterion {criterion_id!r}")
    return {"deleted": criterion_id}


@router.put("/houses/{house_id}/scores/{criterion_id}")
def set_score(house_id: str, criterion_id: str, body: ScoreIn,
              store: HouseStore = Depends(get_store),
              person: Person = Depends(current_person)) -> dict:
    if store.get_house(house_id) is None:
        raise HTTPException(status_code=404, detail=f"no house {house_id!r}")
    if not any(c.id == criterion_id
               for c in store.list_criteria(active_only=False)):
        raise HTTPException(status_code=404,
                            detail=f"no criterion {criterion_id!r}")
    if not 1.0 <= body.value <= 5.0:              # spec §6: subjective values are 1-5
        raise HTTPException(status_code=422, detail="value must be between 1 and 5")
    store.upsert_score(house_id, person.id, criterion_id, body.value, now=today())
    return {"house_id": house_id, "person_id": person.id,
            "criterion_id": criterion_id, "value": body.value}


@router.delete("/houses/{house_id}/scores/{criterion_id}")
def clear_score(house_id: str, criterion_id: str,
                store: HouseStore = Depends(get_store),
                person: Person = Depends(current_person)) -> dict:
    """Back to 'unscored' — which counts differently from any value (spec §6). Idempotent:
    a double tap on the phone must not surface an error."""
    if store.get_house(house_id) is None:
        raise HTTPException(status_code=404, detail=f"no house {house_id!r}")
    deleted = store.delete_score(house_id, person.id, criterion_id)
    return {"house_id": house_id, "person_id": person.id,
            "criterion_id": criterion_id, "deleted": deleted}
