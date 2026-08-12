"""
services/catalog-service/app/main.py
--------------------------------------
FastAPI entrypoint for the Catalog Service.
Handles: Professions, Skills, Career Roadmaps, Skill Gap analysis.
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
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("🗂  %s v%s starting...", settings.PROJECT_NAME, settings.PROJECT_VERSION)
    initialize_database()
    logger.info("✓  Catalog Service ready.")
    yield
    logger.info("Catalog Service shutdown.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="Catalog microservice: Professions, Skills, Career Roadmaps.",
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
async def request_timing(request: Request, call_next: Any) -> Any:
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time-Ms"] = f"{(time.perf_counter()-start)*1000:.3f}"
    return response


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"success": False, "error": {"code": 422, "type": "ValidationError", "message": "Validation failed.", "detail": exc.errors()}})


@app.exception_handler(HTTPException)
async def http_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, headers=exc.headers, content={"success": False, "error": {"code": exc.status_code, "type": "HTTPException", "message": exc.detail, "detail": None}})


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled: %s", exc, exc_info=True)
    return JSONResponse(status_code=500, content={"success": False, "error": {"code": 500, "type": "InternalServerError", "message": "Internal error.", "detail": None}})


# ── Routers ────────────────────────────────────────────────────────────────── #
from app.api.v1.professions.router import router as professions_router   # noqa: E402
from app.api.v1.skills.router import router as skills_router             # noqa: E402
from app.api.v1.career_roadmaps.router import roadmap_router, step_router  # noqa: E402

prefix = settings.API_V1_STR
app.include_router(professions_router, prefix=f"{prefix}/professions", tags=["Professions"])
app.include_router(skills_router, prefix=f"{prefix}/skills", tags=["Skills"])
app.include_router(roadmap_router, prefix=f"{prefix}/career-roadmaps", tags=["Career Roadmaps"])
app.include_router(step_router, prefix=f"{prefix}/roadmap-steps", tags=["Roadmap Steps"])


@app.get("/", tags=["Root"])
async def root() -> JSONResponse:
    return JSONResponse(content={"application": settings.PROJECT_NAME, "version": settings.PROJECT_VERSION})


@app.get("/health", tags=["Health"])
async def health_check() -> JSONResponse:
    return JSONResponse(content={"status": "healthy", "application": settings.PROJECT_NAME})
