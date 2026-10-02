"""OpenRouteService router. The core talks to the `Router` Protocol, so tests use a fake
opener and no network runs. ORS coordinates are [longitude, latitude]; the free API key
comes from the env (HT_ORS_KEY), passed in by the caller — never hard-coded."""
from __future__ import annotations

import json
import urllib.request
from typing import Protocol

from housetracker.model import ROUTE_MODES

_ORS = "https://api.openrouteservice.org/v2/directions"


class Router(Protocol):
    def route(self, start: tuple[float, float], end: tuple[float, float],
              mode: str) -> tuple[float, float] | None: ...


def _parse_ors(data: dict) -> tuple[float, float]:
    s = data["routes"][0]["summary"]
    return (s["duration"] / 60.0, s["distance"])


def _post_ors(api_key: str, mode: str, coords: list) -> dict:
    body = json.dumps({"coordinates": coords}).encode("utf-8")
    req = urllib.request.Request(
        f"{_ORS}/{mode}/json", data=body,
        headers={"Authorization": api_key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


class ORSRouter:
    def __init__(self, api_key: str, opener=None):
        self.api_key = api_key
        self.opener = opener or _post_ors

    def route(self, start, end, mode) -> tuple[float, float] | None:
        if mode not in ROUTE_MODES:
            return None
        try:
            data = self.opener(self.api_key, mode, [list(start), list(end)])
            return _parse_ors(data)
        except Exception:
            # ponytail: swallow so enrichment never fails a house. Upgrade path: log the
            # (url, status) for triage if ORS quota/errors ever need debugging.
            return None
