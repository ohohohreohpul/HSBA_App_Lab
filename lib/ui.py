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

# --------------------------------------------------------------------------- #
# Global stylesheet.
#
# One big CSS string injected once per page (see inject_theme). It sets the
# font, the colour palette (the :root variables every rule references), the
# page background, then styles each recurring surface: KPI tiles, the hero
# banner, risk badges, Streamlit's metric/dataframe/button widgets, the page
# footer, and finally layout tweaks (hide sidebar, grey the Admin nav item).
# Editing a --var here re-themes the whole app at once.
# --------------------------------------------------------------------------- #
_CSS = """
<style>
/* Font + colour tokens ---------------------------------------------------- */
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

/* Base page + text colours ------------------------------------------------ */
.stApp { background: linear-gradient(160deg, #fbfbfe 0%, #f4f5fb 100%); }

.stApp, .stApp p, .stApp span, .stApp label, .stApp li,
[data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"] * { color: var(--ink); }
[data-testid="stCaptionContainer"], .stApp small { color: var(--muted) !important; }
[data-baseweb="select"] *, [data-testid="stSlider"] * { color: var(--ink) !important; }
[data-testid="stDataFrame"] * { color: var(--ink); }

h1, h2, h3, h4 { color: var(--ink) !important; letter-spacing: -0.02em; }
h1 { font-weight: 800 !important; }

/* Page container: a full-height flex column so the footer can sink to the
   bottom of short pages while long pages just scroll normally. */
.main .block-container { padding-top: 2rem; max-width: 1280px;
    min-height: calc(100vh - 3rem); display: flex; flex-direction: column; }
.main .block-container > div { width: 100%; }
/* Push the footer to the very bottom of the page, full width & centered */
.main .block-container > div:has(.app-footer) {
    margin-top: auto; width: 100%; animation: none; }
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
.hero, .hero * { color:#fff !important; }
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
.stButton > button:hover { background:var(--accent); }
.stButton > button:hover, .stButton > button:hover * { color:#fff !important; }
.stButton > button[kind="primary"] { background:var(--accent); }
.stButton > button[kind="primary"], .stButton > button[kind="primary"] * { color:#fff !important; }

hr { margin:1.4rem 0; opacity:.5; }

/* Page footer */
.app-footer { display:block; width:100%; margin:40px auto 0; padding:22px 0 10px;
              border-top:1px solid var(--line); text-align:center !important;
              color:var(--muted); font-size:.85rem; line-height:1.5; }
.app-footer strong { color:var(--accent); font-weight:600; }
/* Ensure Streamlit's markdown wrapper around the footer stretches full width */
[data-testid="stMarkdownContainer"]:has(.app-footer) { width:100%; text-align:center; }

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


# --------------------------------------------------------------------------- #
# Reusable components.
#
# Small helpers each page calls so the look stays identical everywhere: the
# theme injector, KPI tile rows, the coloured risk badge, the breadcrumb, and
# the "how is this score calculated?" popover.
# --------------------------------------------------------------------------- #
def inject_theme() -> None:
    """Inject the global stylesheet. Call once, early, on every page."""
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


def risk_badge_html(level: str, prefix: str = "") -> str:
    """Coloured risk pill. `prefix` (e.g. "Risk:") is prepended for places that
    need the label spelled out rather than just the level word."""
    color = risk_color(level)
    text = f"{prefix} {level}".strip()
    return (
        f'<span class="badge" style="background:{color}1a;color:{color};">'
        f'● {text}</span>'
    )


def confidence_badge_html(low_confidence: bool, num_ratings: int | None = None) -> str:
    """Coloured pill for data confidence: amber "Confidence: Low" when a supplier
    has too few ratings to trust the score, green "Confidence: OK" otherwise."""
    if low_confidence:
        color = "#d97706"  # amber
        text = "Confidence: Low"
        if num_ratings is not None:
            text += f" ({num_ratings} rating{'s' if num_ratings != 1 else ''})"
    else:
        color = "#10b981"  # green
        text = "Confidence: OK"
    return (
        f'<span class="badge" style="background:{color}1a;color:{color};">'
        f'● {text}</span>'
    )


def special_badge_html(num_special: int) -> str:
    """Blue pill flagging that a supplier has stepped in on special-circumstance
    orders (e.g. the only one able to deliver). Their justified high prices are
    excluded from the price score, so this badge explains a low price score."""
    color = "#2563eb"  # blue
    label = f"Special circumstance ×{num_special}" if num_special > 1 else "Special circumstance"
    return (
        f'<span class="badge" style="background:{color}1a;color:{color};">'
        f'★ {label}</span>'
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
