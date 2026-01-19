import pytest

from invest_registry.pagination import paginate  # type: ignore[import-untyped]


def test_paginate_returns_total_pages_and_slice() -> None:
    items = list(range(25))
    page_items, total = paginate(items, page=2, page_size=10)
    assert total == 3
    assert page_items == list(range(10, 20))


def test_paginate_clamps_page() -> None:
    items = list(range(3))
    page_items, total = paginate(items, page=99, page_size=2)
    assert total == 2
    assert page_items == [2]


def test_paginate_empty() -> None:
    page_items, total = paginate([], page=1, page_size=10)
    assert total == 0
    assert page_items == []


def test_paginate_rejects_non_positive_page_size() -> None:
    with pytest.raises(ValueError):
        paginate([1, 2, 3], page=1, page_size=0)

