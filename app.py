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
from lib.admin import is_admin

st.set_page_config(
    page_title="Supplier Scorecard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)
inject_theme()

# --------------------------------------------------------------------------- #
# Admin is "hidden": it only enters the top nav after authentication. Until
# then it stays reachable via a query param (?admin=unlock) that the discreet
# footer link on the Landing page sets — so regular users never see it, but the
# route still exists.  See pages/5_Admin.py for the login gate.
# --------------------------------------------------------------------------- #
landing = st.Page("pages/1_Landing.py", title="Home", icon="🏠", default=True)
scorecards = st.Page("pages/2_Scorecards.py", title="Scorecards", icon="📋")
drilldown = st.Page("pages/3_Drilldown.py", title="Drilldown", icon="🔎")
analytics = st.Page("pages/4_Analytics.py", title="Analytics", icon="📈")
admin = st.Page("pages/5_Admin.py", title="Admin", icon="🔐")

pages = [landing, scorecards, drilldown, analytics]

# Reveal the Admin route once the user is authenticated OR is in the middle of
# unlocking it (query param set by the discreet Landing-page link).
unlocking = st.query_params.get("admin") == "unlock"
if is_admin() or unlocking:
    pages.append(admin)

nav = st.navigation(pages, position="top")
nav.run()
