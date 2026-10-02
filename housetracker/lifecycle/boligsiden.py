# housetracker/lifecycle/boligsiden.py
"""Boligsiden lookup. One GET per house to Boligsiden's open JSON API gives the current
asking price, how far it has moved since it was listed, days on market, and every
tinglyst sale of the address. It is keyed by the DAWA address id (Boligsiden uses the
same UUID), so there is no fuzzy address matching. The core talks to the `Boligsiden`
Protocol; tests use a fake opener and no network runs."""
from __future__ import annotations

import json
import urllib.request
from datetime import date, timedelta
from typing import Protocol

# ponytail: calibration constants, checked 2026-09-26. /addresses/{id}
# answers plain HTTP; /cases/{id}, /search/addresses and the website sit behind a
# Cloudflare challenge, so only /addresses is used. Re-check the field names in
# parse_address if Boligsiden changes its API.
BOLIGSIDEN_API = "https://api.boligsiden.dk"
_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


class Boligsiden(Protocol):
    def address(self, address_id: str) -> dict | None: ...


def _default_opener(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


class BoligsidenClient:
    def __init__(self, opener=None):
        self.opener = opener or _default_opener

    def address(self, address_id: str) -> dict | None:
        """The raw /addresses payload, or None on any failure (best-effort)."""
        try:
            data = json.loads(self.opener(f"{BOLIGSIDEN_API}/addresses/{address_id}"))
        except Exception:
            return None
        return data if isinstance(data, dict) else None


def parse_address(data: dict, today: str) -> dict:
    """Map an /addresses payload to what the sweep stores. `price_dkk` and the listing
    keys are None when the address has no open case (not for sale on Boligsiden);
    `next_open_house` is the open case's raw nextOpenHouse."""
    sales = sorted(
        ({"date": r["date"][:10], "price_dkk": float(r["amount"]), "type": r.get("type")}
         for r in data.get("registrations") or [] if r.get("amount") and r.get("date")),
        key=lambda s: s["date"], reverse=True)
    out = {"price_dkk": None, "listed_price_dkk": None, "listed_date": None,
           "days_on_market": None, "total_days_on_market": None, "realtor": None,
           "sales": sales, "next_open_house": None}
    case = next((c for c in data.get("cases") or [] if c.get("status") == "open"), None)
    out["next_open_house"] = (case or {}).get("nextOpenHouse")
    if not case or not case.get("priceCash"):
        return out
    price = float(case["priceCash"])
    pct = case.get("priceChangePercentage") or 0
    # ponytail: Boligsiden gives the total change as a % rounded to 2 decimals, not the
    # first price. Working it back lands within a few thousand kr, and asking prices
    # are set in 5,000s. Use a dated cut list instead if Boligsiden ever exposes one.
    listed = round(price / (1 + pct / 100) / 5000) * 5000.0 if pct else price
    days = case.get("daysOnMarket")
    days = days if isinstance(days, int) else None
    total = ((case.get("timeOnMarket") or {}).get("total") or {}).get("days")
    out.update(
        price_dkk=price,
        listed_price_dkk=listed,
        listed_date=((date.fromisoformat(today) - timedelta(days=days)).isoformat()
                     if days is not None else None),
        days_on_market=days,
        total_days_on_market=total if isinstance(total, int) else None,
        realtor=(case.get("realtor") or {}).get("name"))
    return out
