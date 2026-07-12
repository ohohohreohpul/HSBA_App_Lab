"""Drilldown — the full profile of one supplier."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from lib.core import (
    CANCEL_WEIGHT,
    CRITERIA,
    CRITERIA_LABELS,
    CRITERIA_WEIGHTS,
    DEFAULT_THRESHOLD,
    _linear_score,
    build_scoreboard,
    cancel_reliability_score,
    delivery_days_to_score,
    load_tables,
    risk_color,
    suggest_names,
    weighted_overall,
)
from lib.ui import (
    breadcrumb,
    confidence_badge_html,
    risk_badge_html,
    score_info_popover,
    special_badge_html,
)

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
    special_badge = (
        f"{special_badge_html(int(row['num_special_orders']))} &nbsp; "
        if row.get("has_special_orders", False) else ""
    )
    st.markdown(
        f"{risk_badge_html(row['risk_level'], prefix='Risk:')} &nbsp; "
        f"{confidence_badge_html(bool(row['low_confidence']), int(row['num_ratings']))} &nbsp; "
        f"{special_badge}"
        f"**{row['country']}** · {row['category_name']} · "
        f"✉ {row['contact_email']}",
        unsafe_allow_html=True,
    )
    if row["low_confidence"]:
        st.warning(
            f"⚠ **Low confidence** — this score is based on only "
            f"{int(row['num_ratings'])} rated order(s), so treat it with caution."
        )
    if row.get("has_special_orders", False):
        st.info(
            f"★ **Special circumstance** — this supplier stepped in on "
            f"{int(row['num_special_orders'])} order(s) where a high price was "
            "justified (e.g. the only supplier able to deliver). Those orders are "
            "**excluded from the price score**, so a low price score here doesn't "
            "mean they're simply expensive — they're a reliable fallback when no "
            "one else can deliver."
        )
with meta_r:
    score_info_popover("drill")

color = risk_color(row["risk_level"])
mc1, mc2, mc3, mc4, mc5 = st.columns(5)
mc1.metric("Overall score", f"{row['overall_score']:.2f}")
mc2.metric("Orders", int(row["num_orders"]),
           help="All orders on record (delivered, in transit and cancelled).")
mc3.metric("Total spend", f"€{row['total_spend']:,.0f}",
           help="Delivered + in-transit orders. Cancelled orders are excluded.")
n_canc = int(row["num_cancelled"])
crate = row.get("cancel_rate")
mc4.metric(
    "Cancelled", n_canc,
    delta=(f"{crate*100:.0f}% of resolved" if pd.notna(crate) else None),
    delta_color="inverse",
    help="Cancellations vs delivered orders drive the reliability score "
         f"({int(round(CANCEL_WEIGHT*100))}% of the overall). More cancellations "
         "lower the score exponentially.",
)
last = row["last_order"]
mc5.metric("Last order", last.date().isoformat() if pd.notna(last) else "—")

# Flag a poor cancellation record explicitly.
if pd.notna(crate) and crate >= 0.25:
    st.warning(
        f"⚠ **High cancellation rate** — {n_canc} of "
        f"{n_canc + int(row['num_delivered'])} resolved orders were cancelled "
        f"({crate*100:.0f}%). This lowers the overall score via the reliability "
        f"component (reliability score {row['cancel_score']:.2f}/5)."
    )

st.divider()

# --------------------------------------------------------------------------- #
# Score components — with the exact weighted contribution of each criterion
# --------------------------------------------------------------------------- #
left, right = st.columns([1, 1])
with left:
    st.subheader("Criterion averages")
    # Effective weights: the four base criteria share (1 - CANCEL_WEIGHT) of the
    # overall, reliability takes CANCEL_WEIGHT. Listing reliability here as a fifth
    # row means "Threshold violations" and "weakest area" account for the whole
    # overall score, not just the base.
    comp = pd.DataFrame({
        "Criterion": [CRITERIA_LABELS[c] for c in CRITERIA] + ["Reliability"],
        "Score": [row[c] for c in CRITERIA] + [row.get("cancel_score")],
        "Weight": [w * (1.0 - CANCEL_WEIGHT) for w in CRITERIA_WEIGHTS.values()]
                  + [CANCEL_WEIGHT],
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

    # The four base criteria share 85% of the overall (the base), split by their
    # own weights; reliability is the remaining 15%. So a criterion's *effective*
    # weight in the overall is (1 - CANCEL_WEIGHT) × its base weight — that's what
    # we show, so the five tiles' weights sum to 100% and reconcile to "Overall".
    base_share = 1.0 - CANCEL_WEIGHT

    # 2×2 tiles: big number = the real average; the delta shows the 1–5 score
    # that average maps to (so you see both the measurement and its score).
    tile_rows = [CRITERIA[i:i + 2] for i in range(0, len(CRITERIA), 2)]
    for pair in tile_rows:
        cols = st.columns(2)
        for col, crit in zip(cols, pair):
            label, value, help_txt = tile_spec[crit]
            score = row[crit]
            eff_w = CRITERIA_WEIGHTS[crit] * base_share
            col.metric(
                label, value,
                delta=(f"score {score:.2f}/5" if pd.notna(score) else None),
                delta_color="off",
                help=help_txt + f" Weight in overall: {eff_w*100:.0f}%.",
            )

    # Fifth component: reliability (from cancellations). Shown alongside the four
    # base criteria so the panel accounts for the whole overall score, not just
    # the 85% base. Its big number is the cancellation rate; the delta is the 1–5
    # reliability score that feeds the overall at CANCEL_WEIGHT.
    rel_score = row.get("cancel_score")
    rel_value = f"{crate*100:.0f}% cancelled" if pd.notna(crate) else "—"
    st.metric(
        "Reliability", rel_value,
        delta=(f"score {rel_score:.2f}/5" if pd.notna(rel_score) else None),
        delta_color="off",
        help="Reliability score from cancellations (cancelled ÷ delivered+cancelled), "
             "penalised exponentially. 0% cancelled → 5.0. "
             f"Weight in overall: {CANCEL_WEIGHT*100:.0f}%.",
    )

    if row.get("missing_delivery_data", False):
        st.caption("ℹ No delivered orders yet — there is no delivery history to "
                   "measure, so delivery time is **excluded** from the overall "
                   "score. The remaining criteria are re-weighted to fill the gap.")

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
    if pd.notna(weakest["Score"]) and weakest["Score"] < 3.5:
        recs.append(f"Weakest area is **{weakest['Criterion']}** "
                    f"({weakest['Score']:.2f}). Raise this in the next review.")
    if pd.notna(crate) and crate >= 0.25:
        recs.append(f"High cancellation rate ({crate*100:.0f}%) — investigate why "
                    "orders are being cancelled; it is dragging the score down.")
    if row["low_confidence"]:
        recs.append("Few rated orders — gather more feedback before major decisions.")
    if not recs:
        recs.append("Performing well across the board. Maintain the relationship.")
    for r in recs:
        st.markdown(f"- {r}")

st.divider()

# --------------------------------------------------------------------------- #
# Trend over time — quarterly average overall score, computed the SAME way as
# the scoreboard so the line and the headline score can't drift apart:
#   * base per delivered order: delivery from days, price scaled against the
#     supplier's CATEGORY peers (same anchors as the board), quality/comm from
#     ratings; cancelled/in-transit orders carry no base (delivered-only).
#   * each quarter's base is then blended with that quarter's cancellation
#     reliability (delivered vs cancelled), exactly like build_scoreboard.
# --------------------------------------------------------------------------- #
st.subheader("Performance trend")
sup_all = orders[orders["supplier_id"] == sid].merge(
    ratings[["order_id", "quality", "communication"]], on="order_id", how="left"
).copy()
if sup_all["order_date"].notna().any():
    sup_all = sup_all.dropna(subset=["order_date"]).copy()
    period = sup_all["order_date"].dt.to_period("Q")
    sup_all["period"] = period.dt.start_time
    sup_all["quarter"] = period.apply(lambda p: f"Q{p.quarter} {p.year}")

    # Price anchors = this supplier's category bounds from the scoreboard, so the
    # per-order price score matches the board's per-category scaling. Fall back
    # to the supplier's own spread if the category has no usable range.
    cat_prices = board.loc[board["category_name"] == row["category_name"],
                           "avg_price_eur"].dropna()
    if len(cat_prices) >= 2:
        pcheap, ppricey = cat_prices.min(), cat_prices.max()
    else:
        vals = sup_all.loc[sup_all["status"] == "Delivered", "amount_eur"].dropna()
        pcheap, ppricey = (vals.min(), vals.max()) if len(vals) else (0.0, 0.0)

    # Base is delivered-only: non-delivered orders get NaN criteria and are
    # excluded from that order's base (weights re-normalised) — matching the board.
    delivered_mask = sup_all["status"] == "Delivered"
    sup_all["delivery_time"] = sup_all["delivery_days"].apply(
        lambda d: float("nan") if pd.isna(d) else delivery_days_to_score(d)
    )
    sup_all["price"] = sup_all.apply(
        lambda r: _linear_score(r["amount_eur"], best=pcheap, worst=ppricey)
        if r["status"] == "Delivered" else float("nan"),
        axis=1,
    )
    # Quality/communication only count for delivered orders (others aren't rated).
    for c in ("quality", "communication"):
        sup_all.loc[~delivered_mask, c] = float("nan")
    sup_all["base"] = sup_all.apply(weighted_overall, axis=1)

    # Per quarter: mean base over delivered orders, blended with that quarter's
    # cancellation reliability (delivered vs cancelled in the same quarter).
    def _quarter_overall(g: pd.DataFrame) -> float:
        base = g.loc[g["status"] == "Delivered", "base"].mean()
        n_deliv = int((g["status"] == "Delivered").sum())
        n_canc = int((g["status"] == "Cancelled").sum())
        canc = cancel_reliability_score(n_canc, n_deliv)
        if pd.isna(base) and pd.isna(canc):
            return float("nan")
        if pd.isna(base):
            return canc
        if pd.isna(canc):
            return base
        return (1.0 - CANCEL_WEIGHT) * base + CANCEL_WEIGHT * canc

    trend = (
        sup_all.groupby(["period", "quarter"])
        .apply(_quarter_overall).rename("overall").reset_index()
        .dropna(subset=["overall"]).sort_values("period")
    )
    # A constant column drives the colour legend so the blue line is labelled.
    trend["series"] = "Avg. overall score"
    line = (
        alt.Chart(trend)
        .mark_line(point=True, strokeWidth=3)
        .encode(
            x=alt.X(
                "quarter:N", title="Quarter",
                sort=trend["quarter"].tolist(),
            ),
            y=alt.Y("overall:Q", scale=alt.Scale(domain=[1, 5]), title="Avg. overall"),
            color=alt.Color(
                "series:N", title=None,
                scale=alt.Scale(range=["#4f46e5"]),
                legend=alt.Legend(orient="top"),
            ),
            tooltip=[alt.Tooltip("quarter:N", title="Quarter"),
                     alt.Tooltip("overall:Q", title="Avg. overall", format=".2f")],
        )
        .properties(height=240)
    )
    rule = alt.Chart(pd.DataFrame({"y": [threshold]})).mark_rule(
        color="#ef4444", strokeDash=[5, 4]).encode(y="y:Q")
    st.altair_chart(line + rule, use_container_width=True)
    st.caption("Blue line = average overall score per quarter · dashed red line = underperformer threshold.")
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
        "special_circumstance": "Special",
    })[["Order", "Ordered", "Delivered", "Days", "Amount (€)", "Status",
        "Special", "Quality", "Communication"]]
    st.dataframe(
        ov.sort_values("Ordered"), use_container_width=True, hide_index=True,
        column_config={
            "Amount (€)": st.column_config.NumberColumn(format="€%.0f"),
            "Days": st.column_config.NumberColumn(format="%d d"),
            "Special": st.column_config.CheckboxColumn(
                "Special", help="Special-circumstance order — excluded from the price score."),
        },
    )
    avg_days = sup_orders["delivery_days"].mean()
    days_txt = f" · avg delivery {avg_days:.1f} days" if pd.notna(avg_days) else ""
    st.caption(
        f"{len(sup_orders)} order(s) · total €{sup_orders['amount_eur'].sum():,.0f}"
        f"{days_txt}"
    )
