"""
Global stylesheet for the Supplier Scorecard — the single source of truth for
look & feel.

Design language: **shadcn/ui** (the look, implemented in CSS over Streamlit's
own widgets — not literal React components). Neutral zinc palette, white
surfaces on a faint muted page, 1px borders with a soft ``shadow-sm``, a small
8px radius, Inter throughout, and near-black primary. Colour is otherwise
reserved for meaning (the risk palette). Tokens mirror shadcn's HSL variables so
the whole app re-themes from ``:root``.
"""

APP_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* shadcn/ui tokens (light) --------------------------------------------------- */
:root {
    --background: 0 0% 100%;
    --foreground: 240 10% 3.9%;
    --card: 0 0% 100%;
    --muted: 240 4.8% 95.9%;
    --muted-foreground: 240 3.8% 46.1%;
    --border: 240 5.9% 90%;
    --primary: 240 5.9% 10%;
    --primary-foreground: 0 0% 98%;
    --accent: 240 4.8% 95.9%;
    --ring: 240 5% 65%;
    --radius: 0.5rem;

    /* Semantic risk (destructive / warning / success) */
    --risk-high: #dc2626;
    --risk-med: #d97706;
    --risk-low: #16a34a;

    --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
    --shadow: 0 1px 3px 0 rgb(0 0 0 / 0.08), 0 1px 2px -1px rgb(0 0 0 / 0.06);

    --font: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Base ---------------------------------------------------------------------- */
html, body, [class*="css"] { font-family: var(--font); }
.stApp { background: #fafafa; }

.stApp, .stApp p, .stApp span, .stApp label, .stApp li,
[data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"] * { color: hsl(var(--foreground)); }
[data-testid="stCaptionContainer"], .stApp small { color: hsl(var(--muted-foreground)) !important; }
[data-baseweb="select"] *, [data-testid="stSlider"] * { color: hsl(var(--foreground)) !important; }
[data-testid="stDataFrame"] * { color: hsl(var(--foreground)); }
.tnum { font-variant-numeric: tabular-nums; }

/* Headings: tight, medium weight (shadcn) ----------------------------------- */
h1, h2, h3, h4 { color: hsl(var(--foreground)) !important; letter-spacing: -0.02em; font-weight: 600; }
h1 { font-weight: 700 !important; font-size: clamp(1.7rem, 1.3rem + 1.6vw, 2.25rem); line-height: 1.15; }
h2 { font-size: 1.35rem; }
h3 { font-size: 1.05rem; }

.main .block-container { padding-top: 2rem; max-width: 1200px;
    min-height: calc(100vh - 3rem); display: flex; flex-direction: column; }
.main .block-container > div { width: 100%; }
.main .block-container > div:has(.app-footer) { margin-top: auto; width: 100%; animation: none; }

/* Card primitive ------------------------------------------------------------ */
.card, .kpi, .stat,
[data-testid="stMetric"],
[data-testid="stExpander"] details,
[data-testid="stVerticalBlockBorderWrapper"]:not(:has(.stFullScreenFrame)) {
    background: hsl(var(--card));
    border: 1px solid hsl(var(--border));
    border-radius: var(--radius);
    box-shadow: var(--shadow-sm);
}

/* KPI / story stats (shadcn card) ------------------------------------------- */
.kpi-grid, .stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
    gap: 16px; margin: 6px 0; }
.kpi, .stat { padding: 20px 22px; transition: box-shadow .18s ease, transform .18s ease; }
.kpi .k-label, .stat .s-label { color: hsl(var(--muted-foreground)); font-weight: 500; font-size: .82rem; }
.kpi .k-value, .stat .s-value { color: hsl(var(--foreground)); font-weight: 700; font-size: 2rem;
    line-height: 1.1; margin-top: 8px; font-variant-numeric: tabular-nums; letter-spacing: -0.02em; }
.kpi .k-sub, .stat .s-delta { color: hsl(var(--muted-foreground)); font-size: .82rem; margin-top: 8px; }
.stat .s-delta.up { color: var(--risk-low); }
.stat .s-delta.down { color: var(--risk-high); }
.stat .s-spark { margin-top: 10px; display: block; }
@media (hover: hover) { .kpi:hover, .stat:hover { box-shadow: var(--shadow); transform: translateY(-1px); } }

/* Badge (shadcn) ------------------------------------------------------------ */
.badge { display: inline-flex; align-items: center; gap: 6px; padding: 2px 9px; border-radius: 6px;
    font-weight: 500; font-size: .74rem; line-height: 1.5; border: 1px solid transparent; }

/* Streamlit metric → shadcn card -------------------------------------------- */
[data-testid="stMetric"] { padding: 18px 20px; }
[data-testid="stMetricValue"] { color: hsl(var(--foreground)); font-weight: 700; font-variant-numeric: tabular-nums; }
[data-testid="stMetricLabel"] { color: hsl(var(--muted-foreground)); font-weight: 500; }
[data-testid="stMetricLabel"] p { font-size: .82rem !important; }

/* Dataframe ----------------------------------------------------------------- */
[data-testid="stDataFrame"] { border-radius: var(--radius); overflow: hidden; box-shadow: var(--shadow-sm); }

/* Buttons: default = outline/secondary, primary = solid ---------------------- */
.stButton > button { border-radius: calc(var(--radius) - 2px); border: 1px solid hsl(var(--border));
    background: hsl(var(--card)); color: hsl(var(--foreground)); font-weight: 500; font-size: .9rem;
    box-shadow: var(--shadow-sm); transition: background .15s ease, border-color .15s ease, transform .1s ease; }
.stButton > button:hover { background: hsl(var(--accent)); border-color: hsl(var(--border)); }
.stButton > button:hover * { color: hsl(var(--foreground)) !important; }
.stButton > button:active { transform: translateY(1px); }
.stButton > button[kind="primary"] { background: hsl(var(--primary)); border-color: hsl(var(--primary)); }
.stButton > button[kind="primary"] *, .stButton > button[kind="primary"]:hover * { color: hsl(var(--primary-foreground)) !important; }
.stButton > button[kind="primary"]:hover { background: hsl(240 5.9% 16%); }

/* Inputs: border + focus ring ----------------------------------------------- */
.stTextInput input, [data-baseweb="select"] > div, [data-baseweb="input"] > div {
    border-radius: calc(var(--radius) - 2px) !important; border-color: hsl(var(--border)) !important; }
.stTextInput input:focus, [data-baseweb="select"] > div:focus-within {
    box-shadow: 0 0 0 2px hsl(var(--ring) / 0.5) !important; border-color: hsl(var(--ring)) !important; }
[data-testid="stCheckbox"] input { accent-color: hsl(var(--primary)); }

hr { margin: 1.4rem 0; border: none; border-top: 1px solid hsl(var(--border)); }

/* Expander ------------------------------------------------------------------ */
[data-testid="stExpander"] details { overflow: hidden; }
[data-testid="stExpander"] summary { font-weight: 500; font-size: .92rem; padding: 4px 2px; }
[data-testid="stExpander"] summary:hover { color: hsl(var(--foreground)); }

/* Alerts: shadcn alert (bordered, muted, no loud fills) ---------------------- */
[data-testid="stAlert"] { border-radius: var(--radius); border: 1px solid hsl(var(--border));
    box-shadow: var(--shadow-sm); }

/* Footer -------------------------------------------------------------------- */
.app-footer { display: block; width: 100%; margin: 44px auto 0; padding: 20px 0 10px;
    border-top: 1px solid hsl(var(--border)); text-align: left !important;
    color: hsl(var(--muted-foreground)); font-size: .84rem; line-height: 1.6; }
.app-footer strong { color: hsl(var(--foreground)); font-weight: 600; }
[data-testid="stMarkdownContainer"]:has(.app-footer) { width: 100%; }

/* Breadcrumb ---------------------------------------------------------------- */
.crumb { color: hsl(var(--muted-foreground)); font-size: .82rem; margin-bottom: .5rem; }

/* Entrance motion (subtle) -------------------------------------------------- */
@keyframes riseIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
.main .block-container > div { animation: riseIn .22s ease both; }
.main .block-container > div:nth-child(1) { animation-delay: 0ms; }
.main .block-container > div:nth-child(2) { animation-delay: 40ms; }
.main .block-container > div:nth-child(n+3) { animation-delay: 80ms; }

/* Chrome cleanup ------------------------------------------------------------ */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
[data-testid="stHeader"] { background: transparent; }

/* Remove the left sidebar entirely (top nav is the only navigation) --------- */
[data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] { display: none !important; }

/* Top nav: shadcn nav links -------------------------------------------------- */
[data-testid="stHeader"] a, header a[href] { font-weight: 500; font-size: .9rem;
    color: hsl(var(--muted-foreground)); transition: color .15s ease, opacity .15s ease; }
[data-testid="stHeader"] a:hover, header a[href]:hover { color: hsl(var(--foreground)); }

/* Admin: the last nav item, quieter secondary entry ------------------------- */
[data-testid="stHeader"] a[href*="Admin"], header a[href*="Admin"] { color: hsl(var(--muted-foreground)) !important; opacity: .7; }
[data-testid="stHeader"] a[href*="Admin"] *, header a[href*="Admin"] * { color: hsl(var(--muted-foreground)) !important; fill: hsl(var(--muted-foreground)) !important; }
[data-testid="stHeader"] a[href*="Admin"]:hover, header a[href*="Admin"]:hover { opacity: 1; }

/* Accessibility ------------------------------------------------------------- */
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation-duration: .01ms !important; transition-duration: .01ms !important; }
}
"""
