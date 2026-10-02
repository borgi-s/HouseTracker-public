from housetracker.model import Criterion, House
from housetracker import scoring

def _crit(**kw):
    return Criterion.from_dict({"label": kw["key"].title(), **kw})

def test_auto_normalized_all_equal_lower_is_better_maps_to_1():
    # single house (trivially all-equal): lower-is-better must yield 1.0, not 0.0
    houses = [House.from_dict({"id": "a", "address": "A", "price_dkk": 4_000_000, "size_m2": 100})]
    c = _crit(key="ppm2", kind="auto", auto_source="price_per_m2", higher_is_better=False)
    assert scoring.auto_normalized(houses, c) == {"a": 1.0}

def test_auto_normalized_all_equal_multi_house_lower_is_better_maps_to_1():
    houses = [
        House.from_dict({"id": "a", "address": "A", "price_dkk": 4_000_000, "size_m2": 100}),
        House.from_dict({"id": "b", "address": "B", "price_dkk": 4_000_000, "size_m2": 100}),
    ]
    c = _crit(key="ppm2", kind="auto", auto_source="price_per_m2", higher_is_better=False)
    assert scoring.auto_normalized(houses, c) == {"a": 1.0, "b": 1.0}

def test_auto_normalized_min_max_lower_is_better():
    houses = [
        House.from_dict({"id": "a", "address": "A", "price_dkk": 4_000_000, "size_m2": 100}),  # 40k/m2
        House.from_dict({"id": "b", "address": "B", "price_dkk": 6_000_000, "size_m2": 100}),  # 60k/m2
    ]
    c = _crit(key="ppm2", kind="auto", auto_source="price_per_m2", higher_is_better=False)
    norm = scoring.auto_normalized(houses, c)
    assert norm["a"] == 1.0 and norm["b"] == 0.0  # cheaper per m2 scores higher

def test_person_overall_excludes_blanks():
    houses = [House.from_dict({"id": "a", "address": "A"})]
    crits = [_crit(key="light", kind="subjective", weight=1.0),
             _crit(key="garden", kind="subjective", weight=3.0)]
    scores = {("alex", "light"): 5.0}  # garden left blank -> excluded entirely
    # only 'light' counts: (1.0 * (5/5)) / 1.0 == 1.0
    assert scoring.person_overall(houses[0], "alex", houses, crits, scores) == 1.0

def test_person_overall_weighted_mix_subjective_and_auto():
    houses = [
        House.from_dict({"id": "a", "address": "A", "price_dkk": 4_000_000, "size_m2": 100}),
        House.from_dict({"id": "b", "address": "B", "price_dkk": 6_000_000, "size_m2": 100}),
    ]
    crits = [_crit(key="light", kind="subjective", weight=1.0),
             _crit(key="ppm2", kind="auto", auto_source="price_per_m2", higher_is_better=False, weight=1.0)]
    scores = {("alex", "light"): 3.0}  # 3/5 = 0.6 ; auto for a = 1.0
    # (1*0.6 + 1*1.0) / (1+1) = 0.8
    assert scoring.person_overall(houses[0], "alex", houses, crits, scores) == 0.8

def test_person_overall_none_when_nothing_scorable():
    houses = [House.from_dict({"id": "a", "address": "A"})]
    crits = [_crit(key="light", kind="subjective")]
    assert scoring.person_overall(houses[0], "alex", houses, crits, {}) is None

def test_disagreement_only_where_both_scored():
    crits = [_crit(key="light", kind="subjective"), _crit(key="garden", kind="subjective")]
    scores = {("alex", "light"): 5.0, ("partner", "light"): 2.0,
              ("alex", "garden"): 4.0}  # partner didn't score garden
    assert scoring.disagreement(crits, scores, ("alex", "partner")) == {"light": 3.0}

def test_person_overall_none_until_that_person_rated_something():
    # Owner, 2026-09-22: listings are added long before any viewing, so the automatic
    # criteria alone must not read as a rating ("Alex 1.7" before Alex rated anything).
    houses = [
        House.from_dict({"id": "a", "address": "A", "price_dkk": 4_000_000, "size_m2": 100}),
        House.from_dict({"id": "b", "address": "B", "price_dkk": 6_000_000, "size_m2": 100}),
    ]
    crits = [_crit(key="light", kind="subjective"),
             _crit(key="ppm2", kind="auto", auto_source="price_per_m2", higher_is_better=False)]
    assert scoring.person_overall(houses[0], "alex", houses, crits, {}) is None
    assert scoring.person_overall(houses[0], "alex", houses, crits, {("sam", "light"): 4.0}) is None
    assert scoring.person_overall(houses[0], "alex", houses, crits, {("alex", "light"): 3.0}) == 0.8
