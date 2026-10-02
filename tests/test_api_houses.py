from housetracker.store import HouseStore


def _seed(api):
    """Two people, one subjective + one auto criterion, two houses with scores."""
    api.post("/api/persons", json={"name": "Alex"})
    api.post("/api/persons", json={"name": "Sam"})
    store = HouseStore(api.app.state.db_path)
    store.add_criterion({"key": "light", "label": "Light", "kind": "subjective",
                         "weight": 2.0}, now="2026-09-20")
    store.add_criterion({"key": "ppm2", "label": "Price/m2", "kind": "auto",
                         "auto_source": "price_per_m2", "higher_is_better": False},
                        now="2026-09-20")
    a = store.add_house({"address": "Nyvej 2, 2800", "price_dkk": 5_000_000.0,
                         "size_m2": 100.0}, now="2026-09-20")
    b = store.add_house({"address": "Andenvej 9, 2800", "price_dkk": 8_000_000.0,
                         "size_m2": 100.0}, now="2026-09-20")
    store.upsert_score(a.id, "alex", "light", 5.0, now="2026-09-20")
    store.upsert_score(a.id, "sam", "light", 2.0, now="2026-09-20")
    store.conn.close()
    return a.id, b.id


def test_list_houses_includes_price_per_m2(api):
    a, _ = _seed(api)
    rows = api.get("/api/houses").json()
    assert len(rows) == 2
    first = [r for r in rows if r["id"] == a][0]
    assert first["address"] == "Nyvej 2, 2800"
    assert first["price_per_m2"] == 50_000.0


def test_house_detail_assembles_everything(api):
    a, _ = _seed(api)
    d = api.get(f"/api/houses/{a}").json()
    assert d["house"]["id"] == a
    assert d["status_history"] == [{"status": "not_visited", "at": "2026-09-20"}]
    assert d["scores"] == {"alex": {"light": 5.0}, "sam": {"light": 2.0}}
    # light=5/5 weighted 2.0 + auto ppm2 (cheapest of the two -> 1.0) weighted 1.0
    assert d["overall"]["alex"] == 1.0
    assert d["disagreement"] == {"light": 3.0}
    assert d["media"] == [] and d["notes"] == [] and d["tags"] == []
    assert d["school_map_url"] is None          # not geocoded yet
    assert d["schools"] is None                 # no district lookup yet


def test_house_detail_exposes_the_school_map_once_geocoded(api):
    a, _ = _seed(api)
    store = HouseStore(api.app.state.db_path)
    store.update_house_location(a, lat=55.78, lon=12.52, now="2026-09-20")
    store.conn.close()
    url = api.get(f"/api/houses/{a}").json()["school_map_url"]
    assert url is not None and "12.52/55.78" in url     # Vidi hash is lon before lat


def test_unknown_house_is_404(api):
    assert api.get("/api/houses/nope").status_code == 404


def test_rank_orders_by_overall(api):
    a, b = _seed(api)
    rows = api.get("/api/rank", params={"person_id": "alex"}).json()
    assert [r["house_id"] for r in rows] == [a, b]
    assert rows[0]["overall"] == 1.0
    assert rows[0]["address"] == "Nyvej 2, 2800"


def test_create_house_manually(api):
    r = api.post("/api/houses", json={"address": "Kvikvej 1, 2800",
                                      "price_dkk": 4_200_000.0, "size_m2": 84.0})
    assert r.status_code == 201
    body = r.json()
    assert body["id"] == "kvikvej-1-2800" and body["status"] == "not_visited"
    assert body["price_per_m2"] == 50_000.0


def test_adding_a_house_we_track_is_409_naming_it_and_its_status(api):
    hid = api.post("/api/houses", json={"address": "Kvikvej 1", "postal_code": "2800"}).json()["id"]
    api.patch(f"/api/houses/{hid}/status", json={"status": "rejected"})
    r = api.post("/api/houses", json={"address": "Kvikvej 1", "postal_code": "2800"})
    assert r.status_code == 409
    assert r.json()["detail"]["house"] == {"id": hid, "address": "Kvikvej 1",
                                           "status": "rejected"}
    assert len(api.get("/api/houses").json()) == 1


def test_create_house_rejects_a_negative_price(api):
    r = api.post("/api/houses", json={"address": "X 1", "price_dkk": -5.0})
    assert r.status_code == 422


def test_set_status_logs_an_event(api):
    a, _ = _seed(api)
    r = api.patch(f"/api/houses/{a}/status", json={"status": "shortlist"})
    assert r.status_code == 200 and r.json()["status"] == "shortlist"
    hist = api.get(f"/api/houses/{a}").json()["status_history"]
    assert [e["status"] for e in hist] == ["not_visited", "shortlist"]


def test_set_unknown_status_is_422_and_unknown_house_is_404(api):
    a, _ = _seed(api)
    assert api.patch(f"/api/houses/{a}/status",
                     json={"status": "maybe"}).status_code == 422
    assert api.patch("/api/houses/nope/status",
                     json={"status": "sold"}).status_code == 404


def test_notes_require_a_picked_person(api):
    a, _ = _seed(api)
    assert api.post(f"/api/houses/{a}/notes",
                    json={"body": "dark"}).status_code == 401


def test_note_and_tag_attribution(api):
    a, _ = _seed(api)
    api.post("/api/session", json={"person_id": "alex"})
    mine = api.post(f"/api/houses/{a}/notes", json={"body": "Kitchen is dark"})
    ours = api.post(f"/api/houses/{a}/notes",
                    json={"body": "Offer deadline Friday", "shared": True})
    assert mine.status_code == 201 and mine.json()["person_id"] == "alex"
    assert ours.json()["person_id"] is None
    tag = api.post(f"/api/houses/{a}/tags", json={"label": "needs-new-roof"})
    assert tag.status_code == 201 and tag.json()["person_id"] == "alex"

    d = api.get(f"/api/houses/{a}").json()
    assert [n["body"] for n in d["notes"]] == ["Kitchen is dark",
                                               "Offer deadline Friday"]
    assert [t["label"] for t in d["tags"]] == ["needs-new-roof"]

    assert api.delete(f"/api/tags/{tag.json()['id']}").status_code == 200
    assert api.get(f"/api/houses/{a}").json()["tags"] == []
    assert api.delete(f"/api/tags/{tag.json()['id']}").status_code == 404


def test_empty_note_body_is_422(api):
    a, _ = _seed(api)
    api.post("/api/session", json={"person_id": "alex"})
    assert api.post(f"/api/houses/{a}/notes",
                    json={"body": "  "}).status_code == 422


def test_list_houses_carries_cover_overall_and_disagreement(api):
    a, b = _seed(api)
    c = api.post("/api/houses", json={"address": "Tomvej 3, 2800"}).json()["id"]
    store = HouseStore(api.app.state.db_path)
    store.add_media({"house_id": a, "kind": "floorplan", "path": "/x/fp.png"},
                    now="2026-09-21")
    store.add_media({"house_id": a, "kind": "photo", "path": "/x/p2.jpg", "sort": 2},
                    now="2026-09-21")
    p1 = store.add_media({"house_id": a, "kind": "photo", "path": "/x/p1.jpg",
                          "sort": 1}, now="2026-09-21")
    u = store.add_media({"house_id": b, "kind": "user_photo", "path": "/x/u.jpg",
                         "source": "manual"}, now="2026-09-21")
    store.conn.close()

    rows = {r["id"]: r for r in api.get("/api/houses").json()}
    assert rows[a]["cover_url"] == f"/api/media/{p1.id}/file"   # lowest-sort scraped photo
    assert rows[b]["cover_url"] == f"/api/media/{u.id}/file"    # falls back to our own
    assert rows[c]["cover_url"] is None
    assert rows[a]["overall"]["alex"] == 1.0                    # same number as the detail
    assert rows[a]["disagreement"] == {"light": 3.0}
    assert rows[b]["disagreement"] == {}


def test_patch_house_edits_fields_and_keeps_status_history(api):
    a, _ = _seed(api)
    r = api.patch(f"/api/houses/{a}", json={"price_dkk": 4_000_000.0,
                                            "energy_label": "B"})
    assert r.status_code == 200
    body = r.json()
    assert body["price_dkk"] == 4_000_000.0 and body["energy_label"] == "B"
    assert body["price_per_m2"] == 40_000.0
    assert len(api.get(f"/api/houses/{a}").json()["status_history"]) == 1


def test_patch_house_can_clear_a_field_but_not_the_address(api):
    a, _ = _seed(api)
    assert api.patch(f"/api/houses/{a}", json={"size_m2": None}).json()["size_m2"] is None
    assert api.patch(f"/api/houses/{a}", json={"address": None}).status_code == 422
    assert api.patch(f"/api/houses/{a}", json={"price_dkk": -1}).status_code == 422
    assert api.patch("/api/houses/nope", json={"city": "X"}).status_code == 404


def test_delete_note(api):
    a, _ = _seed(api)
    api.post("/api/session", json={"person_id": "alex"})
    n = api.post(f"/api/houses/{a}/notes", json={"body": "Kitchen is dark"}).json()
    assert api.delete(f"/api/notes/{n['id']}").json() == {"deleted": n["id"]}
    assert api.get(f"/api/houses/{a}").json()["notes"] == []
    assert api.delete(f"/api/notes/{n['id']}").status_code == 404


def test_a_house_never_checked_has_a_short_price_story(api):
    a, _ = _seed(api)
    assert api.get(f"/api/houses/{a}").json()["price_history"] == {
        "events": [{"price_dkk": 5_000_000.0, "at": "2026-09-20", "source": "added"}],
        "listing": None, "sales": [], "original_price_dkk": 5_000_000.0}


def test_list_and_detail_carry_the_price_story(api):
    a, _ = _seed(api)
    store = HouseStore(api.app.state.db_path)
    sales = [{"date": "2019-05-20", "price_dkk": 4_195_000.0, "type": "normal"}]
    store.save_listing(a, {"address_id": "abc", "listed_price_dkk": 5_200_000.0,
                           "listed_date": "2026-09-01", "days_on_market": 25,
                           "total_days_on_market": 25, "realtor": "EDC Lyngby",
                           "checked_at": "2026-09-26", "sales": sales})
    store.record_price(a, 4_900_000.0, "boligsiden", now="2026-09-26")
    store.conn.close()

    row = [r for r in api.get("/api/houses").json() if r["id"] == a][0]
    assert row["price_dkk"] == 4_900_000.0 and row["original_price_dkk"] == 5_200_000.0

    ph = api.get(f"/api/houses/{a}").json()["price_history"]
    assert ph["events"] == [
        {"price_dkk": 5_000_000.0, "at": "2026-09-20", "source": "added"},
        {"price_dkk": 4_900_000.0, "at": "2026-09-26", "source": "boligsiden"}]
    assert ph["listing"] == {"listed_price_dkk": 5_200_000.0, "listed_date": "2026-09-01",
                             "days_on_market": 25, "total_days_on_market": 25,
                             "realtor": "EDC Lyngby", "checked_at": "2026-09-26"}
    assert ph["sales"] == sales
    assert ph["original_price_dkk"] == 5_200_000.0


def test_delete_house_removes_rows_and_files(api):
    a, b = _seed(api)
    store = HouseStore(api.app.state.db_path)
    store.add_note(a, None, "nice", now="2026-09-20")
    store.conn.close()
    folder = api.app.state.data_dir / "houses" / a
    folder.mkdir(parents=True)
    (folder / "x.jpg").write_bytes(b"x")

    assert api.delete(f"/api/houses/{a}").json() == {"deleted": a}
    assert api.get(f"/api/houses/{a}").status_code == 404
    assert not folder.exists()
    store = HouseStore(api.app.state.db_path)
    assert store.get_scores(a) == {} and store.list_notes(a) == []
    assert store.get_house(b) is not None
    store.conn.close()
    assert api.delete(f"/api/houses/{a}").status_code == 404


def _figures(grade, year="2024/2025", rank=None):
    return {"year": year, "total_schools": 2870, "national": {}, "significance": None,
            "series": {"karaktergennemsnit": [[year, grade]]},
            "snapshot": {"grade": grade}, "rank": {"grade": rank} if rank else {}}


def test_house_detail_lists_district_schools_against_the_kommune_average(api):
    a, _ = _seed(api)
    store = HouseStore(api.app.state.db_path)
    for inst, slug, grade, rank in (("173003", "fuglsanggaardsskolen", 8.8, 71),
                                    ("173011", "virum-skole", 7.8, 900)):
        store.upsert_school({"inst_nr": inst, "slug": slug, "name": slug, "address": "Vej 1",
                             "lat": 55.79, "lon": 12.47, "kommune": "Lyngby-Taarbæk",
                             "top_grade": 9, "fetched_at": "2026-09-26",
                             "figures": _figures(grade, rank=rank)})
    store.replace_house_schools(a, [{
        "district_order": 0, "rank": 1, "district_name": "Fuglsanggårdsskolen",
        "district_grades": "0.–9.", "district_link": None, "district_schools": 1,
        "fallback": False, "inst_nr": "173003", "walk_min": 11.5, "walk_m": 900.0,
        "bike_min": 4.0, "bike_m": 1000.0, "straight_m": 700}], "2026-09-26")
    store.conn.close()
    sch = api.get(f"/api/houses/{a}").json()["schools"]
    assert sch["checked_at"] == "2026-09-26"
    [d] = sch["districts"]
    assert (d["name"], d["grades"], d["school_count"], d["fallback"]) == \
        ("Fuglsanggårdsskolen", "0.–9.", 1, False)
    [school] = d["schools"]
    assert school["url"] == "https://skolegang.dk/skole/fuglsanggaardsskolen"
    assert (school["grades"], school["walk_min"], school["bike_m"]) == ("0.–9.", 11.5, 1000.0)
    grade = next(f for f in school["figures"] if f["key"] == "grade")
    assert (grade["value"], grade["year"], grade["kommune_avg"], grade["national_rank"]) == \
        (8.8, "2024/2025", 8.3, 71)


def test_open_houses_upcoming_on_the_list_and_all_on_the_detail(api):
    a, b = _seed(api)
    store = HouseStore(api.app.state.db_path)
    held = {"starts_at": "2026-01-04T10:00:00Z", "ends_at": "2026-01-04T10:30:00Z",
            "signup": False, "signup_url": None}
    later = {"starts_at": "2099-10-11T08:00:00Z", "ends_at": "2099-10-11T08:30:00Z",
             "signup": True, "signup_url": None}
    cancelled = {"starts_at": "2099-10-04T13:30:00Z", "ends_at": "2099-10-04T13:50:00Z",
                 "signup": None, "signup_url": None}
    store.sync_open_houses(a, [held, later, cancelled], "agency", "2026-01-01T00:00:00Z")
    store.sync_open_houses(a, [held, later], "agency", "2026-01-02T00:00:00Z")
    store.conn.close()
    items = {r["id"]: r for r in api.get("/api/houses").json()}
    assert items[a]["open_houses"] == [{**later, "cancelled": False}]
    assert items[b]["open_houses"] == []
    detail = api.get(f"/api/houses/{a}").json()["open_houses"]
    assert [(o["starts_at"], o["cancelled"]) for o in detail] == [
        ("2026-01-04T10:00:00Z", False), ("2099-10-04T13:30:00Z", True), ("2099-10-11T08:00:00Z", False)]
