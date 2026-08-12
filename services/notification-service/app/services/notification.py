"""
backend/app/services/notification.py
======================================
Business-logic service layer for Notifications.

What this module does
---------------------
Provides ``NotificationService`` to handle:
  1. Creating user notifications for events (tasks, interviews, progress, reminders).
  2. Listing user notifications (paginated + unread count).
  3. Marking notifications as read.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.repositories.notification import NotificationRepository

logger: logging.Logger = logging.getLogger(__name__)


class NotificationError(Exception):
    """Business-rule violation raised by NotificationService.

    Code constants:
        ``NOT_FOUND``    — notification UUID does not exist.
        ``UNAUTHORIZED`` — user does not own notification.
    """

    NOT_FOUND: str = "not_found"
    UNAUTHORIZED: str = "unauthorized"

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code

    def __repr__(self) -> str:
        return f"NotificationError(code={self.code!r}, message={self.message!r})"


class NotificationService:
    """Service managing learner notification lifecycle.

    Args:
        db: An active SQLAlchemy ``Session``.
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = NotificationRepository(db)

    def create_notification(
        self,
        user_id: uuid.UUID,
        title: str,
        message: str,
        type_: str = "Task",
    ) -> Notification:
        """Create a new notification for a user.

        Args:
            user_id: UUID of recipient user.
            title: Headline / title.
            message: Body text.
            type_: 'Task', 'Interview', 'Progress', or 'Reminder'.

        Returns:
            Created ``Notification`` instance.
        """
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=type_,
            is_read=False,
        )
        notification = self._repo.create(notification)
        self._db.commit()
        logger.info("Created notification id=%s type=%s for user=%s", notification.id, type_, user_id)
        return notification

    def list_user_notifications(
        self,
        user_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Notification], int, int]:
        """List notifications for the authenticated user.

        Args:
            user_id: UUID of user.
            skip: Pagination offset.
            limit: Maximum results.

        Returns:
            Tuple of (list of notifications, total count, unread count).
        """
        return self._repo.list_by_user(user_id, skip=skip, limit=limit)

    def mark_as_read(
        self,
        notification_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Notification:
        """Mark a notification as read.

        Args:
            notification_id: UUID of notification.
            user_id: UUID of requesting user.

        Returns:
            Updated ``Notification`` instance with is_read=True.

        Raises:
            NotificationError: NOT_FOUND if notification missing.
            NotificationError: UNAUTHORIZED if not owned by user.
        """
        notification = self._repo.get_by_id(notification_id)
        if notification is None:
            raise NotificationError(
                f"Notification with id '{notification_id}' not found.",
                code=NotificationError.NOT_FOUND,
            )

        if notification.user_id != user_id:
            raise NotificationError(
                "You do not have permission to modify this notification.",
                code=NotificationError.UNAUTHORIZED,
            )

        notification.is_read = True
        notification = self._repo.update(notification)
        self._db.commit()
        logger.info("Marked notification id=%s as read for user=%s", notification_id, user_id)
        return notification
