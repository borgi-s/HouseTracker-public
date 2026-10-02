import json

from housetracker.store import HouseStore


def _store(tmp_path):
    return HouseStore(tmp_path / "data" / "ht.db")


def test_adapter_config_table_exists(tmp_path):
    assert "adapter_config" in _store(tmp_path).table_names()


def test_upsert_get_roundtrip(tmp_path):
    s = _store(tmp_path)
    sel = json.dumps({"fields": {"address": {"selector": ".a", "attr": "text"}}})
    s.upsert_adapter_config("nybolig.dk", sel, completeness_last=0.71,
                            source="llm", confirmed=False, now="2026-09-14")
    cfg = s.get_adapter_config("nybolig.dk")
    assert cfg is not None
    assert cfg.chain == "nybolig.dk"
    assert cfg.source == "llm"
    assert cfg.confirmed is False
    assert cfg.completeness_last == 0.71
    assert cfg.selectors()["fields"]["address"]["selector"] == ".a"
    assert s.get_adapter_config("unknown.dk") is None


def test_upsert_replaces_and_preserves_created_at(tmp_path):
    s = _store(tmp_path)
    s.upsert_adapter_config("edc.dk", "{}", 0.5, "llm", False, now="2026-09-14")
    created = s.get_adapter_config("edc.dk").created_at
    s.upsert_adapter_config("edc.dk", '{"fields":{}}', 0.9, "llm", False,
                            now="2026-09-20")
    cfg = s.get_adapter_config("edc.dk")
    assert cfg.completeness_last == 0.9          # updated
    assert cfg.created_at == created             # preserved
    assert cfg.updated_at == "2026-09-20"        # bumped


def test_confirm_flips_flag(tmp_path):
    s = _store(tmp_path)
    s.upsert_adapter_config("home.dk", "{}", 0.8, "llm", False, now="2026-09-14")
    assert s.get_adapter_config("home.dk").confirmed is False
    s.confirm_adapter_config("home.dk", now="2026-09-15")
    cfg = s.get_adapter_config("home.dk")
    assert cfg.confirmed is True
    assert cfg.updated_at == "2026-09-15"


def test_bad_source_rejected(tmp_path):
    from housetracker.model import AdapterConfig, ValidationError
    import pytest
    with pytest.raises(ValidationError):
        AdapterConfig.from_dict({"chain": "x.dk", "selectors_json": "{}",
                                 "source": "bogus"})
