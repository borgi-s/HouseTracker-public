# tests/test_api_media.py
from pathlib import Path

from housetracker.api.media import looks_like_image
from housetracker.store import HouseStore

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8


def _house(api):
    return api.post("/api/houses", json={"address": "Nyvej 2, 2800"}).json()["id"]


def test_upload_stores_the_file_and_records_it(api):
    hid = _house(api)
    r = api.post(f"/api/houses/{hid}/media",
                 files={"file": ("kitchen.jpg", b"\xff\xd8\xffJPEGBYTES", "image/jpeg")},
                 data={"caption": "Kitchen"})
    assert r.status_code == 201
    m = r.json()
    assert m["kind"] == "user_photo" and m["source"] == "manual"
    assert m["caption"] == "Kitchen"
    assert m["url"] == f"/api/media/{m['id']}/file"
    assert Path(m["path"]).read_bytes() == b"\xff\xd8\xffJPEGBYTES"
    assert "user_photos" in m["path"]
    # and it shows up on the house detail
    assert [x["id"] for x in api.get(f"/api/houses/{hid}").json()["media"]] == [m["id"]]


def test_uploaded_file_is_served_back(api):
    hid = _house(api)
    m = api.post(f"/api/houses/{hid}/media",
                 files={"file": ("kitchen.jpg", b"\xff\xd8\xffJPEGBYTES", "image/jpeg")}
                 ).json()
    r = api.get(m["url"])
    assert r.status_code == 200 and r.content == b"\xff\xd8\xffJPEGBYTES"


def test_non_image_upload_is_rejected(api):
    hid = _house(api)
    r = api.post(f"/api/houses/{hid}/media",
                 files={"file": ("evil.sh", b"rm -rf /", "text/x-shellscript")})
    assert r.status_code == 415


def test_oversize_upload_is_rejected_and_leaves_no_file(api, monkeypatch):
    monkeypatch.setattr("housetracker.api.media.MAX_UPLOAD_BYTES", 8)
    hid = _house(api)
    r = api.post(f"/api/houses/{hid}/media",
                 files={"file": ("big.jpg", b"\xff\xd8\xff" + b"0" * 16, "image/jpeg")})
    assert r.status_code == 413
    data_dir = Path(api.app.state.data_dir)
    assert list(data_dir.rglob("*.jpg")) == []
    assert api.get(f"/api/houses/{hid}").json()["media"] == []


def test_upload_to_an_unknown_house_is_404(api):
    r = api.post("/api/houses/nope/media",
                 files={"file": ("a.jpg", b"x", "image/jpeg")})
    assert r.status_code == 404


def test_serving_refuses_a_path_outside_the_data_dir(api, tmp_path):
    """A media row pointing at /etc/passwd (or anywhere else off the data dir) must not
    be served, whatever put it there."""
    hid = _house(api)
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")
    store = HouseStore(api.app.state.db_path)
    m = store.add_media({"house_id": hid, "kind": "user_photo",
                         "path": str(outside), "source": "manual"}, now="2026-09-20")
    store.conn.close()
    assert api.get(f"/api/media/{m.id}/file").status_code == 404


def test_serving_an_unknown_or_missing_media_is_404(api):
    hid = _house(api)
    m = api.post(f"/api/houses/{hid}/media",
                 files={"file": ("k.jpg", b"\xff\xd8\xffx", "image/jpeg")}).json()
    assert api.get("/api/media/nope/file").status_code == 404
    Path(m["path"]).unlink()
    assert api.get(m["url"]).status_code == 404


def test_magic_bytes_decide_not_the_claimed_type():
    assert looks_like_image(b"\xff\xd8\xff\xe0")
    assert looks_like_image(PNG)
    assert looks_like_image(b"RIFF\x00\x00\x00\x00WEBPVP8 ")
    assert looks_like_image(b"\x00\x00\x00\x18ftypheic")
    assert not looks_like_image(b"GIF89a")
    assert not looks_like_image(b"<html>")


def test_upload_sniffs_bytes_instead_of_trusting_content_type(api):
    hid = _house(api)
    ok = api.post(f"/api/houses/{hid}/media",
                  files={"file": ("p.png", PNG, "application/octet-stream")})
    assert ok.status_code == 201
    lie = api.post(f"/api/houses/{hid}/media",
                   files={"file": ("x.jpg", b"<script>", "image/jpeg")})
    assert lie.status_code == 415


def _upload(api, hid):
    return api.post(f"/api/houses/{hid}/media",
                    files={"file": ("k.jpg", b"\xff\xd8\xffk", "image/jpeg")}).json()


def test_delete_own_photo_removes_row_and_file(api):
    hid = _house(api)
    m = _upload(api, hid)
    assert api.delete(f"/api/media/{m['id']}").json() == {"deleted": m["id"]}
    assert not Path(m["path"]).exists()
    assert api.get(f"/api/houses/{hid}").json()["media"] == []
    assert api.delete(f"/api/media/{m['id']}").status_code == 404


def test_scraped_media_cannot_be_deleted(api):
    hid = _house(api)
    store = HouseStore(api.app.state.db_path)
    m = store.add_media({"house_id": hid, "kind": "photo", "path": "/x/p.jpg"},
                        now="2026-09-21")
    store.conn.close()
    assert api.delete(f"/api/media/{m.id}").status_code == 409
    assert len(api.get(f"/api/houses/{hid}").json()["media"]) == 1


def test_delete_never_touches_a_file_outside_the_data_dir(api, tmp_path):
    hid = _house(api)
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(b"keep me")
    store = HouseStore(api.app.state.db_path)
    m = store.add_media({"house_id": hid, "kind": "user_photo", "path": str(outside),
                         "source": "manual"}, now="2026-09-21")
    store.conn.close()
    assert api.delete(f"/api/media/{m.id}").status_code == 200
    assert outside.read_bytes() == b"keep me"


def test_media_open_in_the_page_rather_than_downloading(api):
    # The laptop's PDF tab is an <iframe>; "attachment" would download it instead.
    hid = _house(api)
    m = api.post(f"/api/houses/{hid}/media",
                 files={"file": ("kitchen.jpg", b"\xff\xd8\xffJPEGBYTES", "image/jpeg")}).json()
    r = api.get(m["url"])
    assert r.headers["content-disposition"].startswith("inline")
    assert r.headers["content-type"] == "image/jpeg"


def test_a_file_named_like_a_page_is_served_as_what_its_bytes_are(api):
    # A JPEG-headed polyglot uploaded as "x.html": the name must not make it a page.
    hid = _house(api)
    m = api.post(f"/api/houses/{hid}/media",
                 files={"file": ("x.html", b"\xff\xd8\xff<script>alert(1)</script>", "image/jpeg")}).json()
    r = api.get(m["url"])
    assert r.headers["content-type"] == "image/jpeg"
    assert r.headers["x-content-type-options"] == "nosniff"


def _scraped(api, name: str, data: bytes) -> str:
    # A scraped download is not sniffed on the way in, so anything can land.
    hid = _house(api)
    f = Path(api.app.state.data_dir) / "houses" / hid / "photos" / name
    f.parent.mkdir(parents=True)
    f.write_bytes(data)
    store = HouseStore(api.app.state.db_path)
    m = store.add_media({"house_id": hid, "kind": "photo", "path": str(f)}, now="2026-09-22")
    store.conn.close()
    return f"/api/media/{m.id}/file"


def test_bytes_of_no_known_type_are_never_shown_inline(api):
    r = api.get(_scraped(api, "000-x.html", b"<html><script>alert(1)</script></html>"))
    assert r.headers["content-disposition"].startswith("attachment")
    assert r.headers["content-type"] == "application/octet-stream"
    assert r.headers["x-content-type-options"] == "nosniff"


def test_an_svg_floor_plan_shows_inline_but_sandboxed_so_its_scripts_never_run(api):
    r = api.get(_scraped(api, "000-x.svg", b'<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg">'
                                          b'<script>alert(1)</script></svg>'))
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert r.headers["content-disposition"].startswith("inline")
    csp = r.headers["content-security-policy"]
    assert csp.startswith("sandbox;") and "default-src 'none'" in csp
    assert r.headers["x-content-type-options"] == "nosniff"


def test_a_pdf_is_served_as_a_pdf_inline(api):
    hid = _house(api)
    pdf = Path(api.app.state.data_dir) / "houses" / hid / "pdf" / "000-salg"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.7 ...")
    store = HouseStore(api.app.state.db_path)
    m = store.add_media({"house_id": hid, "kind": "pdf", "path": str(pdf)}, now="2026-09-22")
    store.conn.close()
    r = api.get(f"/api/media/{m.id}/file")
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"].startswith("inline")
