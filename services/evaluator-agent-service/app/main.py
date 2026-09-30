"""
Evaluator Agent Service — FastAPI application entry point.

Agent 3: GitHub Repository Evaluator.

Endpoints:
Internal (not via gateway):
- POST /internal/evaluate  — Trigger evaluation pipeline (fire-and-forget)

Public (via gateway, JWT-protected):
- GET  /evaluations/{task_id}  — Student-facing evaluation result

Dev only (APP_ENV=development):
- POST /dev/evaluations/trigger/{task_id}  — Manual trigger for local testing
"""

import hmac
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.routers.evaluations import (
    internal_router,
    public_router,
    dev_router,
)

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("evaluator-agent")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup and shutdown hooks."""
    logger.info("Starting Evaluator Agent Service v%s", settings.APP_VERSION)
    logger.info("LLM Provider configured: %s", settings.LLM_PROVIDER)
    logger.info("Application environment: %s", settings.APP_ENV)
    logger.info("PASS_SCORE configured: %.0f", settings.PASS_SCORE)

    github_configured = bool(settings.GITHUB_API_TOKEN and settings.GITHUB_API_TOKEN.strip())
    logger.info("GitHub API token: %s", "configured" if github_configured else "NOT configured (using unauthenticated, 60 req/hr limit)")

    if settings.APP_ENV == "development":
        logger.warning(
            "APP_ENV=development — DEV-ONLY endpoints (/dev/*) are ACTIVE. "
            "Ensure these are never exposed in production."
        )

    yield
    logger.info("Shutting down Evaluator Agent Service")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Defense-in-depth: Require X-Gateway-Token from API Gateway for user-facing routes
@app.middleware("http")
async def verify_gateway_token_middleware(request: Request, call_next):
    """
    Require X-Gateway-Token for all public routes.

    Exempt: /health, /docs, /redoc, /openapi.json, /internal/*, /dev/*
    This ensures all user-facing requests arrive via the gateway,
    preventing direct service access bypassing JWT verification.
    """
    if (
        request.url.path in ("/health", "/docs", "/redoc", "/openapi.json")
        or request.url.path.startswith("/internal/")
        or request.url.path.startswith("/dev/")
    ):
        return await call_next(request)

    token = request.headers.get("X-Gateway-Token", "")
    if not token or not hmac.compare_digest(token, settings.GATEWAY_SERVICE_TOKEN):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Forbidden: missing or invalid gateway token"},
        )
    return await call_next(request)


# Public routes (proxied via API gateway with JWT verification)
app.include_router(public_router)

# Internal routes — never routed through the gateway
app.include_router(internal_router)

# Dev-only routes — only registered when APP_ENV=development
if settings.APP_ENV == "development":
    app.include_router(dev_router)
    logger.info("DEV endpoints registered: /dev/*")


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint for Docker and load balancer probes."""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "env": settings.APP_ENV,
    }
