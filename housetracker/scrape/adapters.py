"""Host detection + adapter dispatch. Chain adapters route through the generic parser
until a real page shows the fallback misses fields for that chain — then add a per-chain
parse function `fn(html, url) -> ScrapeResult` to _ADAPTERS keyed by the chain name."""
from __future__ import annotations

import html as _html
import json
import re
from urllib.parse import urljoin, urlparse

from housetracker.scrape.parse import (
    MediaRef, ScrapeResult, _completeness, _dedup, _num, _parse_dkk, _TagParser,
    json_scripts, parse_listing, street_only,
)

_CHAINS = {
    "nybolig.dk": "nybolig",
    "edc.dk": "edc",
    "home.dk": "home",
    "danbolig.dk": "danbolig",
    "estate.dk": "estate",
    "fiskerliljengren.dk": "fiskerliljengren",
    "boligone.dk": "boligone",
    "lokalbolig.dk": "lokalbolig",
    "realmaeglerne.dk": "realmaeglerne",
    "johnfrandsen.dk": "johnfrandsen",
}

# Danish fact-table labels -> house fields, for the chains that print label/value rows.
_FACT_LABELS = {
    "Kontantpris": "price_dkk", "Pris": "price_dkk",
    "Ejerudgift": "ejerudgift_dkk", "Ejerudgift pr. md.": "ejerudgift_dkk",
    "Ejerudg. pr. md.": "ejerudgift_dkk",
    "Boligareal": "size_m2", "Grundareal": "lot_m2", "Grundstørrelse": "lot_m2",
    "Rum": "rooms", "Værelser": "rooms",
    "Byggeår": "build_year", "Bygget/ombygget": "build_year",
    "Bygge-/ombygningsår": "build_year",
    "Energimærke": "energy_label",
}


def _pdfs(result: ScrapeResult) -> list:
    return [m for m in result.media if m.kind == "pdf"]


def _set(result: ScrapeResult, **fields) -> None:
    result.house.update({k: v for k, v in fields.items() if v is not None})


def _plain(html_text: str) -> str:
    """Listing prose to plain text: <br> -> newline, other tags dropped."""
    return _html.unescape(re.sub(r"<[^>]+>", "", re.sub(r"<br\s*/?>", "\n", html_text))).strip()


def _year(v) -> int | None:
    n = _num(v)
    return int(n) if n else None


def _facts(pairs) -> dict:
    """(label, value) rows of a facts table -> house fields. First row per field wins."""
    out: dict = {}
    for label, value in pairs:
        field = _FACT_LABELS.get(label.strip().rstrip(":"))
        if field is None or field in out or not value:
            continue
        if field == "energy_label":
            m = re.match(r"[A-G][0-9+]*", value.strip())
            v = m and m.group(0)
        elif field == "build_year":                       # "1975/1999" -> built 1975
            m = re.search(r"\d{4}", value)
            v = m and int(m.group(0))
        else:
            v = _parse_dkk(value)
        if v is not None:
            out[field] = v
    return out


def _json_array(text: str, key: str) -> list:
    """The JSON array after the first `"key":[` in text, or []."""
    i = text.find(f'"{key}":[')
    if i < 0:
        return []
    try:
        return json.JSONDecoder().raw_decode(text, i + len(key) + 3)[0]
    except json.JSONDecodeError:
        return []


def _rsc_text(html: str) -> str:
    """Next.js App Router streams its payload as JS string literals in
    self.__next_f.push([1, "..."]); decoded and joined they hold the page's JSON."""
    out = []
    for m in re.finditer(r'self\.__next_f\.push\(\[1,\s*("(?:[^"\\]|\\.)*")\]\)', html):
        try:
            out.append(json.loads(m.group(1)))
        except json.JSONDecodeError:
            continue
    return "".join(out)


_NUXT_WRAPPERS = {"Reactive", "ShallowReactive", "Ref", "ShallowRef"}


def _nuxt_state(html: str):
    """Nuxt 3 ships its state as one flat JSON array whose objects and arrays hold
    indexes into that same array (devalue). Rebuild the tree, unwrapping reactive
    wrappers; other typed values (Date, Set, ...) are dropped."""
    flat = next((b for b in json_scripts(html, "application/json")
                 if isinstance(b, list) and b), None)
    if flat is None:
        return None
    memo: dict = {}

    def rev(i):
        if not isinstance(i, int) or not 0 <= i < len(flat):
            return None
        if i in memo:
            return memo[i]
        v = flat[i]
        if isinstance(v, list) and v and isinstance(v[0], str):
            memo[i] = rev(v[1]) if v[0] in _NUXT_WRAPPERS and len(v) == 2 else None
        elif isinstance(v, list):
            memo[i] = out = []
            out.extend(rev(j) for j in v)
        elif isinstance(v, dict):
            memo[i] = out = {}
            out.update({k: rev(j) for k, j in v.items()})
        else:
            memo[i] = v
        return memo[i]
    return rev(0)


def _edc(html: str, url: str) -> ScrapeResult:
    """EDC's JSON-LD carries one 300px image; the gallery and floor plans live in the
    case JSON (each image offered in ~10 sizes, up to 3000px)."""
    r = parse_listing(html, url)
    case = next((d for d in json_scripts(html, "application/json")
                 if isinstance(d, dict) and "bluePrints" in d), None)
    if case is None:
        return r
    value = lambda v: _num(v.get("value") if isinstance(v, dict) else v)
    facts = {f.get("type"): f.get("value")
             for group in case.get("propertyFacts") or [] for f in group.get("facts") or []}
    # livingArea, not the JSON-LD floorSize: that is EDC's weighted area incl. basement.
    _set(r, description=_plain(case["description"]) if case.get("description") else None,
         city=case.get("city"), size_m2=value(case.get("livingArea")),
         lot_m2=value(case.get("areaLand")), rooms=value(case.get("rooms")),
         build_year=_year(facts.get("yearBuilt")), energy_label=facts.get("energyRating"),
         ejerudgift_dkk=_parse_dkk(facts.get("ownerExpensesTotalMonthly")))
    largest = lambda img: max(img["sources"], key=lambda s: s.get("width") or 0)["src"]
    r.media = ([MediaRef("photo", largest(i)) for i in case.get("images") or [] if i.get("sources")]
               + [MediaRef("floorplan", largest(i)) for i in case.get("bluePrints") or []
                  if i.get("sources")]
               + _pdfs(r))
    return r


def _estate(html: str, url: str) -> ScrapeResult:
    """Estate and Nybolig (one Mindworking template) render the full-screen gallery and
    the floor plans as <img> at 2100px. The generic floor-plan match also caught the
    212px slider thumbnails, and other listings' tiles share the image host — so pick
    by class. Plot size, ejerudgift and the map pin are only in the page text/markup."""
    r = parse_listing(html, url)
    tp = _TagParser()
    tp.feed(html)
    pick = lambda cls, kind: [MediaRef(kind, urljoin(url, i["src"])) for i in tp.imgs if cls in i["class"]]
    picked = _dedup(pick("slider-image__image", "photo") + pick("floorplan__drawing", "floorplan"))
    if picked:                                  # a template change keeps the generic media
        r.media = picked + _pdfs(r)
    label = re.search(r"-rated-([A-G][0-9+]*)", html)
    text = _html.unescape(re.sub(r"<[^>]+>", " ", html))
    owner = re.search(r"Ejerudgift pr\. md\.\s*([\d.]+)", text)       # Nybolig drops the "kr"
    lot = re.search(r"Grundstørrelse:\s*([\d.]+)", text)
    lat, lon = (re.search(rf'data-{k}="([\d.]+)"', html) for k in ("lat", "long"))
    _set(r, energy_label=label and label.group(1),
         ejerudgift_dkk=owner and _parse_dkk(owner.group(1)), lot_m2=lot and _parse_dkk(lot.group(1)),
         lat=lat and _num(lat.group(1)), lon=lon and _num(lon.group(1)))
    return r


def _danbolig(html: str, url: str) -> ScrapeResult:
    """Danbolig (Mindworking, Vue): the first JSON-LD block has no address (the Residence
    one does), the facts are a label/value table, the full gallery is an ImageGallery
    JSON-LD block, the floor plans ride in component props as JSON, and the
    salgsopstilling link sits in the overlay's props."""
    from bs4 import BeautifulSoup  # lazy: scrape extra
    r = parse_listing(html, url)
    soup = BeautifulSoup(html, "html.parser")
    res = next((b for b in json_scripts(html, "application/ld+json")
                if isinstance(b, dict) and isinstance(b.get("address"), dict)), {})
    addr, geo = res.get("address", {}), res.get("geo") or {}
    facts = {tds[0].get_text(strip=True): tds[1].get_text(strip=True)
             for tr in soup.select("tr") if len(tds := tr.find_all("td")) == 2}
    desc = soup.select_one(".o-propertyDescription__description")
    _set(r, address=addr.get("streetAddress"), postal_code=addr.get("postalCode"),
         city=addr.get("addressLocality"), lat=_num(geo.get("latitude")),
         lon=_num(geo.get("longitude")), **_facts(facts.items()),
         description=desc.get_text("\n", strip=True) if desc else None)
    props = lambda tag, attr: [i["url"] for el in soup.select(tag)
                               for i in json.loads(el.get(attr) or "[]") if i.get("url")]
    gallery = next((b.get("associatedMedia") or [] for b in json_scripts(html, "application/ld+json")
                    if isinstance(b, dict) and "ImageGallery" in str(b.get("@type"))), [])
    photos = [m["contentUrl"] for m in gallery if isinstance(m, dict) and m.get("contentUrl")]
    hero = [re.sub(r"&width=\d+", "", i["src"]) for i in soup.select(".o-propertyHero__imageLink img")]
    overlay = " ".join(el[":property"] for el in soup.find_all(attrs={":property": True}))
    pdf = re.search(r"'url':\s*'([^']+)',\s*'name':\s*'Salgsopstilling'", overlay)
    photos = photos or hero + props("o-property-details", ":images")
    plans = props("o-property-floorplan", ":floorplan2d")
    if photos or plans:
        r.media = _dedup([MediaRef("photo", u) for u in photos] + [MediaRef("floorplan", u) for u in plans]
                         + ([MediaRef("pdf", pdf.group(1))] if pdf else _pdfs(r)))
    return r


def _realequity(html: str, url: str) -> ScrapeResult:
    """RealEquity sites (Fisker & Liljengren) stream the case as escaped JSON inside a
    Next.js RSC push. The JSON-LD has only 10 photos and no plans or documents, so the
    gallery, floor plans, salgsopstilling and the remaining facts come from the case."""
    r = parse_listing(html, url)
    case = html.replace('\\"', '"')
    num = lambda key: (m := re.search(rf'"{key}":(\d+)', case)) and float(m.group(1))
    label = re.search(r'"energyLabel":"([A-G][0-9+]*)"', case)
    desc = re.search(r'<div id="contentSection"[^>]*>(.*?)</div>', html, re.S)
    _set(r, price_dkk=None if r.house.get("price_dkk") else num("price"),   # sold: no JSON-LD price
         lot_m2=num("plotArea"), build_year=_year(num("yearBuilt")),
         energy_label=label and label.group(1), ejerudgift_dkk=num("ownerExpensesTotalMonthly"),
         description=desc and _plain(re.sub(r"</p>\s*<p[^>]*>", "\n", desc.group(1))))
    items = re.findall(r'\{"xlUrl":"([^"]+)"[^{}]*?"namespace":"dk\.realequity\.mediaitem\.image\.(photo|drawing)"', case)
    pdf = re.search(r'"namespace":"[^"]*salgsopstilling[^"]*","url":"([^"]+)"', case)
    pick = lambda ns, kind: [MediaRef(kind, urljoin(url, u)) for u, n in items if n == ns]
    if items:
        r.media = _dedup(pick("photo", "photo") + pick("drawing", "floorplan")
                         + ([MediaRef("pdf", pdf.group(1))] if pdf else _pdfs(r)))
    return r


def _home(html: str, url: str) -> ScrapeResult:
    """home.dk (Nuxt): the JSON-LD is only the company; the whole case (facts, gallery,
    floor plans) is in the Nuxt state. Their salgsopstilling is an online page, no PDF."""
    r = parse_listing(html, url)
    data = (_nuxt_state(html) or {}).get("data") or {}
    case = next((v for k, v in data.items() if k.startswith("case-") and isinstance(v, dict)), None)
    if case is None:
        return r
    offer, addr, stats = (case.get(k) or {} for k in ("offer", "address", "stats"))
    amount = lambda v: _num((v or {}).get("amount"))
    desc = case.get("salesPresentationDescription")
    _set(r, address=street_only(addr["full"], addr.get("postalCode")) if addr.get("full") else None,
         postal_code=addr.get("postalCode"), city=addr.get("city"),
         lat=_num(addr.get("latitude")), lon=_num(addr.get("longitude")),
         price_dkk=amount(offer.get("cashPrice")),
         ejerudgift_dkk=amount(offer.get("ownerCostsTotalMonthlyAmount")),
         size_m2=_num(stats.get("floorArea")), lot_m2=_num(stats.get("plotArea")),
         rooms=_num(stats.get("rooms")), build_year=_year(str(stats.get("yearBuilt") or "")[:4]),
         energy_label=stats.get("energyLabel") or None, description=desc and _plain(desc))
    urls = lambda key: [m["url"] for m in case.get(key) or [] if isinstance(m, dict) and m.get("url")
                        and (key != "presentationMedia" or m.get("mediaType") == "Billede")]
    photos, plans = urls("presentationMedia"), urls("floorPlanMedia")
    if photos or plans:
        r.media = _dedup([MediaRef("photo", u) for u in photos] + [MediaRef("floorplan", u) for u in plans])
    return r


def _lokalbolig(html: str, url: str) -> ScrapeResult:
    """LokalBolig (Next.js): the JSON-LD graph carries the facts; the full-size gallery,
    floor plans, plot size and documents are in the case JSON of the RSC payload."""
    r = parse_listing(html, url)
    text = _rsc_text(html)
    src = lambda key: [i["sourceUrl"] for i in _json_array(text, key)
                       if isinstance(i, dict) and i.get("sourceUrl")]
    pdf = next((d["url"] for d in _json_array(text, "documents")
                if isinstance(d, dict) and d.get("title") == "Salgsopstilling" and d.get("url")), None)
    lot = re.search(r'"yearOfConstruction":[^{}]*?"plotArea":(\d+)', text)
    _set(r, lot_m2=lot and float(lot.group(1)))
    # Each photo comes twice under one `order`: the frame (HORIZONTAL) and a portrait crop
    # of it (VERTICAL). Keep one per order, the frame when there is one.
    shots: dict = {}
    for i in _json_array(text, "pictures"):
        if isinstance(i, dict) and i.get("sourceUrl"):
            key = i.get("order", i["sourceUrl"])
            if key not in shots or i.get("orientation") == "HORIZONTAL":
                shots[key] = i["sourceUrl"]
    photos, plans = list(shots.values()), src("floorplans")
    if photos or plans:
        r.media = _dedup([MediaRef("photo", u) for u in photos] + [MediaRef("floorplan", u) for u in plans]
                         + ([MediaRef("pdf", pdf)] if pdf else _pdfs(r)))
    return r


def _realmaeglerne(html: str, url: str) -> ScrapeResult:
    """RealMæglerne renders server-side: label/value fact rows, the gallery and floor
    plans as lazy <img data-src> at xl size, the energy label as a data attribute."""
    from bs4 import BeautifulSoup  # lazy: scrape extra
    r = parse_listing(html, url)
    soup = BeautifulSoup(html, "html.parser")
    rows = [(d[0].get_text(" ", strip=True), d[1].get_text(" ", strip=True))
            for row in soup.select(".table-item, .address-info-item, .address-price > div")
            if len(d := row.find_all("div", recursive=False)) == 2]
    fields = _facts(rows)
    label = soup.select_one("[data-energylabel]")
    fields.setdefault("energy_label", label and label["data-energylabel"] or None)
    desc = soup.select_one(".description .text-full")
    _set(r, **fields, description=desc.get_text("\n", strip=True) if desc else None)
    hero = [re.sub(r"/(lg|md)$", "/xl", i["src"]) for i in soup.select('img[data-target="#assets-modal"]')]
    lazy = lambda scope: [i["data-src"] for i in soup.select(f"{scope} img[data-src]")]
    photos, plans = hero + lazy(".large-images"), lazy(".blueprint-content")
    if photos or plans:
        r.media = _dedup([MediaRef("photo", u) for u in photos]
                         + [MediaRef("floorplan", u) for u in plans] + _pdfs(r))
    return r


def _johnfrandsen(html: str, url: str) -> ScrapeResult:
    """John Frandsen (WordPress, Mindworking media): facts as <li>label<span>value</span>,
    gallery and plan slides as lazy <img data-lazy>, the map pin on #case-map. The
    salgsopstilling sits behind a form."""
    from bs4 import BeautifulSoup  # lazy: scrape extra
    r = parse_listing(html, url)
    soup = BeautifulSoup(html, "html.parser")
    rows = [(li.find(string=True, recursive=False) or "", li.span.get_text(strip=True))
            for li in soup.select("li") if li.span]
    pin = soup.select_one("#case-map") or {}
    _set(r, **_facts(rows), lat=_num(pin.get("data-latitude")), lon=_num(pin.get("data-longitude")))
    slides = lambda cls: [i["data-lazy"] for i in soup.select(f".slide.{cls} img[data-lazy]")]
    photos, plans = slides("image"), slides("plan")
    if photos or plans:
        r.media = _dedup([MediaRef("photo", u) for u in photos]
                         + [MediaRef("floorplan", u) for u in plans] + _pdfs(r))
    return r


# Per-chain parsers; a chain without one parses through the generic fallback.
_ADAPTERS: dict = {"edc": _edc, "estate": _estate, "nybolig": _estate, "danbolig": _danbolig,
                   "fiskerliljengren": _realequity, "boligone": _realequity, "home": _home,
                   "lokalbolig": _lokalbolig, "realmaeglerne": _realmaeglerne,
                   "johnfrandsen": _johnfrandsen}

# Shared platforms: an agent with no chain entry still gets the right parser when its
# page carries the platform's fingerprint.
_PLATFORMS = (("dk.realequity.mediaitem", "realequity", _realequity),
              ("slider-image__image", "mindworking", _estate))


def detect_chain(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    for domain, name in _CHAINS.items():
        if host == domain or host.endswith("." + domain):
            return name
    return "generic"


def parse_for(url: str, html: str) -> ScrapeResult:
    chain = detect_chain(url)
    name, parser = chain, _ADAPTERS.get(chain)
    if parser is None:
        name, parser = next(((n, fn) for mark, n, fn in _PLATFORMS if mark in html), (chain, None))
    result = parse_listing(html, url) if parser is None else parser(html, url)
    if chain != "generic":
        result.house["maegler_chain"] = chain
    if parser is not None:                       # it may have replaced the media
        result.house["source_adapter"] = name
        result.house["scrape_completeness"] = _completeness(result.house, result.media)
    return result
