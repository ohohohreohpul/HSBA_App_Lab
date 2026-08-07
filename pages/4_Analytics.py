"""Analytics — portfolio-level KPIs and charts, all filterable."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from lib.core import (
    CRITERIA,
    CRITERIA_LABELS,
    DEFAULT_THRESHOLD,
    apply_filters,
    build_scoreboard,
)
from lib.ui import breadcrumb, kpi_row

# Chart palette — editorial. Data marks are ink; the only meaningful colour is
# the risk palette, kept in sync with lib.theme so "High" is the same red
# everywhere.
RISK_COLORS = {"High": "#c0392b", "Medium": "#b07400", "Low": "#2f7d55"}
ACCENT = "#1a1a1a"

# Data source: the scored board — one row per supplier.
board = build_scoreboard()

breadcrumb("Home", "Analytics")
st.title("Analytics")

# --------------------------------------------------------------------------- #
# Filters — every chart below reacts to these
# --------------------------------------------------------------------------- #
with st.expander("Filters", expanded=False):
    a1, a2, a3 = st.columns(3)
    with a1:
        countries = st.multiselect("Country", sorted(board["country"].dropna().unique()))
    with a2:
        categories = st.multiselect("Category", sorted(board["category_name"].dropna().unique()))
    with a3:
        risk_levels = st.multiselect("Risk level", ["High", "Medium", "Low"])

view = apply_filters(board, {
    "countries": countries, "categories": categories, "risk_levels": risk_levels,
})

if view.empty:
    st.warning("No suppliers match the current filters.")
    st.stop()

# --------------------------------------------------------------------------- #
# KPI dashboard
# --------------------------------------------------------------------------- #
kpi_row([
    {"label": "Suppliers", "value": len(view)},
    {"label": "Avg. score", "value": f"{view['overall_score'].mean():.2f}"},
    {"label": "Below threshold", "value": int((view['overall_score'] < DEFAULT_THRESHOLD).sum())},
    {"label": "High risk", "value": int((view['risk_level'] == 'High').sum())},
    {"label": "Countries", "value": view['country'].nunique()},
    {"label": "Categories", "value": view['category_name'].nunique()},
])
st.write("")

# --------------------------------------------------------------------------- #
# Row 1: Risk distribution (pie) + Score histogram
# --------------------------------------------------------------------------- #
r1c1, r1c2 = st.columns(2)
with r1c1:
    st.subheader("Risk distribution")
    rd = view["risk_level"].value_counts().reindex(["High", "Medium", "Low"]).fillna(0).reset_index()
    rd.columns = ["risk", "count"]
    pie = (
        alt.Chart(rd)
        .mark_arc(innerRadius=55)
        .encode(
            theta="count:Q",
            color=alt.Color("risk:N",
                            scale=alt.Scale(domain=list(RISK_COLORS), range=list(RISK_COLORS.values())),
                            legend=alt.Legend(title="Risk")),
            tooltip=["risk", "count"],
        )
        .properties(height=260)
    )
    st.altair_chart(pie, use_container_width=True)

with r1c2:
    st.subheader("Score distribution")
    hist = (
        alt.Chart(view)
        .mark_bar(color=ACCENT, cornerRadiusEnd=3)
        .encode(
            x=alt.X("overall_score:Q", bin=alt.Bin(step=0.25), title="Overall score"),
            y=alt.Y("count():Q", title="Suppliers"),
            tooltip=[alt.Tooltip("count():Q", title="Suppliers")],
        )
        .properties(height=260)
    )
    st.altair_chart(hist, use_container_width=True)

# --------------------------------------------------------------------------- #
# Row 2: Country distribution + Category avg score (bar charts)
# --------------------------------------------------------------------------- #
r2c1, r2c2 = st.columns(2)
with r2c1:
    st.subheader("Suppliers by country")
    cc = view["country"].value_counts().head(12).reset_index()
    cc.columns = ["country", "count"]
    st.altair_chart(
        alt.Chart(cc).mark_bar(color=ACCENT, cornerRadiusEnd=3).encode(
            x=alt.X("count:Q", title="Suppliers"),
            y=alt.Y("country:N", sort="-x", title=None),
            tooltip=["country", "count"],
        ).properties(height=300),
        use_container_width=True,
    )
with r2c2:
    st.subheader("Avg. score by category")
    cat = view.groupby("category_name")["overall_score"].mean().reset_index()
    st.altair_chart(
        alt.Chart(cat).mark_bar(cornerRadiusEnd=3).encode(
            x=alt.X("overall_score:Q", scale=alt.Scale(domain=[0, 5]), title="Avg. score"),
            y=alt.Y("category_name:N", sort="-x", title=None),
            color=alt.Color("overall_score:Q",
                            scale=alt.Scale(scheme="redyellowgreen", domain=[2, 5]),
                            legend=None),
            tooltip=["category_name", alt.Tooltip("overall_score", format=".2f")],
        ).properties(height=300),
        use_container_width=True,
    )

# --------------------------------------------------------------------------- #
# Row 3: Heatmap — avg criterion score by category
# --------------------------------------------------------------------------- #
st.subheader("Category × criterion heatmap")
st.caption(
    "Each cell is that **category's average score for one criterion**. "
    "Green = strong, red = weak — so you can spot which category lags on a "
    "specific area (e.g. weak on Delivery Time but strong on Quality) and target "
    "improvement there."
)
heat_src = view.melt(
    id_vars="category_name", value_vars=CRITERIA,
    var_name="criterion", value_name="score",
)
heat_src["criterion"] = heat_src["criterion"].map(CRITERIA_LABELS)
heat = heat_src.groupby(["category_name", "criterion"])["score"].mean().reset_index()
st.altair_chart(
    alt.Chart(heat).mark_rect().encode(
        x=alt.X("criterion:N", title=None),
        y=alt.Y("category_name:N", title=None),
        color=alt.Color("score:Q", scale=alt.Scale(scheme="redyellowgreen", domain=[2, 5]),
                        legend=alt.Legend(title="Avg")),
        tooltip=["category_name", "criterion", alt.Tooltip("score", format=".2f")],
    ).properties(height=260),
    use_container_width=True,
)
