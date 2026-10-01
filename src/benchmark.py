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

3. **Timeline** — both portfolios' total gain on every trading day from the
   first trade to today, for the dashboard chart. Holdings are valued at
   each day's close and USD/THB rate; its last point equals the headline.
"""
import logging
from collections import defaultdict
from datetime import date

import market_data

logger = logging.getLogger(__name__)

BENCHMARK_SYMBOL = "SPY"
FX_SYMBOL = "THB=X"  # THB per 1 USD

# Net units below this are float residue from fractional sells, not a holding.
_EPS = 1e-4


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


def compute_timeline(
    flows: list[dict],
    spy: market_data.PriceSeries,
    fx: market_data.PriceSeries,
    prices: dict[str, market_data.PriceSeries | None],
    latest_prices: dict[str, float],
    today: date,
) -> dict:
    """Daily total gain (THB) for you and the S&P 500 mirror.

    Total gain on a day = what's held, valued at that day's close and FX
    rate, plus all cash taken out so far, minus all cash put in so far.
    """
    flows = sorted(flows, key=lambda f: f["date"])  # stable: keeps same-day order
    days = [d for d in spy.dates if flows[0]["date"] <= d < today] + [today]

    units: dict[str, float] = defaultdict(float)
    last_trade_price: dict[str, float] = {}
    cash_thb = spy_shares = 0.0
    approximated: set[str] = set()
    points = []
    i = 0
    for day in days:
        while i < len(flows) and flows[i]["date"] <= day:
            f = flows[i]
            units[f["security"]] += f["units"]
            if f["unit_price"]:
                last_trade_price[f["security"]] = f["unit_price"]
            cash_thb += f["thb"]
            spy_shares += -f["usd"] / spy.on(f["date"])
            i += 1

        is_today = day == today
        holdings_usd = 0.0
        for security, held in units.items():
            if abs(held) < _EPS:
                continue
            if is_today and security in latest_prices:
                price = latest_prices[security]
            else:
                try:
                    series = prices[security]
                    price = series.on(day) * series.split_factor_after(day)
                except (KeyError, AttributeError, LookupError):
                    # No market history (e.g. delisted ticker): fall back to
                    # the last price we traded it at.
                    price = last_trade_price[security]
                    approximated.add(security)
            holdings_usd += held * price

        usd_thb = fx.latest if is_today else fx.on(day)
        spy_price = spy.latest if is_today else spy.on(day)
        points.append(
            {
                "date": day.isoformat(),
                "you": holdings_usd * usd_thb + cash_thb,
                "spy": spy_shares * spy_price * usd_thb + cash_thb,
            }
        )
    return {"points": points, "approximated": sorted(approximated)}


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
    fx = market_data.fetch_prices(FX_SYMBOL, start, today)

    prices: dict[str, market_data.PriceSeries | None] = {}
    for security in sorted({f["security"] for f in flows}):
        try:
            prices[security] = market_data.fetch_prices(market_data.yahoo_symbol(security), start, today)
        except Exception as e:  # e.g. a delisted ticker; the timeline falls back
            logger.info("No price history for %s: %s", security, e)
            prices[security] = None

    latest_prices = {}
    for p in analytics["open_positions"]:
        if prices.get(p["security"]) is None:
            raise LookupError(f"no current price for {p['security']}")
        latest_prices[p["security"]] = prices[p["security"]].latest

    result = compute_benchmark(analytics, spy, latest_prices, fx.latest, today, excluded)
    try:
        result["timeline"] = compute_timeline(flows, spy, fx, prices, latest_prices, today)
    except Exception as e:  # keep the headline numbers even if the chart can't be built
        logger.warning("S&P 500 timeline unavailable: %s", e)
        result["timeline"] = None
    return result
