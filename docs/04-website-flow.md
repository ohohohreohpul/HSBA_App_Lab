# Website / navigation flow

The app uses `st.navigation(position="top")` — a persistent top nav bar on every
page. Buttons and the Scorecards "Open" action jump between pages via
`st.switch_page()`; some jumps carry state through `st.session_state`.

```mermaid
flowchart TD
    NAV["🧭 Top navigation bar (always visible)<br/>Home · Scorecards · Drilldown · Analytics · Admin"]

    HOME["🏠 Home / Landing<br/>hero · at-a-glance KPIs · workflow cards"]
    SCORE["📋 Scorecards<br/>fuzzy search · filters · sortable table"]
    DRILL["🔎 Drilldown<br/>one supplier: components · trend · orders"]
    ANA["📈 Analytics<br/>risk pie · histogram · heatmap"]

    subgraph AdminGate["🔐 Admin"]
        LOGIN{"is_admin()?"}
        LOGINFORM["Access-code form<br/>(showcase gate, default 0000)"]
        ADMINUI["Admin console<br/>📝 Manage · 🩺 Integrity · 📦 Import/Export"]
    end

    NAV --- HOME & SCORE & DRILL & ANA & LOGIN

    HOME -->|"Open Scorecards →"| SCORE
    HOME -->|"View Analytics"| ANA
    HOME -->|"Go to Drilldown"| DRILL

    SCORE -->|"click 'Open ▶' on a row<br/>sets drilldown_supplier"| DRILL
    DRILL -->|"picker pre-selected<br/>from session_state"| DRILL

    LOGIN -->|"not logged in"| LOGINFORM
    LOGINFORM -->|"correct code → is_admin=True, rerun"| ADMINUI
    LOGINFORM -->|"wrong code"| LOGINFORM
    ADMINUI -->|"Log out → switch_page"| HOME
    ADMINUI ==>|"save / fix / import<br/>writes CSV + clears cache"| REFRESH{{"all pages re-score<br/>on next rerun"}}

    classDef page fill:#fff7ed,stroke:#f59e0b,color:#1e293b;
    classDef admin fill:#f1f5f9,stroke:#64748b,color:#1e293b;
    classDef nav fill:#eef2ff,stroke:#4f46e5,color:#1e293b;
    class HOME,SCORE,DRILL,ANA page;
    class LOGIN,LOGINFORM,ADMINUI,REFRESH admin;
    class NAV nav;
```

## Page-by-page

| Page | Purpose | Key interactions |
|------|---------|------------------|
| **Home** (`1_Landing.py`) | Entry point, portfolio KPIs, workflow overview | CTA buttons → Scorecards / Analytics / Drilldown |
| **Scorecards** (`2_Scorecards.py`) | The main working table: fuzzy search, filters, per-column sort | "Open ▶" button on a row sets `drilldown_supplier` and jumps to Drilldown |
| **Drilldown** (`3_Drilldown.py`) | Full profile of one supplier | Reads `drilldown_supplier` to pre-select; supplier picker with fuzzy search |
| **Analytics** (`4_Analytics.py`) | Portfolio charts (risk pie, score histogram, category × criterion heatmap) | Filters react across all charts |
| **Admin** (`5_Admin.py`) | Role-gated data management | Login gate → edit/save, integrity checks + one-click fixes, bulk import/export |

## State passed between pages

- **`drilldown_supplier`** — set by the Scorecards "Open" button, consumed
  (`.pop`) by Drilldown to pre-select the supplier.
- **`is_admin`** — session flag flipped by the Admin login form; every Admin
  render checks `is_admin()` before showing anything.
- **Cache invalidation** — any Admin write calls `save_table()`, which clears the
  `load_tables` / `build_scoreboard` caches, so all pages recompute on the next
  rerun.
