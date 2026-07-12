# Formula verification checklist

A to-do list for checking every calculation in the scoring pipeline.
All scoring logic lives in **`lib/core.py`** (single source of truth).

---

## 1. Criteria weights (`CRITERIA_WEIGHTS`, core.py:47)
- [ ] Weights sum to exactly **1.0** (0.30 + 0.35 + 0.20 + 0.15 = 1.00).
- [ ] The four keys match `CRITERIA` (delivery_time, quality, price, communication).
- [ ] Weighting rationale still holds (quality 0.35 & delivery 0.30 highest — intended?).
- [ ] Weights used in `build_scoreboard` (core.py:224) are the *same* dict used
      in the drilldown trend chart (`3_Drilldown.py`, `overall` calc) — no drift.

## 2. Overall score (`build_scoreboard`)
- [ ] `overall = 0.85·base + 0.15·cancel_score`, where `base` is the weighted
      average of the four criteria over **delivered orders only** and `cancel_score`
      is the reliability penalty (§12). Confirm the blend, not a plain criterion mean.
- [ ] Result lands in the **1.0–5.0** range for real data (spot-check a few suppliers).
- [ ] Rounding to 2 dp happens *after* the blend, not before.
- [ ] Hand-calculate one supplier end-to-end and compare to the app's "Overall".

## 3. Delivery score (`delivery_days_to_score` / `_linear_score`, core.py:75–87)
- [ ] Band is correct: **≤ 5 days → 5.0**, **≥ 30 days → 1.0**, linear between.
- [ ] `delivery_days = delivery_date − order_date` in **days** (core.py:150) — no off-by-one.
- [ ] Suppliers with no delivered orders have **no** delivery score (NaN) — it is
      *excluded* from the base and the remaining weights are re-normalised. They are
      flagged `missing_delivery_data`. (There is no "neutral 3.0" fallback.)
- [ ] Negative delivery_days (delivery before order = bad data) — decide how to handle;
      currently they'd score > 5 before clamping. Check `_linear_score` clamp holds.

## 4. Price score (`build_scoreboard`, `_price_for_category`)
- [ ] Scaling is **relative within each category**: the cheapest supplier in a
      category → 5, the priciest → 1 (not scaled across all suppliers).
- [ ] Uses **average** order value per supplier over **delivered, non-special**
      orders (`avg_price_eur`), not total spend and not cancelled orders.
- [ ] Understand the side effect: adding/removing a supplier **re-scales that
      category's** price scores (relative, not absolute).
- [ ] Category with 0–1 priced suppliers → lone supplier is neutral 3.0, empty → NaN.

## 5. Quality & Communication (core.py:171)
- [ ] These are plain **means** of the 1–5 ratings from `ratings.csv`.
- [ ] Suppliers with no ratings → NaN → check how that flows into `overall_score`.

## 6. Measured vs. rated consistency
- [ ] `ratings.csv` holds only `quality` & `communication` now (the dead
      `delivery_time`/`price` rating columns were removed). Delivery & price are
      derived from order data (`MEASURED_CRITERIA`). Confirm no code still expects
      the old columns.
- [ ] `ratings.csv` contains ratings for **delivered orders only** — cancelled and
      in-transit orders are not rated. Confirm the confidence counts reflect that.
- [ ] The data-check loop validates only `quality` & `communication` are 1–5.

## 7. Risk bands (`RISK_BANDS` / `risk_level`, core.py:98–112)
- [ ] Boundaries: **High** [0, 2.5), **Medium** [2.5, 3.5), **Low** [3.5, 5.01).
- [ ] Half-open intervals — a score of exactly **2.5** is Medium, exactly **3.5** is Low.
- [ ] Upper bound 5.01 so a perfect **5.0** is still "Low" (not "Unknown").
- [ ] NaN score → "Unknown" (not silently mislabelled).

## 8. Threshold & confidence
- [ ] `DEFAULT_THRESHOLD = 3.0` (core.py:95) matches the UI default and drilldown rule line.
- [ ] `MIN_RATINGS_FOR_CONFIDENCE = 3` (core.py:92): a supplier with < 3 ratings is
      flagged `low_confidence` but its score is still shown — confirm that's intended.

## 9. Drilldown trend recomputation (`3_Drilldown.py`)
- [ ] The trend uses the **same** weights, `delivery_days_to_score`, `_linear_score`
      and `cancel_reliability_score` as `build_scoreboard` — base from delivered
      orders, then blended with each quarter's cancellation reliability.
- [ ] Price in the trend uses the **category** anchors from the board (matching the
      scoreboard's per-category scaling), not the supplier's own min/max.
- [ ] The combined trend average should land close to the headline "Overall".
- [ ] Quarterly grouping (`to_period("Q")`) averages the right orders per quarter.

## 10. Aggregations (`ostats` / spend / status counts)
- [ ] `total_spend = Σ amount_eur` over **Delivered + In Transit** only (cancelled
      excluded); `num_orders = count(order_id)` over **all** orders.
- [ ] `avg_delivery_days` / `avg_price_eur` are **means** and ignore NaN correctly.
- [ ] `num_ratings` counts rating rows per supplier, not orders.
- [ ] `num_delivered` / `num_cancelled` come from the status value-counts and feed §12.

## 12. Cancellation reliability (`cancel_reliability_score`, `CANCEL_WEIGHT`)
- [ ] `cancel_rate = cancelled / (cancelled + delivered)` — in-transit orders are
      **not** in the denominator.
- [ ] `cancel_score = 1 + 4·(1 − rate)^CANCEL_EXPONENT` (exponent 2 → convex, so the
      penalty accelerates). 0% → 5.0, 100% → 1.0.
- [ ] Blended at `CANCEL_WEIGHT = 0.15`; base carries the other 0.85.
- [ ] A supplier with no resolved orders → `cancel_score` NaN → overall falls back to
      base; a supplier with no base (nothing delivered) → overall falls back to the
      cancel_score. Confirm neither path yields a spurious NaN overall.

## 11. Reconciliation test
- [ ] Pick **2–3 suppliers**, compute every criterion and the overall by hand from
      the raw CSVs, and confirm they match the Scorecards table exactly.
- [ ] Verify the same numbers agree across **Scorecards**, **Drilldown**, and **Analytics**.
