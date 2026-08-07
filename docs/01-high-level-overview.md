# High-level project overview

The Supplier Scorecard is a multipage **Streamlit** app that evaluates suppliers
from four CSV tables. All scoring logic lives in `lib/core.py` (single source of
truth); the pages under `pages/` are thin views that read the scored board and
render it. Admin edits write back to the CSVs and clear the cache so every page
refreshes.

```mermaid
flowchart TB
    subgraph Data["📁 data/ (CSV store)"]
        direction LR
        C[categories.csv]
        S[suppliers.csv]
        O[orders.csv]
        R[ratings.csv]
    end

    subgraph Logic["🧠 lib/ (single source of truth)"]
        direction TB
        CORE["core.py<br/>load_tables · build_scoreboard<br/>scoring formula · fuzzy_search<br/>apply_filters · run_data_checks"]
        UI["ui.py<br/>theme · KPI tiles · badges<br/>score-info popover"]
        ADMIN["admin.py<br/>login gate (showcase)"]
    end

    subgraph Pages["🖥️ pages/ (Streamlit views)"]
        direction TB
        P1["1 · Home / Landing"]
        P2["2 · Scorecards"]
        P3["3 · Drilldown"]
        P4["4 · Analytics"]
        P5["5 · Admin 🔐"]
    end

    APP["app.py<br/>st.navigation (top bar)"]

    Data -->|"read + cache"| CORE
    CORE --> UI
    APP --> Pages
    CORE -.->|"build_scoreboard()"| P1 & P2 & P3 & P4
    UI -.-> P1 & P2 & P3 & P4 & P5
    ADMIN -.->|"is_admin()"| P5
    P5 ==>|"save_table() → write CSV<br/>+ clear cache"| Data

    classDef data fill:#eef2ff,stroke:#4f46e5,color:#1e293b;
    classDef logic fill:#f0fdf4,stroke:#10b981,color:#1e293b;
    classDef page fill:#fff7ed,stroke:#f59e0b,color:#1e293b;
    class C,S,O,R data;
    class CORE,UI,ADMIN logic;
    class P1,P2,P3,P4,P5 page;
```

**Reading the diagram**

- **data/** holds the four source tables. They are the only persistent state.
- **lib/core.py** loads and caches them, then derives one scored row per supplier
  (`build_scoreboard`). Everything downstream reads that board.
- **pages/** render the board; only **Admin** writes back, via `save_table()`,
  which rewrites the CSV and clears the cache so the next rerun re-scores.
