from dataclasses import dataclass

from invest_registry.clients.france import FranceSearchParams


@dataclass(frozen=True)
class QueryPack:
    name: str
    description: str
    searches: list[FranceSearchParams]


def blossom_like_france(*, paris_only: bool = False) -> QueryPack:
    # Heuristic inspired by Blossom's portfolio tilt toward SaaS/devtools/security/data/fintech.
    naf_codes = [
        "58.29C",  # Édition de logiciels applicatifs
        "62.01Z",  # Programmation informatique
    ]

    # Paris-only is implemented as a post-filter on returned records.
    # The search API expects a 5-digit postal code; passing "75" triggers a 400.
    code_postal = None

    searches: list[FranceSearchParams] = []
    for naf in naf_codes:
        searches.append(
            FranceSearchParams(
                q="",
                activite_principale=naf,
                code_postal=code_postal,
                tranche_effectif_salarie="00,01,02,03,11",
                etat_administratif="A",
            )
        )

    return QueryPack(
        name="blossom_like_france",
        description="Compact pack targeting French software/IT companies (optionally Paris-only).",
        searches=searches,
    )


def get_query_pack(name: str, *, paris_only: bool = False) -> QueryPack:
    if name == "blossom_like_france":
        return blossom_like_france(paris_only=paris_only)
    raise ValueError(f"unknown query pack: {name}")
