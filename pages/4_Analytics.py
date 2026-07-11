"""Analytics — portfolio-level KPIs and charts, all filterable."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from lib.core import (
    CRITERIA,
    CRITERIA_LABELS,
    CRITERIA_WEIGHTS,
    DEFAULT_THRESHOLD,
    _linear_score,
    apply_filters,
    build_scoreboard,
    delivery_days_to_score,
    load_tables,
)
from lib.ui import breadcrumb, kpi_row

# Consistent risk palette used across the app.
RISK_COLORS = {"High": "#ef4444", "Medium": "#f59e0b", "Low": "#10b981"}
ACCENT = "#4f46e5"

board = build_scoreboard()
tables = load_tables()
orders, ratings = tables["orders"], tables["ratings"]

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

# --------------------------------------------------------------------------- #
# Row 4: Monthly score trend (line) across the filtered portfolio
# --------------------------------------------------------------------------- #
st.subheader("Monthly score trend")
ids = set(view["supplier_id"])
tr = orders[orders["supplier_id"].isin(ids)].merge(
    ratings[["order_id", "quality", "communication"]], on="order_id", how="left"
).dropna(subset=["order_date"]).copy()
if tr.empty:
    st.info("No dated orders for the current selection.")
else:
    # Per-order overall consistent with the measured scoring.
    pmin, pmax = tr["amount_eur"].min(), tr["amount_eur"].max()
    tr["delivery_time"] = tr["delivery_days"].apply(
        lambda d: 3.0 if pd.isna(d) else delivery_days_to_score(d)
    )
    tr["price"] = tr["amount_eur"].apply(lambda v: _linear_score(v, best=pmin, worst=pmax))
    tr["overall"] = sum(tr[c] * CRITERIA_WEIGHTS[c] for c in CRITERIA)
    tr["month"] = tr["order_date"].dt.to_period("M").dt.start_time
    monthly = tr.groupby("month").agg(
        avg=("overall", "mean"), n=("overall", "size")).reset_index()
    base = alt.Chart(monthly).encode(x=alt.X("month:T", title=None))
    line = base.mark_line(point=True, color=ACCENT, strokeWidth=3).encode(
        y=alt.Y("avg:Q", scale=alt.Scale(domain=[1, 5]), title="Avg. overall"),
        tooltip=[alt.Tooltip("month:T", title="Month"),
                 alt.Tooltip("avg:Q", format=".2f"),
                 alt.Tooltip("n:Q", title="Ratings")],
    )
    rule = alt.Chart(pd.DataFrame({"y": [DEFAULT_THRESHOLD]})).mark_rule(
        color="#ef4444", strokeDash=[5, 4]).encode(y="y:Q")
    st.altair_chart(line + rule, use_container_width=True)
    st.caption("Dashed red line = underperformer threshold.")
