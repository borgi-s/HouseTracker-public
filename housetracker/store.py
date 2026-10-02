"""SQLite store: schema + persistence for houses, people, criteria, scores."""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

from housetracker.model import (
    CRITERION_KINDS, HOUSE_STATUSES, AdapterConfig, Anchor, Commute, Criterion,
    DuplicateHouse, House, Media, Person, ValidationError,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS house (
    id TEXT PRIMARY KEY, address TEXT NOT NULL, postal_code TEXT, city TEXT,
    kommune TEXT, lat REAL, lon REAL, maegler_chain TEXT, listing_url TEXT,
    price_dkk REAL, ejerudgift_dkk REAL, size_m2 REAL, lot_m2 REAL, rooms REAL,
    build_year INTEGER, energy_label TEXT, description TEXT,
    floors INTEGER, bathrooms INTEGER, basement_m2 REAL,
    status TEXT NOT NULL DEFAULT 'not_visited',
    sold_price_dkk REAL, sold_date TEXT, sold_detected_at TEXT,
    scrape_completeness REAL, source_adapter TEXT,
    created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS person (
    id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS criterion (
    id TEXT PRIMARY KEY, key TEXT NOT NULL UNIQUE, label TEXT NOT NULL,
    kind TEXT NOT NULL, weight REAL NOT NULL DEFAULT 1.0,
    auto_source TEXT, higher_is_better INTEGER NOT NULL DEFAULT 1,
    active INTEGER NOT NULL DEFAULT 1, sort INTEGER NOT NULL DEFAULT 0,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS score (
    house_id TEXT NOT NULL, person_id TEXT NOT NULL, criterion_id TEXT NOT NULL,
    value REAL NOT NULL, created_at TEXT, updated_at TEXT,
    PRIMARY KEY (house_id, person_id, criterion_id)
);
CREATE TABLE IF NOT EXISTS status_event (
    id INTEGER PRIMARY KEY AUTOINCREMENT, house_id TEXT NOT NULL,
    status TEXT NOT NULL, at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS media (
    id TEXT PRIMARY KEY, house_id TEXT NOT NULL, kind TEXT NOT NULL,
    path TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'scrape',
    caption TEXT, sort INTEGER NOT NULL DEFAULT 0, added_at TEXT
);
CREATE TABLE IF NOT EXISTS adapter_config (
    chain TEXT PRIMARY KEY, selectors_json TEXT NOT NULL,
    completeness_last REAL, confirmed INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'llm', created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS anchor (
    id TEXT PRIMARY KEY, label TEXT NOT NULL, address TEXT,
    lat REAL, lon REAL, kind TEXT NOT NULL DEFAULT 'fixed'
);
CREATE TABLE IF NOT EXISTS commute (
    house_id TEXT NOT NULL, anchor_ref TEXT NOT NULL, mode TEXT NOT NULL,
    minutes REAL, distance_m REAL, computed_at TEXT,
    PRIMARY KEY (house_id, anchor_ref, mode)
);
CREATE TABLE IF NOT EXISTS note (
    id INTEGER PRIMARY KEY AUTOINCREMENT, house_id TEXT NOT NULL,
    person_id TEXT, body TEXT NOT NULL, created_at TEXT
);
CREATE TABLE IF NOT EXISTS tag (
    id INTEGER PRIMARY KEY AUTOINCREMENT, house_id TEXT NOT NULL,
    person_id TEXT, label TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS price_event (
    id INTEGER PRIMARY KEY AUTOINCREMENT, house_id TEXT NOT NULL,
    price_dkk REAL NOT NULL, at TEXT NOT NULL, source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS listing (
    house_id TEXT PRIMARY KEY, address_id TEXT, listed_price_dkk REAL, listed_date TEXT,
    days_on_market INTEGER, total_days_on_market INTEGER, realtor TEXT,
    sales_json TEXT, checked_at TEXT
);
CREATE TABLE IF NOT EXISTS school (
    inst_nr TEXT PRIMARY KEY, slug TEXT NOT NULL, name TEXT NOT NULL, address TEXT,
    lat REAL, lon REAL, kommune TEXT NOT NULL, top_grade INTEGER,
    figures_json TEXT NOT NULL, fetched_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS house_school (
    house_id TEXT NOT NULL, district_order INTEGER NOT NULL, rank INTEGER NOT NULL,
    district_name TEXT NOT NULL, district_grades TEXT, district_link TEXT,
    district_schools INTEGER NOT NULL, fallback INTEGER NOT NULL DEFAULT 0,
    inst_nr TEXT NOT NULL, walk_min REAL, walk_m REAL, bike_min REAL, bike_m REAL,
    straight_m REAL, checked_at TEXT NOT NULL,
    PRIMARY KEY (house_id, district_order, rank)
);
CREATE TABLE IF NOT EXISTS open_house (
    house_id TEXT NOT NULL, starts_at TEXT NOT NULL, ends_at TEXT NOT NULL,
    signup INTEGER, signup_url TEXT, source TEXT NOT NULL,
    first_seen TEXT NOT NULL, gone_at TEXT,
    PRIMARY KEY (house_id, starts_at)
);
"""


class HouseStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)  # ponytail: per-request connections are safe across threads; upgrade to thread-local pool if contention appears
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        # Columns added after a database was created (CREATE TABLE IF NOT EXISTS leaves
        # an existing table as it was).
        have = {r["name"] for r in self.conn.execute("PRAGMA table_info(house)")}
        for col, kind in (("floors", "INTEGER"), ("bathrooms", "INTEGER"),
                          ("basement_m2", "REAL")):
            if col not in have:
                self.conn.execute(f"ALTER TABLE house ADD COLUMN {col} {kind}")
        self.conn.commit()
        # Every priced house's history starts with the price it was added at. Idempotent,
        # so it is also the one-time backfill for houses added before price_event existed.
        self.conn.execute(
            "INSERT INTO price_event (house_id, price_dkk, at, source) "
            "SELECT id, price_dkk, COALESCE(created_at, ''), 'added' FROM house "
            "WHERE price_dkk IS NOT NULL "
            "AND id NOT IN (SELECT house_id FROM price_event)")
        self.conn.commit()

    def table_names(self) -> set[str]:
        rows = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        return {r["name"] for r in rows}

    _HOUSE_COLS = (
        "id", "address", "postal_code", "city", "kommune", "lat", "lon",
        "maegler_chain", "listing_url", "price_dkk", "ejerudgift_dkk",
        "size_m2", "lot_m2", "rooms", "build_year", "energy_label",
        "description", "floors", "bathrooms", "basement_m2",
        "status", "sold_price_dkk", "sold_date",
        "sold_detected_at", "scrape_completeness", "source_adapter",
        "created_at", "updated_at",
    )

    def add_house(self, data: dict, now: str) -> House:
        house = House.from_dict({**data})
        if tracked := self.find_house(house):
            raise DuplicateHouse(tracked)
        if not house.id:
            house.id = self._unique_key("house", self._slug(house.address))
        elif self.get_house(house.id):
            raise ValidationError(f"house id {house.id!r} already exists")
        house.created_at = house.updated_at = now
        d = house.to_dict()
        cols = ", ".join(self._HOUSE_COLS)
        marks = ", ".join("?" for _ in self._HOUSE_COLS)
        self.conn.execute(
            f"INSERT INTO house ({cols}) VALUES ({marks})",
            [d[c] for c in self._HOUSE_COLS])
        self.conn.execute(
            "INSERT INTO status_event (house_id, status, at) VALUES (?, ?, ?)",
            (house.id, house.status, now))
        if house.price_dkk is not None:
            self.conn.execute(
                "INSERT INTO price_event (house_id, price_dkk, at, source) "
                "VALUES (?, ?, ?, 'added')", (house.id, house.price_dkk, now))
        self.conn.commit()
        return house

    def find_house(self, house: House) -> House | None:
        """The house we already track as `house`: the same listing link (query string,
        www. and trailing slash ignored), or the same address (_slug-compared) in the same
        postal code, or with either postal code unknown."""
        link = _bare_url(house.listing_url)
        for h in self.list_houses():
            if link and _bare_url(h.listing_url) == link:
                return h
            if (self._slug(h.address) == self._slug(house.address)
                    and (not h.postal_code or not house.postal_code
                         or h.postal_code == house.postal_code)):
                return h
        return None

    def get_house(self, house_id: str) -> House | None:
        row = self.conn.execute(
            "SELECT * FROM house WHERE id = ?", (house_id,)).fetchone()
        return House.from_dict(dict(row)) if row else None

    def list_houses(self) -> list[House]:
        rows = self.conn.execute("SELECT * FROM house ORDER BY created_at").fetchall()
        return [House.from_dict(dict(r)) for r in rows]

    def delete_house(self, house_id: str) -> bool:
        """The house and every row hanging off it. Media files on disk are the caller's."""
        for t in ("score", "status_event", "media", "commute", "note", "tag",
                  "price_event", "listing", "house_school", "open_house"):
            self.conn.execute(f"DELETE FROM {t} WHERE house_id = ?", (house_id,))
        cur = self.conn.execute("DELETE FROM house WHERE id = ?", (house_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def set_status(self, house_id: str, status: str, now: str) -> House:
        if status not in HOUSE_STATUSES:
            raise ValidationError(
                f"status must be one of {HOUSE_STATUSES}, got {status!r}")
        if not self.get_house(house_id):
            raise ValidationError(f"no house with id {house_id!r}")
        self.conn.execute(
            "UPDATE house SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, house_id))
        self.conn.execute(
            "INSERT INTO status_event (house_id, status, at) VALUES (?, ?, ?)",
            (house_id, status, now))
        self.conn.commit()
        return self.get_house(house_id)

    def status_history(self, house_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT status, at FROM status_event WHERE house_id = ? ORDER BY id",
            (house_id,)).fetchall()
        return [dict(r) for r in rows]

    def price_events(self, house_id: str) -> list[dict]:
        """Every price seen for the house, oldest first."""
        rows = self.conn.execute(
            "SELECT price_dkk, at, source FROM price_event WHERE house_id = ? ORDER BY id",
            (house_id,)).fetchall()
        return [dict(r) for r in rows]

    def record_price(self, house_id: str, price_dkk: float, source: str,
                     now: str) -> None:
        """A new asking price seen online: log it and make it the house's current price."""
        self.conn.execute(
            "INSERT INTO price_event (house_id, price_dkk, at, source) VALUES (?, ?, ?, ?)",
            (house_id, price_dkk, now, source))
        self.conn.execute(
            "UPDATE house SET price_dkk = ?, updated_at = ? WHERE id = ?",
            (price_dkk, now, house_id))
        self.conn.commit()

    def original_price(self, house_id: str) -> float | None:
        """What the ↓% bubble compares with: the agent's first asking price when
        Boligsiden told us, else the first price we saw."""
        listing = self.get_listing(house_id)
        if listing and listing["listed_price_dkk"] is not None:
            return listing["listed_price_dkk"]
        row = self.conn.execute(
            "SELECT price_dkk FROM price_event WHERE house_id = ? ORDER BY id LIMIT 1",
            (house_id,)).fetchone()
        return row["price_dkk"] if row else None

    LISTING_FIELDS = ("address_id", "listed_price_dkk", "listed_date", "days_on_market",
                      "total_days_on_market", "realtor", "sales", "checked_at")

    def save_listing(self, house_id: str, fields: dict) -> None:
        """Upsert what the sweep learned about the house's listing. Only the keys given
        change; `sales` (a list of dicts) is stored as JSON."""
        bad = set(fields) - set(self.LISTING_FIELDS)
        if bad:
            raise ValidationError(f"not a listing field: {sorted(bad)}")
        if not fields:
            return
        # Column names come from the whitelist above, never from the caller.
        row = {("sales_json" if k == "sales" else k): (json.dumps(v) if k == "sales" else v)
               for k, v in fields.items()}
        sets = ", ".join(f"{c} = excluded.{c}" for c in row)
        self.conn.execute(
            f"INSERT INTO listing (house_id, {', '.join(row)}) "
            f"VALUES (?, {', '.join('?' for _ in row)}) "
            f"ON CONFLICT(house_id) DO UPDATE SET {sets}",
            [house_id, *row.values()])
        self.conn.commit()

    def get_listing(self, house_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM listing WHERE house_id = ?", (house_id,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["sales"] = json.loads(d.pop("sales_json") or "[]")
        return d

    # --- open houses (docs/specs/2026-09-30-open-houses-design.md §4) ---

    def sync_open_houses(self, house_id: str, slots: list[dict], source: str, at: str,
                         prune: bool = True) -> list[dict]:
        """Record the open houses a source shows at `at` (UTC text); return the ones never
        seen before for this house, soonest first. Slots already over are ignored. A
        known slot is updated and, if it had vanished, un-gone. With `prune` the read is
        complete: a slot not started yet and missing from it is marked gone (cancelled or
        moved); one already under way is left to end as held."""
        live = sorted((s for s in slots if s["ends_at"] > at), key=lambda s: s["starts_at"])
        known = {r["starts_at"] for r in self.conn.execute(
            "SELECT starts_at FROM open_house WHERE house_id = ?", (house_id,))}
        with self.conn:
            self.conn.executemany(
                "INSERT INTO open_house (house_id, starts_at, ends_at, signup, signup_url, "
                "source, first_seen) VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(house_id, starts_at) DO UPDATE SET ends_at = excluded.ends_at, "
                "signup = excluded.signup, signup_url = excluded.signup_url, "
                "source = excluded.source, gone_at = NULL",
                [(house_id, s["starts_at"], s["ends_at"], s["signup"], s.get("signup_url"),
                  source, at) for s in live])
            if prune:
                keep = [s["starts_at"] for s in live]
                self.conn.execute(
                    "UPDATE open_house SET gone_at = ? WHERE house_id = ? AND gone_at IS NULL "
                    f"AND starts_at > ? AND starts_at NOT IN ({', '.join('?' for _ in keep)})",
                    (at, house_id, at, *keep))
        return [s for s in live if s["starts_at"] not in known]

    def list_open_houses(self, house_id: str, upcoming_at: str | None = None) -> list[dict]:
        """The house's open houses, soonest first; with `upcoming_at`, only those still
        listed and ending after it."""
        sql = "SELECT * FROM open_house WHERE house_id = ?"
        args: list = [house_id]
        if upcoming_at is not None:
            sql += " AND gone_at IS NULL AND ends_at > ?"
            args.append(upcoming_at)
        rows = self.conn.execute(sql + " ORDER BY starts_at", args).fetchall()
        return [{"starts_at": r["starts_at"], "ends_at": r["ends_at"],
                 "signup": None if r["signup"] is None else bool(r["signup"]),
                 "signup_url": r["signup_url"], "cancelled": r["gone_at"] is not None}
                for r in rows]

    # --- district schools (docs/specs/2026-09-26-schools-design.md D8) ---

    SCHOOL_FIELDS = ("inst_nr", "slug", "name", "address", "lat", "lon", "kommune",
                     "top_grade", "figures", "fetched_at")

    def upsert_school(self, row: dict) -> None:
        """One folkeskole as skolegang.dk describes it; keys outside SCHOOL_FIELDS are
        ignored and `figures` (a dict) is stored as JSON."""
        vals = {k: row.get(k) for k in self.SCHOOL_FIELDS}
        vals["figures_json"] = json.dumps(vals.pop("figures") or {}, ensure_ascii=False)
        cols = list(vals)                     # names from the tuple above, never the caller
        sets = ", ".join(f"{c} = excluded.{c}" for c in cols if c != "inst_nr")
        self.conn.execute(
            f"INSERT INTO school ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)}) "
            f"ON CONFLICT(inst_nr) DO UPDATE SET {sets}", list(vals.values()))
        self.conn.commit()

    @staticmethod
    def _school(row) -> dict:
        d = dict(row)
        d["figures"] = json.loads(d.pop("figures_json"))
        return d

    def list_schools(self, kommune: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM school WHERE kommune = ? ORDER BY name", (kommune,)).fetchall()
        return [self._school(r) for r in rows]

    def get_school(self, inst_nr: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM school WHERE inst_nr = ?", (inst_nr,)).fetchone()
        return self._school(row) if row else None

    HOUSE_SCHOOL_FIELDS = ("district_order", "rank", "district_name", "district_grades",
                           "district_link", "district_schools", "fallback", "inst_nr",
                           "walk_min", "walk_m", "bike_min", "bike_m", "straight_m")

    def replace_house_schools(self, house_id: str, rows: list[dict], now: str) -> None:
        """The house's district schools, all at once: the old set goes in the same
        transaction, so a reader never sees half of each."""
        cols = ("house_id", *self.HOUSE_SCHOOL_FIELDS, "checked_at")
        with self.conn:
            self.conn.execute("DELETE FROM house_school WHERE house_id = ?", (house_id,))
            self.conn.executemany(
                f"INSERT INTO house_school ({', '.join(cols)}) "
                f"VALUES ({', '.join('?' for _ in cols)})",
                [(house_id, *(r.get(k) for k in self.HOUSE_SCHOOL_FIELDS), now)
                 for r in rows])

    def list_house_schools(self, house_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM house_school WHERE house_id = ? ORDER BY district_order, rank",
            (house_id,)).fetchall()
        return [{**dict(r), "fallback": bool(r["fallback"])} for r in rows]

    # What a person may correct by hand (M7 spec §5 #2). Status has its own method so
    # every change lands in status_event; ids, timestamps and the sold/scrape audit
    # columns are written by automation only.
    EDITABLE_HOUSE_FIELDS = (
        "address", "postal_code", "city", "maegler_chain", "listing_url",
        "price_dkk", "ejerudgift_dkk", "size_m2", "lot_m2", "rooms",
        "build_year", "energy_label", "description",
        "floors", "bathrooms", "basement_m2",
    )

    def update_house(self, house_id: str, fields: dict, now: str) -> House:
        bad = set(fields) - set(self.EDITABLE_HOUSE_FIELDS)
        if bad:
            raise ValidationError(f"not editable: {sorted(bad)}")
        house = self.get_house(house_id)
        if house is None:
            raise ValidationError(f"no house with id {house_id!r}")
        House.from_dict({**house.to_dict(), **fields})      # validate before writing
        if fields:
            # Column names come from the whitelist above, never from the caller.
            sets = ", ".join(f"{k} = ?" for k in fields)
            self.conn.execute(f"UPDATE house SET {sets}, updated_at = ? WHERE id = ?",
                              [*fields.values(), now, house_id])
            self.conn.commit()
        return self.get_house(house_id)

    # What re-reading the listing page may overwrite: the listing's facts and the scrape
    # audit. Never the price (the lifecycle sweep owns price moves and their history),
    # the link, the map pin (enrichment's), status, or anything we added ourselves.
    SCRAPE_REFRESH_FIELDS = (
        "address", "postal_code", "city", "maegler_chain", "ejerudgift_dkk", "size_m2",
        "lot_m2", "rooms", "build_year", "energy_label", "description",
        "scrape_completeness", "source_adapter",
    )

    def refresh_from_scrape(self, house_id: str, scraped: dict, now: str) -> House:
        """Apply a fresh parse of the listing; fields the parse did not find stay as is."""
        fields = {k: scraped[k] for k in self.SCRAPE_REFRESH_FIELDS
                  if scraped.get(k) not in (None, "")}
        house = self.get_house(house_id)
        if house is None:
            raise ValidationError(f"no house with id {house_id!r}")
        House.from_dict({**house.to_dict(), **fields})      # validate before writing
        if fields:
            sets = ", ".join(f"{k} = ?" for k in fields)    # names from the tuple above
            self.conn.execute(f"UPDATE house SET {sets}, updated_at = ? WHERE id = ?",
                              [*fields.values(), now, house_id])
            self.conn.commit()
        return self.get_house(house_id)

    def mark_sold(self, house_id: str, now: str,
                  detected_at: str | None = None) -> House:
        """Auto sold-detection path: transition to 'sold' (logs a status_event via
        set_status) and stamp sold_detected_at. Callers pass only transitioning houses;
        the daily sweep filters status != 'sold' before calling this."""
        self.set_status(house_id, "sold", now)          # status + status_event + updated_at
        self.conn.execute(
            "UPDATE house SET sold_detected_at = ? WHERE id = ?",
            (detected_at or now, house_id))
        self.conn.commit()
        return self.get_house(house_id)

    def set_realized_price(self, house_id: str, sold_price_dkk: float,
                           sold_date: str | None, now: str) -> None:
        """Fill the realized sale price/date. Snapshot-safe: touches only these columns."""
        self.conn.execute(
            "UPDATE house SET sold_price_dkk = ?, sold_date = ?, updated_at = ? "
            "WHERE id = ?",
            (sold_price_dkk, sold_date, now, house_id))
        self.conn.commit()

    def add_person(self, name: str) -> Person:
        pid = self._unique_key("person", self._slug(name))
        self.conn.execute("INSERT INTO person (id, name) VALUES (?, ?)", (pid, name))
        self.conn.commit()
        return Person(id=pid, name=name)

    def list_persons(self) -> list[Person]:
        rows = self.conn.execute("SELECT * FROM person ORDER BY name").fetchall()
        return [Person.from_dict(dict(r)) for r in rows]

    def add_criterion(self, data: dict, now: str) -> Criterion:
        c = Criterion.from_dict({**data})
        if not c.id:
            c.id = self._slug(c.key)
        c.created_at = now
        self.conn.execute(
            "INSERT INTO criterion (id, key, label, kind, weight, auto_source, "
            "higher_is_better, active, sort, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (c.id, c.key, c.label, c.kind, c.weight, c.auto_source,
             int(c.higher_is_better), int(c.active), c.sort, c.created_at))
        self.conn.commit()
        return c

    def list_criteria(self, active_only: bool = True) -> list[Criterion]:
        sql = "SELECT * FROM criterion"
        if active_only:
            sql += " WHERE active = 1"
        sql += " ORDER BY sort, key"
        return [Criterion.from_dict(dict(r)) for r in self.conn.execute(sql).fetchall()]

    EDITABLE_CRITERION_FIELDS = ("label", "weight", "sort", "active")

    def update_criterion(self, criterion_id: str, fields: dict) -> Criterion:
        bad = set(fields) - set(self.EDITABLE_CRITERION_FIELDS)
        if bad:
            raise ValidationError(f"not editable: {sorted(bad)}")
        current = next((c for c in self.list_criteria(active_only=False)
                        if c.id == criterion_id), None)
        if current is None:
            raise ValidationError(f"no criterion with id {criterion_id!r}")
        c = Criterion.from_dict({**current.to_dict(), **fields})   # validates
        self.conn.execute(
            "UPDATE criterion SET label = ?, weight = ?, sort = ?, active = ? "
            "WHERE id = ?", (c.label, c.weight, c.sort, int(c.active), criterion_id))
        self.conn.commit()
        return c

    def _unique_key(self, table: str, base: str) -> str:
        taken = {r["id"] for r in
                 self.conn.execute(f"SELECT id FROM {table}").fetchall()}
        if base not in taken:
            return base
        n = 2
        while f"{base}-{n}" in taken:
            n += 1
        return f"{base}-{n}"

    def upsert_score(self, house_id: str, person_id: str, criterion_id: str,
                     value: float, now: str) -> None:
        self.conn.execute(
            "INSERT INTO score (house_id, person_id, criterion_id, value, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(house_id, person_id, criterion_id) "
            "DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (house_id, person_id, criterion_id, float(value), now, now))
        self.conn.commit()

    def get_scores(self, house_id: str) -> dict[tuple[str, str], float]:
        rows = self.conn.execute(
            "SELECT person_id, criterion_id, value FROM score WHERE house_id = ?",
            (house_id,)).fetchall()
        return {(r["person_id"], r["criterion_id"]): r["value"] for r in rows}

    def delete_score(self, house_id: str, person_id: str, criterion_id: str) -> bool:
        cur = self.conn.execute(
            "DELETE FROM score WHERE house_id = ? AND person_id = ? AND criterion_id = ?",
            (house_id, person_id, criterion_id))
        self.conn.commit()
        return cur.rowcount > 0

    def add_media(self, data: dict, now: str) -> Media:
        m = Media.from_dict({**data})
        if not m.id:
            m.id = self._unique_key("media", self._slug(f"{m.house_id}-{m.kind}"))
        m.added_at = now
        self.conn.execute(
            "INSERT INTO media (id, house_id, kind, path, source, caption, sort, added_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (m.id, m.house_id, m.kind, m.path, m.source, m.caption, m.sort, m.added_at))
        self.conn.commit()
        return m

    def list_media(self, house_id: str) -> list[Media]:
        rows = self.conn.execute(
            "SELECT * FROM media WHERE house_id = ? ORDER BY kind, sort, id",
            (house_id,)).fetchall()
        return [Media.from_dict(dict(r)) for r in rows]

    def get_media(self, media_id: str) -> Media | None:
        row = self.conn.execute(
            "SELECT * FROM media WHERE id = ?", (media_id,)).fetchone()
        return Media.from_dict(dict(row)) if row else None

    def delete_media(self, media_id: str) -> bool:
        cur = self.conn.execute("DELETE FROM media WHERE id = ?", (media_id,))
        self.conn.commit()
        return cur.rowcount > 0

    # --- notes & tags (spec §5; person_id NULL = shared between us) ---

    def add_note(self, house_id: str, person_id: str | None, body: str,
                 now: str) -> dict:
        if not body.strip():
            raise ValidationError("note body is required")
        cur = self.conn.execute(
            "INSERT INTO note (house_id, person_id, body, created_at) "
            "VALUES (?, ?, ?, ?)", (house_id, person_id, body, now))
        self.conn.commit()
        return {"id": cur.lastrowid, "house_id": house_id, "person_id": person_id,
                "body": body, "created_at": now}

    def list_notes(self, house_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, house_id, person_id, body, created_at FROM note "
            "WHERE house_id = ? ORDER BY id", (house_id,)).fetchall()
        return [dict(r) for r in rows]

    def delete_note(self, note_id: int) -> bool:
        cur = self.conn.execute("DELETE FROM note WHERE id = ?", (note_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def add_tag(self, house_id: str, person_id: str | None, label: str) -> dict:
        if not label.strip():
            raise ValidationError("tag label is required")
        cur = self.conn.execute(
            "INSERT INTO tag (house_id, person_id, label) VALUES (?, ?, ?)",
            (house_id, person_id, label))
        self.conn.commit()
        return {"id": cur.lastrowid, "house_id": house_id,
                "person_id": person_id, "label": label}

    def list_tags(self, house_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, house_id, person_id, label FROM tag WHERE house_id = ? "
            "ORDER BY id", (house_id,)).fetchall()
        return [dict(r) for r in rows]

    def delete_tag(self, tag_id: int) -> bool:
        cur = self.conn.execute("DELETE FROM tag WHERE id = ?", (tag_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def get_adapter_config(self, chain: str) -> AdapterConfig | None:
        row = self.conn.execute(
            "SELECT * FROM adapter_config WHERE chain = ?", (chain,)).fetchone()
        return AdapterConfig.from_dict(dict(row)) if row else None

    def upsert_adapter_config(self, chain: str, selectors_json: str,
                              completeness_last: float | None, source: str,
                              confirmed: bool, now: str) -> None:
        self.conn.execute(
            "INSERT INTO adapter_config (chain, selectors_json, completeness_last, "
            "source, confirmed, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(chain) DO UPDATE SET selectors_json = excluded.selectors_json, "
            "completeness_last = excluded.completeness_last, source = excluded.source, "
            "confirmed = excluded.confirmed, updated_at = excluded.updated_at",
            (chain, selectors_json, completeness_last, source, int(confirmed),
             now, now))
        self.conn.commit()

    def confirm_adapter_config(self, chain: str, now: str) -> None:
        self.conn.execute(
            "UPDATE adapter_config SET confirmed = 1, updated_at = ? WHERE chain = ?",
            (now, chain))
        self.conn.commit()

    def add_anchor(self, data: dict) -> Anchor:
        a = Anchor.from_dict({**data})
        if not a.id:
            a.id = self._unique_key("anchor", self._slug(a.label))
        self.conn.execute(
            "INSERT INTO anchor (id, label, address, lat, lon, kind) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (a.id, a.label, a.address, a.lat, a.lon, a.kind))
        self.conn.commit()
        return a

    def get_anchor(self, anchor_id: str) -> Anchor | None:
        row = self.conn.execute(
            "SELECT * FROM anchor WHERE id = ?", (anchor_id,)).fetchone()
        return Anchor.from_dict(dict(row)) if row else None

    def list_anchors(self, kind: str | None = None) -> list[Anchor]:
        if kind is None:
            rows = self.conn.execute("SELECT * FROM anchor ORDER BY id").fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM anchor WHERE kind = ? ORDER BY id", (kind,)).fetchall()
        return [Anchor.from_dict(dict(r)) for r in rows]

    def upsert_commute(self, house_id: str, anchor_ref: str, mode: str,
                       minutes: float | None, distance_m: float | None,
                       now: str) -> None:
        self.conn.execute(
            "INSERT INTO commute (house_id, anchor_ref, mode, minutes, distance_m, "
            "computed_at) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(house_id, anchor_ref, mode) DO UPDATE SET "
            "minutes = excluded.minutes, distance_m = excluded.distance_m, "
            "computed_at = excluded.computed_at",
            (house_id, anchor_ref, mode, minutes, distance_m, now))
        self.conn.commit()

    def list_commutes(self, house_id: str) -> list[Commute]:
        rows = self.conn.execute(
            "SELECT * FROM commute WHERE house_id = ? ORDER BY anchor_ref, mode",
            (house_id,)).fetchall()
        return [Commute.from_dict(dict(r)) for r in rows]

    def update_house_location(self, house_id: str, lat: float | None,
                              lon: float | None, kommune: str | None = None,
                              postal_code: str | None = None,
                              city: str | None = None, now: str | None = None) -> None:
        sets, vals = ["lat = ?", "lon = ?", "updated_at = ?"], [lat, lon, now]
        for col, v in (("kommune", kommune), ("postal_code", postal_code),
                       ("city", city)):
            if v is not None:
                sets.append(f"{col} = ?")
                vals.append(v)
        vals.append(house_id)
        self.conn.execute(
            f"UPDATE house SET {', '.join(sets)} WHERE id = ?", vals)
        self.conn.commit()

    @staticmethod
    def _slug(text: str) -> str:
        s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
        return s or "house"


def _bare_url(url: str | None) -> str | None:
    """A listing link without what varies between shares of it (boliga's ?utm_source=)."""
    if not url:
        return None
    u = urlsplit(url.strip())
    return u.netloc.lower().removeprefix("www.") + u.path.rstrip("/")
