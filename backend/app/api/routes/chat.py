import json
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.db.database import get_db
from app.core.security import get_current_portfolio_id, check_rate_limit, get_client_ip
from app.models.schemas import ChatRequest, ChatResponse, MessageOut, ConversationOut
from app.services import portfolio as portfolio_svc
from app.services.agent import run_agent

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse, summary="Send a message to the portfolio analyst")
async def chat(
    request: Request,
    body: ChatRequest,
    portfolio_id: str = Depends(get_current_portfolio_id),
    db: AsyncSession = Depends(get_db),
):
    # Rate limit chat more strictly (LLM calls cost money)
    check_rate_limit(f"chat:{get_client_ip(request)}")

    pid = UUID(portfolio_id)

    # Get or create conversation
    conv = await portfolio_svc.get_or_create_conversation(db, pid, body.conversation_id)

    # Load conversation history and portfolio context
    history  = await portfolio_svc.get_conversation_history(db, conv.id)
    holdings = await portfolio_svc.get_holdings(db, pid)
    summary  = portfolio_svc.compute_summary(holdings)

    portfolio_context = {
        "summary":  summary.model_dump(),
        "holdings": portfolio_svc.holdings_as_dict(holdings),
    }

    # Save user message
    await portfolio_svc.save_message(db, conv.id, "user", body.message)

    # Run LLM agent
    try:
        reply = await run_agent(
            user_message=body.message,
            history=history,
            portfolio_summary=portfolio_context,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI service error: {str(exc)}")

    # Save assistant message
    saved_msg = await portfolio_svc.save_message(db, conv.id, "assistant", reply)

    return ChatResponse(
        conversation_id=conv.id,
        message=MessageOut.model_validate(saved_msg),
    )


@router.get("/conversations", response_model=list[ConversationOut], summary="List past conversations")
async def list_conversations(
    portfolio_id: str = Depends(get_current_portfolio_id),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from app.models.db_models import Conversation
    result = await db.execute(
        select(Conversation)
        .where(Conversation.portfolio_id == UUID(portfolio_id))
        .order_by(Conversation.created_at.desc())
        .limit(20)
    )
    return [ConversationOut.model_validate(c) for c in result.scalars().all()]
