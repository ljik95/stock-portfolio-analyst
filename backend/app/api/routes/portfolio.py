from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.db.database import get_db
from app.core.security import (
    create_access_token,
    get_current_portfolio_id,
    check_rate_limit,
    get_client_ip,
    validate_csv_size,
)
from app.models.schemas import PortfolioOut, PortfolioWithSummary, HoldingOut, PortfolioValueHistory
from app.services import portfolio as portfolio_svc
from app.services.market_data import get_price_history, get_portfolio_value_history

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.post("/import", summary="Upload a Robinhood CSV and create a portfolio")
async def import_portfolio(
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(default="My Portfolio"),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a Robinhood CSV export. Returns a signed token that identifies
    this portfolio — include it as a Bearer token on all subsequent requests.
    """
    check_rate_limit(get_client_ip(request))

    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only .csv files are accepted")

    content = await file.read()
    validate_csv_size(content)

    portfolio = await portfolio_svc.import_portfolio(db, content, name=name)

    # Issue a token scoped to this portfolio
    token = create_access_token({"portfolio_id": str(portfolio.id)})

    return {"token": token, "portfolio_id": str(portfolio.id), "name": portfolio.name}


@router.get("/me", response_model=PortfolioWithSummary, summary="Get current portfolio with summary metrics")
async def get_portfolio(
    portfolio_id: str = Depends(get_current_portfolio_id),
    db: AsyncSession = Depends(get_db),
):
    portfolio = await portfolio_svc.get_portfolio(db, UUID(portfolio_id))
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    holdings = await portfolio_svc.get_holdings(db, UUID(portfolio_id))
    summary  = portfolio_svc.compute_summary(holdings)
    insights = portfolio_svc.compute_insights(holdings, summary)

    return PortfolioWithSummary(
        portfolio=PortfolioOut.model_validate(portfolio),
        summary=summary,
        insights=insights,
    )


@router.get("/me/holdings", response_model=list[HoldingOut], summary="List all holdings")
async def list_holdings(
    portfolio_id: str = Depends(get_current_portfolio_id),
    db: AsyncSession = Depends(get_db),
):
    holdings = await portfolio_svc.get_holdings(db, UUID(portfolio_id))
    return [HoldingOut.model_validate(h) for h in holdings]


@router.get("/me/history", response_model=PortfolioValueHistory, summary="Get approximate portfolio value over time")
async def get_portfolio_history(
    days: int = 90,
    portfolio_id: str = Depends(get_current_portfolio_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns an approximate total-portfolio-value time series, computed by
    applying *current* holding quantities to historical prices. Useful as a
    trend line, not a record of realised performance.
    """
    days = min(max(days, 7), 365)
    holdings = await portfolio_svc.get_holdings(db, UUID(portfolio_id))
    points   = await get_portfolio_value_history(portfolio_svc.holdings_as_dict(holdings), period_days=days)
    return PortfolioValueHistory(days=days, points=points, approximate=True)


@router.get("/me/history/{ticker}", summary="Get price history for a holding")
async def get_holding_history(
    ticker: str,
    days: int = 90,
    portfolio_id: str = Depends(get_current_portfolio_id),
):
    """Returns daily close prices for charting. Days range: 7–365."""
    days = min(max(days, 7), 365)
    history = await get_price_history(ticker.upper(), period_days=days)
    return {"ticker": ticker.upper(), "days": days, "prices": history}
