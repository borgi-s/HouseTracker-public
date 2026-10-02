"""Download scraped media into the house's on-disk folder + record media rows. I/O.
Layout: data_dir/houses/<house_id>/{photos,floorplan,pdf,user_photos}/."""
from __future__ import annotations

import re
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

_KIND_DIR = {"photo": "photos", "floorplan": "floorplan",
             "pdf": "pdf", "user_photo": "user_photos"}
_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def house_media_dir(data_dir, house_id: str, kind: str) -> Path:
    d = Path(data_dir) / "houses" / house_id / _KIND_DIR[kind]
    d.mkdir(parents=True, exist_ok=True)
    return d


_HEIF_BRANDS = {b"heic", b"heix", b"heim", b"heis", b"hevc", b"hevx", b"mif1", b"msf1"}
_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
        "image/heic": ".heic", "application/pdf": ".pdf"}


def sniff_type(head: bytes) -> str | None:
    """What the first 16 bytes say a file is, for the kinds we keep — never what its
    name or the sender claims. None = not a type we store or render."""
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head[4:8] == b"ftyp" and head[8:12] in _HEIF_BRANDS:
        return "image/heic"
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    return None


def is_svg(head: bytes) -> bool:
    """An SVG (LokalBolig's floor plans come as SVG only). Checked on the first ~2 KB:
    it starts with markup and an <svg root appears before long."""
    return head.lstrip()[:1] == b"<" and b"<svg" in head[:2048]


def _filename(url: str, fallback_stem: str, data: bytes = b"") -> str:
    name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(urlparse(url).path).name) or fallback_stem
    if not Path(name).suffix:
        # Some image hosts end URLs in e.g. /inline/True; give the file a readable name.
        name += _EXT.get(sniff_type(data[:16]), "")
    return name


def _default_opener(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def download_media(store, house_id: str, media_refs, data_dir, now: str,
                   opener=None) -> list:
    """Download each MediaRef to the house folder and record a media row. `opener(url) ->
    bytes` is injectable for tests (default: stdlib urllib GET). A ref that fails to
    download is skipped — the batch continues. Returns the recorded Media rows."""
    opener = opener or _default_opener
    saved = []
    for i, ref in enumerate(media_refs):
        try:
            data = opener(ref.url)
        except Exception:
            continue  # ponytail: skip a dead URL, never abort the archive of the rest
        path = house_media_dir(data_dir, house_id, ref.kind) / (
            f"{i:03d}-" + _filename(ref.url, f"{ref.kind}{i}", data))
        path.write_bytes(data)
        saved.append(store.add_media(
            {"house_id": house_id, "kind": ref.kind, "path": str(path),
             "source": "scrape", "caption": ref.caption, "sort": i}, now=now))
    return saved


def replace_scraped_media(store, house_id: str, media_refs, data_dir, now: str,
                          opener=None) -> list:
    """Swap a house's scraped media for a fresh set; photos we added ourselves stay. No
    fresh refs = keep the old set. The old files go first, so the fresh downloads'
    numbered names never collide with them."""
    if not media_refs:
        return []
    root = Path(data_dir).resolve()
    for m in store.list_media(house_id):
        if m.source == "scrape":
            path = Path(m.path).resolve()
            if path.is_relative_to(root):          # never touch a file outside the archive
                path.unlink(missing_ok=True)
            store.delete_media(m.id)
    return download_media(store, house_id, media_refs, data_dir, now=now, opener=opener)
