# tests/test_store_score.py
from housetracker.store import HouseStore

def _store(tmp_path):
    s = HouseStore(tmp_path / "ht.db")
    s.add_house({"address": "A"}, now="2026-09-13")
    s.add_person("Alex")
    s.add_criterion({"key": "daylight", "label": "Daylight", "kind": "subjective"},
                    now="2026-09-13")
    return s

def test_upsert_and_read(tmp_path):
    s = _store(tmp_path)
    s.upsert_score("a", "alex", "daylight", 4.0, now="2026-09-13")
    assert s.get_scores("a") == {("alex", "daylight"): 4.0}

def test_upsert_overwrites(tmp_path):
    s = _store(tmp_path)
    s.upsert_score("a", "alex", "daylight", 4.0, now="2026-09-13")
    s.upsert_score("a", "alex", "daylight", 2.0, now="2026-09-14")
    assert s.get_scores("a") == {("alex", "daylight"): 2.0}

def test_unscored_is_absent_not_zero(tmp_path):
    s = _store(tmp_path)
    assert s.get_scores("a") == {}

def test_delete_score_removes_one_persons_value(tmp_path):
    s = HouseStore(tmp_path / "ht.db")
    s.upsert_score("h1", "alex", "light", 4.0, now="2026-09-21")
    s.upsert_score("h1", "sam", "light", 2.0, now="2026-09-21")
    assert s.delete_score("h1", "alex", "light") is True
    assert s.get_scores("h1") == {("sam", "light"): 2.0}
    assert s.delete_score("h1", "alex", "light") is False
