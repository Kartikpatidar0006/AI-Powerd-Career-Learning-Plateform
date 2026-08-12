"""
backend/app/repositories/interview.py
=======================================
Repository pattern implementation for ``interviews`` table.

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

logger: logging.Logger = logging.getLogger(__name__)


class InterviewRepository:
    """Data-access layer for the ``interviews`` table.

    Args:
        session: An active SQLAlchemy ``Session``.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # =====================================================================
    #  Read operations
    # =====================================================================

    def get_by_id(self, interview_id: uuid.UUID) -> Optional[Interview]:
        """Fetch an interview by UUID primary key.

        Args:
            interview_id: UUID PK.

        Returns:
            The matching ``Interview`` ORM instance, or ``None``.
        """
        logger.debug("get_by_id | interview_id=%s", interview_id)
        return self._session.get(Interview, interview_id)

    def get_by_user_and_task(
        self,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
    ) -> Optional[Interview]:
        """Fetch an existing active interview for a specific user and task.

        Args:
            user_id: UUID of the learner.
            task_id: UUID of the task.

        Returns:
            The matching ``Interview`` or ``None``.
        """
        logger.debug("get_by_user_and_task | user_id=%s task_id=%s", user_id, task_id)
        stmt = (
            select(Interview)
            .where(Interview.user_id == user_id)
            .where(Interview.task_id == task_id)
            .where(Interview.status != "Cancelled")
        )
        return self._session.execute(stmt).scalars().first()

    def list_by_user(
        self,
        user_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Interview], int]:
        """Return paginated interviews for a user.

        Args:
            user_id: UUID of the user.
            skip: Pagination offset.
            limit: Maximum results.

        Returns:
            Tuple of (list of ``Interview`` instances, total count).
        """
        logger.debug("list_by_user | user_id=%s skip=%d limit=%d", user_id, skip, limit)

        base_stmt = select(Interview).where(Interview.user_id == user_id)
        count_stmt = (
            select(func.count())
            .select_from(Interview)
            .where(Interview.user_id == user_id)
        )

        total: int = self._session.execute(count_stmt).scalar() or 0

        stmt = base_stmt.order_by(Interview.scheduled_at.desc()).offset(skip).limit(limit)
        items: list[Interview] = list(self._session.execute(stmt).scalars().all())

        return items, total

    # =====================================================================
    #  Write operations
    # =====================================================================

    def create(self, interview: Interview) -> Interview:
        """Persist a new interview row.

        Args:
            interview: Populated ``Interview`` ORM instance.

        Returns:
            The created instance with server defaults populated.
        """
        logger.debug("create | user_id=%s task_id=%s", interview.user_id, interview.task_id)
        try:
            self._session.add(interview)
            self._session.flush()
            self._session.refresh(interview)
            return interview
        except SQLAlchemyError as exc:
            logger.error("Failed to create interview: %s", exc, exc_info=True)
            self._session.rollback()
            raise

    def update(self, interview: Interview) -> Interview:
        """Flush pending attribute changes on an existing interview record.

        Args:
            interview: Modified ``Interview`` instance.

        Returns:
            Refreshed ``Interview`` instance.
        """
        logger.debug("update | interview.id=%s", interview.id)
        try:
            self._session.flush()
            self._session.refresh(interview)
            return interview
        except SQLAlchemyError as exc:
            logger.error("Failed to update interview: %s", exc, exc_info=True)
            self._session.rollback()
            raise
