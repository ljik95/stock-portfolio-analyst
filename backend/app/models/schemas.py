from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional


# ─── Holdings ────────────────────────────────────────────────────────────────

class HoldingOut(BaseModel):
    id: UUID
    ticker: str
    name: Optional[str]
    quantity: float
    average_cost: Optional[float]
    current_price: Optional[float]
    current_value: Optional[float]
    total_return: Optional[float]
    return_pct: Optional[float]
    sector: Optional[str]
    asset_type: str
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── Portfolio ────────────────────────────────────────────────────────────────

class PortfolioCreate(BaseModel):
    name: str = "My Portfolio"
    broker: str = "robinhood"


class PortfolioOut(BaseModel):
    id: UUID
    name: str
    broker: str
    imported_at: datetime
    created_at: datetime
    holdings: list[HoldingOut] = []

    class Config:
        from_attributes = True


class PortfolioSummary(BaseModel):
    """High-level stats returned with the portfolio."""
    total_value: float
    total_cost: float
    total_return: float
    total_return_pct: float
    num_holdings: int
    top_holding: Optional[str]
    sectors: dict[str, float]        # sector -> % allocation


class PortfolioWithSummary(BaseModel):
    portfolio: PortfolioOut
    summary: PortfolioSummary


# ─── Chat ────────────────────────────────────────────────────────────────────

class MessageOut(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationOut(BaseModel):
    id: UUID
    portfolio_id: UUID
    created_at: datetime
    messages: list[MessageOut] = []

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: Optional[UUID] = None   # None = start new conversation


class ChatResponse(BaseModel):
    conversation_id: UUID
    message: MessageOut


# ─── Market Data ────────────────────────────────────────────────────────────

class PricePoint(BaseModel):
    date: str
    close: float
    volume: Optional[int]


class TickerHistory(BaseModel):
    ticker: str
    prices: list[PricePoint]
