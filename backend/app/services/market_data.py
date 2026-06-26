"""
Market data service.

Primary:   Polygon.io (free tier — 15-min delayed quotes, full historical bars,
           reference data including SIC codes).  API key from POLYGON_API_KEY env var.
Fallback:  yfinance fast_info (no key needed; the yf.download() batch API is
           unreliable from Docker containers because Yahoo Finance blocks the
           requests, but fast_info hits a lighter-weight endpoint).
"""

import asyncio
import math
from datetime import date, timedelta, datetime
from typing import Any
import pandas as pd
import yfinance as yf
import httpx
from app.core.config import settings

INFO_CACHE:   dict[str, dict] = {}

POLYGON_BASE = "https://api.polygon.io"


# ─── SIC → GICS-like sector mapping ─────────────────────────────────────────
# Covers the most common SIC codes found in US stock portfolios.

def _sic_to_sector(sic: int | str | None) -> str | None:
    """Map an SIC code to a broad sector label."""
    if sic is None:
        return None
    try:
        c = int(sic)
    except (TypeError, ValueError):
        return None

    # Technology (specific ranges first to avoid override by broad Industrials)
    if 3559 <= c <= 3579: return "Technology"   # industrial/commercial machinery
    if 3669 <= c <= 3679: return "Technology"   # electronic components
    if 3812 <= c <= 3812: return "Industrials"  # defense electronics
    if 3825 <= c <= 3829: return "Technology"   # instruments
    if 3841 <= c <= 3851: return "Healthcare"   # medical instruments
    if 7370 <= c <= 7379: return "Technology"   # computer & data processing

    # Healthcare
    if 2830 <= c <= 2836: return "Healthcare"   # pharma
    if 5912 <= c <= 5912: return "Consumer Staples"   # drug stores
    if 8000 <= c <= 8099: return "Healthcare"   # health services
    if 8011 <= c <= 8049: return "Healthcare"

    # Energy
    if 1300 <= c <= 1399: return "Energy"       # oil & gas extraction
    if 2900 <= c <= 2999: return "Energy"       # petroleum refining
    if 4911 <= c <= 4991: return "Utilities"    # electric/gas utilities

    # Financial
    if 6000 <= c <= 6999: return "Financial Services"

    # Consumer
    if 5400 <= c <= 5499: return "Consumer Staples"    # grocery
    if 2000 <= c <= 2399: return "Consumer Staples"    # food & kindred
    if 2100 <= c <= 2199: return "Consumer Staples"    # tobacco
    if 5000 <= c <= 5999: return "Consumer Discretionary"  # retail/wholesale
    if 7000 <= c <= 7369: return "Consumer Discretionary"  # hotels, entertainment
    if 7380 <= c <= 7999: return "Consumer Discretionary"

    # Broad buckets
    if  100 <= c <=  999: return "Agriculture"
    if 1000 <= c <= 1499: return "Energy"       # mining
    if 1500 <= c <= 1799: return "Industrials"  # construction
    if 2400 <= c <= 3999: return "Industrials"  # manufacturing (remaining)
    if 4000 <= c <= 4899: return "Industrials"  # transportation
    if 4900 <= c <= 4999: return "Utilities"

    return None


# ─── Polygon helpers ─────────────────────────────────────────────────────────

def _polygon_key() -> str:
    return settings.polygon_api_key or ""


async def _polygon_get(path: str, params: dict | None = None) -> dict:
    """GET from Polygon.io; returns {} on any error."""
    key = _polygon_key()
    if not key:
        return {}
    p = dict(params or {})
    p["apiKey"] = key
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{POLYGON_BASE}{path}", params=p)
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {}


# ─── Price quotes ─────────────────────────────────────────────────────────────

async def get_current_prices(tickers: list[str]) -> dict[str, float | None]:
    """Return {ticker: current_price}.  Polygon first, yfinance fast_info fallback."""
    if not tickers:
        return {}

    prices = await _polygon_prices(tickers)

    missing = [t for t in tickers if prices.get(t) is None]
    if missing:
        loop = asyncio.get_event_loop()
        yf_prices = await loop.run_in_executor(None, _yfinance_fast_prices, missing)
        for t, v in yf_prices.items():
            if v is not None:
                prices[t] = v

    return prices


async def _polygon_prices(tickers: list[str]) -> dict[str, float | None]:
    """Batch price fetch from Polygon snapshot endpoint."""
    result: dict[str, float | None] = {t: None for t in tickers}

    stocks = [t for t in tickers if not t.endswith("-USD")]
    crypto = [t for t in tickers if t.endswith("-USD")]

    # ── Stocks / ETFs ──────────────────────────────────────────────────────
    if stocks:
        data = await _polygon_get(
            "/v2/snapshot/locale/us/markets/stocks/tickers",
            {"tickers": ",".join(stocks)},
        )
        for snap in data.get("tickers", []):
            sym = snap.get("ticker")
            if sym not in result:
                continue
            lt   = snap.get("lastTrade") or {}
            day  = snap.get("day")       or {}
            prev = snap.get("prevDay")   or {}
            raw  = lt.get("p") or day.get("c") or prev.get("c")
            if raw:
                try:
                    p = float(raw)
                    if math.isfinite(p) and p > 0:
                        result[sym] = p
                except (TypeError, ValueError):
                    pass

    # ── Crypto ─────────────────────────────────────────────────────────────
    for t in crypto:
        base = t.replace("-USD", "")
        pair = f"X:{base}USD"
        data = await _polygon_get(
            f"/v2/snapshot/locale/global/markets/crypto/tickers/{pair}",
        )
        snap = (data.get("ticker") or {})
        day  = snap.get("day") or {}
        raw  = day.get("c")
        if raw:
            try:
                p = float(raw)
                if math.isfinite(p) and p > 0:
                    result[t] = p
            except (TypeError, ValueError):
                pass

    return result


def _yfinance_fast_prices(tickers: list[str]) -> dict[str, float | None]:
    """Per-ticker price fetch via yfinance fast_info (lighter-weight endpoint)."""
    prices: dict[str, float | None] = {t: None for t in tickers}
    for ticker in tickers:
        try:
            fi = yf.Ticker(ticker).fast_info
            price = fi.last_price or fi.previous_close
            if price and math.isfinite(float(price)) and float(price) > 0:
                prices[ticker] = float(price)
        except Exception:
            continue
    return prices


# ─── Price history ────────────────────────────────────────────────────────────

async def get_price_history(
    ticker: str,
    period_days: int = 365,
) -> list[dict[str, Any]]:
    """Return daily OHLCV dicts.  Polygon first, yfinance fallback."""
    end   = date.today()
    start = end - timedelta(days=period_days)

    history = await _polygon_history(ticker, start, end)
    if history:
        return history

    # fallback
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _yfinance_history_sync, ticker, period_days)


async def _polygon_history(ticker: str, start: date, end: date) -> list[dict]:
    """Fetch adjusted daily bars from Polygon aggregates."""
    if ticker.endswith("-USD"):
        base = ticker.replace("-USD", "")
        poly_ticker = f"X:{base}USD"
    else:
        poly_ticker = ticker

    data = await _polygon_get(
        f"/v2/aggs/ticker/{poly_ticker}/range/1/day"
        f"/{start.isoformat()}/{end.isoformat()}",
        {"adjusted": "true", "sort": "asc", "limit": 500},
    )

    rows = []
    for bar in data.get("results", []):
        ts = bar.get("t", 0) / 1000   # ms → s
        try:
            d = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
        except Exception:
            continue
        try:
            rows.append({
                "date":   d,
                "open":   round(float(bar["o"]), 4),
                "high":   round(float(bar["h"]), 4),
                "low":    round(float(bar["l"]), 4),
                "close":  round(float(bar["c"]), 4),
                "volume": int(bar.get("v", 0)),
            })
        except (KeyError, TypeError, ValueError):
            continue
    return rows


def _yfinance_history_sync(ticker: str, period_days: int) -> list[dict]:
    end   = date.today()
    start = end - timedelta(days=period_days)
    try:
        df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
    except Exception:
        return []

    if df.empty:
        return []

    rows = []
    for idx, row in df.iterrows():
        try:
            rows.append({
                "date":   idx.strftime("%Y-%m-%d"),
                "open":   round(float(row["Open"]),   4),
                "high":   round(float(row["High"]),   4),
                "low":    round(float(row["Low"]),    4),
                "close":  round(float(row["Close"]),  4),
                "volume": int(row["Volume"]),
            })
        except Exception:
            continue
    return rows


# ─── Portfolio value history ─────────────────────────────────────────────────

async def get_portfolio_value_history(
    holdings: list[dict],
    period_days: int = 90,
) -> list[dict[str, Any]]:
    """
    Approximate total portfolio value for each trading day in the last
    `period_days`, using current quantities applied to historical prices.
    Options are excluded from the price series; their current_value is
    added as a flat constant on every date.
    """
    quotable = [h for h in holdings if h.get("asset_type") != "option" and h.get("quantity")]
    option_offset = sum(
        _safe(h.get("current_value")) for h in holdings if h.get("asset_type") == "option"
    )

    if not quotable:
        return []

    yahoo_map = {h["ticker"]: _yahoo_symbol(h) for h in quotable}

    raw_histories: list[list[dict] | BaseException] = await asyncio.gather(
        *[get_price_history(yahoo_map[h["ticker"]], period_days) for h in quotable],
        return_exceptions=True,
    )

    price_map: dict[str, dict[str, float]] = {}
    for h, hist in zip(quotable, raw_histories):
        if isinstance(hist, BaseException) or not hist:
            continue
        price_map[h["ticker"]] = {row["date"]: row["close"] for row in hist}

    if not price_map:
        return []

    all_dates = sorted({d for dates in price_map.values() for d in dates})

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


# ─── Ticker metadata (sector, name) ──────────────────────────────────────────

async def get_ticker_info(ticker: str) -> dict[str, Any]:
    """
    Return metadata dict.  Only caches successful lookups (with sector or name)
    so transient failures don't permanently freeze data as "Unknown".
    """
    cached = INFO_CACHE.get(ticker)
    if cached and (cached.get("sector") or cached.get("name")):
        return cached

    # Try Polygon reference data first
    info = await _polygon_ticker_info(ticker)

    # Fall back to yfinance .info if Polygon didn't give us sector/name
    if not info.get("sector") or not info.get("name"):
        loop = asyncio.get_event_loop()
        yf_info = await loop.run_in_executor(None, _yfinance_info_sync, ticker)
        # Merge: prefer values already found via Polygon
        info["sector"] = info.get("sector") or yf_info.get("sector")
        info["name"]   = info.get("name")   or yf_info.get("name")
        for k in ("industry", "market_cap", "pe_ratio", "dividend_yield",
                  "beta", "fifty_two_week_high", "fifty_two_week_low", "description"):
            info.setdefault(k, yf_info.get(k))

    if info.get("sector") or info.get("name"):
        INFO_CACHE[ticker] = info
    return info


async def _polygon_ticker_info(ticker: str) -> dict[str, Any]:
    """Fetch name + sector from Polygon reference endpoint."""
    base = {"ticker": ticker}
    if ticker.endswith("-USD"):
        # Crypto — no reference endpoint; caller handles sector separately
        return base

    data = await _polygon_get(f"/v3/reference/tickers/{ticker}")
    res  = data.get("results") or {}
    if not res:
        return base

    sic_code  = res.get("sic_code")
    sic_desc  = res.get("sic_description")
    asset_type = res.get("type", "")  # "CS", "ETV", "ETF", etc.

    # Derive sector: try SIC mapping; ETFs get "Diversified"
    if asset_type in ("ETV", "ETF", "ETN"):
        sector = "Diversified"
    else:
        sector = _sic_to_sector(sic_code) or (sic_desc.title() if sic_desc else None)

    return {
        "ticker":      ticker,
        "name":        res.get("name"),
        "sector":      sector,
        "industry":    sic_desc,
        "description": (res.get("description") or "")[:500],
        "market_cap":  res.get("market_cap"),
    }


def _yfinance_info_sync(ticker: str) -> dict:
    """yfinance .info fallback for metadata.  Silent on failure."""
    base = {"ticker": ticker}
    try:
        t = yf.Ticker(ticker)
        info: dict = {}
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


# ─── Enrichment ───────────────────────────────────────────────────────────────

def _yahoo_symbol(holding: dict) -> str:
    """Map holding dict to its Yahoo / Polygon price symbol."""
    if holding.get("asset_type") == "crypto":
        return f"{holding['ticker']}-USD"
    return holding["ticker"]


async def enrich_holdings(holdings: list[dict]) -> list[dict]:
    """
    Fetch live prices and sector/name metadata for parsed CSV holdings.
    Options are skipped for live pricing — their CSV equity value is correct.
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
