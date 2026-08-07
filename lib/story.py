"""
Editorial story components — the hero and the "story stats" strip.

These replace the old gradient hero and the boxed KPI cards. They are rendered
as themed HTML through ``st.markdown`` (no iframe, no JS): they inherit the
editorial stylesheet in ``lib/theme`` directly, so the type, hairlines and mono
numerals stay identical to the rest of the app. Motion is the restrained CSS
rise handled globally by the theme.

A "story stat" is not a number in a box. It is a small label, a figure, and a
line that states the *so what* — a comparison against the review line, a share
of the book, a direction — so each figure carries meaning on its own.
"""

from __future__ import annotations

import html

import streamlit as st


def render_hero(headline: str, lead: str, kicker: str = "") -> None:
    """A flat editorial hero: a quiet mono kicker, a large grotesk headline that
    states the finding, and a lead line. No gradient, no icon, left-aligned."""
    kicker_html = (
        f'<div class="hero-kicker">{html.escape(kicker)}</div>' if kicker else ""
    )
    st.markdown(
        f"""
        <div class="hero-ed">
            {kicker_html}
            <h1 class="hero-head">{html.escape(headline)}</h1>
            <p class="hero-lead">{html.escape(lead)}</p>
        </div>
        <style>
        .hero-ed {{ border-top: 2px solid var(--rule); padding-top: 18px; margin-bottom: 8px; }}
        .hero-kicker {{ font-family: var(--font-mono); text-transform: uppercase;
            letter-spacing: .14em; font-size: .74rem; color: var(--muted); margin-bottom: 14px; }}
        .hero-head {{ max-width: 20ch; margin: 0 0 14px; }}
        .hero-lead {{ font-family: var(--font-body); font-size: 1.08rem; line-height: 1.55;
            color: var(--ink-2); max-width: 62ch; margin: 0; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _sparkline_svg(values: list[float], width: int = 120, height: int = 30) -> str:
    """A thin ink polyline for a small series. No axes, no fill — a quiet mark
    that shows shape, not precise value. Returns '' for a degenerate series."""
    pts = [float(v) for v in values if v is not None]
    if len(pts) < 2:
        return ""
    lo, hi = min(pts), max(pts)
    span = hi - lo or 1.0
    n = len(pts)
    coords = []
    for i, v in enumerate(pts):
        x = i / (n - 1) * (width - 2) + 1
        # invert y so larger values sit higher
        y = height - 1 - (v - lo) / span * (height - 2)
        coords.append(f"{x:.1f},{y:.1f}")
    return (
        f'<svg class="s-spark" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" fill="none" '
        f'preserveAspectRatio="none" aria-hidden="true">'
        f'<polyline points="{" ".join(coords)}" '
        f'stroke="var(--ink)" stroke-width="1.25" '
        f'stroke-linejoin="round" stroke-linecap="round"/></svg>'
    )


def render_story_stats(items: list[dict]) -> None:
    """Render a hairline-divided row of story stats (no boxes).

    Each item:
        {"label": str, "value": str,
         "delta": str (optional, the 'so what' line),
         "dir": "up"|"down"|None (optional, colours the delta),
         "spark": list[float] (optional, a small inline series)}
    """
    cells = []
    for it in items:
        label = html.escape(str(it.get("label", "")))
        value = html.escape(str(it.get("value", "")))
        delta = it.get("delta", "")
        direction = it.get("dir")
        dir_cls = f" {direction}" if direction in ("up", "down") else ""
        delta_html = (
            f'<div class="s-delta{dir_cls}">{html.escape(str(delta))}</div>'
            if delta else ""
        )
        spark_html = _sparkline_svg(it["spark"]) if it.get("spark") else ""
        cells.append(
            f'<div class="stat">'
            f'<div class="s-label">{label}</div>'
            f'<div class="s-value">{value}</div>'
            f"{delta_html}{spark_html}"
            f"</div>"
        )
    st.markdown(
        f'<div class="stat-grid">{"".join(cells)}</div>',
        unsafe_allow_html=True,
    )
