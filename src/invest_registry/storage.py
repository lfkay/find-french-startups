import json
from pathlib import Path

from invest_registry.models import CompanyRecord


def cache_dir() -> Path:
    d = Path(".cache")
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_path(key: str) -> Path:
    safe = "".join(ch for ch in key if ch.isalnum() or ch in ("-", "_", "."))
    return cache_dir() / f"{safe}.json"


def load_cached_records(key: str) -> list[CompanyRecord] | None:
    path = cache_path(key)
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [CompanyRecord.model_validate(r) for r in raw]


def save_cached_records(key: str, records: list[CompanyRecord]) -> None:
    path = cache_path(key)
    payload = [r.model_dump(mode="json") for r in records]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

