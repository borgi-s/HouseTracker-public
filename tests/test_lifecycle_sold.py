from housetracker.lifecycle.sold import check_sold, classify


def test_classify_gone_on_404():
    assert classify(404, "https://x.dk/1", "") == "gone"


def test_classify_sold_marker_in_body():
    assert classify(200, "https://x.dk/1", "<h1>Boligen er SOLGT</h1>") == "sold"


def test_classify_sold_marker_in_redirected_url():
    assert classify(200, "https://x.dk/bolig/1/solgt", "<html>ok</html>") == "sold"


def test_classify_listed_on_plain_200():
    assert classify(200, "https://x.dk/1", "<html>Til salg</html>") == "listed"


def test_classify_unknown_on_network_failure():
    assert classify(None, "https://x.dk/1", "") == "unknown"


def test_classify_unknown_on_403():
    # a bot-wall 403 is inconclusive — never mark sold on it
    assert classify(403, "https://x.dk/1", "") == "unknown"


class _FakeProber:
    def __init__(self, result):
        self.result = result

    def probe(self, url):
        return self.result


def test_check_sold_uses_prober():
    assert check_sold("https://x.dk/1", _FakeProber((404, "https://x.dk/1", ""))) == "gone"


def test_check_sold_swallows_prober_errors():
    class Boom:
        def probe(self, url):
            raise OSError("dns down")
    assert check_sold("https://x.dk/1", Boom()) == "unknown"


def test_classify_listed_despite_solgt_in_nav_body():
    # "Solgte boliger" nav link is on active listings — must NOT flip an active house to sold
    html = ('<html><head><title>Til salg: Nyvej 2</title></head>'
            '<body><nav>Solgte boliger</nav><h1>Nyvej 2, 2800</h1>'
            '<p>Se alle solgte boliger her</p></body></html>')
    assert classify(200, "https://x.dk/1", html) == "listed"


def test_probe_listing_hands_back_the_page():
    from housetracker.lifecycle.sold import probe_listing
    page = (200, "https://x.dk/1", "<html>Til salg</html>")
    assert probe_listing("https://x.dk/1", _FakeProber(page)) == ("listed", *page[1:])

    class Boom:
        def probe(self, url):
            raise OSError("down")

    assert probe_listing("https://x.dk/1", Boom()) == ("unknown", "https://x.dk/1", "")
