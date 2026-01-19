from dataclasses import dataclass
from datetime import date

import httpx
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential

from invest_registry.models import CompanyRecord, FranceSearchResponse, FranceSearchResult
from invest_registry.settings import Settings, settings


PER_PAGE_MAX = 25


@dataclass(frozen=True)
class FranceSearchParams:
    q: str
    activite_principale: str | None = None
    code_postal: str | None = None
    tranche_effectif_salarie: str | None = None
    etat_administratif: str | None = "A"
    minimal: bool | None = None
    include: str | None = None


def _should_retry(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in {429, 500, 502, 503, 504}
    return False


class FranceCompanySearchClient:
    def __init__(
        self,
        *,
        app_settings: Settings = settings,
        http: httpx.Client | None = None,
    ) -> None:
        self._settings = app_settings
        self._http = http or httpx.Client(
            base_url=self._settings.france_api_base_url,
            timeout=httpx.Timeout(self._settings.http_timeout_seconds),
            headers={"user-agent": "invest-registry/0.1"},
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "FranceCompanySearchClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _get_json(self, path: str, *, params: dict[str, str | int | bool]) -> dict:
        retrying = Retrying(
            retry=retry_if_exception(_should_retry),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
            stop=stop_after_attempt(self._settings.http_max_retries),
            reraise=True,
        )

        for attempt in retrying:
            with attempt:
                resp = self._http.get(path, params=params)
                resp.raise_for_status()
                return resp.json()

        raise RuntimeError("unreachable")

    def search(
        self,
        *,
        search: FranceSearchParams,
        page: int = 1,
        per_page: int = PER_PAGE_MAX,
    ) -> FranceSearchResponse:
        if per_page > PER_PAGE_MAX:
            raise ValueError(f"per_page must be <= {PER_PAGE_MAX} (API returns 400 otherwise)")

        params: dict[str, str | int | bool] = {
            "q": search.q,
            "page": page,
            "per_page": per_page,
        }
        if search.activite_principale:
            params["activite_principale"] = search.activite_principale
        if search.code_postal:
            params["code_postal"] = search.code_postal
        if search.tranche_effectif_salarie:
            params["tranche_effectif_salarie"] = search.tranche_effectif_salarie
        if search.etat_administratif:
            params["etat_administratif"] = search.etat_administratif
        if search.minimal is not None:
            params["minimal"] = search.minimal
        if search.include:
            # The API requires minimal=True when include is provided.
            if params.get("minimal") is not True:
                params["minimal"] = True
            params["include"] = search.include

        data = self._get_json("/search", params=params)
        return FranceSearchResponse.model_validate(data)

    def iter_results(
        self,
        *,
        search: FranceSearchParams,
        per_page: int = PER_PAGE_MAX,
        max_pages: int | None = None,
    ) -> list[FranceSearchResult]:
        page = 1
        out: list[FranceSearchResult] = []

        while True:
            resp = self.search(search=search, page=page, per_page=per_page)
            out.extend(resp.results)

            if max_pages is not None and page >= max_pages:
                break
            if page >= resp.total_pages:
                break

            page += 1

        return out


def normalize_france_result(r: FranceSearchResult) -> CompanyRecord:
    siege = r.siege

    name = r.nom_raison_sociale or r.nom_complet or r.siren
    naf = r.activite_principale or (siege.activite_principale if siege else None)

    employee_band_year: int | None = None
    if siege and siege.annee_tranche_effectif_salarie:
        try:
            employee_band_year = int(siege.annee_tranche_effectif_salarie)
        except ValueError:
            employee_band_year = None

    is_employer: bool | None = None
    if siege and siege.caractere_employeur:
        if siege.caractere_employeur == "O":
            is_employer = True
        elif siege.caractere_employeur == "N":
            is_employer = False

    return CompanyRecord(
        country="FR",
        siren=r.siren,
        siret=siege.siret if siege else None,
        name=name,
        naf=naf,
        creation_date=r.date_creation or (siege.date_creation if siege else None),
        address=(siege.geo_adresse or siege.adresse) if siege else None,
        postal_code=siege.code_postal if siege else None,
        commune=siege.libelle_commune if siege else None,
        departement=siege.departement if siege else None,
        region=siege.region if siege else None,
        employee_band=siege.tranche_effectif_salarie if siege else None,
        employee_band_year=employee_band_year,
        is_employer=is_employer,
        source="recherche-entreprises.api.gouv.fr/search",
    )


def collect_companies(
    client: FranceCompanySearchClient,
    *,
    searches: list[FranceSearchParams],
    target_count: int = 50,
    per_page: int = PER_PAGE_MAX,
    max_pages_per_search: int | None = 2,
    postal_code_prefix: str | None = None,
    min_creation_date: date | None = None,
) -> list[CompanyRecord]:
    seen: set[str] = set()
    out: list[CompanyRecord] = []

    # Round-robin paging across searches until we have enough *filtered* records.
    # This avoids the "fetch N then filter" failure mode when filters are strict.
    first_pages: list[tuple[FranceSearchParams, FranceSearchResponse]] = []
    total_pages_by_q: dict[FranceSearchParams, int] = {}
    next_page_by_q: dict[FranceSearchParams, int] = {}

    for s in searches:
        resp = client.search(search=s, page=1, per_page=per_page)
        first_pages.append((s, resp))
        total_pages_by_q[s] = resp.total_pages
        next_page_by_q[s] = 1

    def _process(resp: FranceSearchResponse) -> bool:
        for item in resp.results:
            if item.siren in seen:
                continue
            record = normalize_france_result(item)
            if min_creation_date:
                if not record.creation_date or record.creation_date < min_creation_date:
                    continue
            if postal_code_prefix:
                if not record.postal_code or not record.postal_code.startswith(postal_code_prefix):
                    continue
            seen.add(item.siren)
            out.append(record)
            if len(out) >= target_count:
                return True
        return False

    while len(out) < target_count:
        progressed = False
        for s, first_resp in first_pages:
            page = next_page_by_q[s]
            total_pages = total_pages_by_q[s]
            if page > total_pages:
                continue
            if max_pages_per_search is not None and page > max_pages_per_search:
                continue

            resp = first_resp if page == 1 else client.search(search=s, page=page, per_page=per_page)
            progressed = True
            if _process(resp):
                return out
            next_page_by_q[s] = page + 1

        if not progressed:
            break

    return out

