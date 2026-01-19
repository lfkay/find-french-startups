from datetime import date

import streamlit as st

from invest_registry.clients.france import FranceCompanySearchClient, FranceSearchParams
from invest_registry.france_people import dirigeants_personnes_physiques
from invest_registry.models import FranceSearchResult
from invest_registry.scoring import employee_band_label
from invest_registry.social_discovery import (
    SocialCandidate,
    google_search_url,
    linkedin_people_query,
    search_candidates,
    x_people_query,
)

st.set_page_config(page_title="Company deep dive", layout="wide")


def _age_years(created: date | None) -> float | None:
    if not created:
        return None
    return (date.today() - created).days / 365.25


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def _fetch_details_by_siren(siren: str) -> FranceSearchResult | None:
    with FranceCompanySearchClient() as client:
        resp = client.search(
            search=FranceSearchParams(
                q=siren,
                minimal=True,
                include="dirigeants,siege,complements,finances",
            ),
            per_page=1,
        )

    for r in resp.results:
        if r.siren == siren:
            return r
    return resp.results[0] if resp.results else None


selected_siren = st.query_params.get("siren")
if isinstance(selected_siren, list):
    selected_siren = selected_siren[0] if selected_siren else None
selected_siren = str(selected_siren) if selected_siren else None

top_actions = st.columns([1, 3])
with st.sidebar:
    if st.button("← Back", type="secondary"):
        st.query_params.clear()
        st.switch_page("pages/1_Search.py")
    with st.form("siren_form", border=False):
        siren_in = st.text_input("SIREN", value=selected_siren or "", placeholder="e.g. 794598813")
        submitted = st.form_submit_button("Go")
    if submitted:
        siren_in = siren_in.strip()
        if siren_in:
            st.query_params["siren"] = siren_in
        else:
            st.query_params.clear()
        st.rerun()

if not selected_siren:
    st.error(
        "No company selected. Open a deep dive URL like `...?siren=794598813` "
        "or go back and click **Deep dive** on a company card."
    )
    st.stop()

with st.spinner("Loading company details…"):
    details = _fetch_details_by_siren(selected_siren)

if not details:
    st.error(f"No results found for SIREN `{selected_siren}`.")
    st.stop()

inpi_url = f"https://data.inpi.fr/entreprises/{details.siren}"

company_name = details.nom_raison_sociale or details.nom_complet or "Company deep dive"
st.markdown(f"## [{company_name}]({inpi_url})")

siege = details.siege
created = details.date_creation or (siege.date_creation if siege else None)
age_years = _age_years(created)

employee_band = None
employee_band_year = None
is_employer = None
naf = None
postal_code = None
commune = None
departement = None

if siege:
    employee_band = siege.tranche_effectif_salarie
    employee_band_year = siege.annee_tranche_effectif_salarie
    is_employer = siege.caractere_employeur
    naf = siege.activite_principale
    postal_code = siege.code_postal
    commune = siege.libelle_commune
    departement = siege.departement

metrics = st.columns(4)
metrics[0].metric("SIREN", details.siren)
metrics[1].metric("Created", created.isoformat() if created else "—")
metrics[2].metric("Age (years)", f"{age_years:.1f}" if age_years is not None else "—")
metrics[3].metric("Employees", employee_band_label(employee_band) or "—")

loc_bits = [b for b in [commune, departement, postal_code] if b]
st.caption(" · ".join(loc_bits) if loc_bits else "Location: —")

signal_cols = st.columns([1, 1, 2])
with signal_cols[0]:
    if is_employer == "O":
        st.success("Employer: yes")
    elif is_employer == "N":
        st.warning("Employer: no")
    else:
        st.info("Employer: unknown")
with signal_cols[1]:
    if age_years is not None and age_years <= 5:
        st.success("Recently founded (≤ 5y)")
    elif age_years is not None:
        st.info("Founded > 5y")
    else:
        st.info("Founded: unknown")
with signal_cols[2]:
    st.empty()

st.subheader("Founders (dirigeants personnes physiques)")

dirigeants = details.dirigeants or []
founders = dirigeants_personnes_physiques(dirigeants)

shown = founders if founders else dirigeants

if not shown:
    st.warning("No dirigeants data returned for this company.")
else:
    # Shared state: candidates + confirmed URLs.
    st.session_state.setdefault("founder_social", {})
    st.session_state.setdefault("founder_candidates", {})

    per_row = 3 if len(shown) >= 6 else 2
    for i in range(0, len(shown), per_row):
        cols = st.columns(per_row)
        for j in range(per_row):
            idx = i + j
            if idx >= len(shown):
                continue
            d = shown[idx]

            full_name = " ".join([p for p in [d.prenoms, d.nom] if p]).strip() or "—"
            founder_key = f"{details.siren}:{full_name}"

            confirmed = st.session_state["founder_social"].get(founder_key, {})
            linkedin_url = confirmed.get("linkedin")
            x_url = confirmed.get("x")

            with cols[j]:
                with st.container(border=True):
                    st.markdown(f"**{full_name}**")
                    st.caption(d.qualite or "—")

                    birth = d.date_de_naissance or d.annee_de_naissance
                    meta_bits = [b for b in [birth, d.nationalite] if b]
                    if meta_bits:
                        st.caption(" · ".join(meta_bits))

                    social_row = st.columns([1, 1])
                    with social_row[0]:
                        if linkedin_url:
                            st.link_button("LinkedIn ✓", linkedin_url)
                        else:
                            st.link_button(
                                "Search LinkedIn",
                                google_search_url(
                                    linkedin_people_query(full_name, company_name)
                                ),
                            )
                    with social_row[1]:
                        if x_url:
                            st.link_button("X ✓", x_url)
                        else:
                            st.link_button(
                                "Search X",
                                google_search_url(
                                    x_people_query(full_name, company_name)
                                ),
                            )

                    # Semi-automatic: API-assisted candidate discovery.
                    with st.expander("Find socials (semi-auto)", expanded=False):
                        action_cols = st.columns(2)
                        with action_cols[0]:
                            if st.button(
                                "Find LinkedIn candidates", key=f"find_li_{founder_key}"
                            ):
                                st.session_state["founder_candidates"][
                                    f"{founder_key}:linkedin"
                                ] = search_candidates(
                                    query=linkedin_people_query(
                                        full_name, company_name
                                    ),
                                    kind="linkedin",
                                )
                        with action_cols[1]:
                            if st.button(
                                "Find X candidates", key=f"find_x_{founder_key}"
                            ):
                                st.session_state["founder_candidates"][
                                    f"{founder_key}:x"
                                ] = search_candidates(
                                    query=x_people_query(full_name, company_name),
                                    kind="x",
                                )

                        li_cands: list[SocialCandidate] = st.session_state[
                            "founder_candidates"
                        ].get(f"{founder_key}:linkedin", [])
                        x_cands: list[SocialCandidate] = st.session_state[
                            "founder_candidates"
                        ].get(f"{founder_key}:x", [])

                        if not li_cands and not x_cands:
                            st.caption(
                                "Configure a search provider to fetch candidates automatically, "
                                "or use the search links above."
                            )

                        if li_cands:
                            st.markdown("**LinkedIn candidates**")
                            for k, c in enumerate(li_cands[:5]):
                                st.write(f"- [{c.title}]({c.url})")
                                if c.snippet:
                                    st.caption(c.snippet)
                                if st.button(
                                    "Use this LinkedIn URL",
                                    key=f"use_li_{founder_key}_{k}",
                                ):
                                    st.session_state["founder_social"].setdefault(
                                        founder_key, {}
                                    )["linkedin"] = c.url
                                    st.rerun()

                        if x_cands:
                            st.markdown("**X candidates**")
                            for k, c in enumerate(x_cands[:5]):
                                st.write(f"- [{c.title}]({c.url})")
                                if c.snippet:
                                    st.caption(c.snippet)
                                if st.button(
                                    "Use this X URL",
                                    key=f"use_x_{founder_key}_{k}",
                                ):
                                    st.session_state["founder_social"].setdefault(
                                        founder_key, {}
                                    )["x"] = c.url
                                    st.rerun()

st.divider()


def _fmt_eur(amount: object) -> str:
    if not isinstance(amount, (int, float)):
        return "—"
    # Compact EUR formatting (e.g. 311,448,000 -> 311.4M €)
    v = float(amount)
    if abs(v) >= 1_000_000_000:
        return f"{v/1_000_000_000:.1f}B €"
    if abs(v) >= 1_000_000:
        return f"{v/1_000_000:.1f}M €"
    if abs(v) >= 1_000:
        return f"{v/1_000:.1f}K €"
    return f"{v:.0f} €"


def _latest_financial_year(finances: dict[str, object] | None) -> str | None:
    if not finances:
        return None
    years = []
    for k in finances.keys():
        try:
            years.append(int(k))
        except ValueError:
            continue
    if not years:
        return None
    return str(max(years))


st.subheader("Financials")
if not details.finances:
    st.info("No financial data returned.")
else:
    year = _latest_financial_year(details.finances)
    year_data = details.finances.get(year, {}) if year else {}
    if not isinstance(year_data, dict):
        year_data = {}

    ca = year_data.get("ca")
    rn = year_data.get("resultat_net")

    with st.container(border=True):
        header = "Latest year" if not year else f"Year {year}"
        st.caption(header)
        fin_cols = st.columns(2)
        fin_cols[0].metric("Revenue (CA)", _fmt_eur(ca))
        fin_cols[1].metric("Net income", _fmt_eur(rn))
