"""Admin — hidden, role-gated database management and integrity checks."""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from lib.admin import is_admin, logout, try_login
from lib.core import (
    load_tables,
    next_id,
    run_data_checks,
    save_table,
)
from lib.ui import breadcrumb

breadcrumb("Home", "Admin")

# --------------------------------------------------------------------------- #
# Login gate — nothing below renders until the session is authenticated.
# --------------------------------------------------------------------------- #
if not is_admin():
    st.title("🔐 Staff access")
    st.caption("Restricted area. Enter the access code to continue.")
    with st.form("admin_login"):
        code = st.text_input("Access code", type="password")
        submitted = st.form_submit_button("Unlock", type="primary")
    if submitted:
        if try_login(code):
            st.query_params.clear()
            st.rerun()
        else:
            st.error("Incorrect access code.")
    st.stop()

# --------------------------------------------------------------------------- #
# Authenticated
# --------------------------------------------------------------------------- #
top_l, top_r = st.columns([4, 1])
with top_l:
    st.title("🔐 Admin — Database Management")
with top_r:
    st.write("")
    if st.button("Log out", use_container_width=True):
        logout()
        st.query_params.clear()
        st.switch_page("pages/1_Landing.py")

tables = load_tables()
tab_manage, tab_checks, tab_bulk = st.tabs(
    ["📝 Manage data", "🩺 Integrity checks", "📦 Bulk import / export"]
)

# =========================================================================== #
# TAB 1 — Manage data (view / edit / add / delete)
# =========================================================================== #
with tab_manage:
    which = st.selectbox("Table", list(tables.keys()), index=1)  # suppliers default
    df = tables[which].copy().reset_index(drop=True)
    editor_key = f"editor_{which}"

    def _autosave(table_name: str, source: pd.DataFrame, key: str) -> None:
        """Apply the data_editor's pending edits to the source frame and write
        the CSV immediately. Runs as the editor's on_change callback, so any
        cell edit / row add / row delete is persisted with no Save button."""
        state = st.session_state.get(key, {})
        result = source.copy()

        # 1. Edited cells: {row_index: {col: new_value}}
        for row_idx, changes in state.get("edited_rows", {}).items():
            for col, val in changes.items():
                result.at[int(row_idx), col] = val

        # 2. Added rows: list of {col: value} dicts
        added = state.get("added_rows", [])
        if added:
            result = pd.concat([result, pd.DataFrame(added)], ignore_index=True)

        # 3. Deleted rows: list of row indices (into the original frame)
        deleted = state.get("deleted_rows", [])
        if deleted:
            result = result.drop(index=[int(i) for i in deleted]).reset_index(drop=True)

        save_table(table_name, result)
        st.session_state["_autosave_msg"] = f"Saved to {table_name}.csv ✓"

    st.caption(
        f"{len(df)} rows · edits save to **{which}.csv** automatically. "
        "Add a row with the ＋ at the bottom; use the checkbox + trash to delete."
    )
    st.data_editor(
        df, use_container_width=True, num_rows="dynamic", key=editor_key,
        hide_index=True,
        on_change=_autosave, args=(which, df, editor_key),
    )
    if st.session_state.pop("_autosave_msg", None):
        st.success(f"Saved to {which}.csv ✓")

    st.divider()
    st.markdown("#### Quick add — supplier")
    with st.form("add_supplier"):
        f1, f2, f3 = st.columns(3)
        name = f1.text_input("Supplier name")
        country = f2.text_input("Country")
        cat = f3.selectbox("Category", tables["categories"]["category_name"])
        email = st.text_input("Contact email")
        if st.form_submit_button("Add supplier", type="primary"):
            sup = tables["suppliers"].copy()
            cat_id = int(tables["categories"].loc[
                tables["categories"]["category_name"] == cat, "category_id"].iloc[0])
            new = {
                "supplier_id": next_id(sup, "supplier_id"),
                "supplier_name": name, "country": country,
                "category_id": cat_id, "contact_email": email or None,
            }
            if not name.strip():
                st.error("Supplier name is required.")
            elif name in sup["supplier_name"].values:
                st.error("A supplier with that name already exists (duplicate).")
            else:
                save_table("suppliers", pd.concat([sup, pd.DataFrame([new])], ignore_index=True))
                st.success(f"Added {name}.")
                st.rerun()

    st.divider()
    st.markdown("#### Delete supplier")
    dcol1, dcol2 = st.columns([3, 1], vertical_alignment="bottom")
    with dcol1:
        to_del = st.selectbox("Select supplier to delete",
                              tables["suppliers"]["supplier_name"])
    with dcol2:
        if st.button("🗑 Delete", use_container_width=True):
            sup = tables["suppliers"]
            save_table("suppliers", sup[sup["supplier_name"] != to_del])
            st.warning(f"Deleted {to_del}. (Its orders/ratings are now orphaned — "
                       "run integrity checks.)")
            st.rerun()

# =========================================================================== #
# TAB 2 — Integrity checks with one-click fixes
# =========================================================================== #
with tab_checks:
    st.caption("Automated scan for missing values, duplicates, broken references "
               "(orders & ratings), out-of-range ratings, invalid amounts/dates, "
               "and unfinished/low-confidence data.")
    if st.button("🔄 Re-run checks", type="primary"):
        st.rerun()

    findings = run_data_checks()
    clean = all(f["severity"] == "ok" for f in findings)
    if clean:
        st.success("✅ All checks passed — no issues found.")

    icon = {"ok": "✅", "info": "🛈", "warning": "⚠️", "error": "⛔"}
    for f in findings:
        with st.container(border=True):
            c1, c2 = st.columns([4, 1])
            c1.markdown(f"{icon[f['severity']]} **{f['title']}** — "
                        f"{f['count']} affected")
            if f["count"]:
                c1.caption(f["detail"])
            # One-click fixes where a safe automatic remedy exists.
            with c2:
                if f["id"] == "orphan_orders" and f["count"]:
                    if st.button("Fix", key="fix_orphans", use_container_width=True):
                        t = load_tables()
                        valid = set(t["suppliers"]["supplier_id"])
                        save_table("orders", t["orders"][t["orders"]["supplier_id"].isin(valid)])
                        st.rerun()
                elif f["id"] == "orphan_ratings" and f["count"]:
                    if st.button("Fix", key="fix_orphan_ratings", use_container_width=True):
                        t = load_tables()
                        valid = set(t["suppliers"]["supplier_id"])
                        save_table("ratings", t["ratings"][t["ratings"]["supplier_id"].isin(valid)])
                        st.rerun()
                elif f["id"] == "ratings_bad_order" and f["count"]:
                    if st.button("Fix", key="fix_ratings_order", use_container_width=True):
                        t = load_tables()
                        valid = set(t["orders"]["order_id"])
                        save_table("ratings", t["ratings"][t["ratings"]["order_id"].isin(valid)])
                        st.rerun()
                elif f["id"] == "bad_ratings" and f["count"]:
                    if st.button("Fix", key="fix_ratings", use_container_width=True):
                        t = load_tables()
                        r = t["ratings"].copy()
                        # Only the criteria actually scored are validated/clipped.
                        for c in ["quality", "communication"]:
                            r[c] = r[c].clip(1, 5)
                        save_table("ratings", r)
                        st.rerun()
                elif f["id"] == "bad_amount" and f["count"]:
                    if st.button("Fix", key="fix_amount", use_container_width=True):
                        t = load_tables()
                        o = t["orders"]
                        save_table("orders", o[o["amount_eur"] > 0])
                        st.rerun()
                elif f["id"] == "duplicate_names" and f["count"]:
                    if st.button("Fix", key="fix_dups", use_container_width=True):
                        t = load_tables()
                        save_table("suppliers",
                                   t["suppliers"].drop_duplicates("supplier_name", keep="first"))
                        st.rerun()

# =========================================================================== #
# TAB 3 — Bulk import / export
# =========================================================================== #
with tab_bulk:
    st.markdown("#### Export")
    ecol = st.columns(4)
    for i, (nm, d) in enumerate(load_tables().items()):
        ecol[i % 4].download_button(
            f"⬇ {nm}.csv", d.to_csv(index=False).encode(),
            f"{nm}.csv", "text/csv", use_container_width=True, key=f"exp_{nm}",
        )
    # Full workbook.
    xbuf = io.BytesIO()
    with pd.ExcelWriter(xbuf, engine="openpyxl") as xw:
        for nm, d in load_tables().items():
            d.to_excel(xw, sheet_name=nm, index=False)
    st.download_button("⬇ Full workbook (.xlsx)", xbuf.getvalue(),
                       "supplier_db.xlsx", key="exp_all")

    st.divider()
    st.markdown("#### Import (replace a table)")
    imp_table = st.selectbox("Target table", list(tables.keys()), key="imp_tbl")
    up = st.file_uploader("Upload replacement CSV", type="csv")
    if up is not None:
        new_df = pd.read_csv(up)
        st.caption("Preview:")
        st.dataframe(new_df.head(), use_container_width=True, hide_index=True)
        expected = set(tables[imp_table].columns)
        got = set(new_df.columns)
        if expected != got:
            st.error(f"Column mismatch. Expected {sorted(expected)}, got {sorted(got)}.")
        elif st.button("⚠️ Replace table", type="primary"):
            save_table(imp_table, new_df)
            st.success(f"Replaced {imp_table} with {len(new_df)} rows.")
            st.rerun()
