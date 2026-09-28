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

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
from jose import JWTError, jwt

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


# ──────────────────────────────────────────────
# JWT Verification Helper
# ──────────────────────────────────────────────
def extract_and_verify_user_id(request: Request) -> str:
    """
    Extract and verify JWT access token from Authorization header.

    Validates signature, expiration, and token type before extracting
    the user UUID subject claim.

    Args:
        request: Incoming HTTP request.

    Returns:
        User UUID string extracted from the 'sub' claim.

    Raises:
        HTTPException(401): If token is missing, expired, or invalid.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
        )

    token = auth_header[7:].strip()
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )

        # Enforce that only short-lived access tokens are accepted for API calls
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type — access token required",
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token payload missing subject identifier",
            )

        return str(user_id)

    except JWTError as exc:
        logger.warning("Gateway rejected invalid/expired JWT: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
        ) from exc


# ──────────────────────────────────────────────
# Profile Service Proxy (Authenticated)
# ──────────────────────────────────────────────
@app.api_route(
    "/profile/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["Profile Proxy"],
    summary="Authenticated Proxy to Profile Agent Service",
)
async def proxy_profile(request: Request, path: str) -> Response:
    """
    Authenticated reverse proxy for profile-agent-service.

    Enforces JWT verification at the gateway layer BEFORE forwarding.
    Extracts the user_id from the verified token and forwards it via
    the trusted internal header 'X-User-Id'. Strips any spoofed client
    'X-User-Id' headers before dispatching downstream.

    Args:
        request: Incoming client request.
        path: Path suffix after /profile/.

    Returns:
        Proxied response from profile-agent-service.
    """
    # 1. Enforce JWT authentication and extract user_id
    user_id = extract_and_verify_user_id(request)

    client: httpx.AsyncClient = request.app.state.http_client
    target_url = f"{settings.PROFILE_SERVICE_URL}/profile/{path}"

    # 2. Forward headers, strip client-supplied X-User-Id, and inject trusted header
    forward_headers = dict(request.headers)
    forward_headers.pop("host", None)
    forward_headers.pop("x-user-id", None)  # Strip spoofed header if present
    forward_headers["X-User-Id"] = user_id

    try:
        body = await request.body()
        proxied_response = await client.request(
            method=request.method,
            url=target_url,
            headers=forward_headers,
            params=dict(request.query_params),
            content=body,
            timeout=45.0,  # Generous timeout to allow LLM processing
        )

        return Response(
            content=proxied_response.content,
            status_code=proxied_response.status_code,
            headers=dict(proxied_response.headers),
            media_type=proxied_response.headers.get("content-type"),
        )

    except httpx.ConnectError:
        logger.error(
            "Failed to connect to profile-agent-service at %s",
            settings.PROFILE_SERVICE_URL,
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Profile agent service is unavailable"},
        )
    except httpx.TimeoutException:
        logger.error(
            "Timeout connecting to profile-agent-service at %s",
            settings.PROFILE_SERVICE_URL,
        )
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={"detail": "Profile agent service request timed out"},
        )
