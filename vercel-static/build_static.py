"""
Freeze the scored dataset to a static JSON bundle for the Vercel static build.

Run from the repo root:  python vercel-static/build_static.py

This imports the *real* scoring logic from ``lib.core`` (same weights, risk
bands and reliability model the Streamlit app uses), computes one scored row per
supplier plus the per-supplier orders and quarterly trend, and the portfolio
aggregates the Analytics charts need — then writes it all to
``vercel-static/data.json``. The static site reads only that file, so the
deployed page needs no Python and no server.

The data is a *snapshot*: re-run this whenever the CSVs change.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd

# Make the repo root importable no matter where this script is invoked from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.core import (
    CANCEL_WEIGHT,
    CRITERIA,
    CRITERIA_LABELS,
    CRITERIA_WEIGHTS,
    DEFAULT_THRESHOLD,
    MIN_RATINGS_FOR_CONFIDENCE,
    RISK_BANDS,
    _linear_score,
    build_scoreboard,
    cancel_reliability_score,
    delivery_days_to_score,
    load_tables,
    weighted_overall,
)

OUT = Path(__file__).resolve().parent / "data.json"


def _clean(value):
    """JSON-safe scalar: NaN/NaT → None, numpy types → native, else str fallback."""
    if value is None:
        return None
    if isinstance(value, float):
        return None if math.isnan(value) else round(value, 4)
    if isinstance(value, (int, str, bool)):
        return value
    if pd.isna(value):
        return None
    # numpy scalar
    try:
        return value.item()
    except AttributeError:
        return str(value)


def _supplier_trend(sup_all: pd.DataFrame, category_prices: pd.Series) -> list[dict]:
    """Quarterly average overall score for one supplier, computed exactly like the
    Streamlit Drilldown: delivered-only base (delivery from days, price scaled
    against category peers, quality/comm from ratings) blended with that
    quarter's cancellation reliability."""
    if not sup_all["order_date"].notna().any():
        return []
    g = sup_all.dropna(subset=["order_date"]).copy()
    period = g["order_date"].dt.to_period("Q")
    g["period"] = period.dt.start_time
    g["quarter"] = period.apply(lambda p: f"Q{p.quarter} {p.year}")

    if len(category_prices) >= 2:
        pcheap, ppricey = category_prices.min(), category_prices.max()
    else:
        vals = g.loc[g["status"] == "Delivered", "amount_eur"].dropna()
        pcheap, ppricey = (vals.min(), vals.max()) if len(vals) else (0.0, 0.0)

    delivered = g["status"] == "Delivered"
    g["delivery_time"] = g["delivery_days"].apply(
        lambda d: float("nan") if pd.isna(d) else delivery_days_to_score(d)
    )
    g["price"] = g.apply(
        lambda r: _linear_score(r["amount_eur"], best=pcheap, worst=ppricey)
        if r["status"] == "Delivered" else float("nan"),
        axis=1,
    )
    for c in ("quality", "communication"):
        g.loc[~delivered, c] = float("nan")
    g["base"] = g.apply(weighted_overall, axis=1)

    def _q_overall(gr: pd.DataFrame) -> float:
        base = gr.loc[gr["status"] == "Delivered", "base"].mean()
        n_deliv = int((gr["status"] == "Delivered").sum())
        n_canc = int((gr["status"] == "Cancelled").sum())
        canc = cancel_reliability_score(n_canc, n_deliv)
        if pd.isna(base) and pd.isna(canc):
            return float("nan")
        if pd.isna(base):
            return canc
        if pd.isna(canc):
            return base
        return (1.0 - CANCEL_WEIGHT) * base + CANCEL_WEIGHT * canc

    trend = (
        g.groupby(["period", "quarter"]).apply(_q_overall)
        .rename("overall").reset_index().dropna(subset=["overall"]).sort_values("period")
    )
    return [{"quarter": q, "overall": round(float(o), 2)}
            for q, o in zip(trend["quarter"], trend["overall"])]


def main() -> None:
    board = build_scoreboard()
    tables = load_tables()
    orders, ratings = tables["orders"], tables["ratings"]
    o_r = orders.merge(ratings[["order_id", "quality", "communication"]],
                       on="order_id", how="left")

    # Category price spread (for each supplier's trend, same anchors as the board).
    cat_prices = {
        cat: board.loc[board["category_name"] == cat, "avg_price_eur"].dropna()
        for cat in board["category_name"].dropna().unique()
    }

    suppliers = []
    for _, row in board.iterrows():
        sid = int(row["supplier_id"])
        sup_orders = o_r[o_r["supplier_id"] == sid].copy()
        order_list = [
            {
                "order": _clean(r["order_id"]),
                "ordered": r["order_date"].date().isoformat() if pd.notna(r["order_date"]) else None,
                "delivered": pd.to_datetime(r["delivery_date"]).date().isoformat()
                if pd.notna(r["delivery_date"]) else None,
                "days": _clean(r["delivery_days"]),
                "amount": _clean(r["amount_eur"]),
                "status": _clean(r["status"]),
                "special": bool(r["special_circumstance"]),
                "quality": _clean(r["quality"]),
                "communication": _clean(r["communication"]),
            }
            for _, r in sup_orders.sort_values("order_date").iterrows()
        ]
        suppliers.append({
            "id": sid,
            "name": _clean(row["supplier_name"]),
            "country": _clean(row["country"]),
            "category": _clean(row["category_name"]),
            "email": _clean(row["contact_email"]),
            "overall": _clean(row["overall_score"]),
            "risk": _clean(row["risk_level"]),
            "low_confidence": bool(row["low_confidence"]),
            "delivery_time": _clean(row["delivery_time"]),
            "quality": _clean(row["quality"]),
            "price": _clean(row["price"]),
            "communication": _clean(row["communication"]),
            "reliability": _clean(row["cancel_score"]),
            "num_orders": _clean(row["num_orders"]),
            "num_delivered": _clean(row["num_delivered"]),
            "num_cancelled": _clean(row["num_cancelled"]),
            "num_ratings": _clean(row["num_ratings"]),
            "total_spend": _clean(row["total_spend"]),
            "avg_delivery_days": _clean(row["avg_delivery_days"]),
            "avg_price_eur": _clean(row["avg_price_eur"]),
            "cancel_rate": _clean(row["cancel_rate"]),
            "has_special": bool(row["has_special_orders"]),
            "num_special": _clean(row["num_special_orders"]),
            "missing_delivery": bool(row["missing_delivery_data"]),
            "orders": order_list,
            "trend": _supplier_trend(sup_orders, cat_prices.get(row["category_name"], pd.Series(dtype=float))),
        })

    # Portfolio aggregates for the Analytics charts (exact, precomputed).
    n = len(board)
    avg = float(board["overall_score"].mean())
    dist_counts, dist_edges = _histogram(board["overall_score"].dropna(), 1.0, 5.0, 16)
    risk_counts = {lvl: int((board["risk_level"] == lvl).sum()) for lvl in ("High", "Medium", "Low")}
    country_counts = (board["country"].value_counts().head(12)
                      .rename_axis("country").reset_index(name="count"))
    cat_avg = (board.groupby("category_name")["overall_score"].mean()
               .round(2).rename_axis("category").reset_index(name="avg"))
    # Category × criterion heatmap.
    heat = []
    for cat in sorted(board["category_name"].dropna().unique()):
        sub = board[board["category_name"] == cat]
        for c in CRITERIA:
            heat.append({"category": cat, "criterion": CRITERIA_LABELS[c],
                         "score": _clean(sub[c].mean())})

    meta = {
        "threshold": DEFAULT_THRESHOLD,
        "cancel_weight": CANCEL_WEIGHT,
        "min_ratings_confidence": MIN_RATINGS_FOR_CONFIDENCE,
        "criteria": [{"key": c, "label": CRITERIA_LABELS[c], "weight": CRITERIA_WEIGHTS[c]}
                     for c in CRITERIA],
        "risk_bands": [{"label": lbl, "lo": lo, "hi": hi, "color": color}
                       for lbl, lo, hi, color in RISK_BANDS],
        "totals": {
            "suppliers": n,
            "avg_score": round(avg, 2),
            "high_risk": risk_counts["High"],
            "below_threshold": int((board["overall_score"] < DEFAULT_THRESHOLD).sum()),
            "countries": int(board["country"].nunique()),
            "categories": int(board["category_name"].nunique()),
            "cancelled": int((orders["status"] == "Cancelled").sum()),
            "in_transit": int((orders["status"] == "In Transit").sum()),
            "total_orders": int(len(orders)),
        },
        "score_distribution": {"counts": dist_counts, "edges": [round(e, 3) for e in dist_edges]},
        "risk_counts": risk_counts,
        "country_counts": country_counts.to_dict("records"),
        "category_avg": [{"category": r["category"], "avg": _clean(r["avg"])}
                         for _, r in cat_avg.iterrows()],
        "heatmap": heat,
    }

    OUT.write_text(json.dumps({"meta": meta, "suppliers": suppliers},
                              ensure_ascii=False, separators=(",", ":")))
    kb = OUT.stat().st_size / 1024
    print(f"Wrote {OUT} — {n} suppliers, {kb:.0f} KB")


def _histogram(series: pd.Series, lo: float, hi: float, bins: int):
    """Plain-Python histogram → (counts, edges). Avoids a hard numpy dependency."""
    width = (hi - lo) / bins
    counts = [0] * bins
    for v in series:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
        idx = min(int((v - lo) / width), bins - 1) if v >= lo else 0
        idx = max(0, min(idx, bins - 1))
        counts[idx] += 1
    edges = [round(lo + i * width, 4) for i in range(bins + 1)]
    return counts, edges


if __name__ == "__main__":
    main()
