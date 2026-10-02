# tests/test_store_lifecycle.py
from housetracker.store import HouseStore


def _store(tmp_path):
    return HouseStore(tmp_path / "data" / "ht.db")


def _house(s, address="Nyvej 2"):
    s.add_house({"address": address, "listing_url": "https://x.dk/1"}, now="2026-09-18")
    return s.list_houses()[0]


def test_mark_sold_sets_status_detected_at_and_logs_event(tmp_path):
    s = _store(tmp_path)
    h = _house(s)
    out = s.mark_sold(h.id, now="2026-09-19")
    assert out.status == "sold"
    assert out.sold_detected_at == "2026-09-19"
    # status_event audit trail: initial 'not_visited' then 'sold'
    hist = [e["status"] for e in s.status_history(h.id)]
    assert hist == ["not_visited", "sold"]


def test_mark_sold_explicit_detected_at(tmp_path):
    s = _store(tmp_path)
    h = _house(s)
    out = s.mark_sold(h.id, now="2026-09-19", detected_at="2026-09-01")
    assert out.sold_detected_at == "2026-09-01"
    assert out.status == "sold"


def test_set_realized_price_writes_only_price_fields(tmp_path):
    s = _store(tmp_path)
    h = _house(s)
    s.mark_sold(h.id, now="2026-09-19")
    s.set_realized_price(h.id, 5250000.0, "2026-03-14", now="2026-09-20")
    g = s.get_house(h.id)
    assert g.sold_price_dkk == 5250000.0
    assert g.sold_date == "2026-03-14"
    assert g.updated_at == "2026-09-20"
    assert g.status == "sold"          # unchanged by set_realized_price
