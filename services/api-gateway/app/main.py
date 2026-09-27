"""
API Gateway — FastAPI application entry point.

Acts as the single entry point for the frontend, routing requests
to internal microservices. Includes CORS configuration and
request logging middleware.
"""

import logging
import time
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("api-gateway")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage the httpx async client lifecycle.

    Creates a shared httpx client on startup and closes it on shutdown
    to enable connection pooling across requests.
    """
    app.state.http_client = httpx.AsyncClient(timeout=30.0)
    logger.info("API Gateway started — httpx client initialized")
    yield
    await app.state.http_client.aclose()
    logger.info("API Gateway shutting down — httpx client closed")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ──────────────────────────────────────────────
# CORS Middleware
# ──────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────
# Request Logging Middleware
# ──────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next) -> Response:
    """
    Log all incoming requests with method, path, and response time.

    Args:
        request: The incoming HTTP request.
        call_next: The next middleware/handler in the chain.

    Returns:
        The HTTP response from downstream handlers.
    """
    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000

    logger.info(
        "%s %s → %d (%.1fms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


# ──────────────────────────────────────────────
# Health Check
# ──────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint for Docker and load balancer probes."""
    return {"status": "healthy", "service": settings.APP_NAME}


# ──────────────────────────────────────────────
# Auth Service Proxy
# ──────────────────────────────────────────────
@app.api_route(
    "/auth/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["Auth Proxy"],
    summary="Proxy to Auth Service",
)
async def proxy_auth(request: Request, path: str) -> Response:
    """
    Reverse proxy for auth-service.

    Forwards all /auth/* requests to the internal auth-service,
    preserving headers, query parameters, and request body.

    Args:
        request: The incoming client request.
        path: The path suffix after /auth/.

    Returns:
        The proxied response from auth-service.
    """
    client: httpx.AsyncClient = request.app.state.http_client
    target_url = f"{settings.AUTH_SERVICE_URL}/auth/{path}"

    # Prepare forwarded headers (exclude hop-by-hop headers)
    headers = dict(request.headers)
    headers.pop("host", None)

    try:
        body = await request.body()
        proxied_response = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=dict(request.query_params),
            content=body,
        )

        return Response(
            content=proxied_response.content,
            status_code=proxied_response.status_code,
            headers=dict(proxied_response.headers),
            media_type=proxied_response.headers.get("content-type"),
        )

    except httpx.ConnectError:
        logger.error("Failed to connect to auth-service at %s", settings.AUTH_SERVICE_URL)
        return JSONResponse(
            status_code=503,
            content={"detail": "Auth service is unavailable"},
        )
    except httpx.TimeoutException:
        logger.error("Timeout connecting to auth-service at %s", settings.AUTH_SERVICE_URL)
        return JSONResponse(
            status_code=504,
            content={"detail": "Auth service request timed out"},
        )
