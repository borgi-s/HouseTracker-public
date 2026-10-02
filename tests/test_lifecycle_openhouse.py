"""The sweep's open-house step (spec D1, D2, D4, D9 and §4 sync rules)."""
import json
import logging

from housetracker.lifecycle.lifecycle import run_lifecycle
from housetracker.store import HouseStore

AT = "2026-10-01T00:00:00Z"
URL = "https://x.dk/1"
SUN = ("2026-10-04T15:30:00+02:00", "2026-10-04T15:50:00+02:00")      # 13:30Z
NEXT_SUN = ("2026-10-11T10:00:00+02:00", "2026-10-11T10:30:00+02:00")  # 08:00Z
DOWN = (None, URL, "")                                                 # probe failed: unknown


def page(*slots):
    """An agency page on an unknown host (so the JSON-LD Event extractor reads it)."""
    events = [{"@type": "Event", "name": "Åbent hus: Nyvej 2", "startDate": a, "endDate": b}
              for a, b in slots]
    return (200, URL, f'<script type="application/ld+json">{json.dumps(events)}</script>'
                      '<p>Til salg</p>')


def boligsiden(next_open=None):
    case = {"status": "open", "priceCash": 5_000_000, "priceChangePercentage": 0, "daysOnMarket": 8}
    if next_open:
        case["nextOpenHouse"] = next_open
    return {"zipCode": 2800, "cases": [case], "registrations": []}


class Prober:
    def __init__(self, result):
        self.result = result

    def probe(self, url):
        return self.result


class Geo:
    def geocode(self, query):
        return {"lat": 55.8, "lon": 12.5, "address_id": "aid"}


class Bolig:
    def __init__(self, data):
        self.data = data

    def address(self, address_id):
        return self.data


def _house(tmp_path, status="shortlist", **extra):
    s = HouseStore(tmp_path / "data" / "ht.db")
    h = s.add_house({"address": "Nyvej 2", "postal_code": "2800", "listing_url": URL,
                     "price_dkk": 5_000_000, **extra}, now="2026-09-18")
    if status != "not_visited":
        s.set_status(h.id, status, now="2026-09-20")
    return s, h.id


def sweep(s, probe, data, pings=None, at=AT, notify_open=None):
    if pings is not None:
        notify_open = lambda h, new: pings.append((h.id, [x["starts_at"] for x in new]))
    return run_lifecycle(s, Prober(probe), Bolig(data), now=at[:10], geocoder=Geo(),
                         notify_open=notify_open, at=at)


def rows(s, hid):
    return [(r["starts_at"], r["cancelled"]) for r in s.list_open_houses(hid)]


def test_a_new_slot_on_the_realtor_page_pings_a_shortlisted_house_once(tmp_path):
    s, hid = _house(tmp_path)
    pings = []
    summary = sweep(s, page(SUN), boligsiden(), pings)
    assert summary["open_new"] == 1
    assert pings == [(hid, ["2026-10-04T13:30:00Z"])]
    assert rows(s, hid) == [("2026-10-04T13:30:00Z", False)]
    assert sweep(s, page(SUN), boligsiden(), pings, at="2026-10-02T00:00:00Z")["open_new"] == 0
    assert len(pings) == 1


def test_offer_pings_and_other_statuses_do_not(tmp_path):
    for status, pinged in (("offer", True), ("not_visited", False), ("visited", False),
                           ("rejected", False)):
        s, hid = _house(tmp_path / status, status)
        pings = []
        sweep(s, page(SUN), boligsiden(), pings)
        assert bool(pings) is pinged, status
        assert rows(s, hid) == [("2026-10-04T13:30:00Z", False)]


def test_one_message_per_house_with_all_its_new_slots(tmp_path):
    s, hid = _house(tmp_path)
    pings = []
    sweep(s, page(SUN), boligsiden(), pings)
    sweep(s, page(SUN, NEXT_SUN), boligsiden(), pings, at="2026-10-02T00:00:00Z")
    assert pings == [(hid, ["2026-10-04T13:30:00Z"]), (hid, ["2026-10-11T08:00:00Z"])]


def test_realtor_shows_none_so_boligsiden_is_used_and_the_gap_is_logged(tmp_path, caplog):
    s, hid = _house(tmp_path)
    nxt = {"date": "2026-10-04T13:30:00Z", "duration": 20, "signUp": True,
           "signUpUrl": "https://agent.dk/tilmeld"}
    with caplog.at_level(logging.WARNING):     # nothing configures logging: only WARNING+ reach the journal
        sweep(s, page(), boligsiden(nxt), [])
    assert s.list_open_houses(hid) == [{"starts_at": "2026-10-04T13:30:00Z",
                                        "ends_at": "2026-10-04T13:50:00Z", "signup": True,
                                        "signup_url": "https://agent.dk/tilmeld", "cancelled": False}]
    assert f"open houses differ for {hid}: realtor=0 boligsiden=1" in caplog.text


def test_boligsiden_time_is_danish_for_realequity_houses(tmp_path):
    s, hid = _house(tmp_path, source_adapter="fiskerliljengren")
    sweep(s, DOWN, boligsiden({"date": "2026-10-04T10:10:00Z", "duration": 20, "signUp": False}), [])
    assert rows(s, hid) == [("2026-10-04T08:10:00Z", False)]


def test_a_moved_slot_is_new_and_the_old_one_cancelled(tmp_path):
    s, hid = _house(tmp_path)
    pings = []
    sweep(s, page(SUN), boligsiden(), pings)
    sweep(s, page(NEXT_SUN), boligsiden(), pings, at="2026-10-02T00:00:00Z")
    assert pings[-1] == (hid, ["2026-10-11T08:00:00Z"])
    assert rows(s, hid) == [("2026-10-04T13:30:00Z", True), ("2026-10-11T08:00:00Z", False)]


def test_both_sources_show_none_cancels(tmp_path):
    s, hid = _house(tmp_path)
    sweep(s, page(SUN), boligsiden(), [])
    sweep(s, page(), boligsiden(), [], at="2026-10-02T00:00:00Z")
    assert rows(s, hid) == [("2026-10-04T13:30:00Z", True)]


def test_nothing_read_changes_nothing(tmp_path):
    s, hid = _house(tmp_path)
    sweep(s, page(SUN), boligsiden(), [])
    summary = sweep(s, DOWN, None, [], at="2026-10-02T00:00:00Z")
    assert summary["open_new"] == 0
    assert rows(s, hid) == [("2026-10-04T13:30:00Z", False)]


def test_an_empty_realtor_read_without_boligsiden_does_not_cancel(tmp_path):
    s, hid = _house(tmp_path)
    sweep(s, page(SUN), boligsiden(), [])
    sweep(s, page(), None, [], at="2026-10-02T00:00:00Z")
    assert rows(s, hid) == [("2026-10-04T13:30:00Z", False)]


def test_a_boligsiden_only_read_never_cancels_later_slots(tmp_path):
    s, hid = _house(tmp_path)
    sweep(s, page(SUN, NEXT_SUN), boligsiden(), [])
    nxt = {"date": "2026-10-04T13:30:00Z", "duration": 20, "signUp": False}
    sweep(s, DOWN, boligsiden(nxt), [], at="2026-10-02T00:00:00Z")
    assert rows(s, hid) == [("2026-10-04T13:30:00Z", False), ("2026-10-11T08:00:00Z", False)]


def test_a_failing_ping_never_loses_the_slot(tmp_path, caplog):
    s, hid = _house(tmp_path)

    def boom(house, new):
        raise OSError("discord down")
    with caplog.at_level(logging.WARNING):
        summary = sweep(s, page(SUN), boligsiden(), notify_open=boom)
    assert summary["open_new"] == 1 and len(s.list_open_houses(hid)) == 1
    assert f"open-house ping failed for {hid}: OSError" in caplog.text


def test_sold_houses_are_left_alone(tmp_path):
    s, hid = _house(tmp_path, status="sold")
    s.set_realized_price(hid, 5_000_000, "2026-09-25", now="2026-09-25")
    sweep(s, page(SUN), boligsiden(), [])
    assert s.list_open_houses(hid) == []


def test_a_page_showing_only_a_past_slot_does_not_cancel_the_next_one(tmp_path):
    # Review fix: a stale page (yesterday's slot only) is not a complete read.
    s, hid = _house(tmp_path)
    nxt = {"date": "2026-10-11T08:00:00Z", "duration": 30, "signUp": False}
    sweep(s, DOWN, boligsiden(nxt), [])
    sweep(s, page(SUN), boligsiden(nxt), [], at="2026-10-05T00:00:00Z")
    assert rows(s, hid) == [("2026-10-11T08:00:00Z", False)]


def test_a_stale_boligsiden_slot_does_not_block_a_cancellation(tmp_path):
    s, hid = _house(tmp_path)
    sweep(s, page(NEXT_SUN), boligsiden(), [])
    stale = {"date": "2026-10-04T13:30:00Z", "duration": 20, "signUp": False}
    sweep(s, page(), boligsiden(stale), [], at="2026-10-05T00:00:00Z")
    assert rows(s, hid) == [("2026-10-11T08:00:00Z", True)]
