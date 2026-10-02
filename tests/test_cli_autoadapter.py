# tests/test_cli_autoadapter.py
import io

from housetracker.cli import main

# Generic-blind: og:title yields an address; no price/desc/floorplan/pdf/3-photos.
BLIND = '<meta property="og:title" content="Nyvej 2, 2800">'

RICH = """<html><body>
  <h1 class="a">Nyvej 2, 2800</h1><span class="p">3.200.000 kr.</span>
  <div class="d">Lovely villa.</div><img class="fp" src="/p.png">
  <a class="pdf" href="/prospekt-x">prospekt</a>
  <img class="ph" src="/1.jpg"><img class="ph" src="/2.jpg"><img class="ph" src="/3.jpg">
</body></html>"""

GOOD_CFG = {
    "fields": {"address": {"selector": "h1.a", "attr": "text"},
               "price_dkk": {"selector": ".p", "attr": "text"},
               "description": {"selector": ".d", "attr": "text"}},
    "media": {"floorplan": {"selector": "img.fp", "attr": "src"},
              "pdf": {"selector": "a.pdf", "attr": "href"},
              "photo": {"selector": "img.ph", "attr": "src"}},
}


class FakeSynth:
    def __init__(self, *a, **k):
        pass

    def synthesize(self, url, html, result):
        return GOOD_CFG


def run(db, *args):
    buf = io.StringIO()
    return main(["--db", str(db), *args], buf), buf.getvalue()


def test_scrape_new_chain_synthesizes_and_persists(tmp_path, monkeypatch):
    monkeypatch.setattr("housetracker.cli.fetch_html", lambda url, a, b: RICH)
    monkeypatch.setattr("housetracker.cli.InboxSynthesizer", FakeSynth)
    monkeypatch.setattr("housetracker.scrape.download._default_opener",
                        lambda url: b"BYTES")
    db = tmp_path / "data" / "ht.db"
    code, out = run(db, "scrape", "--url", "https://ny-chain.dk/b/1",
                    "--no-browser", "--yes")
    assert code == 0
    from housetracker.store import HouseStore
    cfg = HouseStore(db).get_adapter_config("ny-chain.dk")
    assert cfg is not None and cfg.confirmed is True


def test_scrape_no_llm_still_adds_best_effort(tmp_path, monkeypatch):
    monkeypatch.setattr("housetracker.cli.fetch_html", lambda url, a, b: BLIND)
    monkeypatch.setattr("housetracker.scrape.download._default_opener",
                        lambda url: b"BYTES")
    db = tmp_path / "data" / "ht.db"
    code, out = run(db, "scrape", "--url", "https://ny-chain.dk/b/9",
                    "--no-browser", "--no-llm")
    assert code == 0                      # addable despite failing the gate
    from housetracker.store import HouseStore
    assert HouseStore(db).get_adapter_config("ny-chain.dk") is None   # no synth ran
