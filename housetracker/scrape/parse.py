"""Generic listing parser: JSON-LD + OpenGraph + PDF/gallery detection. Pure, no I/O."""
from __future__ import annotations

import html as _html
import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

_SCRIPT_RE = re.compile(r"<script([^>]*)>(.*?)</script>", re.IGNORECASE | re.DOTALL)
_TYPE_RE = re.compile(r"""type\s*=\s*["']([^"']+)""", re.IGNORECASE)
_FLOORPLAN_HINT = re.compile(r"plantegning|floor[\-_ ]?plan|grundplan", re.IGNORECASE)
_PDF_HINT = re.compile(r"salgsopstilling|prospekt", re.IGNORECASE)
_REALESTATE_TYPES = {"RealEstateListing", "Residence", "SingleFamilyResidence",
                     "House", "Apartment", "Product", "Offer"}
_COMPLETENESS_KEYS = ("address", "price_dkk", "size_m2", "description")


@dataclass
class MediaRef:
    kind: str
    url: str
    caption: str | None = None


@dataclass
class ScrapeResult:
    house: dict = field(default_factory=dict)
    media: list = field(default_factory=list)


class _TagParser(HTMLParser):
    """Collect OpenGraph/meta, <img> src+alt, and <a> href+text for fallback extraction."""

    def __init__(self):
        super().__init__()
        self.meta: dict[str, str] = {}
        self.imgs: list[dict] = []
        self.links: list[dict] = []
        self._a_href: str | None = None
        self._a_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            key = a.get("property") or a.get("name")
            if key and a.get("content"):
                self.meta[key.lower()] = a["content"]
        elif tag == "img" and a.get("src"):
            self.imgs.append({"src": a["src"], "alt": a.get("alt", "") or "",
                              "class": (a.get("class") or "").split()})
        elif tag == "a" and a.get("href"):
            self._a_href = a["href"]
            self._a_text = []

    def handle_data(self, data):
        if self._a_href is not None:
            self._a_text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._a_href is not None:
            self.links.append({"href": self._a_href, "text": "".join(self._a_text).strip()})
            self._a_href = None


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _parse_dkk(text) -> float | None:
    """Danish price text -> float DKK. '4.995.000 kr.' -> 4995000.0
    ('.' = thousands sep, ',' = decimal). Numbers pass straight through."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    m = re.search(r"\d[\d.\s]*(?:,\d+)?", str(text))
    if not m:
        return None
    num = m.group(0).replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(num)
    except ValueError:
        return None


def json_scripts(html: str, script_type: str) -> list:
    """Parsed bodies of every <script type=script_type>. The attribute is unescaped
    first: EDC writes type="application/ld&#x2B;json"."""
    out = []
    for attrs, body in _SCRIPT_RE.findall(html):
        t = _TYPE_RE.search(_html.unescape(attrs))
        if not t or t.group(1).strip().lower() != script_type:
            continue
        try:
            out.append(json.loads(body.strip()))
        except json.JSONDecodeError:
            continue
    return out


def _jsonld_blocks(html: str) -> list:
    out = []
    for data in json_scripts(html, "application/ld+json"):
        if isinstance(data, dict) and "@graph" in data:
            out.extend(data["@graph"])
        elif isinstance(data, list):
            out.extend(data)
        else:
            out.append(data)
    return out


def _pick_listing(blocks: list) -> dict:
    # Graph nodes may point at each other by a bare {"@id": ...} (LokalBolig's listing ->
    # its house -> its floor plans): follow those one level.
    ids = {b["@id"]: b for b in blocks if isinstance(b, dict) and isinstance(b.get("@id"), str)}
    ref = lambda v: ids.get(v["@id"], v) if isinstance(v, dict) and v.keys() == {"@id"} else v
    for b in blocks:
        if not isinstance(b, dict):
            continue
        t = b.get("@type", "")
        types = t if isinstance(t, list) else [t]
        if _REALESTATE_TYPES.intersection(types):
            # The house itself may be nested: RealEstateListing.mainEntity (Estate),
            # Offer.itemOffered (EDC). Its fields win; the wrapper keeps price/image.
            inner = ref(b.get("mainEntity") or b.get("itemOffered"))
            node = {**b, **inner} if isinstance(inner, dict) else b
            return {k: [ref(x) for x in v] if isinstance(v, list) else ref(v)
                    for k, v in node.items()}
    return {}


def street_only(address: str, postal_code=None) -> str:
    """'Åbakken 245, ' / 'Kastanjeparken 30, 2800 Kongens Lyngby' -> the street part."""
    if postal_code:
        address = re.sub(rf",\s*{re.escape(str(postal_code))}\b.*$", "", address)
    return address.strip().rstrip(",").strip()


def _completeness(house: dict, media: list) -> float:
    have = sum(1 for k in _COMPLETENESS_KEYS if house.get(k) is not None)
    have += sum(1 for kind in ("floorplan", "pdf", "photo")
                if any(m.kind == kind for m in media))
    return round(have / (len(_COMPLETENESS_KEYS) + 3), 3)


def _dedup(media: list) -> list:
    seen, out = set(), []
    for m in media:
        key = (m.kind, m.url)
        if key not in seen:
            seen.add(key)
            out.append(m)
    return out


def parse_listing(html: str, url: str) -> ScrapeResult:
    house: dict = {"listing_url": url, "source_adapter": "generic",
                   "maegler_chain": urlparse(url).hostname or None}
    media: list = []

    ld = _pick_listing(_jsonld_blocks(html))

    addr = ld.get("address")
    if isinstance(addr, dict):
        if addr.get("streetAddress"):
            house["address"] = street_only(addr["streetAddress"], addr.get("postalCode"))
        house["postal_code"] = addr.get("postalCode")
        house["city"] = addr.get("addressLocality")
    elif isinstance(addr, str):
        house["address"] = addr

    offers = ld.get("offers")
    if isinstance(offers, dict):                 # Estate spells it "Price"
        house["price_dkk"] = _parse_dkk(offers.get("price") or offers.get("Price"))
    if house.get("price_dkk") is None:
        house["price_dkk"] = _parse_dkk(ld.get("price"))

    plans = [p for p in _as_list(ld.get("accommodationFloorPlan")) if isinstance(p, dict)]
    plan = plans[0] if plans else {}
    fs = ld.get("floorSize") or plan.get("floorSize")
    if isinstance(fs, dict):
        house["size_m2"] = _num(fs.get("value"))

    rooms = ld.get("numberOfRooms") or plan.get("numberOfRooms")
    house["rooms"] = _num(rooms.get("value") if isinstance(rooms, dict) else rooms)
    props = {p.get("name"): p.get("value") for p in _as_list(ld.get("additionalProperty"))
             if isinstance(p, dict)}
    year = _num(ld.get("yearBuilt") or props.get("Byggeår"))
    house["build_year"] = int(year) if year else None
    label = props.get("Energimærke") or props.get("EnergyRating")
    house["energy_label"] = label if isinstance(label, str) and label else None

    geo = ld.get("geo")
    if isinstance(geo, dict):
        house["lat"] = _num(geo.get("latitude"))
        house["lon"] = _num(geo.get("longitude"))

    if ld.get("description"):
        house["description"] = ld["description"]

    for img in _as_list(ld.get("image")):
        u = img.get("url") if isinstance(img, dict) else img
        if isinstance(u, str):
            kind = "floorplan" if _FLOORPLAN_HINT.search(u) else "photo"
            media.append(MediaRef(kind=kind, url=urljoin(url, u)))
    for img in [i for p in plans for i in _as_list(p.get("layoutImage"))]:
        u = img.get("url") if isinstance(img, dict) else img
        if isinstance(u, str):
            media.append(MediaRef(kind="floorplan", url=urljoin(url, u)))

    tp = _TagParser()
    tp.feed(html)
    if "address" not in house and tp.meta.get("og:title"):
        house["address"] = tp.meta["og:title"]
    if house.get("price_dkk") is None:
        house["price_dkk"] = _parse_dkk(tp.meta.get("product:price:amount"))
    if not house.get("description") and tp.meta.get("og:description"):
        house["description"] = tp.meta["og:description"]
    if not media and tp.meta.get("og:image"):
        media.append(MediaRef(kind="photo", url=urljoin(url, tp.meta["og:image"])))
    for img in tp.imgs:
        if _FLOORPLAN_HINT.search(img["src"]) or _FLOORPLAN_HINT.search(img["alt"]):
            media.append(MediaRef(kind="floorplan", url=urljoin(url, img["src"]),
                                  caption=img["alt"] or None))

    for link in tp.links:
        href = link["href"]
        if href.lower().startswith("javascript:"):   # RealMæglerne's "Hent salgsopstilling" panel
            continue
        if (href.lower().endswith(".pdf") or _PDF_HINT.search(href)
                or _PDF_HINT.search(link["text"])):
            media.append(MediaRef(kind="pdf", url=urljoin(url, href),
                                  caption=link["text"] or None))

    house["scrape_completeness"] = _completeness(house, media)
    house = {k: v for k, v in house.items() if v is not None}
    return ScrapeResult(house=house, media=_dedup(media))
