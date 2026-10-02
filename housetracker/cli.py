"""Argparse harness to exercise the HouseTracker core without a UI."""
from __future__ import annotations

import argparse
import os
import shutil
from datetime import date
from pathlib import Path

from housetracker import scoring
from housetracker.model import DuplicateHouse
from housetracker.store import HouseStore
from housetracker.enrich.enrich import enrich_house
from housetracker.enrich.geocode import AddressGeocoder
from housetracker.enrich.route import ORSRouter
from housetracker.enrich.schools import school_district_map_url
from housetracker.scrape.autoadapter import resolve
from housetracker.scrape.download import download_media, replace_scraped_media
from housetracker.scrape.fetch import (
    FetchError, PatchrightFetcher, UrllibFetcher, fetch_html,
)
from housetracker.scrape.openhouse import record_page
from housetracker.scrape.synth import InboxSynthesizer, tmux_poke
from housetracker.lifecycle.boligsiden import BoligsidenClient
from housetracker.lifecycle.lifecycle import run_lifecycle
from housetracker.lifecycle.notify import hooks
from housetracker.lifecycle.sold import HttpProber


def _today() -> str:
    return date.today().isoformat()


def main(argv: list[str], out) -> int:
    p = argparse.ArgumentParser(prog="housetracker")
    p.add_argument("--db", default="data/housetracker.db")
    sub = p.add_subparsers(dest="cmd", required=True)

    ah = sub.add_parser("add-house")
    ah.add_argument("--address", required=True)
    ah.add_argument("--price", type=float)
    ah.add_argument("--size", type=float)

    ap = sub.add_parser("add-person")
    ap.add_argument("name")

    ac = sub.add_parser("add-criterion")
    ac.add_argument("--key", required=True)
    ac.add_argument("--label", required=True)
    ac.add_argument("--kind", choices=("subjective", "auto"), required=True)
    ac.add_argument("--weight", type=float, default=1.0)
    ac.add_argument("--auto-source")
    ac.add_argument("--lower-better", action="store_true")

    sc = sub.add_parser("score")
    for a in ("--house", "--person", "--criterion"):
        sc.add_argument(a, required=True)
    sc.add_argument("--value", type=float, required=True)

    sh = sub.add_parser("show")
    sh.add_argument("--house", required=True)

    rk = sub.add_parser("rank")
    rk.add_argument("--person", required=True)

    en = sub.add_parser("enrich")
    grp = en.add_mutually_exclusive_group(required=True)
    grp.add_argument("--house")
    grp.add_argument("--all", action="store_true")
    en.add_argument("--no-route", action="store_true",
                    help="geocode + school map only; skip travel-time routing")

    dh = sub.add_parser("delete-house", help="remove a house, its rows and its media files")
    dh.add_argument("--house", required=True)

    st = sub.add_parser("status")
    st.add_argument("--house", required=True)
    st.add_argument("--set", dest="set_status", help="transition to this status")

    ss = sub.add_parser("set-sold")
    ss.add_argument("--house", required=True)
    ss.add_argument("--price", type=float, required=True)
    ss.add_argument("--date", help="realized sale date YYYY-MM-DD")

    lc = sub.add_parser("lifecycle")
    lc.add_argument("--no-boligsiden", action="store_true",
                    help="skip Boligsiden and DAWA lookups (sold-detection and the agency-page price only)")

    scr = sub.add_parser("scrape")
    scr.add_argument("--url", required=True)
    scr.add_argument("--no-browser", action="store_true",
                     help="disable the patchright Lane B fallback")
    scr.add_argument("--no-llm", action="store_true",
                     help="disable LLM auto-adapter synthesis on a gate miss")
    scr.add_argument("--yes", action="store_true",
                     help="auto-confirm a synthesized adapter config")

    rs = sub.add_parser("rescrape", help="re-read a house's listing page: facts and media, "
                                         "keeping status, notes, scores, price and our photos")
    rs.add_argument("--house", required=True)
    rs.add_argument("--no-browser", action="store_true",
                    help="disable the patchright Lane B fallback")

    sv = sub.add_parser("serve")
    sv.add_argument("--host", default="127.0.0.1",
                    help="bind address; the systemd unit passes $HT_HOST")
    sv.add_argument("--port", type=int, default=8765)

    args = p.parse_args(argv)
    store = HouseStore(args.db)

    if args.cmd == "add-house":
        h = store.add_house(
            {"address": args.address, "price_dkk": args.price, "size_m2": args.size},
            now=_today())
        print(h.id, file=out)
    elif args.cmd == "add-person":
        print(store.add_person(args.name).id, file=out)
    elif args.cmd == "add-criterion":
        c = store.add_criterion(
            {"key": args.key, "label": args.label, "kind": args.kind,
             "weight": args.weight, "auto_source": args.auto_source,
             "higher_is_better": not args.lower_better}, now=_today())
        print(c.id, file=out)
    elif args.cmd == "score":
        store.upsert_score(args.house, args.person, args.criterion, args.value,
                          now=_today())
        print("ok", file=out)
    elif args.cmd == "delete-house":
        if not store.delete_house(args.house):
            print(f"no house {args.house!r}", file=out)
            return 1
        shutil.rmtree(Path(args.db).resolve().parent / "houses" / args.house,
                      ignore_errors=True)
        print(f"deleted {args.house}", file=out)
    elif args.cmd == "show":
        h = store.get_house(args.house)
        if not h:
            print(f"no house {args.house!r}", file=out)
            return 1
        print(f"{h.address}  status={h.status}  price/m2={h.price_per_m2}", file=out)
        if h.sold_price_dkk is not None:
            print(f"  sold: {h.sold_price_dkk:.0f} DKK on {h.sold_date}", file=out)
        for c in store.list_commutes(h.id):
            print(f"  {c.mode} -> {c.anchor_ref}: "
                  f"{c.minutes:.0f} min, {c.distance_m:.0f} m", file=out)
        if h.lat is not None and h.lon is not None:
            print(f"  school map: {school_district_map_url(h.lon, h.lat)}", file=out)
    elif args.cmd == "rank":
        houses = store.list_houses()
        crits = store.list_criteria()
        ranked = []
        for h in houses:
            s = scoring.person_overall(h, args.person, houses, crits,
                                       store.get_scores(h.id))
            ranked.append((h.id, s))
        ranked.sort(key=lambda t: (t[1] is None, -(t[1] or 0)))
        for hid, s in ranked:
            print(f"{hid}\t{'-' if s is None else round(s, 3)}", file=out)
    elif args.cmd == "enrich":
        geocoder = AddressGeocoder()
        key = os.environ.get("HT_ORS_KEY")
        router = ORSRouter(key) if (key and not args.no_route) else None
        if router is None and not args.no_route:
            print("no HT_ORS_KEY set — geocoding + school map only, skipping routing",
                  file=out)
        houses = store.list_houses() if args.all else [store.get_house(args.house)]
        for h in houses:
            if h is None:
                print(f"no house {args.house!r}", file=out)
                return 1
            summary = enrich_house(h, store, geocoder, router, now=_today())
            print(f"{h.id}\tgeocoded={summary['geocoded']} "
                  f"commutes={summary['commutes']} schools={summary['schools']}", file=out)
    elif args.cmd == "status":
        if not store.get_house(args.house):
            print(f"no house {args.house!r}", file=out)
            return 1
        if args.set_status:
            h = store.set_status(args.house, args.set_status, now=_today())
            print(f"{h.id}\tstatus={h.status}", file=out)
        else:
            for e in store.status_history(args.house):
                print(f"  {e['at']}\t{e['status']}", file=out)
    elif args.cmd == "set-sold":
        h = store.get_house(args.house)
        if not h:
            print(f"no house {args.house!r}", file=out)
            return 1
        if h.status != "sold":
            store.set_status(args.house, "sold", now=_today())
        store.set_realized_price(args.house, args.price, args.date, now=_today())
        print(f"{args.house}\tsold={args.price:.0f} date={args.date}", file=out)
    elif args.cmd == "lifecycle":
        online = not args.no_boligsiden
        notify, notify_open = hooks(store)
        summary = run_lifecycle(store, HttpProber(),
                                BoligsidenClient() if online else None, now=_today(),
                                geocoder=AddressGeocoder() if online else None,
                                notify=notify, notify_open=notify_open)
        print(" ".join(f"{k}={v}" for k, v in summary.items()), file=out)
    elif args.cmd == "scrape":
        lane_b = None if args.no_browser else PatchrightFetcher()
        try:
            html = fetch_html(args.url, UrllibFetcher(), lane_b)
        except FetchError as e:
            print(f"fetch failed: {e}", file=out)
            return 1
        data_dir = Path(args.db).resolve().parent
        synth = None
        if not args.no_llm:
            base = data_dir / "adapter_synth"
            synth = InboxSynthesizer(
                base / "requests", base / "responses",
                poke=tmux_poke(os.environ.get("HT_SYNTH_SESSION", "ht-synth"),
                               "docs/adapter-synth-session.md"))

        def _confirm(result, missing):
            print(f"synthesized config for {result.house.get('maegler_chain')}: "
                  f"completeness={result.house.get('scrape_completeness')} "
                  f"missing={missing}", file=out)
            if args.yes:
                return True
            return input("confirm & save this adapter config? [y/N] ").strip().lower() == "y"

        result = resolve(args.url, html, store, synth, now=_today(), confirm=_confirm)
        if not result.house.get("address"):
            print(f"could not parse an address from {args.url}", file=out)
            return 1
        try:
            h = store.add_house(result.house, now=_today())
        except DuplicateHouse as e:
            print(f"{e} as {e.house.id}", file=out)
            return 1
        record_page(store, h.id, args.url, html)
        saved = download_media(store, h.id, result.media, data_dir, now=_today())
        print(f"{h.id}\t{len(saved)} media", file=out)
    elif args.cmd == "rescrape":
        h = store.get_house(args.house)
        if h is None or not h.listing_url:
            print(f"no house {args.house!r} with a listing link", file=out)
            return 1
        try:
            html = fetch_html(h.listing_url, UrllibFetcher(),
                              None if args.no_browser else PatchrightFetcher())
        except FetchError as e:
            print(f"fetch failed: {e}", file=out)
            return 1
        result = resolve(h.listing_url, html, store, None, now=_today())
        store.refresh_from_scrape(h.id, result.house, now=_today())
        record_page(store, h.id, h.listing_url, html)
        saved = replace_scraped_media(store, h.id, result.media,
                                      Path(args.db).resolve().parent, now=_today())
        print(f"{h.id}\t{len(saved)} media", file=out)
    elif args.cmd == "serve":
        # An empty host (HT_HOST unset in the unit's env) would make uvicorn bind every
        # interface, and this app has no login: refuse instead.
        if not args.host.strip():
            print("serve: empty --host; set HT_HOST in ~/.config/housetracker.env", file=out)
            return 1
        # Imported here so the other verbs still run without the `api` extra installed.
        import uvicorn

        from housetracker.api.app import create_app

        web_dir = Path(__file__).resolve().parent.parent / "web" / "dist"
        print(f"serving on http://{args.host}:{args.port}", file=out)
        if not (web_dir / "index.html").is_file():
            print(f"web UI not built ({web_dir}); API only", file=out)
        uvicorn.run(create_app(args.db, web_dir=web_dir), host=args.host, port=args.port)
    return 0
