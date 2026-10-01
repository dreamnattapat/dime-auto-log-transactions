"""Compares the portfolio against the S&P 500, using SPY as the index.

Two views:

1. **Mirror portfolio** — every Buy/Sell is mirrored by buying/selling the
   same USD amount of SPY on the same trade date. Both portfolios therefore
   have identical cash in and out, so comparing what each is worth today
   (your open positions vs the mirror's SPY) answers "did my picks beat
   just holding the index?". Both are valued at today's USD/THB, so FX
   affects them equally. The mirror pays no fees, and dividends are left out
   on both sides.

2. **Per closed trade** — for the lots each Sell consumed, what SPY returned
   (in THB, using the confirmation FX rates) over the same holding period.
"""
from datetime import date

import market_data

BENCHMARK_SYMBOL = "SPY"
FX_SYMBOL = "THB=X"  # THB per 1 USD


def xirr(flows: list[tuple[date, float]]) -> float | None:
    """Annualized money-weighted return, solved by bisection."""
    if not flows:
        return None
    t0 = min(d for d, _ in flows)

    def npv(rate: float) -> float:
        return sum(amount / (1 + rate) ** ((d - t0).days / 365.0) for d, amount in flows)

    lo, hi = -0.99, 10.0
    f_lo = npv(lo)
    if f_lo * npv(hi) > 0:
        return None  # no sign change, no meaningful rate
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = npv(mid)
        if f_lo * f_mid <= 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


def compute_benchmark(
    analytics: dict,
    spy: market_data.PriceSeries,
    latest_prices: dict[str, float],
    usd_thb: float,
    today: date,
    excluded: set[str] = frozenset(),
) -> dict:
    flows = analytics["cash_flows"]
    if any(f["date"] is None or f["usd"] is None for f in flows):
        raise ValueError("some transactions are missing a trade date or USD amount")

    # Mirror portfolio: buys have negative usd (money in), so -usd/price
    # adds shares on buys and removes them on sells.
    spy_shares = sum(-f["usd"] / spy.on(f["date"]) for f in flows)
    spy_value_thb = spy_shares * spy.latest * usd_thb
    holdings_value_thb = sum(
        p["open_units"] * latest_prices[p["security"]] * usd_thb
        for p in analytics["open_positions"]
    )

    net_cash_thb = sum(f["thb"] for f in flows)  # sells - buys
    dated_flows = [(f["date"], f["thb"]) for f in flows]

    # Per closed trade: SPY's THB return over the same holding period.
    beat = rated = 0
    for t in analytics["trades"]:
        cost = sum(lot["cost_thb"] for lot in t["lots"])
        if not cost or t["fx"] is None or any(lot["buy_fx"] is None for lot in t["lots"]):
            continue
        sell_price_thb = spy.on(t["trade_date"]) * t["fx"]
        mirrored = sum(
            lot["cost_thb"] * sell_price_thb / (spy.on(lot["buy_date"]) * lot["buy_fx"])
            for lot in t["lots"]
        )
        t["spy_pct"] = (mirrored / cost - 1) * 100
        if t["security"] not in excluded and t["pnl_pct"] is not None:
            rated += 1
            beat += t["pnl_pct"] > t["spy_pct"]

    return {
        "symbol": BENCHMARK_SYMBOL,
        "as_of": today,
        "usd_thb": usd_thb,
        "net_invested_thb": -net_cash_thb,  # buys - sells: money still at work
        "your_value_thb": holdings_value_thb,
        "your_gain_thb": holdings_value_thb + net_cash_thb,
        "your_xirr_pct": _pct(xirr(dated_flows + [(today, holdings_value_thb)])),
        "spy_value_thb": spy_value_thb,
        "spy_gain_thb": spy_value_thb + net_cash_thb,
        "spy_xirr_pct": _pct(xirr(dated_flows + [(today, spy_value_thb)])),
        "trades_beat": beat,
        "trades_rated": rated,
        "excluded": sorted(excluded),
    }


def _pct(rate: float | None) -> float | None:
    return None if rate is None else rate * 100


def build_benchmark(analytics: dict, excluded: set[str] = frozenset()) -> dict:
    """Fetches the prices needed and runs compute_benchmark."""
    flows = analytics["cash_flows"]
    if not flows:
        raise ValueError("no transactions yet")
    today = date.today()
    start = min(f["date"] for f in flows if f["date"] is not None)

    spy = market_data.fetch_prices(BENCHMARK_SYMBOL, start, today)
    usd_thb = market_data.fetch_prices(FX_SYMBOL, today, today).latest
    latest_prices = {
        p["security"]: market_data.fetch_prices(market_data.yahoo_symbol(p["security"]), today, today).latest
        for p in analytics["open_positions"]
    }
    return compute_benchmark(analytics, spy, latest_prices, usd_thb, today, excluded)
