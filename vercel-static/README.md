# Supplier Scorecard — static build (for Vercel)

A **self-contained static version** of the Streamlit app, built so it can run on
**Vercel** (which hosts static sites + serverless functions, and cannot run a
Streamlit server). It reproduces the editorial dashboard — overview story stats,
a sortable/filterable board, a per-supplier drilldown, and analytics charts —
entirely in the browser. No backend, no Python at runtime.

## What it is (and isn't)

- **Is:** a faithful, read-only snapshot. The scores come from the *real* scoring
  logic (`lib/core`), frozen to `data.json` at build time.
- **Isn't:** the Admin/editing surface. Data is frozen; there is no write-back.
  Re-run the build to refresh it.

## Files

| File | Role |
|---|---|
| `index.html` · `styles.css` · `app.js` | the static site |
| `data.json` | frozen, scored dataset (generated) |
| `build_static.py` | regenerates `data.json` from the CSVs (dev-only, not deployed) |
| `vercel.json` · `.vercelignore` | force a static deploy; keep Python out of the upload |

## Rebuild the data (only when the CSVs change)

From the **repo root**:

```bash
python vercel-static/build_static.py
```

This writes `vercel-static/data.json`.

## Preview locally

```bash
cd vercel-static
python -m http.server 8000
# open http://localhost:8000
```

## Deploy to Vercel

**Dashboard:** New Project → import the GitHub repo → set **Root Directory** to
`vercel-static` → **Deploy**. (Root Directory is the key step — it stops Vercel
from seeing the Streamlit `app.py` at the repo root.)

**CLI:**

```bash
cd vercel-static
vercel --prod
```

Framework preset: **Other** (static). No build step runs; Vercel just serves the
files.
