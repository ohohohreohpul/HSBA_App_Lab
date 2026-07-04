"""
Supplier Evaluation Dashboard
=============================

A Streamlit app that lets a procurement team evaluate and compare suppliers.

Run locally or in Codespaces with:
    python3 -m streamlit run app.py

Features
--------
Required
  * Table of all suppliers with their average score per criterion + overall score
  * Overall score derived from individual per-order ratings
  * Underperforming suppliers flagged so they stand out
  * Filter by category; summary numbers (# suppliers, avg score, # underperformers)
  * Bar chart ranking suppliers by overall score
  * Drill-down into a single supplier (criterion breakdown + their orders)

Nice-to-have (bonus)
  * Adjustable underperformer threshold (sidebar slider)
  * Conditional highlighting of weak rows
  * Country filter
"""

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from styles import inject_styles, render_header

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
DATA_DIR = Path(__file__).parent / "data"

# The four rating criteria stored in ratings.csv (1-5 scale).
CRITERIA = ["delivery_time", "quality", "price", "communication"]
CRITERIA_LABELS = {
    "delivery_time": "Delivery Time",
    "quality": "Quality",
    "price": "Price",
    "communication": "Communication",
}

st.set_page_config(
    page_title="Supplier Evaluation Dashboard",
    page_icon="📊",
    layout="wide",
)

# Custom look & feel (fonts, palette, subtle animations). See styles.py.
inject_styles()


# --------------------------------------------------------------------------- #
# Data loading & scoring
# --------------------------------------------------------------------------- #
@st.cache_data
def load_data():
    """Load the four CSV tables. Cached so files are read only once per session."""
    categories = pd.read_csv(DATA_DIR / "categories.csv")
    suppliers = pd.read_csv(DATA_DIR / "suppliers.csv")
    orders = pd.read_csv(DATA_DIR / "orders.csv")
    ratings = pd.read_csv(DATA_DIR / "ratings.csv")
    orders["order_date"] = pd.to_datetime(orders["order_date"])
    return categories, suppliers, orders, ratings


def build_scoreboard(suppliers, categories, ratings):
    """
    Aggregate the per-order ratings into one row per supplier.

    For every supplier we average each criterion across all of its ratings,
    then the overall score is the mean of the four criterion averages.
    """
    # Average each criterion per supplier.
    per_supplier = (
        ratings.groupby("supplier_id")[CRITERIA]
        .mean()
        .reset_index()
    )
    # Overall score = mean of the four criterion averages.
    per_supplier["overall_score"] = per_supplier[CRITERIA].mean(axis=1)
    # How many orders/ratings each supplier has (context for the reviewer).
    per_supplier["num_ratings"] = (
        ratings.groupby("supplier_id").size().reindex(per_supplier["supplier_id"]).values
    )

    # Join supplier + category master data.
    board = suppliers.merge(per_supplier, on="supplier_id", how="left")
    board = board.merge(
        categories[["category_id", "category_name"]], on="category_id", how="left"
    )
    # Round scores for display.
    for col in CRITERIA + ["overall_score"]:
        board[col] = board[col].round(2)
    return board


# --------------------------------------------------------------------------- #
# Load everything
# --------------------------------------------------------------------------- #
categories, suppliers, orders, ratings = load_data()
scoreboard = build_scoreboard(suppliers, categories, ratings)

render_header()
st.caption(
    "Evaluate and compare suppliers across delivery time, quality, price and "
    "communication. Scores are averaged from individual order ratings (1–5 scale)."
)

# --------------------------------------------------------------------------- #
# Sidebar: filters & threshold (includes bonus features)
# --------------------------------------------------------------------------- #
st.sidebar.header("Filters")

# Category filter (required)
category_options = ["All"] + sorted(categories["category_name"].tolist())
selected_category = st.sidebar.selectbox("Category", category_options)

# Country filter (bonus)
country_options = ["All"] + sorted(suppliers["country"].unique().tolist())
selected_country = st.sidebar.selectbox("Country", country_options)

st.sidebar.header("Underperformer threshold")
# Adjustable threshold (bonus)
threshold = st.sidebar.slider(
    "Flag suppliers with an overall score below:",
    min_value=1.0,
    max_value=5.0,
    value=3.0,
    step=0.1,
    help="Suppliers scoring below this value are flagged as underperformers.",
)

highlight_rows = st.sidebar.checkbox(
    "Highlight weak rows in the table", value=True,
    help="Conditional formatting: colour rows red (below threshold) / green (top scorers).",
)

# --------------------------------------------------------------------------- #
# Apply filters
# --------------------------------------------------------------------------- #
view = scoreboard.copy()
if selected_category != "All":
    view = view[view["category_name"] == selected_category]
if selected_country != "All":
    view = view[view["country"] == selected_country]

view = view.sort_values("overall_score", ascending=False).reset_index(drop=True)
view["underperformer"] = view["overall_score"] < threshold

# --------------------------------------------------------------------------- #
# Summary metrics (required)
# --------------------------------------------------------------------------- #
col1, col2, col3, col4 = st.columns(4)
col1.metric("Suppliers", len(view))
avg_score = view["overall_score"].mean() if len(view) else 0.0
col2.metric("Average overall score", f"{avg_score:.2f}")
n_under = int(view["underperformer"].sum())
col3.metric("Underperformers", n_under)
col4.metric("Threshold", f"{threshold:.1f}")

st.divider()

if view.empty:
    st.warning("No suppliers match the current filters.")
    st.stop()

# --------------------------------------------------------------------------- #
# Main table (required + conditional highlighting bonus)
# --------------------------------------------------------------------------- #
st.subheader("Supplier scorecard")

display_cols = (
    ["supplier_name", "country", "category_name"]
    + CRITERIA
    + ["overall_score", "num_ratings"]
)
table = view[display_cols].rename(
    columns={
        "supplier_name": "Supplier",
        "country": "Country",
        "category_name": "Category",
        **CRITERIA_LABELS,
        "overall_score": "Overall",
        "num_ratings": "# Ratings",
    }
)


def style_table(df):
    """Conditional highlighting: red for underperformers, green for strong scorers."""
    top_cut = df["Overall"].max()

    def row_colour(row):
        if row["Overall"] < threshold:
            return ["background-color: #fdecea"] * len(row)  # soft red
        if row["Overall"] >= max(4.0, top_cut - 0.01):
            return ["background-color: #eafaf1"] * len(row)  # soft green
        return [""] * len(row)

    styler = df.style.apply(row_colour, axis=1)
    styler = styler.format({**{v: "{:.2f}" for v in CRITERIA_LABELS.values()},
                            "Overall": "{:.2f}"})
    return styler


if highlight_rows:
    st.dataframe(style_table(table), use_container_width=True, hide_index=True)
    st.caption("🟥 below threshold  ·  🟩 top scorers")
else:
    st.dataframe(table, use_container_width=True, hide_index=True)

# List of flagged suppliers for quick scanning.
if n_under:
    flagged = ", ".join(view.loc[view["underperformer"], "supplier_name"])
    st.error(f"⚠️ {n_under} underperforming supplier(s) below {threshold:.1f}: {flagged}")
else:
    st.success("✅ No underperformers under the current threshold.")

st.divider()

# --------------------------------------------------------------------------- #
# Bar chart ranking (required)
# --------------------------------------------------------------------------- #
st.subheader("Ranking by overall score")
sort_order = st.radio(
    "Sort order",
    ["Highest first", "Lowest first", "Alphabetical"],
    horizontal=True,
    label_visibility="collapsed",
)
# Sort suppliers. st.bar_chart orders categories alphabetically by default, so
# we build the chart with Altair and pin the y-axis order to our sorted list to
# make the sort control actually reorder the bars.
if sort_order == "Alphabetical":
    ranked = (
        view[["supplier_name", "overall_score"]]
        .sort_values("supplier_name", ascending=True)
        .reset_index(drop=True)
    )
else:
    ascending = sort_order == "Lowest first"
    ranked = (
        view[["supplier_name", "overall_score"]]
        .sort_values("overall_score", ascending=ascending)
        .reset_index(drop=True)
    )
# For a top-to-bottom visual order, Altair draws the first row at the top, so
# the list is already in the order the user picked.
rank_chart = (
    alt.Chart(ranked)
    .mark_bar(color="#4f46e5", cornerRadiusEnd=4)
    .encode(
        x=alt.X("overall_score:Q", title="Overall score"),
        y=alt.Y("supplier_name:N", sort=ranked["supplier_name"].tolist(), title="Supplier"),
        tooltip=[
            alt.Tooltip("supplier_name:N", title="Supplier"),
            alt.Tooltip("overall_score:Q", title="Overall score", format=".2f"),
        ],
    )
)
st.altair_chart(rank_chart, use_container_width=True)

st.divider()

# --------------------------------------------------------------------------- #
# Drill-down (required)
# --------------------------------------------------------------------------- #
st.subheader("Supplier drill-down")
selected_supplier = st.selectbox(
    "Choose a supplier to inspect", view["supplier_name"].tolist()
)

row = view[view["supplier_name"] == selected_supplier].iloc[0]
sup_id = int(row["supplier_id"])

left, right = st.columns([1, 1])

with left:
    st.markdown(f"### {selected_supplier}")
    st.write(f"**Country:** {row['country']}")
    st.write(f"**Category:** {row['category_name']}")
    st.write(f"**Contact:** {row['contact_email']}")
    st.metric("Overall score", f"{row['overall_score']:.2f}")
    if row["overall_score"] < threshold:
        st.error("Flagged as an underperformer.")
    else:
        st.success("Meets the performance threshold.")

with right:
    st.markdown("#### Criterion breakdown")
    breakdown = pd.DataFrame(
        {
            "Criterion": [CRITERIA_LABELS[c] for c in CRITERIA],
            "Average score": [row[c] for c in CRITERIA],
        }
    ).set_index("Criterion")
    st.bar_chart(breakdown, y_label="Average score (1–5)")

# Orders for this supplier.
st.markdown("#### Orders")
sup_orders = orders[orders["supplier_id"] == sup_id].copy()
if sup_orders.empty:
    st.info("No orders on record for this supplier.")
else:
    # Attach the per-order ratings so the drill-down shows how each order scored.
    sup_orders = sup_orders.merge(
        ratings[["order_id"] + CRITERIA], on="order_id", how="left"
    )
    sup_orders["order_date"] = sup_orders["order_date"].dt.date
    order_view = sup_orders.rename(
        columns={
            "order_id": "Order ID",
            "order_date": "Date",
            "amount_eur": "Amount (€)",
            "status": "Status",
            **CRITERIA_LABELS,
        }
    )[["Order ID", "Date", "Amount (€)", "Status"] + list(CRITERIA_LABELS.values())]
    st.dataframe(
        order_view.sort_values("Date"),
        use_container_width=True,
        hide_index=True,
        column_config={"Amount (€)": st.column_config.NumberColumn(format="€%.2f")},
    )
    st.caption(
        f"{len(sup_orders)} order(s) · "
        f"total spend €{sup_orders['amount_eur'].sum():,.2f}"
    )
