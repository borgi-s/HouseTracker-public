# housetracker/api/media.py
"""Serving and receiving media files. Both directions are trust boundaries: stored
paths originate in scraped URLs, and uploads arrive from a phone, so the serve route
refuses anything outside the data dir and the upload route caps size and type."""
from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, Request, UploadFile,
)
from fastapi.responses import FileResponse

from housetracker.api.deps import get_store, today
from housetracker.scrape.download import house_media_dir, is_svg, sniff_type
from housetracker.store import HouseStore

router = APIRouter(prefix="/api", tags=["media"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024        # a phone photo, with room to spare
_CHUNK = 1 << 20

def looks_like_image(head: bytes) -> bool:
    """JPEG, PNG, WebP or HEIC/HEIF by magic bytes. The client's content_type is only a
    claim, and since M7 the browser renders whatever gets uploaded."""
    return (sniff_type(head) or "").startswith("image/")


@router.get("/media/{media_id}/file")
def media_file(media_id: str, request: Request,
               store: HouseStore = Depends(get_store)) -> FileResponse:
    m = store.get_media(media_id)
    if m is None:
        raise HTTPException(status_code=404, detail=f"no media {media_id!r}")
    data_dir = Path(request.app.state.data_dir).resolve()
    path = Path(m.path).resolve()
    if not path.is_file() or not path.is_relative_to(data_dir):
        # Missing on disk, or pointing out of the archive — both are "not found" here.
        raise HTTPException(status_code=404,
                            detail=f"media {media_id!r} is not available")
    # The type comes from the bytes, never the name: an uploaded "x.html" that starts
    # like a JPEG must not render as a page on this origin. Known images and PDFs show
    # inline (the laptop's PDF tab is an <iframe>); anything else downloads. A scraped
    # SVG floor plan shows too, but sandboxed: no script in it runs, even when the file
    # is opened on its own, and it gets no origin to reach the API from. nosniff stops
    # the browser second-guessing any of it.
    with path.open("rb") as fh:
        head = fh.read(2048)
    mime = sniff_type(head[:16])
    headers = {"X-Content-Type-Options": "nosniff"}
    if mime is None and is_svg(head):
        mime = "image/svg+xml"
        headers["Content-Security-Policy"] = "sandbox; default-src 'none'; style-src 'unsafe-inline'"
    return FileResponse(path, filename=path.name,
                        media_type=mime or "application/octet-stream",
                        content_disposition_type="inline" if mime else "attachment",
                        headers=headers)


@router.post("/houses/{house_id}/media", status_code=201)
def upload_media(house_id: str, request: Request,
                 file: UploadFile = File(...),
                 caption: str | None = Form(None),
                 store: HouseStore = Depends(get_store)) -> dict:
    """The phone quick-add photo path (§11). Stored as kind=user_photo / source=manual
    alongside the scraped archive, so §3's 'everything downloaded locally' holds for our
    own snaps too."""
    if store.get_house(house_id) is None:
        raise HTTPException(status_code=404, detail=f"no house {house_id!r}")
    head = file.file.read(16)
    file.file.seek(0)
    if not looks_like_image(head):
        raise HTTPException(status_code=415,
                            detail="only JPEG, PNG, WebP or HEIC images are accepted")

    dest = house_media_dir(request.app.state.data_dir, house_id, "user_photo")
    name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(file.filename or "photo.jpg").name)
    path = dest / f"{uuid.uuid4().hex[:8]}-{name}"

    written = 0
    try:
        with path.open("wb") as fh:
            # UploadFile.file is a SpooledTemporaryFile: readable synchronously, which
            # keeps this route a plain `def` like every other one.
            while chunk := file.file.read(_CHUNK):
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"upload exceeds {MAX_UPLOAD_BYTES} bytes")
                fh.write(chunk)
    except HTTPException:
        path.unlink(missing_ok=True)
        raise

    m = store.add_media({"house_id": house_id, "kind": "user_photo",
                         "path": str(path), "source": "manual", "caption": caption,
                         "sort": len(store.list_media(house_id))}, now=today())
    return {**m.to_dict(), "url": f"/api/media/{m.id}/file"}


@router.delete("/media/{media_id}")
def delete_media(media_id: str, request: Request,
                 store: HouseStore = Depends(get_store)) -> dict:
    """Our own snaps only: the scraped archive is immutable (spec §9)."""
    m = store.get_media(media_id)
    if m is None:
        raise HTTPException(status_code=404, detail=f"no media {media_id!r}")
    if m.source != "manual":
        raise HTTPException(status_code=409,
                            detail="scraped media are part of the archive")
    data_dir = Path(request.app.state.data_dir).resolve()
    path = Path(m.path).resolve()
    if path.is_relative_to(data_dir):          # never touch a file outside the archive
        path.unlink(missing_ok=True)
    store.delete_media(media_id)
    return {"deleted": media_id}
