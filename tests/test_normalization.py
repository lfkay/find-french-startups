from invest_registry.clients.france import normalize_france_result
from invest_registry.models import FranceSearchResult


def test_normalization_pulls_siege_fields() -> None:
    raw = {
        "siren": "941429565",
        "nom_raison_sociale": "PIGMENT",
        "activite_principale": "62.01Z",
        "siege": {
            "siret": "94142956500026",
            "activite_principale": "62.01Z",
            "code_postal": "75002",
            "libelle_commune": "PARIS",
            "departement": "75",
            "region": "11",
            "date_creation": "2025-04-01",
            "tranche_effectif_salarie": "NN",
            "caractere_employeur": "O",
            "geo_adresse": "1 rue X 75002 Paris",
        },
    }
    r = FranceSearchResult.model_validate(raw)
    c = normalize_france_result(r)

    assert c.siren == "941429565"
    assert c.siret == "94142956500026"
    assert c.name == "PIGMENT"
    assert c.naf == "62.01Z"
    assert c.postal_code == "75002"
    assert c.commune == "PARIS"
    assert c.is_employer is True
