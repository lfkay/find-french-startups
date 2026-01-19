from invest_registry.scoring import employee_band_label
from invest_registry.social_discovery import google_search_url, linkedin_people_query, x_people_query


def test_employee_band_label_returns_human_range() -> None:
    assert employee_band_label("11") == "10-19"
    assert employee_band_label("02") == "3-5"


def test_linkedin_query_builder() -> None:
    q = linkedin_people_query("Stanislas Niox-Chateau", "Doctolib")
    assert "site:linkedin.com/in" in q
    assert "Doctolib" in q


def test_x_query_builder() -> None:
    q = x_people_query("Stanislas Niox-Chateau", "Doctolib")
    assert "site:x.com" in q or "site:twitter.com" in q


def test_google_search_url_encodes_query() -> None:
    url = google_search_url('\"Jane Doe\" site:linkedin.com/in')
    assert url.startswith("https://www.google.com/search?q=")
    assert "linkedin.com%2Fin" in url or "linkedin.com%2Fin" in url

