"""
Robinhood CSV parser.

Robinhood exports a CSV from Account → Statements → Export.
Columns vary slightly by export date; this handles both known formats.
"""

import io
import pandas as pd
from typing import Any
from fastapi import HTTPException, status


# Known Robinhood CSV column aliases → our canonical names
COLUMN_MAP = {
    # ticker
    "symbol":            "ticker",
    "instrument":        "ticker",

    # name
    "name":              "name",
    "simple name":       "name",

    # quantity
    "quantity":          "quantity",
    "shares held":       "quantity",

    # average cost
    "average cost":      "average_cost",
    "average buy price": "average_cost",
    "avg cost":          "average_cost",

    # current price
    "last price":        "current_price",
    "current price":     "current_price",
    "price":             "current_price",

    # equity / current value
    "equity":            "current_value",
    "market value":      "current_value",
    "total value":       "current_value",

    # return fields (optional, computed if missing)
    "total return":      "total_return",
    "return":            "total_return",
    "percent return":    "return_pct",
    "return %":          "return_pct",
}


def parse_robinhood_csv(content: bytes) -> list[dict[str, Any]]:
    """
    Parse raw Robinhood CSV bytes and return a list of normalised holding dicts.
    Raises HTTP 422 with a descriptive message on any parse error.
    """
    try:
        text = content.decode("utf-8", errors="replace")
        df = pd.read_csv(io.StringIO(text))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not read CSV file: {exc}",
        )

    # Normalise column names: lowercase + strip whitespace
    df.columns = [c.lower().strip() for c in df.columns]

    # Rename to canonical names
    df.rename(columns=COLUMN_MAP, inplace=True)

    if "ticker" not in df.columns:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="CSV does not look like a Robinhood export — no symbol/ticker column found.",
        )

    # Drop rows where ticker is blank (Robinhood adds summary rows at the bottom)
    df = df[df["ticker"].notna() & (df["ticker"].str.strip() != "")]

    # Ensure required numeric columns exist; fill with None if absent
    for col in ("quantity", "average_cost", "current_price", "current_value", "total_return", "return_pct"):
        if col not in df.columns:
            df[col] = None
        else:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(r"[$,%]", "", regex=True), errors="coerce")

    # Compute derived fields if missing
    if df["current_value"].isna().all() and not df["quantity"].isna().all():
        df["current_value"] = df["quantity"] * df["current_price"]

    if df["total_return"].isna().all() and not df["average_cost"].isna().all():
        cost_basis = df["quantity"] * df["average_cost"]
        df["total_return"] = df["current_value"] - cost_basis

    if df["return_pct"].isna().all() and not df["average_cost"].isna().all():
        cost_basis = df["quantity"] * df["average_cost"]
        df["return_pct"] = ((df["current_value"] - cost_basis) / cost_basis * 100).round(4)

    holdings = []
    for _, row in df.iterrows():
        holdings.append({
            "ticker":        str(row["ticker"]).upper().strip(),
            "name":          str(row.get("name", "")) or None,
            "quantity":      _safe_float(row.get("quantity")),
            "average_cost":  _safe_float(row.get("average_cost")),
            "current_price": _safe_float(row.get("current_price")),
            "current_value": _safe_float(row.get("current_value")),
            "total_return":  _safe_float(row.get("total_return")),
            "return_pct":    _safe_float(row.get("return_pct")),
            "asset_type":    _infer_asset_type(str(row["ticker"])),
        })

    if not holdings:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No holdings found in the uploaded CSV.",
        )

    return holdings


def _safe_float(value: Any) -> float | None:
    try:
        f = float(value)
        return None if pd.isna(f) else f
    except (TypeError, ValueError):
        return None


def _infer_asset_type(ticker: str) -> str:
    """Best-effort asset type from ticker format."""
    t = ticker.upper()
    if len(t) > 5:
        return "option"
    if t in ("BTC", "ETH", "DOGE", "SOL", "AVAX", "MATIC"):
        return "crypto"
    # Common ETF suffixes are just regular tickers; yfinance will clarify later
    return "stock"
