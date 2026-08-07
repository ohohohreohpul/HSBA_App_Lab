# Scoring calculation

How one supplier's **overall score (1–5)** is computed in `build_scoreboard()`
(`lib/core.py`). The overall is a **base score** (four criteria, delivered orders
only) blended with a **reliability score** that punishes cancellations.

```mermaid
flowchart TD
    START(["Supplier's orders + ratings"]) --> SPLIT{"Split by status"}

    SPLIT -->|Delivered| DEL["Delivered orders"]
    SPLIT -->|In Transit| TRANSIT["In-transit orders"]
    SPLIT -->|Cancelled| CANC["Cancelled orders"]

    %% ---- BASE: four criteria from delivered orders ----
    DEL --> DAYS["avg delivery_days"]
    DEL --> PRICE["avg amount_eur<br/>(non-special only)"]
    DEL --> QC["avg quality &<br/>communication (from ratings)"]

    DAYS --> DSCORE["Delivery score 1–5<br/>≤5 days→5.0, ≥30 days→1.0<br/>delivery_days_to_score()"]
    PRICE --> PSCORE["Price score 1–5<br/>scaled vs CATEGORY peers<br/>cheapest→5.0, priciest→1.0<br/>_price_for_category()"]
    QC --> QSCORE["Quality 1–5"]
    QC --> CSCORE["Communication 1–5"]

    DSCORE --> BASE
    PSCORE --> BASE
    QSCORE --> BASE
    CSCORE --> BASE

    BASE["<b>base_score</b> = weighted avg<br/>Delivery·0.35 + Quality·0.30<br/>+ Price·0.20 + Comm·0.15<br/><i>NaN criteria dropped, weights re-normalised</i><br/>weighted_overall()"]

    %% ---- RELIABILITY: penalty from cancellations ----
    DEL --> NDEL["n_delivered"]
    CANC --> NCANC["n_cancelled"]
    NDEL --> RATE
    NCANC --> RATE
    RATE["cancel_rate = cancelled /<br/>(cancelled + delivered)<br/><i>in-transit ignored</i>"]
    RATE --> RSCORE["<b>cancel_score</b> = 1 + 4·(1 − rate)²<br/>0%→5.0, exponential penalty<br/>cancel_reliability_score()"]

    %% ---- BLEND ----
    BASE --> BLEND
    RSCORE --> BLEND
    BLEND["<b>overall_score</b> =<br/>0.85·base_score + 0.15·cancel_score<br/><i>falls back to whichever side exists</i>"]

    BLEND --> RISK{"risk_level()"}
    RISK -->|< 2.5| HIGH["🔴 High"]
    RISK -->|2.5 – 3.5| MED["🟠 Medium"]
    RISK -->|≥ 3.5| LOW["🟢 Low"]

    TRANSIT -.->|"counts toward total_spend only"| SPEND["total_spend<br/>(Delivered + In Transit)"]
    DEL -.-> SPEND

    classDef base fill:#eef2ff,stroke:#4f46e5,color:#1e293b;
    classDef rel fill:#fef2f2,stroke:#ef4444,color:#1e293b;
    classDef out fill:#f0fdf4,stroke:#10b981,color:#1e293b;
    class DSCORE,PSCORE,QSCORE,CSCORE,BASE base;
    class RATE,RSCORE rel;
    class BLEND,HIGH,MED,LOW out;
```

## The formula

```
base_score = 0.35·Delivery + 0.30·Quality + 0.20·Price + 0.15·Communication
             (delivered orders only; any NaN criterion is dropped and the
              remaining weights are re-normalised to sum to 1.0)

cancel_rate  = n_cancelled / (n_cancelled + n_delivered)
cancel_score = 1 + 4·(1 − cancel_rate)²          # exponential, 1–5

overall_score = 0.85·base_score + 0.15·cancel_score
```

**Effective weight of each component in the overall** (what the drilldown tiles
show): the four base criteria share the 85% base, reliability takes 15%.

| Component | Base weight | Effective weight in overall |
|-----------|:-----------:|:---------------------------:|
| Delivery Time | 0.35 | 0.2975 (~30%) |
| Quality | 0.30 | 0.2550 (~26%) |
| Price | 0.20 | 0.1700 (17%) |
| Communication | 0.15 | 0.1275 (~13%) |
| **Reliability** | — | **0.1500 (15%)** |

## Edge cases (handled in the blend)

- **No delivered orders** → `base_score` is NaN → overall falls back to
  `cancel_score` (a supplier that only ever cancelled scores 1.0, High risk).
- **No resolved orders** (nothing delivered or cancelled) → `cancel_score` is
  NaN → overall falls back to `base_score`.
- **Special-circumstance orders** → excluded from the price average (a justified
  high price shouldn't lower the price score), but still count as delivered.
- **< 3 rated (delivered) orders** → `low_confidence = True`; the score is still
  shown but flagged.

## Where the same math is reused

`lib/core.py` is the single source of truth. The **Drilldown trend chart**
recomputes the quarterly score with the *same* helpers
(`delivery_days_to_score`, `_linear_score`, `cancel_reliability_score`,
`weighted_overall`) and the category price anchors from the board, so the trend
line reconciles with the headline score.
