"""One end-to-end smoke through the built frontend (M7 spec §8): pick a person, add a
house by hand, tap a score, see the overall move. Skips unless web/dist is built
(`cd web && npm run build`) and a patchright browser can launch."""
import importlib.util
import socket
import threading
import time
from pathlib import Path

import pytest

DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
pytestmark = [
    pytest.mark.skipif(not (DIST / "index.html").is_file(), reason="web/dist not built"),
    pytest.mark.skipif(importlib.util.find_spec("patchright") is None,
                       reason="patchright not installed"),
]


class _NoGeocoder:
    """The add flow fires enrich; keep the test off the real DAWA API."""

    def geocode(self, address):
        return None


@pytest.fixture
def server(tmp_path, monkeypatch):
    import uvicorn

    from housetracker.api.app import create_app
    from housetracker.store import HouseStore

    monkeypatch.setattr("housetracker.api.admin.AddressGeocoder", _NoGeocoder)
    monkeypatch.delenv("HT_ORS_KEY", raising=False)
    db = tmp_path / "data" / "ht.db"
    store = HouseStore(db)
    store.add_criterion({"key": "light", "label": "Light", "kind": "subjective"},
                        now="2026-09-21")
    store.conn.close()

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(create_app(db, web_dir=DIST), host="127.0.0.1",
                                        port=port, log_level="warning"))
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not srv.started:
        if time.time() > deadline:
            pytest.fail("server did not start")
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    thread.join(timeout=5)


def test_pick_person_add_house_and_score(server):
    from patchright.sync_api import sync_playwright

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Exception as e:                 # no browser installed on this box
            pytest.skip(f"no launchable browser: {e}")
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(server)

        page.get_by_label("New person").fill("Alex")
        page.get_by_role("button", name="Add", exact=True).click()
        page.get_by_role("button", name="Alex").click()

        page.get_by_role("link", name="Add house").click()
        page.get_by_role("button", name="No link — enter by hand").click()
        page.get_by_label("Address").fill("Kvikvej 1, 2800")
        page.get_by_label("Price (kr)").fill("4200000")
        page.get_by_role("button", name="Add house").click()

        page.get_by_role("heading", name="Kvikvej 1, 2800").wait_for()
        page.get_by_role("button", name="Light 4").click()
        page.get_by_role("img", name="Alex 4.0").wait_for()   # 4 of 5 -> 0.8 -> shown x5
        browser.close()
