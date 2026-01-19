# Invest Registry
test
A small Streamlit app to **discover French companies** via the public registry search API, then **deep dive** on a selected company (founders, basic signals, and a lightweight financial snapshot when available).

## What’s in the app

- **Search**: run a “query pack” (currently `blossom_like_france`), fetch a target number of companies, review results, jump into a deep dive.
- **Company Deep Dive**: load details for a SIREN (dirigeants, siège, complements, finances), and optionally help find founder socials.
- **Caching**: Streamlit cache + optional local disk cache in `.cache/` (toggle in the sidebar).

## Data sources

- **France**: Annuaire des Entreprises API (`https://recherche-entreprises.api.gouv.fr/search`)
- **Company page links**: INPI data portal (linked from the UI)

## Run locally

```bash
uv sync
uv run streamlit run streamlit_app.py
```

Then open the Streamlit URL and use **Search → Deep dive**.

## Optional: semi-automatic founder social discovery

If you configure a search provider, the deep dive page can fetch candidate LinkedIn/X profile URLs.

Environment variables:

- `SEARCH_PROVIDER`: `serpapi` or `google_cse`
- `SERPAPI_API_KEY`: required if `SEARCH_PROVIDER=serpapi`
- `GOOGLE_CSE_API_KEY`, `GOOGLE_CSE_CX`: required if `SEARCH_PROVIDER=google_cse`

If unset, the UI falls back to plain Google search links.

## Tests

```bash
uv run pytest
```

## Notes / limitations

- This is **registry search data**: great for identification + quick screening, not a substitute for paid/enriched datasets.
- Some fields are often missing (e.g., employee bands for young companies), and non-diffusible entities are excluded by design.

