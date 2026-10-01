"""Renders the analytics from analytics.py into a single self-contained
static HTML file — no server, no build step, just open it in a browser.
"""
import html
from datetime import datetime
from pathlib import Path

CSS = """
:root {
    color-scheme: light dark;
    --bg: #f7f7f8; --card: #ffffff; --text: #1a1a1a; --muted: #6b7280;
    --border: #e5e7eb; --green: #16a34a; --red: #dc2626; --accent: #2563eb;
}
@media (prefers-color-scheme: dark) {
    :root {
        --bg: #0f1115; --card: #181b21; --text: #e5e7eb; --muted: #9ca3af;
        --border: #2a2e37; --green: #4ade80; --red: #f87171; --accent: #60a5fa;
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
<script>{JS}</script>
</body>
</html>
"""


def write_dashboard(path: Path, analytics: dict, generated_at: datetime | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(analytics, generated_at or datetime.now()))
