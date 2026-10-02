from housetracker.scrape.autoadapter import apply_config

HTML = """<html><body>
  <h1 class="addr">Testvej 5, 2800 Kongens Lyngby</h1>
  <span class="price">4.995.000 kr.</span>
  <div class="desc">Charming villa near the forest.</div>
  <img class="fp" src="/media/plan.png">
  <a class="doc" href="/files/prospekt-123">Hent prospekt</a>
  <div class="gallery">
    <img class="photo" src="/img/1.jpg">
    <img class="photo" src="/img/2.jpg">
    <img class="photo" src="https://cdn.example.dk/3.jpg">
  </div>
</body></html>"""

CFG = {
    "fields": {
        "address": {"selector": "h1.addr", "attr": "text"},
        "price_dkk": {"selector": ".price", "attr": "text"},
        "description": {"selector": ".desc", "attr": "text"},
    },
    "media": {
        "floorplan": {"selector": "img.fp", "attr": "src"},
        "pdf": {"selector": "a.doc", "attr": "href"},
        "photo": {"selector": ".gallery img.photo", "attr": "src"},
    },
}


def test_apply_extracts_fields_and_media():
    r = apply_config(HTML, "https://ny-chain.dk/bolig/9", CFG)
    assert r.house["address"] == "Testvej 5, 2800 Kongens Lyngby"
    assert r.house["price_dkk"] == 4995000.0            # Danish price normalized
    assert r.house["description"].startswith("Charming")
    assert r.house["source_adapter"] == "llm"
    assert r.house["maegler_chain"] == "ny-chain.dk"
    kinds = sorted(m.kind for m in r.media)
    assert kinds == ["floorplan", "pdf", "photo", "photo", "photo"]
    # relative srcs became absolute against the listing URL
    assert any(m.url == "https://ny-chain.dk/media/plan.png"
               for m in r.media if m.kind == "floorplan")
    assert r.house["scrape_completeness"] > 0


def test_missing_selector_is_skipped_not_fatal():
    cfg = {"fields": {"address": {"selector": "h1.addr", "attr": "text"},
                      "size_m2": {"selector": ".nope", "attr": "text"}}}
    r = apply_config(HTML, "https://ny-chain.dk/x", cfg)
    assert r.house["address"].startswith("Testvej")
    assert "size_m2" not in r.house
