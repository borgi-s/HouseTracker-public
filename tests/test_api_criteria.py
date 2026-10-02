# tests/test_api_criteria.py
from housetracker.store import HouseStore


def _house(api, address="Nyvej 2, 2800"):
    return api.post("/api/houses", json={"address": address,
                                         "price_dkk": 5_000_000.0,
                                         "size_m2": 100.0}).json()["id"]


def test_add_and_list_criteria(api):
    r = api.post("/api/criteria", json={"key": "light", "label": "Light",
                                        "kind": "subjective", "weight": 2.0})
    assert r.status_code == 201 and r.json()["id"] == "light"
    assert [c["key"] for c in api.get("/api/criteria").json()] == ["light"]


def test_auto_criterion_without_a_source_is_422(api):
    r = api.post("/api/criteria", json={"key": "ppm2", "label": "Price/m2",
                                        "kind": "auto"})
    assert r.status_code == 422


def test_duplicate_key_is_409(api):
    body = {"key": "light", "label": "Light", "kind": "subjective"}
    assert api.post("/api/criteria", json=body).status_code == 201
    assert api.post("/api/criteria", json=body).status_code == 409


def test_deactivating_hides_a_criterion_from_the_default_list(api):
    api.post("/api/criteria", json={"key": "light", "label": "Light",
                                    "kind": "subjective"})
    assert api.patch("/api/criteria/light", json={"active": False}).status_code == 200
    assert api.get("/api/criteria").json() == []
    assert [c["key"] for c in
            api.get("/api/criteria", params={"active_only": False}).json()] == ["light"]


def test_score_requires_a_picked_person(api):
    hid = _house(api)
    api.post("/api/criteria", json={"key": "light", "label": "Light",
                                    "kind": "subjective"})
    assert api.put(f"/api/houses/{hid}/scores/light",
                   json={"value": 4.0}).status_code == 401


def test_score_upserts_and_is_attributed(api):
    hid = _house(api)
    api.post("/api/persons", json={"name": "Alex"})
    api.post("/api/session", json={"person_id": "alex"})
    api.post("/api/criteria", json={"key": "light", "label": "Light",
                                    "kind": "subjective"})
    assert api.put(f"/api/houses/{hid}/scores/light",
                   json={"value": 4.0}).json()["person_id"] == "alex"
    api.put(f"/api/houses/{hid}/scores/light", json={"value": 2.0})   # overwrite
    store = HouseStore(api.app.state.db_path)
    assert store.get_scores(hid) == {("alex", "light"): 2.0}
    store.conn.close()


def test_score_range_and_unknown_targets_are_rejected(api):
    hid = _house(api)
    api.post("/api/persons", json={"name": "Alex"})
    api.post("/api/session", json={"person_id": "alex"})
    api.post("/api/criteria", json={"key": "light", "label": "Light",
                                    "kind": "subjective"})
    assert api.put(f"/api/houses/{hid}/scores/light",
                   json={"value": 9.0}).status_code == 422
    assert api.put(f"/api/houses/{hid}/scores/nope",
                   json={"value": 3.0}).status_code == 404
    assert api.put("/api/houses/nope/scores/light",
                   json={"value": 3.0}).status_code == 404


def test_patch_criterion_edits_label_weight_and_sort(api):
    api.post("/api/criteria", json={"key": "light", "label": "Light",
                                    "kind": "subjective"})
    r = api.patch("/api/criteria/light", json={"label": "Daylight", "weight": 3.0,
                                               "sort": 2})
    assert r.status_code == 200
    c = r.json()
    assert (c["label"], c["weight"], c["sort"], c["active"]) == ("Daylight", 3.0, 2, True)
    assert api.patch("/api/criteria/light", json={"weight": -1}).status_code == 422
    assert api.patch("/api/criteria/nope", json={"weight": 1}).status_code == 404


def test_clear_score_removes_only_my_score_and_is_idempotent(api):
    hid = _house(api)
    api.post("/api/persons", json={"name": "Alex"})
    api.post("/api/persons", json={"name": "Sam"})
    api.post("/api/session", json={"person_id": "alex"})
    api.post("/api/criteria", json={"key": "light", "label": "Light",
                                    "kind": "subjective"})
    api.put(f"/api/houses/{hid}/scores/light", json={"value": 4.0})
    store = HouseStore(api.app.state.db_path)
    store.upsert_score(hid, "sam", "light", 2.0, now="2026-09-21")
    store.conn.close()

    r = api.delete(f"/api/houses/{hid}/scores/light")
    assert r.status_code == 200 and r.json()["deleted"] is True
    store = HouseStore(api.app.state.db_path)
    assert store.get_scores(hid) == {("sam", "light"): 2.0}
    store.conn.close()
    assert api.delete(f"/api/houses/{hid}/scores/light").json()["deleted"] is False
    assert api.delete("/api/houses/nope/scores/light").status_code == 404


def test_clear_score_requires_a_picked_person(api):
    hid = _house(api)
    assert api.delete(f"/api/houses/{hid}/scores/light").status_code == 401
