from housetracker.store import HouseStore


def _store(tmp_path):
    return HouseStore(tmp_path / "data" / "ht.db")


def _school(inst="173003", name="Fuglsanggårdsskolen", kommune="Lyngby-Taarbæk", **over):
    return {"inst_nr": inst, "slug": "fuglsanggaardsskolen", "name": name,
            "address": "Askevænget 10, 2830 Virum", "lat": 55.79, "lon": 12.48,
            "kommune": kommune, "top_grade": 9, "fetched_at": "2026-09-26",
            "figures": {"year": "2024/2025", "snapshot": {"grade": 8.8}}, **over}


def _row(order=0, rank=1, inst="173003", **over):
    return {"district_order": order, "rank": rank, "district_name": "Fuglsanggårdsskolen",
            "district_grades": "0.–9.", "district_link": None, "district_schools": 1,
            "fallback": False, "inst_nr": inst, "walk_min": 11.5, "walk_m": 900.0,
            "bike_min": 4.0, "bike_m": 1000.0, "straight_m": 700, **over}


def test_school_tables_exist(tmp_path):
    assert {"school", "house_school"} <= _store(tmp_path).table_names()


def test_upsert_school_roundtrips_figures_and_replaces_by_inst_nr(tmp_path):
    s = _store(tmp_path)
    s.upsert_school({**_school(), "folkeskole": True})         # extra keys are ignored
    assert s.get_school("173003")["figures"]["snapshot"]["grade"] == 8.8
    s.upsert_school(_school(name="Fuglsanggårdsskolen (ny)", fetched_at="2026-10-30"))
    got = s.get_school("173003")
    assert (got["name"], got["fetched_at"]) == ("Fuglsanggårdsskolen (ny)", "2026-10-30")
    assert s.get_school("999") is None


def test_list_schools_is_per_kommune(tmp_path):
    s = _store(tmp_path)
    s.upsert_school(_school())
    s.upsert_school(_school(inst="157003", name="Gentofte Skole", kommune="Gentofte"))
    assert [x["name"] for x in s.list_schools("Gentofte")] == ["Gentofte Skole"]


def test_replace_house_schools_swaps_the_whole_set_in_order(tmp_path):
    s = _store(tmp_path)
    hid = s.add_house({"address": "Nyvej 2"}, now="2026-09-26").id
    s.replace_house_schools(hid, [_row(rank=1), _row(rank=2, inst="173004")], "2026-09-26")
    s.replace_house_schools(hid, [_row(order=1, rank=1, fallback=True),
                                  _row(order=0, rank=1, inst="173009")], "2026-09-27")
    got = s.list_house_schools(hid)
    assert [(r["district_order"], r["inst_nr"]) for r in got] == [(0, "173009"), (1, "173003")]
    assert got[1]["fallback"] is True and got[0]["fallback"] is False
    assert got[0]["checked_at"] == "2026-09-27"


def test_same_district_name_twice_fits_a_grade_split(tmp_path):
    s = _store(tmp_path)
    hid = s.add_house({"address": "Nyvej 2"}, now="2026-09-26").id
    s.replace_house_schools(hid, [_row(order=0, district_grades="0.–6."),
                                  _row(order=1, district_grades="7.–9.")], "2026-09-26")
    assert len(s.list_house_schools(hid)) == 2


def test_deleting_a_house_drops_its_schools_but_keeps_the_school_rows(tmp_path):
    s = _store(tmp_path)
    s.upsert_school(_school())
    hid = s.add_house({"address": "Nyvej 2"}, now="2026-09-26").id
    s.replace_house_schools(hid, [_row()], "2026-09-26")
    assert s.delete_house(hid)
    assert s.list_house_schools(hid) == []
    assert s.get_school("173003") is not None
