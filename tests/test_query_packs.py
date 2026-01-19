from invest_registry.query_packs import get_query_pack


def test_blossom_like_pack_is_compact() -> None:
    pack = get_query_pack("blossom_like_france", paris_only=False)
    assert pack.name == "blossom_like_france"
    assert len(pack.searches) == 2
    assert all(s.tranche_effectif_salarie == "00,01,02,03,11" for s in pack.searches)


def test_paris_only_does_not_set_code_postal() -> None:
    pack = get_query_pack("blossom_like_france", paris_only=True)
    assert all(s.code_postal is None for s in pack.searches)
