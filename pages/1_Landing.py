"""Landing page — entry point into the platform."""

from __future__ import annotations

import numpy as np
import streamlit as st

from lib.core import DEFAULT_THRESHOLD, build_scoreboard, load_tables
from lib.story import render_hero, render_story_stats

board = build_scoreboard()
orders = load_tables()["orders"]

# --------------------------------------------------------------------------- #
# Figures behind the story
# --------------------------------------------------------------------------- #
n = len(board)
avg = board["overall_score"].mean()
countries = board["country"].nunique()
high_risk = int((board["risk_level"] == "High").sum())
n_below = int((board["overall_score"] < DEFAULT_THRESHOLD).sum())
cancelled = int((orders["status"] == "Cancelled").sum())
in_transit = int((orders["status"] == "In Transit").sum())
total_orders = len(orders)

# Worst supplier (for the high-risk "so what" line) and a score-distribution
# series for the avg-score sparkline — both straight from the data, no invention.
worst = board.loc[board["overall_score"].idxmin()]
dist = np.histogram(board["overall_score"].dropna(), bins=12, range=(1, 5))[0].tolist()

# --------------------------------------------------------------------------- #
# Hero — states the finding, not a slogan
# --------------------------------------------------------------------------- #
if n_below:
    headline = f"{n} suppliers. {n_below} sit below the line."
else:
    headline = f"{n} suppliers. None below the line."
render_hero(
    headline,
    "One scored view of the whole supplier book. Delivery, price, quality, "
    "communication and cancellations roll into a single 1–5 score, so the "
    "suppliers that need a conversation surface on their own.",
    kicker="Supplier Scorecard",
)

c1, c2, _ = st.columns([1.1, 1, 3])
with c1:
    if st.button("Open scorecards", type="primary", use_container_width=True):
        st.switch_page("pages/2_Scorecards.py")
with c2:
    if st.button("View analytics", use_container_width=True):
        st.switch_page("pages/4_Analytics.py")

st.write("")

# --------------------------------------------------------------------------- #
# Story stats — each figure carries its own "so what"
# --------------------------------------------------------------------------- #
above = avg - DEFAULT_THRESHOLD
render_story_stats([
    {"label": "Suppliers", "value": f"{n}", "delta": f"{countries} countries"},
    {"label": "Avg. score", "value": f"{avg:.2f}",
     "delta": f"{above:+.2f} vs the {DEFAULT_THRESHOLD:.1f} review line",
     "dir": "up" if above >= 0 else "down", "spark": dist},
    {"label": "Below the line", "value": f"{n_below}",
     "delta": f"{n_below / n * 100:.0f}% of the book",
     "dir": "down" if n_below else "up"},
    {"label": "High risk", "value": f"{high_risk}",
     "delta": f"worst {worst['supplier_name']} {worst['overall_score']:.2f}",
     "dir": "down" if high_risk else "up"},
    {"label": "Cancelled", "value": f"{cancelled}",
     "delta": f"{cancelled / total_orders * 100:.0f}% of {total_orders} orders"},
])

st.write("")
st.divider()

# --------------------------------------------------------------------------- #
# The workflow — an editorial index, not a row of equal cards
# --------------------------------------------------------------------------- #
st.markdown('<div class="crumb">The workflow</div>', unsafe_allow_html=True)
st.markdown(
    """
    <style>
    .wf-row { border-top: 1px solid var(--line); padding: 18px 0 6px; }
    .wf-num { font-family: var(--font-mono); color: var(--muted); font-size: .78rem; }
    .wf-title { font-family: var(--font-display); font-weight: 600; font-size: 1.25rem;
        margin-left: 12px; }
    .wf-desc { font-family: var(--font-body); color: var(--ink-2); margin-top: 6px;
        max-width: 60ch; line-height: 1.5; }
    </style>
    """,
    unsafe_allow_html=True,
)

steps = [
    ("01", "Scorecards", "Every supplier in one sortable, searchable table. Filter, "
     "fuzzy-search and export. Anything below the line is flagged in place.",
     "pages/2_Scorecards.py", "wf_score"),
    ("02", "Drilldown", "One supplier in full: score components, the trend over time, "
     "the orders behind it, and where it breaches the line.",
     "pages/3_Drilldown.py", "wf_drill"),
    ("03", "Analytics", "The book from above: risk mix, country and category "
     "breakdowns, and how scores are distributed.",
     "pages/4_Analytics.py", "wf_ana"),
]
for num, title, desc, page, key in steps:
    text_col, btn_col = st.columns([8, 2])
    with text_col:
        st.markdown(
            f'<div class="wf-row"><span class="wf-num">{num}</span>'
            f'<span class="wf-title">{title}</span>'
            f'<div class="wf-desc">{desc}</div></div>',
            unsafe_allow_html=True,
        )
    with btn_col:
        st.write("")
        if st.button("Open", key=key, use_container_width=True):
            st.switch_page(page)

# --------------------------------------------------------------------------- #
# Footer
# --------------------------------------------------------------------------- #
st.markdown(
    """
    <div class="app-footer">
        Supplier Scorecard &middot; <strong>Innovation Management M.Sc.</strong><br>
        HSBA Hamburg School of Business Administration
    </div>
    """,
    unsafe_allow_html=True,
)
