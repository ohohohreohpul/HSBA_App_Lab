# Supplier Scorecard

Group 3 — Digital Lab App Development, SoSe 2026.

A Streamlit app that helps a procurement team **evaluate, compare and monitor
suppliers**. It scores each supplier from individual order ratings, flags risky
suppliers, and lets you drill into any supplier or analyse the whole portfolio —
all from a single, clean workflow.

## The workflow

The app follows one primary path, exposed as a **top navigation bar** (no more
left-side menu):

```
🏠 Home  →  📋 Scorecards  →  🔎 Drilldown  →  📈 Analytics      (+ 🔐 hidden Admin)
```

| Page | What it's for |
|------|---------------|
| **Home** | Overview, quick KPIs, and one click into the working pages. |
| **Scorecards** | The main table: powerful filters, fuzzy search, conditional risk highlighting, column visibility, pagination, CSV/Excel export. |
| **Drilldown** | Full profile of one supplier: weighted score components, threshold violations, recommendations, quarterly trend, and all orders — every value computed from the CSVs. Every score has an **ⓘ "how is this calculated?"** popover. |
| **Analytics** | Portfolio KPIs plus risk pie, score histogram, country/category bars, a category×criterion heatmap, and a monthly score trend — all filterable. |
| **Admin** | Hidden, code-gated database management + automated integrity checks (see below). |

## Architecture

Still a **single Streamlit app** — one process is both the "backend" (loading
CSVs, computing scores) and the "frontend" (the pages you see). The rewrite
splits responsibilities cleanly:

```
app.py                 # entrypoint: theme + top-nav (st.navigation) router
lib/
  core.py              # data loading, the scoring formula, risk logic,
                       #   fuzzy search, filtering, data-quality checks
  ui.py                # shared theme (CSS) + components (KPI tiles, badges,
                       #   the score-info popover)
  admin.py             # admin authentication (role gate)
pages/
  1_Landing.py  2_Scorecards.py  3_Drilldown.py  4_Analytics.py  5_Admin.py
data/                  # the four CSV tables
```

Keeping **all scoring rules in `lib/core.py`** means the table, the drilldown
and the analytics page can never disagree about how a score was computed.

## Run it

```bash
pip install -r requirements.txt
python -m streamlit run app.py     # or python3 on macOS/Linux
```

Streamlit opens <http://localhost:8501>. Stop it with `Ctrl+C`.

## Scoring

Ratings are on a **1–5 scale**, recorded per order. Each supplier's per-criterion
score is the mean of its order ratings. The **overall score is a weighted
average**:

```
Overall = 0.30·Delivery + 0.35·Quality + 0.20·Price + 0.15·Communication
```

Weights live in `lib/core.py` (`CRITERIA_WEIGHTS`) — change them there and the
whole app updates. Overall scores map to **risk bands**: High (< 2.5),
Medium (2.5–3.5), Low (≥ 3.5). Suppliers with fewer than 3 rated orders are
marked **low confidence**.

## Fuzzy search

Search tolerates typos and partial names (e.g. `shezen micro` finds
*Shenzhen MicroParts Ltd*). It combines substring, token-prefix and
`difflib` similarity matching, and shows "did you mean" suggestions.

## Admin mode (hidden)

Admin mode is **not shown in the navigation**. Reach it via the discreet dot in
the Landing-page footer, then enter the code **`0000`**.

> ⚠️ **This gate is a showcase, not security.** It exists purely to demonstrate
> a role-gated back-office UI. The code just flips a session flag and is visible
> in the source — it protects nothing. You can override it in
> `.streamlit/secrets.toml` (`[admin] code = "…"`, see the `.example` file), but
> that's cosmetic. Real RBAC would need a proper backend — see `DESIGN.md`.

Admin mode provides:

- **Manage data** — inline edit any table; every cell edit, row add, or row
  delete **saves to the CSV automatically** (no Save button). Plus a guided
  "add supplier" form with a duplicate guard.
- **Integrity checks** — automatic detection of missing emails, duplicate names,
  suppliers without ratings, orphaned orders, invalid categories, out-of-range
  ratings, and low-confidence suppliers, with **one-click fixes** where safe.
- **Bulk import / export** — download any table (or the full workbook) and
  replace a table from an uploaded CSV (validated against the expected columns).

## Data model

```
categories (1) ──< suppliers (1) ──< orders (1) ──< ratings
```

| Table | Key columns |
|-------|-------------|
| `categories.csv` | `category_id`, `category_name`, `description` |
| `suppliers.csv` | `supplier_id`, `supplier_name`, `country`, `category_id`, `contact_email` |
| `orders.csv` | `order_id`, `supplier_id`, `order_date`, `amount_eur`, `status` |
| `ratings.csv` | `rating_id`, `order_id`, `supplier_id`, `delivery_time`, `quality`, `price`, `communication` |

## Design & roadmap

See **`DESIGN.md`** for the information architecture, component hierarchy,
what's approximated vs. native to Streamlit, a suggested full-stack target, and
a prioritised (High / Medium / Low) improvement list.

## Repository

<https://github.com/Nodolas/uni_aufgabe>
