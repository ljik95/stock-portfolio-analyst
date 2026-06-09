"""
Market data service.

Primary:  yfinance  (free, no key needed, good for historical + metadata)
Fallback: Polygon.io (free tier, more reliable real-time quotes)
"""

import asyncio
from datetime import date, timedelta
from typing import Any
import yfinance as yf
import httpx
from app.core.config import settings

SECTOR_CACHE: dict[str, str] = {}
INFO_CACHE:   dict[str, dict] = {}


# ─── Price quotes ─────────────────────────────────────────────────────────────

async def get_current_prices(tickers: list[str]) -> dict[str, float | None]:
    """Return {ticker: current_price} for a list of tickers."""
    if not tickers:
        return {}

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _fetch_prices_sync, tickers)
    return result


def _fetch_prices_sync(tickers: list[str]) -> dict[str, float | None]:
    joined = " ".join(tickers)
    data = yf.download(joined, period="1d", progress=False, auto_adjust=True)

    prices: dict[str, float | None] = {}
    if data.empty:
        return {t: None for t in tickers}

    close = data["Close"]
    for ticker in tickers:
        try:
            if len(tickers) == 1:
                prices[ticker] = float(close.iloc[-1])
            else:
                prices[ticker] = float(close[ticker].iloc[-1])
        except Exception:
            prices[ticker] = None
    return prices


# ─── Price history ────────────────────────────────────────────────────────────

async def get_price_history(
    ticker: str,
    period_days: int = 365,
) -> list[dict[str, Any]]:
    """Return daily OHLCV as a list of dicts for the past `period_days`."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_history_sync, ticker, period_days)


def _fetch_history_sync(ticker: str, period_days: int) -> list[dict]:
    end   = date.today()
    start = end - timedelta(days=period_days)
    df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)

    if df.empty:
        return []

    rows = []
    for idx, row in df.iterrows():
        rows.append({
            "date":   idx.strftime("%Y-%m-%d"),
            "open":   round(float(row["Open"]),   4),
            "high":   round(float(row["High"]),   4),
            "low":    round(float(row["Low"]),    4),
            "close":  round(float(row["Close"]),  4),
            "volume": int(row["Volume"]),
        })
    return rows


# ─── Ticker metadata (sector, industry, name) ────────────────────────────────

async def get_ticker_info(ticker: str) -> dict[str, Any]:
    if ticker in INFO_CACHE:
        return INFO_CACHE[ticker]

    loop = asyncio.get_event_loop()
    info = await loop.run_in_executor(None, _fetch_info_sync, ticker)
    INFO_CACHE[ticker] = info
    return info


def _fetch_info_sync(ticker: str) -> dict:
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        return {
            "ticker":        ticker,
            "name":          info.get("shortName") or info.get("longName"),
            "sector":        info.get("sector"),
            "industry":      info.get("industry"),
            "market_cap":    info.get("marketCap"),
            "pe_ratio":      info.get("trailingPE"),
            "dividend_yield": info.get("dividendYield"),
            "beta":          info.get("beta"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low":  info.get("fiftyTwoWeekLow"),
            "description":   (info.get("longBusinessSummary") or "")[:500],
        }
    except Exception:
        return {"ticker": ticker}


# ─── Portfolio enrichment ────────────────────────────────────────────────────

async def enrich_holdings(holdings: list[dict]) -> list[dict]:
    """
    Given parsed CSV holdings, fetch live prices and sector info
    and return enriched holding dicts.
    """
    tickers = [h["ticker"] for h in holdings]

    prices, infos = await asyncio.gather(
        get_current_prices(tickers),
        asyncio.gather(*[get_ticker_info(t) for t in tickers]),
    )
    info_map = {t: info for t, info in zip(tickers, infos)}

    enriched = []
    for h in holdings:
        t   = h["ticker"]
        inf = info_map.get(t, {})

        live_price = prices.get(t)
        if live_price:
            h["current_price"] = live_price
            if h.get("quantity") and live_price:
                h["current_value"] = h["quantity"] * live_price
            if h.get("quantity") and h.get("average_cost") and live_price:
                cost            = h["quantity"] * h["average_cost"]
                h["total_return"] = (h["quantity"] * live_price) - cost
                h["return_pct"]   = ((live_price - h["average_cost"]) / h["average_cost"]) * 100

        h["sector"] = h.get("sector") or inf.get("sector")
        h["name"]   = h.get("name")   or inf.get("name") or t

        enriched.append(h)

    return enriched
