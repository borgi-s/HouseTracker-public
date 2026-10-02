"""Address lookup. DAWA closed on 2026-10-01; its successor for free text is
Klimadatastyrelsen's Adressevask, which turns "street no, postcode town" into the
official DAR address id. Boligsiden keys its address records by that same id, and a
record has what we need: coordinates, postcode, town, kommune and the BBR facts of the
buildings. The core talks to the `Geocoder` Protocol, so tests use a fake opener and no
network runs."""
from __future__ import annotations

import json
import os
import urllib.parse
from typing import Protocol

from housetracker.lifecycle.boligsiden import BoligsidenClient, _default_opener

_VASK = "https://adressevaelger.dk/vask/"
# ponytail: KDS's shared demo token, which KDS hands out until per-user tokens
# ("brugerstyring") exist. Set HT_ADV_TOKEN to a personal one once they do.
_TOKEN = os.environ.get("HT_ADV_TOKEN", "adressevaelger123")


class Geocoder(Protocol):
    def geocode(self, address: str) -> dict | None: ...


def _location(address_id: str, data: dict) -> dict:
    """One Boligsiden /addresses record -> our location + BBR facts. The facts are the
    main building's (the one with the most living area; sheds and carports have none)."""
    coords = data.get("coordinates") or {}
    main = max(data.get("buildings") or [{}], key=lambda b: b.get("housingArea") or 0)
    return {"lat": coords.get("lat"), "lon": coords.get("lon"),
            "postal_code": str(data["zipCode"]) if data.get("zipCode") else None,
            "city": (data.get("zip") or {}).get("name") or data.get("cityName"),
            "kommune": (data.get("municipality") or {}).get("name"),
            "address_id": address_id,
            "floors": main.get("numberOfFloors"), "bathrooms": main.get("numberOfBathrooms"),
            "basement_m2": main.get("basementArea")}


class AddressGeocoder:
    def __init__(self, opener=None):
        self.opener = opener or _default_opener

    def geocode(self, address: str) -> dict | None:
        """None when the address can't be washed to one official address (Adressevask
        refuses text without a postcode rather than guess a town) or on any failure."""
        query = urllib.parse.urlencode({"adresse": address, "token": _TOKEN})
        try:
            washed = json.loads(self.opener(f"{_VASK}?{query}"))
            address_id = (washed.get("vaskeresultat") or {}).get("adresse_id_lokalid")
        except Exception:
            return None
        if not address_id:
            return None
        data = BoligsidenClient(self.opener).address(address_id)
        return _location(address_id, data) if data else None
