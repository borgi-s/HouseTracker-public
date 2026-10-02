import pytest

from housetracker.model import ValidationError
from housetracker.scrape.autoadapter import validate_config


def test_accepts_and_cleans_a_good_config():
    raw = {
        "fields": {"address": {"selector": " .addr ", "attr": "text"},
                   "price_dkk": {"selector": ".price", "attr": "text"}},
        "media": {"pdf": {"selector": "a.doc", "attr": "href"}},
        "junk_top_level": 123,          # ignored, not copied through
    }
    out = validate_config(raw)
    assert out == {
        "fields": {"address": {"selector": " .addr ", "attr": "text"},
                   "price_dkk": {"selector": ".price", "attr": "text"}},
        "media": {"pdf": {"selector": "a.doc", "attr": "href"}},
    }


def test_rejects_non_dict():
    with pytest.raises(ValidationError):
        validate_config(["not", "a", "dict"])


def test_rejects_unknown_field_key():
    with pytest.raises(ValidationError):
        validate_config({"fields": {"evil": {"selector": ".x", "attr": "text"}}})


def test_rejects_unknown_attr():
    with pytest.raises(ValidationError):
        validate_config({"fields": {"address": {"selector": ".x", "attr": "onclick"}}})


def test_rejects_non_string_selector():
    with pytest.raises(ValidationError):
        validate_config({"fields": {"address": {"selector": 42, "attr": "text"}}})


def test_rejects_empty_config():
    with pytest.raises(ValidationError):
        validate_config({"fields": {}, "media": {}})
