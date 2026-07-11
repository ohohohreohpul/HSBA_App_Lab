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
    "delivery_time": 0.30,
    "quality": 0.35,
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

    # Order stats (spend, order count, last order, + measured metrics).
    ostats = (
        orders.groupby("supplier_id")
        .agg(
            num_orders=("order_id", "count"),
            total_spend=("amount_eur", "sum"),
            last_order=("order_date", "max"),
            avg_delivery_days=("delivery_days", "mean"),
            avg_price_eur=("amount_eur", "mean"),
        )
        .reset_index()
    )
    board = board.merge(ostats, on="supplier_id", how="left")

    board["num_ratings"] = board["num_ratings"].fillna(0).astype(int)
    board["num_orders"] = board["num_orders"].fillna(0).astype(int)
    board["total_spend"] = board["total_spend"].fillna(0.0)

    # --- Measured → score conversions -------------------------------------- #
    # Flag suppliers with no delivered orders (hence no measurable delivery time).
    board["missing_delivery_data"] = board["avg_delivery_days"].isna()

    # Delivery: fewer avg days = higher score (fixed linear band). Suppliers with
    # no delivered orders get a neutral 3.0 so the overall score still computes;
    # they're flagged via missing_delivery_data / has_missing_data.
    board["delivery_time"] = board["avg_delivery_days"].apply(
        lambda d: 3.0 if pd.isna(d) else delivery_days_to_score(d)
    )

    # Price: cheaper avg order = higher score, scaled across the observed range
    # of supplier average prices (cheapest supplier → 5, priciest → 1).
    valid_price = board["avg_price_eur"].dropna()
    if len(valid_price):
        cheap, pricey = valid_price.min(), valid_price.max()
        board["price"] = board["avg_price_eur"].apply(
            lambda v: _linear_score(v, best=cheap, worst=pricey)
        )
    else:
        board["price"] = float("nan")

    # Weighted overall score (delivery & price now from measured metrics).
    board["overall_score"] = sum(board[c] * CRITERIA_WEIGHTS[c] for c in CRITERIA)

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


def save_table(name: str, df: pd.DataFrame) -> None:
    """Persist a table back to its CSV and clear the caches so the change is
    picked up on the next rerun. ``name`` is one of the load_tables keys."""
    df.to_csv(DATA_DIR / f"{name}.csv", index=False)
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
    if f.get("only_missing"):
        v = v[v["has_missing_data"]]
    if f.get("only_low_confidence"):
        v = v[v["low_confidence"]]
    if f.get("threshold") is not None and f.get("only_underperformers"):
        v = v[v["overall_score"] < f["threshold"]]
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

    # Out-of-range ratings (not 1..5).
    bad_rating_mask = pd.Series(False, index=ratings.index)
    for c in CRITERIA:
        if c in ratings:
            bad_rating_mask |= ~ratings[c].between(1, 5)
    findings.append({
        "id": "bad_ratings",
        "title": "Ratings outside the 1–5 range",
        "count": int(bad_rating_mask.sum()),
        "severity": "error" if bad_rating_mask.any() else "ok",
        "detail": ", ".join(map(str, ratings[bad_rating_mask]["rating_id"].head(10))) or "None",
    })

    # Low-confidence suppliers (few ratings).
    counts = ratings.groupby("supplier_id").size()
    low_conf = counts[counts < MIN_RATINGS_FOR_CONFIDENCE]
    findings.append({
        "id": "low_confidence",
        "title": f"Suppliers with < {MIN_RATINGS_FOR_CONFIDENCE} ratings (low confidence)",
        "count": len(low_conf),
        "severity": "info" if len(low_conf) else "ok",
        "detail": ", ".join(
            suppliers[suppliers["supplier_id"].isin(low_conf.index)]["supplier_name"].head(10)
        ) or "None",
    })

    return findings
