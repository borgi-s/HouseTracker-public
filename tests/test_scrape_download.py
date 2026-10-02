from housetracker.store import HouseStore
from housetracker.scrape.parse import MediaRef
from housetracker.scrape.download import download_media, house_media_dir


def _store(tmp_path):
    s = HouseStore(tmp_path / "ht.db")
    s.add_house({"address": "A"}, now="2026-09-13")
    return s


def test_media_dir_maps_kind_to_subdir(tmp_path):
    d = house_media_dir(tmp_path / "data", "a", "photo")
    assert d.as_posix().endswith("houses/a/photos")
    assert house_media_dir(tmp_path / "data", "a", "user_photo").as_posix().endswith("user_photos")


def test_download_writes_files_and_rows(tmp_path):
    s = _store(tmp_path)
    refs = [MediaRef(kind="photo", url="https://cdn/x/1.jpg"),
            MediaRef(kind="pdf", url="https://cdn/x/salg.pdf", caption="Salgsopstilling")]
    fake = {"https://cdn/x/1.jpg": b"JPEGDATA", "https://cdn/x/salg.pdf": b"%PDF-1.4"}
    saved = download_media(s, "a", refs, tmp_path / "data", now="2026-09-13",
                           opener=lambda u: fake[u])
    assert len(saved) == 2
    photo = next(m for m in s.list_media("a") if m.kind == "photo")
    assert open(photo.path, "rb").read() == b"JPEGDATA"
    assert "houses/a/photos/" in photo.path.replace("\\", "/")
    pdf = next(m for m in s.list_media("a") if m.kind == "pdf")
    assert pdf.caption == "Salgsopstilling"


def test_download_skips_failures_without_aborting(tmp_path):
    s = _store(tmp_path)
    refs = [MediaRef(kind="photo", url="https://ok/1.jpg"),
            MediaRef(kind="photo", url="https://bad/2.jpg")]

    def opener(u):
        if "bad" in u:
            raise OSError("404")
        return b"OK"

    saved = download_media(s, "a", refs, tmp_path / "data", now="2026-09-13", opener=opener)
    assert len(saved) == 1
    assert len(s.list_media("a")) == 1


def test_a_url_without_an_extension_gets_one_from_the_bytes(tmp_path):
    # Estate's image URLs end in /inline/True — no extension, so the file would be
    # served as application/octet-stream.
    s = _store(tmp_path)
    refs = [MediaRef(kind="photo", url="https://m.example/api/media/1/inline/True?w=2100"),
            MediaRef(kind="pdf", url="https://m.example/doc/salg")]
    fake = {refs[0].url: b"\xff\xd8\xff\xe0JFIF", refs[1].url: b"%PDF-1.7"}
    download_media(s, "a", refs, tmp_path / "data", now="2026-09-22", opener=lambda u: fake[u])
    assert sorted(m.path.rsplit("/", 1)[1] for m in s.list_media("a")) == ["000-True.jpg", "001-salg.pdf"]
