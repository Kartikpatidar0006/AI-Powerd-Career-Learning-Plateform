"""
backend/app/api/v1/notifications/router.py
============================================
FastAPI router for the Notification System feature.

Endpoints
---------
  GET   /api/v1/notifications/me                List user's notifications (auth).
  GET   /api/v1/users/me/notifications          List user's notifications (auth).
  PATCH /api/v1/notifications/{notification_id}/read Mark notification as read (auth).

Architecture contract
---------------------
  ✓ Delegates logic to ``NotificationService``.
  ✓ Maps ``NotificationError`` domain exceptions to ``HTTPException``.
  ✓ Enforces authentication via ``get_current_user``.
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.auth.router import get_current_user
from app.db.session import get_db
from app.schemas.notification import NotificationListResponse, NotificationResponse
from app.schemas.user import UserResponse
from app.services.notification import NotificationError, NotificationService

logger: logging.Logger = logging.getLogger(__name__)

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Error code → HTTP status mapping
# ─────────────────────────────────────────────────────────────────────────────

_NOTIFICATION_ERROR_STATUS: dict[str, int] = {
    NotificationError.NOT_FOUND: status.HTTP_404_NOT_FOUND,
    NotificationError.UNAUTHORIZED: status.HTTP_403_FORBIDDEN,
}


def _raise_http(exc: NotificationError) -> None:
    """Convert a ``NotificationError`` into an ``HTTPException`` and raise it.

    Args:
        exc: The domain exception.

    Raises:
        HTTPException: Always.
    """
    http_status = _NOTIFICATION_ERROR_STATUS.get(
        exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR
    )
    if http_status == status.HTTP_500_INTERNAL_SERVER_ERROR:
        logger.error(
            "Unmapped NotificationError code '%s' fell through to 500: %s",
            exc.code,
            exc.message,
        )
    raise HTTPException(status_code=http_status, detail=exc.message)


# ─────────────────────────────────────────────────────────────────────────────
# Dependency aliases
# ─────────────────────────────────────────────────────────────────────────────

DbDep = Annotated[Session, Depends(get_db)]
CurrentUserDep = Annotated[UserResponse, Depends(get_current_user)]


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/me",
    response_model=NotificationListResponse,
    status_code=status.HTTP_200_OK,
    summary="List authenticated user's notifications",
    description=(
        "Retrieve a paginated list of notifications for the authenticated user, "
        "including total count and unread count.\n\n"
        "**Requires authentication**."
    ),
    responses={
        200: {"description": "User notifications list returned."},
        401: {"description": "Not authenticated."},
    },
)
def get_my_notifications(
    db: DbDep,
    current_user: CurrentUserDep,
    skip: int = Query(0, ge=0, description="Offset for pagination."),
    limit: int = Query(20, ge=1, le=100, description="Max results."),
) -> NotificationListResponse:
    """Retrieve notifications for the authenticated user.

    Args:
        db: Injected database session.
        current_user: Authenticated user.
        skip: Pagination offset.
        limit: Pagination limit.

    Returns:
        ``NotificationListResponse``.
    """
    logger.info("GET /notifications/me | user=%s", current_user.id)
    items, total, unread_count = NotificationService(db).list_user_notifications(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in items],
        total=total,
        unread_count=unread_count,
        skip=skip,
        limit=limit,
    )


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark a notification as read",
    description=(
        "Mark a specific notification as read.\n\n"
        "**Requires authentication** — user must own the notification."
    ),
    responses={
        200: {"description": "Notification marked as read."},
        401: {"description": "Not authenticated."},
        403: {"description": "Notification belongs to another user."},
        404: {"description": "Notification not found."},
    },
)
def mark_notification_read(
    notification_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUserDep,
) -> NotificationResponse:
    """Mark notification as read.

    Args:
        notification_id: UUID of the notification.
        db: Injected database session.
        current_user: Authenticated user.

    Returns:
        Updated ``NotificationResponse``.
    """
    logger.info("PATCH /notifications/%s/read | user=%s", notification_id, current_user.id)
    try:
        notification = NotificationService(db).mark_as_read(
            notification_id=notification_id,
            user_id=current_user.id,
        )
        return NotificationResponse.model_validate(notification)
    except NotificationError as exc:
        _raise_http(exc)
