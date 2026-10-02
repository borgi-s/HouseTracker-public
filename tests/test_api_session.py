def test_persons_add_and_list(api):
    assert api.get("/api/persons").json() == []
    r = api.post("/api/persons", json={"name": "Alex"})
    assert r.status_code == 201 and r.json()["id"] == "alex"
    api.post("/api/persons", json={"name": "Sam"})
    assert [p["name"] for p in api.get("/api/persons").json()] == ["Alex", "Sam"]


def test_session_starts_empty(api):
    assert api.get("/api/session").json() == {"person": None}


def test_pick_person_sets_a_sticky_cookie(api):
    api.post("/api/persons", json={"name": "Alex"})
    r = api.post("/api/session", json={"person_id": "alex"})
    assert r.status_code == 200 and r.json()["person"]["name"] == "Alex"
    assert api.cookies.get("ht_person") == "alex"
    # Sticky: a later request on the same client is already attributed.
    assert api.get("/api/session").json()["person"]["id"] == "alex"


def test_pick_unknown_person_is_404(api):
    r = api.post("/api/session", json={"person_id": "nobody"})
    assert r.status_code == 404
    assert api.get("/api/session").json() == {"person": None}


def test_clear_session(api):
    api.post("/api/persons", json={"name": "Alex"})
    api.post("/api/session", json={"person_id": "alex"})
    assert api.delete("/api/session").json() == {"person": None}
    assert api.get("/api/session").json() == {"person": None}


def test_stale_cookie_reads_as_no_person(api):
    api.cookies.set("ht_person", "deleted-person")
    assert api.get("/api/session").json() == {"person": None}


def test_duplicate_person_is_409(api):
    api.post("/api/persons", json={"name": "Alex"})
    r = api.post("/api/persons", json={"name": "Alex"})
    assert r.status_code == 409
    assert [p["name"] for p in api.get("/api/persons").json()] == ["Alex"]
