"""
gateway/app/main.py
--------------------
FastAPI API Gateway — single entry point for the AI Career Hub frontend.

Responsibilities:
  1. JWT validation middleware (stateless, uses shared SECRET_KEY)
  2. Reverse-proxy all /api/v1/* requests to the correct microservice
  3. Health check at GET /health
  4. CORS headers so the React frontend can reach it
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.security import validate_jwt_middleware
from app.routing.proxy import close_http_client, proxy_request

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("=" * 60)
    logger.info("  🚀  %s  v%s", settings.PROJECT_NAME, settings.PROJECT_VERSION)
    logger.info("  Environment : %s", settings.ENVIRONMENT)
    logger.info("  Auth Svc    : %s", settings.AUTH_SERVICE_URL)
    logger.info("  Catalog Svc : %s", settings.CATALOG_SERVICE_URL)
    logger.info("  Learning Svc: %s", settings.LEARNING_SERVICE_URL)
    logger.info("  Interview   : %s", settings.INTERVIEW_SERVICE_URL)
    logger.info("  Progress    : %s", settings.PROGRESS_SERVICE_URL)
    logger.info("  Notif Svc   : %s", settings.NOTIFICATION_SERVICE_URL)
    logger.info("  Dashboard   : %s", settings.DASHBOARD_SERVICE_URL)
    logger.info("=" * 60)
    yield
    await close_http_client()
    logger.info("Gateway shutdown complete.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="API Gateway — single entry point for the AI Career Hub platform.",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
    debug=settings.DEBUG,
)

# ── CORS ──────────────────────────────────────────────────────────────────── #
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Process-Time-Ms"],
    max_age=600,
)


# ── Request timing middleware ─────────────────────────────────────────────── #
@app.middleware("http")
async def request_timing(request: Request, call_next: Any) -> Any:
    start = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - start) * 1000
    response.headers["X-Process-Time-Ms"] = f"{ms:.3f}"
    logger.debug(
        "%s %s → %s | %.1fms",
        request.method, request.url.path, response.status_code, ms
    )
    return response


# ── JWT validation middleware ─────────────────────────────────────────────── #
@app.middleware("http")
async def jwt_auth_middleware(request: Request, call_next: Any) -> Any:
    return await validate_jwt_middleware(request, call_next)


# ── Built-in endpoints ────────────────────────────────────────────────────── #

@app.get("/", tags=["Root"], summary="Gateway root")
async def root() -> JSONResponse:
    return JSONResponse(content={
        "application": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
        "environment": settings.ENVIRONMENT,
        "health": "/health",
        "docs": f"{settings.API_V1_STR}/docs",
    })


@app.get("/health", tags=["Health"], summary="Gateway health check")
async def health_check() -> JSONResponse:
    return JSONResponse(content={
        "status": "healthy",
        "application": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
    })


# ── Catch-all proxy route ────────────────────────────────────────────────── #
# This MUST be the last route registered.
# It forwards every unmatched /api/v1/* request to the appropriate service.

@app.api_route(
    "/api/v1/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    include_in_schema=False,
)
async def api_proxy(request: Request, path: str) -> Any:
    """Catch-all reverse proxy for all /api/v1/* routes."""
    return await proxy_request(request)
