"""LLM auto-adapter core (pure logic, no LLM/network): the completeness gate, the
selector-config validator, the bs4 config-applier, and the reuse/escalate/confirm/
persist orchestration. A synthesized config is DATA, validated before trust and
handed to bs4 only as CSS selector strings — nothing is ever executed."""
from __future__ import annotations

import json
from urllib.parse import urljoin, urlparse

from housetracker.model import ValidationError
from housetracker.scrape.adapters import parse_for
from housetracker.scrape.parse import (
    MediaRef, ScrapeResult, _completeness, _dedup, _num, _parse_dkk,
)

GATE_MIN_PHOTOS = 3  # ponytail: constant; make it a criterion/env knob if it ever varies per chain


def host_key(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def gate_check(result: ScrapeResult, min_photos: int = GATE_MIN_PHOTOS
               ) -> tuple[bool, list[str]]:
    """The spec §8.3 gate: address + price + floorplan + PDF + >= N photos +
    description. Returns (passed, missing-item names)."""
    house, media = result.house, result.media
    missing: list[str] = []
    if not house.get("address"):
        missing.append("address")
    if house.get("price_dkk") is None:
        missing.append("price")
    if not any(m.kind == "floorplan" for m in media):
        missing.append("floorplan")
    if not any(m.kind == "pdf" for m in media):
        missing.append("pdf")
    if sum(1 for m in media if m.kind == "photo") < min_photos:
        missing.append(f"photos>={min_photos}")
    if not house.get("description"):
        missing.append("description")
    return (not missing, missing)


_ATTR_ALLOW = {"text", "html", "src", "href", "content"}
_FIELD_ALLOW = {"address", "postal_code", "city", "lat", "lon", "price_dkk",
                "ejerudgift_dkk", "size_m2", "lot_m2", "rooms", "build_year",
                "energy_label", "description"}
_MEDIA_ALLOW = {"photo", "floorplan", "pdf"}


def validate_config(raw) -> dict:
    """Reduce a model-produced config to a trusted allowlisted shape. Selectors stay
    opaque strings (applied only via bs4 .select); unknown keys/attrs are rejected,
    not silently kept. Raises ValidationError on anything off-shape."""
    if not isinstance(raw, dict):
        raise ValidationError("config must be a JSON object")
    out: dict = {"fields": {}, "media": {}}
    for section, allow in (("fields", _FIELD_ALLOW), ("media", _MEDIA_ALLOW)):
        block = raw.get(section, {})
        if not isinstance(block, dict):
            raise ValidationError(f"{section} must be an object")
        for key, spec in block.items():
            if key not in allow:
                raise ValidationError(f"unknown {section} key {key!r}")
            if not isinstance(spec, dict):
                raise ValidationError(f"{section}.{key} must be an object")
            selector, attr = spec.get("selector"), spec.get("attr")
            if not isinstance(selector, str) or not selector.strip():
                raise ValidationError(
                    f"{section}.{key}.selector must be a non-empty string")
            if attr not in _ATTR_ALLOW:
                raise ValidationError(
                    f"{section}.{key}.attr must be one of {sorted(_ATTR_ALLOW)}")
            out[section][key] = {"selector": selector, "attr": attr}
    if not out["fields"] and not out["media"]:
        raise ValidationError("config selects nothing")
    return out


_NUM_FIELDS = {"lat", "lon", "size_m2", "lot_m2", "rooms", "build_year"}


def _extract(el, attr: str):
    if attr == "text":
        return el.get_text(strip=True)
    if attr == "html":
        return str(el)
    return el.get(attr)  # src / href / content


def apply_config(html: str, url: str, cfg: dict) -> ScrapeResult:
    """Apply a validated selector config to the DOM. bs4 uses the stdlib html.parser
    backend (no lxml). Selectors are treated purely as CSS strings — never executed."""
    from bs4 import BeautifulSoup  # lazy: scrape extra
    soup = BeautifulSoup(html, "html.parser")
    house: dict = {"listing_url": url, "source_adapter": "llm",
                   "maegler_chain": host_key(url)}
    for name, spec in cfg.get("fields", {}).items():
        el = soup.select_one(spec["selector"])
        if el is None:
            continue
        raw = _extract(el, spec["attr"])
        if raw is None:
            continue
        if name == "price_dkk":
            house[name] = _parse_dkk(raw)
        elif name in _NUM_FIELDS:
            house[name] = _num(raw)
        else:
            house[name] = raw.strip() if isinstance(raw, str) else raw
    media: list = []
    for kind, spec in cfg.get("media", {}).items():
        for el in soup.select(spec["selector"]):
            u = _extract(el, spec["attr"])
            if u:
                media.append(MediaRef(kind=kind, url=urljoin(url, u)))
    house["scrape_completeness"] = _completeness(house, media)
    house = {k: v for k, v in house.items() if v is not None}
    return ScrapeResult(house=house, media=_dedup(media))


def resolve(url, html, store, synth, now, confirm=None) -> ScrapeResult:
    """Parse `url` to the best possible ScrapeResult, escalating to LLM synthesis only
    when the generic parse fails the completeness gate for a host with no confirmed
    saved config. Always returns an addable result (M2 guarantee)."""
    host = host_key(url)
    cfg = store.get_adapter_config(host)

    if cfg is not None and cfg.confirmed:
        result = apply_config(html, url, cfg.selectors())
        ok, _missing = gate_check(result)
        if ok:
            return result
        # Saved config went stale (site redesign) -> fall through to re-synthesize.
    else:
        result = parse_for(url, html)
        ok, _missing = gate_check(result)
        if ok:
            return result  # generic / per-chain adapter sufficed; no LLM

    if synth is None:
        return result  # best-effort, ungated, but addable

    try:
        raw = synth.synthesize(url, html, result)
        clean = validate_config(raw)             # "validated before trust"
        synth_result = apply_config(html, url, clean)
    except Exception:
        # ponytail: a flaky/absent/timed-out synthesizer, or an invalid config, must
        # never make a URL un-addable (M2 guarantee). Fall back to the best-effort
        # generic/stale result. Upgrade path: log the failure for later triage.
        return result
    ok2, missing2 = gate_check(synth_result)
    store.upsert_adapter_config(
        host, json.dumps(clean),
        completeness_last=synth_result.house.get("scrape_completeness"),
        source="llm", confirmed=False, now=now)
    if ok2 and (confirm is None or confirm(synth_result, missing2)):
        store.confirm_adapter_config(host, now)
    return synth_result if ok2 else result
