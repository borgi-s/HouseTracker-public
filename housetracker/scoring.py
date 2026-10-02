"""Pure scoring: weighted per-person overalls + disagreement. No I/O."""
from __future__ import annotations

from housetracker.model import Criterion, House


def auto_normalized(houses: list[House], criterion: Criterion) -> dict[str, float]:
    vals = {h.id: h.auto_value(criterion.auto_source) for h in houses}
    present = {hid: v for hid, v in vals.items() if v is not None}
    if not present:
        return {}
    lo, hi = min(present.values()), max(present.values())
    out = {}
    for hid, v in present.items():
        frac = (v - lo) / (hi - lo) if hi != lo else None
        out[hid] = 1.0 if frac is None else (frac if criterion.higher_is_better else 1.0 - frac)
    return out


def person_overall(house: House, person_id: str, houses: list[House],
                   criteria: list[Criterion],
                   scores: dict[tuple[str, str], float]) -> float | None:
    num = den = 0.0
    rated = False
    for c in criteria:
        # Use c.id when set (DB path), fall back to c.key (test/in-memory path)
        cid = c.id or c.key
        if c.kind == "subjective":
            v = scores.get((person_id, cid))
            if v is None:
                continue
            rated = True
            norm = v / 5.0
        else:  # auto
            norm = auto_normalized(houses, c).get(house.id)
            if norm is None:
                continue
        num += c.weight * norm
        den += c.weight
    # Unrated until this person scores something: the automatic criteria alone would
    # give an overall to a listing nobody has looked at yet.
    return None if den == 0 or not rated else num / den


def disagreement(criteria: list[Criterion],
                 scores: dict[tuple[str, str], float],
                 person_ids: tuple[str, str]) -> dict[str, float]:
    a, b = person_ids
    out = {}
    for c in criteria:
        if c.kind != "subjective":
            continue
        cid = c.id or c.key
        va, vb = scores.get((a, cid)), scores.get((b, cid))
        if va is not None and vb is not None:
            out[cid] = abs(va - vb)
    return out
