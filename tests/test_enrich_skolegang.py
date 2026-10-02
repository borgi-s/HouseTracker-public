from housetracker.enrich.skolegang import (
    figure_rows, kommune_url, latest, parse_kommune_slugs, parse_school,
)
from skolegang_pages import FUGL, FUGL_PROPS, kommune_page, ld, push


def test_kommune_url_keeps_danish_letters_percent_encoded():
    assert kommune_url("Lyngby-Taarbæk") == \
        "https://skolegang.dk/kommune/skoler-i-lyngby-taarb%C3%A6k"
    assert kommune_url("København").endswith("/skoler-i-k%C3%B8benhavn")


def test_kommune_slugs_come_from_the_payload_not_the_links():
    html = kommune_page("virum-skole", "taarbaek-skole", "virum-skole")
    assert parse_kommune_slugs(html) == ["taarbaek-skole", "virum-skole"]


def test_school_page_gives_register_facts_series_snapshot_and_ranks():
    r = parse_school(FUGL, "fuglsanggaardsskolen")
    assert (r["inst_nr"], r["name"], r["top_grade"], r["folkeskole"]) == \
        ("173003", "Fuglsanggårdsskolen", 9, True)
    assert r["address"] == "Askevænget 10, 2830 Virum"       # the name prefix is cut
    assert (r["lat"], r["lon"]) == (55.79309167, 12.47906506)
    f = r["figures"]
    assert f["year"] == "2024/2025" and f["total_schools"] == 2870
    assert f["series"]["karaktergennemsnit"] == [["2023/2024", 8.6], ["2024/2025", 8.8]]
    assert f["series"]["wb:Social trivsel"][-1] == ["2024/2025", 4.1]
    assert f["national"]["wb:Social trivsel"][-1] == ["2024/2025", 3.9]
    assert f["snapshot"]["grade"] == 8.8 and f["snapshot"]["danish_origin"] == 88.2
    assert f["rank"] == {"grade": 71, "teaching_effect": 115, "absence": 337,
                         "danish_origin": 1542}
    assert f["significance"] == "Over niveau"


def test_tenth_grade_centres_and_special_schools_are_not_folkeskoler():
    gxu = ld("GXU - Gladsaxe 10. Klasse og Ungdomsskole", {"InstitutionsNummer": "159038",
                                                          "InstTypeNr": "1012"})
    special = ld("Sorgenfriskolen", {"InstitutionsNummer": "173020", "InstTypeNr": "1015"})
    assert parse_school(gxu, "gxu")["folkeskole"] is False
    assert parse_school(special, "sorgenfriskolen")["folkeskole"] is False


def test_a_page_without_school_json_ld_is_none():
    assert parse_school("<html><title>404</title></html>", "gone") is None


def test_register_gap_page_parses_without_coords_or_type():
    # Tranegårdskolen: figures, but no address, geo or InstTypeNr
    html = ld("Tranegårdskolen", {"InstitutionsNummer": "157012", "År": "2024/2025",
                                  "KarakterGns": 9.4}, geo=None)
    r = parse_school(html, "tranegaardskolen")
    assert (r["lat"], r["address"], r["folkeskole"]) == (None, None, False)
    assert latest(r["figures"], "grade") == (9.4, "2024/2025")


def test_without_the_payload_the_snapshot_still_gives_the_figures():
    r = parse_school(ld("Fuglsanggårdsskolen", FUGL_PROPS), "fuglsanggaardsskolen")
    assert latest(r["figures"], "grade") == (8.8, "2024/2025")
    assert latest(r["figures"], "wellbeing") == (None, None)


def _peer(grade_by_year, year="2024/2025"):
    return {"figures": {"year": year, "series": {"karaktergennemsnit": [
        [y, g] for y, g in grade_by_year.items()]}, "national": {}, "snapshot": {}, "rank": {}}}


def test_figure_rows_carry_year_kommune_mean_national_average_and_rank():
    fugl = parse_school(FUGL, "fuglsanggaardsskolen")["figures"]
    kommune = [{"figures": fugl}, _peer({"2024/2025": 7.8}), _peer({"2023/2024": 9.9})]
    rows = {r["key"]: r for r in figure_rows(fugl, kommune)}
    g = rows["grade"]
    assert (g["value"], g["year"], g["better"]) == (8.8, "2024/2025", "high")
    assert g["kommune_avg"] == 8.3                  # (8.8 + 7.8) / 2; the 2023/24-only peer is out
    assert (g["national_rank"], g["total_schools"], g["national_avg"]) == (71, 2870, None)
    assert rows["social_wellbeing"]["national_avg"] == 3.9
    assert rows["teaching_effect"]["note"] == "Over niveau"
    assert rows["absence"]["better"] == "low" and rows["absence"]["unit"] == "%"
    assert (rows["wellbeing"]["value"], rows["wellbeing"]["year"],
            rows["wellbeing"]["kommune_avg"]) == (None, None, None)


def test_a_newer_series_year_than_the_ranks_shows_no_rank():
    fugl = parse_school(FUGL, "fuglsanggaardsskolen")["figures"]
    fugl["series"]["karaktergennemsnit"].append(["2025/2026", 9.4])
    g = {r["key"]: r for r in figure_rows(fugl, [])}["grade"]
    assert (g["value"], g["year"], g["national_rank"]) == (9.4, "2025/2026", None)


def test_payload_strings_with_escaped_quotes_do_not_break_the_chunk_parse():
    html = push({"text": 'a "quoted"]) word'}) + kommune_page("virum-skole")
    assert parse_kommune_slugs(html) == ["virum-skole"]


def test_the_address_loses_the_name_prefix_even_when_the_name_has_a_suffix():
    # "Bakkegårdsskolen, Gentofte" -> "Bakkegårdsskolen Skolebakken 20, 2820 Gentofte"
    html = ld("Bakkegårdsskolen, Gentofte", {"InstitutionsNummer": "157001"},
              street="Bakkegårdsskolen Skolebakken 20, 2820 Gentofte")
    assert parse_school(html, "bakkegaardsskolen-gentofte")["address"] == \
        "Skolebakken 20, 2820 Gentofte"
