from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict


class FranceSiege(BaseModel):
    model_config = ConfigDict(extra="ignore")

    siret: str | None = None
    activite_principale: str | None = None
    code_postal: str | None = None
    libelle_commune: str | None = None
    departement: str | None = None
    region: str | None = None
    adresse: str | None = None
    geo_adresse: str | None = None
    latitude: str | None = None
    longitude: str | None = None
    coordonnees: str | None = None

    date_creation: date | None = None

    tranche_effectif_salarie: str | None = None
    annee_tranche_effectif_salarie: str | None = None

    etat_administratif: str | None = None
    caractere_employeur: str | None = None


class FranceDirigeant(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type_dirigeant: str | None = None
    qualite: str | None = None

    nom: str | None = None
    prenoms: str | None = None

    date_de_naissance: str | None = None
    annee_de_naissance: str | None = None
    nationalite: str | None = None


class FranceSearchResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    siren: str
    nom_raison_sociale: str | None = None
    nom_complet: str | None = None
    sigle: str | None = None

    activite_principale: str | None = None
    date_creation: date | None = None
    siege: FranceSiege | None = None

    nombre_etablissements: int | None = None
    nombre_etablissements_ouverts: int | None = None

    dirigeants: list[FranceDirigeant] | None = None
    complements: dict[str, object] | None = None
    finances: dict[str, object] | None = None


class FranceSearchResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    page: int
    per_page: int
    total_pages: int
    total_results: int
    results: list[FranceSearchResult]


class CompanyRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    country: Literal["FR"]

    siren: str
    siret: str | None

    name: str
    naf: str | None

    creation_date: date | None

    address: str | None
    postal_code: str | None
    commune: str | None
    departement: str | None
    region: str | None

    employee_band: str | None
    employee_band_year: int | None
    is_employer: bool | None

    source: str

