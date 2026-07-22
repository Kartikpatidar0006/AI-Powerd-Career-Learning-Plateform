"""
backend/app/main.py
--------------------
FastAPI application entry point for AI Career Hub.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT LIVES HERE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  • Logging configuration          — structured, level-aware
  • Application lifespan           — startup + shutdown via @asynccontextmanager
  • Middleware registration         — CORS, request timing
  • Global exception handlers       — catch-all + HTTP exception override
  • API router mounting             — all v1 feature routers
  • Built-in endpoints              — GET / and GET /health

WHAT DOES NOT LIVE HERE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  • Business logic      → app/services/
  • ORM / DB queries    → app/repositories/
  • Route handlers      → app/api/v1/<feature>/router.py
  • Data models (ORM)   → app/models/
  • Pydantic schemas    → app/schemas/

RUNNING THE SERVER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Development:
      uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

  Production (Docker):
      CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000",
           "--workers", "4", "--log-level", "info"]
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


# =========================================================================== #
#  Logging — configure once at module level before anything else              #
# =========================================================================== #
# Use structured format: timestamp | level | logger name | message.
# Level is DEBUG in dev (shows SQL queries, pool events) and INFO in prod.
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger: logging.Logger = logging.getLogger(__name__)


# =========================================================================== #
#  Lifespan — startup and shutdown hooks                                       #
# =========================================================================== #

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    FastAPI lifespan context manager (replaces deprecated @app.on_event).

    Everything BEFORE `yield` runs at startup.
    Everything AFTER  `yield` runs at shutdown.

    Startup sequence
    ----------------
    1. Log application identity and environment.
    2. Run database bootstrap (connection check + table creation).
    3. Signal readiness.

    Shutdown sequence
    -----------------
    1. Log shutdown intent.
    2. Perform graceful cleanup (extend here: Redis, S3, MQ connections).
    3. Signal shutdown complete.
    """
    # ── STARTUP ─────────────────────────────────────────────────────────── #
    logger.info("━" * 60)
    logger.info("  🚀  %s  v%s", settings.PROJECT_NAME, settings.PROJECT_VERSION)
    logger.info("  Environment : %s", settings.ENVIRONMENT)
    logger.info("  Debug mode  : %s", settings.DEBUG)
    logger.info("  API prefix  : %s", settings.API_V1_STR)
    logger.info("  Docs        : %s/docs", settings.API_V1_STR)
    logger.info("━" * 60)

    # Database bootstrap: verify connectivity + create tables if needed.
    initialize_database()

    logger.info("━" * 60)
    logger.info("  ✓  Application startup complete — ready to serve requests.")
    logger.info("━" * 60)

    yield  # ← Application is live and handling requests here.

    # ── SHUTDOWN ─────────────────────────────────────────────────────────── #
    logger.info("━" * 60)
    logger.info("  ⏳  Shutting down %s...", settings.PROJECT_NAME)

    # Add graceful cleanup here as the project grows:
    # await redis_client.close()
    # await message_queue.disconnect()
    # scheduler.shutdown()

    logger.info("  ✓  Shutdown complete. Goodbye.")
    logger.info("━" * 60)


# =========================================================================== #
#  Application factory                                                          #
# =========================================================================== #

def create_application() -> FastAPI:
    """
    Build and return a fully configured FastAPI application instance.

    Separating construction into a factory function rather than using bare
    module-level code provides two key benefits:

      1. Testability — test suites call `create_application()` to get a
         fresh, isolated app without sharing state between test cases.
      2. Clarity — every configuration concern is explicit and visible
         in one place.

    Returns
    -------
    FastAPI
        A fully configured application ready to be served by uvicorn.
    """

    # ── Core application ─────────────────────────────────────────────────── #
    application = FastAPI(
        # ---- Identity ----
        title=settings.PROJECT_NAME,
        version=settings.PROJECT_VERSION,
        description=settings.PROJECT_DESCRIPTION,

        # ---- OpenAPI / Docs ----
        # Swagger UI  → /api/v1/docs
        # ReDoc       → /api/v1/redoc
        # OpenAPI JSON→ /api/v1/openapi.json
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",

        # ---- Contact / License (visible in Swagger UI) ----
        contact={
            "name": "AI Career Hub — Backend Team",
            "url": "https://github.com/Kartikpatidar0006/AI-Powerd-Career-Learning-Plateform",
        },
        license_info={
            "name": "MIT",
        },

        # ---- Lifecycle ----
        lifespan=lifespan,

        # ---- Debug — exposes internal error details; OFF in production ----
        debug=settings.DEBUG,
    )

    # ── Middleware ────────────────────────────────────────────────────────── #
    _register_middleware(application)

    # ── Exception Handlers ────────────────────────────────────────────────── #
    _register_exception_handlers(application)

    # ── API Routers ───────────────────────────────────────────────────────── #
    _register_routers(application)

    return application


# =========================================================================== #
#  Middleware registration                                                       #
# =========================================================================== #

def _register_middleware(app: FastAPI) -> None:
    """
    Attach all middleware to the application.

    Order matters — middleware is applied in reverse registration order
    (last registered = outermost wrapper around the request).
    Register CORS first so it wraps everything.
    """

    # ── 1. CORS ──────────────────────────────────────────────────────────── #
    # Must be registered BEFORE any other middleware.
    # Allowed origins are loaded from BACKEND_CORS_ORIGINS in .env.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Process-Time-Ms", "X-Request-ID"],
        # Cache preflight response for 10 minutes to reduce OPTIONS round-trips.
        max_age=600,
    )
    logger.debug(
        "CORS enabled for origins: %s", settings.BACKEND_CORS_ORIGINS
    )

    # ── 2. Request timing ────────────────────────────────────────────────── #
    # Adds X-Process-Time-Ms header to every response.
    # Zero external dependencies — pure Python.
    @app.middleware("http")
    async def request_timing_middleware(request: Request, call_next: Any) -> Any:
        start: float = time.perf_counter()
        response = await call_next(request)
        duration_ms: float = (time.perf_counter() - start) * 1000
        response.headers["X-Process-Time-Ms"] = f"{duration_ms:.3f}"
        logger.debug(
            "%s %s → %s | %.3fms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response


# =========================================================================== #
#  Exception handler registration                                               #
# =========================================================================== #

def _register_exception_handlers(app: FastAPI) -> None:
    """
    Register global exception handlers.

    These handlers normalise all error responses into a consistent JSON
    envelope so API consumers never see raw FastAPI or Python tracebacks.

    Response envelope shape:
        {
            "success": false,
            "error": {
                "code": <HTTP status code>,
                "type": "<error class name>",
                "message": "<human-readable message>",
                "detail": <optional structured detail>
            }
        }
    """

    # ── Pydantic validation errors (422 Unprocessable Entity) ────────────── #
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """
        Normalise Pydantic v2 validation errors into a structured response.
        FastAPI's default 422 body is verbose; this makes it consistent.
        """
        logger.warning(
            "Validation error on %s %s: %s",
            request.method,
            request.url.path,
            exc.errors(),
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error": {
                    "code": status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "type": "ValidationError",
                    "message": "Request validation failed.",
                    "detail": exc.errors(),
                },
            },
        )

    # ── HTTPException (4xx / 5xx raised by route handlers) ───────────────── #
    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        """
        Override FastAPI's default HTTPException response shape for consistency.
        """
        logger.warning(
            "HTTP %s on %s %s: %s",
            exc.status_code,
            request.method,
            request.url.path,
            exc.detail,
        )
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={
                "success": False,
                "error": {
                    "code": exc.status_code,
                    "type": "HTTPException",
                    "message": exc.detail,
                    "detail": None,
                },
            },
        )

    # ── Catch-all: unhandled exceptions (500 Internal Server Error) ───────── #
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """
        Last-resort handler for any exception not caught by route handlers.

        In production (DEBUG=False) this suppresses internal details.
        In development  (DEBUG=True)  the message includes the exception type.

        NOTE: Always investigate and handle exceptions specifically in
        service/repository layers — this is a safety net, not a strategy.
        """
        logger.error(
            "Unhandled exception on %s %s: %s",
            request.method,
            request.url.path,
            exc,
            exc_info=True,
        )
        # Never expose internal error details in production.
        message = (
            f"[{type(exc).__name__}] An internal server error occurred."
            if settings.DEBUG
            else "An unexpected internal server error occurred. Please try again later."
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "type": "InternalServerError",
                    "message": message,
                    "detail": None,
                },
            },
        )


# =========================================================================== #
#  Router registration                                                          #
# =========================================================================== #

def _register_routers(app: FastAPI) -> None:
    """
    Mount all API v1 feature routers onto the application.

    Convention
    ----------
    Every router is imported INSIDE this function (lazy import) to:
      • Avoid circular import issues at module load time.
      • Keep startup explicit — you can see exactly which routers are active.
      • Allow partial registration during development.

    Router status
    -------------
    ✅ ACTIVE   — router file has a valid `router` object; imported live.
    🔲 PENDING  — router file is empty or not yet implemented; commented out.
                  Uncomment the import + include_router line when ready.
    """

    prefix = settings.API_V1_STR  # /api/v1

    # ── ✅ Users ──────────────────────────────────────────────────────────── #
    from app.api.v1.users.router import router as users_router
    app.include_router(
        users_router,
        prefix=f"{prefix}/users",
        tags=["Users"],
    )

    # ── ✅ Dashboard ──────────────────────────────────────────────────────── #
    from app.api.v1.dashboard.router import router as dashboard_router
    app.include_router(
        dashboard_router,
        prefix=f"{prefix}/dashboard",
        tags=["Dashboard"],
    )

    # ── ✅ Interviews ─────────────────────────────────────────────────────── #
    from app.api.v1.interviews.router import router as interviews_router
    app.include_router(
        interviews_router,
        prefix=f"{prefix}/interviews",
        tags=["Interviews"],
    )

    # ── ✅ Professions ────────────────────────────────────────────────────── #
    from app.api.v1.professions.router import router as professions_router
    app.include_router(
        professions_router,
        prefix=f"{prefix}/professions",
        tags=["Professions"],
    )

    # ── ✅ Resume ─────────────────────────────────────────────────────────── #
    from app.api.v1.resume.router import router as resume_router
    app.include_router(
        resume_router,
        prefix=f"{prefix}/resume",
        tags=["Resume"],
    )

    # ── ✅ Tasks ──────────────────────────────────────────────────────────── #
    from app.api.v1.tasks.router import router as tasks_router
    app.include_router(
        tasks_router,
        prefix=f"{prefix}/tasks",
        tags=["Tasks"],
    )

    # ── ✅ Auth ────────────────────────────────────────────────────────────── #
    from app.api.v1.auth.router import router as auth_router
    app.include_router(auth_router, prefix=f"{prefix}/auth", tags=["Auth"])

    # ── 🔲 AI — PENDING (router file is empty) ────────────────────────────── #
    # Uncomment when app/api/v1/ai/router.py is implemented:
    # from app.api.v1.ai.router import router as ai_router
    # app.include_router(ai_router, prefix=f"{prefix}/ai", tags=["AI"])

    logger.debug(
        "Routers registered: auth, users, dashboard, interviews, professions, resume, tasks"
    )


# =========================================================================== #
#  Module-level app instance — uvicorn / gunicorn entry point                  #
# =========================================================================== #

app: FastAPI = create_application()


# =========================================================================== #
#  Built-in endpoints                                                           #
# =========================================================================== #

@app.get(
    "/",
    tags=["Root"],
    summary="API root",
    include_in_schema=True,
)
async def root() -> JSONResponse:
    """
    GET /

    Welcome endpoint. Returns API identity information.
    Useful for quickly confirming the server is reachable and identifying
    the deployed version.
    """
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "application": settings.PROJECT_NAME,
            "version": settings.PROJECT_VERSION,
            "environment": settings.ENVIRONMENT,
            "docs": f"{settings.API_V1_STR}/docs",
            "redoc": f"{settings.API_V1_STR}/redoc",
            "health": "/health",
        },
    )


@app.get(
    "/health",
    tags=["Health"],
    summary="Health check",
    description=(
        "Liveness probe endpoint. Returns 200 OK when the application process "
        "is running. Used by load balancers, Kubernetes liveness probes, and "
        "uptime monitors. Does not check database or external service status "
        "(use a readiness probe endpoint for that, added later)."
    ),
    response_description="Application health status",
)
async def health_check() -> JSONResponse:
    """
    GET /health

    Returns 200 OK with service identity as long as the process is alive.

    Response schema
    ---------------
    {
        "status":      "healthy",
        "application": "AI Career Hub",
        "version":     "1.0.0"
    }
    """
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "healthy",
            "application": settings.PROJECT_NAME,
            "version": settings.PROJECT_VERSION,
        },
    )
