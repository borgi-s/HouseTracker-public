# tests/test_lifecycle_boligsiden.py
import json

from housetracker.lifecycle.boligsiden import (
    BOLIGSIDEN_API, BoligsidenClient, parse_address,
)

# Shaped like the real GET /addresses/0a3f50a6-5b14-32b8-e044-0003ba298018 answer
# (Grøndalvej 133A, 2830 Virum), captured 2026-09-26, with a price cut added.
ADDRESS_JSON = {
    "addressID": "0a3f50a6-5b14-32b8-e044-0003ba298018",
    "roadName": "Grøndalvej", "houseNumber": "133A", "zipCode": 2830,
    "cases": [{
        "caseID": "5d0c7a11-2b3e-4f60-9a1d-3c4e5f607182", "status": "open",
        "priceCash": 8595000, "priceChangePercentage": -4.45, "daysOnMarket": 32,
        "timeOnMarket": {"current": {"days": 32}, "total": {"days": 40}},
        "realtor": {"name": "Estate Virum"},
    }],
    "registrations": [
        {"amount": 3150000, "date": "2010-03-16", "type": "normal"},
        {"amount": 6450000, "date": "2021-09-08", "type": "normal"},
    ],
}
SALES = [{"date": "2021-09-08", "price_dkk": 6450000.0, "type": "normal"},
         {"date": "2010-03-16", "price_dkk": 3150000.0, "type": "normal"}]


def test_parse_an_open_listing():
    assert parse_address(ADDRESS_JSON, today="2026-09-26") == {
        "price_dkk": 8595000.0,
        "listed_price_dkk": 8995000.0,       # 8595000 / 0.9555, to the nearest 5,000
        "listed_date": "2026-08-25",         # 32 days before the sweep
        "days_on_market": 32,
        "total_days_on_market": 40,
        "realtor": "Estate Virum",
        "sales": SALES,                      # newest first
        "next_open_house": None,
    }


def test_no_cut_means_the_listing_price_is_the_price():
    data = {**ADDRESS_JSON, "cases": [{**ADDRESS_JSON["cases"][0],
                                       "priceCash": 8597500, "priceChangePercentage": 0}]}
    assert parse_address(data, today="2026-09-26")["listed_price_dkk"] == 8597500.0


def test_an_address_not_for_sale_still_has_its_sales():
    data = {**ADDRESS_JSON, "cases": [{**ADDRESS_JSON["cases"][0], "status": "sold"}]}
    got = parse_address(data, today="2026-09-26")
    assert got["price_dkk"] is None and got["listed_price_dkk"] is None
    assert got["listed_date"] is None and got["realtor"] is None
    assert got["sales"] == SALES


def test_client_gets_the_address_endpoint():
    urls = []

    def opener(url):
        urls.append(url)
        return json.dumps(ADDRESS_JSON).encode()

    assert BoligsidenClient(opener=opener).address("abc") == ADDRESS_JSON
    assert urls == [f"{BOLIGSIDEN_API}/addresses/abc"]


def test_client_returns_none_on_failure():
    def boom(url):
        raise OSError("cloudflare 403")

    assert BoligsidenClient(opener=boom).address("abc") is None
    assert BoligsidenClient(opener=lambda url: b"<html>Just a moment...</html>").address("abc") is None
    assert BoligsidenClient(opener=lambda url: b"[]").address("abc") is None


def test_parse_keeps_the_next_open_house_of_the_open_case():
    nxt = {"date": "2026-10-04T13:30:00Z", "duration": 20, "signUp": True}
    data = {"cases": [{"status": "sold", "priceCash": 1, "nextOpenHouse": {"date": "x"}},
                      {"status": "open", "priceCash": 9_995_000, "nextOpenHouse": nxt}]}
    assert parse_address(data, today="2026-09-30")["next_open_house"] == nxt
    assert parse_address({"cases": [{"status": "open", "priceCash": 1}]},
                         today="2026-09-30")["next_open_house"] is None
    assert parse_address({"registrations": []}, today="2026-09-30")["next_open_house"] is None
