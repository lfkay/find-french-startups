from datetime import date

from invest_registry.clients.france import FranceSearchParams, collect_companies
from invest_registry.models import FranceSearchResponse


class _FakeClient:
    def __init__(self, pages: dict[tuple[str, int], dict], *, total_pages: int) -> None:
        self._pages = pages
        self._total_pages = total_pages
        self.calls: list[tuple[str, int]] = []

    def search(self, *, search: FranceSearchParams, page: int = 1, per_page: int = 25) -> FranceSearchResponse:
        key = (search.activite_principale or "", page)
        self.calls.append(key)
        payload = self._pages[key]
        payload = {
            "page": page,
            "per_page": per_page,
            "total_pages": self._total_pages,
            "total_results": self._total_pages * per_page,
            "results": payload["results"],
        }
        return FranceSearchResponse.model_validate(payload)


def test_collect_companies_keeps_paging_until_filtered_target_or_exhaustion() -> None:
    # Page 1: all results are too old => filtered out
    # Page 2: enough recent results => should be returned, proving we keep paging.
    old = {
        "siren": "111111111",
        "nom_raison_sociale": "OLD CO",
        "activite_principale": "62.01Z",
        "date_creation": "2010-01-01",
        "siege": {"code_postal": "75001", "tranche_effectif_salarie": "11"},
    }
    new1 = {
        "siren": "222222222",
        "nom_raison_sociale": "NEW CO 1",
        "activite_principale": "62.01Z",
        "date_creation": "2024-01-01",
        "siege": {"code_postal": "75001", "tranche_effectif_salarie": "11"},
    }
    new2 = {
        "siren": "333333333",
        "nom_raison_sociale": "NEW CO 2",
        "activite_principale": "62.01Z",
        "date_creation": "2025-01-01",
        "siege": {"code_postal": "75001", "tranche_effectif_salarie": "11"},
    }

    pages = {
        ("62.01Z", 1): {"results": [old]},
        ("62.01Z", 2): {"results": [new1, new2]},
    }
    client = _FakeClient(pages, total_pages=2)

    searches = [
        FranceSearchParams(
            q="",
            activite_principale="62.01Z",
            tranche_effectif_salarie="00,01,02,03,11",
            etat_administratif="A",
        )
    ]

    out = collect_companies(
        client,  # type: ignore[arg-type]
        searches=searches,
        target_count=2,
        max_pages_per_search=None,
        postal_code_prefix="75",
        min_creation_date=date(2021, 1, 19),
    )

    assert [c.siren for c in out] == ["222222222", "333333333"]
    assert ("62.01Z", 2) in client.calls

