from housetracker.scrape.parse import parse_listing, _parse_dkk

JSONLD_HTML = '''
<html><head>
<script type="application/ld+json">
{"@type": "RealEstateListing",
 "address": {"streetAddress": "Skovvej 3", "postalCode": "2800", "addressLocality": "Lyngby"},
 "offers": {"price": "4.995.000", "priceCurrency": "DKK"},
 "floorSize": {"value": 140},
 "geo": {"latitude": 55.77, "longitude": 12.50},
 "description": "Dejligt hus",
 "image": ["https://cdn.example.dk/1.jpg", "https://cdn.example.dk/plantegning.png"]}
</script>
</head><body>
<a href="/media/salgsopstilling.pdf">Hent salgsopstilling</a>
</body></html>
'''

OG_HTML = '''
<html><head>
<meta property="og:title" content="Solvej 9, 2000 Frederiksberg">
<meta property="og:description" content="Fin lejlighed">
<meta property="og:image" content="https://cdn.example.dk/cover.jpg">
<meta property="product:price:amount" content="3200000">
</head><body></body></html>
'''


def test_parse_jsonld_house_fields():
    r = parse_listing(JSONLD_HTML, "https://www.nybolig.dk/bolig/123")
    assert r.house["address"] == "Skovvej 3"
    assert r.house["postal_code"] == "2800"
    assert r.house["city"] == "Lyngby"
    assert r.house["price_dkk"] == 4995000.0
    assert r.house["size_m2"] == 140.0
    assert r.house["lat"] == 55.77
    assert r.house["source_adapter"] == "generic"
    assert r.house["listing_url"].endswith("/123")


def test_parse_jsonld_media_classified_and_absolutized():
    r = parse_listing(JSONLD_HTML, "https://www.nybolig.dk/bolig/123")
    got = sorted((m.kind, m.url.rsplit("/", 1)[-1]) for m in r.media)
    assert ("floorplan", "plantegning.png") in got
    assert ("photo", "1.jpg") in got
    assert ("pdf", "salgsopstilling.pdf") in got
    pdf = next(m for m in r.media if m.kind == "pdf")
    assert pdf.url == "https://www.nybolig.dk/media/salgsopstilling.pdf"  # relative -> absolute


def test_parse_opengraph_fallback():
    r = parse_listing(OG_HTML, "https://www.edc.dk/bolig/9")
    assert r.house["address"] == "Solvej 9, 2000 Frederiksberg"
    assert r.house["price_dkk"] == 3200000.0
    assert r.house["description"] == "Fin lejlighed"
    assert any(m.kind == "photo" and m.url.endswith("cover.jpg") for m in r.media)


def test_parse_price_danish_format():
    assert _parse_dkk("4.995.000 kr.") == 4995000.0
    assert _parse_dkk("1.250.000,50") == 1250000.5
    assert _parse_dkk(3200000) == 3200000.0
    assert _parse_dkk(None) is None
    assert _parse_dkk("kontakt mægler") is None


def test_parse_empty_html_is_safe():
    r = parse_listing("<html></html>", "https://x.dk/1")
    assert "address" not in r.house
    assert r.media == []
    assert r.house["source_adapter"] == "generic"


# EDC (real page, 2026-09): the type attribute is entity-escaped and the house sits
# inside Offer.itemOffered, with the floor plans under accommodationFloorPlan.
EDC_LD_HTML = '''
<meta property="og:title" content="Rækkehus til salg hos EDC Michael Tang">
<script type="application/ld&#x2B;json">
{"@type": "Offer", "price": "7995000",
 "image": {"@type": "ImageObject", "url": "https://billeder.edc.dk/a_Size300x200.jpg"},
 "itemOffered": {"@type": "House",
   "address": {"streetAddress": "Ahorntoften 36", "postalCode": "2800", "addressLocality": "Lyngby"},
   "geo": {"latitude": 55.7680, "longitude": 12.5031},
   "numberOfRooms": {"type": "QuantitativeValue", "value": 3.0},
   "accommodationFloorPlan": {"floorSize": {"value": 135.0},
     "layoutImage": [{"@type": "ImageObject", "url": "https://billeder.edc.dk/plan1.jpg"}]}}}
</script>
'''

# Estate (real page, 2026-09): RealEstateListing wraps the house in mainEntity, and the
# offer spells its price "Price".
ESTATE_LD_HTML = '''
<meta property="og:title" content="Til salg - Grøndalvej 133A, 2830 Virum - Estate Ejendomsmægler">
<script type="application/ld+json">
{"@type": "RealEstateListing", "datePosted": "2026-08-25",
 "mainEntity": {"@type": "House", "description": "Beliggenheden er som skræddersyet",
   "numberOfRooms": 4, "yearBuilt": 1951,
   "address": {"streetAddress": "Grøndalvej 133A", "addressLocality": "Virum", "postalCode": "2830"},
   "offers": {"@type": "Offer", "Price": "8595000", "priceCurrency": "DKK"},
   "floorSize": {"value": 150}}}
</script>
'''


def test_escaped_ld_json_type_and_offer_item_nesting_are_read():
    r = parse_listing(EDC_LD_HTML, "https://www.edc.dk/alle-boliger/x/51134985/")
    assert r.house["address"] == "Ahorntoften 36"           # not the page title
    assert r.house["postal_code"] == "2800"
    assert r.house["price_dkk"] == 7995000.0
    assert r.house["size_m2"] == 135.0
    assert r.house["rooms"] == 3.0
    assert r.house["lat"] == 55.7680
    assert [m.url for m in r.media if m.kind == "floorplan"] == ["https://billeder.edc.dk/plan1.jpg"]


def test_real_estate_listing_main_entity_is_read():
    r = parse_listing(ESTATE_LD_HTML, "https://www.estate.dk/raekkehus/2830/x")
    assert r.house["address"] == "Grøndalvej 133A"
    assert r.house["city"] == "Virum"
    assert r.house["price_dkk"] == 8595000.0
    assert r.house["size_m2"] == 150.0
    assert r.house["rooms"] == 4.0
    assert r.house["build_year"] == 1951
    assert r.house["description"].startswith("Beliggenheden")
