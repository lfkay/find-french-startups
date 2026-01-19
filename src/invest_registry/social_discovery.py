from dataclasses import dataclass
from urllib.parse import quote_plus

import httpx

from invest_registry.settings import Settings, settings


@dataclass(frozen=True)
class SocialCandidate:
    title: str
    url: str
    snippet: str | None = None


def linkedin_people_query(person_name: str, company_name: str) -> str:
    bits = [b.strip() for b in [person_name, company_name] if b and b.strip()]
    core = " ".join(bits) if bits else person_name.strip()
    return f"\"{core}\" site:linkedin.com/in"


def x_people_query(person_name: str, company_name: str) -> str:
    bits = [b.strip() for b in [person_name, company_name] if b and b.strip()]
    core = " ".join(bits) if bits else person_name.strip()
    return f"\"{core}\" (site:x.com OR site:twitter.com)"


def google_search_url(query: str) -> str:
    return f"https://www.google.com/search?q={quote_plus(query)}"


def search_candidates(
    *,
    query: str,
    kind: str,
    app_settings: Settings = settings,
    max_results: int = 5,
) -> list[SocialCandidate]:
    provider = (app_settings.search_provider or "").strip().lower()
    if not provider:
        return []

    if provider == "serpapi":
        if not app_settings.serpapi_api_key:
            return []
        return _search_serpapi(query=query, api_key=app_settings.serpapi_api_key, max_results=max_results)

    if provider == "google_cse":
        if not app_settings.google_cse_api_key or not app_settings.google_cse_cx:
            return []
        return _search_google_cse(
            query=query,
            api_key=app_settings.google_cse_api_key,
            cx=app_settings.google_cse_cx,
            max_results=max_results,
        )

    raise ValueError(f"unknown search_provider: {provider!r}")


def _search_serpapi(*, query: str, api_key: str, max_results: int) -> list[SocialCandidate]:
    resp = httpx.get(
        "https://serpapi.com/search.json",
        params={"engine": "google", "q": query, "api_key": api_key, "num": max_results},
        timeout=20.0,
    )
    resp.raise_for_status()
    data = resp.json()

    out: list[SocialCandidate] = []
    for item in (data.get("organic_results") or [])[:max_results]:
        url = item.get("link")
        title = item.get("title") or url
        if not url:
            continue
        out.append(SocialCandidate(title=title, url=url, snippet=item.get("snippet")))
    return out


def _search_google_cse(
    *,
    query: str,
    api_key: str,
    cx: str,
    max_results: int,
) -> list[SocialCandidate]:
    resp = httpx.get(
        "https://www.googleapis.com/customsearch/v1",
        params={"key": api_key, "cx": cx, "q": query, "num": max_results},
        timeout=20.0,
    )
    resp.raise_for_status()
    data = resp.json()

    out: list[SocialCandidate] = []
    for item in (data.get("items") or [])[:max_results]:
        url = item.get("link")
        title = item.get("title") or url
        if not url:
            continue
        out.append(SocialCandidate(title=title, url=url, snippet=item.get("snippet")))
    return out

