"""
backend/app/repositories/notification.py
=========================================
Repository pattern implementation for ``notifications`` table.

Architecture contract
---------------------
- **Single responsibility**: SQL queries only.
- **Session ownership**: caller (service/dependency) owns commit/rollback.
  Calls ``flush()`` after mutating operations.
- **Returns ORM objects only**.
- **Rollback on failure**: wraps mutating methods in try/except SQLAlchemyError → rollback → re-raise.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.notification import Notification

logger: logging.Logger = logging.getLogger(__name__)


class NotificationRepository:
    """Data-access layer for the ``notifications`` table.

    Args:
        session: An active SQLAlchemy ``Session``.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, notification_id: uuid.UUID) -> Optional[Notification]:
        """Fetch a notification by UUID primary key.

        Args:
            notification_id: UUID PK.

        Returns:
            Matching ``Notification`` ORM instance or ``None``.
        """
        logger.debug("get_by_id | notification_id=%s", notification_id)
        return self._session.get(Notification, notification_id)

    def list_by_user(
        self,
        user_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Notification], int, int]:
        """Return paginated notifications for a user, total count, and unread count.

        Args:
            user_id: UUID of user.
            skip: Offset.
            limit: Limit.

        Returns:
            Tuple of (list of ``Notification`` instances, total_count, unread_count).
        """
        logger.debug("list_by_user | user_id=%s skip=%d limit=%d", user_id, skip, limit)

        base_stmt = select(Notification).where(Notification.user_id == user_id)
        count_stmt = (
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id)
        )
        unread_stmt = (
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id)
            .where(Notification.is_read == False)  # noqa: E712
        )

        total: int = self._session.execute(count_stmt).scalar() or 0
        unread_count: int = self._session.execute(unread_stmt).scalar() or 0

        stmt = base_stmt.order_by(Notification.created_at.desc()).offset(skip).limit(limit)
        items: list[Notification] = list(self._session.execute(stmt).scalars().all())

        return items, total, unread_count

    def create(self, notification: Notification) -> Notification:
        """Persist a new notification.

        Args:
            notification: Populated ``Notification`` ORM instance.

        Returns:
            Created instance with server defaults populated.
        """
        logger.debug("create | user_id=%s title=%s", notification.user_id, notification.title)
        try:
            self._session.add(notification)
            self._session.flush()
            self._session.refresh(notification)
            return notification
        except SQLAlchemyError as exc:
            logger.error("Failed to create notification: %s", exc, exc_info=True)
            self._session.rollback()
            raise

    def update(self, notification: Notification) -> Notification:
        """Flush pending changes on an existing notification.

        Args:
            notification: Modified ``Notification`` instance.

        Returns:
            Refreshed instance.
        """
        logger.debug("update | notification_id=%s", notification.id)
        try:
            self._session.flush()
            self._session.refresh(notification)
            return notification
        except SQLAlchemyError as exc:
            logger.error("Failed to update notification: %s", exc, exc_info=True)
            self._session.rollback()
            raise
