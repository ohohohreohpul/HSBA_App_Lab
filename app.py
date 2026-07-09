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
import streamlit.components.v1 as components

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

# Custom table: one row per supplier, all criteria + overall score, and a
# "View" button as the last column that jumps to the drill-down below.
# (st.dataframe can't embed a button in place of its selection checkbox, so
# the whole table is built manually to make rows genuinely clickable.)
col_widths = [3, 1.6, 1.8] + [1.1] * len(CRITERIA) + [1, 1, 1]
col_labels = (
    ["Supplier", "Country", "Category"]
    + [CRITERIA_LABELS[c] for c in CRITERIA]
    + ["Overall", "# Orders Rated", ""]
)

st.caption("Click “View” to jump to that supplier's drill-down below.")
with st.container(height=380, border=True):
    header = st.columns(col_widths)
    for col, label in zip(header, col_labels):
        col.markdown(f"**{label}**")

    top_cut = view["overall_score"].max()
    for _, r in view.iterrows():
        cols = st.columns(col_widths)
        cols[0].write(r["supplier_name"])
        cols[1].write(r["country"])
        cols[2].write(r["category_name"])
        for i, c in enumerate(CRITERIA):
            cols[3 + i].write(f"{r[c]:.2f}")
        overall_cell = cols[3 + len(CRITERIA)]
        if highlight_rows and r["overall_score"] < threshold:
            overall_cell.markdown(
                f'<span style="color:#ef4444; font-weight:600;">{r["overall_score"]:.2f}</span>',
                unsafe_allow_html=True,
            )
        elif highlight_rows and r["overall_score"] >= max(4.0, top_cut - 0.01):
            overall_cell.markdown(
                f'<span style="color:#10b981; font-weight:600;">{r["overall_score"]:.2f}</span>',
                unsafe_allow_html=True,
            )
        else:
            overall_cell.write(f"{r['overall_score']:.2f}")
        cols[4 + len(CRITERIA)].write(int(r["num_ratings"]))
        if cols[5 + len(CRITERIA)].button("View →", key=f"jump_{r['supplier_id']}"):
            st.session_state["jump_to_supplier"] = r["supplier_name"]
            st.session_state["scroll_to_drilldown"] = True

# List of flagged suppliers for quick scanning.
if n_under:
    st.error(f"⚠️ {n_under} underperforming supplier(s) below {threshold:.1f}")
    with st.expander("Show more"):
        flagged = (
            view.loc[view["underperformer"], ["supplier_name", "overall_score"]]
            .sort_values("overall_score", ascending=True)
            .reset_index(drop=True)
        )
        for _, r in flagged.iterrows():
            st.write(f"**{r['supplier_name']}** — {r['overall_score']:.2f}")
else:
    st.success("✅ No underperformers under the current threshold.")

st.divider()

# --------------------------------------------------------------------------- #
# Bar chart ranking (required)
# --------------------------------------------------------------------------- #
st.subheader("Ranking by overall score")
sort_col, filter_col = st.columns([3, 1])
with sort_col:
    sort_order = st.radio(
        "Sort order",
        ["Highest first", "Lowest first", "Alphabetical"],
        horizontal=True,
        label_visibility="collapsed",
    )
with filter_col:
    hide_underperformers = st.toggle(
        "Hide below threshold",
        value=False,
        help=f"Exclude suppliers scoring below {threshold:.1f} from this chart.",
    )

# Sort suppliers. st.bar_chart orders categories alphabetically by default, so
# we build the chart with Altair and pin the y-axis order to our sorted list to
# make the sort control actually reorder the bars.
chart_source = view[view["overall_score"] >= threshold] if hide_underperformers else view
if sort_order == "Alphabetical":
    ranked = (
        chart_source[["supplier_name", "overall_score"]]
        .sort_values("supplier_name", ascending=True)
        .reset_index(drop=True)
    )
else:
    ascending = sort_order == "Lowest first"
    ranked = (
        chart_source[["supplier_name", "overall_score"]]
        .sort_values("overall_score", ascending=ascending)
        .reset_index(drop=True)
    )

if ranked.empty:
    st.info("No suppliers meet the current threshold.")
else:
    # For a top-to-bottom visual order, Altair draws the first row at the top,
    # so the list is already in the order the user picked.
    # Every supplier gets a fixed-height row, so the chart's total height
    # grows with the number of suppliers. It's placed inside a Streamlit
    # scrollable container capped to ~10 rows tall, so only the top 10 show
    # right away and the rest are reachable by scrolling within the chart.
    ROW_HEIGHT = 32
    VISIBLE_ROWS = 10
    bars = alt.Chart(ranked).mark_bar(color="#4f46e5", cornerRadiusEnd=4).encode(
        x=alt.X("overall_score:Q", title="Overall score", scale=alt.Scale(domain=[0, 5])),
        y=alt.Y("supplier_name:N", sort=ranked["supplier_name"].tolist(), title="Supplier"),
        tooltip=[
            alt.Tooltip("supplier_name:N", title="Supplier"),
            alt.Tooltip("overall_score:Q", title="Overall score", format=".2f"),
        ],
    )
    # Score labels at the end of each bar.
    labels = alt.Chart(ranked).mark_text(align="left", dx=5, color="#1e293b", fontWeight=600).encode(
        x=alt.X("overall_score:Q"),
        y=alt.Y("supplier_name:N", sort=ranked["supplier_name"].tolist()),
        text=alt.Text("overall_score:Q", format=".2f"),
    )
    rank_chart = (
        (bars + labels)
        .properties(height=max(len(ranked), 1) * ROW_HEIGHT)
        .configure_view(strokeWidth=0)
    )
    chart_box = st.container(height=VISIBLE_ROWS * ROW_HEIGHT + 40, border=True)
    chart_box.altair_chart(rank_chart, use_container_width=True)

st.divider()

# --------------------------------------------------------------------------- #
# Drill-down (required)
# --------------------------------------------------------------------------- #
st.markdown('<div id="drilldown-anchor"></div>', unsafe_allow_html=True)
st.subheader("Supplier drill-down")

search_col, select_col = st.columns(2)
with search_col:
    search_term = st.text_input(
        "Search suppliers", placeholder="Type a supplier name to filter…"
    )
drilldown_options = view["supplier_name"].tolist()
if search_term:
    drilldown_options = [
        name for name in drilldown_options if search_term.lower() in name.lower()
    ]

if not drilldown_options:
    st.warning(f"No suppliers match “{search_term}”.")
    st.stop()

jump_target = st.session_state.pop("jump_to_supplier", None)
default_index = 0
if jump_target in drilldown_options:
    default_index = drilldown_options.index(jump_target)

with select_col:
    selected_supplier = st.selectbox(
        "Choose a supplier to inspect", drilldown_options, index=default_index
    )

if st.session_state.pop("scroll_to_drilldown", False):
    # The nonce makes each render's HTML unique, since browsers can skip
    # re-executing an iframe's script if the content is byte-identical to
    # the previous render (which it would be on every repeat click).
    nonce = st.session_state.get("_scroll_nonce", 0) + 1
    st.session_state["_scroll_nonce"] = nonce
    components.html(
        f"""
        <script>
        // nonce: {nonce}
        function scrollToAnchor(attemptsLeft) {{
            const el = window.parent.document.getElementById("drilldown-anchor");
            if (el) {{
                el.scrollIntoView({{behavior: "smooth", block: "start"}});
            }} else if (attemptsLeft > 0) {{
                setTimeout(() => scrollToAnchor(attemptsLeft - 1), 100);
            }}
        }}
        setTimeout(() => scrollToAnchor(10), 150);
        </script>
        """,
        height=0,
    )

row = view[view["supplier_name"] == selected_supplier].iloc[0]
sup_id = int(row["supplier_id"])

left, right = st.columns([1, 1])

with left:
    st.markdown(f"### {selected_supplier}")
    st.write(f"**Country:** {row['country']}")
    st.write(f"**Category:** {row['category_name']}")
    st.write(f"**Contact:** {row['contact_email']}")
    meets_threshold = row["overall_score"] >= threshold
    score_bg = "#eafaf1" if meets_threshold else "#fdecea"
    score_color = "#10b981" if meets_threshold else "#ef4444"
    # Recompute from the rounded criterion values shown in the card, so the
    # displayed formula adds up exactly to the displayed result.
    formula_result = sum(row[c] for c in CRITERIA) / len(CRITERIA)
    terms = "".join(
        f'<span style="display:inline-flex; flex-direction:column; align-items:center;">'
        f'<span style="color:#000000; font-weight:600;">{row[c]:.2f}</span>'
        f'<span style="color:#000000; font-size:0.75rem;">{CRITERIA_LABELS[c]}</span>'
        f'</span>'
        + ("<span style='color:#000000;'>+</span>" if i < len(CRITERIA) - 1 else "")
        for i, c in enumerate(CRITERIA)
    )
    card_html = (
        f'<div style="background:{score_bg}; border-radius:16px; padding:18px 20px; '
        f'box-shadow:0 1px 2px rgba(16,24,40,0.04);">'
        f'<div style="color:#000000; font-weight:700; font-size:1.1rem;">Overall score</div>'
        f'<div style="color:{score_color}; font-weight:700; font-size:2.25rem; line-height:1.3;">'
        f'{row["overall_score"]:.2f}</div>'
        f'<div style="margin-top:10px; padding-top:10px; border-top:1px solid rgba(0,0,0,0.06); '
        f'display:flex; align-items:flex-start; gap:8px; font-size:1rem; flex-wrap:wrap;">'
        f'<span style="color:#000000;">(</span>{terms}'
        f'<span style="color:#000000;">) / 4 = {formula_result:.2f}</span>'
        f'</div></div>'
    )
    st.markdown(card_html, unsafe_allow_html=True)

with right:
    st.markdown("#### Criterion breakdown")
    st.caption("This supplier's average score per criterion (1–5 scale).")
    breakdown = pd.DataFrame(
        {
            "Criterion": [CRITERIA_LABELS[c] for c in CRITERIA],
            "Score": [row[c] for c in CRITERIA],
        }
    ).set_index("Criterion")
    breakdown_chart = (
        alt.Chart(breakdown.reset_index())
        .mark_bar(color="#4f46e5", cornerRadiusEnd=4)
        .encode(
            x=alt.X("Criterion:N", title=None, sort=None),
            y=alt.Y("Score:Q", title="Score (1–5)", scale=alt.Scale(domain=[0, 5])),
            tooltip=[
                alt.Tooltip("Criterion:N"),
                alt.Tooltip("Score:Q", format=".2f"),
            ],
        )
    )
    st.altair_chart(breakdown_chart, use_container_width=True)

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
