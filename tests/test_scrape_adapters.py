import json

from housetracker.scrape.adapters import detect_chain, parse_for


def test_detect_known_chains():
    assert detect_chain("https://www.nybolig.dk/bolig/123") == "nybolig"
    assert detect_chain("https://edc.dk/x") == "edc"
    assert detect_chain("https://home.dk/x") == "home"
    assert detect_chain("https://www.danbolig.dk/x") == "danbolig"


def test_detect_subdomain_and_unknown():
    assert detect_chain("https://mier.home.dk/x") == "home"
    assert detect_chain("https://www.some-maegler.dk/x") == "generic"


def test_parse_for_routes_and_tags_chain():
    html = '<meta property="og:title" content="Vej 1"><meta property="og:image" content="/c.jpg">'
    r = parse_for("https://www.nybolig.dk/bolig/1", html)
    assert r.house["maegler_chain"] == "nybolig"
    assert r.house["source_adapter"] == "nybolig"
    # none of the template's markup on the page: the generic fields and media survive
    assert r.house["address"] == "Vej 1"
    assert [(m.kind, m.url) for m in r.media] == [("photo", "https://www.nybolig.dk/c.jpg")]


def test_edc_takes_the_full_gallery_and_floor_plans_at_their_largest_size():
    # The JSON-LD carries one 300px image; the whole gallery is in the case JSON.
    src = lambda stem: {"sources": [{"src": f"https://billeder.edc.dk/{stem}_Size300x200.jpg", "width": 300},
                                    {"src": f"https://billeder.edc.dk/{stem}_Size3000x2000.jpg", "width": 3000},
                                    {"src": f"https://billeder.edc.dk/{stem}_Size1920x1080.jpg", "width": 1920}]}
    case = {"caseNumber": "51134985", "address": "Ahorntoften 36",
            "images": [src("p1"), src("p2")], "bluePrints": [src("b1")]}
    html = ('<script type="application/json">{"logoLink": {}}</script>'
            f'<script type="application/json">{json.dumps(case)}</script>')
    r = parse_for("https://www.edc.dk/alle-boliger/raekkehus/x/51134985/", html)
    assert [(m.kind, m.url) for m in r.media] == [
        ("photo", "https://billeder.edc.dk/p1_Size3000x2000.jpg"),
        ("photo", "https://billeder.edc.dk/p2_Size3000x2000.jpg"),
        ("floorplan", "https://billeder.edc.dk/b1_Size3000x2000.jpg"),
    ]


ESTATE_BODY = '''
<img class="slider-image__image lazy" src="https://estate.mindworking.eu/m/1/True?w=2100" alt="Fremhævet stue billede">
<img class="slider-image__image lazy" src="https://estate.mindworking.eu/m/2/True?w=2100" alt="Fremhævet køkken billede">
<img class="slider-image__image lazy" src="https://estate.mindworking.eu/m/1/True?w=2100" alt="Fremhævet stue billede">
<img class="floorplan__drawing lazy" src="https://estate.mindworking.eu/m/9/True?w=2100" alt="Plantegninger billede">
<img class="lazy" src="https://estate.mindworking.eu/m/9/True?w=212&amp;h=139" alt="Miniature skyderbillede af plantegning">
<img class="o-tile__image lazy" src="https://estate.mindworking.eu/m/77/True?w=534" alt="Rækkehus: Kærmysse 5">
'''


def test_estate_takes_the_gallery_and_full_size_floor_plans_not_thumbnails_or_other_listings():
    r = parse_for("https://www.estate.dk/raekkehus/2830/groendalvej/n593610/n5936100000376", ESTATE_BODY)
    assert r.house["maegler_chain"] == "estate"
    assert [(m.kind, m.url) for m in r.media] == [
        ("photo", "https://estate.mindworking.eu/m/1/True?w=2100"),
        ("photo", "https://estate.mindworking.eu/m/2/True?w=2100"),
        ("floorplan", "https://estate.mindworking.eu/m/9/True?w=2100"),
    ]


def test_edc_reads_the_listing_facts_from_the_case_json():
    case = {"caseNumber": "51134985", "city": "Kongens Lyngby", "images": [], "bluePrints": [],
            "description": "- Stort køkken-alrum.<br><br>Velkommen til <b>Ahorntoften</b> &amp; co",
            "livingArea": {"value": 115}, "areaLand": {"value": 211}, "rooms": {"value": 4},
            "propertyFacts": [{"name": "oplysninger", "facts": [
                {"type": "yearBuilt", "value": "1961"}, {"type": "energyRating", "value": "B"},
                {"type": "ownerExpensesTotalMonthly", "value": "4.732 kr."}]}]}
    html = f'<script type="application/json">{json.dumps(case)}</script>'
    h = parse_for("https://www.edc.dk/alle-boliger/raekkehus/x/51134985/", html).house
    assert h["description"] == "- Stort køkken-alrum.\n\nVelkommen til Ahorntoften & co"
    assert (h["city"], h["size_m2"], h["lot_m2"], h["rooms"]) == ("Kongens Lyngby", 115.0, 211.0, 4.0)
    assert (h["build_year"], h["energy_label"], h["ejerudgift_dkk"]) == (1961, "B", 4732.0)


def test_estate_reads_energy_label_and_ejerudgift_from_the_page():
    body = ESTATE_BODY + '''
    <div><span>Energim&#230;rke: </span> <span class="case-facts__rating -rated-C"></span></div>
    <div><span>Ejerudgift pr. md.</span> <span>5.374 kr.</span></div>'''
    h = parse_for("https://www.estate.dk/raekkehus/2830/x", body).house
    assert (h["energy_label"], h["ejerudgift_dkk"]) == ("C", 5374.0)


DANBOLIG_IMG = "https://danbolig.mindworking.eu/api/mediaData/{}/imageSize/assets/inline/true?deviceid=D"
DANBOLIG_BODY = f'''
<script type="application/ld+json">{{"@type": ["RealEstateListing"], "name": "Søkanten 9B 2820 Gentofte",
  "description": "Villa i Gentofte"}}</script>
<script type="application/ld+json">{{"@type": ["Residence"], "address": {{"streetAddress": "Søkanten 9B",
  "postalCode": "2820", "addressLocality": "Gentofte"}}, "geo": {{"latitude": "55.75", "longitude": "12.52"}}}}</script>
<button class="o-propertyHero__imageLink"><img class="o-propertyHero__image"
  src="{DANBOLIG_IMG.format("h1")}&amp;width=600" srcset="x 600w"></button>
<o-property-details :images="[{{&quot;url&quot;: &quot;{DANBOLIG_IMG.format("d1")}&quot;, &quot;type&quot;: &quot;Billede&quot;}}]"></o-property-details>
<o-property-floorplan :floorplan2d="[{{&quot;url&quot;: &quot;{DANBOLIG_IMG.format("f1")}&quot;, &quot;type&quot;: &quot;Plantegning&quot;}}]"></o-property-floorplan>
<o-property-overlay :property="{{ 'documents': [
  {{ 'url': 'https://danbolig.mindworking.eu/api/Public/Documents/tr', 'name': 'Tilstandsrapport' }},
  {{ 'url': 'https://danbolig.mindworking.eu/api/Public/Documents/so', 'name': 'Salgsopstilling' }}] }}"></o-property-overlay>
<div class="o-propertyDescription__description"><o-hidden-text>Rolig villa.</o-hidden-text></div>
<table><tr><td>Energimærke</td><td>D</td></tr><tr><td>Byggeår</td><td>1954</td></tr>
<tr><td>Rum</td><td>5</td></tr><tr><td>Boligareal</td><td>143 m²</td></tr><tr><td>Grundareal</td><td>630 m²</td></tr>
<tr><td>Kontantpris</td><td>9.250.000 kr.</td></tr><tr><td>Ejerudgift</td><td>5.016 kr.</td></tr></table>
'''


def test_danbolig_reads_address_facts_gallery_plans_and_salgsopstilling():
    r = parse_for("https://danbolig.dk/bolig/gentofte/2820/villa/5753333875-242/", DANBOLIG_BODY)
    h = r.house
    assert (h["address"], h["postal_code"], h["city"], h["lat"], h["lon"]) == (
        "Søkanten 9B", "2820", "Gentofte", 55.75, 12.52)
    assert (h["price_dkk"], h["ejerudgift_dkk"], h["size_m2"], h["lot_m2"], h["rooms"]) == (
        9_250_000.0, 5016.0, 143.0, 630.0, 5.0)
    assert (h["build_year"], h["energy_label"], h["description"]) == (1954, "D", "Rolig villa.")
    assert [(m.kind, m.url) for m in r.media] == [
        ("photo", DANBOLIG_IMG.format("h1")),
        ("photo", DANBOLIG_IMG.format("d1")),
        ("floorplan", DANBOLIG_IMG.format("f1")),
        ("pdf", "https://danbolig.mindworking.eu/api/Public/Documents/so"),
    ]


# RealEquity (Fisker & Liljengren) streams the case as escaped JSON inside a Next.js
# RSC push; the JSON-LD carries only 10 photos and no floor plan or documents.
_RE_CASE = json.dumps({
    "images": [
        {"xlUrl": "/media/images/a/p1.JPG/xl", "lgUrl": "/media/images/a/p1.JPG/lg",
         "namespace": "dk.realequity.mediaitem.image.photo"},
        {"xlUrl": "/media/images/b/Plantegning_01.jpg/xl",
         "namespace": "dk.realequity.mediaitem.image.drawing"},
        {"xlUrl": "/media/images/c/p2.JPG/xl", "namespace": "dk.realequity.mediaitem.image.photo"}],
    "ownerExpensesTotalMonthly": 5312, "plotArea": 209, "yearBuilt": 1955, "energyLabel": "C",
    "documents": [
        {"fileName": "tilstand.pdf", "namespace": "dk.realequity.ie.file.v2.visuel_tilstandsrapport",
         "url": "https://api.prod.realequity.dk/api/blobs/v2/datanodes/tr"},
        {"fileName": "Salgsopstilling.pdf",
         "namespace": "dk.realequity.report.v2.salgsopstilling_ejerbolig_offentlig",
         "url": "https://api.prod.realequity.dk/api/blobs/v2/datanodes/so"}]}, separators=(",", ":"))
REALEQUITY_BODY = f'''
<script type="application/ld+json">{{"@type": "RealEstateListing", "address": {{"streetAddress": "Åbakken 245, ",
  "postalCode": "2830", "addressLocality": "Virum"}}, "description": "Grøn udsigt",
  "offers": {{"price": "7700000"}}, "floorSize": {{"value": 107}}}}</script>
<div id="contentSection" class="styled-description"><p>På Åbakken 245.</p><p>Første række.</p></div>
<script>self.__next_f.push([1,"6:{_RE_CASE.replace('"', chr(92) + '"')}"])</script>
'''


def test_realequity_reads_the_case_json_gallery_plans_documents_and_facts():
    url = "https://fiskerliljengren.dk/ejendom/aabakken-245--2830-virum____8ba269ff"
    r = parse_for(url, REALEQUITY_BODY)
    h = r.house
    assert (h["address"], h["maegler_chain"], h["size_m2"]) == ("Åbakken 245", "fiskerliljengren", 107.0)
    assert (h["lot_m2"], h["build_year"], h["energy_label"], h["ejerudgift_dkk"]) == (209.0, 1955, "C", 5312.0)
    assert h["description"] == "På Åbakken 245.\nFørste række."
    assert [(m.kind, m.url) for m in r.media] == [
        ("photo", "https://fiskerliljengren.dk/media/images/a/p1.JPG/xl"),
        ("photo", "https://fiskerliljengren.dk/media/images/c/p2.JPG/xl"),
        ("floorplan", "https://fiskerliljengren.dk/media/images/b/Plantegning_01.jpg/xl"),
        ("pdf", "https://api.prod.realequity.dk/api/blobs/v2/datanodes/so"),
    ]


def test_danbolig_takes_the_whole_gallery_from_the_image_gallery_json_ld():
    gallery = {"@type": ["ImageGallery"], "associatedMedia": [
        {"@type": "MediaObject", "contentUrl": DANBOLIG_IMG.format(f"g{i}")} for i in range(3)]}
    body = DANBOLIG_BODY + f'<script type="application/ld+json">{json.dumps(gallery)}</script>'
    r = parse_for("https://danbolig.dk/bolig/gentofte/2820/villa/5753333875-242/", body)
    assert [m.url for m in r.media if m.kind == "photo"] == [DANBOLIG_IMG.format(f"g{i}") for i in range(3)]
    assert [m.kind for m in r.media if m.kind != "photo"] == ["floorplan", "pdf"]


def test_nybolig_uses_the_estate_template_and_reads_plot_pin_and_ejerudgift():
    body = ESTATE_BODY + '''
    <div id="js-map-thumb" data-long="12.5439725813075" data-lat="55.7807630923593"></div>
    <li>Grundstørrelse: 769 m²</li><div>Ejerudgift pr. md.</div><div>7.576</div>'''
    r = parse_for("https://www.nybolig.dk/villa/2800/egevangsvej/n436791/n4367913333698", body)
    h = r.house
    assert (h["source_adapter"], h["lot_m2"], h["ejerudgift_dkk"]) == ("nybolig", 769.0, 7576.0)
    assert (h["lat"], h["lon"]) == (55.7807630923593, 12.5439725813075)
    assert sum(m.kind == "photo" for m in r.media) == 2


def _nuxt(tree) -> str:
    """Serialize like Nuxt 3's devalue: one flat array, containers hold indexes, and the
    root (index 0) is a ShallowReactive wrapper."""
    flat: list = [None]
    def put(v):
        flat.append(None)
        i = len(flat) - 1
        flat[i] = ({k: put(x) for k, x in v.items()} if isinstance(v, dict)
                   else [put(x) for x in v] if isinstance(v, list) else v)
        return i
    flat[0] = ["ShallowReactive", put(tree)]
    return f'<script type="application/json" id="__NUXT_DATA__">{json.dumps(flat)}</script>'


def test_home_reads_the_case_from_the_nuxt_state():
    img = "https://home.mindworking.eu/api/mediaData/{}/imageSize/Assets/inline/True"
    case = {"offer": {"cashPrice": {"amount": 22800000}, "ownerCostsTotalMonthlyAmount": {"amount": 14135}},
            "address": {"full": "Hjortevej 20, 2830 Virum", "postalCode": "2830", "city": "Virum",
                        "latitude": 55.80, "longitude": 12.48},
            "stats": {"energyLabel": "B", "plotArea": 2510, "floorArea": 531, "rooms": 7,
                      "yearBuilt": "1906-01-01T00:00:00"},
            "salesPresentationDescription": "<div>Liebhavervilla<br>ved skoven</div>",
            "presentationMedia": [{"url": img.format("p1"), "mediaType": "Billede"},
                                  {"url": img.format("v1"), "mediaType": "Video"},
                                  {"url": img.format("p2"), "mediaType": "Billede"}],
            "floorPlanMedia": [{"url": img.format("f1"), "description": "Plantegning"}]}
    html = '<meta property="og:title" content="Villa til salg: Hjortevej 20, 2830 Virum">' + _nuxt(
        {"data": {"case-1560002595": case, "property-additional-data-1560002595": {}}})
    r = parse_for("https://home.dk/salg/huse-villaer/hjortevej-20-2830-virum/sag-1560002595/", html)
    h = r.house
    assert (h["address"], h["postal_code"], h["city"], h["lat"]) == ("Hjortevej 20", "2830", "Virum", 55.80)
    assert (h["price_dkk"], h["ejerudgift_dkk"], h["size_m2"], h["lot_m2"]) == (22800000, 14135, 531, 2510)
    assert (h["rooms"], h["build_year"], h["energy_label"]) == (7, 1906, "B")
    assert h["description"] == "Liebhavervilla\nved skoven"
    assert [(m.kind, m.url) for m in r.media] == [
        ("photo", img.format("p1")), ("photo", img.format("p2")), ("floorplan", img.format("f1"))]


def test_lokalbolig_follows_the_json_ld_graph_and_reads_the_rsc_case():
    base = "https://www.lokalbolig.dk/bolig/villa/kongens-lyngby/2800/kastanjeparken-30/18-X3335243"
    graph = {"@context": "https://schema.org", "@graph": [
        {"@type": "RealEstateListing", "@id": base + "#listing", "description": "Charmerende etplansvilla",
         "mainEntity": {"@id": base + "#property"}},
        {"@type": "SingleFamilyResidence", "@id": base + "#property",
         "address": {"streetAddress": "Kastanjeparken 30, 2800 Kongens Lyngby", "postalCode": "2800",
                     "addressLocality": "Kongens Lyngby"},
         "geo": {"latitude": 55.77542, "longitude": 12.53149}, "numberOfRooms": 6, "yearBuilt": 1963,
         "floorSize": {"value": 199}, "offers": {"@type": "Offer", "price": 11995000},
         "additionalProperty": {"@type": "PropertyValue", "name": "EnergyRating", "value": "C"},
         "accommodationFloorPlan": [{"@id": base + "#floorplan-1"}]},
        {"@type": "FloorPlan", "@id": base + "#floorplan-1", "layoutImage": "https://lokalbolig.io/e/1200w/plan.svg"}]}
    case = {"pictures": [{"id": "1", "url": "https://lokalbolig.io/e/1200w/https://cdn/p1.jpg", "sourceUrl": "https://cdn/p1.jpg"},
                         {"id": "1v", "url": "https://lokalbolig.io/e/600w/https://cdn/p1.jpg", "sourceUrl": "https://cdn/p1.jpg"},
                         {"id": "2", "url": "https://lokalbolig.io/e/1200w/https://cdn/p2.jpg", "sourceUrl": "https://cdn/p2.jpg"}],
            "floorplans": [{"id": "f", "url": "https://lokalbolig.io/e/1200w/https://cdn/plan.svg", "sourceUrl": "https://cdn/plan.svg"}],
            "facts": {"yearOfConstruction": 1963, "floorArea": 199, "plotArea": 1208, "energyRating": "C"},
            "documents": [{"title": "Tilstandsrapport", "url": "https://lokalbolig.mindworking.eu/api/Public/Documents/tr"},
                          {"title": "Salgsopstilling", "url": "https://lokalbolig.mindworking.eu/api/Public/Documents/so"}],
            "relatedCases": [{"plotArea": 773}]}
    rsc = json.dumps("7:" + json.dumps(case, separators=(",", ":")))   # Next.js writes compact JSON
    html = (f'<script type="application/ld+json">{json.dumps(graph)}</script>'
            f'<script>self.__next_f.push([1,{rsc}])</script>')
    r = parse_for(base, html)
    h = r.house
    assert (h["address"], h["city"], h["price_dkk"], h["size_m2"], h["rooms"]) == (
        "Kastanjeparken 30", "Kongens Lyngby", 11995000.0, 199.0, 6.0)
    assert (h["build_year"], h["energy_label"], h["lot_m2"], h["lat"]) == (1963, "C", 1208.0, 55.77542)
    assert [(m.kind, m.url) for m in r.media] == [
        ("photo", "https://cdn/p1.jpg"), ("photo", "https://cdn/p2.jpg"),
        ("floorplan", "https://cdn/plan.svg"),
        ("pdf", "https://lokalbolig.mindworking.eu/api/Public/Documents/so")]


def test_realmaeglerne_reads_the_fact_rows_lazy_gallery_and_plan():
    img = "https://mediaserver.prod.realequity.dk/images/{}.jpg/{}"
    html = f'''
    <script type="application/ld+json">{{"@context": "http://schema.org", "@type": "Residence",
      "address": {{"postalCode": "2660", "streetAddress": "Kærlunden 15, "}}}}</script>
    <div class="address-price"><div class="d-flex"><div>Kontantpris</div><div>5.995.000 kr.</div></div>
      <div class="d-flex"><div>Ejerudgift</div><div>3.088 kr.</div></div></div>
    <div class="address-info-item"><div>Rum</div><div>5</div></div>
    <div class="address-info-item"><div>Energimærke <a>Prøv klimaberegner</a></div><div class="energylabel" data-energylabel="B"></div></div>
    <div class="table-item"><div role="cell">Boligareal</div><div role="cell">150 m&sup2</div></div>
    <div class="table-item"><div role="cell">Grundareal</div><div role="cell">727 m&sup2</div></div>
    <div class="table-item"><div role="cell">Bygget/ombygget</div><div role="cell">2000 </div></div>
    <div class="description js-description"><div class="text-full"><p>Kun 1 ejer</p><p>Pragtfuldt hus</p></div></div>
    <img class="img-fluid" src="{img.format("a", "lg")}" data-target="#assets-modal" alt="Image of realestate" />
    <div class="image-gallery large-images"><img id="image_large_0" src="/na.png" data-src="{img.format("b", "xl")}" />
      <img id="image_large_1" src="/na.png" data-src="{img.format("c", "xl")}" /></div>
    <div class="content-section blueprint-content"><div class="image-gallery"><img src="/na.png" data-src="{img.format("p", "xl")}" /></div></div>
    <a href="javascript:panelSalgsopstilling('Emnevisning');">Hent salgsopstilling</a>
    <a href="https://api.prod.realequity.dk/api/blobs/v2/datanodes/so" class="btn">Hent Salgsopstilling</a>'''
    r = parse_for("https://www.realmaeglerne.dk/bolig/135-0636-kaerlunden-15", html)
    h = r.house
    assert (h["address"], h["price_dkk"], h["ejerudgift_dkk"], h["rooms"], h["energy_label"]) == (
        "Kærlunden 15", 5995000.0, 3088.0, 5.0, "B")
    assert (h["size_m2"], h["lot_m2"], h["build_year"]) == (150.0, 727.0, 2000)
    assert h["description"] == "Kun 1 ejer\nPragtfuldt hus"
    assert [(m.kind, m.url) for m in r.media] == [
        ("photo", img.format("a", "xl")), ("photo", img.format("b", "xl")), ("photo", img.format("c", "xl")),
        ("floorplan", img.format("p", "xl")), ("pdf", "https://api.prod.realequity.dk/api/blobs/v2/datanodes/so")]


def test_johnfrandsen_reads_the_facts_list_slides_and_map_pin():
    img = "https://johnfrandsen.mindworking.eu/api/mediaData/{}/imageSize/Assets/inline/True?width=2560"
    html = f'''
    <script type="application/ld+json">{{"@type": "Residence", "address": {{"streetAddress": "Skovdiget 2",
      "postalCode": "8400", "addressLocality": "Ebeltoft"}}}}</script>
    <nav><ul><li><a href="/">Forside</a><span>x</span></li></ul></nav>
    <div class="slide plan"><img data-lazy="{img.format("f1")}" /></div>
    <div class="slide image"><img data-lazy="{img.format("p1")}" /></div>
    <div class="slide image"><img data-lazy="{img.format("p2")}" /></div>
    <div id="case-map" data-latitude="56.186470343798" data-longitude="10.674265358398"></div>
    <ul><li>Pris<span>2.095.000 kr.</span></li><li>Ejerudg. pr. md.<span>1.741</span></li></ul>
    <ul><li>Boligareal<span>141 m²</span></li><li>Grundareal<span>1017 m²</span></li>
    <li>Bygge-/ombygningsår<span>1975/1999</span></li><li>Værelser<span>6</span></li>
    <li>Energimærke<span>C</span></li></ul>'''
    r = parse_for("https://www.johnfrandsen.dk/sag/35600002410/skovdiget-2-8400-ebeltoft/", html)
    h = r.house
    assert (h["price_dkk"], h["ejerudgift_dkk"], h["size_m2"], h["lot_m2"]) == (2095000.0, 1741.0, 141.0, 1017.0)
    assert (h["build_year"], h["rooms"], h["energy_label"], h["lat"]) == (1975, 6.0, "C", 56.186470343798)
    assert [(m.kind, m.url) for m in r.media] == [
        ("photo", img.format("p1")), ("photo", img.format("p2")), ("floorplan", img.format("f1"))]


def test_an_unknown_agent_on_realequity_gets_the_realequity_parser_and_the_case_price():
    body = REALEQUITY_BODY.replace('"offers": {"price": "7700000"}, ', "").replace(
        '\\"ownerExpenses', '\\"price\\":2150000,\\"ownerExpenses')
    r = parse_for("https://www.some-new-maegler.dk/ejendom/aabakken-245", body)
    assert (r.house["source_adapter"], r.house["price_dkk"]) == ("realequity", 2150000.0)
    assert sum(m.kind == "photo" for m in r.media) == 2


def test_lokalbolig_keeps_one_of_each_photos_horizontal_and_vertical_crop():
    url = "https://www.lokalbolig.dk/bolig/r%C3%A6kkehus/holte/2840/kildemosevej-54/28-X3335859"
    pic = lambda n, order, orientation: {"id": n, "sourceUrl": f"https://cdn/{n}.jpg",
                                         "order": order, "orientation": orientation}
    case = {"pictures": [pic("51", 1, "HORIZONTAL"), pic("52", 1, "VERTICAL"),
                         pic("59", 3, "VERTICAL"), pic("60", 3, "HORIZONTAL"),
                         pic("70", 4, "VERTICAL")]}                # a portrait shot has no twin
    rsc = json.dumps("7:" + json.dumps(case, separators=(",", ":")))
    html = (f'<script type="application/ld+json">{{"@type": "RealEstateListing", "address": '
            f'{{"streetAddress": "Kildemosevej 54", "postalCode": "2840"}}}}</script>'
            f'<script>self.__next_f.push([1,{rsc}])</script>')
    assert [m.url for m in parse_for(url, html).media if m.kind == "photo"] == [
        "https://cdn/51.jpg", "https://cdn/60.jpg", "https://cdn/70.jpg"]
