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

## 2. Overall score (`build_scoreboard`, core.py:224)
- [ ] `overall = Σ(criterion × weight)` — confirm it's a weighted **sum**, not a mean.
- [ ] Result lands in the **1.0–5.0** range for real data (spot-check a few suppliers).
- [ ] Rounding to 2 dp (core.py:227) happens *after* the weighted sum, not before.
- [ ] Hand-calculate one supplier end-to-end and compare to the app's "Overall".

## 3. Delivery score (`delivery_days_to_score` / `_linear_score`, core.py:75–87)
- [ ] Band is correct: **≤ 5 days → 5.0**, **≥ 30 days → 1.0**, linear between.
- [ ] `delivery_days = delivery_date − order_date` in **days** (core.py:150) — no off-by-one.
- [ ] Suppliers with no delivered orders get neutral **3.0** and are flagged
      `missing_delivery_data` (core.py:203–210) — confirm this is the intended default.
- [ ] Negative delivery_days (delivery before order = bad data) — decide how to handle;
      currently they'd score > 5 before clamping. Check `_linear_score` clamp holds.

## 4. Price score (`build_scoreboard`, core.py:212–221)
- [ ] Scaling is **relative** to the observed range: cheapest supplier → 5, priciest → 1.
- [ ] Uses **average** order value per supplier (`avg_price_eur`), not total spend.
- [ ] Understand the side effect: adding/removing a supplier **re-scales everyone's**
      price score (relative, not absolute). Confirm this is acceptable for the assignment.
- [ ] Single-supplier / all-equal-price edge case → `_linear_score` returns 3.0 (best==worst).

## 5. Quality & Communication (core.py:171)
- [ ] These are plain **means** of the 1–5 ratings from `ratings.csv`.
- [ ] Suppliers with no ratings → NaN → check how that flows into `overall_score`.

## 6. ⚠️ Measured vs. rated consistency (IMPORTANT)
- [ ] `ratings.csv` has `delivery_time` and `price` columns, but the scoreboard
      **ignores them** and derives delivery/price from order data instead
      (core.py:64–65, MEASURED_CRITERIA). Confirm this is intentional and the
      rating-file columns aren't accidentally expected to matter.
- [ ] The data-check loop (core.py:391) validates all 4 CRITERIA are 1–5 in ratings.csv,
      including the now-unused delivery_time/price rating columns — decide if that
      check should stay or be dropped.

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
- [ ] The per-order `overall` in the trend chart uses the **same weights** and the
      **same** `delivery_days_to_score` / `_linear_score` as `build_scoreboard`.
- [ ] Price in the trend is scaled across **that supplier's own orders** (pmin/pmax),
      which differs from the scoreboard's **cross-supplier** scaling — confirm this
      intentional difference and that it's not presented as the same number.
- [ ] Quarterly grouping (`to_period("Q")`) averages the right orders per quarter.

## 10. Aggregations (`ostats`, core.py:184–194)
- [ ] `total_spend = Σ amount_eur`, `num_orders = count(order_id)` — correct columns.
- [ ] `avg_delivery_days` / `avg_price_eur` are **means** and ignore NaN correctly.
- [ ] `num_ratings` counts rating rows per supplier, not orders.

## 11. Reconciliation test
- [ ] Pick **2–3 suppliers**, compute every criterion and the overall by hand from
      the raw CSVs, and confirm they match the Scorecards table exactly.
- [ ] Verify the same numbers agree across **Scorecards**, **Drilldown**, and **Analytics**.
