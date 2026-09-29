"""
Auth Service — FastAPI application entry point.

Configures the FastAPI application with routers, CORS middleware,
rate limiting, and a health check endpoint for Docker container orchestration.
"""

import hmac
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.routers.auth import limiter, router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.

    Handles startup and shutdown events. Database table creation
    is managed by Alembic migrations — NOT here.
    """
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Rate limiter state — required by slowapi
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
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
    # Health checks and documentation endpoints are exempt
    if (
        request.url.path in ("/health", "/docs", "/redoc", "/openapi.json")
        or request.url.path.startswith("/internal/")
    ):
        return await call_next(request)

    token = request.headers.get("X-Gateway-Token", "")
    if not token or not hmac.compare_digest(token, settings.GATEWAY_SERVICE_TOKEN):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Forbidden: missing or invalid gateway token"},
        )
    return await call_next(request)

# Register routers
app.include_router(auth_router)


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint for Docker and load balancer probes."""
    return {"status": "healthy", "service": settings.APP_NAME}

