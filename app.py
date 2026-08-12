"""
Supplier Scorecard — application entrypoint.
============================================================================

Multipage Streamlit app with a top-navigation workflow:

    Landing → Scorecards → Drilldown → Analytics   (+ hidden Admin)

Run:  python -m streamlit run app.py

All pages live in ``pages/`` and share logic from ``lib/`` so the scoring
rules and styling stay consistent across the whole app.
"""

import streamlit as st

from lib.ui import inject_theme

st.set_page_config(
    page_title="Supplier Scorecard",
    page_icon=":material/table_rows:",
    layout="wide",
    initial_sidebar_state="collapsed",
)
inject_theme()

# --------------------------------------------------------------------------- #
# Top-navigation workflow. Admin sits last (right after Analytics) as a
# permanent but visually greyed-out entry — see styles.py / inject_theme for
# the grey styling of the final nav item. Clicking it opens the login gate.
# --------------------------------------------------------------------------- #
landing = st.Page("pages/1_Landing.py", title="Home", icon=":material/home:", default=True)
scorecards = st.Page("pages/2_Scorecards.py", title="Scorecards", icon=":material/table_rows:")
drilldown = st.Page("pages/3_Drilldown.py", title="Drilldown", icon=":material/search:")
analytics = st.Page("pages/4_Analytics.py", title="Analytics", icon=":material/monitoring:")
admin = st.Page("pages/5_Admin.py", title="Admin")

pages = [landing, scorecards, drilldown, analytics, admin]

nav = st.navigation(pages, position="top")
nav.run()
