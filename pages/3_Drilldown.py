"""Drilldown — the full profile of one supplier."""

from __future__ import annotations

import altair as alt # For the perfromance dashboard chart
import pandas as pd #tables and data maanipulation
import streamlit as st #UI layout, app we are running

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
) # Core logic behing the app and what youre seeing, functions and computed scores, load data, etc.
from lib.ui import (
    breadcrumb,
    confidence_badge_html,
    risk_badge_html,
    score_info_popover,
    special_badge_html,
) # for better looks and feel of the app

board = build_scoreboard()
tables = load_tables()
orders, ratings = tables["orders"], tables["ratings"]
names = board["supplier_name"].tolist()
# loading in data from CSV (static!) and building the scoreboard (computed from the data)
breadcrumb("Home", "Scorecards", "Drilldown") #For top menu (breadcrump) for navigation, showing where you are in the app

# --------------------------------------------------------------------------- #
# Supplier picker (honours a jump from the Scorecards page) + fuzzy search
# --------------------------------------------------------------------------- #
preselect = st.session_state.pop("drilldown_supplier", None) # Pre-select a supplier if coming from any page
sc1, sc2 = st.columns([2, 3]) # Create search column box and supplier select box
with sc1:
    q = st.text_input("Find supplier", placeholder="Type a name (typos ok)") # Search box for supplier name, fuzzy search is allowed
options = names
if q: 
    sugg = suggest_names(q, names, limit=15) # Suggest names based on the search query, limit to 15 results
    options = sugg or names # If no suggestions, show all names
default_idx = options.index(preselect) if preselect in options else 0 # If preselect is in options, set pre-selceted supplier, otherwise set to first option (0)
with sc2:
    supplier = st.selectbox("Supplier", options, index=default_idx) # Gets the drop down for supplier selection - if 0 -> pre selected supplier

row = board[board["supplier_name"] == supplier].iloc[0] # Get the row of the selected supplier from the scoreboard
sid = int(row["supplier_id"]) # Get the supplier ID from the row and store it in sid
threshold = DEFAULT_THRESHOLD # Set to 3.5 as default

# --------------------------------------------------------------------------- #
# Header: name, meta, overall score card
# --------------------------------------------------------------------------- #
st.title(supplier) # Sets the header to the supplier name
meta_l, meta_r = st.columns([3, 2]) # creates the left column for metadata (risk, confidence, specoal) and right column for "How is this score calculated?" popover
with meta_l:
    special_badge = (
        f"{special_badge_html(int(row['num_special_orders']))} &nbsp; "
        if row.get("has_special_orders", False) else ""
    ) # Shows a badge if the supplier has special orders, otherwise shows nothing
    st.markdown(
        f"{risk_badge_html(row['risk_level'], prefix='Risk:')} &nbsp; "
        f"{confidence_badge_html(bool(row['low_confidence']), int(row['num_ratings']))} &nbsp; "
        f"{special_badge}"
        f"**{row['country']}** · {row['category_name']} · "
        f"{row['contact_email']}",
        unsafe_allow_html=True,
    ) # Shows the risk-, confidence- and special-badges, country, category and contact email of the supplier
    if row["low_confidence"]:
        st.warning(
            f"**Low confidence** — this score is based on only "
            f"{int(row['num_ratings'])} rated order(s), so treat it with caution."
        ) # Warning for low confidence if supplier has lass than 5 rated orders
    if row.get("has_special_orders", False):
        st.info(
            f"**Special circumstance** — this supplier stepped in on "
            f"{int(row['num_special_orders'])} order(s) where a high price was "
            "justified (e.g. the only supplier able to deliver). Those orders are "
            "**excluded from the price score**, so a low price score here doesn't "
            "mean they're simply expensive — they're a reliable fallback when no "
            "one else can deliver."
        ) # Spedcial order information
with meta_r:
    score_info_popover("drill") # Pre-stored information on how the score is calculated.

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
mc5.metric("Last order", last.date().isoformat() if pd.notna(last) else "—") # Creates the 5 boxes and loads in information + ?-mark-boxes for the supplier: Overall score, Orders, Total spend, Cancelled and Last order. 

# Flag a poor cancellation record explicitly if below 25% or above.
if pd.notna(crate) and crate >= 0.25:
    st.warning(
        f"**High cancellation rate** — {n_canc} of "
        f"{n_canc + int(row['num_delivered'])} resolved orders were cancelled "
        f"({crate*100:.0f}%). This lowers the overall score via the reliability "
        f"component (reliability score {row['cancel_score']:.2f}/5)."
    )

st.divider()

# --------------------------------------------------------------------------- #
# Score components — with the exact weighted contribution of each criterion
# --------------------------------------------------------------------------- #
left, right = st.columns([1, 1]) # Splitting the criterion averages and threshold violations/recommendations into two columns
with left:
    st.subheader("Criterion averages")
    comp = pd.DataFrame({
        "Criterion": [CRITERIA_LABELS[c] for c in CRITERIA] + ["Reliability"], # turns internal categories into labels shown on website (Delivery Time, Quality, Price, Communication, Reliability)
        "Score": [row[c] for c in CRITERIA] + [row.get("cancel_score")], # adding actual scores to each criterion.
        "Weight": [w * (1.0 - CANCEL_WEIGHT) for w in CRITERIA_WEIGHTS.values()] # defines the weight of each criterion in the overall score with reliablity getting 15% ( Canel weight and the main critiria 85
                  + [CANCEL_WEIGHT],
    })
    comp["Contribution"] = (comp["Score"] * comp["Weight"]).round(3) # calculates the contribution of each criterion to the overall score by multiplying the score by its weight and rounding to 3 decimal places

    def _avg_days(r):
        v = r["avg_delivery_days"]
        return "—" if pd.isna(v) else f"{v:.1f} days" # formats average delivery days (dash if missing)

    def _avg_eur(r):
        v = r["avg_price_eur"]
        return "—" if pd.isna(v) else f"€{v:,.0f}" # formats average price in euros (dash if missing)

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
    } # defines the labels, values and help text for each criterion tile (Delivery Time, Quality, Price, Communication)

    # The four base criteria share 85% of the overall (the base), split by their
    # own weights; reliability is the remaining 15%. So a criterion's *effective*
    # weight in the overall is (1 - CANCEL_WEIGHT) × its base weight — that's what
    # we show, so the five tiles' weights sum to 100% and reconcile to "Overall".
    base_share = 1.0 - CANCEL_WEIGHT

    # 2×2 tiles: big number = the real average; the delta shows the 1–5 score
    # that average maps to (so you see both the measurement and its score).
    tile_rows = [CRITERIA[i:i + 2] for i in range(0, len(CRITERIA), 2)] # splits the criteria into pairs for display in two columns
    for pair in tile_rows: # iterates over the pairs of criteria to display them in two columns
        cols = st.columns(2)
        for col, crit in zip(cols, pair): # iterates over the criteria in the pair and displays them in the corresponding column
            label, value, help_txt = tile_spec[crit]
            score = row[crit]
            eff_w = CRITERIA_WEIGHTS[crit] * base_share
            col.metric(
                label, value,
                delta=(f"score {score:.2f}/5" if pd.notna(score) else None),
                delta_color="off",
                help=help_txt + f" Weight in overall: {eff_w*100:.0f}%.",
            ) # displays the metric for each criterion with its label, value, score, and weight in the overall score. The delta shows the score (1-5) that the average maps to, and the help text provides additional information about the criterion and its weight in the overall score.

    rel_score = row.get("cancel_score")
    rel_value = f"{crate*100:.0f}% cancelled" if pd.notna(crate) else "—"
    st.metric(
        "Reliability", rel_value,
        delta=(f"score {rel_score:.2f}/5" if pd.notna(rel_score) else None),
        delta_color="off",
        help="Reliability score from cancellations (cancelled ÷ delivered+cancelled), "
             "penalised exponentially. 0% cancelled → 5.0. "
             f"Weight in overall: {CANCEL_WEIGHT*100:.0f}%.",
    ) # Shows the reliability metric with its value (canceled order in %) and score + explaining in Helper box

    if row.get("missing_delivery_data", False):
        st.caption("No delivered orders yet — there is no delivery history to "
                   "measure, so delivery time is **excluded** from the overall "
                   "score. The remaining criteria are re-weighted to fill the gap.")
# Explains when no orders are taken that the delivery time is excluded from the overall score and the remaining criteria are re-weighted to fill the gap.
with right:
    st.subheader("Threshold violations")
    violations = comp[comp["Score"] < threshold]
    if violations.empty:
        st.success(f"No criterion below the {threshold:.1f} threshold.")
    else:
        for r in violations.itertuples():
            st.error(f"**{r.Criterion}**: {r.Score:.2f} (below {threshold:.1f})")
# Shopws criteria below scoring threshold or success text if all criteria are above the threshold. The threshold is set to 3.5 by default.
    # Recommendations derived from the weakest criteria, pre-defined text recommendations in code. Output written in markwodn bullets.
    st.subheader("Recommendations")
    weakest = comp.sort_values("Score").iloc[0]
    recs = []
    if row["overall_score"] < threshold:
        recs.append("Overall score is below threshold - consider a formal review "
                    "or corrective-action plan.")
    if pd.notna(weakest["Score"]) and weakest["Score"] < 3.5:
        recs.append(f"Weakest area is **{weakest['Criterion']}** "
                    f"({weakest['Score']:.2f}). Raise this in the next review.")
    if pd.notna(crate) and crate >= 0.25:
        recs.append(f"High cancellation rate ({crate*100:.0f}%) - investigate why "
                    "orders are being cancelled; it is dragging the score down.")
    if row["low_confidence"]:
        recs.append("Few rated orders - gather more feedback before major decisions.")
    if not recs:
        recs.append("Performing well across the board. Maintain the relationship.")
    for r in recs:
        st.markdown(f"- {r}")

st.divider()

# --------------------------------------------------------------------------- #
# Trend over time - quarterly average overall score, computed the SAME way as
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
).copy() # Filters for supplier and merges ratings inside sup_all
if sup_all["order_date"].notna().any():
    sup_all = sup_all.dropna(subset=["order_date"]).copy()
    period = sup_all["order_date"].dt.to_period("Q")
    sup_all["period"] = period.dt.start_time
    sup_all["quarter"] = period.apply(lambda p: f"Q{p.quarter} {p.year}") # checks orders for dates and drops any without a date, then creates a new column for the period (quarter) and quarter label (Q1 2024, Q2 2024, etc.)

    # Price anchors:
    cat_prices = board[board["category_name"] == row["category_name"]]["avg_price_eur"].dropna() # finds the price range from scoreboard for the supplier's category peers, dropping any missing values
    if len(cat_prices) >= 2:
        pcheap, ppricey = cat_prices.min(), cat_prices.max()
    else:
        vals = sup_all[sup_all["status"] == "Delivered"]["amount_eur"].dropna()
        pcheap, ppricey = (vals.min(), vals.max()) if len(vals) else (0.0, 0.0) # If there are not enough category peers, use the supplier's own delivered orders to set the price range

    # Compute pre-order scores:
    delivered_mask = sup_all["status"] == "Delivered" # Creates a mask for delivered orders with all devliered orders
    sup_all["delivery_time"] = sup_all["delivery_days"].apply(
        lambda d: float("nan") if pd.isna(d) else delivery_days_to_score(d)
    ) # converting delivery days to a score 
    sup_all["price"] = sup_all.apply(
        lambda r: _linear_score(r["amount_eur"], best=pcheap, worst=ppricey)
        if r["status"] == "Delivered" else float("nan"),
        axis=1,
    ) # converting amout to price score for only devliered orders
    # Quality/communication only count for delivered orders (others aren't rated).
    for c in ("quality", "communication"):
        sup_all.loc[~delivered_mask, c] = float("nan")
    sup_all["base"] = sup_all.apply(weighted_overall, axis=1)

    # Per quarter cpomputing:
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
# defines how to compute the overall score for a quarter by averaging the base scores of delivered orders and blending it with the cancellation reliability score, weighted by CANCEL_WEIGHT.
    # Build trend chart:   
    trend = (
        sup_all.groupby(["period", "quarter"])
        .apply(_quarter_overall).rename("overall").reset_index()
        .dropna(subset=["overall"]).sort_values("period")
    ) # Group by quarter to compute average overall score / quarter.

    trend["series"] = "Avg. overall score" # Create a line line chart with: 
    line = (
        alt.Chart(trend)
        .mark_line(point=True, strokeWidth=3)
        .encode(
            x=alt.X(
                "quarter:N", title="Quarter",
                sort=trend["quarter"].tolist(),
            ), # Quarter on the x-axis
            y=alt.Y("overall:Q", scale=alt.Scale(domain=[1, 5]), title="Avg. overall"),
            color=alt.Color(
                "series:N", title=None,
                scale=alt.Scale(range=["#1a1a1a"]),
                legend=alt.Legend(orient="top"),
            ), # Average overall score on the y-axis, with a scale from 1 to 5
            tooltip=[alt.Tooltip("quarter:N", title="Quarter"),
                     alt.Tooltip("overall:Q", title="Avg. overall", format=".2f")],
        ) # constant legend table
        .properties(height=240)
    )
    # Add a dashed red line for the threshold:
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
if sup_orders.empty: # Filters for all orders of the supplier and shows a message if there are no orders on record.
    st.info("No orders on record.")
else:
    # Show the measured delivery (date + days) per order, plus the quality & communication ratings for that order.
    rating_cols = ["quality", "communication"]
    sup_orders = sup_orders.merge(
        ratings[["order_id", *rating_cols]], on="order_id", how="left"
    ) # Merges quality and communication ratings into the orders table for the supplier
    sup_orders["order_date"] = sup_orders["order_date"].dt.date
    sup_orders["delivery_date"] = pd.to_datetime(sup_orders["delivery_date"]).dt.date # Converts order and delivery dates to date format
    ov = sup_orders.rename(columns={
        "order_id": "Order", "order_date": "Ordered", "delivery_date": "Delivered",
        "delivery_days": "Days", "amount_eur": "Amount (€)", "status": "Status",
        "quality": "Quality", "communication": "Communication",
        "special_circumstance": "Special",
    })[["Order", "Ordered", "Delivered", "Days", "Amount (€)", "Status",
        "Special", "Quality", "Communication"]] # Rearranges and renames columns for display in the orders table
    st.dataframe(
        ov.sort_values("Ordered"), use_container_width=True, hide_index=True,
        column_config={
            "Amount (€)": st.column_config.NumberColumn(format="€%.0f"),
            "Days": st.column_config.NumberColumn(format="%d d"),
            "Special": st.column_config.CheckboxColumn(
                "Special", help="Special-circumstance order — excluded from the price score."),
        },
    ) #   Displaying the data frame (orders) in an interactive table sorted by order date and formatted for readability with flags for special-circumstance orders.
# Computing average and displaying a caoption that summarizes the order:
    avg_days = sup_orders["delivery_days"].mean()
    days_txt = f" · avg delivery {avg_days:.1f} days" if pd.notna(avg_days) else ""
    st.caption(
        f"{len(sup_orders)} order(s) · total €{sup_orders['amount_eur'].sum():,.0f}"
        f"{days_txt}"
    )
