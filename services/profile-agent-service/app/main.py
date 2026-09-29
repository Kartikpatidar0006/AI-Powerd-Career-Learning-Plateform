"""
Profile Agent Service — FastAPI application entry point.

Configures the FastAPI application with routers, CORS middleware,
and a health check endpoint for Docker container orchestration.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import logging

import hmac
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers.profile import router as profile_router
from app.routers.internal import internal_router

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("profile-agent")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.

    Initializes resources on startup and cleans up on shutdown.
    """
    logger.info("Starting Profile Agent Service v%s", settings.APP_VERSION)
    logger.info("LLM Provider configured: %s", settings.LLM_PROVIDER)
    yield
    logger.info("Shutting down Profile Agent Service")


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
    # Health checks, openapi docs, and internal service routes are exempt
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

# Include Routers
app.include_router(profile_router)
app.include_router(internal_router)  # Service-to-service, not exposed via gateway


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint for Docker and API gateway probes."""
    return {"status": "healthy", "service": settings.APP_NAME}
