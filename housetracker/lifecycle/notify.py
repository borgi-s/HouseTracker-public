# housetracker/lifecycle/notify.py
"""Pings to a Discord channel through a channel webhook: price drops and new open houses.
The webhook URL is a secret: it comes from HT_DISCORD_WEBHOOK (~/.config/housetracker.env,
loaded by the systemd units), never from the repo. Links point at HT_APP_URL. Which
kinds are sent is a Settings switch (the `setting` table), read by hooks()."""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime

from housetracker.scrape.openhouse import CPH

# Discord's edge rejects urllib's default agent; an honest custom one is accepted.
_UA = "HouseTracker (https://github.com/borgi-s/HouseTracker-public, 1)"


def _app_url() -> str:
    """Where the people pinged open the app (e.g. http://myserver:8765)."""
    return os.environ.get("HT_APP_URL", "http://localhost:8765").rstrip("/")


def _kr(v: float) -> str:
    return f"{round(v):,} kr".replace(",", ".")


def _pct(v: float) -> str:
    return f"{v:.1f} %".replace(".", ",")


def drop_message(house, old: float, new: float, original: float | None) -> str:
    place = " ".join(p for p in (house.postal_code, house.city) if p)
    lines = [f"↓ Price drop: {house.address}" + (f", {place}" if place else ""),
             f"{_kr(old)} → {_kr(new)} (−{_kr(old - new)}, −{_pct((old - new) / old * 100)})"]
    if original and original > new and original != old:
        lines.append(f"Down {_pct((original - new) / original * 100)} since it was listed")
    lines.append(f"{_app_url()}/house/{urllib.parse.quote(house.id)}")
    return "\n".join(lines)


_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _when(s: dict) -> str:
    """'Sun 4 Oct 15:30–15:50' in Danish time."""
    a, b = (datetime.fromisoformat(s[k]).astimezone(CPH) for k in ("starts_at", "ends_at"))
    return f"{_WEEKDAYS[a.weekday()]} {a.day} {_MONTHS[a.month - 1]} {a:%H:%M}–{b:%H:%M}"


def open_house_message(house, slots: list[dict]) -> str:
    """One line per new slot; links in <…> so Discord shows no preview card."""
    place = " ".join(p for p in (house.postal_code, house.city) if p)
    lines = [f"Open house: {house.address}" + (f", {place}" if place else "")]
    for s in slots:
        if s["signup"]:
            link = s.get("signup_url") or house.listing_url
            lines.append(f"{_when(s)} · sign-up" + (f": <{link}>" if link else ""))
        elif s["signup"] is False:
            lines.append(f"{_when(s)} · drop-in")
        else:
            lines.append(_when(s))
    lines.append(f"{_app_url()}/house/{urllib.parse.quote(house.id)}")
    return "\n".join(lines)


def _post(url: str, payload: dict) -> None:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json", "User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=15) as resp:
        resp.read()


class DiscordWebhook:
    """The sweep's `notify` callable. Raises on a failed POST; the sweep catches it."""

    def __init__(self, url: str, post=None):
        self.url, self.post = url, post or _post

    def __call__(self, house, old: float, new: float, original: float | None) -> None:
        # allowed_mentions: listing text is third-party data and must never ping anyone.
        self.post(self.url, {"content": drop_message(house, old, new, original),
                             "allowed_mentions": {"parse": []}})

    def open_houses(self, house, slots: list[dict]) -> None:
        """The sweep's `notify_open` callable. Raises on a failed POST; the sweep catches it."""
        self.post(self.url, {"content": open_house_message(house, slots),
                             "allowed_mentions": {"parse": []}})


def from_env() -> DiscordWebhook | None:
    url = os.environ.get("HT_DISCORD_WEBHOOK")
    return DiscordWebhook(url) if url else None


def hooks(store) -> tuple:
    """The sweep's (notify, notify_open): the webhook, minus what Settings switched off."""
    hook = from_env()
    if hook is None:
        return None, None
    on = lambda key: store.get_setting(key, "1") == "1"
    return (hook if on("notify_price_drops") else None,
            hook.open_houses if on("notify_open_houses") else None)
