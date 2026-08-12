"""
services/dashboard-bff/app/api/v1/dashboard/router.py
-------------------------------------------------------
Dashboard BFF router — aggregates data from other services.
"""
from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/student",
    status_code=status.HTTP_200_OK,
    summary="Get aggregated student dashboard state",
    description="Aggregates data from Auth, Catalog, Learning, Interview, Progress, and Notification services.",
)
async def get_student_dashboard(request: Request) -> JSONResponse:
    """
    GET /api/v1/dashboard/student

    Aggregates all dashboard data by calling downstream microservices in parallel.
    The Authorization header is forwarded to each downstream service.
    """
    from app.services.dashboard import DashboardAggregatorService

    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header.",
        )

    # Extract user_id from JWT payload (set by the gateway middleware if present,
    # or decode here directly from the token)
    jwt_payload = getattr(request.state, "jwt_payload", None)
    if jwt_payload is None:
        # Decode locally (gateway already validated the signature)
        from app.core.security import decode_token
        token = auth_header.removeprefix("Bearer ").strip()
        jwt_payload = decode_token(token)

    try:
        user_id = uuid.UUID(str(jwt_payload["sub"]))
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject claim.",
        ) from exc

    logger.info("GET /dashboard/student | user_id=%s", user_id)

    svc = DashboardAggregatorService(auth_header=auth_header, user_id=user_id)
    payload = await svc.get_student_dashboard()
    return JSONResponse(content=payload)


@router.get(
    "/me",
    status_code=status.HTTP_200_OK,
    summary="Alias for /dashboard/student",
)
async def get_student_dashboard_me(request: Request) -> JSONResponse:
    """Alias for GET /dashboard/student."""
    return await get_student_dashboard(request)
