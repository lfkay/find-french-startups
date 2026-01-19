from invest_registry.models import FranceDirigeant


def dirigeants_personnes_physiques(
    dirigeants: list[FranceDirigeant] | None,
) -> list[FranceDirigeant]:
    if not dirigeants:
        return []
    return [d for d in dirigeants if (d.type_dirigeant or "").strip().lower() == "personne physique"]

