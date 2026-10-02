import io
from pathlib import Path

from housetracker.cli import main

FIXTURE = '''<html><head>
<script type="application/ld+json">
{"@type":"RealEstateListing","address":{"streetAddress":"Testvej 5","postalCode":"2800"},
 "offers":{"price":"3.000.000"},"image":["https://cdn/x/1.jpg"]}
</script></head><body>
<a href="https://cdn/x/salgsopstilling.pdf">salgsopstilling</a></body></html>'''


def run(db, *args):
    buf = io.StringIO()
    code = main(["--db", str(db), *args], buf)
    return code, buf.getvalue()


def test_scrape_end_to_end(tmp_path, monkeypatch):
    # No network / no browser: stub the fetch and the media opener.
    monkeypatch.setattr("housetracker.cli.fetch_html", lambda url, a, b: FIXTURE)
    monkeypatch.setattr("housetracker.scrape.download._default_opener", lambda url: b"BYTES")
    db = tmp_path / "data" / "ht.db"
    code, out = run(db, "scrape", "--url", "https://www.nybolig.dk/bolig/1",
                    "--no-browser", "--no-llm")
    assert code == 0
    assert out.startswith("testvej-5")
    assert "2 media" in out
    # House persisted and media on disk under the db's data dir.
    _, show = run(db, "show", "--house", "testvej-5")
    assert "Testvej 5" in show
    assert (tmp_path / "data" / "houses" / "testvej-5" / "pdf").is_dir()


def test_scrape_reports_when_no_address(tmp_path, monkeypatch):
    monkeypatch.setattr("housetracker.cli.fetch_html", lambda url, a, b: "<html></html>")
    db = tmp_path / "data" / "ht.db"
    code, out = run(db, "scrape", "--url", "https://x.dk/1", "--no-browser", "--no-llm")
    assert code == 1
    assert "address" in out.lower()


def test_rescrape_refreshes_the_listing_but_keeps_our_status_notes_scores_price_and_photos(tmp_path, monkeypatch):
    from housetracker.store import HouseStore
    monkeypatch.setattr("housetracker.scrape.download._default_opener", lambda url: b"\xff\xd8\xffJPEG")
    monkeypatch.setattr("housetracker.cli.fetch_html", lambda url, a, b: FIXTURE)
    db = tmp_path / "data" / "ht.db"
    run(db, "scrape", "--url", "https://www.x.dk/bolig/1", "--no-browser", "--no-llm")
    store = HouseStore(db)
    store.set_status("testvej-5", "visited", now="2026-09-26")
    store.add_note("testvej-5", None, "Fin have", now="2026-09-26")
    store.upsert_score("testvej-5", "alex", "light", 4.0, now="2026-09-26")
    mine = tmp_path / "data" / "houses" / "testvej-5" / "user_photos" / "mine.jpg"
    mine.parent.mkdir(parents=True)
    mine.write_bytes(b"\xff\xd8\xffMINE")
    store.add_media({"house_id": "testvej-5", "kind": "user_photo", "path": str(mine),
                     "source": "manual"}, now="2026-09-26")
    store.conn.close()

    fresh = (FIXTURE.replace('"3.000.000"', '"3.500.000"')
             .replace('"image":["https://cdn/x/1.jpg"]',
                      '"floorSize":{"value":120},"description":"Nyt tag",'
                      '"image":["https://cdn/x/1.jpg","https://cdn/x/2.jpg","https://cdn/x/3.jpg"]'))
    monkeypatch.setattr("housetracker.cli.fetch_html", lambda url, a, b: fresh)
    code, out = run(db, "rescrape", "--house", "testvej-5", "--no-browser")
    assert (code, out) == (0, "testvej-5\t4 media\n")

    store = HouseStore(db)
    h = store.get_house("testvej-5")
    assert (h.status, h.size_m2, h.description, h.price_dkk) == ("visited", 120.0, "Nyt tag", 3_000_000.0)
    assert [n["body"] for n in store.list_notes("testvej-5")] == ["Fin have"]
    assert store.get_scores("testvej-5") == {("alex", "light"): 4.0}
    media = store.list_media("testvej-5")
    assert sorted(m.kind for m in media) == ["pdf", "photo", "photo", "photo", "user_photo"]
    assert mine.exists()
    assert all(Path(m.path).exists() for m in media)


def test_rescrape_refuses_a_house_without_a_listing_link(tmp_path):
    db = tmp_path / "ht.db"
    run(db, "add-house", "--address", "Sol Vej 9")
    assert run(db, "rescrape", "--house", "sol-vej-9")[0] == 1
    assert run(db, "rescrape", "--house", "nope")[0] == 1


def test_scrape_records_the_open_houses(tmp_path, monkeypatch):
    page = FIXTURE.replace("</head>", '<script type="application/ld+json">[{"@type": "Event", '
                           '"name": "Åbent hus", "startDate": "2099-10-04T15:30:00+02:00", '
                           '"endDate": "2099-10-04T15:50:00+02:00"}]</script></head>')
    monkeypatch.setattr("housetracker.cli.fetch_html", lambda url, a, b: page)
    monkeypatch.setattr("housetracker.scrape.download._default_opener", lambda url: b"BYTES")
    db = tmp_path / "data" / "ht.db"
    code, _ = run(db, "scrape", "--url", "https://www.x.dk/bolig/1", "--no-browser", "--no-llm")
    assert code == 0
    from housetracker.store import HouseStore
    assert [r["starts_at"] for r in HouseStore(db).list_open_houses("testvej-5")] == [
        "2099-10-04T13:30:00Z"]
