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
