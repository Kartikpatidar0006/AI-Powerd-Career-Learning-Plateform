"""
backend/app/repositories/user_progress.py
==========================================
Repository pattern implementation for the ``user_progress`` table.

Architecture contract
---------------------
- **Single responsibility**: SQL only.  No business logic, no schema
  validation, no password or JWT handling.
- **Session ownership**: the caller (service or ``get_db`` dependency) owns
  commit / rollback / close.  This repository calls ``flush()`` after
  mutating operations to surface ``IntegrityError`` early and resolve
  server-side defaults before returning.
- **Returns ORM objects only**: ``UserProgress`` instances or
  ``list[UserProgress]`` or primitives (``bool``, ``int``).
- **Rollback on failure**: every mutating method wraps its work in
  ``try/except SQLAlchemyError`` → rollback → re-raise.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.user_progress import UserProgress

logger: logging.Logger = logging.getLogger(__name__)


class UserProgressRepository:
    """Data-access layer for the ``user_progress`` table.

    All public methods issue exactly one logical SQL statement (SELECT, INSERT,
    UPDATE).  PATCH semantics (only non-``None`` fields updated) are handled
    in ``update_progress`` so that the service layer passes values directly.

    Args:
        session: An active SQLAlchemy ``Session``.  The caller is responsible
            for committing or rolling back after each service-level operation.

    Example::

        repo = UserProgressRepository(db)
        record = repo.get_by_id(some_uuid)
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # =========================================================================
    #  Read operations
    # =========================================================================

    def get_by_id(self, progress_id: uuid.UUID) -> Optional[UserProgress]:
        """Fetch a progress record by UUID primary key using the identity map.

        Args:
            progress_id: The UUID PK of the record to retrieve.

        Returns:
            The matching ``UserProgress`` ORM instance, or ``None``.
        """
        logger.debug("get_by_id | progress_id=%s", progress_id)
        return self._session.get(UserProgress, progress_id)

    def get_by_user_and_skill(
        self,
        user_id: uuid.UUID,
        skill_id: uuid.UUID,
    ) -> Optional[UserProgress]:
        """Fetch the progress record for a specific (user, skill) pair.

        Used for uniqueness checking before INSERT and for fast targeted
        retrieval.  The UNIQUE DB constraint guarantees at most one row.

        Args:
            user_id: UUID of the user.
            skill_id: UUID of the skill.

        Returns:
            The matching ``UserProgress`` ORM instance, or ``None``.
        """
        logger.debug(
            "get_by_user_and_skill | user_id=%s | skill_id=%s",
            user_id, skill_id,
        )
        stmt = (
            select(UserProgress)
            .where(UserProgress.user_id == user_id)
            .where(UserProgress.skill_id == skill_id)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def progress_exists_for_user_skill(
        self,
        user_id: uuid.UUID,
        skill_id: uuid.UUID,
        *,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> bool:
        """Check whether a progress record already exists for (user, skill).

        Args:
            user_id: UUID of the user.
            skill_id: UUID of the skill.
            exclude_id: UUID of the record to exclude from the check.
                Pass this when validating an update on an existing row.

        Returns:
            ``True`` if a matching record exists, else ``False``.
        """
        logger.debug(
            "progress_exists_for_user_skill | user_id=%s | skill_id=%s"
            " | exclude_id=%s",
            user_id, skill_id, exclude_id,
        )
        stmt = (
            select(func.count())
            .select_from(UserProgress)
            .where(UserProgress.user_id == user_id)
            .where(UserProgress.skill_id == skill_id)
        )
        if exclude_id is not None:
            stmt = stmt.where(UserProgress.id != exclude_id)
        count: int = self._session.execute(stmt).scalar_one()
        return count > 0

    def list_progress(
        self,
        *,
        user_id: Optional[uuid.UUID] = None,
        skill_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[UserProgress]:
        """Return a paginated list of progress records with optional filters.

        Results are ordered by ``updated_at`` descending so the most
        recently active records appear first — the most useful default for
        a learner's dashboard.

        Args:
            user_id: Filter to progress records for this user.
                ``None`` = return records across all users.
            skill_id: Filter to progress records for this skill.
                ``None`` = return records across all skills.
            status: Filter by lifecycle status (e.g. ``'IN_PROGRESS'``).
                ``None`` = return all statuses.
            skip: Row offset for pagination.  Must be >= 0.
            limit: Max rows to return.  Defaults to 50; capped by the caller.

        Returns:
            A (possibly empty) list of ``UserProgress`` ORM instances.
        """
        logger.debug(
            "list_progress | user_id=%s | skill_id=%s | status=%s"
            " | skip=%d | limit=%d",
            user_id, skill_id, status, skip, limit,
        )
        stmt = select(UserProgress).order_by(UserProgress.updated_at.desc())

        if user_id is not None:
            stmt = stmt.where(UserProgress.user_id == user_id)
        if skill_id is not None:
            stmt = stmt.where(UserProgress.skill_id == skill_id)
        if status is not None:
            stmt = stmt.where(UserProgress.status == status)

        stmt = stmt.offset(skip).limit(limit)
        return list(self._session.execute(stmt).scalars().all())

    def count_progress(
        self,
        *,
        user_id: Optional[uuid.UUID] = None,
        skill_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
    ) -> int:
        """Return the total count matching the given filters.

        Used alongside ``list_progress`` to build pagination metadata.

        Args:
            user_id: Same filter semantics as ``list_progress``.
            skill_id: Same filter semantics as ``list_progress``.
            status: Same filter semantics as ``list_progress``.

        Returns:
            Integer count of matching rows.
        """
        stmt = select(func.count()).select_from(UserProgress)
        if user_id is not None:
            stmt = stmt.where(UserProgress.user_id == user_id)
        if skill_id is not None:
            stmt = stmt.where(UserProgress.skill_id == skill_id)
        if status is not None:
            stmt = stmt.where(UserProgress.status == status)
        return self._session.execute(stmt).scalar_one()

    def get_completion_stats(self, user_id: uuid.UUID) -> dict:
        """Return skill-status counts for a given user.

        Executes a single aggregation query.  Returns a dict with
        ``total``, ``not_started``, ``in_progress``, and ``completed``
        counts — useful for dashboard widgets.

        Args:
            user_id: UUID of the user to aggregate over.

        Returns:
            Dict with integer counts per status bucket.
        """
        from sqlalchemy import case

        stmt = (
            select(
                func.count().label("total"),
                func.count(
                    case((UserProgress.status == "NOT_STARTED", 1))
                ).label("not_started"),
                func.count(
                    case((UserProgress.status == "IN_PROGRESS", 1))
                ).label("in_progress"),
                func.count(
                    case((UserProgress.status == "COMPLETED", 1))
                ).label("completed"),
            )
            .select_from(UserProgress)
            .where(UserProgress.user_id == user_id)
        )
        row = self._session.execute(stmt).one()
        return {
            "total": row.total,
            "not_started": row.not_started,
            "in_progress": row.in_progress,
            "completed": row.completed,
        }

    # =========================================================================
    #  Write operations
    # =========================================================================

    def create_progress(
        self,
        *,
        user_id: uuid.UUID,
        skill_id: uuid.UUID,
        status: str = "NOT_STARTED",
        progress_percentage: int = 0,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        last_accessed: Optional[datetime] = None,
        time_spent_minutes: int = 0,
    ) -> UserProgress:
        """Persist a new user progress row and return the ORM instance.

        Calls ``flush()`` so that server-side defaults (``created_at``,
        ``updated_at``) are written back to the object before returning.
        The caller must commit the session.

        Args:
            user_id: UUID of the owning User (FK).
            skill_id: UUID of the Skill being tracked (FK).
            status: Initial lifecycle status string.
            progress_percentage: Initial completion percentage (0–100).
            started_at: Optional first-interaction timestamp.
            completed_at: Optional completion timestamp.
            last_accessed: Optional last-access timestamp.
            time_spent_minutes: Initial cumulative time in minutes.

        Returns:
            The freshly created ``UserProgress`` ORM instance with all
            DB-populated fields resolved.

        Raises:
            sqlalchemy.exc.IntegrityError: If the FK references a
                non-existent user or skill row, or if a progress record
                already exists for (user_id, skill_id).
            sqlalchemy.exc.SQLAlchemyError: For any other DB-level error.
            Both exceptions are raised after session rollback.
        """
        logger.debug(
            "create_progress | user_id=%s | skill_id=%s | status=%s",
            user_id, skill_id, status,
        )
        record = UserProgress(
            user_id=user_id,
            skill_id=skill_id,
            status=status,
            progress_percentage=progress_percentage,
            started_at=started_at,
            completed_at=completed_at,
            last_accessed=last_accessed,
            time_spent_minutes=time_spent_minutes,
        )
        try:
            self._session.add(record)
            self._session.flush()
            logger.info(
                "UserProgress created | id=%s | user_id=%s | skill_id=%s"
                " | status=%s",
                record.id, record.user_id, record.skill_id, record.status,
            )
            return record
        except IntegrityError:
            logger.warning(
                "create_progress failed — constraint violation"
                " | user_id=%s | skill_id=%s",
                user_id, skill_id,
            )
            self._session.rollback()
            raise
        except SQLAlchemyError:
            logger.exception(
                "create_progress failed | user_id=%s | skill_id=%s",
                user_id, skill_id,
            )
            self._session.rollback()
            raise

    def update_progress(
        self,
        record: UserProgress,
        *,
        status: Optional[str] = None,
        progress_percentage: Optional[int] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        last_accessed: Optional[datetime] = None,
        time_spent_minutes: Optional[int] = None,
    ) -> UserProgress:
        """Apply a partial update to an existing progress row (PATCH semantics).

        Only keyword arguments that are **not** ``None`` are written.  The
        method flushes after mutation so that ``updated_at`` is refreshed
        and the object reflects the current DB state.

        Args:
            record: The ``UserProgress`` ORM instance to update (must be
                attached to this session).
            status: New lifecycle status, or ``None`` to leave unchanged.
            progress_percentage: New percentage (0–100), or ``None``.
            started_at: New first-interaction timestamp, or ``None``.
            completed_at: New completion timestamp, or ``None``.
            last_accessed: New last-access timestamp, or ``None``.
            time_spent_minutes: New cumulative time, or ``None``.

        Returns:
            The updated ``UserProgress`` ORM instance.

        Raises:
            sqlalchemy.exc.SQLAlchemyError: For any DB-level error (after
                session rollback).
        """
        logger.debug("update_progress | id=%s", record.id)

        if status is not None:
            record.status = status
        if progress_percentage is not None:
            record.progress_percentage = progress_percentage
        if started_at is not None:
            record.started_at = started_at
        if completed_at is not None:
            record.completed_at = completed_at
        if last_accessed is not None:
            record.last_accessed = last_accessed
        if time_spent_minutes is not None:
            record.time_spent_minutes = time_spent_minutes

        try:
            self._session.flush()
            logger.info(
                "UserProgress updated | id=%s | status=%s | progress=%s%%",
                record.id, record.status, record.progress_percentage,
            )
            return record
        except IntegrityError:
            logger.warning(
                "update_progress failed — constraint violation | id=%s", record.id
            )
            self._session.rollback()
            raise
        except SQLAlchemyError:
            logger.exception("update_progress failed | id=%s", record.id)
            self._session.rollback()
            raise

    def delete_progress(self, record: UserProgress) -> None:
        """Hard-delete a user progress row from the database.

        Args:
            record: The ``UserProgress`` ORM instance to delete (must be
                attached to this session).

        Raises:
            sqlalchemy.exc.SQLAlchemyError: On any DB-level failure (after
                session rollback).
        """
        logger.debug(
            "delete_progress | id=%s | user_id=%s | skill_id=%s",
            record.id, record.user_id, record.skill_id,
        )
        try:
            self._session.delete(record)
            self._session.flush()
            logger.info(
                "UserProgress deleted | id=%s | user_id=%s | skill_id=%s",
                record.id, record.user_id, record.skill_id,
            )
        except SQLAlchemyError:
            logger.exception("delete_progress failed | id=%s", record.id)
            self._session.rollback()
            raise
