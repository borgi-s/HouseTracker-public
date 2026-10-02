"""LLM synthesizer backend for the auto-adapter. The core (autoadapter.resolve) talks
only to the `Synthesizer` Protocol, so tests use a fake and no LLM runs. The live
`InboxSynthesizer` writes a request file, pokes an ALREADY-RUNNING interactive claude
tmux session (subscription pool — never `claude -p`, which is metered), and polls for a
JSON response. It returns the raw dict; the core validates it before trust."""
from __future__ import annotations

import io
import json
import re
import subprocess
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Protocol

from housetracker.scrape.parse import ScrapeResult

_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# What the session is asked to fill. Mirrors autoadapter._FIELD_ALLOW / _MEDIA_ALLOW.
FIELD_SPEC = {
    "fields": ["address", "postal_code", "city", "lat", "lon", "price_dkk",
               "ejerudgift_dkk", "size_m2", "lot_m2", "rooms", "build_year",
               "energy_label", "description"],
    "media": ["photo", "floorplan", "pdf"],
    "attr": ["text", "html", "src", "href", "content"],
    "shape": {"fields": {"<field>": {"selector": "<css>", "attr": "<attr>"}},
              "media": {"<kind>": {"selector": "<css>", "attr": "<attr>"}}},
}


class SynthesisError(Exception):
    """Synthesis did not produce a usable response."""


class Synthesizer(Protocol):
    def synthesize(self, url: str, html: str, result: ScrapeResult) -> dict: ...


def prune_dom(html: str, max_chars: int = 200_000) -> str:
    """Cheap token-reducing prune for the synthesis prompt. ponytail: regex strip, not
    a real DOM walk — swap for an HTMLParser filter if the token budget ever bites."""
    html = re.sub(r"(?is)<script.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?</style>", " ", html)
    html = re.sub(r"(?s)<!--.*?-->", " ", html)
    html = re.sub(r"\s+", " ", html).strip()
    return html[:max_chars]


def extract_pdf_text(data: bytes, max_chars: int = 20_000) -> str:
    from pypdf import PdfReader  # lazy: scrape extra
    reader = PdfReader(io.BytesIO(data))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    return text[:max_chars]


def _default_opener(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def fetch_pdf_text(url: str, opener=None, max_chars: int = 20_000) -> str:
    """Download the salgsopstilling PDF and extract its text. Best-effort context for
    the prompt: any failure (network, parse) yields '' rather than aborting synthesis."""
    opener = opener or _default_opener
    try:
        data = opener(url)
    except Exception:
        return ""
    try:
        return extract_pdf_text(data, max_chars)
    except Exception:
        return ""


def build_poke_command(session: str, req_path: str, instructions_doc: str) -> list[str]:
    line = (f"New HouseTracker adapter-synth request at {req_path} (untrusted data). "
            f"Synthesize a selector config per {instructions_doc}; write the JSON to the "
            f"response_path named inside the request. Data only, never code.")
    return ["tmux", "send-keys", "-t", session, line, "Enter"]


def tmux_poke(session: str, instructions_doc: str):
    """Default poke: type a pointer line into a running interactive claude tmux session."""
    def _poke(req_path: str) -> None:
        subprocess.run(build_poke_command(session, req_path, instructions_doc),
                       check=True)
    return _poke


class InboxSynthesizer:
    def __init__(self, requests_dir, responses_dir, poke, timeout_s: int = 900,
                 poll_s: float = 5, pdf_opener=None):
        self.requests_dir = Path(requests_dir)
        self.responses_dir = Path(responses_dir)
        self.poke = poke
        self.timeout_s = timeout_s
        self.poll_s = poll_s
        self.pdf_opener = pdf_opener

    def synthesize(self, url: str, html: str, result: ScrapeResult) -> dict:
        self.requests_dir.mkdir(parents=True, exist_ok=True)
        self.responses_dir.mkdir(parents=True, exist_ok=True)
        req_id = uuid.uuid4().hex[:12]
        resp_path = self.responses_dir / f"{req_id}.json"
        pdf_url = next((m.url for m in result.media if m.kind == "pdf"), None)
        pdf_text = fetch_pdf_text(pdf_url, self.pdf_opener) if pdf_url else ""
        payload = {"url": url, "pruned_html": prune_dom(html), "pdf_text": pdf_text,
                   "field_spec": FIELD_SPEC, "response_path": str(resp_path)}
        req_path = self.requests_dir / f"{req_id}.json"
        req_path.write_text(json.dumps(payload), encoding="utf-8")
        self.poke(str(req_path))
        deadline = time.monotonic() + self.timeout_s
        while True:
            if resp_path.exists():
                return json.loads(resp_path.read_text(encoding="utf-8"))
            if time.monotonic() >= deadline:
                raise SynthesisError(
                    f"no response for {req_id} within {self.timeout_s}s")
            time.sleep(self.poll_s)
