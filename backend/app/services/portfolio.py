"""
Portfolio service — orchestrates CSV parsing, enrichment, DB persistence, and summary computation.
"""

import json
import math
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.models.db_models import Portfolio, Holding, Conversation, Message
from app.models.schemas import PortfolioSummary, Insight
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

def _num(value) -> float:
    """Coerce to a finite float; NaN/inf/None (e.g. bad legacy rows) → 0."""
    try:
        f = float(value)
        return f if math.isfinite(f) else 0.0
    except (TypeError, ValueError):
        return 0.0


def compute_summary(holdings: list[Holding]) -> PortfolioSummary:
    total_value = sum(_num(h.current_value) for h in holdings)

    # Prefer computing total_return from cost basis (qty × avg_cost) to avoid
    # inflating returns. For holdings where average_cost IS available, use
    # current_value - cost. For holdings where it is NOT (some Robinhood
    # export formats omit it), fall back to the h.total_return the CSV
    # already computed and stored.
    total_cost   = 0.0
    total_return = 0.0
    for h in holdings:
        qty, avg = _num(h.quantity), _num(h.average_cost)
        if qty and avg:
            cost = qty * avg
            total_cost += cost
            if h.current_value is not None:
                total_return += _num(h.current_value) - cost
            elif h.total_return is not None:
                total_return += _num(h.total_return)
        elif h.total_return is not None:
            # No cost basis — use the pre-computed return from the CSV directly.
            total_return += _num(h.total_return)

    if total_cost:
        return_pct = total_return / total_cost * 100
    elif total_value and total_return:
        # Infer cost as (current_value − total_return) so return_pct is still
        # meaningful when the CSV provided dollar returns but no average cost.
        implied_cost = total_value - total_return
        return_pct = (total_return / implied_cost * 100) if implied_cost > 0 else 0
    else:
        return_pct = 0

    sector_values: dict[str, float] = {}
    for h in holdings:
        s = h.sector or "Unknown"
        sector_values[s] = sector_values.get(s, 0) + _num(h.current_value)
    sector_pct = {s: round(v / total_value * 100, 2) for s, v in sector_values.items()} if total_value else {}

    top = max(holdings, key=lambda h: _num(h.current_value), default=None)

    return PortfolioSummary(
        total_value=round(total_value, 2),
        total_cost=round(total_cost, 2),
        total_return=round(total_return, 2),
        total_return_pct=round(return_pct, 2),
        num_holdings=len(holdings),
        top_holding=top.ticker if top else None,
        sectors=sector_pct,
    )


# ─── Insights ─────────────────────────────────────────────────────────────────

CONCENTRATION_THRESHOLD = 25.0   # % of portfolio in a single holding
SECTOR_THRESHOLD        = 40.0   # % of portfolio in a single sector
MIN_HOLDINGS_FOR_DIVERSIFICATION_CHECK = 4
MIN_SECTORS_FOR_DIVERSIFICATION        = 3


def compute_insights(holdings: list[Holding], summary: PortfolioSummary) -> list[Insight]:
    """
    Generate plain-language observations about the portfolio. These are
    rule-based (not LLM-generated) so they're cheap, deterministic, and
    always in sync with the numbers shown on the dashboard.
    """
    insights: list[Insight] = []
    total_value = summary.total_value

    if not holdings or total_value <= 0:
        return insights

    # ── Single-position concentration ──────────────────────────────────────
    by_value = sorted(holdings, key=lambda h: _num(h.current_value), reverse=True)
    top = by_value[0]
    top_pct = _num(top.current_value) / total_value * 100
    if top_pct >= CONCENTRATION_THRESHOLD:
        insights.append(Insight(
            severity="warning",
            title=f"{top.ticker} is {top_pct:.0f}% of your portfolio",
            detail=(
                f"A single position this large means {top.ticker}'s price moves have an "
                f"outsized effect on your total value. Consider whether this concentration "
                f"is intentional."
            ),
        ))

    # ── Sector concentration ────────────────────────────────────────────────
    if summary.sectors:
        sector, pct = max(summary.sectors.items(), key=lambda kv: kv[1])
        if pct >= SECTOR_THRESHOLD and sector != "Unknown":
            insights.append(Insight(
                severity="warning",
                title=f"{sector} makes up {pct:.0f}% of your portfolio",
                detail=(
                    f"Heavy exposure to one sector means sector-wide news or downturns "
                    f"affect a large share of your holdings at once."
                ),
            ))

    # ── Diversification ─────────────────────────────────────────────────────
    if (
        summary.num_holdings >= MIN_HOLDINGS_FOR_DIVERSIFICATION_CHECK
        and len(summary.sectors) < MIN_SECTORS_FOR_DIVERSIFICATION
    ):
        insights.append(Insight(
            severity="info",
            title=f"Your portfolio spans only {len(summary.sectors)} sector(s)",
            detail=(
                f"With {summary.num_holdings} holdings concentrated in so few sectors, "
                f"a downturn in one of them would broadly affect your portfolio."
            ),
        ))

    # ── Best / worst performers ─────────────────────────────────────────────
    with_returns = [h for h in holdings if h.return_pct is not None]
    if with_returns:
        best  = max(with_returns, key=lambda h: _num(h.return_pct))
        worst = min(with_returns, key=lambda h: _num(h.return_pct))

        if _num(best.return_pct) > 0:
            insights.append(Insight(
                severity="positive",
                title=f"{best.ticker} is your top performer, up {_num(best.return_pct):.1f}%",
                detail=f"It's contributed {_fmt_money(_num(best.total_return))} to your total return.",
            ))

        if worst.ticker != best.ticker and _num(worst.return_pct) < 0:
            insights.append(Insight(
                severity="warning",
                title=f"{worst.ticker} is down {_num(worst.return_pct):.1f}%",
                detail=(
                    f"It's your biggest drag on returns, at {_fmt_money(_num(worst.total_return))}. "
                    f"Worth checking whether the original thesis still holds."
                ),
            ))

    # ── Missing cost basis ──────────────────────────────────────────────────
    missing_cost = [h.ticker for h in holdings if not _num(h.average_cost) and _num(h.quantity)]
    if missing_cost:
        names = ", ".join(missing_cost[:3]) + ("…" if len(missing_cost) > 3 else "")
        insights.append(Insight(
            severity="info",
            title=f"{len(missing_cost)} holding(s) are missing a cost basis",
            detail=(
                f"{names} don't have an average cost on file, so they're excluded from "
                f"your total return calculation. Returns shown may understate your real gains/losses."
            ),
        ))

    # ── Overall return framing ──────────────────────────────────────────────
    if summary.total_cost > 0:
        if summary.total_return_pct >= 0:
            insights.append(Insight(
                severity="positive",
                title=f"Portfolio is up {summary.total_return_pct:.1f}% overall",
                detail=f"That's {_fmt_money(summary.total_return)} in unrealised gains across positions with a known cost basis.",
            ))
        else:
            insights.append(Insight(
                severity="warning",
                title=f"Portfolio is down {abs(summary.total_return_pct):.1f}% overall",
                detail=f"That's {_fmt_money(summary.total_return)} in unrealised losses across positions with a known cost basis.",
            ))

    # Warnings first, then info, then positive
    order = {"warning": 0, "info": 1, "positive": 2}
    insights.sort(key=lambda i: order.get(i.severity, 3))
    return insights


def _fmt_money(value: float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.2f}"


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
            "purchased_at":  h.purchased_at.isoformat() if h.purchased_at else None,
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
                Conversation.id == conversation_id,
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
