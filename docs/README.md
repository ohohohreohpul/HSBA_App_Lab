# Documentation

Architecture and logic diagrams for the Supplier Scorecard app. Each file
contains a [Mermaid](https://mermaid.js.org/) diagram that renders on GitHub and
in most Markdown viewers.

| Diagram | What it shows |
|---------|---------------|
| [01 · High-level overview](01-high-level-overview.md) | The whole project at a glance: data → logic → pages, and the Admin write-back loop. |
| [02 · Data structure](02-data-structure.md) | The four CSV tables, their columns and relationships (ER diagram), and what data lives where. |
| [03 · Scoring calculation](03-scoring-calculation.md) | How a supplier's overall 1–5 score is built: delivered-only base + exponential cancellation penalty. |
| [04 · Website flow](04-website-flow.md) | Page navigation, the "Open" jump to Drilldown, and the Admin login/write-back flow. |

All scoring logic lives in `lib/core.py` (the single source of truth). If the
formula there changes, update **03-scoring-calculation.md** to match.
