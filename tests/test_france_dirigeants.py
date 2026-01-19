from invest_registry.france_people import dirigeants_personnes_physiques
from invest_registry.models import FranceSearchResponse


def test_parses_dirigeants_and_filters_personne_physique() -> None:
    payload = {
        "page": 1,
        "per_page": 1,
        "total_pages": 1,
        "total_results": 1,
        "results": [
            {
                "siren": "794598813",
                "nom_raison_sociale": "DOCTOLIB",
                "dirigeants": [
                    {
                        "type_dirigeant": "personne physique",
                        "qualite": "Président de SAS",
                        "nom": "NIOX-CHATEAU",
                        "prenoms": "STANISLAS",
                        "annee_de_naissance": "1986",
                        # Extra fields should be ignored
                        "ville_naissance": "Paris",
                    },
                    {
                        "type_dirigeant": "personne morale",
                        "qualite": "Administrateur",
                        "denomination": "SOME_HOLDCO",
                        "siren": "111222333",
                    },
                ],
            }
        ],
    }

    resp = FranceSearchResponse.model_validate(payload)
    assert resp.results[0].dirigeants is not None
    assert len(resp.results[0].dirigeants) == 2

    phys = dirigeants_personnes_physiques(resp.results[0].dirigeants)
    assert [d.type_dirigeant for d in phys] == ["personne physique"]
    assert phys[0].nom == "NIOX-CHATEAU"

