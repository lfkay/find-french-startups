import csv
import json
import re
from dataclasses import dataclass
from datetime import date
from io import StringIO

import streamlit as st

from invest_registry.clients.france import (
    FranceCompanySearchClient,
    FranceSearchParams,
    collect_companies,
)
from invest_registry.models import CompanyRecord
from invest_registry.pagination import paginate
from invest_registry.query_packs import get_query_pack
from invest_registry.scoring import employee_band_label
from invest_registry.storage import load_cached_records, save_cached_records

st.set_page_config(layout="wide")


def years_ago(today: date, years: int) -> date:
    try:
        return today.replace(year=today.year - years)
    except ValueError:
        return today.replace(year=today.year - years, day=28)


TRANCHE_EFFECTIF_LT20 = "00,01,02,03,11"
FOUNDED_WITHIN_YEARS = 5
NAF_RE = re.compile(r"^\\d{2}\\.\\d{2}[A-Z]$")


def normalize_naf_override(raw: str | None) -> tuple[str | None, list[str]]:
    if not raw:
        return None, []
    raw = raw.strip().upper()
    if not raw:
        return None, []
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    valid: list[str] = []
    invalid: list[str] = []
    for p in parts:
        # Strip accidental non-NAF characters (e.g. trailing "~") but keep dots.
        cleaned = re.sub(r"[^0-9A-Z.]", "", p)
        if NAF_RE.fullmatch(cleaned):
            valid.append(cleaned)
        else:
            invalid.append(p)
    return (",".join(valid) if valid else None), invalid


@dataclass(frozen=True)
class AdvancedOptions:
    q: str
    activite_principale: str | None
    tranche_effectif_salarie: str | None
    etat_administratif: str | None
    per_page: int
    max_pages_per_search: int | None
    postal_code_prefix: str | None
    founded_within_years: int | None
    employer_filter: str  # "any" | "yes" | "no"


def _override_searches(
    searches: list[FranceSearchParams],
    *,
    q: str,
    activite_principale: str | None,
    tranche_effectif_salarie: str | None,
    etat_administratif: str | None,
) -> list[FranceSearchParams]:
    base = searches[0] if searches else FranceSearchParams(q="")

    q_val = q if q else base.q
    tranche_val = (
        tranche_effectif_salarie
        if tranche_effectif_salarie is not None
        else base.tranche_effectif_salarie
    )
    etat_val = (
        etat_administratif
        if etat_administratif is not None
        else base.etat_administratif
    )

    naf_codes: list[str] = []
    if activite_principale:
        naf_codes = [c.strip() for c in activite_principale.split(",") if c.strip()]

    # If NAF override is provided, replace the pack’s NAF list entirely.
    if naf_codes:
        return [
            FranceSearchParams(
                q=q_val,
                activite_principale=naf,
                code_postal=base.code_postal,
                tranche_effectif_salarie=tranche_val,
                etat_administratif=etat_val,
            )
            for naf in naf_codes
        ]

    return [
        FranceSearchParams(
            q=q_val if q else s.q,
            activite_principale=s.activite_principale,
            code_postal=s.code_postal,
            tranche_effectif_salarie=(
                tranche_effectif_salarie
                if tranche_effectif_salarie is not None
                else s.tranche_effectif_salarie
            ),
            etat_administratif=(
                etat_administratif
                if etat_administratif is not None
                else s.etat_administratif
            ),
        )
        for s in searches
    ]


def records_to_csv_bytes(records: list[CompanyRecord]) -> bytes:
    fieldnames = [
        "siren",
        "name",
        "naf",
        "creation_date",
        "employee_band",
        "employee_band_year",
        "is_employer",
        "siret",
        "postal_code",
        "commune",
        "departement",
        "address",
        "source",
    ]
    buf = StringIO()
    w = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    w.writeheader()
    for r in records:
        w.writerow(r.model_dump(mode="json"))
    return buf.getvalue().encode("utf-8")


def cache_key(
    *,
    pack_name: str,
    paris_only: bool,
    target_count: int,
    adv: AdvancedOptions,
) -> str:
    bits = [
        f"fr-{pack_name}",
        f"paris{int(paris_only)}",
        f"n{target_count}",
        f"q{(adv.q or '').strip()[:24]}",
        f"naf{adv.activite_principale or ''}",
        f"eff{adv.tranche_effectif_salarie or ''}",
        f"etat{adv.etat_administratif or ''}",
        f"pp{adv.per_page}",
        f"mp{adv.max_pages_per_search or 'none'}",
        f"pc{adv.postal_code_prefix or ''}",
        f"fy{adv.founded_within_years or 'none'}",
        f"emp{adv.employer_filter}",
    ]
    return "-".join(bits)


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def fetch_records_cached(
    *,
    pack_name: str,
    paris_only: bool,
    target_count: int,
    q: str,
    activite_principale: str | None,
    tranche_effectif_salarie: str | None,
    etat_administratif: str | None,
    per_page: int,
    max_pages_per_search: int | None,
    postal_code_prefix: str | None,
    founded_within_years: int | None,
    employer_filter: str,
) -> list[dict]:
    pack = get_query_pack(pack_name, paris_only=paris_only)

    searches = _override_searches(
        pack.searches,
        q=q,
        activite_principale=activite_principale,
        tranche_effectif_salarie=tranche_effectif_salarie,
        etat_administratif=etat_administratif,
    )

    min_creation_date = (
        years_ago(date.today(), founded_within_years)
        if founded_within_years is not None
        else None
    )

    eff_prefix = postal_code_prefix or ("75" if paris_only else None)

    with FranceCompanySearchClient() as client:
        records = collect_companies(
            client,
            searches=searches,
            target_count=target_count,
            # Strict mode: keep paging until we hit target_count or exhaust results.
            per_page=per_page,
            max_pages_per_search=max_pages_per_search,
            postal_code_prefix=eff_prefix,
            min_creation_date=min_creation_date,
        )

    if employer_filter == "yes":
        records = [r for r in records if r.is_employer is True]
    elif employer_filter == "no":
        records = [r for r in records if r.is_employer is False]

    return [r.model_dump(mode="json") for r in records]


def fetch_records(
    *,
    pack_name: str,
    paris_only: bool,
    target_count: int,
    use_disk_cache: bool,
    adv: AdvancedOptions,
) -> list[dict]:
    key = cache_key(
        pack_name=pack_name,
        paris_only=paris_only,
        target_count=target_count,
        adv=adv,
    )

    if use_disk_cache:
        cached = load_cached_records(key)
        if cached:
            return [r.model_dump(mode="json") for r in cached][:target_count]

    rows = fetch_records_cached(
        pack_name=pack_name,
        paris_only=paris_only,
        target_count=target_count,
        q=adv.q,
        activite_principale=adv.activite_principale,
        tranche_effectif_salarie=adv.tranche_effectif_salarie,
        etat_administratif=adv.etat_administratif,
        per_page=adv.per_page,
        max_pages_per_search=adv.max_pages_per_search,
        postal_code_prefix=adv.postal_code_prefix,
        founded_within_years=adv.founded_within_years,
        employer_filter=adv.employer_filter,
    )

    if use_disk_cache:
        # Store the same payload we show in the UI.
        save_cached_records(key, [CompanyRecord.model_validate(r) for r in rows])

    return rows


with st.sidebar:
    st.header("Pull settings")
    pack_name = st.selectbox(
        "Query pack",
        options=["blossom_like_france"],
        format_func=lambda x: "Blossom",
    )
    paris_only = st.toggle("Paris-only (postal code starts with 75)", value=False)
    target_count = st.slider(
        "Companies to fetch", min_value=50, max_value=200, value=50, step=10
    )
    use_disk_cache = st.toggle("Use local disk cache (.cache/)", value=True)

    # Defaults for AdvancedOptions (used even if expander unopened).
    q = ""
    activite_principale = ""
    etat_administratif = "A"
    tranche_effectif = TRANCHE_EFFECTIF_LT20
    per_page = 25
    max_pages = 10
    founded_within_years = FOUNDED_WITHIN_YEARS
    postal_prefix = "75" if paris_only else ""
    employer_filter = "any"

    with st.expander("Advanced", expanded=False):
        q = st.text_input(
            "q (keyword / name search)", value="", placeholder="e.g. fintech"
        )
        activite_principale = st.text_input(
            "NAF (activite_principale)",
            value="",
            placeholder="e.g. 62.01Z (or CSV: 62.01Z,58.29C)",
            help="Overrides the query pack NAF codes when set.",
        )
        etat_administratif = st.selectbox(
            "etat_administratif",
            options=["A", "C", ""],
            format_func=lambda x: (
                "Active (A)" if x == "A" else "Closed (C)" if x == "C" else "Any"
            ),
            index=0,
        )
        tranche_effectif = st.text_input(
            "tranche_effectif_salarie (codes CSV)",
            value=TRANCHE_EFFECTIF_LT20,
            help="Example: 00,01,02,03,11 (≈ <20). Leave blank for any.",
        )
        per_page = st.slider("per_page", min_value=1, max_value=25, value=25)
        max_pages = st.number_input(
            "max_pages_per_search",
            min_value=0,
            max_value=50,
            value=0,
            help="0 means no cap (strict mode).",
        )
        founded_within_years = st.number_input(
            "Founded within (years)",
            min_value=0,
            max_value=50,
            value=FOUNDED_WITHIN_YEARS,
            help="0 disables this filter.",
        )
        postal_prefix = st.text_input(
            "postal_code_prefix (post-filter)",
            value="75" if paris_only else "",
            help="Overrides the Paris-only toggle when set.",
        )
        employer_filter = st.selectbox(
            "Employer filter",
            options=["any", "yes", "no"],
            index=0,
        )

    run = st.button("Fetch / Refresh", type="primary")

if run:
    naf_override, naf_invalid = normalize_naf_override(activite_principale)
    if naf_invalid:
        st.error(
            "Invalid NAF code(s): "
            + ", ".join(f"`{x}`" for x in naf_invalid)
            + ". Expected format like `62.01Z` (or CSV list)."
        )
        st.stop()

    adv = AdvancedOptions(
        q=q.strip(),
        activite_principale=naf_override,
        tranche_effectif_salarie=tranche_effectif.strip() or None,
        etat_administratif=etat_administratif or None,
        per_page=int(per_page),
        max_pages_per_search=(None if int(max_pages) == 0 else int(max_pages)),
        postal_code_prefix=postal_prefix.strip() or None,
        founded_within_years=(
            None if int(founded_within_years) == 0 else int(founded_within_years)
        ),
        employer_filter=employer_filter,
    )
    try:
        with st.spinner("Fetching companies…"):
            fetched_rows = fetch_records(
                pack_name=pack_name,
                paris_only=paris_only,
                target_count=target_count,
                use_disk_cache=use_disk_cache,
                adv=adv,
            )
    except Exception as e:
        st.error(f"Fetch failed: {e}")
        st.stop()
    st.session_state["rows"] = fetched_rows
    st.session_state["page"] = 1


rows: list[dict] | None = st.session_state.get("rows")
if not rows:
    st.info("Configure the sidebar, then click **Fetch / Refresh**.")
    st.stop()

records = [CompanyRecord.model_validate(r) for r in rows]
records = sorted(records, key=lambda r: r.creation_date or date.min, reverse=True)

page_size = 10
page = int(st.session_state.get("page", 1))
page_records, total_pages = paginate(records, page=page, page_size=page_size)

with st.container(horizontal=True):
    if st.button("Prev", disabled=(page <= 1)):
        st.session_state["page"] = max(1, page - 1)
        st.rerun()
    if st.button("Next", disabled=(total_pages == 0 or page >= total_pages)):
        st.session_state["page"] = min(total_pages, page + 1)
        st.rerun()

if total_pages:
    st.caption(
        f"Page **{min(page, total_pages)}** of **{total_pages}** (showing {len(page_records)} of {len(records)})"
    )


def _render_company_card(r: CompanyRecord) -> None:
    inpi_url = f"https://data.inpi.fr/entreprises/{r.siren}"
    created = r.creation_date.isoformat() if r.creation_date else "—"
    band = employee_band_label(r.employee_band) or "—"
    band_year = str(r.employee_band_year) if r.employee_band_year else "—"
    employer = (
        "Yes" if r.is_employer is True else "No" if r.is_employer is False else "—"
    )

    loc_bits = [b for b in [r.commune, r.departement, r.postal_code] if b]
    loc = " · ".join(loc_bits) if loc_bits else "—"

    addr = (r.address or "").strip()
    if len(addr) > 90:
        addr = addr[:87].rstrip() + "…"
    if not addr:
        addr = "—"

    with st.container(border=True):
        st.markdown(f"**{r.name}**")
        st.markdown(f"[INPI ({r.siren})]({inpi_url})")
        st.caption(loc)

        cols = st.columns(2)
        with cols[0]:
            st.caption(f"Created: {created}")
            st.caption(f"Employees: {band} ({band_year})")
            st.caption(f"NAF: {r.naf or '—'}")
        with cols[1]:
            st.caption(f"Employer: {employer}")
            st.caption(f"SIRET: {r.siret or '—'}")
            st.caption(f"Address: {addr}")

        actions = st.columns(2)
        with actions[0]:
            if st.button("Deep dive", key=f"deep_dive_{r.siren}", type="primary"):
                st.switch_page(
                    "pages/2_Company_Deep_Dive.py", query_params={"siren": r.siren}
                )
        with actions[1]:
            st.link_button("INPI", inpi_url)


for i in range(0, len(page_records), 2):
    cols = st.columns(2)
    with cols[0]:
        _render_company_card(page_records[i])
    if i + 1 < len(page_records):
        with cols[1]:
            _render_company_card(page_records[i + 1])
    else:
        with cols[1]:
            st.empty()
