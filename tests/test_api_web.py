import pytest
from fastapi.testclient import TestClient

from housetracker.api.app import create_app


@pytest.fixture
def web(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>app shell</html>")
    (dist / "assets" / "app.js").write_text("console.log('app')")
    (tmp_path / "secret.txt").write_text("secret")
    return TestClient(create_app(tmp_path / "data" / "ht.db", tmp_path / "data",
                                 web_dir=dist))


def test_root_and_client_routes_get_the_app_shell(web):
    for path in ("/", "/house/nyvej-2", "/settings"):
        r = web.get(path)
        assert r.status_code == 200 and "app shell" in r.text


def test_built_assets_are_served_as_files(web):
    r = web.get("/assets/app.js")
    assert r.status_code == 200 and r.text == "console.log('app')"


def test_api_routes_still_win_and_unknown_api_paths_stay_json_404(web):
    assert web.get("/api/health").json()["ok"] is True
    r = web.get("/api/nope")
    assert r.status_code == 404 and r.json() == {"detail": "Not Found"}


def test_paths_cannot_escape_the_web_dir(web):
    assert "secret" not in web.get("/..%2Fsecret.txt").text


def test_without_a_build_only_the_api_is_served(tmp_path):
    c = TestClient(create_app(tmp_path / "ht.db", web_dir=tmp_path / "missing"))
    assert c.get("/").status_code == 404
    assert c.get("/api/health").status_code == 200


def test_the_app_shell_is_revalidated_so_a_deploy_never_strands_a_phone(web):
    # A cached index.html points at hashed assets the next build deletes.
    for path in ("/", "/house/nyvej-2"):
        assert web.get(path).headers["cache-control"] == "no-cache"
