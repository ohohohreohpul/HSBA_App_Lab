"""
Shared UI: theme injection, reusable components (KPI tiles, risk badges,
score-info popover). Keeps every page visually consistent.
"""

from __future__ import annotations

import streamlit as st

from lib.core import (
    CRITERIA,
    CRITERIA_LABELS,
    CRITERIA_WEIGHTS,
    RISK_BANDS,
    explain_formula,
    risk_color,
)

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }

:root {
    --accent: #4f46e5;
    --accent-2: #7c3aed;
    --accent-soft: #eef2ff;
    --ink: #1e293b;
    --muted: #64748b;
    --line: #e9ecf5;
}

.stApp { background: linear-gradient(160deg, #fbfbfe 0%, #f4f5fb 100%); }

.stApp, .stApp p, .stApp span, .stApp label, .stApp li,
[data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"] * { color: var(--ink); }
[data-testid="stCaptionContainer"], .stApp small { color: var(--muted) !important; }
[data-baseweb="select"] *, [data-testid="stSlider"] * { color: var(--ink) !important; }
[data-testid="stDataFrame"] * { color: var(--ink); }

h1, h2, h3, h4 { color: var(--ink) !important; letter-spacing: -0.02em; }
h1 { font-weight: 800 !important; }

.main .block-container { padding-top: 2rem; max-width: 1280px;
    min-height: calc(100vh - 3rem); display: flex; flex-direction: column; }
/* Push the footer to the very bottom of the page */
.main .block-container > div:has(.app-footer) { margin-top: auto; animation: none; }
.main .block-container > div { animation: fadeInUp 0.45s ease both; }

/* KPI tiles */
.kpi-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:14px; margin:8px 0 4px; }
.kpi { background:#fff; border:1px solid var(--line); border-radius:16px; padding:18px 20px;
       box-shadow:0 1px 2px rgba(16,24,40,.04); transition:transform .2s ease, box-shadow .2s ease; }
.kpi:hover { transform:translateY(-3px); box-shadow:0 12px 28px rgba(79,70,229,.12); }
.kpi .k-label { color:var(--muted); font-weight:500; font-size:.82rem; text-transform:uppercase; letter-spacing:.04em; }
.kpi .k-value { color:var(--accent); font-weight:800; font-size:2rem; line-height:1.25; margin-top:2px; }
.kpi .k-sub { color:var(--muted); font-size:.8rem; }

/* Hero */
.hero { background:linear-gradient(135deg,var(--accent),var(--accent-2)); border-radius:22px;
        padding:40px 44px; color:#fff; box-shadow:0 18px 44px rgba(79,70,229,.28); }
.hero h1 { color:#fff !important; margin:0 0 8px; font-size:2.4rem; }
.hero p  { color:rgba(255,255,255,.92) !important; font-size:1.06rem; max-width:640px; margin:0; }

/* Risk badge */
.badge { display:inline-flex; align-items:center; gap:6px; padding:2px 10px; border-radius:999px;
         font-weight:600; font-size:.8rem; }

[data-testid="stMetric"] { background:#fff; border:1px solid var(--line); border-radius:16px;
    padding:16px 18px; box-shadow:0 1px 2px rgba(16,24,40,.04); }
[data-testid="stMetricValue"] { color:var(--accent); font-weight:800; }
[data-testid="stMetricLabel"] { color:var(--muted); font-weight:500; }

[data-testid="stDataFrame"] { border-radius:14px; overflow:hidden; box-shadow:0 1px 3px rgba(16,24,40,.06); }

.stButton > button { border-radius:10px; border:1px solid var(--accent); font-weight:600; transition:all .18s ease; }
.stButton > button:hover { background:var(--accent); color:#fff; transform:translateY(-1px); }
.stButton > button[kind="primary"] { background:var(--accent); color:#fff; }

hr { margin:1.4rem 0; opacity:.5; }

/* Page footer */
.app-footer { margin-top:40px; padding:22px 0 10px; border-top:1px solid var(--line);
              text-align:center; color:var(--muted); font-size:.85rem; line-height:1.5; }
.app-footer strong { color:var(--accent); font-weight:600; }

@keyframes fadeInUp { from{opacity:0;transform:translateY(12px);} to{opacity:1;transform:translateY(0);} }

#MainMenu { visibility:hidden; }
footer { visibility:hidden; }
[data-testid="stHeader"] { background:transparent; }

/* Nav pills spacing (st.navigation top bar already handles this; this is for our breadcrumb) */
.crumb { color:var(--muted); font-size:.85rem; margin-bottom:.2rem; }

/* ---- Remove the left sidebar entirely (top nav is the only navigation) ---- */
[data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] { display: none !important; }

/* ---- Admin: the last item in the top nav, greyed out -------------------- */
/* st.navigation(position="top") renders the page links inside the header.
   The Admin page is always last, so grey the final nav link so it reads as a
   quieter, secondary entry than the main workflow pages. */
[data-testid="stHeader"] a[href*="Admin"],
header a[href*="Admin"] {
    color: #94a3b8 !important;
    opacity: .8;
}
[data-testid="stHeader"] a[href*="Admin"] *,
header a[href*="Admin"] * {
    color: #94a3b8 !important;
    fill: #94a3b8 !important;
}
[data-testid="stHeader"] a[href*="Admin"]:hover,
header a[href*="Admin"]:hover { opacity: 1; }
</style>
"""


def inject_theme() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def kpi_row(items: list[dict]) -> None:
    """Render a responsive row of KPI tiles.
    items: [{"label":..., "value":..., "sub":...(optional)}]"""
    cells = "".join(
        f'<div class="kpi"><div class="k-label">{i["label"]}</div>'
        f'<div class="k-value">{i["value"]}</div>'
        f'<div class="k-sub">{i.get("sub","")}</div></div>'
        for i in items
    )
    st.markdown(f'<div class="kpi-grid">{cells}</div>', unsafe_allow_html=True)


def risk_badge_html(level: str) -> str:
    color = risk_color(level)
    return (
        f'<span class="badge" style="background:{color}1a;color:{color};">'
        f'● {level}</span>'
    )


def breadcrumb(*parts: str) -> None:
    st.markdown('<div class="crumb">' + " › ".join(parts) + "</div>", unsafe_allow_html=True)




def score_info_popover(key: str = "") -> None:
    """The '(i) how is this score calculated?' popover — full transparency."""
    info = explain_formula()
    with st.popover("ⓘ How is this score calculated?", use_container_width=False):
        from lib.core import DELIVERY_FAST_DAYS, DELIVERY_SLOW_DAYS

        st.markdown("#### Overall score formula")
        st.markdown(
            "The overall score is a **weighted average** of four criteria, each "
            "expressed on a 1–5 scale:"
        )
        st.markdown(
            f"- **Delivery Time** — from the *measured* average days between "
            f"order and delivery: ≤{DELIVERY_FAST_DAYS:.0f} days → 5.0, "
            f"≥{DELIVERY_SLOW_DAYS:.0f} days → 1.0 (linear).\n"
            "- **Price** — from the *measured* average order value in €, scaled "
            "across all suppliers (cheapest → 5.0, priciest → 1.0).\n"
            "- **Quality** — average of the supplier's quality ratings (1–5).\n"
            "- **Communication** — average of its communication ratings (1–5)."
        )
        st.latex(
            r"\text{Overall} = "
            + " + ".join(
                rf"{CRITERIA_WEIGHTS[c]:.2f}\cdot\text{{{CRITERIA_LABELS[c]}}}"
                for c in CRITERIA
            )
        )
        st.markdown("**Weighting**")
        for c in CRITERIA:
            st.markdown(f"- {CRITERIA_LABELS[c]}: **{CRITERIA_WEIGHTS[c]*100:.0f}%**")
        st.markdown("**Risk bands**")
        for label, lo, hi, color in RISK_BANDS:
            hi_disp = "5.0" if hi > 5 else f"{hi:.1f}"
            st.markdown(
                f'- {risk_badge_html(label)} &nbsp; score {lo:.1f} – {hi_disp}',
                unsafe_allow_html=True,
            )
        st.caption(
            f"Suppliers with fewer than {info['min_ratings']} rated orders are "
            "marked **low confidence** — the score is shown but should be read "
            "with caution."
        )
