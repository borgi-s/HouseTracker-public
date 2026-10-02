# housetracker/lifecycle/lifecycle.py
"""The daily lifecycle sweep, per house:
1. re-probe the agency listing and flip gone/sold ones (sold-detection);
2. read today's asking price (Boligsiden, else the agency page just fetched) and log
   real changes; a drop pings Discord through `notify`;
3. fill the realized price for sold houses from Boligsiden's tinglyst sales;
4. read the house's open houses (the agency page, else Boligsiden's next slot), record
   them, and ping Discord through `notify_open` for new ones on shortlist/offer houses.
Best-effort: a None or failing backend degrades to 'did less', never to a crash."""
from __future__ import annotations

import logging
from datetime import date

from housetracker.lifecycle.boligsiden import parse_address
from housetracker.lifecycle.sold import probe_listing
from housetracker.scrape.adapters import parse_for
from housetracker.scrape.openhouse import (
    WALL_CLOCK_ADAPTERS, boligsiden_slot, open_houses, utc_now,
)

log = logging.getLogger(__name__)

# ponytail: a move of more than 25% between two readings is taken as a misread (a
# redesign parsing the monthly cost, a "similar homes" price) and skipped; real Danish
# cuts are 2-10%. If a genuine big move gets stuck behind it, raise this.
MAX_JUMP = 0.25

_LISTING_FACTS = ("listed_price_dkk", "listed_date", "days_on_market",
                  "total_days_on_market", "realtor")

# Statuses whose new open houses ping Discord (spec D4).
PING_STATUSES = ("shortlist", "offer")


def _address_id(house, listing, geocoder) -> str | None:
    """DAWA's id for the house, resolved once and then kept in the listing row."""
    if listing and listing.get("address_id"):
        return listing["address_id"]
    if geocoder is None:
        return None
    query = " ".join(p for p in (house.address, house.postal_code, house.city) if p)
    try:
        return (geocoder.geocode(query) or {}).get("address_id")
    except Exception:
        return None


def _boligsiden_facts(house, address_id, boligsiden, now) -> dict | None:
    if not address_id or boligsiden is None:
        return None
    try:
        data = boligsiden.address(address_id)
    except Exception:
        return None
    if not data:
        return None
    if house.postal_code and str(data.get("zipCode")) != str(house.postal_code):
        return None                  # the geocoder found a namesake street in another town
    try:
        return parse_address(data, today=now)
    except Exception:
        return None


def _agency_price(final_url: str, html: str) -> float | None:
    try:
        return parse_for(final_url, html).house.get("price_dkk")
    except Exception:
        return None


def _track_price(store, house, verdict, final_url, html, boligsiden, geocoder, now,
                 summary, notify) -> dict | None:
    """Read today's asking price and log it when it is a believable change. Compares
    with the last price seen online (the newest price_event), not price_dkk, so a hand
    correction survives until the online price really changes. Returns the Boligsiden
    facts it read (None when there were none), for the open-house step."""
    listing = store.get_listing(house.id)
    aid = _address_id(house, listing, geocoder)
    facts = _boligsiden_facts(house, aid, boligsiden, now)
    if facts and facts["price_dkk"] is not None:
        reading, source = facts["price_dkk"], "boligsiden"
    elif verdict == "listed":
        reading, source = _agency_price(final_url, html), "agency"
    else:
        reading, source = None, None

    events = store.price_events(house.id)
    last = events[-1]["price_dkk"] if events else None
    base = house.price_dkk or last          # the price the app shows; == last unless hand-corrected
    usable = bool(reading) and reading > 0
    if usable and base and abs(reading - base) / base > MAX_JUMP:
        log.warning("price jump skipped for %s: %s -> %s (%s)",
                    house.id, base, reading, source)
        summary["skipped"] += 1
        usable = False

    fields = {"address_id": aid} if aid else {}
    if facts:
        fields["sales"] = facts["sales"]
    if usable:
        fields["checked_at"] = now
        if source == "boligsiden":             # listing facts only from a trusted reading
            fields.update({k: facts[k] for k in _LISTING_FACTS})
    store.save_listing(house.id, fields)       # before record_price: original_price uses it
    if not usable or reading == last:
        return facts
    store.record_price(house.id, reading, source, now)
    summary["repriced"] += 1
    if notify is not None and base and reading < base:
        try:
            notify(house, base, reading, store.original_price(house.id))
        except Exception as e:                     # never lose the price over a ping
            log.warning("price-drop ping failed for %s: %s %s",
                        house.id, type(e).__name__, getattr(e, "code", ""))
    return facts


def _track_open_houses(store, house, verdict, final_url, html, facts, at, today,
                       summary, notify_open) -> None:
    """The agency page's slots, else Boligsiden's next one (spec D1). The read prunes
    (marks vanished upcoming slots gone) only when it is complete: the page showed
    slots, or the page and Boligsiden were both read and both show none. Slots already
    over count as none (a page still showing yesterday's is not a complete read).
    Nothing read at all changes nothing."""
    page_read, bolig_read = verdict == "listed", facts is not None
    if not (page_read or bolig_read):
        return
    agency = ([s for s in open_houses(final_url, html, today) if s["ends_at"] > at]
              if page_read else [])
    nxt = boligsiden_slot((facts or {}).get("next_open_house"),
                          house.source_adapter in WALL_CLOCK_ADAPTERS)
    nxt = nxt if nxt and nxt["ends_at"] > at else None
    if page_read and bolig_read and bool(agency) != bool(nxt):
        log.warning("open houses differ for %s: realtor=%d boligsiden=%d",
                    house.id, len(agency), int(nxt is not None))
    if agency:
        slots, source, prune = agency, "agency", True
    else:
        slots, source = ([nxt] if nxt else []), "boligsiden"
        prune = page_read and bolig_read and nxt is None
    new = store.sync_open_houses(house.id, slots, source, at, prune=prune)
    summary["open_new"] += len(new)
    if new and notify_open is not None and house.status in PING_STATUSES:
        try:
            notify_open(house, new)
        except Exception as e:                     # never lose the slots over a ping
            log.warning("open-house ping failed for %s: %s %s",
                        house.id, type(e).__name__, getattr(e, "code", ""))


def _fill_sold_price(store, house, boligsiden, geocoder, now, summary) -> None:
    """This sale is the first tinglyst sale on/after the listing date (else the day we
    added the house). Tinglysning lags weeks to months; until it lands this finds
    nothing and the next sweep simply asks again."""
    listing = store.get_listing(house.id)
    aid = _address_id(house, listing, geocoder)
    facts = _boligsiden_facts(house, aid, boligsiden, now)
    if not facts:
        return
    store.save_listing(house.id, {"address_id": aid, "sales": facts["sales"]})
    since = (listing or {}).get("listed_date") or house.created_at or ""
    sale = next((s for s in reversed(facts["sales"]) if s["date"] >= since), None)
    if sale:
        store.set_realized_price(house.id, sale["price_dkk"], sale["date"], now)
        summary["priced"] += 1


def run_lifecycle(store, prober, boligsiden, now: str, geocoder=None, notify=None,
                  notify_open=None, at: str | None = None) -> dict:
    """`now` is today's date (YYYY-MM-DD); `at` the UTC timestamp open houses are
    judged against (default: this moment)."""
    at = at or utc_now()
    today = date.fromisoformat(now)
    summary = {"checked": 0, "marked_sold": 0, "priced": 0, "repriced": 0, "skipped": 0,
               "open_new": 0}
    for h in store.list_houses():
        verdict, final_url, html = None, "", ""
        if h.status != "sold" and prober is not None and h.listing_url:
            summary["checked"] += 1
            verdict, final_url, html = probe_listing(h.listing_url, prober)
            if verdict in ("gone", "sold"):
                store.mark_sold(h.id, now)
                summary["marked_sold"] += 1
                h = store.get_house(h.id)          # refresh so the sold-price step runs now

        if h.status == "sold":
            if h.sold_price_dkk is None:
                _fill_sold_price(store, h, boligsiden, geocoder, now, summary)
        else:
            facts = _track_price(store, h, verdict, final_url, html, boligsiden, geocoder,
                                 now, summary, notify)
            _track_open_houses(store, h, verdict, final_url, html, facts, at, today,
                               summary, notify_open)
    return summary
