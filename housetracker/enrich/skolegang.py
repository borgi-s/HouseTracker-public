"""skolegang.dk: the folkeskoler of a kommune and each school's figures. The site is
server-rendered Next.js: a school page carries a schema.org `School` JSON-LD block (the
register facts and one school year of figures with national ranks) and the page payload
(`self.__next_f.push`) holds the per-year series. Pure parsing + figure maths here; the
network lives behind the `fetch` seam in schools.py."""
from __future__ import annotations

import json
import re
import urllib.parse

SKOLEGANG = "https://skolegang.dk"
FOLKESKOLE = "1012"                       # InstTypeNr of a municipal folkeskole

# key, label, better ("high" / "low" / None = neutral), unit, series field in the
# payload ("wb:<name>" = a wellbeing indicator), JSON-LD value, JSON-LD national rank
FIGURES = (
    ("grade", "Grade average", "high", "", "karaktergennemsnit", "KarakterGns", "KarakterGnsRang"),
    ("expected_grade", "Expected grade (pupils' background)", None, "",
     "socRefSocioøkonomiskReference", "SocRefSocioøkonomiskReference", None),
    ("teaching_effect", "Teaching effect", "high", "", "socRefForskel",
     "UndervisningsEffekt", "UndervisningsEffektRang"),
    ("wellbeing", "Overall wellbeing", "high", "", "wb:Generel trivsel", None, None),
    ("social_wellbeing", "Social wellbeing", "high", "", "wb:Social trivsel",
     "SocialTrivsel", "SocialTrivselRang"),
    ("academic_wellbeing", "Academic wellbeing", "high", "", "wb:Faglig trivsel",
     "FagligTrivsel", "FagligTrivselRang"),
    ("calm", "Calm and order", "high", "", "wb:Ro og orden", "RoOgOrden", "RoOgOrdenRang"),
    ("support", "Support and inspiration", "high", "", "wb:Støtte og inspiration",
     "Inspiration", "InspirationRang"),
    ("high_wellbeing", "Share with high wellbeing", "high", "%", "andelMedHøjestTrivsel",
     "AndelMedHøjestTrivsel", "AndelMedHøjestTrivselRang"),
    ("absence", "Absence", "low", "%", "samletElevfravær", "ElevFravær", "ElevFraværRang"),
    ("class_size", "Pupils per class", None, "", "klassekvotient", "KlasseKvotient",
     "KlasseKvotientRang"),
    ("coverage", "Teacher subject coverage", "high", "%", "kompetencedækning",
     "KompetenceDækning", "KompetenceDækningRang"),
    ("pupils", "Pupils", None, "", "elevtal", "AntalElever", "AntalEleverRang"),
    ("danish_origin", "Share of Danish origin", None, "%", None, "DanskHerkomst",
     "DanskHerkomstRang"),
)

_PUSH = re.compile(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)')
_LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
_TENTH = re.compile(r"\b10\.\s*klasse", re.I)       # 10.-klasse centres are type 1012 too


def kommune_url(kommune: str) -> str:
    """DAWA's kommune name -> skolegang's list page (letters kept: `lyngby-taarbæk`)."""
    slug = "skoler-i-" + kommune.strip().lower().replace(" ", "-")
    return f"{SKOLEGANG}/kommune/{urllib.parse.quote(slug)}"


def school_url(slug: str) -> str:
    return f"{SKOLEGANG}/skole/{urllib.parse.quote(slug)}"


def _payload(html: str) -> str:
    """The Next.js flight payload: the pushed string chunks, JS-unescaped and joined."""
    out = []
    for chunk in _PUSH.findall(html):
        try:
            out.append(json.loads(f'"{chunk}"'))
        except ValueError:
            continue
    return "".join(out)


def parse_kommune_slugs(html: str) -> list[str]:
    """Every school slug in the kommune page's payload. The rendered page links only
    ten; the payload holds them all (Lyngby-Taarbæk: 12)."""
    return sorted(set(re.findall(r'"slug":"([^"]+)"', _payload(html))))


def _school_ld(html: str) -> dict | None:
    for block in _LD.findall(html):
        try:
            d = json.loads(block)
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("@type") == "School":
            return d
    return None


def _decode_at(text: str, key: str, opener: str):
    """Every JSON value that follows `"key":` and starts with `opener` ([ or {)."""
    out, dec = [], json.JSONDecoder()
    for m in re.finditer(re.escape(f'"{key}":{opener}'), text):
        try:
            out.append(dec.raw_decode(text, m.end() - 1)[0])
        except ValueError:
            continue
    return out


def _series(payload: str) -> tuple[dict, dict]:
    """(school series, national series), each {field: [[school_year, value], ...]}
    oldest first, nulls dropped. National only exists for the wellbeing indicators."""
    school: dict[str, list] = {}
    national: dict[str, list] = {}
    for rows in _decode_at(payload, "yearlyPerformance", "["):
        if rows and isinstance(rows[0], dict) and "elevtal" in rows[0]:
            for r in rows:
                for f, v in r.items():
                    if f not in ("schoolYear", "year") and isinstance(v, (int, float)):
                        school.setdefault(f, []).append([r["schoolYear"], v])
            break
    for wb in _decode_at(payload, "wellbeingPerformance", "{"):
        for name, ind in (wb.get("indicators") or {}).items():
            for r in ind.get("yearlyPerformance") or []:
                if r.get("indicatorScore") is not None:
                    school.setdefault(f"wb:{name}", []).append([r["schoolYear"], r["indicatorScore"]])
                if r.get("nationalAverage") is not None:
                    national.setdefault(f"wb:{name}", []).append([r["schoolYear"], r["nationalAverage"]])
        break
    return school, national


def parse_school(html: str, slug: str) -> dict | None:
    """One school page -> a `school` row (figures as a dict), or None when the page has
    no School JSON-LD. `folkeskole` says whether the register calls it one."""
    ld = _school_ld(html)
    if ld is None:
        return None
    props = {p.get("name"): p.get("value") for p in ld.get("additionalProperty") or []}
    name = ld.get("name") or slug
    geo = ld.get("geo") or {}
    street = (ld.get("address") or {}).get("streetAddress")
    for prefix in (name, name.split(",")[0]):     # "Fuglsanggårdsskolen Askevænget 10, ..."
        if street and street.startswith(prefix):  # "Bakkegårdsskolen, Gentofte" drops ", Gentofte"
            street = street[len(prefix):].strip()
            break
    payload = _payload(html)
    series, national = _series(payload)
    total = re.search(r'"totalSchools":(\d+)', payload)
    top = props.get("ÆldsteKlasseTrin")
    return {
        "inst_nr": str(props.get("InstitutionsNummer") or ""),
        "slug": slug,
        "name": name,
        "address": street,
        "lat": geo.get("latitude"),
        "lon": geo.get("longitude"),
        "top_grade": int(top) if str(top or "").isdigit() else None,
        "folkeskole": props.get("InstTypeNr") == FOLKESKOLE and not _TENTH.search(name),
        "figures": {
            "year": props.get("År"),
            "total_schools": int(total.group(1)) if total else None,
            "series": series,
            "national": national,
            "snapshot": {k: props[ld_key] for k, *_, ld_key, _ in FIGURES
                         if ld_key and isinstance(props.get(ld_key), (int, float))},
            "rank": {k: props[rank_key] for k, *_, rank_key in FIGURES
                     if rank_key and isinstance(props.get(rank_key), int)},
            "significance": _latest_text(payload, "socRefSignifikantForskel"),
        },
    }


def _latest_text(payload: str, field: str) -> str | None:
    found = re.findall(rf'"{field}":"([^"]*)"', payload)
    return found[-1] if found else None


def value_in(figures: dict, key: str, year: str) -> float | None:
    """The school's value of a figure in one school year: the series first, else the
    JSON-LD snapshot when that is the year it describes."""
    field = next(f[4] for f in FIGURES if f[0] == key)
    for y, v in figures.get("series", {}).get(field or "", []):
        if y == year:
            return v
    if year == figures.get("year"):
        return figures.get("snapshot", {}).get(key)
    return None


def latest(figures: dict, key: str) -> tuple[float | None, str | None]:
    """(value, school year) of the newest year that has the figure."""
    field = next(f[4] for f in FIGURES if f[0] == key)
    rows = figures.get("series", {}).get(field or "", [])
    if rows:
        year, value = max(rows, key=lambda r: r[0])
        return value, year
    v = figures.get("snapshot", {}).get(key)
    return (v, figures.get("year")) if v is not None else (None, None)


def figure_rows(figures: dict, kommune: list[dict]) -> list[dict]:
    """What the house page shows for one school: every figure with its year, the plain
    mean over the kommune's folkeskoler that have it that year, the national average
    (wellbeing only) and the national rank (only for the year the ranks describe)."""
    out = []
    for key, label, better, unit, field, _, _ in FIGURES:
        value, year = latest(figures, key)
        peers = [v for s in kommune if (v := value_in(s["figures"], key, year)) is not None] \
            if year else []
        nat = next((v for y, v in figures.get("national", {}).get(field or "", [])
                    if y == year), None)
        ranked = year is not None and year == figures.get("year")
        out.append({
            "key": key, "label": label, "better": better, "unit": unit,
            "value": value, "year": year,
            "kommune_avg": round(sum(peers) / len(peers), 2) if peers else None,
            "national_avg": nat,
            "national_rank": figures.get("rank", {}).get(key) if ranked else None,
            "total_schools": figures.get("total_schools"),
            "note": figures.get("significance") if key == "teaching_effect" else None,
        })
    return out
