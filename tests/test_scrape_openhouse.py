"""Open houses read from listing pages. Markup is trimmed from live listings
(2026-09-30); times are asserted in UTC (Danish summer time = UTC+2)."""
import json
import logging
from datetime import date, datetime

import housetracker.scrape.openhouse as oh
from housetracker.scrape.openhouse import _aware, open_houses, slot, utc

TODAY = date(2026, 9, 30)


def when(slots):
    """(start, end, signup): the shape every assertion reads."""
    return [(s["starts_at"], s["ends_at"], s["signup"]) for s in slots]


def _nuxt(tree) -> str:
    """Serialize like Nuxt 3's devalue (copy of the helper in test_scrape_adapters.py)."""
    flat: list = [None]
    def put(v):
        flat.append(None)
        i = len(flat) - 1
        flat[i] = ({k: put(x) for k, x in v.items()} if isinstance(v, dict)
                   else [put(x) for x in v] if isinstance(v, list) else v)
        return i
    flat[0] = ["ShallowReactive", put(tree)]
    return f'<script type="application/json" id="__NUXT_DATA__">{json.dumps(flat)}</script>'


def _rsc(case: dict) -> str:
    """A Next.js RSC push carrying the case as compact JSON, like the live pages."""
    return f'<script>self.__next_f.push([1,{json.dumps("6:" + json.dumps(case, separators=(",", ":")))}])</script>'


# ---- time helpers -------------------------------------------------------------------

def test_a_time_without_a_zone_is_danish_time():
    assert utc(_aware("2026-10-04T13:00:00")) == "2026-10-04T11:00:00Z"            # summer
    assert utc(_aware("2026-11-01T13:00:00")) == "2026-11-01T12:00:00Z"            # winter
    assert utc(_aware("2026-10-02T10:00:00.0000000")) == "2026-10-02T08:00:00Z"    # EDC's 7 digits
    assert utc(_aware("2026-10-04T11:30:00+02:00")) == "2026-10-04T09:30:00Z"
    assert utc(_aware("2026-10-04T10:00:00Z")) == "2026-10-04T10:00:00Z"
    assert _aware("04-10-2026") is None and _aware(None) is None


def test_a_slot_needs_an_end_after_its_start():
    a, b = datetime(2026, 10, 4, 10), datetime(2026, 10, 4, 11)
    a, b = _aware(a.isoformat()), _aware(b.isoformat())
    assert slot(a, b, True) == {"starts_at": "2026-10-04T08:00:00Z", "ends_at": "2026-10-04T09:00:00Z",
                                "signup": True, "signup_url": None}
    assert slot(a, a, True) is None and slot(b, a, True) is None and slot(None, b, None) is None
    assert slot(a, b, None)["signup"] is None


# ---- John Frandsen + any site with JSON-LD Events -------------------------------------

JF_URL = "https://www.johnfrandsen.dk/sag/35610001199/dokkedalvej-89-mou-9280-storvorde/"


def test_john_frandsen_reads_its_json_ld_event():
    graph = {"@context": "https://schema.org", "@graph": [
        {"@type": "BreadcrumbList", "itemListElement": []},
        {"@type": "Event", "@id": JF_URL + "#openhouse-20261010100000",
         "name": "Åbent hus med tilmelding: Dokkedalvej 89, Mou, 9280 Storvorde",
         "startDate": "2026-10-10T10:00:00+02:00", "endDate": "2026-10-10T16:00:00+02:00",
         "eventStatus": "https://schema.org/EventScheduled"}]}
    html = f'<script type="application/ld+json">{json.dumps(graph)}</script>'
    assert when(open_houses(JF_URL, html, TODAY)) == [
        ("2026-10-10T08:00:00Z", "2026-10-10T14:00:00Z", True)]


def test_an_unknown_agent_gets_its_json_ld_events_and_date_only_ones_are_skipped():
    events = [{"@type": "Event", "name": "Åbent hus", "startDate": "2026-10-11T12:00:00+02:00",
               "endDate": "2026-10-11T12:30:00+02:00"},
              {"@type": "Event", "name": "Åbenthus", "startDate": "04-10-2026", "endDate": "04-10-2026"},
              {"@type": "Event", "name": "Koncert", "startDate": "2026-10-05T20:00:00+02:00",
               "endDate": "2026-10-05T22:00:00+02:00"}]
    html = f'<script type="application/ld+json">{json.dumps(events)}</script>'
    assert when(open_houses("https://www.some-maegler.dk/bolig/1", html, TODAY)) == [
        ("2026-10-11T10:00:00Z", "2026-10-11T10:30:00Z", False)]


# ---- danbolig -----------------------------------------------------------------------

DB_URL = "https://danbolig.dk/bolig/hvidovre/2650/villa/0040001289-004/"


def _danbolig_prop(pid: str, start: str, end: str, signup: str) -> str:
    """The `:property` Vue prop as danbolig prints it (single quotes, one key per line)."""
    return ("<o-property-hero :property=\"{\n  'openHouses': [\n    {\n"
            "      'brokerId': '004',\n"
            f"      'propertyId': '{pid}',\n"
            "      'openHouseFrom': '2026-10-04T09:30:00',\n"
            "      'remark': null,\n"
            f"      'signupRequired': {signup},\n"
            "      'registrationDeadline': null,\n"
            f"      'openHouseFromCET': '{start}',\n"
            f"      'openHouseToCET': '{end}'\n"
            "    }\n  ],\n  'fallbackImageUrl': null\n}\"></o-property-hero>")


def test_danbolig_keeps_only_this_listings_slots():
    own = _danbolig_prop("0040001289", "2026-10-04T11:30:00+02:00", "2026-10-04T11:50:00+02:00", "true")
    other = _danbolig_prop("1170000936", "2026-10-04T13:40:00+02:00", "2026-10-04T14:00:00+02:00", "false")
    html = own + own + other + own          # the page repeats the prop per component
    assert when(open_houses(DB_URL, html, TODAY)) == [
        ("2026-10-04T09:30:00Z", "2026-10-04T09:50:00Z", True)]


def test_danbolig_with_no_open_house():
    assert open_houses(DB_URL, "<o-x :property=\"{\n  'openHouses': [],\n}\"></o-x>", TODAY) == []


# ---- EDC ----------------------------------------------------------------------------

EDC_URL = "https://www.edc.dk/alle-boliger/villa/2850-naerum/rosevej-12c/29106271/"


def _edc_case(**extra) -> str:
    case = {"caseNumber": "29106271", "bluePrints": [], "showOpenHouseSignupCta": True,
            "openHouseFormId": "2552", **extra}
    return ('<script type="application/json">{"logoLink": {}}</script>'
            f'<script type="application/json">{json.dumps(case)}</script>')


def test_edc_reads_every_upcoming_slot_in_danish_time():
    html = _edc_case(openHouseActivitySubscription=True, upcomingOpenHouses=[
        {"dateFrom": "2026-10-11T13:00:00.0000000", "dateTo": "2026-10-11T17:00:00.0000000"},
        {"dateFrom": "2026-10-04T13:00:00.0000000", "dateTo": "2026-10-04T17:00:00.0000000"}])
    assert when(open_houses(EDC_URL, html, TODAY)) == [
        ("2026-10-04T11:00:00Z", "2026-10-04T15:00:00Z", True),
        ("2026-10-11T11:00:00Z", "2026-10-11T15:00:00Z", True)]


def test_edc_sold_or_without_open_house():
    assert open_houses(EDC_URL, _edc_case(openHouseActivitySubscription=False,
                                          upcomingOpenHouses=[]), TODAY) == []
    assert open_houses(EDC_URL, _edc_case(), TODAY) == []


# ---- home ---------------------------------------------------------------------------

HOME_URL = "https://home.dk/salg/lejligheder/gertrude-steins-vej-5-5tv-2300-koebenhavn-s/sag-1770020991/"


def test_home_reads_the_nuxt_case():
    html = _nuxt({"data": {"case-1770020991": {"hasOpenHousesThisWeek": True, "openHouses": [
        {"id": "SUFwcG9pbnRtZW50QWN0aXZpdHk6MzM5MDYzODc", "startDate": "2026-10-04T10:00:00Z",
         "endDate": "2026-10-04T11:00:00Z", "isRegistrationRequired": False},
        {"id": "SUFwcG9pbnRtZW50QWN0aXZpdHk6MzM5MDYzODg", "startDate": "2026-10-11T10:00:00Z",
         "endDate": "2026-10-11T11:00:00Z", "isRegistrationRequired": True}]}}})
    assert when(open_houses(HOME_URL, html, TODAY)) == [
        ("2026-10-04T10:00:00Z", "2026-10-04T11:00:00Z", False),
        ("2026-10-11T10:00:00Z", "2026-10-11T11:00:00Z", True)]


def test_home_related_homes_text_is_not_ours():
    html = _nuxt({"data": {"case-1490002553": {"openHouses": []}}}) + (
        "<div>Relaterede boliger til salg og leje Åbent hus Søndag 04.10, kl. 17.00-17.15</div>")
    assert open_houses(HOME_URL, html, TODAY) == []


# ---- LokalBolig ---------------------------------------------------------------------

def test_lokalbolig_reads_the_rsc_case():
    html = _rsc({"openHouse": [{"id": "SUFwcG9pbnRtZW50QWN0aXZpdHk6NDM4MjMxMQ", "needsRegistration": True,
                                "start": "2026-10-11T16:00:00+02:00", "end": "2026-10-11T17:00:00+02:00"}],
                 "areaHeading": None})
    url = "https://www.lokalbolig.dk/bolig/boliglandbrug/gistrup/9260/bakkevej-130/54-X0000640"
    assert when(open_houses(url, html, TODAY)) == [
        ("2026-10-11T14:00:00Z", "2026-10-11T15:00:00Z", True)]


# ---- dispatch -----------------------------------------------------------------------

def test_a_failing_extractor_gives_nothing_and_is_logged(monkeypatch, caplog):
    def boom(html, url, today):
        raise KeyError("x")
    monkeypatch.setitem(oh._EXTRACTORS, "edc", boom)
    with caplog.at_level(logging.WARNING):
        assert open_houses(EDC_URL, "<html></html>", TODAY) == []
    assert "open-house read failed for" in caplog.text and "KeyError" in caplog.text


import html as _html

from housetracker.scrape.openhouse import boligsiden_slot

# ---- Estate / Nybolig (Mindworking) ---------------------------------------------------

ESTATE_URL = "https://www.estate.dk/raekkehus/2820/egelundsvej/n435120/n4351200000489"
NYBOLIG_URL = "https://www.nybolig.dk/raekkehus/2830/birkevang/n593380/n5933800000409"


def _estate_item(i: int, date_text: str, time_text: str, signup: bool, where: str = "desktop") -> str:
    link = ('<a class="openhouse-list__item__signuplink" data-js-useroverlay-opener="" '
            'data-js-useroverlay-type="signUpOpenHouse" title="Tilmeld"> <span>Tilmeld</span> </a>'
            if signup else "")
    return (f'<div class="openhouse-list__item openhouse-list__item--openhouse-{where}-{i}"> '
            f'<input class="openhouse-list__item__input" name="splashOpenhouse-{where}" '
            f'id="openhouse-{where}-{i}" type="radio" /> '
            f'<label class="openhouse-list__item__info" for="openhouse-{where}-{i}"> '
            '<span class="openhouse-list__item__info__day">S&#248;ndag</span> '
            f'<span class="openhouse-list__item__info__date">{date_text}</span> '
            f'<span class="openhouse-list__item__info__time">{time_text}</span> {link}</label> </div>')


# A "similar homes" tile further down an Estate page (other markup, other house).
SIMILAR = ('<div class="case-tile"><span>Tilmeld åbent hus søndag 04. oktober kl. 13.15 - 13.45</span>'
           '<span>Christian IVs Vej 1, 2., 3400 Hillerød</span></div>')


def test_mindworking_reads_the_hero_list_with_a_sign_up_link_per_slot():
    # The first item is real (Egelundsvej 61); the second shows the multi-slot form.
    desktop = ('<form class="openhouse-list openhouse-list--desktop"> '
               + _estate_item(0, "04. oktober", "15:30 - 15:50", True)
               + _estate_item(1, "11. oktober", "10:35 - 10:55", False) + '</form>')
    mobile = ('<form class="openhouse-list openhouse-list--mobile"> '
              + _estate_item(0, "04. oktober", "15:30 - 15:50", True, "mobile") + '</form>')
    html = f'<div class="openhouse-list-container">{desktop}{mobile}</div>{SIMILAR}'
    assert when(open_houses(ESTATE_URL, html, TODAY)) == [
        ("2026-10-04T13:30:00Z", "2026-10-04T13:50:00Z", True),
        ("2026-10-11T08:35:00Z", "2026-10-11T08:55:00Z", False)]


def test_mindworking_reads_the_one_line_text_form():
    line = lambda text: ('<div class="openhouse-list-container" data-js-initialize="vt.initOpenHouseSlider"> '
                         '<div class="openhouse-list openhouse-list--desktop"> '
                         f'<div class="openhouse-list__text">{text}</div> </div> </div>')
    drop_in = line('&#197;bent hus <span class="font-normal">s&#248;ndag 04. oktober kl. 12.30 - 13.00</span>')
    sign_up = line('Tilmeld &#229;bent hus <span class="font-normal">s&#248;ndag 04. oktober kl. 8.30 - 16.30</span>')
    assert when(open_houses(NYBOLIG_URL, drop_in, TODAY)) == [
        ("2026-10-04T10:30:00Z", "2026-10-04T11:00:00Z", False)]
    assert when(open_houses(NYBOLIG_URL, sign_up, TODAY)) == [
        ("2026-10-04T06:30:00Z", "2026-10-04T14:30:00Z", True)]


def test_mindworking_ignores_similar_homes_tiles():
    assert open_houses(ESTATE_URL, f"<main>{SIMILAR}</main>", TODAY) == []


def test_mindworking_dates_without_a_year_roll_into_next_year():
    html = ('<div class="openhouse-list openhouse-list--desktop"> '
            + _estate_item(0, "04. januar", "11:00 - 11:30", False) + '</div>')
    assert when(open_houses(ESTATE_URL, html, date(2026, 12, 20))) == [
        ("2027-01-04T10:00:00Z", "2027-01-04T10:30:00Z", False)]
    html = ('<div class="openhouse-list openhouse-list--desktop"> '
            + _estate_item(0, "18. december", "11:00 - 11:30", False) + '</div>')
    assert when(open_houses(ESTATE_URL, html, date(2026, 12, 20)))[0][0] == "2026-12-18T10:00:00Z"


def test_mindworking_skips_an_unreadable_slot():
    html = ('<div class="openhouse-list openhouse-list--desktop"> '
            + _estate_item(0, "31. juni", "11:00 - 11:30", False)
            + _estate_item(1, "4. oktober", "", False) + '</div>')
    assert open_houses(ESTATE_URL, html, TODAY) == []


# ---- RealEquity (F&L, Boligone, fingerprinted sites) -------------------------------

def _re_case(start: str, end: str, booking: bool) -> str:
    return _rsc({"isSold": False, "hasUpcomingOpenhouse": True, "openhouses": [
        {"appointmentId": "71e078c1-05a2-433c-b029-c3eab412497b",
         "namespace": "dk.realequity.appointment.openhouse", "displayName": "ÅH", "title": "ÅH",
         "description": "", "location": "Åbakken 245, 2830 Virum", "startDate": start,
         "endDate": end, "isAllDay": False, "bookingRequired": booking}]})


def test_realequity_times_are_danish_despite_their_z():
    # The F&L page prints "Åbent hus - Søndag 4. oktober 10.10 - 10.30" for these.
    html = _re_case("2026-10-04T10:10:00.000Z", "2026-10-04T10:30:00.000Z", False)
    url = "https://fiskerliljengren.dk/ejendom/aabakken-245--2830-virum____8ba269ff"
    assert when(open_houses(url, html, TODAY)) == [
        ("2026-10-04T08:10:00Z", "2026-10-04T08:30:00Z", False)]
    boligone = _re_case("2026-10-11T13:00:00.000Z", "2026-10-11T13:45:00.000Z", True)
    assert when(open_houses("https://boligone.dk/ejendom/egetoften-3", boligone, TODAY)) == [
        ("2026-10-11T11:00:00Z", "2026-10-11T11:45:00Z", True)]


def test_an_unknown_realequity_site_is_found_by_its_fingerprint():
    html = _re_case("2026-10-04T11:45:00.000Z", "2026-10-04T12:05:00.000Z", False) + (
        '<script>"namespace":"dk.realequity.mediaitem.image.photo"</script>')
    assert when(open_houses("https://www.some-realequity-agent.dk/ejendom/x", html, TODAY)) == [
        ("2026-10-04T09:45:00Z", "2026-10-04T10:05:00Z", False)]


# ---- RealMæglerne ---------------------------------------------------------------------

def test_realmaeglerne_reads_the_data_attribute_once():
    data = {"Dato": "2026-10-04T00:00:00", "FraKlokken": "13:45:00", "TilKlokken": "14:00:00",
            "DatoFormateret": "d. 4/10", "Dag": "søndag", "Tidspunkt": "kl. 13:45 - 14:00",
            "VisInterval": False, "Id": "d4c24e75-8fdf-47ad-9653-c0fbdde1eeb1", "Tilmelding": True}
    attr = _html.escape(json.dumps(data))
    el = f'<div class="d-inline-block js-aabenthus-time-val js-primary-open-house" data-aabent-hus="{attr}"></div>'
    html = el + el + '<div data-aabent-hus="{not json"></div>'      # desktop + phone copy, and junk
    assert when(open_houses("https://www.realmaeglerne.dk/bolig/103-8453-dunkerquegade-23-2-th",
                            html, TODAY)) == [("2026-10-04T11:45:00Z", "2026-10-04T12:00:00Z", True)]


# ---- Boligsiden's nextOpenHouse -------------------------------------------------------

def test_boligsiden_slot():
    raw = {"date": "2026-10-04T13:30:00Z", "duration": 20, "signUp": True,
           "signUpUrl": "https://www.estate.dk/services/redirect/case/N435120/N4351200000489"}
    assert boligsiden_slot(raw) == {
        "starts_at": "2026-10-04T13:30:00Z", "ends_at": "2026-10-04T13:50:00Z", "signup": True,
        "signup_url": "https://www.estate.dk/services/redirect/case/N435120/N4351200000489"}
    fl = {"date": "2026-10-04T10:10:00Z", "duration": 20, "signUp": False}
    assert boligsiden_slot(fl, wall_clock=True)["starts_at"] == "2026-10-04T08:10:00Z"
    assert boligsiden_slot(None) is None
    assert boligsiden_slot({"date": "2026-10-04T10:10:00Z"}) is None          # no duration
    assert boligsiden_slot({"date": "2026-10-04T10:10:00Z", "duration": 0}) is None


from housetracker.lifecycle.lifecycle import run_lifecycle
from housetracker.scrape.openhouse import record_page
from housetracker.store import HouseStore

FUTURE = [{"@type": "Event", "name": "Åbent hus", "startDate": "2099-10-04T15:30:00+02:00",
           "endDate": "2099-10-04T15:50:00+02:00"}]
FUTURE_PAGE = f'<script type="application/ld+json">{json.dumps(FUTURE)}</script><p>Til salg</p>'


def test_record_page_keeps_the_slots_and_an_empty_page_changes_nothing(tmp_path):
    s = HouseStore(tmp_path / "ht.db")
    hid = s.add_house({"address": "Nyvej 2"}, now="2026-09-30").id
    assert record_page(s, hid, "https://x.dk/1", FUTURE_PAGE) == 1
    assert record_page(s, hid, "https://x.dk/1", "<p>nothing</p>") == 0
    assert [(r["starts_at"], r["cancelled"]) for r in s.list_open_houses(hid)] == [
        ("2099-10-04T13:30:00Z", False)]


def test_a_slot_seen_at_add_never_pings_later(tmp_path):
    s = HouseStore(tmp_path / "ht.db")
    hid = s.add_house({"address": "Nyvej 2", "listing_url": "https://x.dk/1"}, now="2026-09-30").id
    record_page(s, hid, "https://x.dk/1", FUTURE_PAGE)
    s.set_status(hid, "shortlist", now="2026-09-30")

    class Prober:
        def probe(self, url):
            return (200, url, FUTURE_PAGE)
    pings = []
    summary = run_lifecycle(s, Prober(), None, now="2026-09-30",
                            notify_open=lambda h, new: pings.append(new))
    assert pings == [] and summary["open_new"] == 0


def test_record_page_with_only_a_past_slot_changes_nothing(tmp_path):
    s = HouseStore(tmp_path / "ht.db")
    hid = s.add_house({"address": "Nyvej 2"}, now="2026-09-30").id
    record_page(s, hid, "https://x.dk/1", FUTURE_PAGE)
    past = FUTURE_PAGE.replace("2099-10-04", "2000-10-01")
    assert record_page(s, hid, "https://x.dk/1", past) == 0
    assert [r["cancelled"] for r in s.list_open_houses(hid)] == [False]


def test_danbolig_url_shapes():
    own = _danbolig_prop("0040001289", "2026-10-04T11:30:00+02:00", "2026-10-04T11:50:00+02:00", "true")
    other = _danbolig_prop("1170000936", "2026-10-04T13:40:00+02:00", "2026-10-04T14:00:00+02:00", "false")
    assert len(open_houses(DB_URL + "foto", own + other, TODAY)) == 1       # a sub-page still finds its id
    assert open_houses("https://danbolig.dk/bolig/hvidovre/2650/villa/", own + other, TODAY) == []
