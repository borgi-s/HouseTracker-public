from datetime import date

from housetracker.store import HouseStore


class FakeGeocoder:
    def __init__(self, *a, **k):
        pass

    def geocode(self, address):
        return {"lat": 55.78, "lon": 12.52, "kommune": "Lyngby-Taarbæk",
                "postal_code": "2800", "city": "Kongens Lyngby", "address_id": "abc"}


class FakeRouter:
    def __init__(self, *a, **k):
        pass

    def route(self, origin, dest, mode):
        return (21.0, 8400.0)


class FakeProber:
    def __init__(self, *a, **k):
        pass

    def probe(self, url):
        return (404, url, "")            # -> 'gone' -> mark sold


class FakeBoligsiden:
    def __init__(self, *a, **k):
        pass

    def address(self, address_id):
        # dated today: a house added through the API has created_at = today
        return {"cases": [], "registrations": [
            {"date": date.today().isoformat(), "amount": 5_250_000, "type": "normal"}]}


def _house(api, **extra):
    return api.post("/api/houses",
                    json={"address": "Nyvej 2, 2800", **extra}).json()["id"]


def test_anchors_start_empty_and_are_addable(api):
    assert api.get("/api/anchors").json() == []
    r = api.post("/api/anchors", json={"label": "Mormor", "address": "Vejlevej 4",
                                       "lat": 55.6, "lon": 12.4})
    assert r.status_code == 201 and r.json()["id"] == "mormor"
    assert len(api.get("/api/anchors").json()) == 1


def test_anchor_without_a_label_is_422(api):
    assert api.post("/api/anchors", json={"address": "nowhere"}).status_code == 422


def test_enrich_geocodes_and_routes(api, monkeypatch):
    monkeypatch.setattr("housetracker.api.admin.AddressGeocoder", FakeGeocoder)
    monkeypatch.setattr("housetracker.api.admin.ORSRouter", FakeRouter)
    monkeypatch.setenv("HT_ORS_KEY", "test-key")
    api.post("/api/anchors", json={"label": "Work", "lat": 55.7, "lon": 12.5})
    hid = _house(api)
    r = api.post(f"/api/houses/{hid}/enrich")
    assert r.status_code == 200
    assert r.json()["geocoded"] is True
    assert r.json()["commutes"] == 3            # three ROUTE_MODES to the one fixed anchor
    d = api.get(f"/api/houses/{hid}").json()
    assert d["house"]["kommune"] == "Lyngby-Taarbæk"
    assert d["school_map_url"] is not None
    assert len(d["commutes"]) == 3


def test_enrich_without_a_routing_key_still_geocodes(api, monkeypatch):
    monkeypatch.setattr("housetracker.api.admin.AddressGeocoder", FakeGeocoder)
    monkeypatch.delenv("HT_ORS_KEY", raising=False)
    hid = _house(api)
    body = api.post(f"/api/houses/{hid}/enrich").json()
    assert body["geocoded"] is True and body["commutes"] == 0


def test_enrich_unknown_house_is_404(api):
    assert api.post("/api/houses/nope/enrich").status_code == 404


def test_lifecycle_sweep(api, monkeypatch):
    monkeypatch.setattr("housetracker.api.admin.HttpProber", FakeProber)
    monkeypatch.setattr("housetracker.api.admin.BoligsidenClient", FakeBoligsiden)
    monkeypatch.setattr("housetracker.api.admin.AddressGeocoder", FakeGeocoder)
    hid = _house(api, listing_url="https://x.dk/1")
    assert api.post("/api/admin/lifecycle").json() == {
        "checked": 1, "marked_sold": 1, "priced": 1, "repriced": 0, "skipped": 0, "open_new": 0}
    house = api.get(f"/api/houses/{hid}").json()["house"]
    assert house["status"] == "sold" and house["sold_price_dkk"] == 5_250_000.0


JSONLD_HTML = '''
<html><head>
<script type="application/ld+json">
{"@type": "RealEstateListing",
 "address": {"streetAddress": "Skovvej 3", "postalCode": "2800", "addressLocality": "Lyngby"},
 "offers": {"price": "4.995.000", "priceCurrency": "DKK"},
 "floorSize": {"value": 140},
 "description": "Dejligt hus",
 "image": ["https://cdn.example.dk/1.jpg", "https://cdn.example.dk/plantegning.png"]}
</script>
</head><body>
<a href="/media/salgsopstilling.pdf">Hent salgsopstilling</a>
</body></html>
'''


def test_scrape_adds_the_house_and_queues_the_media(api, monkeypatch):
    calls = []
    monkeypatch.setattr("housetracker.api.admin.fetch_html",
                        lambda url, lane_a, lane_b=None: JSONLD_HTML)
    monkeypatch.setattr("housetracker.api.admin.download_media",
                        lambda store, house_id, refs, data_dir, now: calls.append(
                            (house_id, len(refs))) or [])
    r = api.post("/api/houses/scrape", json={"url": "https://www.nybolig.dk/bolig/123"})
    assert r.status_code == 201
    body = r.json()
    assert body["address"] == "Skovvej 3" and body["price_dkk"] == 4995000.0
    assert body["media_pending"] >= 3
    # TestClient runs BackgroundTasks after the response — the download really fired.
    assert calls and calls[0][0] == body["id"]


def test_scrape_does_not_launch_a_browser_unless_asked(api, monkeypatch):
    seen = {}

    def fake_fetch(url, lane_a, lane_b=None):
        seen["lane_b"] = lane_b
        return JSONLD_HTML

    monkeypatch.setattr("housetracker.api.admin.fetch_html", fake_fetch)
    monkeypatch.setattr("housetracker.api.admin.download_media",
                        lambda *a, **k: [])
    monkeypatch.setattr("housetracker.api.admin.PatchrightFetcher",
                        lambda *a, **k: "LANE-B")
    api.post("/api/houses/scrape", json={"url": "https://x.dk/1"})
    assert seen["lane_b"] is None
    api.post("/api/houses/scrape", json={"url": "https://x.dk/2",
                                         "use_browser": True})
    assert seen["lane_b"] == "LANE-B"


def test_scrape_reports_a_fetch_failure_as_502(api, monkeypatch):
    from housetracker.scrape.fetch import FetchError

    def boom(url, lane_a, lane_b=None):
        raise FetchError("lane A failed for https://x.dk/1: 403")

    monkeypatch.setattr("housetracker.api.admin.fetch_html", boom)
    r = api.post("/api/houses/scrape", json={"url": "https://x.dk/1"})
    assert r.status_code == 502 and "403" in r.json()["detail"]


def test_scrape_without_an_address_is_422_and_adds_nothing(api, monkeypatch):
    monkeypatch.setattr("housetracker.api.admin.fetch_html",
                        lambda url, lane_a, lane_b=None: "<html><body>nope</body></html>")
    monkeypatch.setattr("housetracker.api.admin.download_media", lambda *a, **k: [])
    r = api.post("/api/houses/scrape", json={"url": "https://x.dk/1"})
    assert r.status_code == 422
    assert api.get("/api/houses").json() == []


def test_scraping_a_house_we_track_is_409_and_adds_nothing(api, monkeypatch):
    monkeypatch.setattr("housetracker.api.admin.fetch_html",
                        lambda url, lane_a, lane_b=None: JSONLD_HTML)
    monkeypatch.setattr("housetracker.api.admin.download_media", lambda *a, **k: [])
    first = api.post("/api/houses/scrape", json={"url": "https://x.dk/1"}).json()
    r = api.post("/api/houses/scrape", json={"url": "https://x.dk/1?utm_source=boliga"})
    assert r.status_code == 409
    assert r.json()["detail"]["house"]["id"] == first["id"]
    assert len(api.get("/api/houses").json()) == 1


def test_rescrape_refreshes_the_listing_and_queues_a_media_swap(api, monkeypatch):
    calls = []
    monkeypatch.setattr("housetracker.api.admin.fetch_html",
                        lambda url, lane_a, lane_b=None: JSONLD_HTML)
    monkeypatch.setattr("housetracker.api.admin.download_media", lambda *a, **k: [])
    hid = api.post("/api/houses/scrape", json={"url": "https://www.x.dk/bolig/123"}).json()["id"]
    monkeypatch.setattr("housetracker.api.admin.fetch_html",
                        lambda url, lane_a, lane_b=None: JSONLD_HTML.replace("Dejligt hus", "Nyt køkken"))
    monkeypatch.setattr("housetracker.api.admin.replace_scraped_media",
                        lambda store, house_id, refs, data_dir, now: calls.append((house_id, len(refs))) or [])
    r = api.post(f"/api/houses/{hid}/rescrape")
    assert r.status_code == 200
    assert r.json()["description"] == "Nyt køkken" and r.json()["media_pending"] >= 3
    assert calls and calls[0][0] == hid
    assert api.post("/api/houses/nope/rescrape").status_code == 404


OPEN_HOUSE_EVENT = ('<script type="application/ld+json">[{"@type": "Event", "name": "Åbent hus", '
                    '"startDate": "2099-10-04T15:30:00+02:00", "endDate": "2099-10-04T15:50:00+02:00"}]'
                    '</script>')


def test_scrape_and_rescrape_record_the_pages_open_houses(api, monkeypatch):
    monkeypatch.setattr("housetracker.api.admin.fetch_html",
                        lambda url, lane_a, lane_b=None: JSONLD_HTML + OPEN_HOUSE_EVENT)
    monkeypatch.setattr("housetracker.api.admin.download_media", lambda *a, **k: [])
    monkeypatch.setattr("housetracker.api.admin.replace_scraped_media", lambda *a, **k: [])
    hid = api.post("/api/houses/scrape", json={"url": "https://www.x.dk/bolig/123"}).json()["id"]
    store = HouseStore(api.app.state.db_path)
    assert [r["starts_at"] for r in store.list_open_houses(hid)] == ["2099-10-04T13:30:00Z"]
    monkeypatch.setattr("housetracker.api.admin.fetch_html",
                        lambda url, lane_a, lane_b=None: JSONLD_HTML + OPEN_HOUSE_EVENT.replace(
                            "2099-10-04", "2099-10-11"))
    assert api.post(f"/api/houses/{hid}/rescrape").status_code == 200
    assert [(r["starts_at"], r["cancelled"]) for r in store.list_open_houses(hid)] == [
        ("2099-10-04T13:30:00Z", True), ("2099-10-11T13:30:00Z", False)]


def test_anchor_with_only_an_address_is_geocoded(api, monkeypatch):
    monkeypatch.setattr("housetracker.api.admin.AddressGeocoder", FakeGeocoder)
    r = api.post("/api/anchors", json={"label": "Work", "address": "Arbejdsvej 1, 2800"})
    assert r.status_code == 201
    assert (r.json()["lat"], r.json()["lon"]) == (55.78, 12.52)


def test_anchor_whose_address_is_not_found_is_422(api, monkeypatch):
    class Nowhere(FakeGeocoder):
        def geocode(self, address):
            return None
    monkeypatch.setattr("housetracker.api.admin.AddressGeocoder", Nowhere)
    r = api.post("/api/anchors", json={"label": "Work", "address": "Nowhere 1"})
    assert r.status_code == 422 and api.get("/api/anchors").json() == []


def test_new_anchor_is_routed_to_every_located_house(api, monkeypatch):
    monkeypatch.setattr("housetracker.api.admin.ORSRouter", FakeRouter)
    monkeypatch.setenv("HT_ORS_KEY", "test-key")
    located = _house(api)
    HouseStore(api.app.state.db_path).update_house_location(located, 55.7, 12.5, now="x")
    unlocated = _house(api, address="Gammelvej 9, 2800")
    api.post("/api/anchors", json={"label": "Work", "lat": 55.8, "lon": 12.6})
    assert len(api.get(f"/api/houses/{located}").json()["commutes"]) == 3
    assert api.get(f"/api/houses/{unlocated}").json()["commutes"] == []


def test_delete_anchor(api):
    api.post("/api/anchors", json={"label": "Work", "lat": 55.8, "lon": 12.6})
    assert api.delete("/api/anchors/work").status_code == 200
    assert api.get("/api/anchors").json() == []
    assert api.delete("/api/anchors/work").status_code == 404


def test_settings_read_and_write(api, monkeypatch):
    monkeypatch.delenv("HT_DISCORD_WEBHOOK", raising=False)
    assert api.get("/api/settings").json() == {
        "notify_price_drops": True, "notify_open_houses": True, "discord_configured": False}
    r = api.patch("/api/settings", json={"notify_open_houses": False})
    assert r.json()["notify_open_houses"] is False and r.json()["notify_price_drops"] is True
    monkeypatch.setenv("HT_DISCORD_WEBHOOK", "https://discord.test/hook")
    assert api.get("/api/settings").json()["discord_configured"] is True


def test_edit_anchor_label_and_address(api, monkeypatch):
    monkeypatch.setattr("housetracker.api.admin.AddressGeocoder", FakeGeocoder)
    monkeypatch.setattr("housetracker.api.admin.ORSRouter", FakeRouter)
    monkeypatch.setenv("HT_ORS_KEY", "test-key")
    api.post("/api/anchors", json={"label": "Work", "lat": 55.8, "lon": 12.6})
    hid = _house(api)
    HouseStore(api.app.state.db_path).update_house_location(hid, 55.7, 12.5, now="x")
    r = api.patch("/api/anchors/work", json={"label": "Office"})
    assert r.status_code == 200 and r.json()["label"] == "Office" and r.json()["lat"] == 55.8
    r = api.patch("/api/anchors/work", json={"address": "Arbejdsvej 1, 2800"})
    assert (r.json()["lat"], r.json()["address"]) == (55.78, "Arbejdsvej 1, 2800")
    assert len(api.get(f"/api/houses/{hid}").json()["commutes"]) == 3   # re-routed


def test_edit_anchor_errors(api, monkeypatch):
    class Nowhere(FakeGeocoder):
        def geocode(self, address):
            return None
    monkeypatch.setattr("housetracker.api.admin.AddressGeocoder", Nowhere)
    api.post("/api/anchors", json={"label": "Work", "lat": 55.8, "lon": 12.6})
    assert api.patch("/api/anchors/nope", json={"label": "X"}).status_code == 404
    assert api.patch("/api/anchors/work", json={"address": "Nowhere 1"}).status_code == 422
    assert api.patch("/api/anchors/work", json={"label": ""}).status_code == 422
    assert api.get("/api/anchors").json()[0]["lat"] == 55.8
