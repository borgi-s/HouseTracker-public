"""Fetch listing HTML. Lane A = stdlib urllib (fast, plain HTTP). Lane B = patchright
stealth browser (Task 5) for hosts that block Lane A. Escalation is policy; the fetchers
are seams so both lanes are trivially faked in tests."""
from __future__ import annotations

import urllib.request
from typing import Protocol

_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


class FetchError(Exception):
    """A URL could not be retrieved by a fetcher."""


class Fetcher(Protocol):
    def fetch(self, url: str) -> str: ...


class UrllibFetcher:
    """Lane A: one plain-HTTP GET via stdlib. Raises FetchError on any HTTP/network
    failure (incl. 403/429 anti-bot) so the caller can escalate to Lane B."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def fetch(self, url: str) -> str:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                return resp.read().decode(charset, errors="replace")
        except Exception as e:  # URLError, HTTPError, timeout, decode
            raise FetchError(f"lane A failed for {url}: {e}") from e


def _looks_empty(html: str) -> bool:
    """A 200 too short to carry a listing (JS shell) — worth escalating to Lane B."""
    return len(html.strip()) < 500


def fetch_html(url: str, lane_a: Fetcher, lane_b: Fetcher | None = None) -> str:
    """Try Lane A; on failure or an empty/JS-shell body, fall back to Lane B when given.
    Raises FetchError if Lane A fails and no Lane B is available."""
    html, problem = None, ""
    try:
        html = lane_a.fetch(url)
        if not _looks_empty(html):
            return html
        problem = "lane A returned an empty/JS-shell body"
    except FetchError as e:
        problem = str(e)
    if lane_b is None:
        if html is not None:
            return html  # empty, but nothing better available
        raise FetchError(problem)
    return lane_b.fetch(url)


class PatchrightFetcher:
    """Lane B: fully-rendered HTML via a patchright (stealth Playwright) browser, reusing
    the JobSearch lane_b launch config. Heavy: needs `patchright` + a Chrome/Chromium
    install (`pip install '.[scrape]'` then `patchright install chromium`). patchright is
    imported lazily so Lane A stays dependency-free.

    ponytail: env knob — headless=True works headless; for the highest-stealth profile run
    headed under Xvfb (headless=False, DISPLAY=:99, a persistent profile_dir) like
    JobSearch's start-browser-patchright.py. Default is plain headless.
    """

    def __init__(self, profile_dir: str | None = None, headless: bool = True,
                 timeout_ms: int = 30000):
        self.profile_dir = profile_dir
        self.headless = headless
        self.timeout_ms = timeout_ms

    def fetch(self, url: str) -> str:
        try:
            from patchright.sync_api import sync_playwright
        except ImportError as e:
            raise FetchError("patchright not installed (pip install '.[scrape]')") from e
        try:
            with sync_playwright() as p:
                if self.profile_dir:
                    ctx = p.chromium.launch_persistent_context(
                        user_data_dir=self.profile_dir, channel="chrome",
                        headless=self.headless, no_viewport=True,
                        args=["--disable-blink-features=AutomationControlled",
                              "--no-first-run", "--no-default-browser-check"])
                    page = ctx.pages[0] if ctx.pages else ctx.new_page()
                    closer = ctx
                else:
                    browser = p.chromium.launch(headless=self.headless)
                    page = browser.new_page()
                    closer = browser
                page.goto(url, wait_until="networkidle", timeout=self.timeout_ms)
                html = page.content()
                closer.close()
                return html
        except FetchError:
            raise
        except Exception as e:
            raise FetchError(f"lane B (patchright) failed for {url}: {e}") from e
