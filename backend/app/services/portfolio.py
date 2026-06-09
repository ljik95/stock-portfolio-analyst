"""
Portfolio service — orchestrates CSV parsing, enrichment, DB persistence, and summary computation.
"""

import json
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.models.db_models import Portfolio, Holding, Conversation, Message
from app.models.schemas import PortfolioSummary
from app.services.csv_parser import parse_robinhood_csv
from app.services.market_data import enrich_holdings


# ─── Create / import ─────────────────────────────────────────────────────────

async def import_portfolio(
    db: AsyncSession,
    csv_bytes: bytes,
    name: str = "My Portfolio",
) -> Portfolio:
    """Parse + enrich CSV, persist portfolio and holdings, return ORM object."""

    raw_holdings = parse_robinhood_csv(csv_bytes)
    enriched     = await enrich_holdings(raw_holdings)

    portfolio = Portfolio(name=name, broker="robinhood", raw_csv=csv_bytes.decode("utf-8", errors="replace"))
    db.add(portfolio)
    await db.flush()   # get portfolio.id without committing

    for h in enriched:
        db.add(Holding(portfolio_id=portfolio.id, **h))

    await db.commit()
    await db.refresh(portfolio)
    return portfolio


# ─── Read ─────────────────────────────────────────────────────────────────────

async def get_portfolio(db: AsyncSession, portfolio_id: UUID) -> Portfolio | None:
    result = await db.execute(
        select(Portfolio).where(Portfolio.id == portfolio_id)
    )
    return result.scalar_one_or_none()


async def get_holdings(db: AsyncSession, portfolio_id: UUID) -> list[Holding]:
    result = await db.execute(
        select(Holding).where(Holding.portfolio_id == portfolio_id)
    )
    return list(result.scalars().all())


# ─── Summary computation ──────────────────────────────────────────────────────

def compute_summary(holdings: list[Holding]) -> PortfolioSummary:
    total_value  = sum(h.current_value or 0 for h in holdings)
    total_cost   = sum((h.quantity or 0) * (h.average_cost or 0) for h in holdings)
    total_return = total_value - total_cost
    return_pct   = (total_return / total_cost * 100) if total_cost else 0

    sector_values: dict[str, float] = {}
    for h in holdings:
        s = h.sector or "Unknown"
        sector_values[s] = sector_values.get(s, 0) + (h.current_value or 0)
    sector_pct = {s: round(v / total_value * 100, 2) for s, v in sector_values.items()} if total_value else {}

    top = max(holdings, key=lambda h: h.current_value or 0, default=None)

    return PortfolioSummary(
        total_value=round(total_value, 2),
        total_cost=round(total_cost, 2),
        total_return=round(total_return, 2),
        total_return_pct=round(return_pct, 2),
        num_holdings=len(holdings),
        top_holding=top.ticker if top else None,
        sectors=sector_pct,
    )


def holdings_as_dict(holdings: list[Holding]) -> list[dict]:
    """Serialise holdings to plain dicts for injecting into LLM context."""
    return [
        {
            "ticker":        h.ticker,
            "name":          h.name,
            "quantity":      float(h.quantity) if h.quantity else None,
            "average_cost":  float(h.average_cost) if h.average_cost else None,
            "current_price": float(h.current_price) if h.current_price else None,
            "current_value": float(h.current_value) if h.current_value else None,
            "total_return":  float(h.total_return) if h.total_return else None,
            "return_pct":    float(h.return_pct) if h.return_pct else None,
            "sector":        h.sector,
            "asset_type":    h.asset_type,
        }
        for h in holdings
    ]


# ─── Conversation helpers ────────────────────────────────────────────────────

async def get_or_create_conversation(
    db: AsyncSession,
    portfolio_id: UUID,
    conversation_id: UUID | None,
) -> Conversation:
    if conversation_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == portfolio_id,
                Conversation.portfolio_id == portfolio_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

    conv = Conversation(portfolio_id=portfolio_id)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def get_conversation_history(
    db: AsyncSession,
    conversation_id: UUID,
) -> list[dict]:
    """Return conversation history in Anthropic message format."""
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()
    return [{"role": m.role, "content": m.content} for m in messages]


async def save_message(
    db: AsyncSession,
    conversation_id: UUID,
    role: str,
    content: str,
) -> Message:
    msg = Message(conversation_id=conversation_id, role=role, content=content)
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg
