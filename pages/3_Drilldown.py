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
    _linear_score,
    build_scoreboard,
    delivery_days_to_score,
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
    st.subheader("Criterion averages")
    comp = pd.DataFrame({
        "Criterion": [CRITERIA_LABELS[c] for c in CRITERIA],
        "Score": [row[c] for c in CRITERIA],
        "Weight": [CRITERIA_WEIGHTS[c] for c in CRITERIA],
    })
    comp["Contribution"] = (comp["Score"] * comp["Weight"]).round(3)

    # Per-criterion tile spec: what real average to show and how to format it.
    #   Delivery → average days (measured)   Price → average € (measured)
    #   Quality / Communication → average 1–5 rating
    def _avg_days(r):
        v = r["avg_delivery_days"]
        return "—" if pd.isna(v) else f"{v:.1f} days"

    def _avg_eur(r):
        v = r["avg_price_eur"]
        return "—" if pd.isna(v) else f"€{v:,.0f}"

    tile_spec = {
        "delivery_time": ("Delivery Time", _avg_days(row),
                          "Average days from order to delivery (measured)."),
        "quality": ("Quality", f"{row['quality']:.2f}" if pd.notna(row['quality']) else "—",
                    "Average of this supplier's quality ratings (1–5)."),
        "price": ("Price", _avg_eur(row),
                  "Average order value (measured). Cheaper = better score."),
        "communication": ("Communication",
                          f"{row['communication']:.2f}" if pd.notna(row['communication']) else "—",
                          "Average of this supplier's communication ratings (1–5)."),
    }

    # 2×2 tiles: big number = the real average; the delta shows the 1–5 score
    # that average maps to (so you see both the measurement and its score).
    tile_rows = [CRITERIA[i:i + 2] for i in range(0, len(CRITERIA), 2)]
    for pair in tile_rows:
        cols = st.columns(2)
        for col, crit in zip(cols, pair):
            label, value, help_txt = tile_spec[crit]
            score = row[crit]
            col.metric(
                label, value,
                delta=(f"score {score:.2f}/5" if pd.notna(score) else None),
                delta_color="off",
                help=help_txt + f" Weight in overall: {CRITERIA_WEIGHTS[crit]*100:.0f}%.",
            )
    if row.get("missing_delivery_data", False):
        st.caption("⚠ No delivered orders yet — delivery time is unmeasured "
                   "(scored neutral 3.0).")

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
# Trend over time — quarterly average overall score, consistent with the
# measured scoring (per-order delivery score from days, price score from €,
# quality & communication from ratings).
# --------------------------------------------------------------------------- #
st.subheader("Performance trend")
sup_ratings = orders[orders["supplier_id"] == sid].merge(
    ratings[["order_id", "quality", "communication"]], on="order_id", how="left"
)
if sup_ratings["order_date"].notna().any():
    sup_ratings = sup_ratings.dropna(subset=["order_date"]).copy()
    # Per-order price score, scaled across this supplier's own orders.
    pmin, pmax = sup_ratings["amount_eur"].min(), sup_ratings["amount_eur"].max()
    sup_ratings["delivery_time"] = sup_ratings["delivery_days"].apply(
        lambda d: 3.0 if pd.isna(d) else delivery_days_to_score(d)
    )
    sup_ratings["price"] = sup_ratings["amount_eur"].apply(
        lambda v: _linear_score(v, best=pmin, worst=pmax)
    )
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
    # Show the measured delivery (date + days) per order, plus the quality &
    # communication ratings for that order.
    rating_cols = ["quality", "communication"]
    sup_orders = sup_orders.merge(
        ratings[["order_id", *rating_cols]], on="order_id", how="left"
    )
    sup_orders["order_date"] = sup_orders["order_date"].dt.date
    sup_orders["delivery_date"] = pd.to_datetime(sup_orders["delivery_date"]).dt.date
    ov = sup_orders.rename(columns={
        "order_id": "Order", "order_date": "Ordered", "delivery_date": "Delivered",
        "delivery_days": "Days", "amount_eur": "Amount (€)", "status": "Status",
        "quality": "Quality", "communication": "Communication",
    })[["Order", "Ordered", "Delivered", "Days", "Amount (€)", "Status",
        "Quality", "Communication"]]
    st.dataframe(
        ov.sort_values("Ordered"), use_container_width=True, hide_index=True,
        column_config={
            "Amount (€)": st.column_config.NumberColumn(format="€%.0f"),
            "Days": st.column_config.NumberColumn(format="%d d"),
        },
    )
    avg_days = sup_orders["delivery_days"].mean()
    days_txt = f" · avg delivery {avg_days:.1f} days" if pd.notna(avg_days) else ""
    st.caption(
        f"{len(sup_orders)} order(s) · total €{sup_orders['amount_eur'].sum():,.0f}"
        f"{days_txt}"
    )
