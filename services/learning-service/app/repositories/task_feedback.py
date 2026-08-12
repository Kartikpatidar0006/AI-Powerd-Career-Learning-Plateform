"""
backend/app/repositories/task_feedback.py
===========================================
Repository pattern implementation for ``task_feedback`` table.

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

from app.models.task import TaskSubmission
from app.models.task_feedback import TaskFeedback

logger: logging.Logger = logging.getLogger(__name__)


class TaskFeedbackRepository:
    """Data-access layer for the ``task_feedback`` table.

    Args:
        session: An active SQLAlchemy ``Session``.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # =====================================================================
    #  Read operations
    # =====================================================================

    def get_by_id(self, feedback_id: uuid.UUID) -> Optional[TaskFeedback]:
        """Fetch feedback by UUID primary key.

        Args:
            feedback_id: UUID PK.

        Returns:
            The matching ``TaskFeedback`` ORM instance, or ``None``.
        """
        logger.debug("get_by_id | feedback_id=%s", feedback_id)
        return self._session.get(TaskFeedback, feedback_id)

    def get_by_submission_id(self, submission_id: uuid.UUID) -> Optional[TaskFeedback]:
        """Fetch feedback by submission UUID.

        Args:
            submission_id: UUID of the TaskSubmission.

        Returns:
            The matching ``TaskFeedback`` ORM instance, or ``None``.
        """
        logger.debug("get_by_submission_id | submission_id=%s", submission_id)
        stmt = (
            select(TaskFeedback)
            .where(TaskFeedback.submission_id == submission_id)
        )
        return self._session.execute(stmt).scalars().first()

    def list_by_user_id(
        self,
        user_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[TaskFeedback], int]:
        """Return paginated feedback records for all submissions belonging to a user.

        Args:
            user_id: UUID of the user.
            skip: Offset for pagination.
            limit: Maximum results.

        Returns:
            Tuple of (list of ``TaskFeedback`` instances, total count).
        """
        logger.debug("list_by_user_id | user_id=%s skip=%d limit=%d", user_id, skip, limit)

        # Join with TaskSubmission to filter by user_id
        base_query = (
            select(TaskFeedback)
            .join(TaskSubmission, TaskFeedback.submission_id == TaskSubmission.id)
            .where(TaskSubmission.user_id == user_id)
        )

        count_query = (
            select(func.count())
            .select_from(TaskFeedback)
            .join(TaskSubmission, TaskFeedback.submission_id == TaskSubmission.id)
            .where(TaskSubmission.user_id == user_id)
        )

        total: int = self._session.execute(count_query).scalar() or 0

        stmt = base_query.order_by(TaskFeedback.created_at.desc()).offset(skip).limit(limit)
        items: list[TaskFeedback] = list(self._session.execute(stmt).scalars().all())

        return items, total

    # =====================================================================
    #  Write operations
    # =====================================================================

    def create(self, feedback: TaskFeedback) -> TaskFeedback:
        """Persist a new feedback row.

        Args:
            feedback: Populated ``TaskFeedback`` ORM instance.

        Returns:
            The created instance with server defaults populated.
        """
        logger.debug("create | submission_id=%s", feedback.submission_id)
        try:
            self._session.add(feedback)
            self._session.flush()
            self._session.refresh(feedback)
            return feedback
        except SQLAlchemyError as exc:
            logger.error("Failed to create feedback: %s", exc, exc_info=True)
            self._session.rollback()
            raise

    def update(self, feedback: TaskFeedback) -> TaskFeedback:
        """Flush pending attribute changes on an existing feedback record.

        Args:
            feedback: Modified ``TaskFeedback`` instance.

        Returns:
            Refreshed ``TaskFeedback`` instance.
        """
        logger.debug("update | feedback.id=%s", feedback.id)
        try:
            self._session.flush()
            self._session.refresh(feedback)
            return feedback
        except SQLAlchemyError as exc:
            logger.error("Failed to update feedback: %s", exc, exc_info=True)
            self._session.rollback()
            raise
