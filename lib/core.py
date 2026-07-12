"""
Core data, scoring and search logic for the Supplier Scorecard app.
============================================================================

This module is the single source of truth for *everything that isn't UI*:

  * loading the four CSV tables
  * turning per-order ratings into one scored row per supplier
  * the scoring formula (weights, thresholds, risk levels) — all in one place
  * fuzzy search (typo-tolerant matching + suggestions)
  * data-quality checks used by Admin mode

Keeping this here means the pages under ``pages/`` stay thin and the scoring
rules can never drift between the table, the drilldown and the analytics page.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import streamlit as st

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# --------------------------------------------------------------------------- #
# Scoring configuration — the ONE place the formula lives.
# --------------------------------------------------------------------------- #
# The four rating criteria stored in ratings.csv (1-5 scale).
CRITERIA = ["delivery_time", "quality", "price", "communication"]

CRITERIA_LABELS = {
    "delivery_time": "Delivery Time",
    "quality": "Quality",
    "price": "Price",
    "communication": "Communication",
}

# Weighted overall score. Weights sum to 1.0. Quality and delivery matter most
# to a procurement team, so they carry more weight than price/communication.
# Changing these here changes the score everywhere in the app at once.
CRITERIA_WEIGHTS = {
    "delivery_time": 0.35,
    "quality": 0.30,
    "price": 0.20,
    "communication": 0.15,
}

# --------------------------------------------------------------------------- #
# Measured-metric scoring.
#
# Delivery and Price are no longer subjective 1–5 ratings — they are derived
# from real measured quantities and converted to a 1–5 score:
#   * Delivery: average days between order_date and delivery_date (faster = better)
#   * Price:    average order value in € (cheaper = better)
# Quality and Communication remain 1–5 ratings from ratings.csv.
# --------------------------------------------------------------------------- #
# Which criteria are measured (derived) vs. a plain rating.
MEASURED_CRITERIA = {"delivery_time", "price"}
RATING_CRITERIA = {"quality", "communication"}

# Delivery: linear band. <= FAST days scores 5, >= SLOW days scores 1.
DELIVERY_FAST_DAYS = 5.0     # this fast or better → 5.0
DELIVERY_SLOW_DAYS = 30.0    # this slow or worse → 1.0

# Price: cheaper is better. Scored linearly across the observed price range
# (min avg price across suppliers → 5.0, max → 1.0). Computed at build time.


def _linear_score(value: float, best: float, worst: float) -> float:
    """Map a measured value to a 1–5 score. `best` → 5.0, `worst` → 1.0,
    linear in between, clamped. Works whether best<worst or best>worst."""
    if pd.isna(value) or best == worst:
        return float("nan") if pd.isna(value) else 3.0
    frac = (value - worst) / (best - worst)
    frac = min(max(frac, 0.0), 1.0)
    return round(1.0 + 4.0 * frac, 2)


def delivery_days_to_score(days: float) -> float:
    """Fewer days = higher score (5 at ≤5 days, 1 at ≥30 days)."""
    return _linear_score(days, best=DELIVERY_FAST_DAYS, worst=DELIVERY_SLOW_DAYS)


# A supplier needs at least this many rated orders before we fully trust its
# score. Below it, the score is shown but flagged "low confidence".
MIN_RATINGS_FOR_CONFIDENCE = 3

# Default underperformer threshold (overridable in the UI).
DEFAULT_THRESHOLD = 3.0

# Risk bands on the 1–5 overall score. Order matters: first match wins.
RISK_BANDS = [
    ("High", 0.0, 2.5, "#ef4444"),      # red
    ("Medium", 2.5, 3.5, "#f59e0b"),    # amber
    ("Low", 3.5, 5.01, "#10b981"),      # green
]


def risk_level(score: float) -> str:
    """Map an overall score to a High / Medium / Low risk label."""
    if pd.isna(score):
        return "Unknown"
    for label, lo, hi, _ in RISK_BANDS:
        if lo <= score < hi:
            return label
    return "Unknown"


def risk_color(level: str) -> str:
    for label, _, _, color in RISK_BANDS:
        if label == level:
            return color
    return "#94a3b8"  # slate for Unknown


def weighted_overall(row) -> float:
    """Weighted overall score over the criteria that actually have data.

    Any criterion whose score is NaN (no information — e.g. delivery time for a
    supplier with no delivered orders) is dropped, and the weights of the
    remaining criteria are re-normalised to sum to 1.0. A missing criterion
    therefore neither raises nor lowers the score. If nothing is scoreable the
    result is NaN."""
    avail = [c for c in CRITERIA if pd.notna(row[c])]
    total_w = sum(CRITERIA_WEIGHTS[c] for c in avail)
    if total_w == 0:
        return float("nan")
    return sum(row[c] * CRITERIA_WEIGHTS[c] for c in avail) / total_w


def explain_formula() -> dict:
    """Structured description of the scoring logic, used by the info popovers
    so the explanation and the actual computation can never disagree."""
    return {
        "weights": CRITERIA_WEIGHTS,
        "labels": CRITERIA_LABELS,
        "min_ratings": MIN_RATINGS_FOR_CONFIDENCE,
        "risk_bands": RISK_BANDS,
        "formula": " + ".join(
            f"{CRITERIA_LABELS[c]}×{CRITERIA_WEIGHTS[c]:.2f}" for c in CRITERIA
        ),
    }


# --------------------------------------------------------------------------- #
# Data loading & scoring
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def load_tables() -> dict[str, pd.DataFrame]:
    """Load the four CSV tables. Cached so the CSVs are read once per process.
    Admin edits clear this cache (``load_tables.clear()``) so changes show up."""
    categories = pd.read_csv(DATA_DIR / "categories.csv")
    suppliers = pd.read_csv(DATA_DIR / "suppliers.csv")
    orders = pd.read_csv(DATA_DIR / "orders.csv")
    ratings = pd.read_csv(DATA_DIR / "ratings.csv")
    orders["order_date"] = pd.to_datetime(orders["order_date"], errors="coerce")
    if "delivery_date" in orders.columns:
        orders["delivery_date"] = pd.to_datetime(orders["delivery_date"], errors="coerce")
        orders["delivery_days"] = (orders["delivery_date"] - orders["order_date"]).dt.days
    else:
        orders["delivery_date"] = pd.NaT
        orders["delivery_days"] = pd.NA
    # "Special circumstance" flag: an order where a high price is justified (e.g.
    # the only supplier able to deliver). Such orders are EXCLUDED from the price
    # score so they don't unfairly drag it down. Coerce to a real bool; default
    # to False when the column is absent or blank.
    if "special_circumstance" in orders.columns:
        orders["special_circumstance"] = (
            orders["special_circumstance"]
            .map({True: True, False: False, "True": True, "False": False,
                  "true": True, "false": False, 1: True, 0: False})
            .fillna(False)
            .astype(bool)
        )
    else:
        orders["special_circumstance"] = False
    return {
        "categories": categories,
        "suppliers": suppliers,
        "orders": orders,
        "ratings": ratings,
    }


@st.cache_data(show_spinner=False)
def build_scoreboard() -> pd.DataFrame:
    """One scored row per supplier: weighted criterion averages, overall score,
    risk level, order stats and a data-confidence flag."""
    t = load_tables()
    suppliers, categories = t["suppliers"], t["categories"]
    orders, ratings = t["orders"], t["ratings"]

    # Quality & communication remain averaged 1–5 ratings.
    per = ratings.groupby("supplier_id")[list(RATING_CRITERIA)].mean().reset_index()

    # Rating counts (confidence context).
    per["num_ratings"] = (
        ratings.groupby("supplier_id").size().reindex(per["supplier_id"]).values
    )

    board = suppliers.merge(per, on="supplier_id", how="left")
    board = board.merge(
        categories[["category_id", "category_name"]], on="category_id", how="left"
    )

    # Order stats (spend, order count, last order, delivery metric). total_spend
    # and num_orders count ALL orders; the price metric is handled separately
    # below because special-circumstance orders are excluded from it.
    ostats = (
        orders.groupby("supplier_id")
        .agg(
            num_orders=("order_id", "count"),
            total_spend=("amount_eur", "sum"),
            last_order=("order_date", "max"),
            avg_delivery_days=("delivery_days", "mean"),
            num_special_orders=("special_circumstance", "sum"),
        )
        .reset_index()
    )
    board = board.merge(ostats, on="supplier_id", how="left")

    # Average price for scoring uses NON-special orders only. A special order (a
    # justified high price) neither raises nor lowers the price score.
    normal_orders = orders[~orders["special_circumstance"]]
    avg_price = (
        normal_orders.groupby("supplier_id")["amount_eur"]
        .mean().rename("avg_price_eur").reset_index()
    )
    board = board.merge(avg_price, on="supplier_id", how="left")

    board["num_ratings"] = board["num_ratings"].fillna(0).astype(int)
    board["num_orders"] = board["num_orders"].fillna(0).astype(int)
    board["num_special_orders"] = board["num_special_orders"].fillna(0).astype(int)
    board["has_special_orders"] = board["num_special_orders"] > 0
    board["total_spend"] = board["total_spend"].fillna(0.0)

    # --- Measured → score conversions -------------------------------------- #
    # Flag suppliers with no delivered orders (hence no measurable delivery time).
    board["missing_delivery_data"] = board["avg_delivery_days"].isna()

    # Delivery: fewer avg days = higher score (fixed linear band). Suppliers with
    # no delivered orders have NO delivery history, so we have no information to
    # score — delivery stays NaN and is *excluded* from the overall score (the
    # remaining weights are re-normalised below). The gap is surfaced in the
    # drilldown via missing_delivery_data / has_missing_data.
    board["delivery_time"] = board["avg_delivery_days"].apply(
        lambda d: float("nan") if pd.isna(d) else delivery_days_to_score(d)
    )

    # Price: cheaper avg order = higher score, scaled PER CATEGORY. Anchors are
    # the cheapest/priciest supplier *within the same category*, so suppliers only
    # compete on price against peers selling comparable goods — a logistics
    # supplier's high price never drags down an electronics supplier and vice
    # versa. Suppliers with no non-special orders (hence no avg_price_eur) get a
    # NaN price score, which weighted_overall then excludes and re-normalises.
    def _price_for_category(group: pd.DataFrame) -> pd.Series:
        valid = group["avg_price_eur"].dropna()
        if len(valid) < 2:
            # 0 or 1 priced supplier in the category → no meaningful spread.
            # A lone priced supplier is "neutral" (3.0); an empty group stays NaN.
            return group["avg_price_eur"].apply(
                lambda v: float("nan") if pd.isna(v) else 3.0
            )
        cheap, pricey = valid.min(), valid.max()
        return group["avg_price_eur"].apply(
            lambda v: _linear_score(v, best=cheap, worst=pricey)
        )

    board["price"] = (
        board.groupby("category_name", group_keys=False).apply(_price_for_category)
    )

    # Weighted overall score (delivery & price now from measured metrics).
    # Criteria with no data (e.g. delivery time for a supplier with no delivered
    # orders) are NaN and get *excluded*: we sum only the available criteria and
    # re-normalise their weights so they still add up to 1.0. This way a missing
    # criterion neither helps nor hurts the score — it simply doesn't count.
    board["overall_score"] = board.apply(weighted_overall, axis=1)

    for col in list(CRITERIA) + ["overall_score", "avg_delivery_days", "avg_price_eur"]:
        board[col] = board[col].round(2)

    board["risk_level"] = board["overall_score"].apply(risk_level)
    board["low_confidence"] = board["num_ratings"] < MIN_RATINGS_FOR_CONFIDENCE
    board["has_missing_data"] = (
        board["overall_score"].isna()
        | board["contact_email"].isna()
        | (board["num_ratings"] == 0)
        | board["missing_delivery_data"]
    )
    return board


# Columns computed at load time — never persisted back to the CSV.
_DERIVED_COLS = {"delivery_days"}


def save_table(name: str, df: pd.DataFrame) -> None:
    """Persist a table back to its CSV and clear the caches so the change is
    picked up on the next rerun. ``name`` is one of the load_tables keys.
    Derived columns (e.g. delivery_days) are stripped so they don't leak into
    the CSV and get re-derived on the next load."""
    out = df.drop(columns=[c for c in _DERIVED_COLS if c in df.columns])
    out.to_csv(DATA_DIR / f"{name}.csv", index=False)
    load_tables.clear()
    build_scoreboard.clear()


def next_id(df: pd.DataFrame, col: str) -> int:
    return int(df[col].max()) + 1 if len(df) else 1


# --------------------------------------------------------------------------- #
# Fuzzy search
# --------------------------------------------------------------------------- #
def _normalize(s: str) -> str:
    return "".join(ch for ch in str(s).lower().strip() if ch.isalnum() or ch == " ")


@dataclass
class SearchHit:
    supplier_name: str
    score: float  # 0..1 match strength


def fuzzy_search(query: str, names: list[str], limit: int = 8) -> list[SearchHit]:
    """Typo-tolerant supplier search.

    Combines three signals so misspellings and partial names still match:
      1. substring match (highest — "micro" -> "Shenzhen MicroParts")
      2. token/prefix match on any word
      3. difflib similarity ratio (handles transpositions/typos)
    """
    q = _normalize(query)
    if not q:
        return []
    hits: list[SearchHit] = []
    for name in names:
        n = _normalize(name)
        if not n:
            continue
        if q in n:
            # Earlier match = stronger; exact start is best.
            score = 0.9 + 0.1 * (1 - n.index(q) / max(len(n), 1))
        elif any(tok.startswith(q) or q in tok for tok in n.split()):
            score = 0.75
        else:
            score = difflib.SequenceMatcher(None, q, n).ratio()
        if score >= 0.34:
            hits.append(SearchHit(name, round(score, 3)))
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:limit]


def suggest_names(query: str, names: list[str], limit: int = 5) -> list[str]:
    """Autocomplete suggestions for the search box."""
    return [h.supplier_name for h in fuzzy_search(query, names, limit=limit)]


# --------------------------------------------------------------------------- #
# Filtering (shared by Scorecards + Analytics so filters behave identically)
# --------------------------------------------------------------------------- #
def apply_filters(board: pd.DataFrame, f: dict) -> pd.DataFrame:
    """Apply a dict of filters to the scoreboard. Missing keys are ignored."""
    v = board.copy()
    if f.get("search"):
        keep = {h.supplier_name for h in fuzzy_search(f["search"], v["supplier_name"].tolist(), limit=len(v))}
        v = v[v["supplier_name"].isin(keep)]
    if f.get("countries"):
        v = v[v["country"].isin(f["countries"])]
    if f.get("categories"):
        v = v[v["category_name"].isin(f["categories"])]
    if f.get("risk_levels"):
        v = v[v["risk_level"].isin(f["risk_levels"])]
    if f.get("score_range"):
        lo, hi = f["score_range"]
        v = v[(v["overall_score"] >= lo) & (v["overall_score"] <= hi)]
    if f.get("spend_range"):
        lo, hi = f["spend_range"]
        v = v[(v["total_spend"] >= lo) & (v["total_spend"] <= hi)]
    if f.get("only_missing"):
        v = v[v["has_missing_data"]]
    if f.get("only_low_confidence"):
        v = v[v["low_confidence"]]
    if f.get("only_high_confidence"):
        v = v[~v["low_confidence"]]
    if f.get("threshold") is not None and f.get("only_underperformers"):
        v = v[v["overall_score"] < f["threshold"]]
    if f.get("threshold") is not None and f.get("only_above_threshold"):
        v = v[v["overall_score"] >= f["threshold"]]
    return v


# --------------------------------------------------------------------------- #
# Data-quality checks (Admin mode)
# --------------------------------------------------------------------------- #
def run_data_checks() -> list[dict]:
    """Scan the raw tables for integrity problems. Returns a list of findings;
    each finding is a dict the Admin page renders into a card."""
    t = load_tables()
    suppliers, categories = t["suppliers"], t["categories"]
    orders, ratings = t["orders"], t["ratings"]
    findings: list[dict] = []

    # Missing contact emails.
    miss_email = suppliers[suppliers["contact_email"].isna()]
    findings.append({
        "id": "missing_email",
        "title": "Missing contact emails",
        "count": len(miss_email),
        "severity": "warning" if len(miss_email) else "ok",
        "detail": ", ".join(miss_email["supplier_name"].head(10)) or "None",
    })

    # Duplicate supplier names.
    dup = suppliers[suppliers["supplier_name"].duplicated(keep=False)]
    findings.append({
        "id": "duplicate_names",
        "title": "Duplicate supplier names",
        "count": len(dup),
        "severity": "error" if len(dup) else "ok",
        "detail": ", ".join(sorted(dup["supplier_name"].unique())) or "None",
    })

    # Suppliers with no ratings at all.
    no_ratings = set(suppliers["supplier_id"]) - set(ratings["supplier_id"])
    findings.append({
        "id": "no_ratings",
        "title": "Suppliers with no ratings",
        "count": len(no_ratings),
        "severity": "warning" if no_ratings else "ok",
        "detail": ", ".join(
            suppliers[suppliers["supplier_id"].isin(no_ratings)]["supplier_name"].head(10)
        ) or "None",
    })

    # Broken references: orders/ratings pointing at unknown suppliers.
    orphan_orders = set(orders["supplier_id"]) - set(suppliers["supplier_id"])
    findings.append({
        "id": "orphan_orders",
        "title": "Orders referencing unknown suppliers",
        "count": len(orphan_orders),
        "severity": "error" if orphan_orders else "ok",
        "detail": ", ".join(map(str, sorted(orphan_orders))) or "None",
    })

    # Suppliers pointing at an unknown category.
    bad_cat = suppliers[~suppliers["category_id"].isin(categories["category_id"])]
    findings.append({
        "id": "bad_category",
        "title": "Suppliers with invalid category",
        "count": len(bad_cat),
        "severity": "error" if len(bad_cat) else "ok",
        "detail": ", ".join(bad_cat["supplier_name"].head(10)) or "None",
    })

    # Broken references: ratings pointing at unknown suppliers.
    orphan_ratings = set(ratings["supplier_id"]) - set(suppliers["supplier_id"])
    findings.append({
        "id": "orphan_ratings",
        "title": "Ratings referencing unknown suppliers",
        "count": len(orphan_ratings),
        "severity": "error" if orphan_ratings else "ok",
        "detail": ", ".join(map(str, sorted(orphan_ratings))) or "None",
    })

    # Ratings whose order_id doesn't exist in the orders table.
    ratings_bad_order = ratings[~ratings["order_id"].isin(orders["order_id"])]
    findings.append({
        "id": "ratings_bad_order",
        "title": "Ratings referencing unknown orders",
        "count": len(ratings_bad_order),
        "severity": "error" if len(ratings_bad_order) else "ok",
        "detail": ", ".join(map(str, ratings_bad_order["rating_id"].head(10))) or "None",
    })

    # Out-of-range ratings (not 1..5). Only the criteria actually sourced from
    # ratings.csv are scored now (quality, communication) — delivery_time and
    # price are derived from measured order data, so we don't validate those
    # (legacy) columns here.
    bad_rating_mask = pd.Series(False, index=ratings.index)
    for c in sorted(RATING_CRITERIA):
        if c in ratings:
            bad_rating_mask |= ~ratings[c].between(1, 5)
    findings.append({
        "id": "bad_ratings",
        "title": "Quality/communication ratings outside the 1–5 range",
        "count": int(bad_rating_mask.sum()),
        "severity": "error" if bad_rating_mask.any() else "ok",
        "detail": ", ".join(map(str, ratings[bad_rating_mask]["rating_id"].head(10))) or "None",
    })

    # Orders with a missing order date (can't be placed on the timeline / trend).
    miss_order_date = orders[orders["order_date"].isna()]
    findings.append({
        "id": "missing_order_date",
        "title": "Orders with no order date",
        "count": len(miss_order_date),
        "severity": "error" if len(miss_order_date) else "ok",
        "detail": ", ".join(map(str, miss_order_date["order_id"].head(10))) or "None",
    })

    # Orders with a non-positive amount (0 or negative € makes no business sense
    # and would distort the price scoring / spend totals).
    bad_amount = orders[~(orders["amount_eur"] > 0)]
    findings.append({
        "id": "bad_amount",
        "title": "Orders with zero or negative amount",
        "count": len(bad_amount),
        "severity": "error" if len(bad_amount) else "ok",
        "detail": ", ".join(map(str, bad_amount["order_id"].head(10))) or "None",
    })

    # Delivery date earlier than the order date (impossible — negative lead time).
    if "delivery_days" in orders:
        neg_lead = orders[orders["delivery_days"] < 0]
        findings.append({
            "id": "negative_lead_time",
            "title": "Orders delivered before they were ordered",
            "count": len(neg_lead),
            "severity": "error" if len(neg_lead) else "ok",
            "detail": ", ".join(map(str, neg_lead["order_id"].head(10))) or "None",
        })

    # Unfinished deliveries: orders still open (cancelled / in transit) with no
    # completed delivery. Informational — a normal business state, not an error,
    # but worth surfacing (mirrors the "Unfinished deliveries" KPI on the home
    # page and the missing_delivery_data flag on the scoreboard).
    unfinished = orders[orders["delivery_date"].isna()]
    findings.append({
        "id": "unfinished_deliveries",
        "title": "Orders with no delivery yet (cancelled / in transit)",
        "count": len(unfinished),
        "severity": "info" if len(unfinished) else "ok",
        "detail": ", ".join(map(str, unfinished["order_id"].head(10))) or "None",
    })

    # Special-circumstance orders: flagged as a justified high price (e.g. only
    # supplier able to deliver). Excluded from the price score — informational.
    if "special_circumstance" in orders.columns:
        special = orders[orders["special_circumstance"]]
        findings.append({
            "id": "special_orders",
            "title": "Special-circumstance orders (excluded from price score)",
            "count": len(special),
            "severity": "info" if len(special) else "ok",
            "detail": ", ".join(map(str, special["order_id"].head(10))) or "None",
        })

    # Low-confidence suppliers: fewer than MIN_RATINGS_FOR_CONFIDENCE rated
    # orders. Counted per supplier (reindexed over all suppliers, so a supplier
    # with zero ratings counts as 0) — this matches the `low_confidence` flag in
    # build_scoreboard and the "Confidence" column shown on the Scorecards page,
    # so the Admin count can never disagree with what the user sees there.
    rating_counts = (
        ratings.groupby("supplier_id").size()
        .reindex(suppliers["supplier_id"], fill_value=0)
    )
    low_conf_ids = rating_counts[rating_counts < MIN_RATINGS_FOR_CONFIDENCE].index
    findings.append({
        "id": "low_confidence",
        "title": f"Low-confidence suppliers (< {MIN_RATINGS_FOR_CONFIDENCE} rated orders)",
        "count": len(low_conf_ids),
        "severity": "info" if len(low_conf_ids) else "ok",
        "detail": ", ".join(
            suppliers[suppliers["supplier_id"].isin(low_conf_ids)]["supplier_name"].head(10)
        ) or "None",
    })

    return findings
