# tests/test_lifecycle_flow.py
import logging

from housetracker.lifecycle.lifecycle import run_lifecycle
from housetracker.store import HouseStore

AID = "0a3f50a4-9c47-32b8-e044-0003ba298018"
LISTED = (200, "https://x.dk/1", "<html>Til salg</html>")
AGENCY_PAGE = ('<html><head><script type="application/ld+json">'
               '{"@type": "RealEstateListing", "offers": {"price": "4.900.000"}}'
               '</script></head><body>Til salg</body></html>')


def payload(price=5_000_000, pct=0, days=8, zip_code=2800, open_case=True, sales=()):
    """A Boligsiden /addresses answer (shape per tests/test_lifecycle_boligsiden.py)."""
    return {"zipCode": zip_code,
            "cases": [{"status": "open" if open_case else "sold", "priceCash": price,
                       "priceChangePercentage": pct, "daysOnMarket": days,
                       "timeOnMarket": {"total": {"days": days}},
                       "realtor": {"name": "EDC Lyngby"}}],
            "registrations": [{"date": d, "amount": a, "type": "normal"} for d, a in sales]}


class FakeProber:
    def __init__(self, result):
        self.result = result

    def probe(self, url):
        return self.result


class FakeGeocoder:
    def __init__(self):
        self.calls = []

    def geocode(self, query):
        self.calls.append(query)
        return {"lat": 55.8, "lon": 12.5, "address_id": AID}


class FakeBoligsiden:
    def __init__(self, result):
        self.result, self.calls = result, []

    def address(self, address_id):
        self.calls.append(address_id)
        return self.result


def _store(tmp_path):
    return HouseStore(tmp_path / "data" / "ht.db")


def _house(s, price=5_000_000, **extra):
    return s.add_house({"address": "Nyvej 2", "postal_code": "2800",
                        "listing_url": "https://x.dk/1", "price_dkk": price, **extra},
                       now="2026-09-18")


def sweep(s, prober=None, bs=None, geo=None, now="2026-09-26"):
    return run_lifecycle(s, prober, bs, now=now, geocoder=geo or FakeGeocoder())


def counts(**over):
    return {"checked": 0, "marked_sold": 0, "priced": 0, "repriced": 0, "skipped": 0,
            "open_new": 0, **over}


# ---- asking price ------------------------------------------------------------------

def test_an_unchanged_price_only_stamps_the_check(tmp_path):
    s = _store(tmp_path)
    h = _house(s)
    assert sweep(s, FakeProber(LISTED), FakeBoligsiden(payload())) == counts(checked=1)
    assert len(s.price_events(h.id)) == 1
    got = s.get_listing(h.id)
    assert got["address_id"] == AID and got["checked_at"] == "2026-09-26"
    assert got["listed_price_dkk"] == 5_000_000.0 and got["listed_date"] == "2026-09-18"
    assert got["days_on_market"] == 8 and got["realtor"] == "EDC Lyngby"


def test_a_boligsiden_drop_is_logged_and_becomes_current(tmp_path):
    s = _store(tmp_path)
    h = _house(s)
    summary = sweep(s, None, FakeBoligsiden(payload(4_800_000, pct=-4.0)))
    assert summary == counts(repriced=1)
    assert s.get_house(h.id).price_dkk == 4_800_000.0
    assert s.price_events(h.id)[-1] == {"price_dkk": 4_800_000.0, "at": "2026-09-26",
                                        "source": "boligsiden"}
    assert s.original_price(h.id) == 5_000_000.0     # 4.8M / 0.96


def test_the_address_id_is_resolved_once(tmp_path):
    s = _store(tmp_path)
    _house(s)
    geo, bs = FakeGeocoder(), FakeBoligsiden(payload())
    sweep(s, None, bs, geo)
    sweep(s, None, bs, geo, now="2026-09-27")
    assert geo.calls == ["Nyvej 2 2800"]
    assert bs.calls == [AID, AID]


def test_the_agency_page_is_the_fallback(tmp_path):
    s = _store(tmp_path)
    h = _house(s)
    summary = sweep(s, FakeProber((200, "https://x.dk/1", AGENCY_PAGE)), FakeBoligsiden(None))
    assert summary == counts(checked=1, repriced=1)
    assert s.price_events(h.id)[-1]["source"] == "agency"
    assert s.get_house(h.id).price_dkk == 4_900_000.0


def test_no_price_is_read_off_a_sold_page(tmp_path):
    s = _store(tmp_path)
    h = _house(s)
    sweep(s, FakeProber((200, "https://x.dk/1/solgt", AGENCY_PAGE)), FakeBoligsiden(None))
    assert s.get_house(h.id).status == "sold"
    assert len(s.price_events(h.id)) == 1


def test_a_big_jump_is_skipped_and_logged(tmp_path, caplog):
    s = _store(tmp_path)
    h = _house(s)
    with caplog.at_level(logging.WARNING):
        summary = sweep(s, None, FakeBoligsiden(payload(2_000_000)))
    assert summary == counts(skipped=1)
    assert s.get_house(h.id).price_dkk == 5_000_000.0
    got = s.get_listing(h.id)
    assert got["checked_at"] is None and got["listed_price_dkk"] is None   # misread not kept
    assert "price jump skipped" in caplog.text


def test_hand_correction_survives_an_unchanged_online_price(tmp_path):
    s = _store(tmp_path)
    h = _house(s)
    s.update_house(h.id, {"price_dkk": 5_050_000}, now="2026-09-20")
    assert sweep(s, None, FakeBoligsiden(payload(5_000_000))) == counts()
    assert s.get_house(h.id).price_dkk == 5_050_000.0
    assert len(s.price_events(h.id)) == 1


def test_namesake_in_another_town_is_ignored(tmp_path):
    s = _store(tmp_path)
    h = _house(s)
    assert sweep(s, None, FakeBoligsiden(payload(4_800_000, zip_code=8000))) == counts()
    assert s.get_house(h.id).price_dkk == 5_000_000.0
    got = s.get_listing(h.id)
    assert got["listed_price_dkk"] is None and got["checked_at"] is None


def test_unpriced_house_takes_the_first_reading(tmp_path):
    s = _store(tmp_path)
    h = _house(s, price=None)
    assert sweep(s, None, FakeBoligsiden(payload())) == counts(repriced=1)
    assert s.get_house(h.id).price_dkk == 5_000_000.0
    assert [e["source"] for e in s.price_events(h.id)] == ["boligsiden"]


def test_a_zero_priced_house_takes_the_first_reading(tmp_path):
    s = _store(tmp_path)
    h = _house(s, price=0)
    assert sweep(s, None, FakeBoligsiden(payload())) == counts(repriced=1)
    assert s.get_house(h.id).price_dkk == 5_000_000.0


def test_boligsiden_error_falls_back_quietly(tmp_path):
    s = _store(tmp_path)
    h = _house(s)

    class Boom:
        def address(self, address_id):
            raise RuntimeError("boligsiden down")

    assert sweep(s, FakeProber(LISTED), Boom()) == counts(checked=1)   # no price on page
    assert s.get_house(h.id).price_dkk == 5_000_000.0
    assert s.get_listing(h.id)["checked_at"] is None


def test_rejected_houses_are_still_tracked(tmp_path):
    s = _store(tmp_path)
    h = _house(s)
    s.set_status(h.id, "rejected", now="2026-09-20")
    assert sweep(s, None, FakeBoligsiden(payload(4_800_000)))["repriced"] == 1


def test_sold_houses_are_not_price_tracked(tmp_path):
    s = _store(tmp_path)
    h = _house(s)
    s.mark_sold(h.id, now="2026-09-20")
    sweep(s, None, FakeBoligsiden(payload(4_800_000)))
    assert len(s.price_events(h.id)) == 1


def test_a_malformed_boligsiden_answer_is_ignored(tmp_path):
    s = _store(tmp_path)
    h = _house(s)
    bs = FakeBoligsiden({"zipCode": 2800, "cases": [{"status": "open", "priceCash": "n/a"}]})
    assert sweep(s, None, bs) == counts()
    assert s.get_house(h.id).price_dkk == 5_000_000.0


# ---- sold-detection and realized price ---------------------------------------------

def test_gone_listing_marked_sold_then_priced_from_boligsiden(tmp_path):
    s = _store(tmp_path)
    h = _house(s)
    bs = FakeBoligsiden(payload(open_case=False,
                                sales=[("2026-09-24", 5_100_000), ("2019-05-20", 4_195_000)]))
    summary = sweep(s, FakeProber((404, "https://x.dk/1", "")), bs)
    assert summary == counts(checked=1, marked_sold=1, priced=1)
    g = s.get_house(h.id)
    assert g.status == "sold" and g.sold_detected_at == "2026-09-26"
    assert g.sold_price_dkk == 5_100_000.0 and g.sold_date == "2026-09-24"
    assert len(s.get_listing(h.id)["sales"]) == 2


def test_a_sold_house_waits_for_tinglysning(tmp_path):
    s = _store(tmp_path)
    h = _house(s)
    s.mark_sold(h.id, now="2026-09-20")
    summary = sweep(s, None, FakeBoligsiden(payload(open_case=False,
                                                    sales=[("2019-05-20", 4_195_000)])))
    assert summary == counts()                       # the 2019 sale is not this one
    assert s.get_house(h.id).sold_price_dkk is None


def test_prober_none_skips_sold_detection(tmp_path):
    s = _store(tmp_path)
    h = _house(s)
    assert sweep(s, None, None, geo=FakeGeocoder()) == counts()
    assert s.get_house(h.id).status == "not_visited"


def test_no_listing_url_not_marked_sold(tmp_path):
    s = _store(tmp_path)
    s.add_house({"address": "Ingenvej 1"}, now="2026-09-18")      # no listing_url
    h = s.list_houses()[-1]
    assert sweep(s, FakeProber((404, "", "")), None) == counts()
    assert s.get_house(h.id).status == "not_visited"


# ---- Discord pings -----------------------------------------------------------------

class Pings:
    def __init__(self, fail=False):
        self.sent, self.fail = [], fail

    def __call__(self, house, old, new, original):
        if self.fail:
            raise OSError("discord down")
        self.sent.append((house.id, old, new, original))


def ping_sweep(s, bs, pings, now="2026-09-26"):
    return run_lifecycle(s, None, bs, now=now, geocoder=FakeGeocoder(), notify=pings)


def test_a_drop_pings_once(tmp_path):
    s = _store(tmp_path)
    h = _house(s)
    pings = Pings()
    ping_sweep(s, FakeBoligsiden(payload(4_800_000, pct=-4.0)), pings)
    ping_sweep(s, FakeBoligsiden(payload(4_800_000, pct=-4.0)), pings, now="2026-09-27")
    assert pings.sent == [(h.id, 5_000_000.0, 4_800_000.0, 5_000_000.0)]


def test_rises_and_first_readings_do_not_ping(tmp_path):
    s = _store(tmp_path)
    h = _house(s)                                   # priced at 5.0M
    u = _house(s, price=None, address="Andenvej 9",  # no price yet
               listing_url="https://x.dk/2")
    pings = Pings()
    ping_sweep(s, FakeBoligsiden(payload(5_200_000, pct=4.0)), pings)
    assert pings.sent == []
    assert s.get_house(h.id).price_dkk == 5_200_000.0
    assert s.get_house(u.id).price_dkk == 5_200_000.0


def test_a_failing_ping_never_loses_the_price(tmp_path, caplog):
    s = _store(tmp_path)
    h = _house(s)
    with caplog.at_level(logging.WARNING):
        summary = ping_sweep(s, FakeBoligsiden(payload(4_800_000, pct=-4.0)), Pings(fail=True))
    assert summary["repriced"] == 1
    assert s.get_house(h.id).price_dkk == 4_800_000.0
    assert s.get_listing(h.id)["checked_at"] == "2026-09-26"
    assert "ping failed" in caplog.text


def test_secret_is_not_logged_on_ping_failure(tmp_path, caplog):
    s = _store(tmp_path)
    h = _house(s)

    def bad_notify(house, old, new, original):
        raise ValueError("unknown url type: 'discord.com/api/webhooks/1/SECRET'")

    with caplog.at_level(logging.WARNING):
        ping_sweep(s, FakeBoligsiden(payload(4_800_000, pct=-4.0)), bad_notify)
    assert "SECRET" not in caplog.text
    assert "ping failed" in caplog.text


def test_a_hand_correction_unsticks_a_misread_price(tmp_path):
    s = _store(tmp_path)
    h = _house(s, price=50_000_000)
    s.update_house(h.id, {"price_dkk": 5_000_000}, now="2026-09-20")
    summary = sweep(s, FakeProber(LISTED), FakeBoligsiden(payload(5_000_000)))
    assert summary == counts(checked=1, repriced=1)
    assert s.get_house(h.id).price_dkk == 5_000_000.0
    events = s.price_events(h.id)
    assert events[-1]["source"] == "boligsiden"
    assert s.get_listing(h.id)["checked_at"] == "2026-09-26"


def test_realigning_after_a_hand_correction_does_not_ping(tmp_path):
    s = _store(tmp_path)
    h = _house(s, price=50_000_000)
    s.update_house(h.id, {"price_dkk": 5_000_000}, now="2026-09-20")
    pings = Pings()
    ping_sweep(s, FakeBoligsiden(payload(5_000_000)), pings)
    assert pings.sent == []
