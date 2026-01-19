import streamlit as st

st.set_page_config(page_title="Invest Registry", layout="wide")

nav = st.navigation(
    [
        st.Page("pages/1_Search.py", title="Search", default=True, url_path="search"),
        st.Page("pages/2_Company_Deep_Dive.py", title="Company Deep Dive", url_path="deep-dive"),
    ]
)
nav.run()
