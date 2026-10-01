"""Computes realized profit/loss and win rate from the logged transactions.

Cost basis is tracked per security using FIFO: each Buy (or Reward/Exercise,
which also add units) pushes a lot onto that security's queue; each Sell
consumes lots oldest-first and the difference between net proceeds and
matched cost is the realized P&L for that trade. Everything is computed in
THB, using the per-row `total_amount_thb` (already net of VAT/withholding),
since that's the actual cash cost/proceeds in the account's home currency.

This only computes *realized* P&L (closed trades) — no live market price is
fetched, so open positions are reported as units + cost basis, not paper
gains.
"""
from collections import deque
from pathlib import Path

from openpyxl import load_workbook

# Smallest fraction-of-a-unit we treat as real rather than float residue.
# Units are logged with up to 7 decimal places, so 1e-4 comfortably clears
# rounding error from repeated FIFO subtraction without hiding a real lot.
_EPS = 1e-4

# Cash-parking ETFs left out of the headline win rate. Their return comes
# almost entirely from dividends (not tracked here), so every sell looks like
# a small fee/FX loss. They still count toward realized P&L.
WIN_RATE_EXCLUDED = {"SGOV"}


def _to_float(value) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value).replace(",", ""))


def _sort_key(row: dict):
    date_key = ""
    for field in ("effective_date", "settlement_date", "received_date"):
        value = row.get(field)
        if not value:
            continue
        if field == "received_date":
            date_key = value  # ISO 8601, already sortable
        else:
            day, month, year = value.split("/")
            date_key = f"{year}-{month}-{day}"
        break

    # order_id is a broker-assigned sequential trade ID — same-day trades
    # (common when a message batches several orders) sort correctly by it,
    # which plain date sorting can't do since it's only day-resolution.
    try:
        order_key = int(row.get("order_id"))
    except (TypeError, ValueError):
        order_key = 0
    return (date_key, order_key)


def load_transactions(excel_path: Path) -> list[dict]:
    wb = load_workbook(excel_path, read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    header = rows[0]
    return [dict(zip(header, row)) for row in rows[1:]]


def compute_analytics(transactions: list[dict]) -> dict:
    ok_rows = [r for r in transactions if r.get("parse_status") == "ok"]
    unparsed_count = len(transactions) - len(ok_rows)
    ok_rows.sort(key=_sort_key)

    lots: dict[str, deque] = {}
    trades = []
    per_security: dict[str, dict] = {}

    def sec_stats(security: str) -> dict:
        return per_security.setdefault(
            security,
            {"security": security, "trades": 0, "wins": 0, "realized_pnl_thb": 0.0},
        )

    for row in ok_rows:
        security = row.get("security")
        units = _to_float(row.get("units"))
        total_thb = _to_float(row.get("total_amount_thb"))
        if not security or units is None or total_thb is None:
            continue

        queue = lots.setdefault(security, deque())

        if row.get("transaction_type") == "Sell":
            units_to_sell = units
            matched_cost = 0.0
            basis_complete = True
            while units_to_sell > _EPS and queue:
                lot_units, lot_cost_per_unit = queue[0]
                take = min(lot_units, units_to_sell)
                matched_cost += take * lot_cost_per_unit
                units_to_sell -= take
                if take >= lot_units - _EPS:
                    queue.popleft()
                else:
                    queue[0] = (lot_units - take, lot_cost_per_unit)
            if units_to_sell > _EPS:
                basis_complete = False  # sold more than we ever bought

            pnl = total_thb - matched_cost
            stats = sec_stats(security)
            stats["trades"] += 1
            stats["realized_pnl_thb"] += pnl
            if pnl > 0:
                stats["wins"] += 1

            trades.append(
                {
                    "date": row.get("effective_date") or row.get("settlement_date"),
                    "security": security,
                    "units": units,
                    "proceeds_thb": total_thb,
                    "cost_thb": matched_cost,
                    "pnl_thb": pnl,
                    "pnl_pct": (pnl / matched_cost * 100) if matched_cost else None,
                    "win": pnl > 0,
                    "basis_complete": basis_complete,
                }
            )
        else:
            # Buy, Reward, Exercise Call/Put: adds a cost-basis lot.
            cost_per_unit = total_thb / units if units else 0.0
            queue.append((units, cost_per_unit))

    open_positions = []
    for security, queue in lots.items():
        open_units = sum(u for u, _ in queue)
        open_cost = sum(u * c for u, c in queue)
        if open_units > _EPS:
            open_positions.append(
                {"security": security, "open_units": open_units, "open_cost_basis_thb": open_cost}
            )

    total_trades = len(trades)
    total_wins = sum(1 for t in trades if t["win"])
    total_pnl = sum(t["pnl_thb"] for t in trades)
    incomplete_basis_trades = sum(1 for t in trades if not t["basis_complete"])

    rated_trades = [t for t in trades if t["security"] not in WIN_RATE_EXCLUDED]
    rated_wins = sum(1 for t in rated_trades if t["win"])

    return {
        "summary": {
            "total_realized_pnl_thb": total_pnl,
            "total_trades": total_trades,
            "total_wins": total_wins,
            "win_rate_pct": (rated_wins / len(rated_trades) * 100) if rated_trades else None,
            "win_rate_excluded": sorted(WIN_RATE_EXCLUDED),
            "open_position_count": len(open_positions),
            "unparsed_count": unparsed_count,
            "incomplete_basis_trades": incomplete_basis_trades,
        },
        "per_security": sorted(
            per_security.values(), key=lambda s: s["realized_pnl_thb"], reverse=True
        ),
        "open_positions": sorted(open_positions, key=lambda p: p["security"]),
        "trades": list(reversed(trades)),  # most recent first
    }


def build_analytics(excel_path: Path) -> dict:
    return compute_analytics(load_transactions(excel_path))
