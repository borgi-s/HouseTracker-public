# tests/test_cli_serve.py
import io

import uvicorn

from housetracker.cli import main


def run(db, *args):
    buf = io.StringIO()
    return main(["--db", str(db), *args], buf), buf.getvalue()


def test_serve_binds_loopback_by_default(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(uvicorn, "run",
                        lambda app, host, port: seen.update(host=host, port=port,
                                                            app=app))
    code, out = run(tmp_path / "ht.db", "serve")
    assert code == 0
    assert seen["host"] == "127.0.0.1" and seen["port"] == 8765
    assert "127.0.0.1:8765" in out


def test_serve_honours_host_and_port(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(uvicorn, "run",
                        lambda app, host, port: seen.update(host=host, port=port))
    code, _ = run(tmp_path / "ht.db", "serve", "--host", "192.0.2.10",
                  "--port", "9000")
    assert code == 0
    assert seen == {"host": "192.0.2.10", "port": 9000}


def test_serve_builds_a_real_app(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(uvicorn, "run",
                        lambda app, host, port: captured.update(app=app))
    run(tmp_path / "ht.db", "serve")
    routes = set(captured["app"].openapi()["paths"])
    assert {"/api/health", "/api/houses", "/api/session"} <= routes


def test_serve_hands_the_app_the_repo_web_build(tmp_path, monkeypatch):
    from pathlib import Path

    import housetracker.cli as cli_mod

    seen = {}
    monkeypatch.setattr("housetracker.api.app.create_app",
                        lambda db, web_dir=None: seen.update(web_dir=web_dir) or object())
    monkeypatch.setattr(uvicorn, "run", lambda app, host, port: None)
    run(tmp_path / "ht.db", "serve")
    assert seen["web_dir"] == Path(cli_mod.__file__).resolve().parent.parent / "web" / "dist"


def test_serve_refuses_an_empty_host(tmp_path, monkeypatch):
    """systemd passes `--host ""` when HT_HOST is unset; uvicorn would then bind every
    interface of an app that has no login."""
    called = []
    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: called.append(1))
    code, out = run(tmp_path / "ht.db", "serve", "--host", " ")
    assert code == 1 and called == []
    assert "HT_HOST" in out
