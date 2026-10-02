import builtins
import importlib.util

import pytest
from housetracker.scrape.fetch import FetchError, PatchrightFetcher

_HAS_PATCHRIGHT = importlib.util.find_spec("patchright") is not None


def test_missing_patchright_raises_fetcherror(monkeypatch):
    """Absent patchright must surface as FetchError, not a leaked ImportError."""
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name.startswith("patchright"):
            raise ImportError("no patchright")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(FetchError):
        PatchrightFetcher().fetch("https://x.dk/1")


@pytest.mark.skipif(not _HAS_PATCHRIGHT, reason="patchright not installed")
def test_patchright_smoke_data_url():
    """Real-browser smoke test — runs only where patchright AND a browser exist;
    skips (not fails) when no browser is launchable, so the suite stays green in CI."""
    try:
        html = PatchrightFetcher(headless=True).fetch(
            "data:text/html,<html><body>hello-lane-b</body></html>")
    except FetchError as e:
        pytest.skip(f"no launchable browser: {e}")
    assert "hello-lane-b" in html
