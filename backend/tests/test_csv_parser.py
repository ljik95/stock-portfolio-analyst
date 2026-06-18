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


def test_derived_fields_filled_per_row():
    """Rows missing equity must get value derived from qty*price even when
    other rows have it (regression: was only computed if whole column empty)."""
    csv = (
        b"symbol,quantity,average cost,last price,equity\n"
        b"AAPL,10,150.00,175.50,1755.00\n"
        b"MSFT,5,280.00,415.00,\n"
    )
    holdings = parse_robinhood_csv(csv)
    msft = next(h for h in holdings if h["ticker"] == "MSFT")
    assert msft["current_value"] == pytest.approx(5 * 415.00)
    assert msft["total_return"] == pytest.approx(5 * 415.00 - 5 * 280.00)


def test_zero_cost_basis_no_division_error():
    csv = b"symbol,quantity,average cost,last price,equity\nFREE,10,0,5.00,50.00\n"
    holdings = parse_robinhood_csv(csv)
    assert holdings[0]["return_pct"] is None  # undefined, not inf/NaN


def test_compute_summary_ignores_missing_cost_basis():
    """Holdings without average_cost must not count as pure profit."""
    from types import SimpleNamespace
    from app.services.portfolio import compute_summary

    holdings = [
        SimpleNamespace(ticker="AAPL", quantity=10, average_cost=150.0,
                        current_value=1755.0, total_return=None, sector="Technology"),
        SimpleNamespace(ticker="BTC", quantity=0.5, average_cost=None,
                        current_value=50000.0, total_return=None, sector="Crypto"),
    ]
    s = compute_summary(holdings)
    assert s.total_value == pytest.approx(51755.0)
    assert s.total_cost == pytest.approx(1500.0)
    assert s.total_return == pytest.approx(255.0)       # AAPL only
    assert s.total_return_pct == pytest.approx(17.0)    # not ~3350%


def test_compute_summary_survives_nan_values():
    from types import SimpleNamespace
    from app.services.portfolio import compute_summary

    holdings = [
        SimpleNamespace(ticker="GOOD", quantity=1, average_cost=100.0,
                        current_value=110.0, total_return=None, sector=None),
        SimpleNamespace(ticker="BAD", quantity=1, average_cost=float("nan"),
                        current_value=float("nan"), total_return=None, sector=None),
    ]
    s = compute_summary(holdings)
    assert s.total_value == pytest.approx(110.0)
    assert s.total_return == pytest.approx(10.0)


def test_compute_summary_uses_csv_total_return_as_fallback():
    """When avg_cost is missing but CSV provided a total_return, use it.
    This covers Robinhood exports that omit the Average Cost column."""
    from types import SimpleNamespace
    from app.services.portfolio import compute_summary

    holdings = [
        # Has cost basis — contributes normally
        SimpleNamespace(ticker="AAPL", quantity=10, average_cost=150.0,
                        current_value=1755.0, total_return=None, sector="Technology"),
        # No cost basis, but CSV total_return is available
        SimpleNamespace(ticker="BTC", quantity=0.5, average_cost=None,
                        current_value=50000.0, total_return=500.0, sector="Crypto"),
    ]
    s = compute_summary(holdings)
    # total_return = AAPL's 255 + BTC's CSV 500 = 755
    assert s.total_return == pytest.approx(755.0)
    # total_cost only comes from AAPL (BTC has no cost basis)
    assert s.total_cost == pytest.approx(1500.0)
    # return_pct uses total_cost since it's available
    assert s.total_return_pct == pytest.approx(755.0 / 1500.0 * 100)


def test_compute_summary_infers_pct_when_no_cost_basis():
    """When ALL holdings lack avg_cost but have CSV total_return, infer return_pct
    from (total_value - total_return) as an implied cost."""
    from types import SimpleNamespace
    from app.services.portfolio import compute_summary

    holdings = [
        SimpleNamespace(ticker="X", quantity=1, average_cost=None,
                        current_value=110.0, total_return=10.0, sector=None),
    ]
    s = compute_summary(holdings)
    assert s.total_return == pytest.approx(10.0)
    assert s.total_cost == pytest.approx(0.0)       # no cost basis data
    # implied cost = 110 - 10 = 100, so 10/100 * 100 = 10%
    assert s.total_return_pct == pytest.approx(10.0)
