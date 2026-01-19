from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    france_api_base_url: str = "https://recherche-entreprises.api.gouv.fr"
    http_timeout_seconds: float = 20.0
    http_max_retries: int = 3

    # Optional: enable semi-automatic social discovery in the UI.
    # If unset, the app will fall back to plain search links.
    search_provider: str | None = None  # "serpapi" or "google_cse"
    serpapi_api_key: str | None = None
    google_cse_api_key: str | None = None
    google_cse_cx: str | None = None


settings = Settings()

