from housetracker.enrich.route import ORSRouter, _parse_ors

# Real ORS /json response shape: routes[0].summary.{duration (s), distance (m)}.
ORS_JSON = {"routes": [{"summary": {"distance": 8400.0, "duration": 750.0}}]}


def test_parse_ors_seconds_to_minutes():
    minutes, dist = _parse_ors(ORS_JSON)
    assert minutes == 12.5          # 750 s / 60
    assert dist == 8400.0


def test_ors_router_routes_via_fake_opener():
    seen = {}

    def opener(api_key, mode, coords):
        seen["key"], seen["mode"], seen["coords"] = api_key, mode, coords
        return ORS_JSON

    r = ORSRouter("KEY123", opener=opener)
    out = r.route((12.52, 55.79), (12.5234, 55.7861), "driving-car")
    assert out == (12.5, 8400.0)
    assert seen["key"] == "KEY123"
    assert seen["mode"] == "driving-car"
    assert seen["coords"] == [[12.52, 55.79], [12.5234, 55.7861]]   # [lon, lat]


def test_ors_router_unknown_mode_is_none():
    r = ORSRouter("K", opener=lambda *a: ORS_JSON)
    assert r.route((0, 0), (1, 1), "teleport") is None


def test_ors_router_swallows_errors():
    def boom(api_key, mode, coords):
        raise OSError("ORS down")
    assert ORSRouter("K", opener=boom).route((0, 0), (1, 1), "driving-car") is None
