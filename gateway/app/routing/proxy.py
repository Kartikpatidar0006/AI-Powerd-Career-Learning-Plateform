"""
gateway/app/routing/proxy.py
-----------------------------
Reverse-proxy logic for the API Gateway.

Uses httpx.AsyncClient to forward requests to the appropriate downstream
microservice, streaming the response back to the client.

Route table
-----------
  /api/v1/auth/*           → AUTH_SERVICE_URL
  /api/v1/users/*          → AUTH_SERVICE_URL
  /api/v1/professions/*    → CATALOG_SERVICE_URL
  /api/v1/skills/*         → CATALOG_SERVICE_URL
  /api/v1/career-roadmaps/*→ CATALOG_SERVICE_URL
  /api/v1/roadmap-steps/*  → CATALOG_SERVICE_URL
  /api/v1/learning-paths/* → LEARNING_SERVICE_URL
  /api/v1/courses/*        → LEARNING_SERVICE_URL
  /api/v1/tasks/*          → LEARNING_SERVICE_URL
  /api/v1/resume/*         → LEARNING_SERVICE_URL
  /api/v1/interviews/*     → INTERVIEW_SERVICE_URL
  /api/v1/ai/*             → INTERVIEW_SERVICE_URL
  /api/v1/user-progress/*  → PROGRESS_SERVICE_URL
  /api/v1/notifications/*  → NOTIFICATION_SERVICE_URL
  /api/v1/dashboard/*      → DASHBOARD_SERVICE_URL
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import HTTPException, Request, status
from fastapi.responses import Response, StreamingResponse

from app.core.config import settings

logger = logging.getLogger(__name__)

def _get_route_table() -> list[tuple[str, str]]:
    return [
        ("/api/v1/career-roadmaps", settings.CATALOG_SERVICE_URL),
        ("/api/v1/roadmap-steps",   settings.CATALOG_SERVICE_URL),
        ("/api/v1/learning-paths",  settings.LEARNING_SERVICE_URL),
        ("/api/v1/user-progress",   settings.PROGRESS_SERVICE_URL),
        ("/api/v1/notifications",   settings.NOTIFICATION_SERVICE_URL),
        ("/api/v1/dashboard",       settings.DASHBOARD_SERVICE_URL),
        ("/api/v1/professions",     settings.CATALOG_SERVICE_URL),
        ("/api/v1/skills",          settings.CATALOG_SERVICE_URL),
        ("/api/v1/courses",         settings.LEARNING_SERVICE_URL),
        ("/api/v1/tasks",           settings.LEARNING_SERVICE_URL),
        ("/api/v1/resume",          settings.LEARNING_SERVICE_URL),
        ("/api/v1/interviews",      settings.INTERVIEW_SERVICE_URL),
        ("/api/v1/auth",            settings.AUTH_SERVICE_URL),
        ("/api/v1/users",           settings.AUTH_SERVICE_URL),
        ("/api/v1/ai",              settings.INTERVIEW_SERVICE_URL),
    ]


def _resolve_upstream(path: str) -> str | None:
    """Return the upstream base URL for the given request path, or None."""
    for prefix, base_url in _get_route_table():
        if path.startswith(prefix):
            return base_url
    return None


# Module-level shared AsyncClient (connection pool reuse)
_http_client: httpx.AsyncClient | None = None


async def get_http_client() -> httpx.AsyncClient:
    """Return (and lazily create) the shared httpx async client."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=settings.HTTP_TIMEOUT,
            follow_redirects=False,
        )
    return _http_client


async def close_http_client() -> None:
    """Close the shared httpx client. Called on application shutdown."""
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None


# ── Hop-by-hop & proxy headers that must NOT be forwarded ─────────────────── #
_HOP_BY_HOP = frozenset([
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
    "content-length",  # httpx recalculates this
    "access-control-allow-origin",
    "access-control-allow-credentials",
    "access-control-allow-methods",
    "access-control-allow-headers",
])


async def proxy_request(request: Request) -> Response:
    """
    Forward the incoming request to the appropriate upstream service.

    Steps:
        1. Resolve upstream URL from the route table.
        2. Build a new httpx request (method, URL, headers, body).
        3. Stream the upstream response back to the client.
        4. Map connection errors to 502 Bad Gateway.
    """
    path = request.url.path
    upstream_base = _resolve_upstream(path)

    if upstream_base is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No upstream service configured for path: {path}",
        )

    # Build target URL preserving path and query string
    query = request.url.query
    target_url = f"{upstream_base}{path}"
    if query:
        target_url = f"{target_url}?{query}"

    # Forward all client headers except hop-by-hop
    forward_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in _HOP_BY_HOP
    }

    # Read body (for POST/PUT/PATCH)
    body = await request.body()

    client = await get_http_client()

    try:
        upstream_response = await client.request(
            method=request.method,
            url=target_url,
            headers=forward_headers,
            content=body,
        )
    except httpx.ConnectError as exc:
        logger.error("Cannot reach upstream %s: %s", upstream_base, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream service unavailable: {upstream_base}",
        )
    except httpx.TimeoutException as exc:
        logger.error("Upstream %s timed out: %s", upstream_base, exc)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Upstream service timed out.",
        )

    # Strip hop-by-hop headers from the upstream response
    response_headers = {
        k: v for k, v in upstream_response.headers.items()
        if k.lower() not in _HOP_BY_HOP
    }

    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=response_headers,
        media_type=upstream_response.headers.get("content-type"),
    )
