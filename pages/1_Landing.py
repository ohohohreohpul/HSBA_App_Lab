"""Landing page — entry point into the platform."""

import streamlit as st

from lib.core import build_scoreboard
from lib.ui import kpi_row

board = build_scoreboard()

# --------------------------------------------------------------------------- #
# Hero
# --------------------------------------------------------------------------- #
st.markdown(
    """
    <div class="hero">
        <h1>📊 Supplier Scorecard</h1>
        <p>Evaluate, compare and monitor your suppliers in one place. Spot risks
        early, understand every score, and drill into the detail — from a single
        clean workflow.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.write("")

# Primary CTA → the main working page.
c1, c2, c3 = st.columns([1.2, 1, 3])
with c1:
    if st.button("Open Scorecards  →", type="primary", use_container_width=True):
        st.switch_page("pages/2_Scorecards.py")
with c2:
    if st.button("View Analytics", use_container_width=True):
        st.switch_page("pages/4_Analytics.py")

st.write("")

# --------------------------------------------------------------------------- #
# Quick-summary KPIs
# --------------------------------------------------------------------------- #
n = len(board)
avg = board["overall_score"].mean()
high_risk = int((board["risk_level"] == "High").sum())
countries = board["country"].nunique()
# Suppliers whose orders are all still open (cancelled / in transit), so no
# delivery has completed yet — an unfinished-delivery count, not a data error.
unfinished = int(board["missing_delivery_data"].sum())

st.subheader("At a glance")
kpi_row([
    {"label": "Suppliers", "value": n, "sub": f"{countries} countries"},
    {"label": "Avg. score", "value": f"{avg:.2f}", "sub": "weighted, 1–5"},
    {"label": "High risk", "value": high_risk, "sub": "< 2.5 overall"},
    {"label": "Unfinished deliveries", "value": unfinished, "sub": "no completed order yet"},
])

st.write("")
st.divider()

# --------------------------------------------------------------------------- #
# What you can do — short overview of the workflow
# --------------------------------------------------------------------------- #
st.subheader("The workflow")
w1, w2, w3 = st.columns(3)
with w1:
    st.markdown("#### 📋 Scorecards")
    st.write(
        "One powerful table of every supplier. Filter, fuzzy-search, sort and "
        "export. Risky suppliers are highlighted so problems jump out."
    )
    if st.button("Go to Scorecards", key="w_score", use_container_width=True):
        st.switch_page("pages/2_Scorecards.py")
with w2:
    st.markdown("#### 🔎 Drilldown")
    st.write(
        "Open any supplier for the full profile: score components, trends over "
        "time, orders, threshold violations and recommendations."
    )
    if st.button("Go to Drilldown", key="w_drill", use_container_width=True):
        st.switch_page("pages/3_Drilldown.py")
with w3:
    st.markdown("#### 📈 Analytics")
    st.write(
        "Portfolio-level view: risk distribution, country and category "
        "breakdowns, and score trends — all filterable."
    )
    if st.button("Go to Analytics", key="w_ana", use_container_width=True):
        st.switch_page("pages/4_Analytics.py")

# --------------------------------------------------------------------------- #
# Footer
# --------------------------------------------------------------------------- #
st.markdown(
    """
    <div class="app-footer">
        Supplier Scorecard · <strong>Innovation Management M.Sc.</strong><br>
        HSBA Hamburg School of Business Administration
    </div>
    """,
    unsafe_allow_html=True,
)
