"""Daily closing prices from Yahoo Finance's public chart endpoint (no API
key). Only ticker symbols and a date range are sent — nothing about the
account or the trades themselves.

Closes are split-adjusted but *not* dividend-adjusted, i.e. price return —
which matches the rest of the dashboard, since dividends aren't tracked.
"""
import json
from bisect import bisect_right
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?{query}"
_HEADERS = {"User-Agent": "Mozilla/5.0"}
_TIMEOUT_S = 15


class PriceSeries:
    def __init__(self, symbol: str, closes: list[tuple[date, float]], latest: float):
        self.symbol = symbol
        self._dates = [d for d, _ in closes]
        self._closes = [c for _, c in closes]
        self.latest = latest

    def on(self, day: date) -> float:
        """Close on `day`, or the last trading day before it."""
        i = bisect_right(self._dates, day)
        if i == 0:
            raise LookupError(f"No {self.symbol} price on or before {day}")
        return self._closes[i - 1]


def yahoo_symbol(security: str) -> str:
    # Dime! writes share classes with a dot (BRK.B); Yahoo uses a dash.
    return security.replace(".", "-")


def _epoch(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp())


def fetch_prices(symbol: str, start: date, end: date | None = None) -> PriceSeries:
    end = end or date.today()
    query = urlencode(
        {
            # Pad the start so a trade on a market holiday can fall back to
            # the previous close.
            "period1": _epoch(start - timedelta(days=7)),
            "period2": _epoch(end + timedelta(days=1)),
            "interval": "1d",
        }
    )
    request = Request(_URL.format(symbol=symbol, query=query), headers=_HEADERS)
    with urlopen(request, timeout=_TIMEOUT_S) as response:
        data = json.load(response)

    result = (data.get("chart") or {}).get("result")
    if not result:
        raise LookupError(f"No price data for {symbol}: {data.get('chart', {}).get('error')}")
    result = result[0]
    # Timestamps are the session open in UTC; shift by the exchange's offset
    # so they land on the exchange's local trading date.
    offset = result["meta"].get("gmtoffset", 0)
    closes = [
        (datetime.fromtimestamp(ts + offset, tz=timezone.utc).date(), close)
        for ts, close in zip(result.get("timestamp", []), result["indicators"]["quote"][0]["close"])
        if close is not None
    ]
    if not closes:
        raise LookupError(f"No closing prices for {symbol} in range")
    latest = result["meta"].get("regularMarketPrice") or closes[-1][1]
    return PriceSeries(symbol, closes, latest)
