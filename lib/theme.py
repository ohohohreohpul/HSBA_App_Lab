"""
Global stylesheet for the Supplier Scorecard — the single source of truth for
look & feel.

Design language: **editorial / Swiss**. Ink on paper. Flat. No gradients, no
decorative colour, no boxed "dashboard" cards. Structure comes from a strong
typographic scale, generous whitespace, and hairline rules — the way a
well-set report reads. The *only* colour that carries meaning is the risk
palette (red / amber / green), used semantically and nowhere else.

Type: a grotesk display (Space Grotesk) against a neutral body (Inter), with a
monospace (IBM Plex Mono) reserved for figures and small labels — tabular
numerals give the data an instrument-panel precision. Motion is restrained and
transform-only, and collapses under `prefers-reduced-motion`.

Editing a `--var` in `:root` re-themes the whole app at once.
"""

APP_CSS = """
/* Type ------------------------------------------------------------------- */
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

:root {
    /* Ink-on-paper neutrals. No brand colour — colour is reserved for risk. */
    --paper: #f5f4f1;
    --surface: #ffffff;
    --ink: #1a1a1a;          /* near-black, never #000 */
    --ink-2: #3d3d3a;
    --muted: #6f6d66;
    --line: #dedcd5;         /* hairline */
    --rule: #1a1a1a;         /* strong editorial rule */

    /* Semantic risk palette (the only meaningful colour). */
    --risk-high: #c0392b;
    --risk-med: #b07400;
    --risk-low: #2f7d55;

    /* Type families */
    --font-display: 'Space Grotesk', 'Inter', sans-serif;
    --font-body: 'Inter', -apple-system, sans-serif;
    --font-mono: 'IBM Plex Mono', ui-monospace, monospace;

    /* Motion (restrained) */
    --ease-out: cubic-bezier(.165, .84, .44, 1);
    --dur-1: 120ms;
    --dur-2: 220ms;
}

/* Base ------------------------------------------------------------------- */
html, body, [class*="css"] { font-family: var(--font-body); }
.stApp { background: var(--paper); }

.stApp, .stApp p, .stApp span, .stApp label, .stApp li,
[data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"] * { color: var(--ink); }
[data-testid="stCaptionContainer"], .stApp small { color: var(--muted) !important; }
[data-baseweb="select"] *, [data-testid="stSlider"] * { color: var(--ink) !important; }
[data-testid="stDataFrame"] * { color: var(--ink); }

/* Headings: display grotesk, tight, big scale contrast (editorial) -------- */
h1, h2, h3, h4 { font-family: var(--font-display); color: var(--ink) !important;
    letter-spacing: -0.02em; font-weight: 600; }
h1 { font-weight: 700 !important; font-size: clamp(2rem, 1.4rem + 2.6vw, 3.4rem);
     line-height: 1.02; letter-spacing: -0.035em; }
h2 { font-size: 1.5rem; margin-top: .4rem; }
h3 { font-size: 1.15rem; }

/* Tabular monospace numerals everywhere numbers matter (Swiss data feel) -- */
[data-testid="stMetricValue"], .kpi .k-value, .stat-value, .stat-delta,
[data-testid="stDataFrame"] { font-variant-numeric: tabular-nums; }

/* Page container --------------------------------------------------------- */
.main .block-container { padding-top: 2.2rem; max-width: 1200px;
    min-height: calc(100vh - 3rem); display: flex; flex-direction: column; }
.main .block-container > div { width: 100%; }
.main .block-container > div:has(.app-footer) { margin-top: auto; width: 100%; animation: none; }

/* -------------------------------------------------------------------------
   Story stats — the replacement for boxed KPI cards. No box: a hairline top
   rule, a small mono label, a big mono figure, and a comparison line that
   states the "so what". Grouped by negative space and dividers, not cards.
   ------------------------------------------------------------------------- */
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 0; margin: 4px 0; border-top: 1px solid var(--rule); }
.stat { padding: 16px 22px 18px 0; border-right: 1px solid var(--line); }
.stat:last-child { border-right: none; }
.stat .s-label { font-family: var(--font-mono); font-size: .72rem; font-weight: 500;
    text-transform: uppercase; letter-spacing: .08em; color: var(--muted); }
.stat .s-value { font-family: var(--font-mono); font-weight: 600;
    font-size: clamp(1.8rem, 1.3rem + 1.6vw, 2.6rem); line-height: 1.1; color: var(--ink);
    margin-top: 6px; font-variant-numeric: tabular-nums; }
.stat .s-delta { font-family: var(--font-mono); font-size: .78rem; color: var(--muted);
    margin-top: 4px; }
.stat .s-delta.up { color: var(--risk-low); }
.stat .s-delta.down { color: var(--risk-high); }
.stat .s-spark { margin-top: 8px; display: block; }

/* Legacy .kpi tiles (still used on some pages) reflattened to match ------- */
.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 0; margin: 4px 0; border-top: 1px solid var(--rule); }
.kpi { background: transparent; border: none; border-right: 1px solid var(--line);
    border-radius: 0; padding: 16px 22px 18px 0; box-shadow: none; }
.kpi:last-child { border-right: none; }
.kpi .k-label { font-family: var(--font-mono); color: var(--muted); font-weight: 500;
    font-size: .72rem; text-transform: uppercase; letter-spacing: .08em; }
.kpi .k-value { font-family: var(--font-mono); color: var(--ink); font-weight: 600;
    font-size: 2rem; line-height: 1.1; margin-top: 6px; }
.kpi .k-sub { font-family: var(--font-mono); color: var(--muted); font-size: .78rem; margin-top: 4px; }

/* Risk / status tags: flat squared tags, semantic colour, hairline border - */
.badge { display: inline-flex; align-items: center; gap: 6px; padding: 2px 8px;
    border-radius: 2px; font-family: var(--font-mono); font-weight: 500;
    font-size: .74rem; letter-spacing: .02em; border: 1px solid currentColor; }

/* Streamlit metric: flat, no card. Big mono figure, small mono label. ----- */
[data-testid="stMetric"] { background: transparent; border: none; border-top: 1px solid var(--line);
    border-radius: 0; padding: 14px 0 4px; box-shadow: none; }
[data-testid="stMetricValue"] { font-family: var(--font-mono); color: var(--ink); font-weight: 600; }
[data-testid="stMetricLabel"] { font-family: var(--font-mono); color: var(--muted); font-weight: 500;
    text-transform: uppercase; letter-spacing: .06em; font-size: .74rem; }
[data-testid="stMetricDelta"] { font-family: var(--font-mono); }

/* Dataframe: flat, hairline framed, no shadow ---------------------------- */
[data-testid="stDataFrame"] { border-radius: 0; overflow: hidden;
    border: 1px solid var(--line); box-shadow: none; }

/* Buttons: squared, ink outline, invert on hover (no fill/gradient) ------- */
.stButton > button { border-radius: 2px; border: 1px solid var(--ink);
    background: transparent; color: var(--ink); font-family: var(--font-mono);
    font-weight: 500; letter-spacing: .02em; text-transform: uppercase; font-size: .8rem;
    transition: background var(--dur-1) ease, color var(--dur-1) ease, transform var(--dur-1) var(--ease-out); }
.stButton > button:hover { background: var(--ink); }
.stButton > button:hover, .stButton > button:hover * { color: var(--paper) !important; }
.stButton > button:active { transform: translateY(1px); }
.stButton > button[kind="primary"] { background: var(--ink); }
.stButton > button[kind="primary"], .stButton > button[kind="primary"] * { color: var(--paper) !important; }
.stButton > button[kind="primary"]:hover { background: var(--ink-2); }

hr { margin: 1.6rem 0; border: none; border-top: 1px solid var(--line); opacity: 1; }

/* Expander: flat hairline, no elevation ---------------------------------- */
[data-testid="stExpander"] details { border-radius: 0; border: none;
    border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); box-shadow: none; }
[data-testid="stExpander"] summary { font-family: var(--font-mono); text-transform: uppercase;
    letter-spacing: .04em; font-size: .82rem; }

/* Bordered containers → hairline blocks, not floating cards --------------- */
[data-testid="stVerticalBlockBorderWrapper"]:not(:has(.stFullScreenFrame)) {
    border-radius: 0; border-color: var(--line); box-shadow: none; }

/* Footer ----------------------------------------------------------------- */
.app-footer { display: block; width: 100%; margin: 48px auto 0; padding: 20px 0 10px;
    border-top: 1px solid var(--rule); text-align: left !important;
    color: var(--muted); font-family: var(--font-mono); font-size: .78rem; line-height: 1.6; }
.app-footer strong { color: var(--ink); font-weight: 600; }
[data-testid="stMarkdownContainer"]:has(.app-footer) { width: 100%; }

/* Breadcrumb ------------------------------------------------------------- */
.crumb { font-family: var(--font-mono); color: var(--muted); font-size: .74rem;
    text-transform: uppercase; letter-spacing: .08em; margin-bottom: .5rem; }

/* Motion: a single restrained rise on section entrance ------------------- */
@keyframes riseIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
.main .block-container > div { animation: riseIn var(--dur-2) var(--ease-out) both; }
.main .block-container > div:nth-child(1) { animation-delay: 0ms; }
.main .block-container > div:nth-child(2) { animation-delay: 40ms; }
.main .block-container > div:nth-child(3) { animation-delay: 80ms; }
.main .block-container > div:nth-child(n+4) { animation-delay: 120ms; }

/* Chrome cleanup --------------------------------------------------------- */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
[data-testid="stHeader"] { background: transparent; }

/* Remove the left sidebar entirely (top nav is the only navigation) ------ */
[data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] { display: none !important; }

/* Top nav: monospace, quiet, ink underline on the active/hover item ------ */
[data-testid="stHeader"] a, header a[href] { font-family: var(--font-mono);
    text-transform: uppercase; letter-spacing: .04em; font-size: .8rem;
    transition: color var(--dur-1) ease, opacity var(--dur-1) ease; }

/* Admin: the last nav item, greyed as a quieter secondary entry ---------- */
[data-testid="stHeader"] a[href*="Admin"], header a[href*="Admin"] { color: var(--muted) !important; opacity: .7; }
[data-testid="stHeader"] a[href*="Admin"] *, header a[href*="Admin"] * { color: var(--muted) !important; fill: var(--muted) !important; }
[data-testid="stHeader"] a[href*="Admin"]:hover, header a[href*="Admin"]:hover { opacity: 1; }

/* Accessibility: collapse motion for users who opt out ------------------- */
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
    }
}
"""
