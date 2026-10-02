import http.server
import socketserver
import threading

import pytest
from housetracker.scrape.fetch import FetchError, UrllibFetcher, fetch_html


class _Fake:
    def __init__(self, html=None, err=None):
        self.html, self.err, self.calls = html, err, 0

    def fetch(self, url):
        self.calls += 1
        if self.err:
            raise FetchError(self.err)
        return self.html


_BIG = "<html>" + "x" * 600 + "</html>"


def test_lane_a_success_skips_lane_b():
    a, b = _Fake(html=_BIG), _Fake(html="from B")
    assert fetch_html("https://x.dk/1", a, b) == _BIG
    assert b.calls == 0


def test_lane_a_failure_escalates_to_lane_b():
    a, b = _Fake(err="403 blocked"), _Fake(html=_BIG)
    assert fetch_html("https://x.dk/1", a, b) == _BIG
    assert b.calls == 1


def test_empty_body_escalates_to_lane_b():
    a, b = _Fake(html="<html></html>"), _Fake(html=_BIG)  # A body < 500 chars
    assert fetch_html("https://x.dk/1", a, b) == _BIG


def test_no_lane_b_raises_on_failure():
    with pytest.raises(FetchError):
        fetch_html("https://x.dk/1", _Fake(err="timeout"), None)


def test_urllib_fetcher_reads_local_server():
    body = b"<html>" + b"o" * 600 + b"</html>"

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = socketserver.TCPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        port = srv.server_address[1]
        html = UrllibFetcher().fetch(f"http://127.0.0.1:{port}/x")
        assert "ooo" in html
    finally:
        srv.shutdown()
