"""
API Gateway — FastAPI application entry point.

Acts as the single entry point for the frontend, routing requests
to internal microservices. Includes CORS configuration and
request logging middleware.

Week 3 changes:
- Added ROADMAP_SERVICE_URL to route /roadmap/* and /tasks/*
- Generic proxy_authenticated() helper eliminates copy-paste across routes
- Added blocking of /internal/* and /dev/* at the gateway level
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
# Block /internal/* and /dev/* at the gateway
# ──────────────────────────────────────────────
@app.api_route(
    "/internal/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["Blocked Routes"],
    include_in_schema=False,
)
async def block_internal(path: str) -> JSONResponse:
    """
    Block all /internal/* requests at the gateway.

    Internal endpoints are for service-to-service communication only
    and must never be reachable from external clients.
    """
    logger.warning("Gateway blocked /internal/%s — this path is not externally accessible", path)
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": "Not found"},
    )


@app.api_route(
    "/dev/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["Blocked Routes"],
    include_in_schema=False,
)
async def block_dev(path: str) -> JSONResponse:
    """
    Block all /dev/* requests at the gateway.

    Dev endpoints are only accessible directly on the service port
    in development environments and must never be proxied externally.
    """
    logger.warning("Gateway blocked /dev/%s — this path is not externally accessible", path)
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": "Not found"},
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
# Per-User Rate Limiter for Expensive LLM Routes
# (3 requests per minute per user on /roadmap/generate and /tasks/next)
# ──────────────────────────────────────────────
import threading

class UserRateLimiter:
    """Thread-safe sliding-window rate limiter per user ID and endpoint."""

    def __init__(self, max_requests: int = 3, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._history: dict[str, list[float]] = {}

    def is_allowed(self, user_id: str, endpoint: str) -> tuple[bool, int]:
        key = f"{user_id}:{endpoint}"
        now = time.time()
        with self._lock:
            timestamps = self._history.get(key, [])
            cutoff = now - self.window_seconds
            valid = [t for t in timestamps if t > cutoff]
            if len(valid) >= self.max_requests:
                retry_after = max(1, int(self.window_seconds - (now - valid[0])))
                self._history[key] = valid
                return False, retry_after
            valid.append(now)
            self._history[key] = valid
            return True, 0


rate_limiter = UserRateLimiter(max_requests=3, window_seconds=60.0)


# ──────────────────────────────────────────────
# Generic Authenticated Proxy Helper
# (Refactored to eliminate copy-paste across routes)
# ──────────────────────────────────────────────
async def proxy_authenticated(
    request: Request,
    target_url: str,
    service_name: str,
    timeout: float = 45.0,
    rate_limit_endpoint: str | None = None,
) -> Response:
    """
    Generic authenticated reverse proxy with JWT enforcement, defense-in-depth token,
    and trusted X-User-Id injection.

    Enforces JWT verification, strips client-supplied X-User-Id to prevent spoofing,
    injects verified user_id and X-Gateway-Token header, and checks rate limits.

    Args:
        request: Incoming client request.
        target_url: Full URL of the downstream service endpoint.
        service_name: Human-readable service name for error messages.
        timeout: Request timeout in seconds.
        rate_limit_endpoint: Name of the endpoint if rate limiting applies.

    Returns:
        Proxied response from the downstream service.
    """
    # 1. Enforce JWT authentication and extract user_id
    user_id = extract_and_verify_user_id(request)

    # 2. Check per-user rate limit for expensive endpoints (e.g. 3/min)
    if rate_limit_endpoint:
        allowed, retry_after = rate_limiter.is_allowed(user_id, rate_limit_endpoint)
        if not allowed:
            logger.warning("User %s rate limited on %s (retry after %ss)", user_id, rate_limit_endpoint, retry_after)
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Maximum 3 requests per minute for this endpoint."},
                headers={"Retry-After": str(retry_after)},
            )

    client: httpx.AsyncClient = request.app.state.http_client

    # 3. Forward headers, strip client-supplied X-User-Id and X-Gateway-Token, inject trusted headers
    forward_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "x-user-id", "x-gateway-token")
    }
    forward_headers["X-User-Id"] = user_id
    forward_headers["X-Gateway-Token"] = settings.GATEWAY_SERVICE_TOKEN

    try:
        body = await request.body()
        proxied_response = await client.request(
            method=request.method,
            url=target_url,
            headers=forward_headers,
            params=dict(request.query_params),
            content=body,
            timeout=timeout,
        )

        return Response(
            content=proxied_response.content,
            status_code=proxied_response.status_code,
            headers=dict(proxied_response.headers),
            media_type=proxied_response.headers.get("content-type"),
        )

    except httpx.ConnectError:
        logger.error(
            "Failed to connect to %s at %s", service_name, target_url
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": f"{service_name} is unavailable"},
        )
    except httpx.TimeoutException:
        logger.error(
            "Timeout connecting to %s at %s", service_name, target_url
        )
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={"detail": f"{service_name} request timed out"},
        )


# ──────────────────────────────────────────────
# Auth Service Proxy (unauthenticated)
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

    # Prepare forwarded headers (exclude hop-by-hop headers, strip client tokens, inject gateway token)
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "x-user-id", "x-gateway-token")
    }
    headers["X-Gateway-Token"] = settings.GATEWAY_SERVICE_TOKEN

    try:
        body = await request.body()
        proxied_response = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=dict(request.query_params),
            content=body,
            timeout=settings.DEFAULT_TIMEOUT,
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
    """
    timeout = settings.LLM_ROUTE_TIMEOUT if path.rstrip("/") == "onboarding" else settings.DEFAULT_TIMEOUT
    return await proxy_authenticated(
        request=request,
        target_url=f"{settings.PROFILE_SERVICE_URL}/profile/{path}",
        service_name="Profile agent service",
        timeout=timeout,
    )


# ──────────────────────────────────────────────
# Roadmap Service Proxy (Authenticated)
# ──────────────────────────────────────────────
@app.api_route(
    "/roadmap/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["Roadmap Proxy"],
    summary="Authenticated Proxy to Roadmap Agent Service",
)
async def proxy_roadmap(request: Request, path: str) -> Response:
    """
    Authenticated reverse proxy for roadmap-agent-service (/roadmap/* routes).
    Applies per-user rate limit (3/min) and LLM-extended timeout on /roadmap/generate.
    """
    is_generate = request.method == "POST" and path.rstrip("/") == "generate"
    timeout = settings.LLM_ROUTE_TIMEOUT if is_generate else settings.DEFAULT_TIMEOUT
    rate_endpoint = "/roadmap/generate" if is_generate else None

    return await proxy_authenticated(
        request=request,
        target_url=f"{settings.ROADMAP_SERVICE_URL}/roadmap/{path}",
        service_name="Roadmap agent service",
        timeout=timeout,
        rate_limit_endpoint=rate_endpoint,
    )


# ──────────────────────────────────────────────
# Tasks Service Proxy (Authenticated)
# ──────────────────────────────────────────────
@app.api_route(
    "/tasks/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["Tasks Proxy"],
    summary="Authenticated Proxy to Roadmap Agent Service (Tasks)",
)
async def proxy_tasks(request: Request, path: str) -> Response:
    """
    Authenticated reverse proxy for roadmap-agent-service (/tasks/* routes).
    Applies per-user rate limit (3/min) on expensive endpoints (/tasks/next and /tasks/*/submit).
    """
    is_next = request.method == "POST" and path.rstrip("/") == "next"
    is_submit = request.method == "POST" and path.rstrip("/").endswith("/submit")
    timeout = settings.LLM_ROUTE_TIMEOUT if is_next else settings.DEFAULT_TIMEOUT
    rate_endpoint = "/tasks/next" if is_next else ("/tasks/submit" if is_submit else None)

    return await proxy_authenticated(
        request=request,
        target_url=f"{settings.ROADMAP_SERVICE_URL}/tasks/{path}",
        service_name="Roadmap agent service",
        timeout=timeout,
        rate_limit_endpoint=rate_endpoint,
    )


# ──────────────────────────────────────────────
# Evaluator Service Proxy (Authenticated)
# ──────────────────────────────────────────────
@app.api_route(
    "/evaluations/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["Evaluations Proxy"],
    summary="Authenticated Proxy to Evaluator Agent Service (Agent 3)",
)
async def proxy_evaluations(request: Request, path: str) -> Response:
    """
    Authenticated reverse proxy for evaluator-agent-service (/evaluations/* routes).
    Standard timeout — evaluation results are pre-computed by the background pipeline.
    """
    return await proxy_authenticated(
        request=request,
        target_url=f"{settings.EVALUATOR_SERVICE_URL}/evaluations/{path}",
        service_name="Evaluator agent service",
        timeout=settings.DEFAULT_TIMEOUT,
    )

