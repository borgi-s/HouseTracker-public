import json

from housetracker.enrich.geocode import AddressGeocoder, _location

AID = "0a3f50a4-7e21-32b8-e044-0003ba298018"
# Adressevask: free text -> the official address id (real shape, trimmed).
VASK = {"vaskestatus": {"kode": 1000, "tekst": "Eksakt match"},
        "vaskeresultat": {"adresse_id_lokalid": AID,
                          "adressebetegnelse": "Møllehaven 17, 2800 Kongens Lyngby"}}
VASK_NO_POSTCODE = {"vaskestatus": {"kode": -300, "tekst": "Postnummer er ikke angivet"},
                    "vaskeresultat": {"adresse_id_lokalid": None}}
# Boligsiden /addresses/{id} (real shape, trimmed): a terraced house plus a shed.
BOLIGSIDEN = {
    "addressID": AID, "zipCode": 2800, "zip": {"name": "Kongens Lyngby", "zipCode": 2800},
    "cityName": "Kongens Lyngby", "municipality": {"name": "Gladsaxe", "municipalityCode": 159},
    "coordinates": {"lat": 55.76804, "lon": 12.50311, "type": "EPSG4326"},
    "buildings": [{"numberOfFloors": None, "housingArea": None},
                  {"numberOfFloors": 1, "numberOfBathrooms": 1, "numberOfToilets": 1,
                   "basementArea": 40, "housingArea": 103}],
}


def opener(vask=VASK, boligsiden=BOLIGSIDEN):
    def open_(url):
        return json.dumps(vask if "adressevaelger.dk/vask/" in url else boligsiden).encode()
    return open_


def test_location_reads_boligsiden_and_the_main_buildings_bbr_facts():
    assert _location(AID, BOLIGSIDEN) == {
        "lat": 55.76804, "lon": 12.50311, "postal_code": "2800", "city": "Kongens Lyngby",
        "kommune": "Gladsaxe", "address_id": AID,
        "floors": 1, "bathrooms": 1, "basement_m2": 40}


def test_geocode_washes_the_text_then_reads_that_address():
    seen = []
    def spy(url):
        seen.append(url)
        return opener()(url)
    loc = AddressGeocoder(opener=spy).geocode("Møllehaven 17, 2800 Kongens Lyngby")
    assert loc["postal_code"] == "2800" and loc["kommune"] == "Gladsaxe"
    assert seen[1].endswith(f"/addresses/{AID}")


def test_an_address_without_postal_code_is_not_guessed():
    assert AddressGeocoder(opener=opener(vask=VASK_NO_POSTCODE)).geocode("Møllehaven 17") is None


def test_geocode_swallows_network_errors():
    def boom(url):
        raise OSError("no network")
    assert AddressGeocoder(opener=boom).geocode("x, 2800") is None


def test_a_house_registered_as_floor_units_is_washed_via_its_ground_floor():
    """Adressevask answers -600 for a house number that only exists as unit addresses
    (Vinkelhøj 6, 8260 Viby J: '6, st.', '6, 1.'); the ground floor's coordinates and BBR
    are the house's."""
    import urllib.parse
    UNITS = {"vaskestatus": {"kode": -600, "tekst": "Etage findes ikke på adresse på husnummer"},
             "vaskeresultat": {"adresse_id_lokalid": None}}
    asked = []
    def units(url):
        if "adressevaelger.dk/vask/" in url:
            text = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["adresse"][0]
            asked.append(text)
            return json.dumps(VASK if text == "Møllehaven 17 st., 2800 Kongens Lyngby" else UNITS).encode()
        return json.dumps(BOLIGSIDEN).encode()
    loc = AddressGeocoder(opener=units).geocode("Møllehaven 17, 2800 Kongens Lyngby")
    assert loc is not None and loc["address_id"] == AID
    assert asked == ["Møllehaven 17, 2800 Kongens Lyngby", "Møllehaven 17 st., 2800 Kongens Lyngby"]


def test_a_single_house_that_rejects_every_floor_is_still_none():
    UNITS = {"vaskestatus": {"kode": -600, "tekst": "x"}, "vaskeresultat": {"adresse_id_lokalid": None}}
    assert AddressGeocoder(opener=opener(vask=UNITS)).geocode("Møllehaven 17, 2800") is None
