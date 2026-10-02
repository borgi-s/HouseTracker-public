from urllib.parse import parse_qs, urlsplit


def test_wms_adds_our_token_and_passes_the_tile_back(api, monkeypatch):
    seen = []
    monkeypatch.setenv("HT_DATAFORSYNINGEN_TOKEN", "tok")
    monkeypatch.setattr("housetracker.api.maps.opener",
                        lambda url: seen.append(url) or (b"PNG", "image/png"))
    r = api.get("/api/wms/plots?service=WMS&request=GetMap&layers=MatrikelSkel_Gaeldende"
                "&transparent=true&token=someone-elses")
    assert (r.status_code, r.content, r.headers["content-type"]) == (200, b"PNG", "image/png")
    assert seen[0].startswith("https://api.dataforsyningen.dk/wms/MatGaeldendeOgForeloebigWMS_DAF?")
    q = parse_qs(urlsplit(seen[0]).query)
    assert (q["token"], q["transparent"], q["layers"]) == (["tok"], ["TRUE"], ["MatrikelSkel_Gaeldende"])


def test_wms_names_only_its_services_and_says_when_the_token_is_missing(api, monkeypatch):
    monkeypatch.delenv("HT_DATAFORSYNINGEN_TOKEN", raising=False)
    assert api.get("/api/wms/anything").status_code == 404
    assert api.get("/api/wms/plots").status_code == 503


def test_an_upstream_error_is_a_502_that_never_shows_the_token(api, monkeypatch, caplog):
    monkeypatch.setenv("HT_DATAFORSYNINGEN_TOKEN", "sekret-token")
    monkeypatch.setattr("housetracker.api.maps.opener",            # servers echo the request
                        lambda url: (f"<ServiceExceptionReport>{url}</ServiceExceptionReport>".encode(),
                                     "application/vnd.ogc.se_xml"))
    r = api.get("/api/wms/elevation?request=GetMap")
    assert r.status_code == 502 and "sekret-token" not in r.text

    def unreachable(url):
        raise OSError(f"cannot open {url}")
    monkeypatch.setattr("housetracker.api.maps.opener", unreachable)
    r = api.get("/api/wms/plots?request=GetMap")
    assert r.status_code == 502 and "sekret-token" not in r.text
    assert "sekret-token" not in caplog.text and "[token]" in caplog.text
