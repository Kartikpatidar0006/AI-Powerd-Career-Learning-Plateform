"""
backend/app/api/v1/dashboard/router.py
======================================
FastAPI router for the Student Dashboard API.

Endpoints
---------
  GET /api/v1/dashboard/student  Student dashboard aggregated state (auth).
  GET /api/v1/dashboard/me       Alias endpoint for student dashboard (auth).
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.v1.auth.router import get_current_user
from app.db.session import get_db
from app.schemas.student_dashboard import StudentDashboardResponse
from app.schemas.user import UserResponse
from app.services.dashboard import DashboardService

logger: logging.Logger = logging.getLogger(__name__)

router = APIRouter()

DbDep = Annotated[Session, Depends(get_db)]
CurrentUserDep = Annotated[UserResponse, Depends(get_current_user)]


@router.get(
    "/student",
    response_model=StudentDashboardResponse,
    status_code=status.HTTP_200_OK,
    summary="Get aggregated student dashboard state",
    description=(
        "Retrieve complete aggregated state for student homepage: profile, profession, "
        "active roadmap, current task, latest task feedback, upcoming interview, "
        "latest interview feedback, progress metrics, and unread notifications count.\n\n"
        "**Requires authentication**."
    ),
    responses={
        200: {"description": "Student dashboard payload returned."},
        401: {"description": "Not authenticated."},
    },
)
def get_student_dashboard(
    db: DbDep,
    current_user: CurrentUserDep,
) -> StudentDashboardResponse:
    """Retrieve student aggregated dashboard payload.

    Args:
        db: Injected database session.
        current_user: Authenticated user.

    Returns:
        ``StudentDashboardResponse``.
    """
    logger.info("GET /dashboard/student | user=%s", current_user.id)
    payload = DashboardService(db).get_student_dashboard(user_id=current_user.id)
    return StudentDashboardResponse.model_validate(payload)


@router.get(
    "/me",
    response_model=StudentDashboardResponse,
    status_code=status.HTTP_200_OK,
    summary="Get authenticated student's dashboard payload (alias)",
    description="Alias endpoint for ``GET /dashboard/student``.",
)
def get_student_dashboard_me(
    db: DbDep,
    current_user: CurrentUserDep,
) -> StudentDashboardResponse:
    """Alias for student dashboard endpoint.

    Args:
        db: Database session.
        current_user: Authenticated user.

    Returns:
        ``StudentDashboardResponse``.
    """
    return get_student_dashboard(db=db, current_user=current_user)
