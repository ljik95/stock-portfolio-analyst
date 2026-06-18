"""
Robinhood CSV parser.

Robinhood exports a CSV from Account → Statements → Export.
Columns vary slightly by export date; this handles both known formats.
"""

import io
from datetime import date
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

    # average cost (many Robinhood / broker export variants)
    "average cost":           "average_cost",
    "average buy price":      "average_cost",
    "avg cost":               "average_cost",
    "avg. cost":              "average_cost",
    "average cost basis":     "average_cost",
    "cost per share":         "average_cost",
    "unit cost":              "average_cost",
    "price paid":             "average_cost",

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

    # acquisition date (present in some export formats)
    "date acquired":     "purchased_at",
    "acquisition date":  "purchased_at",
    "date":              "purchased_at",
    "purchase date":     "purchased_at",
    "open date":         "purchased_at",
    "created at":        "purchased_at",
}


def parse_robinhood_csv(content: bytes) -> list[dict[str, Any]]:
    """
    Parse raw Robinhood CSV bytes and return a list of normalised holding dicts.
    Raises HTTP 422 with a descriptive message on any parse error.
    """
    try:
        text = content.decode("utf-8", errors="replace")
        df = pd.read_csv(io.StringIO(text), on_bad_lines="skip")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not read CSV file: {exc}",
        )

    # Normalise column names: lowercase + strip whitespace
    df.columns = [c.lower().strip() for c in df.columns]

    # Rename to canonical names, then drop duplicate column names that can
    # arise when the CSV has both "Instrument" and "Symbol" (both map to
    # "ticker"). Keep the first occurrence — for options, "Instrument" is
    # the full OCC symbol (len > 5) which lets _infer_asset_type work.
    df.rename(columns=COLUMN_MAP, inplace=True)
    df = df.loc[:, ~df.columns.duplicated(keep="first")]

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
            df[col] = float("nan")  # float dtype, so derived-field arithmetic below works
        else:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(r"[$,%]", "", regex=True), errors="coerce")

    # Parse acquisition date if present; leave as NaT (→ None) if column missing or unparseable
    if "purchased_at" not in df.columns:
        df["purchased_at"] = pd.NaT
    else:
        df["purchased_at"] = pd.to_datetime(df["purchased_at"], errors="coerce")

    # Drop rows with null or zero quantity — closed/expired positions and
    # summary rows that slipped through. quantity is NOT NULL in the DB.
    df = df[df["quantity"].notna() & (df["quantity"] > 0)]

    # Compute derived fields per row wherever they're missing. (Doing this
    # only when the entire column is empty leaves partially-missing rows as
    # NaN, which then count as $0 in portfolio totals.)
    df["current_value"] = df["current_value"].fillna(df["quantity"] * df["current_price"])

    # cost basis of 0 → leave derived returns as NaN rather than dividing by zero
    cost_basis = (df["quantity"] * df["average_cost"])
    cost_basis = cost_basis.where(cost_basis != 0)

    df["total_return"] = df["total_return"].fillna(df["current_value"] - cost_basis)
    df["return_pct"]   = df["return_pct"].fillna(
        ((df["current_value"] - cost_basis) / cost_basis * 100).round(4)
    )

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
            "purchased_at":  _safe_date(row.get("purchased_at")),
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


def _safe_date(value: Any) -> date | None:
    """Convert a pandas Timestamp / NaT / string to a Python date, or None."""
    try:
        ts = pd.Timestamp(value)
        return None if pd.isna(ts) else ts.date()
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
