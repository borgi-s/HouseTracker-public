# tests/test_lifecycle_notify.py
from housetracker.lifecycle.notify import DiscordWebhook, drop_message, from_env
from housetracker.model import House

import pytest


@pytest.fixture(autouse=True)
def _app_url(monkeypatch):
    monkeypatch.setenv("HT_APP_URL", "http://ht.example:8765/")

H = House(address="Grøndalvej 133A", id="gr-ndalvej-133a", postal_code="2830", city="Virum")


def test_drop_message():
    assert drop_message(H, 8_995_000, 8_595_000, 9_195_000) == (
        "↓ Price drop: Grøndalvej 133A, 2830 Virum\n"
        "8.995.000 kr → 8.595.000 kr (−400.000 kr, −4,4 %)\n"
        "Down 6,5 % since it was listed\n"
        "http://ht.example:8765/house/gr-ndalvej-133a")


def test_a_first_cut_has_no_since_listed_line():
    assert "since it was listed" not in drop_message(H, 8_995_000, 8_595_000, 8_995_000)
    assert "since it was listed" not in drop_message(H, 8_995_000, 8_595_000, None)


def test_webhook_posts_the_message_and_mentions_nobody():
    sent = []
    hook = DiscordWebhook("https://discord.test/hook", post=lambda url, body: sent.append((url, body)))
    hook(H, 9_000_000, 8_500_000, None)
    [(url, body)] = sent
    assert url == "https://discord.test/hook"
    assert body["allowed_mentions"] == {"parse": []}
    assert body["content"].startswith("↓ Price drop: Grøndalvej 133A")


def test_from_env(monkeypatch):
    monkeypatch.delenv("HT_DISCORD_WEBHOOK", raising=False)
    assert from_env() is None
    monkeypatch.setenv("HT_DISCORD_WEBHOOK", "https://discord.test/hook")
    assert from_env().url == "https://discord.test/hook"


from housetracker.lifecycle.notify import open_house_message

OH = House(address="Grøndalvej 133A", id="gr-ndalvej-133a", postal_code="2830", city="Virum",
           listing_url="https://www.estate.dk/raekkehus/2830/groendalvej/n593610/n5936100000376")


def _slot(start, end, signup, url=None):
    return {"starts_at": start, "ends_at": end, "signup": signup, "signup_url": url}


def test_open_house_message_lists_the_new_slots_in_danish_time():
    msg = open_house_message(OH, [
        _slot("2026-10-04T13:30:00Z", "2026-10-04T13:50:00Z", True, "https://www.estate.dk/tilmeld"),
        _slot("2026-10-11T08:00:00Z", "2026-10-11T08:30:00Z", False),
        _slot("2026-11-01T12:00:00Z", "2026-11-01T12:20:00Z", None)])       # winter time
    assert msg == (
        "Open house: Grøndalvej 133A, 2830 Virum\n"
        "Sun 4 Oct 15:30–15:50 · sign-up: <https://www.estate.dk/tilmeld>\n"
        "Sun 11 Oct 10:00–10:30 · drop-in\n"
        "Sun 1 Nov 13:00–13:20\n"
        "http://ht.example:8765/house/gr-ndalvej-133a")


def test_sign_up_without_its_own_link_points_at_the_listing():
    msg = open_house_message(OH, [_slot("2026-10-04T13:30:00Z", "2026-10-04T13:50:00Z", True)])
    assert f"· sign-up: <{OH.listing_url}>" in msg
    bare = House(address="Nyvej 2", id="nyvej-2")
    assert open_house_message(bare, [_slot("2026-10-04T13:30:00Z", "2026-10-04T13:50:00Z", True)]
                              ).splitlines()[:2] == ["Open house: Nyvej 2", "Sun 4 Oct 15:30–15:50 · sign-up"]


def test_webhook_posts_open_houses_and_mentions_nobody():
    sent = []
    hook = DiscordWebhook("https://discord.test/hook", post=lambda url, body: sent.append((url, body)))
    hook.open_houses(OH, [_slot("2026-10-04T13:30:00Z", "2026-10-04T13:50:00Z", False)])
    [(url, body)] = sent
    assert body["allowed_mentions"] == {"parse": []}
    assert body["content"].startswith("Open house: Grøndalvej 133A")


def test_the_link_defaults_to_localhost(monkeypatch):
    monkeypatch.delenv("HT_APP_URL")
    assert drop_message(H, 2, 1, None).endswith("http://localhost:8765/house/gr-ndalvej-133a")
