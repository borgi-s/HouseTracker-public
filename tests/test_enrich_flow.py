# tests/test_enrich_flow.py
from housetracker.enrich.enrich import enrich_house
from housetracker.store import HouseStore

LOC = {"lat": 55.7861, "lon": 12.5234, "postal_code": "2800",
       "city": "Kongens Lyngby", "kommune": "Lyngby-Taarbæk", "kommunekode": "0173"}


class FakeGeocoder:
    def __init__(self, loc):
        self.loc = loc

    def geocode(self, address):
        return self.loc


class FakeRouter:
    def __init__(self, result=(10.0, 5000.0)):
        self.result, self.calls = result, []

    def route(self, start, end, mode):
        self.calls.append((start, end, mode))
        return self.result


def _store(tmp_path):
    s = HouseStore(tmp_path / "data" / "ht.db")
    s.add_anchor({"label": "Work", "lat": 55.7, "lon": 12.5, "kind": "fixed"})
    return s


def _house(store, address="Nyvej 2"):
    store.add_house({"address": address}, now="2026-09-18")
    return store.list_houses()[0]


def test_geocode_updates_house_and_routes_all_modes(tmp_path):
    s = _store(tmp_path)
    h = _house(s)
    summary = enrich_house(h, s, FakeGeocoder(LOC), FakeRouter(), now="2026-09-18")
    assert summary["geocoded"] is True
    assert summary["school_map_url"] and "12.5234/55.7861" in summary["school_map_url"]
    # 1 fixed anchor (work) x 3 modes = 3 commutes
    assert summary["commutes"] == 3
    stored = s.get_house(h.id)
    assert stored.lat == 55.7861 and stored.kommune == "Lyngby-Taarbæk"
    assert len(s.list_commutes(h.id)) == 3


def test_no_geocoder_uses_existing_coords(tmp_path):
    s = _store(tmp_path)
    s.add_house({"address": "Nyvej 2", "lat": 55.79, "lon": 12.52}, now="2026-09-18")
    h = s.list_houses()[0]
    summary = enrich_house(h, s, None, FakeRouter(), now="2026-09-18")
    assert summary["geocoded"] is False       # no geocoder ran
    assert summary["commutes"] == 3           # but existing coords still route
    assert summary["school_map_url"] is not None


def test_geocode_none_skips_routing_and_map(tmp_path):
    s = _store(tmp_path)
    h = _house(s)
    summary = enrich_house(h, s, FakeGeocoder(None), FakeRouter(), now="2026-09-18")
    assert summary == {"geocoded": False, "commutes": 0, "school_map_url": None,
                       "schools": 0}
    assert s.get_house(h.id).lat is None       # house untouched
    assert s.list_commutes(h.id) == []


def test_router_none_geocode_only(tmp_path):
    s = _store(tmp_path)
    h = _house(s)
    summary = enrich_house(h, s, FakeGeocoder(LOC), None, now="2026-09-18")
    assert summary["geocoded"] is True
    assert summary["commutes"] == 0            # no router -> no commutes
    assert summary["school_map_url"] is not None


def test_router_error_is_swallowed(tmp_path):
    s = _store(tmp_path)
    h = _house(s)

    class Boom:
        def route(self, start, end, mode):
            raise RuntimeError("ORS down")

    summary = enrich_house(h, s, FakeGeocoder(LOC), Boom(), now="2026-09-18")
    assert summary["geocoded"] is True         # geocode still persisted
    assert summary["commutes"] == 0            # routing failed, non-fatal
    assert s.get_house(h.id).lat == 55.7861


def test_district_schools_are_resolved_with_the_same_router(tmp_path, monkeypatch):
    s = _store(tmp_path)
    h = _house(s)
    router, seen = FakeRouter(), []

    def fake(house, store, r, geocoder, now):
        seen.append((house.kommune, r))
        return 2

    monkeypatch.setattr("housetracker.enrich.enrich.resolve_schools", fake)
    summary = enrich_house(h, s, FakeGeocoder(LOC), router, now="2026-09-18")
    assert summary["schools"] == 2
    assert seen == [("Lyngby-Taarbæk", router)]      # kommune from this geocode


def test_a_failing_school_lookup_never_fails_enrichment(tmp_path, monkeypatch):
    s = _store(tmp_path)
    h = _house(s)

    def boom(*a, **k):
        raise RuntimeError("GeoFA 500")

    monkeypatch.setattr("housetracker.enrich.enrich.resolve_schools", boom)
    summary = enrich_house(h, s, FakeGeocoder(LOC), FakeRouter(), now="2026-09-18")
    assert (summary["geocoded"], summary["commutes"], summary["schools"]) == (True, 3, 0)


class SpyGeocoder(FakeGeocoder):
    def geocode(self, address):
        self.asked = address
        return self.loc


def test_geocode_asks_with_the_postcode_and_town(tmp_path):
    s = _store(tmp_path)
    s.add_house({"address": "Møllehaven 17", "postal_code": "2800", "city": "Kongens Lyngby"},
                now="2026-10-01")
    g = SpyGeocoder(LOC)
    enrich_house(s.list_houses()[0], s, g, None, now="2026-10-01")
    assert g.asked == "Møllehaven 17, 2800 Kongens Lyngby"


def test_a_namesake_street_in_another_postcode_never_moves_the_house(tmp_path):
    s = _store(tmp_path)
    s.add_house({"address": "Møllehaven 17", "postal_code": "2800", "city": "Kongens Lyngby"},
                now="2026-10-01")
    helsinge = {**LOC, "lat": 56.02, "lon": 12.19, "postal_code": "3200", "city": "Helsinge"}
    summary = enrich_house(s.list_houses()[0], s, FakeGeocoder(helsinge), None, now="2026-10-01")
    h = s.list_houses()[0]
    assert summary["geocoded"] is False
    assert (h.postal_code, h.city, h.lat) == ("2800", "Kongens Lyngby", None)


def test_bbr_facts_fill_empty_fields_and_an_upstairs_in_the_text_counts_as_a_floor(tmp_path):
    s = _store(tmp_path)
    s.add_house({"address": "Birkevang 58", "postal_code": "2830",
                 "description": "Førstesalen rummer to værelser."}, now="2026-10-01")
    bbr = {**LOC, "postal_code": "2830", "floors": 1, "bathrooms": 1, "basement_m2": 32}
    enrich_house(s.list_houses()[0], s, FakeGeocoder(bbr), None, now="2026-10-01")
    h = s.list_houses()[0]
    assert (h.floors, h.bathrooms, h.basement_m2) == (2, 1, 32)
    s.update_house(h.id, {"bathrooms": 2}, now="2026-10-02")          # our own count wins
    enrich_house(s.get_house(h.id), s, FakeGeocoder(bbr), None, now="2026-10-03")
    assert s.get_house(h.id).bathrooms == 2


def test_floor_count_reads_the_listing_text():
    from housetracker.enrich.enrich import floor_count
    assert floor_count(1, "Stueplan med køkken. Førstesalen har tre værelser.") == 2
    assert floor_count(1, "Huset er fordelt på to plan") == 2
    assert floor_count(2, "Andensalen rummer et kontor") == 3
    assert floor_count(2, "Ingen trapper") == 2
    assert floor_count(1, "144 etagemeter fordelt over tre plan; førstesalen har tre værelser") == 2
    assert floor_count(None, None) is None


def test_bathroom_count_reads_the_listing_text():
    from housetracker.enrich.enrich import bathroom_count
    assert bathroom_count(1, "Boligen har desuden to moderne badeværelser") == 2
    assert bathroom_count(3, "et pænt og renoveret badeværelse") == 3
    assert bathroom_count(None, "") is None
