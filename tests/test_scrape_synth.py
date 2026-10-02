import json

from housetracker.scrape.parse import MediaRef, ScrapeResult
from housetracker.scrape.synth import (
    InboxSynthesizer, SynthesisError, build_poke_command, fetch_pdf_text, prune_dom,
)


def test_prune_dom_strips_scripts_styles_comments():
    html = ('<style>.x{color:red}</style><script>evil()</script>'
            '<!-- secret --><h1 class="a">Hi</h1>')
    out = prune_dom(html)
    assert "evil()" not in out
    assert "color:red" not in out
    assert "secret" not in out
    assert 'class="a"' in out and "Hi" in out


def test_prune_dom_truncates():
    assert len(prune_dom("<p>" + "x" * 10000 + "</p>", max_chars=100)) == 100


def test_build_poke_command_shape():
    cmd = build_poke_command("ht-synth", "/reqs/5.json", "docs/adapter-synth-session.md")
    assert cmd[:4] == ["tmux", "send-keys", "-t", "ht-synth"]
    assert cmd[-1] == "Enter"
    assert "/reqs/5.json" in cmd[4]
    assert "adapter-synth-session.md" in cmd[4]


def test_fetch_pdf_text_swallows_errors():
    def boom(url):
        raise OSError("no network")
    assert fetch_pdf_text("http://x/s.pdf", opener=boom) == ""


def test_inbox_handshake_writes_request_pokes_and_reads_response(tmp_path):
    reqs, resps = tmp_path / "requests", tmp_path / "responses"
    canned = {"fields": {"address": {"selector": ".a", "attr": "text"}}}
    poked = {}

    def poke(req_path):
        # Simulate the running session: read the request, write the response.
        payload = json.loads((tmp_path / req_path).read_text()
                             if not req_path.startswith("/") else
                             open(req_path).read())
        poked["payload"] = payload
        open(payload["response_path"], "w").write(json.dumps(canned))

    synth = InboxSynthesizer(reqs, resps, poke=poke, poll_s=0)
    result = ScrapeResult(house={"address": "?"},
                          media=[MediaRef("pdf", "http://x/s.pdf")])
    out = synth.synthesize("https://ny.dk/b/1", "<h1 class='a'>X</h1>", result)
    assert out == canned
    assert poked["payload"]["url"] == "https://ny.dk/b/1"
    assert "pruned_html" in poked["payload"] and "field_spec" in poked["payload"]


def test_inbox_times_out_without_response(tmp_path):
    synth = InboxSynthesizer(tmp_path / "q", tmp_path / "a",
                             poke=lambda p: None, timeout_s=0, poll_s=0)
    try:
        synth.synthesize("https://ny.dk/1", "<html></html>",
                         ScrapeResult(house={}, media=[]))
        assert False, "expected SynthesisError"
    except SynthesisError:
        pass
