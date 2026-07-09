"""
Custom look & feel for the Supplier Evaluation Dashboard.

Keeps all presentation (CSS, fonts, animations) out of app.py. Call
``inject_styles()`` once, right after ``st.set_page_config``.
"""

import streamlit as st

# A single, restrained palette. One accent colour, generous whitespace,
# soft shadows — "simplistic" on purpose. Animations are subtle: content
# fades/slides in, cards lift on hover, metrics count into view.
_CSS = """
<style>
/* ---- Typography ------------------------------------------------------ */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

:root {
    --accent: #4f46e5;          /* indigo */
    --accent-soft: #eef2ff;
    --ink: #1e293b;
}

/* ---- App background: soft, calm gradient ----------------------------- */
.stApp {
    background: linear-gradient(160deg, #fbfbfe 0%, #f4f5fb 100%);
}

/* ---- Force dark text everywhere (prevents white-on-white in dark mode) */
.stApp, .stApp p, .stApp span, .stApp label, .stApp li, .stApp div,
[data-testid="stMarkdownContainer"],
[data-testid="stWidgetLabel"] * {
    color: var(--ink);
}
/* Caption / secondary text: a softer grey, still readable */
[data-testid="stCaptionContainer"], .stApp small { color: #64748b !important; }

/* Selectbox & slider readouts: readable on their white controls */
[data-baseweb="select"] *, [data-testid="stSlider"] * { color: var(--ink) !important; }

/* Dataframe cell + header text */
[data-testid="stDataFrame"] * { color: var(--ink); }

/* ---- Headings -------------------------------------------------------- */
h1, h2, h3, h4 { color: var(--ink) !important; letter-spacing: -0.02em; }

/* Main title: gradient text + gentle entrance */
h1 {
    font-weight: 700 !important;
    background: linear-gradient(90deg, #4f46e5, #7c3aed);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent !important;
    background-clip: text;
    animation: slideDown 0.6s ease both;
}

/* ---- Global entrance animation for main blocks ----------------------- */
.main .block-container > div {
    animation: fadeInUp 0.5s ease both;
}
.main .block-container {
    padding-top: 2.5rem;
    max-width: 1250px;
}

/* ---- Metric cards ---------------------------------------------------- */
[data-testid="stMetric"] {
    background: #ffffff;
    border: 1px solid #eceef5;
    border-radius: 16px;
    padding: 18px 20px;
    box-shadow: 0 1px 2px rgba(16,24,40,0.04);
    transition: transform 0.25s ease, box-shadow 0.25s ease;
    animation: fadeInUp 0.5s ease both;
}
[data-testid="stMetric"]:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 28px rgba(79,70,229,0.12);
}
[data-testid="stMetricValue"] {
    color: var(--accent);
    font-weight: 700;
}
[data-testid="stMetricLabel"] {
    color: #64748b;
    font-weight: 500;
}

/* ---- Dataframes ------------------------------------------------------ */
[data-testid="stDataFrame"] {
    border-radius: 14px;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(16,24,40,0.06);
    animation: fadeInUp 0.5s ease both;
}

/* ---- Sidebar --------------------------------------------------------- */
[data-testid="stSidebar"] {
    background: #ffffff;
    border-right: 1px solid #eceef5;
}
[data-testid="stSidebar"] h2 {
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #94a3b8;
}

/* ---- Inputs: rounded, accent focus ----------------------------------- */
[data-baseweb="select"] > div, .stSlider {
    border-radius: 10px !important;
}

/* ---- Alert boxes: rounded, animated ---------------------------------- */
[data-testid="stAlert"] {
    border-radius: 12px;
    animation: fadeInUp 0.45s ease both;
}

/* ---- Dividers -------------------------------------------------------- */
hr { margin: 1.6rem 0; opacity: 0.5; }

/* ---- Charts fade in -------------------------------------------------- */
[data-testid="stVegaLiteChart"], .stBarChart {
    animation: fadeInUp 0.6s ease both;
}

/* ---- Buttons --------------------------------------------------------- */
.stButton > button {
    border-radius: 10px;
    border: 1px solid var(--accent);
    transition: all 0.2s ease;
}
.stButton > button:hover {
    background: var(--accent);
    color: #fff;
    transform: translateY(-1px);
}

/* ---- Keyframes ------------------------------------------------------- */
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(14px); }
    to   { opacity: 1; transform: translateY(0); }
}
@keyframes slideDown {
    from { opacity: 0; transform: translateY(-12px); }
    to   { opacity: 1; transform: translateY(0); }
}

/* Hide Streamlit's default chrome for a cleaner, app-like feel */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
[data-testid="stHeader"] { background: transparent; }
</style>
"""


# Simple mark shown to the left of the header, styled to match the accent palette.
_HEADER_HTML = """
<div class="app-header">
    <div class="app-logo">📊</div>
    <h1>Supplier Evaluation Dashboard</h1>
</div>
<style>
.app-header {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    gap: 1rem;
    animation: slideDown 0.6s ease both;
}
.app-header h1 { margin: 0; animation: none; }   /* header handles the entrance */
.app-logo {
    height: 56px;
    width: 56px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.7rem;
    border-radius: 14px;
    background: linear-gradient(135deg, var(--accent), #7c3aed);
    box-shadow: 0 4px 14px rgba(79,70,229,0.25);
    transition: transform 0.25s ease;
}
.app-logo:hover { transform: scale(1.06) rotate(-2deg); }
@media (max-width: 640px) { .app-logo { height: 44px; width: 44px; font-size: 1.3rem; } }
</style>
"""


def render_header() -> None:
    """Render the title with the animated logo in the top-right corner."""
    st.markdown(_HEADER_HTML, unsafe_allow_html=True)


def inject_styles() -> None:
    """Inject the custom CSS. Call once after ``st.set_page_config``."""
    st.markdown(_CSS, unsafe_allow_html=True)
