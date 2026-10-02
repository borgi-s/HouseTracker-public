import pytest
from housetracker.store import HouseStore
from housetracker.model import ValidationError

def _store(tmp_path):
    return HouseStore(tmp_path / "ht.db")

def test_add_and_list_persons(tmp_path):
    s = _store(tmp_path)
    s.add_person("Alex")
    s.add_person("Partner")
    assert sorted(p.name for p in s.list_persons()) == ["Alex", "Partner"]

def test_add_subjective_criterion(tmp_path):
    s = _store(tmp_path)
    c = s.add_criterion({"key": "daylight", "label": "Daylight",
                         "kind": "subjective", "weight": 2.0}, now="2026-09-13")
    assert c.id == "daylight"
    assert [x.key for x in s.list_criteria()] == ["daylight"]

def test_auto_criterion_requires_source(tmp_path):
    s = _store(tmp_path)
    with pytest.raises(ValidationError):
        s.add_criterion({"key": "value", "label": "Value", "kind": "auto"},
                        now="2026-09-13")

def test_criteria_are_runtime_extensible_and_deactivatable(tmp_path):
    s = _store(tmp_path)
    s.add_criterion({"key": "a", "label": "A", "kind": "subjective"}, now="2026-09-13")
    b = s.add_criterion({"key": "b", "label": "B", "kind": "subjective"}, now="2026-09-13")
    s.update_criterion(b.id, {"active": False})
    assert [c.key for c in s.list_criteria(active_only=True)] == ["a"]
    assert len(s.list_criteria(active_only=False)) == 2


def test_update_criterion_edits_label_weight_sort(tmp_path):
    s = _store(tmp_path)
    s.add_criterion({"key": "light", "label": "Light", "kind": "subjective"},
                    now="2026-09-13")
    c = s.update_criterion("light", {"label": "Daylight", "weight": 2.5, "sort": 3})
    assert (c.label, c.weight, c.sort, c.active) == ("Daylight", 2.5, 3, True)
    assert s.list_criteria()[0].label == "Daylight"


def test_update_criterion_validates(tmp_path):
    s = _store(tmp_path)
    s.add_criterion({"key": "light", "label": "Light", "kind": "subjective"},
                    now="2026-09-13")
    with pytest.raises(ValidationError):
        s.update_criterion("light", {"weight": -1.0})
    with pytest.raises(ValidationError):
        s.update_criterion("light", {"key": "dark"})          # keys are identity
    with pytest.raises(ValidationError):
        s.update_criterion("nope", {"weight": 1.0})
    assert s.list_criteria()[0].weight == 1.0
