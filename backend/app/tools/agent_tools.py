"""
Agent tools — functions the LLM can invoke via tool calling.

Each tool is a plain async Python function plus an Anthropic tool definition dict.
The agent service wires them together.
"""

import json
from typing import Any
from app.services import market_data as md


# ─── Tool implementations ─────────────────────────────────────────────────────

async def tool_get_current_price(ticker: str) -> str:
    prices = await md.get_current_prices([ticker.upper()])
    price  = prices.get(ticker.upper())
    if price is None:
        return json.dumps({"error": f"Could not fetch price for {ticker}"})
    return json.dumps({"ticker": ticker.upper(), "price": price, "currency": "USD"})


async def tool_get_price_history(ticker: str, days: int = 90) -> str:
    days    = min(max(days, 1), 365)
    history = await md.get_price_history(ticker.upper(), period_days=days)
    if not history:
        return json.dumps({"error": f"No history for {ticker}"})
    # Return summary to avoid flooding the context window
    prices = [p["close"] for p in history]
    return json.dumps({
        "ticker":       ticker.upper(),
        "days":         len(history),
        "start_date":   history[0]["date"],
        "end_date":     history[-1]["date"],
        "start_price":  prices[0],
        "end_price":    prices[-1],
        "min_price":    min(prices),
        "max_price":    max(prices),
        "price_change_pct": round((prices[-1] - prices[0]) / prices[0] * 100, 2),
    })


async def tool_get_ticker_info(ticker: str) -> str:
    info = await md.get_ticker_info(ticker.upper())
    return json.dumps(info)


async def tool_calculate_portfolio_metrics(holdings_json: str) -> str:
    """Compute aggregate metrics from a JSON list of holdings."""
    try:
        holdings: list[dict] = json.loads(holdings_json)
    except Exception:
        return json.dumps({"error": "Invalid holdings JSON"})

    total_value  = sum(h.get("current_value") or 0 for h in holdings)
    total_cost   = sum((h.get("quantity") or 0) * (h.get("average_cost") or 0) for h in holdings)
    total_return = total_value - total_cost
    return_pct   = (total_return / total_cost * 100) if total_cost else 0

    # Sector breakdown
    sector_values: dict[str, float] = {}
    for h in holdings:
        s = h.get("sector") or "Unknown"
        sector_values[s] = sector_values.get(s, 0) + (h.get("current_value") or 0)
    sector_pct = {s: round(v / total_value * 100, 2) for s, v in sector_values.items()} if total_value else {}

    # Top/bottom performers
    with_return = [h for h in holdings if h.get("return_pct") is not None]
    sorted_by_return = sorted(with_return, key=lambda h: h["return_pct"], reverse=True)
    top3    = [{"ticker": h["ticker"], "return_pct": h["return_pct"]} for h in sorted_by_return[:3]]
    bottom3 = [{"ticker": h["ticker"], "return_pct": h["return_pct"]} for h in sorted_by_return[-3:]]

    return json.dumps({
        "total_value":     round(total_value, 2),
        "total_cost":      round(total_cost, 2),
        "total_return":    round(total_return, 2),
        "return_pct":      round(return_pct, 2),
        "num_holdings":    len(holdings),
        "sector_breakdown": sector_pct,
        "top_performers":  top3,
        "bottom_performers": bottom3,
    })


# ─── Tool definitions (Anthropic format) ─────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "get_current_price",
        "description": "Get the current market price for a stock or ETF ticker symbol.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL"}
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_price_history",
        "description": "Get historical price performance for a ticker over the past N days (max 365). Returns start/end price and percentage change.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol"},
                "days":   {"type": "integer", "description": "Number of days of history (default 90, max 365)"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_ticker_info",
        "description": "Get fundamental information about a ticker: sector, industry, P/E ratio, market cap, beta, 52-week range.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol"}
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "calculate_portfolio_metrics",
        "description": "Compute aggregate portfolio metrics: total value, total return, sector allocation, top/bottom performers. Pass the full holdings list as JSON.",
        "input_schema": {
            "type": "object",
            "properties": {
                "holdings_json": {
                    "type": "string",
                    "description": 'JSON array of holding objects with keys: ticker, quantity, average_cost, current_price, current_value, return_pct, sector',
                }
            },
            "required": ["holdings_json"],
        },
    },
]


# ─── Tool dispatcher ──────────────────────────────────────────────────────────

TOOL_HANDLERS = {
    "get_current_price":          tool_get_current_price,
    "get_price_history":          tool_get_price_history,
    "get_ticker_info":            tool_get_ticker_info,
    "calculate_portfolio_metrics": tool_calculate_portfolio_metrics,
}


async def dispatch_tool(name: str, inputs: dict[str, Any]) -> str:
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {name}"})
    return await handler(**inputs)
