"""Hand-coded SVG chart builders for the Lodestar report.

Every chart is plain, dependency-free SVG
with pixel positions computed from data, plus a `data-tip` attribute that the
template's shared tooltip script picks up on hover. This
keeps the report a single static file with zero external JS runtime.
"""
from __future__ import annotations

import html as _html

# Theme-aware: these are literal CSS custom-property references, not resolved
# hex values, so every chart recolors itself under the device's light/dark
# preference with no JS -- the host page defines the actual
# --gold/--ink/etc. values, swapped wholesale inside a `prefers-color-scheme`
# media query. This only works because every usage below embeds the constant
# inside a `style="fill:{GOLD}"` attribute (a real CSS declaration); var()
# does not reliably resolve in bare presentation attributes like fill="...".
GOLD = "var(--gold)"
INK = "var(--ink)"
MUTED = "var(--ink-3)"
LINE = "var(--line)"
GRID = "var(--line-2)"


def _esc(text: str) -> str:
    return _html.escape(str(text), quote=True)


def _ticks(lo: float, hi: float, step: float) -> list[float]:
    ticks = []
    value = lo
    while value <= hi + 1e-9:
        ticks.append(round(value, 6))
        value += step
    return ticks


def frontier_chart(
    scales: list[float],
    coherence: list[float],
    relevance: list[float],
    ses: list[float],
    optimal_scale: float,
    *,
    threshold: float | None = 7.0,
    width: int = 760,
    height: int = 430,
) -> str:
    """Coherence (x) vs relevance (y) scatter+line, both axes fixed 0-10."""
    x0, x1, y0, y1 = 70, width - 28, height - 60, 26

    def px(value: float) -> float:
        return x0 + (value / 10) * (x1 - x0)

    def py(value: float) -> float:
        return y0 - (value / 10) * (y0 - y1)

    axis_ticks = _ticks(0, 10, 2)
    grid = "".join(
        f'<line x1="{px(t):.1f}" y1="{y1}" x2="{px(t):.1f}" y2="{y0}" style="stroke:{GRID};stroke-width:1"></line>'
        for t in axis_ticks
    )
    grid += "".join(
        f'<line x1="{x0}" y1="{py(t):.1f}" x2="{x1}" y2="{py(t):.1f}" style="stroke:{GRID};stroke-width:1"></line>'
        for t in axis_ticks[1:-1]
    )
    axes = (
        f'<line x1="{x0}" y1="{y1}" x2="{x0}" y2="{y0}" style="stroke:{LINE};stroke-width:1.3"></line>'
        f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y0}" style="stroke:{LINE};stroke-width:1.3"></line>'
    )
    band = ""
    if threshold is not None and 0 <= threshold <= 10:
        bx = px(threshold)
        band = (
            f'<rect x="{bx:.1f}" y="{y1}" width="{x1 - bx:.1f}" height="{y0 - y1}" style="fill:{GOLD};opacity:.07"></rect>'
            f'<line x1="{bx:.1f}" y1="{y1}" x2="{bx:.1f}" y2="{y0}" style="stroke:{MUTED};stroke-width:1;stroke-dasharray:4 4;opacity:.7"></line>'
            f'<text x="{bx + 5:.1f}" y="{y1 + 15}" style="fill:{MUTED};font-size:11px">coherence &#8805; {threshold:g}</text>'
        )

    points = list(zip(scales, coherence, relevance, ses, strict=True))
    poly = " ".join(f"{px(c):.1f},{py(r):.1f}" for _, c, r, _ in points)
    line = f'<polyline points="{poly}" style="fill:none;stroke:{GOLD};stroke-width:2;stroke-linejoin:round;opacity:.9"></polyline>'

    markers = []
    for scale, coh, rel, se in points:
        cx, cy = px(coh), py(rel)
        is_optimal = scale == optimal_scale
        tip = f"scale {scale:g}{' &#183; optimal' if is_optimal else ''}|coh {coh:.1f}&#8195;rel {rel:.1f}&#8195;SES {se:.2f}"
        if is_optimal:
            markers.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="9" style="fill:none;stroke:{GOLD};stroke-width:2"></circle>')
        markers.append(
            f'<g class="lodestar-point" data-scale="{scale:.4g}" data-tip="{_esc(tip)}" style="cursor:pointer">'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="14" style="fill:transparent"></circle>'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4.4" '
            f'style="fill:{GOLD if is_optimal else INK};opacity:{1 if is_optimal else 0.55}"></circle>'
            f"</g>"
        )

    x_labels = "".join(
        f'<text x="{px(t):.1f}" y="{y0 + 16}" text-anchor="middle" style="fill:{MUTED};font-size:11px">{t:g}</text>'
        for t in axis_ticks
    )
    y_labels = "".join(
        f'<text x="{x0 - 10}" y="{py(t) + 3.5:.1f}" text-anchor="end" style="fill:{MUTED};font-size:11px">{t:g}</text>'
        for t in axis_ticks
    )

    return (
        f'<svg viewBox="0 0 {width} {height}" style="width:100%;height:auto;display:block;font-family:var(--mono)" '
        f'role="img" aria-label="Coherence versus relevance scatter">'
        f"{band}{grid}{axes}{line}{''.join(markers)}{x_labels}{y_labels}"
        f'<text x="{(x0 + x1) / 2:.1f}" y="{height - 14}" text-anchor="middle" style="fill:{INK};font-size:11px;letter-spacing:.08em">COHERENCE</text>'
        f'<text x="22" y="{(y0 + y1) / 2:.1f}" text-anchor="middle" transform="rotate(-90 22 {(y0 + y1) / 2:.1f})" '
        f'style="fill:{INK};font-size:11px;letter-spacing:.08em">RELEVANCE</text>'
        f"</svg>"
    )


def control_chart(
    rel_steered: float,
    rel_control: float,
    ci_lo: float,
    ci_hi: float,
    *,
    width: int = 760,
    height: int = 210,
) -> str:
    """Two horizontal bars (steered vs random control) on a 0-10 relevance axis."""
    x0, x1, y0, y1 = 130, width - 40, height - 40, 20

    def px(value: float) -> float:
        return x0 + (value / 10) * (x1 - x0)

    axis_ticks = _ticks(0, 10, 2)
    grid = "".join(
        f'<line x1="{px(t):.1f}" y1="{y1}" x2="{px(t):.1f}" y2="{y0}" style="stroke:{GRID if t else LINE};stroke-width:{1.3 if not t else 1}"></line>'
        for t in axis_ticks
    )
    axis = f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y0}" style="stroke:{LINE};stroke-width:1.3"></line>'

    steered_w = px(rel_steered) - x0
    ci_lo_x, ci_hi_x = px(ci_lo), px(ci_hi)
    steered_tip = f"Steered &#183; relevance {rel_steered:.1f} (95% CI {ci_lo:.1f}&#8211;{ci_hi:.1f})"
    control_tip = f"Random control &#183; relevance {rel_control:.1f}"
    bars = (
        f'<g data-tip="{_esc(steered_tip)}" style="cursor:pointer">'
        f'<rect x="{x0}" y="41" width="{steered_w:.1f}" height="34" style="fill:{GOLD}"></rect>'
        f"</g>"
        f'<line x1="{ci_lo_x:.1f}" y1="58" x2="{ci_hi_x:.1f}" y2="58" style="stroke:{INK};stroke-width:1.4"></line>'
        f'<line x1="{ci_lo_x:.1f}" y1="52" x2="{ci_lo_x:.1f}" y2="64" style="stroke:{INK};stroke-width:1.4"></line>'
        f'<line x1="{ci_hi_x:.1f}" y1="52" x2="{ci_hi_x:.1f}" y2="64" style="stroke:{INK};stroke-width:1.4"></line>'
        f'<text x="{x0 - 12}" y="62" text-anchor="end" style="fill:{INK};font-size:12px">Steered</text>'
        # Positioned past the CI whisker's right end (ci_hi_x), not the bar's
        # own end -- the whisker can extend past the point estimate, and the
        # label must clear it regardless of which one is further right.
        f'<text x="{ci_hi_x + 10:.1f}" y="62" style="fill:{INK};font-size:13px;font-weight:500">{rel_steered:.1f}</text>'
        f'<g data-tip="{_esc(control_tip)}" style="cursor:pointer">'
        f'<rect x="{x0}" y="111" width="{(px(rel_control) - x0):.1f}" height="34" style="fill:{MUTED};opacity:.55"></rect>'
        f"</g>"
        f'<text x="{x0 - 12}" y="132" text-anchor="end" style="fill:{INK};font-size:12px">Random control</text>'
        f'<text x="{px(rel_control) + 10:.1f}" y="132" style="fill:{MUTED};font-size:13px">{rel_control:.1f}</text>'
    )
    x_labels = "".join(
        f'<text x="{px(t):.1f}" y="{y0 + 18}" text-anchor="middle" style="fill:{MUTED};font-size:11px">{t:g}</text>'
        for t in axis_ticks
    )

    return (
        f'<svg viewBox="0 0 {width} {height}" style="width:100%;height:auto;display:block;font-family:var(--mono)" '
        f'role="img" aria-label="Control gap bar chart">'
        f"{grid}{axis}{bars}{x_labels}"
        f'<text x="{(x0 + x1) / 2:.1f}" y="{height - 4}" text-anchor="middle" style="fill:{MUTED};font-size:11px;letter-spacing:.08em">CONCEPT RELEVANCE</text>'
        f"</svg>"
    )


def human_chart(human: list[float], judge: list[float], *, width: int = 420, height: int = 360) -> str:
    """Judge score (y) vs human score (x) calibration scatter, 0-10 both axes."""
    x0, x1, y0, y1 = 50, width - 18, height - 44, 18

    def px(value: float) -> float:
        return x0 + (value / 10) * (x1 - x0)

    def py(value: float) -> float:
        return y0 - (value / 10) * (y0 - y1)

    axes = (
        f'<line x1="{x0}" y1="{y1}" x2="{x0}" y2="{y0}" style="stroke:{LINE};stroke-width:1.3"></line>'
        f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y0}" style="stroke:{LINE};stroke-width:1.3"></line>'
        f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y1}" style="stroke:{MUTED};stroke-width:1;stroke-dasharray:4 4;opacity:.6"></line>'
    )
    points = "".join(
        f'<circle cx="{px(h):.1f}" cy="{py(j):.1f}" r="3.6" style="fill:{GOLD};opacity:.85" '
        f'data-tip="{_esc(f"human {h:g}&#8195;judge {j:g}")}"></circle>'
        for h, j in zip(human, judge, strict=True)
    )
    ticks = _ticks(0, 10, 5)
    x_labels = "".join(
        f'<text x="{px(t):.1f}" y="{y0 + 16}" text-anchor="middle" style="fill:{MUTED};font-size:10px">{t:g}</text>' for t in ticks
    )
    y_labels = "".join(
        f'<text x="{x0 - 8}" y="{py(t) + 3.5:.1f}" text-anchor="end" style="fill:{MUTED};font-size:10px">{t:g}</text>' for t in ticks
    )

    return (
        f'<svg viewBox="0 0 {width} {height}" style="width:100%;height:auto;display:block;font-family:var(--mono)" '
        f'role="img" aria-label="Judge versus human calibration scatter">'
        f"{axes}{points}{x_labels}{y_labels}"
        f'<text x="{(x0 + x1) / 2:.1f}" y="{height - 8}" text-anchor="middle" style="fill:{INK};font-size:10px;letter-spacing:.06em">HUMAN SCORE</text>'
        f'<text x="14" y="{(y0 + y1) / 2:.1f}" text-anchor="middle" transform="rotate(-90 14 {(y0 + y1) / 2:.1f})" '
        f'style="fill:{INK};font-size:10px;letter-spacing:.06em">JUDGE SCORE</text>'
        f"</svg>"
    )


def normalize_columns(rows: list[list[float]]) -> list[list[float]]:
    """Per-column min-max normalize, so each metric shades on its own scale."""
    columns = list(zip(*rows, strict=True))
    out = []
    for column in columns:
        lo, hi = min(column), max(column)
        span = (hi - lo) or 1.0
        out.append([(v - lo) / span for v in column])
    return [list(row) for row in zip(*out, strict=True)]


def cross_lingual_grid(langs: list[str], metrics: list[str], raw: list[list[float]]) -> str:
    """CSS-grid heatmap (no SVG needed): rows=langs, cols=metrics."""
    shade = normalize_columns(raw)
    header = (
        f'<div style="font-family:var(--mono);font-size:10px;letter-spacing:.06em;color:{MUTED};'
        'text-transform:uppercase;padding:8px 10px">Language</div>'
    )
    header += "".join(
        f'<div style="font-family:var(--mono);font-size:10px;letter-spacing:.06em;color:{MUTED};'
        f'text-transform:uppercase;padding:8px 10px;text-align:center">{_esc(metric)}</div>'
        for metric in metrics
    )
    rows_html = []
    for language, values, opacities in zip(langs, raw, shade, strict=True):
        rows_html.append(
            f'<div style="font-family:var(--mono);font-size:12px;padding:0 10px;display:flex;align-items:center">{_esc(language)}</div>'
        )
        for value, opacity in zip(values, opacities, strict=True):
            rows_html.append(
                '<div class="lodestar-cell" style="position:relative;height:56px;display:flex;align-items:center;'
                'justify-content:center;outline:2px solid transparent;outline-offset:-2px">'
                # Neutral wash, not gold -- gold is reserved for the single
                # optimal/lodestar signal, and a per-cell heatmap value isn't it.
                f'<div style="position:absolute;inset:0;background:{MUTED};opacity:{0.06 + 0.79 * opacity:.2f}"></div>'
                f'<span style="position:relative;font-variant-numeric:tabular-nums">{value:.2f}</span>'
                "</div>"
            )
    return (
        f'<div style="display:grid;grid-template-columns:120px repeat({len(metrics)},1fr);gap:4px;font-size:14px">'
        f"{header}{''.join(rows_html)}</div>"
    )
