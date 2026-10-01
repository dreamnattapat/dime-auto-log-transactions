"""Renders the analytics from analytics.py into a single self-contained
static HTML file — no server, no build step, just open it in a browser.
"""
import html
import json
from datetime import datetime
from pathlib import Path

CSS = """
:root {
    color-scheme: light dark;
    --bg: #f7f7f8; --card: #ffffff; --text: #1a1a1a; --muted: #6b7280;
    --border: #e5e7eb; --green: #16a34a; --red: #dc2626; --accent: #2563eb;
    --series-you: #2a78d6; --series-spy: #eb6834; --baseline: #c3c2b7;
}
@media (prefers-color-scheme: dark) {
    :root {
        --bg: #0f1115; --card: #181b21; --text: #e5e7eb; --muted: #9ca3af;
        --border: #2a2e37; --green: #4ade80; --red: #f87171; --accent: #60a5fa;
        --series-you: #3987e5; --series-spy: #d95926; --baseline: #454a55;
    }
}
* { box-sizing: border-box; }
body {
    margin: 0; padding: 2rem 1.25rem 4rem; background: var(--bg); color: var(--text);
    font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.wrap { max-width: 1000px; margin: 0 auto; }
h1 { font-size: 1.4rem; margin: 0 0 0.15rem; }
.subtitle { color: var(--muted); font-size: 0.85rem; margin-bottom: 1.75rem; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 0.75rem; margin-bottom: 2rem; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 0.9rem 1rem; }
.card .label { color: var(--muted); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.03em; }
.card .value { font-size: 1.4rem; font-weight: 600; margin-top: 0.2rem; font-variant-numeric: tabular-nums; }
.warn { background: color-mix(in srgb, var(--red) 12%, var(--card)); border: 1px solid var(--red); border-radius: 8px; padding: 0.6rem 0.9rem; margin-bottom: 1.5rem; font-size: 0.85rem; }
section { margin-bottom: 2.25rem; }
h2 { font-size: 1rem; margin: 0 0 0.75rem; }
table { width: 100%; border-collapse: collapse; background: var(--card); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; font-size: 0.85rem; }
th, td { padding: 0.55rem 0.75rem; text-align: right; border-bottom: 1px solid var(--border); font-variant-numeric: tabular-nums; }
th:first-child, td:first-child { text-align: left; }
th { color: var(--muted); font-weight: 500; cursor: pointer; user-select: none; white-space: nowrap; }
th:hover { color: var(--text); }
tr:last-child td { border-bottom: none; }
.pos { color: var(--green); } .neg { color: var(--red); }
.flag { color: var(--red); font-size: 0.75rem; }
.scroll { overflow-x: auto; }
.table-wrap { max-height: 480px; overflow-y: auto; border-radius: 10px; }
.table-wrap table { border-radius: 0; }
.note { color: var(--muted); font-size: 0.8rem; margin-top: -1.25rem; }
.chart-card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 1rem 1rem 0.5rem; margin-top: 1.25rem; position: relative; }
.chart-head { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: baseline; gap: 0.5rem 1.5rem; margin-bottom: 0.5rem; }
.chart-head h3 { font-size: 0.9rem; margin: 0; }
.legend { display: flex; gap: 1.25rem; font-size: 0.8rem; color: var(--muted); }
.legend span { display: inline-flex; align-items: center; gap: 0.4rem; }
.key { display: inline-block; width: 14px; height: 2px; border-radius: 1px; }
.chart svg { display: block; width: 100%; overflow: visible; }
.chart svg:focus { outline: none; }
.chart svg:focus-visible { outline: 2px solid var(--accent); outline-offset: 4px; border-radius: 4px; }
.chart .grid { stroke: var(--border); stroke-width: 1; }
.chart .zero { stroke: var(--baseline); stroke-width: 1; }
.chart .tick { fill: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; }
.chart .end-label { fill: var(--text); font-size: 12px; font-weight: 600; }
.chart .end-name { fill: var(--muted); font-size: 11px; }
.chart .line { fill: none; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
.chart .dot { stroke: var(--card); stroke-width: 2; }
.chart .cross { stroke: var(--muted); stroke-width: 1; }
.tip { position: absolute; pointer-events: none; background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 0.5rem 0.65rem; font-size: 0.8rem; box-shadow: 0 4px 16px rgba(0,0,0,0.12); min-width: 170px; }
.tip .tip-date { color: var(--muted); margin-bottom: 0.3rem; }
.tip .tip-row { display: flex; align-items: center; gap: 0.45rem; margin-top: 0.15rem; }
.tip .tip-row strong { font-variant-numeric: tabular-nums; }
.tip .tip-row .name { color: var(--muted); margin-left: auto; padding-left: 0.75rem; }
.tip .tip-diff { border-top: 1px solid var(--border); margin-top: 0.4rem; padding-top: 0.35rem; color: var(--muted); }
details.table-view { margin-top: 0.5rem; font-size: 0.8rem; }
details.table-view summary { color: var(--muted); cursor: pointer; padding: 0.25rem 0 0.5rem; }
details.table-view table { margin-bottom: 0.5rem; }
.card .sub { color: var(--muted); font-size: 0.8rem; margin-top: 0.1rem; font-variant-numeric: tabular-nums; }
"""

JS = """
function sortTable(table, col, numeric) {
    const tbody = table.tBodies[0];
    const rows = Array.from(tbody.rows);
    const dir = table.dataset.sortCol == col && table.dataset.sortDir == 'asc' ? 'desc' : 'asc';
    table.dataset.sortCol = col; table.dataset.sortDir = dir;
    rows.sort((a, b) => {
        let x = a.cells[col].dataset.sort ?? a.cells[col].innerText;
        let y = b.cells[col].dataset.sort ?? b.cells[col].innerText;
        if (numeric) { x = parseFloat(x) || 0; y = parseFloat(y) || 0; }
        if (x < y) return dir === 'asc' ? -1 : 1;
        if (x > y) return dir === 'asc' ? 1 : -1;
        return 0;
    });
    rows.forEach(r => tbody.appendChild(r));
}
document.querySelectorAll('table.sortable').forEach(table => {
    table.tHead.querySelectorAll('th').forEach((th, i) => {
        th.addEventListener('click', () => sortTable(table, i, th.dataset.numeric === '1'));
    });
});
"""


def _fmt_thb(value: float | None) -> str:
    if value is None:
        return "–"
    return f"{value:,.2f}"


def _pnl_span(value: float | None) -> str:
    if value is None:
        return "–"
    cls = "pos" if value > 0 else "neg" if value < 0 else ""
    sign = "+" if value > 0 else ""
    return f'<span class="{cls}" data-sort="{value}">{sign}{value:,.2f}</span>'


def _esc(value) -> str:
    return html.escape(str(value)) if value is not None else ""


def _summary_cards(summary: dict) -> str:
    pnl = summary["total_realized_pnl_thb"]
    pnl_cls = "pos" if pnl > 0 else "neg" if pnl < 0 else ""
    win_rate = summary["win_rate_pct"]
    win_rate_str = f"{win_rate:.0f}%" if win_rate is not None else "–"
    excluded = summary["win_rate_excluded"]
    win_rate_label = f"Win Rate (excl. {', '.join(excluded)})" if excluded else "Win Rate"
    return f"""
    <div class="cards">
        <div class="card"><div class="label">Realized P&amp;L</div>
            <div class="value {pnl_cls}">{'+' if pnl > 0 else ''}฿{pnl:,.0f}</div></div>
        <div class="card"><div class="label">{_esc(win_rate_label)}</div>
            <div class="value">{win_rate_str}</div></div>
        <div class="card"><div class="label">Closed Trades</div>
            <div class="value">{summary['total_trades']}</div></div>
        <div class="card"><div class="label">Open Positions</div>
            <div class="value">{summary['open_position_count']}</div></div>
    </div>
    """


def _signed_thb(value: float) -> str:
    cls = "pos" if value > 0 else "neg" if value < 0 else ""
    return f'<span class="{cls}">{"+" if value > 0 else "−" if value < 0 else ""}฿{abs(value):,.0f}</span>'


def _fmt_pct(value: float | None) -> str:
    return f"{value:+.1f}%" if value is not None else "–"


CHART_JS = r"""
(function () {
    const root = document.getElementById('spy-chart');
    if (!root) return;
    const pts = JSON.parse(document.getElementById('spy-chart-data').textContent)
        .map(p => ({ t: new Date(p.date + 'T00:00:00').getTime(), date: p.date, you: p.you, spy: p.spy }));
    const svg = root.querySelector('svg');
    const tip = root.parentElement.querySelector('.tip');
    const NS = 'http://www.w3.org/2000/svg';
    const H = 300;
    const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    let idx = null, geom = null;

    function el(name, attrs, parent) {
        const node = document.createElementNS(NS, name);
        for (const k in attrs) node.setAttribute(k, attrs[k]);
        (parent || svg).appendChild(node);
        return node;
    }
    function compact(v) {
        const a = Math.abs(v), sign = v < 0 ? '−' : '';
        if (a >= 1e6) return sign + '฿' + (a / 1e6).toFixed(1).replace(/\.0$/, '') + 'M';
        if (a >= 1e3) return sign + '฿' + (a / 1e3).toFixed(a >= 1e4 ? 0 : 1).replace(/\.0$/, '') + 'K';
        return sign + '฿' + a.toFixed(0);
    }
    function signed(v) {
        return (v > 0 ? '+' : v < 0 ? '−' : '') + '฿' + Math.abs(Math.round(v)).toLocaleString('en-US');
    }
    function niceStep(range, count) {
        const raw = range / count, mag = Math.pow(10, Math.floor(Math.log10(raw)));
        for (const m of [1, 2, 2.5, 5, 10]) if (m * mag >= raw) return m * mag;
        return 10 * mag;
    }
    function fmtDate(d) {
        const dt = new Date(d + 'T00:00:00');
        return dt.getDate() + ' ' + MONTHS[dt.getMonth()] + ' ' + dt.getFullYear();
    }

    function render() {
        svg.textContent = '';
        const W = root.clientWidth;
        const wide = W >= 560;
        const m = { top: 12, right: wide ? 104 : 12, bottom: 26, left: 52 };
        const iw = W - m.left - m.right, ih = H - m.top - m.bottom;
        svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
        svg.setAttribute('height', H);

        const vals = pts.flatMap(p => [p.you, p.spy]);
        let lo = Math.min(0, ...vals), hi = Math.max(0, ...vals);
        const step = niceStep(hi - lo || 1, 5);
        lo = Math.floor(lo / step) * step; hi = Math.ceil(hi / step) * step;
        const t0 = pts[0].t, t1 = pts[pts.length - 1].t;
        const x = t => m.left + (t1 === t0 ? iw / 2 : (t - t0) / (t1 - t0) * iw);
        const y = v => m.top + (hi - v) / (hi - lo) * ih;
        geom = { x, y, m, iw, ih, W };

        // Gridlines + y ticks
        for (let v = lo; v <= hi + step / 2; v += step) {
            el('line', { x1: m.left, x2: m.left + iw, y1: y(v), y2: y(v), class: Math.abs(v) < step / 2 ? 'zero' : 'grid' });
            const label = el('text', { x: m.left - 8, y: y(v) + 4, 'text-anchor': 'end', class: 'tick' });
            label.textContent = Math.abs(v) < step / 2 ? '0' : compact(v);
        }
        // X ticks: first trading day of each month, thinned to fit
        const monthStarts = pts.filter((p, i) => i === 0 || new Date(p.t).getMonth() !== new Date(pts[i - 1].t).getMonth());
        const every = Math.max(1, Math.ceil(monthStarts.length / Math.max(2, Math.floor(iw / 80))));
        let lastYear = null;
        monthStarts.forEach((p, i) => {
            if (i % every) return;
            const d = new Date(p.t);
            const label = el('text', { x: x(p.t), y: H - 6, 'text-anchor': i === 0 ? 'start' : 'middle', class: 'tick' });
            // Year on the first label, then on the first label of each new year.
            const year = d.getFullYear() !== lastYear ? " '" + String(d.getFullYear()).slice(2) : '';
            lastYear = d.getFullYear();
            label.textContent = MONTHS[d.getMonth()] + year;
        });

        // Lines: S&P first so "you" draws on top
        for (const [key, color] of [['spy', '--series-spy'], ['you', '--series-you']]) {
            const d = pts.map((p, i) => (i ? 'L' : 'M') + x(p.t).toFixed(1) + ',' + y(p[key]).toFixed(1)).join('');
            el('path', { d, class: 'line', style: `stroke: var(${color})` });
        }
        // End dots + direct labels (only when they won't collide)
        const last = pts[pts.length - 1];
        const ends = [['you', 'You', '--series-you'], ['spy', 'S&P 500', '--series-spy']];
        const apart = Math.abs(y(last.you) - y(last.spy)) >= 30;
        for (const [key, name, color] of ends) {
            el('circle', { cx: x(last.t), cy: y(last[key]), r: 4, class: 'dot', style: `fill: var(${color})` });
            if (wide && apart) {
                const v = el('text', { x: x(last.t) + 10, y: y(last[key]) - 1, class: 'end-label' });
                v.textContent = signed(last[key]);
                const n = el('text', { x: x(last.t) + 10, y: y(last[key]) + 13, class: 'end-name' });
                n.textContent = name;
            }
        }
        // Hover layer: crosshair + dots, created once per render
        geom.cross = el('line', { y1: m.top, y2: m.top + ih, class: 'cross', visibility: 'hidden' });
        geom.dots = ends.map(([key, , color]) => el('circle', { r: 4, class: 'dot', style: `fill: var(${color})`, visibility: 'hidden' }));
        if (idx !== null) show(idx);
    }

    function show(i) {
        idx = i;
        const p = pts[i], { x, y, cross, dots, W } = geom;
        cross.setAttribute('x1', x(p.t)); cross.setAttribute('x2', x(p.t));
        cross.setAttribute('visibility', 'visible');
        [['you', dots[0]], ['spy', dots[1]]].forEach(([key, dot]) => {
            dot.setAttribute('cx', x(p.t)); dot.setAttribute('cy', y(p[key])); dot.setAttribute('visibility', 'visible');
        });

        tip.textContent = '';
        const date = document.createElement('div'); date.className = 'tip-date'; date.textContent = fmtDate(p.date);
        tip.appendChild(date);
        for (const [key, name, color] of [['you', 'You', '--series-you'], ['spy', 'S&P 500', '--series-spy']]) {
            const row = document.createElement('div'); row.className = 'tip-row';
            const k = document.createElement('span'); k.className = 'key'; k.style.background = `var(${color})`;
            const v = document.createElement('strong'); v.textContent = signed(p[key]);
            const n = document.createElement('span'); n.className = 'name'; n.textContent = name;
            row.append(k, v, n); tip.appendChild(row);
        }
        const diff = document.createElement('div'); diff.className = 'tip-diff';
        const gap = p.you - p.spy;
        diff.textContent = (gap >= 0 ? 'Ahead by ' : 'Behind by ') + signed(Math.abs(gap)).replace('+', '');
        tip.appendChild(diff);

        tip.hidden = false;
        const box = root.getBoundingClientRect(), card = root.parentElement.getBoundingClientRect();
        const px = box.left - card.left + x(p.t);
        const left = px + 14 + tip.offsetWidth > card.width ? px - 14 - tip.offsetWidth : px + 14;
        tip.style.left = left + 'px';
        tip.style.top = (box.top - card.top + 16) + 'px';
    }
    function hide() {
        idx = null; tip.hidden = true;
        if (!geom) return;
        geom.cross.setAttribute('visibility', 'hidden');
        geom.dots.forEach(d => d.setAttribute('visibility', 'hidden'));
    }
    function nearest(clientX) {
        const r = svg.getBoundingClientRect();
        const px = (clientX - r.left) * (geom.W / r.width);
        const t = pts[0].t + (px - geom.m.left) / geom.iw * (pts[pts.length - 1].t - pts[0].t);
        let best = 0;
        for (let i = 1; i < pts.length; i++) if (Math.abs(pts[i].t - t) < Math.abs(pts[best].t - t)) best = i;
        return best;
    }

    svg.addEventListener('pointermove', e => show(nearest(e.clientX)));
    svg.addEventListener('pointerleave', hide);
    svg.addEventListener('focus', () => show(idx ?? pts.length - 1));
    svg.addEventListener('blur', hide);
    svg.addEventListener('keydown', e => {
        if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
        e.preventDefault();
        const i = (idx ?? pts.length - 1) + (e.key === 'ArrowRight' ? 1 : -1);
        show(Math.max(0, Math.min(pts.length - 1, i)));
    });
    let raf;
    window.addEventListener('resize', () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(render); });
    render();
})();
"""


def _month_end_rows(points: list[dict]) -> str:
    rows = []
    for i, p in enumerate(points):
        if i + 1 < len(points) and points[i + 1]["date"][:7] == p["date"][:7]:
            continue  # keep the last trading day of each month (and today)
        gap = p["you"] - p["spy"]
        rows.append(f"""<tr>
            <td>{p['date']}</td>
            <td>{_pnl_span(p['you'])}</td>
            <td>{_pnl_span(p['spy'])}</td>
            <td>{_pnl_span(gap)}</td>
        </tr>""")
    return "".join(rows)


def _timeline_chart(timeline: dict | None) -> str:
    if not timeline or len(timeline["points"]) < 2:
        return ""
    # Escape "</" so the JSON can't close the script tag early.
    data = json.dumps(
        [{"date": p["date"], "you": round(p["you"], 2), "spy": round(p["spy"], 2)} for p in timeline["points"]]
    ).replace("</", "<\\/")
    approx = ""
    if timeline["approximated"]:
        approx = (
            f"<p class=\"note\" style=\"margin-top:0.25rem;\">No market price history for "
            f"{_esc(', '.join(timeline['approximated']))}; valued at your last trade price while held.</p>"
        )
    return f"""
        <div class="chart-card">
            <div class="chart-head">
                <h3>Total gain over time (THB)</h3>
                <div class="legend">
                    <span><i class="key" style="background:var(--series-you)"></i>You</span>
                    <span><i class="key" style="background:var(--series-spy)"></i>Same money in S&amp;P 500</span>
                </div>
            </div>
            <div class="chart" id="spy-chart">
                <svg tabindex="0" role="img" aria-label="Line chart of your total gain versus the same money in the S&amp;P 500 over time. Use left and right arrow keys to step through days."></svg>
            </div>
            <div class="tip" hidden></div>
            <script type="application/json" id="spy-chart-data">{data}</script>
            <details class="table-view">
                <summary>Show as table (month-end)</summary>
                <div class="scroll"><table>
                    <thead><tr><th>Date</th><th>You</th><th>S&amp;P 500</th><th>Difference</th></tr></thead>
                    <tbody>{_month_end_rows(timeline['points'])}</tbody>
                </table></div>
            </details>
            {approx}
        </div>
    """


def _benchmark_section(b: dict | None) -> str:
    if not b:
        return ""
    if "error" in b:
        return f"""
    <section>
        <h2>vs S&amp;P 500</h2>
        <div class="warn">S&amp;P 500 comparison unavailable this run: {_esc(b['error'])}</div>
    </section>
    """
    diff = b["your_gain_thb"] - b["spy_gain_thb"]
    verdict = "ahead of" if diff > 0 else "behind" if diff < 0 else "level with"
    excluded = f" (excl. {', '.join(b['excluded'])})" if b["excluded"] else ""
    return f"""
    <section>
        <h2>vs S&amp;P 500</h2>
        <div class="cards">
            <div class="card"><div class="label">Your Total Gain</div>
                <div class="value">{_signed_thb(b['your_gain_thb'])}</div>
                <div class="sub">{_fmt_pct(b['your_xirr_pct'])} / yr</div></div>
            <div class="card"><div class="label">Same Money in S&amp;P 500</div>
                <div class="value">{_signed_thb(b['spy_gain_thb'])}</div>
                <div class="sub">{_fmt_pct(b['spy_xirr_pct'])} / yr</div></div>
            <div class="card"><div class="label">You vs S&amp;P</div>
                <div class="value">{_signed_thb(diff)}</div>
                <div class="sub">{verdict} the index</div></div>
            <div class="card"><div class="label">Trades Beating S&amp;P{_esc(excluded)}</div>
                <div class="value">{b['trades_beat']} / {b['trades_rated']}</div></div>
        </div>
        <p class="note">
            Mirror portfolio: every buy and sell you made, the same amount bought or sold
            {_esc(b['symbol'])} on the same day. Total gain = realized P&amp;L + today's value of what's
            still held. Net money in ฿{b['net_invested_thb']:,.0f}; holdings now worth
            ฿{b['your_value_thb']:,.0f} vs ฿{b['spy_value_thb']:,.0f} in {_esc(b['symbol'])}.
            Valued at ฿{b['usd_thb']:.2f}/USD as of {b['as_of']:%Y-%m-%d}. Price return only — dividends
            excluded on both sides; the mirror pays no fees. % / yr is money-weighted (XIRR).
        </p>
        {_timeline_chart(b.get('timeline'))}
    </section>
    """


def _warnings(summary: dict) -> str:
    warnings = []
    if summary["unparsed_count"]:
        warnings.append(f"{summary['unparsed_count']} email(s) failed to parse and are excluded.")
    if summary["incomplete_basis_trades"]:
        warnings.append(
            f"{summary['incomplete_basis_trades']} sell(s) had no matching buy on record "
            "(cost basis incomplete for those trades)."
        )
    if not warnings:
        return ""
    return f'<div class="warn">⚠️ {" ".join(warnings)}</div>'


def _per_security_table(rows: list[dict]) -> str:
    body = ""
    for r in rows:
        win_rate = (r["wins"] / r["trades"] * 100) if r["trades"] else None
        win_rate_str = f"{win_rate:.0f}%" if win_rate is not None else "–"
        body += f"""<tr>
            <td>{_esc(r['security'])}</td>
            <td data-sort="{r['trades']}">{r['trades']}</td>
            <td data-sort="{r['wins']}">{r['wins']}</td>
            <td data-sort="{win_rate if win_rate is not None else -1}">{win_rate_str}</td>
            <td>{_pnl_span(r['realized_pnl_thb'])}</td>
        </tr>"""
    return f"""
    <section>
        <h2>Realized P&amp;L by Security</h2>
        <div class="scroll"><table class="sortable">
            <thead><tr>
                <th>Security</th>
                <th data-numeric="1">Trades</th>
                <th data-numeric="1">Wins</th>
                <th data-numeric="1">Win Rate</th>
                <th data-numeric="1">Realized P&amp;L (THB)</th>
            </tr></thead>
            <tbody>{body or '<tr><td colspan="5">No closed trades yet.</td></tr>'}</tbody>
        </table></div>
    </section>
    """


def _open_positions_table(rows: list[dict]) -> str:
    body = ""
    for r in rows:
        body += f"""<tr>
            <td>{_esc(r['security'])}</td>
            <td data-sort="{r['open_units']}">{r['open_units']:,.4f}</td>
            <td data-sort="{r['open_cost_basis_thb']}">฿{r['open_cost_basis_thb']:,.2f}</td>
        </tr>"""
    return f"""
    <section>
        <h2>Open Positions <span style="color:var(--muted); font-weight:400;">(cost basis only, no live price)</span></h2>
        <div class="scroll"><table class="sortable">
            <thead><tr><th>Security</th><th data-numeric="1">Units</th><th data-numeric="1">Cost Basis (THB)</th></tr></thead>
            <tbody>{body or '<tr><td colspan="3">No open positions.</td></tr>'}</tbody>
        </table></div>
    </section>
    """


def _fmt_spy_pct(trade: dict) -> str:
    spy_pct = trade["spy_pct"]
    if spy_pct is None:
        return "–"
    beat = trade["pnl_pct"] is not None and trade["pnl_pct"] > spy_pct
    mark = '<span class="pos" title="Beat the S&amp;P 500">✓</span> ' if beat else ""
    return f"{mark}{spy_pct:.1f}%"


def _trade_log_table(trades: list[dict]) -> str:
    body = ""
    for t in trades:
        flag = "" if t["basis_complete"] else '<span class="flag">⚠ partial basis</span>'
        pct = f"{t['pnl_pct']:.1f}%" if t["pnl_pct"] is not None else "–"
        body += f"""<tr>
            <td>{_esc(t['date'])}</td>
            <td>{_esc(t['security'])} {flag}</td>
            <td data-sort="{t['units']}">{t['units']:,.4f}</td>
            <td data-sort="{t['proceeds_thb']}">฿{t['proceeds_thb']:,.2f}</td>
            <td data-sort="{t['cost_thb']}">฿{t['cost_thb']:,.2f}</td>
            <td>{_pnl_span(t['pnl_thb'])}</td>
            <td data-sort="{t['pnl_pct'] if t['pnl_pct'] is not None else -999999}">{pct}</td>
            <td data-sort="{t['spy_pct'] if t['spy_pct'] is not None else -999999}">{_fmt_spy_pct(t)}</td>
        </tr>"""
    return f"""
    <section>
        <h2>Closed Trade Log</h2>
        <div class="table-wrap scroll"><table class="sortable">
            <thead><tr>
                <th>Date</th><th>Security</th>
                <th data-numeric="1">Units</th>
                <th data-numeric="1">Proceeds (THB)</th>
                <th data-numeric="1">Cost (THB)</th>
                <th data-numeric="1">P&amp;L (THB)</th>
                <th data-numeric="1">P&amp;L %</th>
                <th data-numeric="1">S&amp;P Same Period</th>
            </tr></thead>
            <tbody>{body or '<tr><td colspan="8">No closed trades yet.</td></tr>'}</tbody>
        </table></div>
    </section>
    """


def render_html(analytics: dict, generated_at: datetime) -> str:
    summary = analytics["summary"]
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dime! Portfolio Dashboard</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
    <h1>Dime! Portfolio Dashboard</h1>
    <div class="subtitle">Generated {generated_at.strftime('%Y-%m-%d %H:%M')} · realized P&amp;L on FIFO cost basis, all figures in THB</div>
    {_warnings(summary)}
    {_summary_cards(summary)}
    {_benchmark_section(analytics.get('benchmark'))}
    {_per_security_table(analytics['per_security'])}
    {_open_positions_table(analytics['open_positions'])}
    {_trade_log_table(analytics['trades'])}
</div>
<script>{JS}{CHART_JS}</script>
</body>
</html>
"""


def write_dashboard(path: Path, analytics: dict, generated_at: datetime | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(analytics, generated_at or datetime.now()))
