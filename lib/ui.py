"""
Shared UI: theme injection, reusable components (KPI tiles, risk badges,
score-info popover). Keeps every page visually consistent.
"""

from __future__ import annotations

import streamlit as st

from lib.core import (
    CRITERIA,
    CRITERIA_LABELS,
    CRITERIA_WEIGHTS,
    RISK_BANDS,
    explain_formula,
    risk_color,
)
from lib.theme import APP_CSS

# --------------------------------------------------------------------------- #
# Reusable components.
#
# Small helpers each page calls so the look stays identical everywhere: the
# theme injector, KPI tile rows, the coloured risk badge, the breadcrumb, and
# the "how is this score calculated?" popover.
# --------------------------------------------------------------------------- #
def inject_theme() -> None:
    """Inject the global stylesheet. Call once, early, on every page."""
    st.markdown(f"<style>{APP_CSS}</style>", unsafe_allow_html=True)


def kpi_row(items: list[dict]) -> None:
    """Render a responsive row of KPI tiles.
    items: [{"label":..., "value":..., "sub":...(optional)}]"""
    cells = "".join(
        f'<div class="kpi"><div class="k-label">{i["label"]}</div>'
        f'<div class="k-value">{i["value"]}</div>'
        f'<div class="k-sub">{i.get("sub","")}</div></div>'
        for i in items
    )
    st.markdown(f'<div class="kpi-grid">{cells}</div>', unsafe_allow_html=True)


def _tag(text: str, color: str) -> str:
    """A shadcn-style badge: soft tinted background, matching border, coloured
    text. The semantic colour carries the meaning; the tint keeps it quiet."""
    return (
        f'<span class="badge" style="color:{color};background:{color}14;'
        f'border-color:{color}33;">{text}</span>'
    )


def risk_badge_html(level: str, prefix: str = "") -> str:
    """Risk tag, colour-coded by level. `prefix` (e.g. "Risk:") spells out the
    label where just the level word would be ambiguous."""
    text = f"{prefix} {level}".strip()
    return _tag(text, risk_color(level))


def confidence_badge_html(low_confidence: bool, num_ratings: int | None = None) -> str:
    """Confidence tag: amber "Confidence: Low" when a supplier has too few
    ratings to trust the score, green "Confidence: OK" otherwise."""
    if low_confidence:
        color = "#b07400"  # amber
        text = "Confidence: Low"
        if num_ratings is not None:
            text += f" ({num_ratings} rating{'s' if num_ratings != 1 else ''})"
    else:
        color = "#2f7d55"  # green
        text = "Confidence: OK"
    return _tag(text, color)


def special_badge_html(num_special: int) -> str:
    """Neutral ink tag flagging that a supplier stepped in on special-circumstance
    orders (e.g. the only one able to deliver). Their justified high prices are
    excluded from the price score, so this explains a low price score. Kept ink,
    not a second accent colour, to stay within the semantic-colour discipline."""
    label = f"Special circumstance x{num_special}" if num_special > 1 else "Special circumstance"
    return _tag(label, "#1a1a1a")


def breadcrumb(*parts: str) -> None:
    st.markdown('<div class="crumb">' + " / ".join(parts) + "</div>", unsafe_allow_html=True)




def score_info_popover(key: str = "") -> None:
    """The '(i) how is this score calculated?' popover — full transparency."""
    info = explain_formula()
    with st.popover("How is this score calculated?", use_container_width=False):
        from lib.core import DELIVERY_FAST_DAYS, DELIVERY_SLOW_DAYS

        from lib.core import CANCEL_WEIGHT

        st.markdown("#### Overall score formula")
        st.markdown(
            "The overall score is a **base score** (a weighted average of four "
            "criteria, computed from *delivered* orders only) blended with a "
            "**reliability score** that penalises cancellations:"
        )
        st.latex(
            rf"\text{{Overall}} = {1 - CANCEL_WEIGHT:.2f}\cdot\text{{Base}}"
            rf" + {CANCEL_WEIGHT:.2f}\cdot\text{{Reliability}}"
        )
        st.markdown("**Base — four criteria (delivered orders only), 1–5 scale:**")
        st.markdown(
            f"- **Delivery Time** — from the *measured* average days between "
            f"order and delivery: ≤{DELIVERY_FAST_DAYS:.0f} days → 5.0, "
            f"≥{DELIVERY_SLOW_DAYS:.0f} days → 1.0 (linear).\n"
            "- **Price** — from the *measured* average order value in €, scaled "
            "against category peers (cheapest → 5.0, priciest → 1.0).\n"
            "- **Quality** — average of the supplier's quality ratings (1–5).\n"
            "- **Communication** — average of its communication ratings (1–5)."
        )
        st.latex(
            r"\text{Base} = "
            + " + ".join(
                rf"{CRITERIA_WEIGHTS[c]:.2f}\cdot\text{{{CRITERIA_LABELS[c]}}}"
                for c in CRITERIA
            )
        )
        st.markdown("**Base weighting**")
        for c in CRITERIA:
            st.markdown(f"- {CRITERIA_LABELS[c]}: **{CRITERIA_WEIGHTS[c]*100:.0f}%**")
        st.markdown(
            f"**Reliability ({CANCEL_WEIGHT*100:.0f}%)** — penalises cancellations "
            "*exponentially*: 0% cancelled → 5.0, and the score falls faster the "
            "more a supplier cancels (rate = cancelled ÷ (cancelled + delivered))."
        )
        st.markdown("**Risk bands**")
        for label, lo, hi, color in RISK_BANDS:
            hi_disp = "5.0" if hi > 5 else f"{hi:.1f}"
            st.markdown(
                f'- {risk_badge_html(label)} &nbsp; score {lo:.1f} – {hi_disp}',
                unsafe_allow_html=True,
            )
        st.caption(
            f"Suppliers with fewer than {info['min_ratings']} rated orders are "
            "marked **low confidence** — the score is shown but should be read "
            "with caution."
        )
