import pytest

from housetracker.enrich.schools import ROUTE_CANDIDATES, resolve_schools
from housetracker.enrich.skolegang import kommune_url, school_url
from housetracker.store import HouseStore
from skolegang_pages import kommune_page, school_page

HOUSE = (55.790, 12.470)            # lat, lon


class Site:
    """skolegang.dk stand-in: url -> html; anything else is a 404."""
    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def __call__(self, url):
        self.calls.append(url)
        if url not in self.pages:
            raise RuntimeError(f"404 {url}")
        return self.pages[url]


def site(kommune, schools):
    """schools: [(slug, inst, name, lat, lon, extra props...)]"""
    pages = {kommune_url(kommune): kommune_page(*[s[0] for s in schools])}
    for slug, inst, name, lat, lon, *props in schools:
        pages[school_url(slug)] = school_page(inst, name, lat, lon, **dict(props))
    return Site(pages)


class Geofa:
    def __init__(self, rows):
        self.rows, self.sql = rows, []

    def __call__(self, sql):
        self.sql.append(sql)
        if isinstance(self.rows, Exception):
            raise self.rows
        return self.rows


class Router:
    """Walking minutes per school (inst -> minutes), found by the school's (lat, lon) in
    `at`; bike = walk / 3. ORS takes (lon, lat)."""
    def __init__(self, walk, at):
        self.walk, self.calls = walk, []
        self.by_point = {(lon, lat): inst for inst, (lat, lon) in at.items()}

    def route(self, start, end, mode):
        self.calls.append((end, mode))
        m = self.walk[self.by_point[end]]
        return (m, m * 80.0) if mode == "foot-walking" else (m / 3, m * 90.0)


def _house(store, kommune="Lyngby-Taarbæk", lat=HOUSE[0], lon=HOUSE[1]):
    h = store.add_house({"address": "Nyvej 2"}, now="2026-09-26")
    store.update_house_location(h.id, lat=lat, lon=lon, kommune=kommune, now="2026-09-26")
    return store.get_house(h.id)


def district(name, inst, start=11, stop=9, link=None):
    return {"name": name, "start": start, "stop": stop, "link": link, "inst": inst}


def run(store, house, fetch, geofa, router=None, now="2026-09-26", geocoder=None):
    return resolve_schools(house, store, router, geocoder, now, fetch=fetch, geofa=geofa,
                           sleep=lambda s: None)


@pytest.fixture
def store(tmp_path):
    return HouseStore(tmp_path / "data" / "ht.db")


def test_a_one_school_district_stores_that_school_with_walk_and_bike(store):
    h = _house(store)
    web = site("Lyngby-Taarbæk", [("fugl", "173003", "Fuglsanggårdsskolen", 55.793, 12.479),
                                  ("virum", "173011", "Virum Skole", 55.790, 12.460)])
    geofa = Geofa([district("Fuglsanggårdsskolen", "173003")])
    r = Router({"173003": 12.0, "173011": 5.0},
               {"173003": (55.793, 12.479), "173011": (55.790, 12.460)})
    assert run(store, h, web, geofa, r) == 1
    [row] = store.list_house_schools(h.id)
    assert (row["inst_nr"], row["rank"], row["district_grades"], row["district_schools"],
            row["fallback"]) == ("173003", 1, "0.–9.", 1, False)
    assert (row["walk_min"], row["walk_m"], row["bike_min"]) == (12.0, 960.0, 4.0)
    assert "'173003'" in geofa.sql[0] and "'173011'" in geofa.sql[0]
    assert "ST_MakePoint(12.47, 55.79)" in geofa.sql[0]          # the house, lon first


def test_a_shared_district_keeps_the_three_nearest_by_walking_routing_only_five(store):
    h = _house(store, kommune="Gentofte")
    schools = [(f"s{i}", f"15700{i}", f"Skole {i}", HOUSE[0] + 0.001 * i, HOUSE[1])
               for i in range(1, 8)]                        # s1 nearest ... s7 farthest
    web = site("Gentofte", schools)
    geofa = Geofa([district("Gentofte", s[1], link="https://gentofte.dk/skoler")
                   for s in schools])
    # by walking the 5 straight-line nearest order s5, s4, s1, s3, s2 (s6, s7 never routed)
    r = Router({"157005": 3.0, "157004": 4.0, "157001": 5.0, "157003": 6.0, "157002": 7.0,
                "157006": 1.0, "157007": 1.0}, {s[1]: (s[3], s[4]) for s in schools})
    assert run(store, h, web, geofa, r) == 3
    rows = store.list_house_schools(h.id)
    assert [x["inst_nr"] for x in rows] == ["157005", "157004", "157001"]
    assert len(r.calls) == ROUTE_CANDIDATES * 2
    assert {x["district_schools"] for x in rows} == {7}
    assert rows[0]["district_link"] == "https://gentofte.dk/skoler"


def test_a_grade_split_gives_two_districts_and_the_named_school_wins(store):
    h = _house(store)
    web = site("Lyngby-Taarbæk", [("trong", "173009", "Trongårdsskolen", 55.781, 12.531),
                                  ("taarb", "173008", "Taarbæk Skole", 55.787, 12.595)])
    geofa = Geofa([district("Trongårdsskolen", "173009", 11, 6),
                   district("Trongårdsskolen", "173009", 7, 9),
                   district("Trongårdsskolen", "173008", 7, 9)])   # Taarbæk sits in 7.-9.
    assert run(store, h, web, geofa) == 2
    rows = store.list_house_schools(h.id)
    assert [(x["district_order"], x["district_grades"], x["inst_nr"], x["district_schools"])
            for x in rows] == [(0, "0.–6.", "173009", 1), (1, "7.–9.", "173009", 1)]


def test_a_district_with_no_school_inside_falls_back_to_the_nearest_three(store):
    h = _house(store)
    schools = [(f"s{i}", f"17300{i}", f"Skole {i}", HOUSE[0] + 0.001 * i, HOUSE[1])
               for i in range(1, 6)]
    geofa = Geofa([district("Vadgård", None)])
    assert run(store, h, site("Lyngby-Taarbæk", schools), geofa) == 3
    rows = store.list_house_schools(h.id)
    assert [x["inst_nr"] for x in rows] == ["173001", "173002", "173003"]
    assert all(x["fallback"] and x["district_schools"] == 0 for x in rows)


def test_without_a_router_order_is_by_straight_line_and_times_are_blank(store):
    h = _house(store)
    schools = [("far", "173001", "Far Skole", HOUSE[0] + 0.01, HOUSE[1]),
               ("near", "173002", "Near Skole", HOUSE[0] + 0.001, HOUSE[1])]
    geofa = Geofa([district("Område", "173001"), district("Område", "173002")])
    run(store, h, site("Lyngby-Taarbæk", schools), geofa)
    rows = store.list_house_schools(h.id)
    assert [x["inst_nr"] for x in rows] == ["173002", "173001"]
    assert rows[0]["walk_min"] is None and rows[0]["straight_m"] == 111


def test_a_geofa_failure_raises_and_leaves_the_previous_schools(store):
    h = _house(store)
    web = site("Lyngby-Taarbæk", [("fugl", "173003", "Fuglsanggårdsskolen", 55.793, 12.479)])
    run(store, h, web, Geofa([district("Fuglsanggårdsskolen", "173003")]))
    with pytest.raises(RuntimeError):
        run(store, h, web, Geofa(RuntimeError("GeoFA 500")))
    assert [x["inst_nr"] for x in store.list_house_schools(h.id)] == ["173003"]


def test_the_school_list_is_reused_for_30_days_and_survives_a_dead_site(store):
    h = _house(store)
    web = site("Lyngby-Taarbæk", [("fugl", "173003", "Fuglsanggårdsskolen", 55.793, 12.479)])
    geofa = Geofa([district("Fuglsanggårdsskolen", "173003")])
    run(store, h, web, geofa, now="2026-09-26")
    fetched = len(web.calls)
    run(store, h, web, geofa, now="2026-10-25")            # 29 days: no refetch
    assert len(web.calls) == fetched
    dead = Site({})
    assert run(store, h, dead, geofa, now="2026-10-27") == 1   # 31 days, site down: stale list
    assert dead.calls == [kommune_url("Lyngby-Taarbæk")]


def test_no_coordinates_or_kommune_means_nothing_is_fetched(store):
    h = store.add_house({"address": "Nyvej 2"}, now="2026-09-26")
    web = Site({})
    assert run(store, h, web, Geofa([])) == 0
    assert web.calls == []


def test_non_folkeskoler_and_unsafe_ids_never_reach_the_store_or_the_sql(store):
    h = _house(store)
    web = site("Lyngby-Taarbæk", [
        ("fugl", "173003", "Fuglsanggårdsskolen", 55.793, 12.479),
        ("special", "173020", "Sorgenfriskolen", 55.79, 12.47, ("InstTypeNr", "1015")),
        ("evil", "1') OR 1=1 --", "Evil Skole", 55.79, 12.47)])
    geofa = Geofa([district("Fuglsanggårdsskolen", "173003")])
    run(store, h, web, geofa)
    assert [s["inst_nr"] for s in store.list_schools("Lyngby-Taarbæk")] == ["173003"]
    assert "OR 1=1" not in geofa.sql[0] and "173020" not in geofa.sql[0]


def test_a_register_gap_school_is_added_from_extra_schools_and_geocoded(store):
    h = _house(store, kommune="Gentofte")
    web = site("Gentofte", [("gentofte-skole", "157003", "Gentofte Skole", 55.743, 12.547)])
    web.pages[school_url("tranegaardskolen")] = (
        '<script type="application/ld+json">{"@type":"School","name":"Tranegårdskolen",'
        '"additionalProperty":[{"name":"InstitutionsNummer","value":"157012"},'
        '{"name":"År","value":"2024/2025"}]}</script>')

    class Dawa:
        def geocode(self, address):
            assert address == "Gersonsvej 38, 2900 Hellerup"
            return {"lat": 55.735, "lon": 12.566}

    run(store, h, web, Geofa([district("Gentofte", "157003")]), geocoder=Dawa())
    t = store.get_school("157012")
    assert (t["lat"], t["address"], t["kommune"]) == (55.735, "Gersonsvej 38, 2900 Hellerup",
                                                      "Gentofte")


def test_a_routing_outage_keeps_the_walk_and_bike_times_we_had(store):
    h = _house(store)
    web = site("Lyngby-Taarbæk", [("fugl", "173003", "Fuglsanggårdsskolen", 55.793, 12.479)])
    geofa = Geofa([district("Fuglsanggårdsskolen", "173003")])
    run(store, h, web, geofa, Router({"173003": 12.0}, {"173003": (55.793, 12.479)}))

    class Down:
        def route(self, start, end, mode):
            return None

    assert run(store, h, web, geofa, Down()) == 0         # ORS down or rate-limited
    assert run(store, h, web, geofa, None) == 0           # no key / --no-route
    [row] = store.list_house_schools(h.id)
    assert (row["walk_min"], row["bike_min"]) == (12.0, 4.0)


def test_a_school_that_drops_off_the_list_does_not_turn_the_cache_off(store):
    h = _house(store)
    web = site("Lyngby-Taarbæk", [("fugl", "173003", "Fuglsanggårdsskolen", 55.793, 12.479),
                                  ("virum", "173011", "Virum Skole", 55.790, 12.460)])
    geofa = Geofa([district("Fuglsanggårdsskolen", "173003")])
    run(store, h, web, geofa, now="2026-09-26")
    web.pages[kommune_url("Lyngby-Taarbæk")] = kommune_page("fugl")     # Virum closes
    run(store, h, web, geofa, now="2026-10-27")           # monthly re-read; Virum's row goes stale
    calls = len(web.calls)
    run(store, h, web, geofa, now="2026-10-28")
    assert len(web.calls) == calls                        # the kommune is fresh again
