from housetracker.store import HouseStore

A = {"starts_at": "2026-10-04T13:30:00Z", "ends_at": "2026-10-04T13:50:00Z", "signup": True,
     "signup_url": "https://x.dk/tilmeld"}
B = {"starts_at": "2026-10-11T08:00:00Z", "ends_at": "2026-10-11T08:30:00Z", "signup": False,
     "signup_url": None}
C = {"starts_at": "2026-10-18T08:00:00Z", "ends_at": "2026-10-18T08:30:00Z", "signup": None,
     "signup_url": None}
T1, T2 = "2026-10-01T00:00:00Z", "2026-10-02T00:00:00Z"


def _store(tmp_path):
    s = HouseStore(tmp_path / "ht.db")
    return s, s.add_house({"address": "Nyvej 2"}, now="2026-09-30").id


def starts(rows):
    return [r["starts_at"] for r in rows]


def test_first_sight_is_new_and_the_second_is_not(tmp_path):
    s, h = _store(tmp_path)
    assert starts(s.sync_open_houses(h, [B, A], "agency", T1)) == [A["starts_at"], B["starts_at"]]
    assert s.sync_open_houses(h, [A, B], "agency", T2) == []
    assert s.list_open_houses(h) == [
        {"starts_at": A["starts_at"], "ends_at": A["ends_at"], "signup": True,
         "signup_url": "https://x.dk/tilmeld", "cancelled": False},
        {"starts_at": B["starts_at"], "ends_at": B["ends_at"], "signup": False,
         "signup_url": None, "cancelled": False}]


def test_unknown_sign_up_stays_unknown(tmp_path):
    s, h = _store(tmp_path)
    s.sync_open_houses(h, [C], "boligsiden", T1)
    assert s.list_open_houses(h)[0]["signup"] is None


def test_a_slot_already_over_is_ignored(tmp_path):
    s, h = _store(tmp_path)
    assert s.sync_open_houses(h, [A], "agency", "2026-10-05T00:00:00Z") == []
    assert s.list_open_houses(h) == []


def test_prune_marks_a_missing_upcoming_slot_cancelled(tmp_path):
    s, h = _store(tmp_path)
    s.sync_open_houses(h, [A, B], "agency", T1)
    s.sync_open_houses(h, [B], "agency", T2)
    assert [(r["starts_at"], r["cancelled"]) for r in s.list_open_houses(h)] == [
        (A["starts_at"], True), (B["starts_at"], False)]


def test_without_prune_a_missing_slot_stays(tmp_path):
    s, h = _store(tmp_path)
    s.sync_open_houses(h, [A, B], "agency", T1)
    s.sync_open_houses(h, [A], "boligsiden", T2, prune=False)
    assert [r["cancelled"] for r in s.list_open_houses(h)] == [False, False]


def test_prune_with_nothing_cancels_every_upcoming_slot(tmp_path):
    s, h = _store(tmp_path)
    s.sync_open_houses(h, [A, B], "agency", T1)
    s.sync_open_houses(h, [], "agency", T2)
    assert [r["cancelled"] for r in s.list_open_houses(h)] == [True, True]


def test_a_slot_that_comes_back_is_not_new_and_not_cancelled(tmp_path):
    s, h = _store(tmp_path)
    s.sync_open_houses(h, [A], "agency", T1)
    s.sync_open_houses(h, [], "agency", T2)
    assert s.sync_open_houses(h, [A], "agency", "2026-10-03T00:00:00Z") == []
    assert s.list_open_houses(h)[0]["cancelled"] is False


def test_a_held_slot_is_never_cancelled(tmp_path):
    s, h = _store(tmp_path)
    s.sync_open_houses(h, [A, B], "agency", T1)
    s.sync_open_houses(h, [B], "agency", "2026-10-05T00:00:00Z")     # A ended on the 4th
    assert s.list_open_houses(h)[0]["cancelled"] is False


def test_a_sync_updates_the_known_slot(tmp_path):
    s, h = _store(tmp_path)
    s.sync_open_houses(h, [A], "boligsiden", T1)
    s.sync_open_houses(h, [{**A, "ends_at": "2026-10-04T14:00:00Z", "signup": False}], "agency", T2)
    row = s.list_open_houses(h)[0]
    assert row["ends_at"] == "2026-10-04T14:00:00Z" and row["signup"] is False


def test_upcoming_only(tmp_path):
    s, h = _store(tmp_path)
    s.sync_open_houses(h, [A, B, C], "agency", T1)
    s.sync_open_houses(h, [A, C], "agency", T2)                     # B cancelled
    assert starts(s.list_open_houses(h, upcoming_at="2026-10-05T00:00:00Z")) == [C["starts_at"]]


def test_slots_are_per_house_and_go_with_the_house(tmp_path):
    s, h = _store(tmp_path)
    other = s.add_house({"address": "Andenvej 9"}, now="2026-09-30").id
    s.sync_open_houses(h, [A], "agency", T1)
    assert s.sync_open_houses(other, [A], "agency", T1) == [A]
    assert s.delete_house(h) is True
    assert s.list_open_houses(h) == [] and len(s.list_open_houses(other)) == 1


def test_a_slot_in_progress_is_never_cancelled(tmp_path):
    s, h = _store(tmp_path)
    s.sync_open_houses(h, [A, B], "agency", T1)
    s.sync_open_houses(h, [B], "agency", "2026-10-04T13:40:00Z")     # A runs 13:30-13:50
    assert [r["cancelled"] for r in s.list_open_houses(h)] == [False, False]
