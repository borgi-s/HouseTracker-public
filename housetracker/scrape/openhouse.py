"""Open houses ("åbent hus") read from a listing page. One extractor per chain family,
picked the way parse_for picks a parser; each returns only the listing's own slots
(never a "similar homes" tile's), as UTC times. Spec:
docs/specs/2026-09-30-open-houses-design.md (§2 says where each chain keeps them)."""
from __future__ import annotations

import html as _html
import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from housetracker.scrape.adapters import (
    _PLATFORMS, _json_array, _nuxt_state, _rsc_text, detect_chain,
)
from housetracker.scrape.parse import json_scripts

log = logging.getLogger(__name__)

CPH = ZoneInfo("Europe/Copenhagen")

_MONTHS = {m: i for i, m in enumerate(
    ("januar", "februar", "marts", "april", "maj", "juni", "juli", "august",
     "september", "oktober", "november", "december"), 1)}

# Houses whose Boligsiden open-house times are Danish wall-clock time stamped with Z
# (RealEquity sites; spec §2). Values of house.source_adapter.
WALL_CLOCK_ADAPTERS = ("fiskerliljengren", "boligone", "realequity")


def utc(dt: datetime) -> str:
    """The one text form every slot time is stored in; it sorts as time."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_now() -> str:
    return utc(datetime.now(timezone.utc))


def _aware(s) -> datetime | None:
    """ISO text -> aware datetime. A time without a zone is Danish wall-clock time."""
    try:
        dt = datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=CPH)


def _wall(s) -> datetime | None:
    """ISO text whose zone is wrong: Danish wall-clock time stamped with Z."""
    dt = _aware(s)
    return dt and dt.replace(tzinfo=CPH)


def slot(start: datetime | None, end: datetime | None, signup,
         signup_url: str | None = None) -> dict | None:
    if start is None or end is None or end <= start:
        return None
    return {"starts_at": utc(start), "ends_at": utc(end),
            "signup": None if signup is None else bool(signup), "signup_url": signup_url}


def _danbolig(html, url, today):
    """A single-quoted object in a Vue prop, repeated per component; the `…CET` fields
    carry the zone. Items of other homes carry another propertyId."""
    pid = re.search(r"/(\d+)-\d+(?:/|[?#]|$)", url)
    if pid is None:                   # cannot tell this listing's items from other homes'
        return []
    out = []
    for block in re.finditer(r"'openHouses': \[(.*?)\]", html, re.S):
        for item in re.findall(r"\{[^{}]*\}", block.group(1)):
            get = lambda k: (m := re.search(rf"'{k}': '([^']*)'", item)) and m.group(1)
            if get("propertyId") != pid.group(1):
                continue
            signup = re.search(r"'signupRequired': (true|false)", item)
            out.append(slot(_aware(get("openHouseFromCET")), _aware(get("openHouseToCET")),
                            signup and signup.group(1) == "true"))
    return out


def _edc(html, url, today):
    """The case JSON: `upcomingOpenHouses` in Danish time; one sign-up flag per case."""
    case = next((d for d in json_scripts(html, "application/json")
                 if isinstance(d, dict) and "upcomingOpenHouses" in d), None)
    if case is None:
        return []
    signup = case.get("openHouseActivitySubscription")
    return [slot(_aware(o.get("dateFrom")), _aware(o.get("dateTo")), signup)
            for o in case["upcomingOpenHouses"] or [] if isinstance(o, dict)]


_DK_DATE = re.compile(r"(\d{1,2})\.\s*([a-zæøå]+)", re.I)
_DK_TIME = re.compile(r"(\d{1,2})[.:](\d{2})\s*-\s*(\d{1,2})[.:](\d{2})")


def _on(day: int, month: int, today: date) -> date:
    """A day and month with no year: this year's, unless that is over a month ago."""
    d = date(today.year, month, day)
    return d if d >= today - timedelta(days=31) else date(today.year + 1, month, day)


def _dk_slot(date_text: str, time_text: str, signup: bool, today: date) -> dict | None:
    dm, tm = _DK_DATE.search(date_text), _DK_TIME.search(time_text)
    month = dm and _MONTHS.get(dm.group(2).lower())
    if not (month and tm):
        return None
    try:
        d = _on(int(dm.group(1)), month, today)
    except ValueError:                        # "31. juni"
        return None
    h1, m1, h2, m2 = map(int, tm.groups())
    at = lambda h, m: datetime(d.year, d.month, d.day, h, m, tzinfo=CPH)
    return slot(at(h1, m1), at(h2, m2), signup)


def _mindworking(html, url, today):
    """Estate / Nybolig: the hero's desktop open-house list. Either one radio item per
    slot (with a "Tilmeld" link when sign-up is needed) or one line of text starting
    "Tilmeld åbent hus" or "Åbent hus". Similar-homes tiles use other markup."""
    from bs4 import BeautifulSoup  # lazy: scrape extra
    box = BeautifulSoup(html, "html.parser").select_one(".openhouse-list--desktop")
    if box is None:
        return []
    text = lambda el, css: (f := el.select_one(css)) and f.get_text(" ", strip=True) or ""
    items = box.select(".openhouse-list__item")
    if items:
        return [_dk_slot(text(it, ".openhouse-list__item__info__date"),
                         text(it, ".openhouse-list__item__info__time"),
                         it.select_one(".openhouse-list__item__signuplink") is not None, today)
                for it in items]
    lines = [el.get_text(" ", strip=True) for el in box.select(".openhouse-list__text")]
    return [_dk_slot(t, t, t.lower().startswith("tilmeld"), today) for t in lines]

def _home(html, url, today):
    """The Nuxt case's `openHouses`, in UTC."""
    data = (_nuxt_state(html) or {}).get("data") or {}
    case = next((v for k, v in data.items() if k.startswith("case-") and isinstance(v, dict)), {})
    return [slot(_aware(o.get("startDate")), _aware(o.get("endDate")), o.get("isRegistrationRequired"))
            for o in case.get("openHouses") or [] if isinstance(o, dict)]


def _lokalbolig(html, url, today):
    """The case's `openHouse` array in the RSC payload, with zone offsets."""
    return [slot(_aware(o.get("start")), _aware(o.get("end")), o.get("needsRegistration"))
            for o in _json_array(_rsc_text(html), "openHouse") if isinstance(o, dict)]


def _realequity(html, url, today):
    """The case's `openhouses` in the RSC payload. Their times end in Z but are Danish
    wall-clock time (F&L prints 10.10 for "10:10:00.000Z"); Boligsiden copies the error."""
    return [slot(_wall(o.get("startDate")), _wall(o.get("endDate")), o.get("bookingRequired"))
            for o in _json_array(_rsc_text(html), "openhouses") if isinstance(o, dict)]


def _realmaeglerne(html, url, today):
    """One JSON data attribute per slot, printed twice (desktop and phone)."""
    out = []
    for raw in re.findall(r'data-aabent-hus="([^"]+)"', html):
        try:
            o = json.loads(_html.unescape(raw))
        except json.JSONDecodeError:
            continue
        day = str(o.get("Dato") or "")[:10]
        out.append(slot(_aware(f"{day}T{o.get('FraKlokken')}"),
                        _aware(f"{day}T{o.get('TilKlokken')}"), o.get("Tilmelding")))
    return out

def _events(html, url, today):
    """schema.org Events named "Åbent hus…" in the JSON-LD (John Frandsen, and any
    site that publishes them). "…med tilmelding" means sign-up."""
    found = []

    def walk(x):
        if isinstance(x, dict):
            name = str(x.get("name") or "").lower()
            if x.get("@type") == "Event" and "åbent" in name:
                found.append(slot(_aware(x.get("startDate")), _aware(x.get("endDate")),
                                  "tilmelding" in name))
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    for block in json_scripts(html, "application/ld+json"):
        walk(block)
    return found


# Chain (or platform) -> extractor; anything else reads JSON-LD Events.
_EXTRACTORS = {"danbolig": _danbolig, "edc": _edc, "estate": _mindworking,
               "nybolig": _mindworking, "mindworking": _mindworking, "home": _home,
               "lokalbolig": _lokalbolig, "fiskerliljengren": _realequity,
               "boligone": _realequity, "realequity": _realequity,
               "realmaeglerne": _realmaeglerne, "johnfrandsen": _events}


def open_houses(url: str, html: str, today: date | None = None) -> list[dict]:
    """The listing's own open houses, soonest first, one per start time:
    {starts_at, ends_at (UTC 'YYYY-MM-DDTHH:MM:SSZ'), signup (bool | None), signup_url}.
    `today` dates the Danish text dates that carry no year. Best-effort: a page its
    extractor cannot read gives []."""
    chain = detect_chain(url)
    key = chain if chain in _EXTRACTORS else next(
        (n for mark, n, _ in _PLATFORMS if mark in html), chain)
    try:
        slots = _EXTRACTORS.get(key, _events)(html, url, today or datetime.now(CPH).date())
    except Exception as e:
        log.warning("open-house read failed for %s: %s", url, type(e).__name__)
        return []
    first: dict = {}
    for s in slots:
        if s:
            first.setdefault(s["starts_at"], s)
    return [first[k] for k in sorted(first)]


def boligsiden_slot(raw, wall_clock: bool = False) -> dict | None:
    """Boligsiden's `nextOpenHouse` {date, duration (min), signUp, signUpUrl} as a slot.
    `wall_clock`: its Z is really Danish time (RealEquity houses, spec §2)."""
    if not isinstance(raw, dict):
        return None
    start = (_wall if wall_clock else _aware)(raw.get("date"))
    minutes = raw.get("duration")
    if start is None or not isinstance(minutes, (int, float)):
        return None
    return slot(start, start + timedelta(minutes=minutes), raw.get("signUp"), raw.get("signUpUrl"))


def record_page(store, house_id: str, url: str, html: str) -> int:
    """Open houses on a listing page just fetched to add or refresh a house (spec D2):
    recorded as seen, so the sweep never pings them as new. A page showing none
    changes nothing, and so does one showing only slots already over. Returns how many
    upcoming slots the page showed."""
    at = utc_now()
    slots = [s for s in open_houses(url, html) if s["ends_at"] > at]
    if slots:
        store.sync_open_houses(house_id, slots, "agency", at)
    return len(slots)
