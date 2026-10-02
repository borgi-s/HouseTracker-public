"""Builders for skolegang.dk-shaped pages, trimmed from the real ones (2026-09-26): a
schema.org School JSON-LD block and a Next.js flight chunk. Compact JSON like the site's
(`separators=(",", ":")`), because the payload parser matches `"key":[` with no space."""
import json


def ld(name, props, geo=(55.79309167, 12.47906506), street=None):
    d = {"@context": "https://schema.org", "@type": "School", "name": name,
         "additionalProperty": [{"@type": "PropertyValue", "name": k, "value": v}
                                for k, v in props.items()]}
    if geo:
        d["geo"] = {"@type": "GeoCoordinates", "latitude": geo[0], "longitude": geo[1]}
    if street:
        d["address"] = {"@type": "PostalAddress", "streetAddress": street}
    return f'<script type="application/ld+json">{json.dumps(d, ensure_ascii=False)}</script>'


def push(payload) -> str:
    """One `self.__next_f.push([1,"..."])` chunk carrying `payload` as flight text."""
    text = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    return f"<script>self.__next_f.push([1,{json.dumps(text, ensure_ascii=False)}])</script>"


def kommune_page(*slugs) -> str:
    # the rendered page links a few; the payload lists them all
    links = "".join(f'<a href="/skole/{s}">x</a>' for s in slugs[:1])
    return links + push({"schools": [{"slug": s, "name": s} for s in slugs]})


def school_page(inst, name, lat, lon, inst_type="1012", **props) -> str:
    return ld(name, {"InstitutionsNummer": inst, "InstTypeNr": inst_type,
                     "ÆldsteKlasseTrin": "9", "År": "2024/2025", **props},
              geo=(lat, lon), street=f"{name} Skolevej 1, 2800 Lyngby")


FUGL_PROPS = {
    "InstitutionsNummer": "173003", "InstTypeNr": "1012", "ÆldsteKlasseTrin": "9",
    "År": "2024/2025", "KarakterGns": 8.8, "KarakterGnsRang": 71,
    "UndervisningsEffekt": 0.5, "UndervisningsEffektRang": 115,
    "SocRefSocioøkonomiskReference": 8.3, "ElevFravær": 6.3, "ElevFraværRang": 337,
    "DanskHerkomst": 88.2, "DanskHerkomstRang": 1542,
}
FUGL_PAYLOAD = {"school": {
    "totalSchools": 2870,
    "wellbeingPerformance": {"indicators": {"Social trivsel": {"yearlyPerformance": [
        {"schoolYear": "2023/2024", "year": 2023, "indicatorScore": 4.1,
         "responseRate": "100,0 %", "nationalAverage": 3.9},
        {"schoolYear": "2024/2025", "year": 2024, "indicatorScore": 4.1,
         "responseRate": "100,0 %", "nationalAverage": 3.9}]}}},
    "yearlyPerformance": [
        {"schoolYear": "2023/2024", "year": 2023, "elevtal": 733, "karaktergennemsnit": 8.6,
         "samletElevfravær": 6.5, "socRefForskel": 0.4, "socRefSignifikantForskel": "På niveau"},
        {"schoolYear": "2024/2025", "year": 2024, "elevtal": 744, "karaktergennemsnit": 8.8,
         "samletElevfravær": 6.3, "socRefForskel": 0.5,
         "socRefSignifikantForskel": "Over niveau"}],
}}
FUGL = (ld("Fuglsanggårdsskolen", FUGL_PROPS,
           street="Fuglsanggårdsskolen Askevænget 10, 2830 Virum") + push(FUGL_PAYLOAD))
