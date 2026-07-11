"""Drilldown — the full profile of one supplier."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from lib.core import (
    CRITERIA,
    CRITERIA_LABELS,
    CRITERIA_WEIGHTS,
    DEFAULT_THRESHOLD,
    build_scoreboard,
    load_tables,
    risk_color,
    suggest_names,
)
from lib.ui import breadcrumb, risk_badge_html, score_info_popover

board = build_scoreboard()
tables = load_tables()
orders, ratings = tables["orders"], tables["ratings"]
names = board["supplier_name"].tolist()

breadcrumb("Home", "Scorecards", "Drilldown")

# --------------------------------------------------------------------------- #
# Supplier picker (honours a jump from the Scorecards page) + fuzzy search
# --------------------------------------------------------------------------- #
preselect = st.session_state.pop("drilldown_supplier", None)
sc1, sc2 = st.columns([2, 3])
with sc1:
    q = st.text_input("🔍 Find supplier", placeholder="Type a name (typos ok)…")
options = names
if q:
    sugg = suggest_names(q, names, limit=15)
    options = sugg or names
default_idx = options.index(preselect) if preselect in options else 0
with sc2:
    supplier = st.selectbox("Supplier", options, index=default_idx)

row = board[board["supplier_name"] == supplier].iloc[0]
sid = int(row["supplier_id"])
threshold = DEFAULT_THRESHOLD

# --------------------------------------------------------------------------- #
# Header: name, meta, overall score card
# --------------------------------------------------------------------------- #
st.title(supplier)
meta_l, meta_r = st.columns([3, 2])
with meta_l:
    st.markdown(
        f"{risk_badge_html(row['risk_level'])} &nbsp; "
        f"**{row['country']}** · {row['category_name']} · "
        f"✉ {row['contact_email']}",
        unsafe_allow_html=True,
    )
    if row["low_confidence"]:
        st.warning(f"⚠ Low confidence — only {int(row['num_ratings'])} rated order(s).")
with meta_r:
    score_info_popover("drill")

color = risk_color(row["risk_level"])
mc1, mc2, mc3, mc4 = st.columns(4)
mc1.metric("Overall score", f"{row['overall_score']:.2f}")
mc2.metric("Orders", int(row["num_orders"]))
mc3.metric("Total spend", f"€{row['total_spend']:,.0f}")
last = row["last_order"]
mc4.metric("Last order", last.date().isoformat() if pd.notna(last) else "—")

st.divider()

# --------------------------------------------------------------------------- #
# Score components — with the exact weighted contribution of each criterion
# --------------------------------------------------------------------------- #
left, right = st.columns([1, 1])
with left:
    st.subheader("Average rating per criterion")
    comp = pd.DataFrame({
        "Criterion": [CRITERIA_LABELS[c] for c in CRITERIA],
        "Score": [row[c] for c in CRITERIA],
        "Weight": [CRITERIA_WEIGHTS[c] for c in CRITERIA],
    })
    comp["Contribution"] = (comp["Score"] * comp["Weight"]).round(3)

    # Four metric tiles (2×2), each showing the average rating for a criterion.
    tile_rows = [CRITERIA[i:i + 2] for i in range(0, len(CRITERIA), 2)]
    for pair in tile_rows:
        cols = st.columns(2)
        for col, crit in zip(cols, pair):
            avg = row[crit]
            col.metric(
                CRITERIA_LABELS[crit],
                f"{avg:.2f}" if pd.notna(avg) else "—",
                help=f"Average of this supplier's order ratings for "
                     f"{CRITERIA_LABELS[crit]} (1–5 scale). "
                     f"Weight in overall score: {CRITERIA_WEIGHTS[crit]*100:.0f}%.",
            )
    st.caption(
        "Each tile is the average of this supplier's order ratings (1–5). "
        "Overall = Σ (average × weight) = "
        + " + ".join(f"{r.Score:.2f}×{r.Weight:.2f}" for r in comp.itertuples())
        + f" = **{row['overall_score']:.2f}**"
    )

with right:
    st.subheader("Threshold violations")
    violations = comp[comp["Score"] < threshold]
    if violations.empty:
        st.success(f"✅ No criterion below the {threshold:.1f} threshold.")
    else:
        for r in violations.itertuples():
            st.error(f"**{r.Criterion}**: {r.Score:.2f} (below {threshold:.1f})")

    # Recommendations derived from the weakest criteria.
    st.subheader("Recommendations")
    weakest = comp.sort_values("Score").iloc[0]
    recs = []
    if row["overall_score"] < threshold:
        recs.append("Overall score is below threshold — consider a formal review "
                    "or corrective-action plan.")
    if weakest["Score"] < 3.5:
        recs.append(f"Weakest area is **{weakest['Criterion']}** "
                    f"({weakest['Score']:.2f}). Raise this in the next review.")
    if row["low_confidence"]:
        recs.append("Few rated orders — gather more feedback before major decisions.")
    if not recs:
        recs.append("Performing well across the board. Maintain the relationship.")
    for r in recs:
        st.markdown(f"- {r}")

st.divider()

# --------------------------------------------------------------------------- #
# Trend over time — quarterly average of this supplier's order ratings
# --------------------------------------------------------------------------- #
st.subheader("Performance trend")
sup_ratings = ratings[ratings["supplier_id"] == sid].merge(
    orders[["order_id", "order_date"]], on="order_id", how="left"
)
if sup_ratings["order_date"].notna().any():
    sup_ratings = sup_ratings.dropna(subset=["order_date"]).copy()
    sup_ratings["overall"] = sum(sup_ratings[c] * CRITERIA_WEIGHTS[c] for c in CRITERIA)
    sup_ratings["period"] = sup_ratings["order_date"].dt.to_period("Q").dt.start_time
    trend = sup_ratings.groupby("period")["overall"].mean().reset_index()
    line = (
        alt.Chart(trend)
        .mark_line(point=True, color="#4f46e5", strokeWidth=3)
        .encode(
            x=alt.X("period:T", title="Quarter"),
            y=alt.Y("overall:Q", scale=alt.Scale(domain=[1, 5]), title="Avg. overall"),
            tooltip=[alt.Tooltip("period:T", title="Quarter"),
                     alt.Tooltip("overall:Q", format=".2f")],
        )
        .properties(height=240)
    )
    rule = alt.Chart(pd.DataFrame({"y": [threshold]})).mark_rule(
        color="#ef4444", strokeDash=[5, 4]).encode(y="y:Q")
    st.altair_chart(line + rule, use_container_width=True)
    st.caption("Dashed red line = underperformer threshold.")
else:
    st.info("Not enough dated orders to plot a trend.")

st.divider()

# --------------------------------------------------------------------------- #
# Orders table
# --------------------------------------------------------------------------- #
st.subheader("Orders")
sup_orders = orders[orders["supplier_id"] == sid].copy()
if sup_orders.empty:
    st.info("No orders on record.")
else:
    sup_orders = sup_orders.merge(ratings[["order_id", *CRITERIA]], on="order_id", how="left")
    sup_orders["order_date"] = sup_orders["order_date"].dt.date
    ov = sup_orders.rename(columns={
        "order_id": "Order", "order_date": "Date", "amount_eur": "Amount (€)",
        "status": "Status", **CRITERIA_LABELS,
    })[["Order", "Date", "Amount (€)", "Status", *CRITERIA_LABELS.values()]]
    st.dataframe(
        ov.sort_values("Date"), use_container_width=True, hide_index=True,
        column_config={"Amount (€)": st.column_config.NumberColumn(format="€%.0f")},
    )
    st.caption(f"{len(sup_orders)} order(s) · total €{sup_orders['amount_eur'].sum():,.0f}")
