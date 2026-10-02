from housetracker.enrich.schools import (
    BASELAYER, DEFAULT_ZOOM, FKG_CONFIG, SCHOOL_DISTRICT_LAYER, school_district_map_url,
)


def test_url_centres_on_house_lon_then_lat_with_the_district_layer_on():
    url = school_district_map_url(12.5234, 55.7861, zoom=15)
    base, frag = url.split("#", 1)
    assert base.startswith("https://geofa-kort.geodanmark.dk/app/fkg/?config=")
    assert FKG_CONFIG in base
    assert frag == f"{BASELAYER}/15/12.5234/55.7861/{SCHOOL_DISTRICT_LAYER}"   # lon before lat


def test_config_is_a_real_published_key():
    # GeoFA keys end in a hash; without it the map loads no layers ("No schemata").
    # Verified in a browser 2026-09-22: this config draws the 5710 districts.
    assert FKG_CONFIG.endswith("/configuration_distrikter_69d0c3b971df1242454664.json")
    assert SCHOOL_DISTRICT_LAYER == "fkg.t_5710_born_skole_dis"


def test_url_defaults_zoom():
    url = school_district_map_url(12.0, 55.0)
    assert f"/{DEFAULT_ZOOM}/12.0/55.0/" in url


def test_url_is_https():
    assert school_district_map_url(12.0, 55.0).startswith("https://")
