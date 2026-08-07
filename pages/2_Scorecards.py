"""Scorecards — the primary working page: filter, search, scan."""

from __future__ import annotations

import streamlit as st

from lib.core import (
    CRITERIA,
    CRITERIA_LABELS,
    DEFAULT_THRESHOLD,
    MIN_RATINGS_FOR_CONFIDENCE,
    apply_filters,
    build_scoreboard,
    suggest_names,
)
from lib.ui import breadcrumb, risk_badge_html, score_info_popover

board = build_scoreboard()
names = board["supplier_name"].tolist()

breadcrumb("Home", "Scorecards")
h_left, h_right = st.columns([4, 1])
with h_left:
    st.title("Supplier Scorecards")
with h_right:
    st.write("")
    score_info_popover("scorecards")

# --------------------------------------------------------------------------- #
# Fuzzy search with a live "recommended companies" dropdown you can pick from.
#
# Streamlit has no native type-ahead-with-dropdown widget, so we build one: as
# you type, matching companies appear as clickable suggestions. Clicking one
# selects it (locks the table to that supplier). The raw typed text still
# fuzzy-filters the table, so you can also just type without picking.
# --------------------------------------------------------------------------- #
typed = st.text_input(
    "Search suppliers",
    key="sc_search",
    placeholder="Type a name, typos are fine (e.g. 'shezen micro')",
)

# A picked suggestion takes precedence over the raw typed text.
picked = st.session_state.get("sc_picked")

if typed:
    matches = suggest_names(typed, names, limit=8)
    if matches:
        st.caption("Recommended — click to select:")
        # Lay the suggestions out as a row of clickable pills.
        cols = st.columns(min(len(matches), 4))
        for i, name in enumerate(matches):
            if cols[i % len(cols)].button(name, key=f"sugg_{i}", use_container_width=True):
                st.session_state["sc_picked"] = name
                st.rerun()
    else:
        st.caption("No matching suppliers.")

# Show + allow clearing the current selection.
if picked:
    pc1, pc2 = st.columns([4, 1])
    pc1.markdown(f"Selected: **{picked}**")
    if pc2.button("Clear", key="clear_pick", use_container_width=True):
        del st.session_state["sc_picked"]
        st.rerun()

# The effective search term: an exact picked name, else the raw typed text.
search = picked if picked else typed

# --------------------------------------------------------------------------- #
# Filters — update results instantly (Streamlit reruns on any change)
# --------------------------------------------------------------------------- #
with st.expander("Filters", expanded=True):
    # Row 1 — attribute filters (what to include)
    st.markdown("**Attributes**")
    a1, a2, a3 = st.columns(3)
    countries = a1.multiselect("Country", sorted(board["country"].dropna().unique()))
    categories = a2.multiselect("Category", sorted(board["category_name"].dropna().unique()))
    risk_levels = a3.multiselect("Risk level", ["High", "Medium", "Low"])

    # Total-spend range (€). Bounds come from the data so the slider always spans
    # the real min..max; default selection is the full range (no filtering).
    spend_lo = int(board["total_spend"].min())
    spend_hi = int(board["total_spend"].max()) + 1
    spend_range = st.slider(
        "Total spend (€)", spend_lo, spend_hi, (spend_lo, spend_hi), step=1000,
        format="€%d",
    )

    # Row 2 — score-based filters (ranges)
    st.markdown("**Score**")
    s1, s2 = st.columns(2)
    score_range = s1.slider("Score range", 1.0, 5.0, (1.0, 5.0), 0.1)
    threshold = s2.slider("Underperformer threshold", 1.0, 5.0, DEFAULT_THRESHOLD, 0.1)

    # Row 3 — quick toggles (data quality / shortcuts), paired opposites.
    st.markdown("**Quick filters**")
    q1, q2 = st.columns(2)
    only_under = q1.checkbox("Only below threshold")
    only_above = q2.checkbox("Only above threshold")
    q3, q4 = st.columns(2)
    only_low_conf = q3.checkbox("Only low-confidence (few ratings)")
    only_high_conf = q4.checkbox("Only high-confidence (enough ratings)")

filters = {
    # A picked suggestion is an exact name, so don't fuzzy-match it; the exact
    # filter below handles it. Only pass the raw typed text to fuzzy search.
    "search": "" if picked else typed,
    "countries": countries,
    "categories": categories,
    "risk_levels": risk_levels,
    "score_range": score_range,
    "spend_range": spend_range,
    "only_low_confidence": only_low_conf,
    "only_high_confidence": only_high_conf,
    "only_underperformers": only_under,
    "only_above_threshold": only_above,
    "threshold": threshold,
}
view = apply_filters(board, filters)
if picked:
    # Selected a specific company → show exactly that supplier.
    view = view[view["supplier_name"] == picked]
view = view.sort_values("overall_score", ascending=False)

# Count below-threshold suppliers (used by the flagged-list expander below).
n_under = int((view["overall_score"] < threshold).sum())

if view.empty:
    st.warning("No suppliers match the current filters. Try clearing some.")
    st.stop()

# --------------------------------------------------------------------------- #
# Table columns
# --------------------------------------------------------------------------- #
all_cols = {
    "supplier_name": "Supplier",
    "country": "Country",
    "category_name": "Category",
    **CRITERIA_LABELS,
    "overall_score": "Overall",
    "risk_level": "Risk",
    "confidence": "Confidence",
    "num_orders": "Orders",
    "total_spend": "Total spend (€)",
    "num_ratings": "Ratings",
}
visible = ["supplier_name", "country", "category_name", "overall_score",
           "risk_level", "confidence", "num_orders", "total_spend"]

st.caption("Red cell = below threshold. Confidence \"Low\" means fewer than "
           f"{MIN_RATINGS_FOR_CONFIDENCE} rated orders, so the score is less reliable.")

# --------------------------------------------------------------------------- #
# The scorecard table — all suppliers in the filtered view, sortable, with
# conditional risk formatting. st.dataframe gives native per-column sort + a
# sticky header, and scrolls internally within its fixed height, so every row
# is reachable without paging.
# --------------------------------------------------------------------------- #
display = view.copy()
display["Supplier"] = display["supplier_name"]
# Dedicated confidence column: "Low" when there are too few ratings to trust the
# score, "OK" otherwise (coloured by _risk_style below).
display["Confidence"] = display["low_confidence"].map({True: "Low", False: "OK"})
# First column: a per-row action button ("Open ▶") that opens the drilldown.
display["Select for drilldown"] = ":material/arrow_forward: Open"
display = display.rename(columns={
    "country": "Country", "category_name": "Category",
    "overall_score": "Overall", "risk_level": "Risk",
    "num_orders": "Orders", "total_spend": "Total spend (€)", "num_ratings": "Ratings",
    **CRITERIA_LABELS,
})
ordered = ["Select for drilldown", "Supplier"] + [all_cols[c] for c in visible if c != "supplier_name"]
ordered = list(dict.fromkeys(ordered))  # de-dupe, keep order
# Defensive: only keep columns that were actually built (e.g. "Confidence" is a
# derived column, not a raw board field) so a rename/schema change can't KeyError.
ordered = [c for c in ordered if c in display.columns]
table = display[ordered].reset_index(drop=True)

# The ButtonColumn click reports the row's position in the dataframe *as passed*
# to st.dataframe (not the user's client-side sort), so resolve the clicked row
# against this exact frame's Supplier column — which stays correct no matter how
# the user re-sorts the table visually.
row_supplier = table["Supplier"].tolist()
st.session_state["_scorecard_row_supplier"] = row_supplier


def _risk_style(row):
    styles = [""] * len(row)
    if "Overall" in row.index and row["Overall"] < threshold:
        idx = list(row.index).index("Overall")
        styles[idx] = "background-color:#fdecea;color:#b91c1c;font-weight:700;"
    if "Confidence" in row.index and row["Confidence"] == "Low":
        idx = list(row.index).index("Confidence")
        styles[idx] = "background-color:#fef3c7;color:#92400e;font-weight:700;"
    return styles


styler = table.style.apply(_risk_style, axis=1).format(
    {c: "{:.2f}" for c in ["Overall", *CRITERIA_LABELS.values()] if c in table.columns}
    | ({"Total spend (€)": "€{:,.0f}"} if "Total spend (€)" in table.columns else {})
)


def _open_drilldown() -> None:
    """ButtonColumn callback: map the clicked row to a supplier and navigate.
    We resolve the supplier from the table's own Supplier column (captured at
    render as `_scorecard_row_supplier`) rather than from `view`, so a click
    still opens the right supplier even after the user re-sorts the table."""
    click = st.session_state.get("drill_click")
    row_supplier = st.session_state.get("_scorecard_row_supplier", [])
    if click is not None:
        pos = click["row"]
        if 0 <= pos < len(row_supplier):
            st.session_state["drilldown_supplier"] = row_supplier[pos]
            st.session_state["_go_drilldown"] = True


st.dataframe(
    styler, use_container_width=True, hide_index=True, height=440,
    key="scorecard_table",
    column_config={
        "Select for drilldown": st.column_config.ButtonColumn(
            "Select for drilldown",
            help="Open this supplier's drilldown",
            on_click=_open_drilldown,
            key="drill_click",
        ),
    },
)

# The callback can't call st.switch_page (it runs before the rerun completes),
# so it sets a flag and we navigate here on the resulting rerun.
if st.session_state.pop("_go_drilldown", False):
    st.switch_page("pages/3_Drilldown.py")

# Flagged list for fast scanning.
if n_under:
    with st.expander(f"{n_under} supplier(s) below the {threshold:.1f} threshold"):
        flagged = view.loc[view["overall_score"] < threshold,
                           ["supplier_name", "country", "overall_score", "risk_level"]]
        for _, r in flagged.sort_values("overall_score").iterrows():
            st.markdown(
                f"**{r['supplier_name']}** ({r['country']}) — {r['overall_score']:.2f} "
                + risk_badge_html(r["risk_level"]),
                unsafe_allow_html=True,
            )
