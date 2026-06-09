"""
Basic tests for the CSV parser and portfolio service.
Run with: pytest tests/ -v
"""

import pytest
from app.services.csv_parser import parse_robinhood_csv


SAMPLE_CSV = b"""symbol,name,quantity,average cost,last price,equity,percent return,total return
AAPL,Apple Inc,10,150.00,175.50,1755.00,17.0,255.00
MSFT,Microsoft Corp,5,280.00,415.00,2075.00,48.21,675.00
TSLA,Tesla Inc,3,220.00,185.00,555.00,-15.91,-105.00
"""

EMPTY_CSV = b"""symbol,name,quantity,average cost,last price,equity
"""

BAD_CSV = b"""foo,bar,baz
1,2,3
"""


def test_parse_valid_csv():
    holdings = parse_robinhood_csv(SAMPLE_CSV)
    assert len(holdings) == 3
    tickers = [h["ticker"] for h in holdings]
    assert "AAPL" in tickers
    assert "MSFT" in tickers
    assert "TSLA" in tickers


def test_parse_numeric_fields():
    holdings = parse_robinhood_csv(SAMPLE_CSV)
    aapl = next(h for h in holdings if h["ticker"] == "AAPL")
    assert aapl["quantity"] == 10.0
    assert aapl["average_cost"] == 150.0
    assert aapl["current_price"] == 175.50


def test_parse_negative_return():
    holdings = parse_robinhood_csv(SAMPLE_CSV)
    tsla = next(h for h in holdings if h["ticker"] == "TSLA")
    assert tsla["return_pct"] is not None
    assert tsla["return_pct"] < 0


def test_parse_bad_csv_raises():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        parse_robinhood_csv(BAD_CSV)
    assert exc.value.status_code == 422


def test_parse_empty_csv_raises():
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        parse_robinhood_csv(EMPTY_CSV)


def test_asset_type_inference():
    crypto_csv = b"symbol,name,quantity,average cost,last price,equity\nBTC,Bitcoin,0.5,30000,45000,22500\n"
    holdings = parse_robinhood_csv(crypto_csv)
    assert holdings[0]["asset_type"] == "crypto"
