from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import time
import logging

from app.core.config import settings
from app.api.routes import portfolio, chat

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Portfolio Analyst API",
    description="Conversational AI portfolio analysis powered by Claude.",
    version="1.0.0",
    # Disable docs in production
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url="/redoc" if settings.environment == "development" else None,
)

# ─── Request logging ─────────────────────────────────────────────────────────
# Registered FIRST so it ends up innermost — CORS (registered last) wraps it
# and will attach its headers to every response, including error ones.

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        response = JSONResponse(
            status_code=500,
            content={"detail": "An unexpected error occurred. Please try again."},
        )
    duration = round((time.time() - start) * 1000, 1)
    logger.info(f"{request.method} {request.url.path} → {response.status_code} ({duration}ms)")
    if "server" in response.headers:
        del response.headers["server"]
    return response


# ─── Security middleware ──────────────────────────────────────────────────────
# NOTE: Starlette applies middleware in reverse-registration order — the LAST
# call to add_middleware becomes the outermost layer. Register CORS last so it
# wraps log_requests and adds its headers to ALL responses, including errors.

# Only allow requests from known hosts in production
if settings.environment == "production":
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["your-domain.com", "*.railway.app"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ─── Global error handler ─────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again."},
    )


# ─── Routes ───────────────────────────────────────────────────────────────────

app.include_router(portfolio.router, prefix="/api/v1")
app.include_router(chat.router,      prefix="/api/v1")


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "environment": settings.environment}
