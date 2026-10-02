"""Map tiles that need our Dataforsyningen token: the plots (matrikler) and the cloudburst
map (the elevation model's bluespots). The browser asks us and we add the token, so it
never reaches a page, then pass the WMS tile straight back."""
from __future__ import annotations

import logging
import os
import urllib.error
import urllib.parse
import urllib.request

from fastapi import APIRouter, HTTPException, Request, Response

router = APIRouter(prefix="/api", tags=["maps"])
log = logging.getLogger(__name__)

_WMS = {
    "plots": "https://api.dataforsyningen.dk/wms/MatGaeldendeOgForeloebigWMS_DAF",
    "elevation": "https://api.dataforsyningen.dk/wms/dhm",
}


def opener(url: str) -> tuple[bytes, str]:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return resp.read(), resp.headers.get_content_type()


@router.get("/wms/{service}")
def wms(service: str, request: Request) -> Response:
    base = _WMS.get(service)
    if base is None:
        raise HTTPException(status_code=404, detail=f"no map service {service!r}")
    token = os.environ.get("HT_DATAFORSYNINGEN_TOKEN")
    if not token:
        raise HTTPException(status_code=503, detail="no Dataforsyningen token (HT_DATAFORSYNINGEN_TOKEN)")
    # Leaflet sends transparent=true; the plot service only takes TRUE or FALSE.
    params = [(k, v.upper() if k.lower() == "transparent" else v)
              for k, v in request.query_params.multi_items() if k.lower() != "token"]
    # Upstream errors can echo the request URL, token included: the journal gets them
    # with the token blanked, the browser only a generic line.
    try:
        body, kind = opener(f"{base}?{urllib.parse.urlencode([*params, ('token', token)])}")
    except (urllib.error.URLError, OSError) as e:
        log.warning("wms %s unreachable: %s", service, str(e).replace(token, "[token]"))
        raise HTTPException(status_code=502, detail="the map service is unreachable") from None
    if not kind.startswith("image/"):         # a WMS error comes back as XML, status 200
        log.warning("wms %s error: %s", service, body[:300].decode(errors="replace").replace(token, "[token]"))
        raise HTTPException(status_code=502, detail="the map service sent an error, not a tile")
    return Response(body, media_type=kind, headers={"Cache-Control": "public, max-age=604800"})
