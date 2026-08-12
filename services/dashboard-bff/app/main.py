"""
services/dashboard-bff/app/main.py
------------------------------------
FastAPI entrypoint for the Dashboard BFF.
Aggregates data from Auth, Catalog, Learning, Interview, Progress, Notification services.
NO database of its own.
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.security import decode_token

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# JWT validation middleware for incoming requests
_PUBLIC_PATHS = {"/", "/health"}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("📈  %s v%s starting...", settings.PROJECT_NAME, settings.PROJECT_VERSION)
    logger.info("  Auth Svc    : %s", settings.AUTH_SERVICE_URL)
    logger.info("  Catalog Svc : %s", settings.CATALOG_SERVICE_URL)
    logger.info("  Learning Svc: %s", settings.LEARNING_SERVICE_URL)
    logger.info("  Interview   : %s", settings.INTERVIEW_SERVICE_URL)
    logger.info("  Progress    : %s", settings.PROGRESS_SERVICE_URL)
    logger.info("  Notif Svc   : %s", settings.NOTIFICATION_SERVICE_URL)
    logger.info("✓  Dashboard BFF ready.")
    yield
    logger.info("Dashboard BFF shutdown.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="Dashboard BFF: aggregated student dashboard view.",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
    debug=settings.DEBUG,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def jwt_middleware(request: Request, call_next: Any) -> Any:
    """Validate Bearer JWT for all non-public paths."""
    if request.url.path not in _PUBLIC_PATHS:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth.removeprefix("Bearer ").strip()
            try:
                payload = decode_token(token)
                request.state.jwt_payload = payload
            except HTTPException:
                raise
    return await call_next(request)


@app.middleware("http")
async def request_timing(request: Request, call_next: Any) -> Any:
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time-Ms"] = f"{(time.perf_counter()-start)*1000:.3f}"
    return response


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"success": False, "error": {"code": 422, "message": "Validation failed.", "detail": exc.errors()}})


@app.exception_handler(HTTPException)
async def http_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, headers=exc.headers, content={"success": False, "error": {"code": exc.status_code, "message": exc.detail}})


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled: %s", exc, exc_info=True)
    return JSONResponse(status_code=500, content={"success": False, "error": {"code": 500, "message": "Internal error."}})


# ── Routers ────────────────────────────────────────────────────────────────── #
from app.api.v1.dashboard.router import router as dashboard_router  # noqa: E402

prefix = settings.API_V1_STR
app.include_router(dashboard_router, prefix=f"{prefix}/dashboard", tags=["Dashboard"])


@app.get("/", tags=["Root"])
async def root() -> JSONResponse:
    return JSONResponse(content={"application": settings.PROJECT_NAME, "version": settings.PROJECT_VERSION})


@app.get("/health", tags=["Health"])
async def health_check() -> JSONResponse:
    return JSONResponse(content={"status": "healthy", "application": settings.PROJECT_NAME})
