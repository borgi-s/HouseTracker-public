from housetracker.scrape.autoadapter import GATE_MIN_PHOTOS, gate_check, host_key
from housetracker.scrape.parse import MediaRef, ScrapeResult


def _full():
    house = {"address": "Vej 1", "price_dkk": 3_000_000.0, "description": "Nice"}
    media = [MediaRef("floorplan", "f.png"), MediaRef("pdf", "s.pdf"),
             MediaRef("photo", "1.jpg"), MediaRef("photo", "2.jpg"),
             MediaRef("photo", "3.jpg")]
    return ScrapeResult(house=house, media=media)


def test_full_result_passes():
    ok, missing = gate_check(_full())
    assert ok is True
    assert missing == []


def test_each_missing_item_reported():
    r = _full()
    r.house.pop("price_dkk")
    ok, missing = gate_check(r)
    assert ok is False
    assert "price" in missing


def test_too_few_photos_fails():
    r = _full()
    r.media = [m for m in r.media if m.kind != "photo"][:1] + [MediaRef("photo", "1.jpg")]
    ok, missing = gate_check(r)
    assert ok is False
    assert any("photo" in m for m in missing)


def test_missing_floorplan_pdf_description_address():
    r = ScrapeResult(house={}, media=[])
    ok, missing = gate_check(r)
    assert ok is False
    for item in ("address", "price", "floorplan", "pdf", "description"):
        assert item in missing


def test_host_key_strips_www():
    assert host_key("https://www.Nybolig.dk/bolig/1") == "nybolig.dk"
    assert host_key("https://mier.home.dk/x") == "mier.home.dk"
    assert GATE_MIN_PHOTOS == 3
