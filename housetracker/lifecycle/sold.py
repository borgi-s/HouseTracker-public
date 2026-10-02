"""Sold-detection: re-fetch a house's listing_url and decide whether it is still listed,
gone (404/410), or shows a sold marker. The core talks to the `Prober` Protocol, so tests
use a fake and no network runs. Best-effort: any failure classifies as 'unknown', which
never marks a house sold."""
from __future__ import annotations

import re
import urllib.error
import urllib.request
from typing import Protocol

_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# ponytail: markers searched only in final_url + <title>/<h1> — avoids nav "Solgte boliger"
# false-positives on active listings. Remaining ceilings: a sold marker appearing ONLY in
# body text would be missed (fix: `status --set sold`), or a chain whose active listing
# includes a sold word in its title/h1. Upgrade path: per-chain sold selector if it misfires.
SOLD_MARKERS = ("solgt", "er solgt", "boligen er solgt")

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)


def _sold_haystack(final_url: str, html: str) -> str:
    """Only the redirect target + the page's <title>/<h1> text — NOT the whole body,
    so a nav 'Solgte boliger' link on an active listing can't trigger a false 'sold'."""
    parts = [final_url, *_TITLE_RE.findall(html), *_H1_RE.findall(html)]
    return " ".join(parts).lower()
GONE_CODES = (404, 410, 451)


class Prober(Protocol):
    def probe(self, url: str) -> tuple[int | None, str, str]: ...


def _default_probe(url: str) -> tuple[int | None, str, str]:
    """GET the url; return (status, final_url, html). A 4xx/5xx comes back as its code
    (HTTPError is a readable response), a network error as (None, url, "")."""
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode(
                resp.headers.get_content_charset() or "utf-8", errors="replace")
            return (getattr(resp, "status", 200), resp.url, body)
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return (e.code, getattr(e, "url", url) or url, body)
    except Exception:
        return (None, url, "")


def classify(status: int | None, final_url: str, html: str) -> str:
    if status in GONE_CODES:
        return "gone"
    if status is None:
        return "unknown"
    if status == 200:
        hay = _sold_haystack(final_url, html)
        if any(m in hay for m in SOLD_MARKERS):
            return "sold"
        return "listed"
    return "unknown"          # 403 bot-wall, 5xx, redirects to non-sold — inconclusive


def probe_listing(url: str, prober: Prober) -> tuple[str, str, str]:
    """(verdict, final_url, html) from one fetch, so the sweep can also read the price
    off the page it already has. Never raises."""
    try:
        status, final_url, html = prober.probe(url)
    except Exception:
        return ("unknown", url, "")
    return (classify(status, final_url, html), final_url, html)


def check_sold(url: str, prober: Prober) -> str:
    """Best-effort verdict: 'gone' | 'sold' | 'listed' | 'unknown'. Never raises."""
    return probe_listing(url, prober)[0]


class HttpProber:
    """The live Prober used by the CLI/systemd sweep."""

    def probe(self, url: str) -> tuple[int | None, str, str]:
        return _default_probe(url)
