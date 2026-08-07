"""
Admin gate — a *showcase*, not real security.

This deliberately only demonstrates a role-gated back-office UI. It is NOT meant
to protect anything: the code just flips a boolean flag in the session so the
Admin page and its actions become available. Anyone who reads the source can see
the code.

The code defaults to ``0000``. It can be overridden in
``.streamlit/secrets.toml`` (``[admin] code = "…"``) if you want a different
one, but that's a convenience, not a security boundary.
"""

from __future__ import annotations

import streamlit as st

_DEFAULT_CODE = "0000"  # showcase code — intentionally not a secret


def _configured_code() -> str:
    try:
        return str(st.secrets["admin"]["code"])  # optional override
    except Exception:
        return _DEFAULT_CODE


def is_admin() -> bool:
    return bool(st.session_state.get("is_admin", False))


def try_login(code: str) -> bool:
    """Flip the session role flag if the code matches. Showcase only."""
    ok = code.strip() == _configured_code()
    if ok:
        st.session_state["is_admin"] = True
    return ok


def logout() -> None:
    st.session_state["is_admin"] = False
