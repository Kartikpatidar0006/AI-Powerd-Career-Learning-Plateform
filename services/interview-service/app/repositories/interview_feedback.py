"""
backend/app/repositories/interview_feedback.py
================================================
Repository pattern implementation for ``interview_feedback`` table.

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

from app.models.interview import Interview
from app.models.interview_feedback import InterviewFeedback

logger: logging.Logger = logging.getLogger(__name__)


class InterviewFeedbackRepository:
    """Data-access layer for the ``interview_feedback`` table.

    Args:
        session: An active SQLAlchemy ``Session``.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # =====================================================================
    #  Read operations
    # =====================================================================

    def get_by_id(self, feedback_id: uuid.UUID) -> Optional[InterviewFeedback]:
        """Fetch feedback by UUID primary key.

        Args:
            feedback_id: UUID PK.

        Returns:
            The matching ``InterviewFeedback`` ORM instance, or ``None``.
        """
        logger.debug("get_by_id | feedback_id=%s", feedback_id)
        return self._session.get(InterviewFeedback, feedback_id)

    def get_by_interview_id(self, interview_id: uuid.UUID) -> Optional[InterviewFeedback]:
        """Fetch feedback by interview UUID.

        Args:
            interview_id: UUID of the Interview.

        Returns:
            The matching ``InterviewFeedback`` ORM instance, or ``None``.
        """
        logger.debug("get_by_interview_id | interview_id=%s", interview_id)
        stmt = (
            select(InterviewFeedback)
            .where(InterviewFeedback.interview_id == interview_id)
        )
        return self._session.execute(stmt).scalars().first()

    def list_by_user_id(
        self,
        user_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[InterviewFeedback], int]:
        """Return paginated interview feedback records for a user.

        Args:
            user_id: UUID of the user.
            skip: Offset for pagination.
            limit: Maximum results.

        Returns:
            Tuple of (list of ``InterviewFeedback`` instances, total count).
        """
        logger.debug("list_by_user_id | user_id=%s skip=%d limit=%d", user_id, skip, limit)

        base_query = (
            select(InterviewFeedback)
            .join(Interview, InterviewFeedback.interview_id == Interview.id)
            .where(Interview.user_id == user_id)
        )

        count_query = (
            select(func.count())
            .select_from(InterviewFeedback)
            .join(Interview, InterviewFeedback.interview_id == Interview.id)
            .where(Interview.user_id == user_id)
        )

        total: int = self._session.execute(count_query).scalar() or 0

        stmt = base_query.order_by(InterviewFeedback.created_at.desc()).offset(skip).limit(limit)
        items: list[InterviewFeedback] = list(self._session.execute(stmt).scalars().all())

        return items, total

    # =====================================================================
    #  Write operations
    # =====================================================================

    def create(self, feedback: InterviewFeedback) -> InterviewFeedback:
        """Persist a new interview feedback row.

        Args:
            feedback: Populated ``InterviewFeedback`` ORM instance.

        Returns:
            The created instance with server defaults populated.
        """
        logger.debug("create | interview_id=%s", feedback.interview_id)
        try:
            self._session.add(feedback)
            self._session.flush()
            self._session.refresh(feedback)
            return feedback
        except SQLAlchemyError as exc:
            logger.error("Failed to create interview feedback: %s", exc, exc_info=True)
            self._session.rollback()
            raise

    def update(self, feedback: InterviewFeedback) -> InterviewFeedback:
        """Flush pending attribute changes on an existing feedback record.

        Args:
            feedback: Modified ``InterviewFeedback`` instance.

        Returns:
            Refreshed ``InterviewFeedback`` instance.
        """
        logger.debug("update | feedback.id=%s", feedback.id)
        try:
            self._session.flush()
            self._session.refresh(feedback)
            return feedback
        except SQLAlchemyError as exc:
            logger.error("Failed to update interview feedback: %s", exc, exc_info=True)
            self._session.rollback()
            raise
