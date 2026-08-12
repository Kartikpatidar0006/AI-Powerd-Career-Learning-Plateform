"""
services/auth-service/app/main.py
----------------------------------
FastAPI entrypoint for the Auth Service.
Handles: user registration, login, token refresh, user management.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.db.init_db import initialize_database

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("=" * 60)
    logger.info("  🔐  %s  v%s", settings.PROJECT_NAME, settings.PROJECT_VERSION)
    logger.info("  Environment : %s", settings.ENVIRONMENT)
    logger.info("=" * 60)
    initialize_database()
    logger.info("  ✓  Auth Service ready.")
    logger.info("=" * 60)
    yield
    logger.info("Auth Service shutdown complete.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="Authentication & User Management microservice.",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
    debug=settings.DEBUG,
)

# CORS — allow all internal + frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=600,
)


@app.middleware("http")
async def request_timing(request: Request, call_next: Any) -> Any:
    start = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - start) * 1000
    response.headers["X-Process-Time-Ms"] = f"{ms:.3f}"
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"success": False, "error": {"code": 422, "type": "ValidationError", "message": "Request validation failed.", "detail": exc.errors()}},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content={"success": False, "error": {"code": exc.status_code, "type": "HTTPException", "message": exc.detail, "detail": None}},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"success": False, "error": {"code": 500, "type": "InternalServerError", "message": "An internal server error occurred.", "detail": None}},
    )


# ── Routers ────────────────────────────────────────────────────────────────── #
from app.api.v1.auth.router import router as auth_router  # noqa: E402
from app.api.v1.users.router import router as users_router  # noqa: E402

app.include_router(auth_router, prefix=f"{settings.API_V1_STR}/auth", tags=["Auth"])
app.include_router(users_router, prefix=f"{settings.API_V1_STR}/users", tags=["Users"])


# ── Built-in endpoints ─────────────────────────────────────────────────────── #
@app.get("/", tags=["Root"])
async def root() -> JSONResponse:
    return JSONResponse(content={"application": settings.PROJECT_NAME, "version": settings.PROJECT_VERSION, "health": "/health"})


@app.get("/health", tags=["Health"])
async def health_check() -> JSONResponse:
    return JSONResponse(content={"status": "healthy", "application": settings.PROJECT_NAME, "version": settings.PROJECT_VERSION})
