"""
Market data service.

Primary:  yfinance  (free, no key needed, good for historical + metadata)
Fallback: Polygon.io (free tier, more reliable real-time quotes)
"""

import asyncio
import math
from datetime import date, timedelta
from typing import Any
import pandas as pd
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
    """
    Batch-fetch latest close prices. Tickers yfinance can't price come back
    as NaN columns (not exceptions) — those must map to None, never NaN,
    or downstream value/return math silently turns into NaN.
    """
    prices: dict[str, float | None] = {t: None for t in tickers}
    try:
        data = yf.download(" ".join(tickers), period="1d", progress=False, auto_adjust=True)
    except Exception:
        return prices

    if data is None or data.empty or "Close" not in data:
        return prices

    close = data["Close"]
    for ticker in tickers:
        try:
            if isinstance(close, pd.DataFrame):
                # Multi-ticker (or newer yfinance single-ticker MultiIndex) shape
                series = close[ticker] if ticker in close.columns else (
                    close.iloc[:, 0] if len(tickers) == 1 else None
                )
            else:
                series = close  # legacy single-ticker Series shape
            if series is None:
                continue
            series = series.dropna()
            if series.empty:
                continue
            value = float(series.iloc[-1])
            if math.isfinite(value) and value > 0:
                prices[ticker] = value
        except Exception:
            continue
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


# ─── Portfolio value history ─────────────────────────────────────────────────

async def get_portfolio_value_history(
    holdings: list[dict],
    period_days: int = 90,
) -> list[dict[str, Any]]:
    """
    Approximate total portfolio value for each trading day in the last
    `period_days`, computed by weighting each holding's price history by its
    *current* quantity (we don't store historical transactions).

    Uses the proven single-ticker get_price_history path for each holding
    (concurrent) rather than a batch multi-ticker download, which has
    inconsistent column-naming behaviour across yfinance versions.

    Options are excluded from the live series (OCC symbols aren't quotable via
    yfinance); their current_value is added as a flat constant on every date.
    """
    quotable = [h for h in holdings if h.get("asset_type") != "option" and h.get("quantity")]
    option_offset = sum(
        _safe(h.get("current_value")) for h in holdings if h.get("asset_type") == "option"
    )

    if not quotable:
        return []

    yahoo_map = {h["ticker"]: _yahoo_symbol(h) for h in quotable}

    # Fetch per-ticker close-price histories concurrently using the proven
    # single-ticker path (get_price_history / _fetch_history_sync).
    raw_histories: list[list[dict] | BaseException] = await asyncio.gather(
        *[get_price_history(yahoo_map[h["ticker"]], period_days) for h in quotable],
        return_exceptions=True,
    )

    # Build {ticker: {date_str: close_price}} lookup
    price_map: dict[str, dict[str, float]] = {}
    for h, hist in zip(quotable, raw_histories):
        if isinstance(hist, BaseException) or not hist:
            continue
        price_map[h["ticker"]] = {row["date"]: row["close"] for row in hist}

    if not price_map:
        return []

    # Union of all dates across all tickers, sorted chronologically
    all_dates = sorted({d for dates in price_map.values() for d in dates})

    # Walk the timeline, forward-filling each ticker's last known price so
    # that e.g. stocks on weekends use Friday's close.
    points: list[dict[str, Any]] = []
    last_price: dict[str, float] = {}

    for d in all_dates:
        for h in quotable:
            t     = h["ticker"]
            price = price_map.get(t, {}).get(d)
            if price is not None and math.isfinite(price) and price > 0:
                last_price[t] = price

        total = option_offset
        for h in quotable:
            filled = last_price.get(h["ticker"])
            if filled is not None:
                total += h["quantity"] * filled

        points.append({"date": d, "value": round(total, 2)})

    return points


def _safe(value: Any) -> float:
    try:
        f = float(value)
        return f if math.isfinite(f) else 0.0
    except (TypeError, ValueError):
        return 0.0


# ─── Ticker metadata (sector, industry, name) ────────────────────────────────

async def get_ticker_info(ticker: str) -> dict[str, Any]:
    cached = INFO_CACHE.get(ticker)
    # Only use the cache if we previously got useful metadata (sector or name).
    # Don't permanently cache failed/empty responses — let them retry so that
    # a transient yfinance hiccup at import time doesn't freeze sector data as
    # "Unknown" forever.
    if cached and (cached.get("sector") or cached.get("name")):
        return cached

    loop = asyncio.get_event_loop()
    info = await loop.run_in_executor(None, _fetch_info_sync, ticker)
    if info.get("sector") or info.get("name"):
        INFO_CACHE[ticker] = info
    return info


def _fetch_info_sync(ticker: str) -> dict:
    """
    Fetch ticker metadata from yfinance.

    Newer yfinance versions (0.2.x+) changed the `.info` property to sometimes
    return an empty dict without raising.  We try `get_info()` first (the
    explicit method call is more reliable), then fall back to the `.info`
    property, so we get sector data in as many cases as possible.
    """
    base = {"ticker": ticker}
    try:
        t = yf.Ticker(ticker)

        info: dict = {}
        # Prefer the explicit method; fall back to the property.
        try:
            info = t.get_info() or {}
        except Exception:
            try:
                info = t.info or {}
            except Exception:
                pass

        if not info:
            return base

        return {
            "ticker":              ticker,
            "name":                info.get("shortName") or info.get("longName"),
            # "sectorDisp" is the display name used in some yfinance versions
            "sector":              info.get("sector") or info.get("sectorDisp"),
            "industry":            info.get("industry"),
            "market_cap":          info.get("marketCap"),
            "pe_ratio":            info.get("trailingPE"),
            "dividend_yield":      info.get("dividendYield"),
            "beta":                info.get("beta"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low":  info.get("fiftyTwoWeekLow"),
            "description":         (info.get("longBusinessSummary") or "")[:500],
        }
    except Exception:
        return base


# ─── Portfolio enrichment ────────────────────────────────────────────────────

def _yahoo_symbol(holding: dict) -> str:
    """Map a holding to its Yahoo Finance symbol. Crypto needs a -USD suffix —
    plain 'BTC'/'ETH' resolve to unrelated ETFs on Yahoo and produce wildly
    wrong prices."""
    if holding.get("asset_type") == "crypto":
        return f"{holding['ticker']}-USD"
    return holding["ticker"]


async def enrich_holdings(holdings: list[dict]) -> list[dict]:
    """
    Given parsed CSV holdings, fetch live prices and sector info
    and return enriched holding dicts.

    Options are skipped: OCC symbols aren't quotable via yfinance, and their
    CSV equity already includes the x100 contract multiplier — re-deriving
    value as quantity * price would be wrong. Their CSV values are kept as-is.
    """
    quotable  = [h for h in holdings if h.get("asset_type") != "option"]
    yahoo_map = {h["ticker"]: _yahoo_symbol(h) for h in quotable}
    tickers   = list(yahoo_map)
    symbols   = [yahoo_map[t] for t in tickers]

    prices_raw, infos = await asyncio.gather(
        get_current_prices(symbols),
        asyncio.gather(*[get_ticker_info(s) for s in symbols]),
    )
    prices   = {t: prices_raw.get(yahoo_map[t]) for t in tickers}
    info_map = {t: info for t, info in zip(tickers, infos)}

    enriched = []
    for h in holdings:
        t   = h["ticker"]
        inf = info_map.get(t, {})

        live_price = prices.get(t)
        if live_price is not None and math.isfinite(live_price) and live_price > 0:
            h["current_price"] = live_price
            if h.get("quantity"):
                h["current_value"] = h["quantity"] * live_price
            if h.get("quantity") and h.get("average_cost"):
                cost              = h["quantity"] * h["average_cost"]
                h["total_return"] = (h["quantity"] * live_price) - cost
                h["return_pct"]   = ((live_price - h["average_cost"]) / h["average_cost"]) * 100

        if h.get("asset_type") == "crypto":
            h["sector"] = h.get("sector") or "Crypto"
        else:
            h["sector"] = h.get("sector") or inf.get("sector")
        h["name"] = h.get("name") or inf.get("name") or t

        enriched.append(h)

    return enriched
