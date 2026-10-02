"""Validated dataclasses for houses, people, criteria."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass

HOUSE_STATUSES = ("not_visited", "visited", "shortlist", "rejected", "offer", "sold")
CRITERION_KINDS = ("subjective", "auto")


class ValidationError(ValueError):
    pass


@dataclass
class House:
    address: str
    id: str = ""
    postal_code: str | None = None
    city: str | None = None
    kommune: str | None = None
    lat: float | None = None
    lon: float | None = None
    maegler_chain: str | None = None
    listing_url: str | None = None
    price_dkk: float | None = None
    ejerudgift_dkk: float | None = None
    size_m2: float | None = None
    lot_m2: float | None = None
    rooms: float | None = None
    build_year: int | None = None
    energy_label: str | None = None
    description: str | None = None
    floors: int | None = None             # living floors above ground (enrich: BBR + text)
    bathrooms: int | None = None
    basement_m2: float | None = None
    status: str = "not_visited"
    sold_price_dkk: float | None = None
    sold_date: str | None = None
    sold_detected_at: str | None = None
    scrape_completeness: float | None = None
    source_adapter: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def price_per_m2(self) -> float | None:
        if self.price_dkk is None or not self.size_m2:
            return None
        return self.price_dkk / self.size_m2

    def auto_value(self, name: str) -> float | None:
        """Resolve an auto-criterion source: a field or a computed property."""
        val = getattr(self, name, None)
        return float(val) if isinstance(val, (int, float)) else None

    @classmethod
    def from_dict(cls, data: dict) -> "House":
        d = dict(data)
        address = d["address"]  # KeyError if missing
        fields = {k: v for k, v in d.items() if k in cls.__dataclass_fields__ and k != "address"}
        h = cls(address=address, **fields)
        h.validate()
        return h

    def validate(self) -> None:
        if not self.address:
            raise ValidationError("address is required")
        if self.status not in HOUSE_STATUSES:
            raise ValidationError(
                f"status must be one of {HOUSE_STATUSES}, got {self.status!r}")
        if self.price_dkk is not None and self.price_dkk < 0:
            raise ValidationError("price_dkk must be >= 0")
        if self.size_m2 is not None and self.size_m2 < 0:
            raise ValidationError("size_m2 must be >= 0")

    def to_dict(self) -> dict:
        return asdict(self)


class DuplicateHouse(ValidationError):
    """add_house refused: we already track this house (as .house)."""

    def __init__(self, house: House):
        super().__init__(f"{house.address} is already tracked "
                         f"(status: {house.status.replace('_', ' ')})")
        self.house = house


@dataclass
class Person:
    name: str
    id: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "Person":
        return cls(name=data["name"], id=data.get("id", ""))

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Criterion:
    key: str
    label: str
    kind: str
    weight: float = 1.0
    auto_source: str | None = None
    higher_is_better: bool = True
    active: bool = True
    sort: int = 0
    id: str = ""
    created_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "Criterion":
        d = dict(data)
        c = cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        c.active = bool(c.active)
        c.higher_is_better = bool(c.higher_is_better)
        c.validate()
        return c

    def validate(self) -> None:
        if self.kind not in CRITERION_KINDS:
            raise ValidationError(
                f"kind must be one of {CRITERION_KINDS}, got {self.kind!r}")
        if self.kind == "auto" and not self.auto_source:
            raise ValidationError("auto criterion requires auto_source")
        if self.weight < 0:
            raise ValidationError("weight must be >= 0")

    def to_dict(self) -> dict:
        return asdict(self)


MEDIA_KINDS = ("photo", "floorplan", "pdf", "user_photo")
MEDIA_SOURCES = ("scrape", "manual")


@dataclass
class Media:
    house_id: str
    kind: str
    path: str
    source: str = "scrape"
    caption: str | None = None
    sort: int = 0
    id: str = ""
    added_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "Media":
        d = dict(data)
        m = cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        m.validate()
        return m

    def validate(self) -> None:
        if not self.house_id:
            raise ValidationError("house_id is required")
        if not self.path:
            raise ValidationError("path is required")
        if self.kind not in MEDIA_KINDS:
            raise ValidationError(
                f"kind must be one of {MEDIA_KINDS}, got {self.kind!r}")
        if self.source not in MEDIA_SOURCES:
            raise ValidationError(
                f"source must be one of {MEDIA_SOURCES}, got {self.source!r}")

    def to_dict(self) -> dict:
        return asdict(self)


ADAPTER_SOURCES = ("handwritten", "llm")


@dataclass
class AdapterConfig:
    chain: str
    selectors_json: str
    completeness_last: float | None = None
    confirmed: bool = False
    source: str = "llm"
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "AdapterConfig":
        d = dict(data)
        c = cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        c.confirmed = bool(c.confirmed)
        c.validate()
        return c

    def validate(self) -> None:
        if not self.chain:
            raise ValidationError("chain is required")
        if not self.selectors_json:
            raise ValidationError("selectors_json is required")
        if self.source not in ADAPTER_SOURCES:
            raise ValidationError(
                f"source must be one of {ADAPTER_SOURCES}, got {self.source!r}")

    def selectors(self) -> dict:
        return json.loads(self.selectors_json)

    def to_dict(self) -> dict:
        return asdict(self)


ANCHOR_KINDS = ("fixed", "school_district")
ROUTE_MODES = ("driving-car", "cycling-regular", "foot-walking")


@dataclass
class Anchor:
    id: str = ""
    label: str = ""
    address: str | None = None
    lat: float | None = None
    lon: float | None = None
    kind: str = "fixed"

    @classmethod
    def from_dict(cls, data: dict) -> "Anchor":
        c = cls(**{k: v for k, v in dict(data).items()
                   if k in cls.__dataclass_fields__})
        c.validate()
        return c

    def validate(self) -> None:
        if not self.label:
            raise ValidationError("anchor label is required")
        if self.kind not in ANCHOR_KINDS:
            raise ValidationError(
                f"kind must be one of {ANCHOR_KINDS}, got {self.kind!r}")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Commute:
    house_id: str
    anchor_ref: str
    mode: str
    minutes: float | None = None
    distance_m: float | None = None
    computed_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "Commute":
        c = cls(**{k: v for k, v in dict(data).items()
                   if k in cls.__dataclass_fields__})
        c.validate()
        return c

    def validate(self) -> None:
        if not self.house_id:
            raise ValidationError("commute house_id is required")
        if not self.anchor_ref:
            raise ValidationError("commute anchor_ref is required")
        if not self.mode:
            raise ValidationError("commute mode is required")

    def to_dict(self) -> dict:
        return asdict(self)
