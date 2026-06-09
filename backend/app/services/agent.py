"""
LLM agent service.

Wraps the Anthropic API with:
  - Tool calling (agentic loop)
  - Conversation memory (full history per session)
  - Portfolio context injection
  - LangSmith tracing via environment vars
"""

import json
import os
from typing import AsyncIterator
import anthropic
from app.core.config import settings
from app.tools.agent_tools import TOOL_DEFINITIONS, dispatch_tool

# Set LangSmith env vars before the Anthropic client is used
os.environ.setdefault("LANGCHAIN_TRACING_V2", str(settings.langchain_tracing_v2).lower())
os.environ.setdefault("LANGCHAIN_PROJECT",    settings.langchain_project)
if settings.langsmith_api_key:
    os.environ.setdefault("LANGCHAIN_API_KEY", settings.langsmith_api_key)

client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

SYSTEM_PROMPT = """You are an expert portfolio analyst assistant. The user has uploaded their investment portfolio and wants to understand their holdings, returns, risk exposure, and more.

You have access to real-time tools to fetch current prices, price history, company information, and to calculate portfolio metrics. Always use these tools rather than guessing at numbers.

Guidelines:
- Be concise and specific. Reference actual tickers and dollar amounts from the portfolio.
- When discussing returns, clarify whether they are realised or unrealised.
- When you see concentration risk or sector imbalance, mention it proactively.
- Format dollar amounts with $ and 2 decimal places. Format percentages with 2 decimal places and a % sign.
- Never give personalised financial advice or tell the user to buy/sell specific securities. You are an analyst, not an advisor.
- If the user asks something outside the portfolio domain, politely redirect them.

The user's portfolio context will be provided with each message."""


def _build_portfolio_context(portfolio_summary: dict) -> str:
    if not portfolio_summary:
        return ""
    return f"""
<portfolio_context>
{json.dumps(portfolio_summary, indent=2)}
</portfolio_context>
"""


async def run_agent(
    user_message: str,
    history: list[dict],          # [{"role": "user"|"assistant", "content": "..."}]
    portfolio_summary: dict,      # serialised holdings + metrics
) -> str:
    """
    Run one turn of the agentic loop.
    Returns the final assistant text response.
    Handles multi-step tool calling internally.
    """
    context = _build_portfolio_context(portfolio_summary)
    system  = SYSTEM_PROMPT + "\n\n" + context

    # Build message list: history + new user message
    messages = list(history) + [{"role": "user", "content": user_message}]

    # Agentic loop — keeps going until the model stops calling tools
    MAX_TOOL_ROUNDS = 5
    for _ in range(MAX_TOOL_ROUNDS):
        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1024,
            system=system,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        # If model is done, return the text
        if response.stop_reason == "end_turn":
            return _extract_text(response)

        # Process tool calls
        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = await dispatch_tool(block.name, block.input)
                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": block.id,
                        "content":     result,
                    })

            # Append assistant message + tool results to history and loop
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user",      "content": tool_results})
            continue

        # Fallback: return whatever text is there
        return _extract_text(response)

    return "I reached the maximum number of reasoning steps. Please try a simpler question."


def _extract_text(response: anthropic.types.Message) -> str:
    parts = [block.text for block in response.content if hasattr(block, "text")]
    return "\n".join(parts).strip()
