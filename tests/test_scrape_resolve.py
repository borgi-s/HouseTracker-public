# tests/test_scrape_resolve.py
import json

from housetracker.scrape.autoadapter import resolve
from housetracker.scrape.parse import MediaRef, ScrapeResult
from housetracker.store import HouseStore

# Generic-blind page: og:title gives an address, nothing else the gate needs.
BLIND = '<meta property="og:title" content="Nyvej 2">'

# The same page, but with classed elements a synthesized config can target.
RICH = """<html><body>
  <h1 class="a">Nyvej 2, 2800</h1><span class="p">3.200.000 kr.</span>
  <div class="d">Lovely.</div><img class="fp" src="/p.png">
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
    def __init__(self, config):
        self.config, self.calls = config, 0

    def synthesize(self, url, html, result):
        self.calls += 1
        return self.config


def _store(tmp_path):
    return HouseStore(tmp_path / "data" / "ht.db")


def test_generic_passes_gate_skips_synth(tmp_path):
    # A page the generic parser fully handles: JSON-LD with everything + 3 images + pdf.
    html = ('<script type="application/ld+json">' + json.dumps({
        "@type": "RealEstateListing",
        "address": {"streetAddress": "Helvej 9"}, "offers": {"price": "2.000.000"},
        "description": "d", "image": ["/1.jpg", "/2.jpg", "/3.jpg", "/plantegning.png"],
    }) + '</script><a href="/salgsopstilling.pdf">salgsopstilling</a>')
    synth = FakeSynth(GOOD_CFG)
    r = resolve("https://known.dk/x", html, _store(tmp_path), synth, now="2026-09-14")
    assert synth.calls == 0                       # generic sufficed
    assert r.house["source_adapter"] == "generic"


def test_gate_failure_synthesizes_and_confirms(tmp_path):
    s = _store(tmp_path)
    synth = FakeSynth(GOOD_CFG)
    seen = {}

    def confirm(result, missing):
        seen["missing"] = missing
        return True

    r = resolve("https://ny-chain.dk/b/1", RICH, s, synth, now="2026-09-14",
                confirm=confirm)
    assert synth.calls == 1
    assert r.house["source_adapter"] == "llm"
    assert r.house["address"].startswith("Nyvej 2")
    cfg = s.get_adapter_config("ny-chain.dk")
    assert cfg is not None and cfg.confirmed is True
    assert cfg.source == "llm"


def test_confirmed_config_is_reused_without_synth(tmp_path):
    s = _store(tmp_path)
    s.upsert_adapter_config("ny-chain.dk", json.dumps(GOOD_CFG), 0.9, "llm",
                            confirmed=True, now="2026-09-14")
    synth = FakeSynth(GOOD_CFG)
    r = resolve("https://ny-chain.dk/b/2", RICH, s, synth, now="2026-09-20")
    assert synth.calls == 0                       # reused the saved config
    assert r.house["source_adapter"] == "llm"


def test_decline_persists_unconfirmed_and_reescalates(tmp_path):
    s = _store(tmp_path)
    synth = FakeSynth(GOOD_CFG)
    r = resolve("https://ny-chain.dk/b/1", RICH, s, synth, now="2026-09-14",
                confirm=lambda result, missing: False)
    assert synth.calls == 1
    cfg = s.get_adapter_config("ny-chain.dk")
    assert cfg is not None and cfg.confirmed is False    # saved but not trusted
    # Next scrape does NOT blindly reuse an unconfirmed config -> synth runs again.
    resolve("https://ny-chain.dk/b/2", RICH, s, synth, now="2026-09-15",
            confirm=lambda result, missing: False)
    assert synth.calls == 2


def test_no_synth_still_returns_addable_best_effort(tmp_path):
    r = resolve("https://ny-chain.dk/b/1", BLIND, _store(tmp_path), None,
                now="2026-09-14")
    assert r.house.get("address") == "Nyvej 2"    # M2 guarantee intact


def test_synth_error_falls_back_to_best_effort(tmp_path):
    s = _store(tmp_path)

    class Boom:
        def synthesize(self, url, html, result):
            raise RuntimeError("session down")

    r = resolve("https://ny-chain.dk/b/1", RICH, s, Boom(), now="2026-09-14")
    assert r.house["source_adapter"] == "generic"       # fell back, still addable
    assert s.get_adapter_config("ny-chain.dk") is None   # nothing persisted on failure
