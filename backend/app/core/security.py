"""
Security utilities.

For a portfolio project this uses simple API-key auth.
Swap out for OAuth/JWT (e.g. NextAuth + FastAPI) when ready to add multi-user support.
"""

import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, Security, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from app.core.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


# ─── JWT (stateless session tokens) ─────────────────────────────────────────

def create_access_token(data: dict, expires_delta: timedelta = timedelta(days=7)) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + expires_delta
    payload["iat"] = datetime.utcnow()
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


async def get_current_portfolio_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> str:
    """
    FastAPI dependency.
    For now, the token payload carries the portfolio_id directly.
    Extend this when you add user accounts.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(credentials.credentials)
    portfolio_id = payload.get("portfolio_id")
    if not portfolio_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    return portfolio_id


# ─── Rate limiting (in-memory, good enough for solo portfolio project) ───────

from collections import defaultdict
import time

_rate_limit_store: dict[str, list[float]] = defaultdict(list)

RATE_LIMIT_REQUESTS = 30   # requests
RATE_LIMIT_WINDOW   = 60   # seconds


def check_rate_limit(identifier: str) -> None:
    """Sliding window rate limiter. Raises 429 if exceeded."""
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    requests = _rate_limit_store[identifier]

    # Evict old entries
    _rate_limit_store[identifier] = [t for t in requests if t > window_start]

    if len(_rate_limit_store[identifier]) >= RATE_LIMIT_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW}s",
            headers={"Retry-After": str(RATE_LIMIT_WINDOW)},
        )

    _rate_limit_store[identifier].append(now)


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ─── Input sanitization ──────────────────────────────────────────────────────

import re

TICKER_RE = re.compile(r"^[A-Z]{1,10}$")

def validate_ticker(ticker: str) -> str:
    """Ensure ticker is a safe uppercase symbol, e.g. AAPL."""
    clean = ticker.upper().strip()
    if not TICKER_RE.match(clean):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid ticker: {ticker}")
    return clean


MAX_CSV_BYTES = 5 * 1024 * 1024  # 5 MB

def validate_csv_size(content: bytes) -> None:
    if len(content) > MAX_CSV_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="CSV file too large (max 5 MB)",
        )
