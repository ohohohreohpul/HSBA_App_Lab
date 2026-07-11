"""Scorecards — the primary working page: filter, search, scan, export."""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from lib.core import (
    CRITERIA,
    CRITERIA_LABELS,
    DEFAULT_THRESHOLD,
    apply_filters,
    build_scoreboard,
    suggest_names,
)
from lib.ui import breadcrumb, kpi_row, risk_badge_html, score_info_popover

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
    "🔍 Search suppliers",
    key="sc_search",
    placeholder="Type a name — typos are fine (e.g. 'shezen micro')",
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
    if pc2.button("✕ Clear", key="clear_pick", use_container_width=True):
        del st.session_state["sc_picked"]
        st.rerun()

# The effective search term: an exact picked name, else the raw typed text.
search = picked if picked else typed

# --------------------------------------------------------------------------- #
# Filters — update results instantly (Streamlit reruns on any change)
# --------------------------------------------------------------------------- #
with st.expander("Filters", expanded=True):
    f1, f2, f3 = st.columns(3)
    with f1:
        countries = st.multiselect("Country", sorted(board["country"].dropna().unique()))
        categories = st.multiselect("Category", sorted(board["category_name"].dropna().unique()))
    with f2:
        risk_levels = st.multiselect("Risk level", ["High", "Medium", "Low"])
        threshold = st.slider("Underperformer threshold", 1.0, 5.0, DEFAULT_THRESHOLD, 0.1)
    with f3:
        score_range = st.slider("Score range", 1.0, 5.0, (1.0, 5.0), 0.1)
        only_missing = st.checkbox("Only missing data")
        only_low_conf = st.checkbox("Only low-confidence (few ratings)")
        only_under = st.checkbox("Only below threshold")

filters = {
    "search": search,
    "countries": countries,
    "categories": categories,
    "risk_levels": risk_levels,
    "score_range": score_range,
    "only_missing": only_missing,
    "only_low_confidence": only_low_conf,
    "only_underperformers": only_under,
    "threshold": threshold,
}
view = apply_filters(board, filters).sort_values("overall_score", ascending=False)

# --------------------------------------------------------------------------- #
# Summary KPIs for the current filtered set
# --------------------------------------------------------------------------- #
n_under = int((view["overall_score"] < threshold).sum())
kpi_row([
    {"label": "In view", "value": len(view), "sub": f"of {len(board)} total"},
    {"label": "Avg. score", "value": f"{view['overall_score'].mean():.2f}" if len(view) else "—"},
    {"label": "Below threshold", "value": n_under, "sub": f"< {threshold:.1f}"},
    {"label": "High risk", "value": int((view['risk_level'] == 'High').sum())},
])

if view.empty:
    st.warning("No suppliers match the current filters. Try clearing some.")
    st.stop()

# --------------------------------------------------------------------------- #
# Column visibility + export controls
# --------------------------------------------------------------------------- #
all_cols = {
    "supplier_name": "Supplier",
    "country": "Country",
    "category_name": "Category",
    **CRITERIA_LABELS,
    "overall_score": "Overall",
    "risk_level": "Risk",
    "num_orders": "Orders",
    "total_spend": "Spend (€)",
    "num_ratings": "Ratings",
}
ctrl1, ctrl2, ctrl3 = st.columns([3, 1, 1])
with ctrl1:
    default_visible = ["supplier_name", "country", "category_name", "overall_score",
                       "risk_level", "num_orders", "total_spend"]
    visible = st.multiselect(
        "Columns", list(all_cols.keys()),
        default=default_visible,
        format_func=lambda c: all_cols[c],
        label_visibility="collapsed",
    )
if not visible:
    visible = default_visible

# Export current (filtered) view.
export_df = view[["supplier_name", "country", "category_name", *CRITERIA,
                  "overall_score", "risk_level", "num_orders", "total_spend",
                  "num_ratings"]].rename(columns=all_cols)
with ctrl2:
    st.download_button(
        "⬇ CSV", export_df.to_csv(index=False).encode(),
        "suppliers.csv", "text/csv", use_container_width=True,
    )
with ctrl3:
    xbuf = io.BytesIO()
    with pd.ExcelWriter(xbuf, engine="openpyxl") as xw:
        export_df.to_excel(xw, index=False, sheet_name="Suppliers")
    st.download_button(
        "⬇ Excel", xbuf.getvalue(), "suppliers.xlsx",
        "application/vnd.openpyxl", use_container_width=True,
    )

# --------------------------------------------------------------------------- #
# Pagination
# --------------------------------------------------------------------------- #
p1, p2, _ = st.columns([1, 1, 4])
with p1:
    page_size = st.selectbox("Rows / page", [10, 25, 50, 100], index=1)
n_pages = max(1, (len(view) + page_size - 1) // page_size)
with p2:
    page = st.number_input("Page", 1, n_pages, 1, step=1)
start = (page - 1) * page_size
page_df = view.iloc[start:start + page_size].copy()

st.caption(
    f"Showing {start + 1}–{min(start + page_size, len(view))} of {len(view)} · "
    "🔴 red = below threshold · low-confidence rows marked ⚠"
)

# --------------------------------------------------------------------------- #
# The scorecard table — sortable, with conditional risk formatting.
# st.dataframe gives native per-column sort + sticky header. We style the
# overall-score column by risk so problem rows are impossible to miss.
# --------------------------------------------------------------------------- #
display = page_df.copy()
display["Supplier"] = display.apply(
    lambda r: f"⚠ {r['supplier_name']}" if r["low_confidence"] else r["supplier_name"], axis=1
)
display = display.rename(columns={
    "country": "Country", "category_name": "Category",
    "overall_score": "Overall", "risk_level": "Risk",
    "num_orders": "Orders", "total_spend": "Spend (€)", "num_ratings": "Ratings",
    **CRITERIA_LABELS,
})
label_to_key = {v: k for k, v in all_cols.items()}
ordered = ["Supplier"] + [all_cols[c] for c in visible if c != "supplier_name"]
ordered = list(dict.fromkeys(ordered))  # de-dupe, keep order
table = display[ordered]


def _risk_style(row):
    styles = [""] * len(row)
    if "Overall" in row.index and row["Overall"] < threshold:
        idx = list(row.index).index("Overall")
        styles[idx] = "background-color:#fdecea;color:#b91c1c;font-weight:700;"
    return styles


styler = table.style.apply(_risk_style, axis=1).format(
    {c: "{:.2f}" for c in ["Overall", *CRITERIA_LABELS.values()] if c in table.columns}
    | ({"Spend (€)": "€{:,.0f}"} if "Spend (€)" in table.columns else {})
)

st.dataframe(styler, use_container_width=True, hide_index=True, height=440)

# Quick jump to drilldown for any supplier in the current page.
st.write("")
jump_c1, jump_c2 = st.columns([3, 1])
with jump_c1:
    pick = st.selectbox("Open a supplier's drilldown", page_df["supplier_name"].tolist())
with jump_c2:
    st.write("")
    if st.button("Open drilldown →", type="primary", use_container_width=True):
        st.session_state["drilldown_supplier"] = pick
        st.switch_page("pages/3_Drilldown.py")

# Flagged list for fast scanning.
if n_under:
    with st.expander(f"⚠️ {n_under} supplier(s) below the {threshold:.1f} threshold"):
        flagged = view.loc[view["overall_score"] < threshold,
                           ["supplier_name", "country", "overall_score", "risk_level"]]
        for _, r in flagged.sort_values("overall_score").iterrows():
            st.markdown(
                f"**{r['supplier_name']}** ({r['country']}) — {r['overall_score']:.2f} "
                + risk_badge_html(r["risk_level"]),
                unsafe_allow_html=True,
            )
