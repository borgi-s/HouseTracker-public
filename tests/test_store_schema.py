from housetracker.store import HouseStore

def test_store_creates_schema(tmp_path):
    store = HouseStore(tmp_path / "ht.db")
    tables = store.table_names()
    assert {"house", "person", "criterion", "score", "status_event"} <= tables

def test_store_schema_is_idempotent(tmp_path):
    p = tmp_path / "ht.db"
    HouseStore(p)
    store2 = HouseStore(p)  # reopening must not raise
    assert "house" in store2.table_names()
