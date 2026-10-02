import pytest
from fastapi.testclient import TestClient

from housetracker.api.app import create_app


@pytest.fixture
def api(tmp_path):
    """TestClient over a throwaway db + data dir. Cookies persist across calls on one
    client, which is what the session tests rely on."""
    return TestClient(create_app(tmp_path / "data" / "ht.db", tmp_path / "data"))


@pytest.fixture(autouse=True)
def _no_school_network(monkeypatch):
    """Every enrich now resolves district schools; no test may reach GeoFA or
    skolegang.dk. Tests of the resolver pass their own fetch/geofa fakes."""
    def refuse(url):
        raise RuntimeError(f"network disabled in tests: {url}")
    monkeypatch.setattr("housetracker.enrich.schools._get_text", refuse)
