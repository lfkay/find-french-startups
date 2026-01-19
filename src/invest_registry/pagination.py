from typing import TypeVar

T = TypeVar("T")


def paginate(items: list[T], *, page: int, page_size: int) -> tuple[list[T], int]:
    if page_size <= 0:
        raise ValueError("page_size must be > 0")
    if not items:
        return [], 0

    total_pages = (len(items) + page_size - 1) // page_size
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], total_pages

