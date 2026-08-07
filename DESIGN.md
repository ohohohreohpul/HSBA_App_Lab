# Supplier Scorecard — Design & Architecture

Design rationale for the redesigned app, plus a roadmap. This is the written
half of the "senior UX designer / full-stack engineer" brief; the app itself is
the built half.

---

## 1. Information architecture

The old app was **one long scrolling page** with a left sidebar mixing filters,
threshold controls and (implicitly) navigation. The redesign splits it into a
**linear task workflow** exposed as a top nav:

```
Home ──▶ Scorecards ──▶ Drilldown ──▶ Analytics        Admin (hidden, gated)
 entry     triage         diagnose      portfolio        back-office
```

- **Home** — orient + one click to work. KPIs answer "is anything on fire?"
- **Scorecards** — the 90% page. Find and triage suppliers.
- **Drilldown** — diagnose one supplier in depth.
- **Analytics** — zoom out to the portfolio.
- **Admin** — separate audience (data stewards), so it's off the main path and
  behind a role gate.

Each working page shows a **breadcrumb** (`Home › Scorecards › Drilldown`) so
users always know where they are in the flow.

## 2. Page structure & wireframe notes

**Home** — gradient hero + CTA · KPI tile row · 3 workflow cards · discreet
admin dot in the footer.

**Scorecards** — search box (with "did you mean") · collapsible filter panel
(country, category, risk, threshold, score range, missing-data / low-confidence
toggles) · KPI row for the *filtered* set · column-visibility + CSV/Excel export
· paginated table with the **Overall** column red when below threshold and a ⚠
prefix on low-confidence rows · a "jump to drilldown" selector · an expandable
"below threshold" list.

**Drilldown** — supplier picker (honours a jump from Scorecards) · header with
risk badge + meta · 4 metric tiles · score-components bar (with weighted
contributions) beside threshold-violations + recommendations · quarterly trend
line with a threshold rule · orders table · an ⓘ score-explanation popover.

**Analytics** — filter panel · KPI row · risk pie + score histogram · country
bar + category-avg bar · category×criterion heatmap · monthly trend line.

**Admin** — login gate → three tabs: *Manage data* (inline editor + add/delete),
*Integrity checks* (finding cards with one-click fixes), *Bulk import/export*.

## 3. Component hierarchy

```
app.py (router, theme)
└─ lib/ui.py         inject_theme · kpi_row · risk_badge_html · breadcrumb
│                    · score_info_popover
└─ lib/core.py       load_tables · build_scoreboard · risk_level/color
│                    · fuzzy_search/suggest_names · apply_filters
│                    · run_data_checks · save_table
└─ lib/admin.py      is_admin · try_login · logout
```

Pages are thin: they compose these primitives. `apply_filters` is shared by
Scorecards **and** Analytics so filtering behaves identically in both.

## 4. Database / data improvements

Implemented now (CSV-backed):

- One **scoreboard builder** with weighted scoring, risk bands, confidence flag,
  order stats — cached, single source of truth.
- **Integrity checks**: missing emails, duplicate names, no-rating suppliers,
  orphaned orders, invalid categories, out-of-range ratings, low confidence.
- **Write-back**: admin edits persist to CSV and bust the cache.

Recommended next: migrate CSVs → **SQLite** (or Postgres) so edits are
transactional, referential integrity is enforced by the DB (foreign keys make
orphaned orders impossible), and "database checks" become real constraints
rather than after-the-fact scans. Adding `comments` and `audit_log` tables would
also enable real per-supplier comments and an audit trail on the drilldown.

## 5. Backend architecture (target, beyond Streamlit)

Streamlit is one process with **no real backend, no true RBAC, no server-side
pagination**. What's approximated today and how a real stack would do it:

| Requirement | Now (Streamlit) | Real target |
|---|---|---|
| Auth / admin | code checked server-side, session flag | Auth provider + JWT/session, RBAC middleware |
| Pagination | client-side slicing | server-side `LIMIT/OFFSET` or keyset |
| Persistence | CSV write-back | Postgres with FKs + migrations |
| Caching | `st.cache_data` | Redis / query cache |
| Optimistic updates | full rerun | React Query mutations |

Suggested full rewrite if the project outgrows Streamlit: **FastAPI + Postgres**
backend, **Next.js/React + TanStack Table** frontend. Documented, not built —
out of scope for a Streamlit assignment.

## 6. UI/UX improvements delivered

Top-nav workflow (was: sidebar) · consistent indigo theme + risk palette
(red/amber/green) reused across every chart · KPI tiles · fuzzy search with
suggestions · conditional row formatting · column visibility · pagination ·
CSV/Excel export · score-transparency popovers · breadcrumbs · responsive KPI
grid · fewer clicks (jump-to-drilldown from the table; CTA-driven home).

## 7. Suggested technology stack

- **Now:** Streamlit · pandas · Altair · openpyxl (all already in the app).
- **Later:** FastAPI · SQLAlchemy · Postgres · Alembic (backend);
  Next.js · React · TanStack Table · Recharts (frontend); RapidFuzz for
  search at scale.

## 8. Implementation plan (done here)

1. Extract shared `lib/` (scoring, search, UI) ✅
2. Top-nav multipage router ✅
3. Landing ✅ → Scorecards ✅ → Drilldown ✅ → Analytics ✅
4. Hidden Admin (auth, manage, checks, bulk) ✅
5. Verify every page renders (Streamlit `AppTest`) ✅

## 9. Priority list

**High**
- Migrate CSV → SQLite/Postgres (unlocks real integrity + persistence).

The Admin code-gate is intentionally a **demo, not a security feature** — see the
honesty notes. If this ever guarded real data it would need proper auth, but
that is out of scope for the assignment.

**Medium**
- Server-side pagination + search (matters past a few thousand suppliers).
- Supplier aliases table to strengthen fuzzy search.
- Saved filter views / shareable URL state.
- Automated tests in CI (extend the `AppTest` checks used during the build).

**Low**
- Dark-mode theme toggle.
- PDF export of a supplier scorecard.
- Email alerts when a supplier crosses the threshold.
- Mobile-specific table layout (cards instead of a wide table).

## 10. Honesty notes

- **Admin gate is a deliberate showcase, not security.** It exists to demo a
  role-gated back-office UI; the code (`0000`) just flips a session flag. It is
  not meant to protect anything.
- **Pagination** is client-side; fine at 150 suppliers, revisit at scale.
- The data is clean, so integrity checks currently report mostly "all clear"
  (except 38 low-confidence suppliers, which is real) — they light up as soon as
  data degrades or after an admin delete creates orphans.
