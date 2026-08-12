"""
backend/app/repositories/task.py
==================================
Repository pattern implementations for ``tasks`` and ``task_submissions``
tables.

Architecture contract
---------------------
- **Single responsibility**: SQL only.  No business logic, no schema
  validation, no password or JWT handling.
- **Session ownership**: the caller (service or ``get_db`` dependency) owns
  commit / rollback / close.  This repository calls ``flush()`` after
  mutating operations to surface ``IntegrityError`` early and resolve
  server-side defaults before returning.
- **Returns ORM objects only**: ORM instances or ``list`` or primitives.
- **Rollback on failure**: every mutating method wraps its work in
  ``try/except SQLAlchemyError`` → rollback → re-raise.

Two repository classes are defined here:
  ``TaskRepository``           — CRUD for ``tasks``.
  ``TaskSubmissionRepository`` — CRUD for ``task_submissions``.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.task import Task, TaskSubmission

logger: logging.Logger = logging.getLogger(__name__)


# =========================================================================== #
#  TaskRepository                                                               #
# =========================================================================== #


class TaskRepository:
    """Data-access layer for the ``tasks`` table.

    All public methods issue exactly one logical SQL statement per call.

    Args:
        session: An active SQLAlchemy ``Session``.  The caller is responsible
            for committing or rolling back after each service-level operation.

    Example::

        repo = TaskRepository(db)
        task = repo.get_by_id(some_uuid)
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # =====================================================================
    #  Read operations
    # =====================================================================

    def get_by_id(self, task_id: uuid.UUID) -> Optional[Task]:
        """Fetch a task by UUID primary key using the identity map.

        Args:
            task_id: The UUID PK of the task to retrieve.

        Returns:
            The matching ``Task`` ORM instance, or ``None``.
        """
        logger.debug("get_by_id | task_id=%s", task_id)
        return self._session.get(Task, task_id)

    def list_tasks(
        self,
        *,
        roadmap_step_id: Optional[uuid.UUID] = None,
        difficulty: Optional[str] = None,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Task], int]:
        """Return a paginated, filtered list of tasks.

        Args:
            roadmap_step_id: Limit results to tasks under this roadmap step.
            difficulty: Filter by difficulty level.
            is_active: Filter by visibility flag.
            skip: Number of rows to skip (offset).
            limit: Maximum number of rows to return.

        Returns:
            Tuple of (list of ``Task`` ORM instances, total count).
        """
        logger.debug(
            "list_tasks | step=%s difficulty=%s active=%s skip=%d limit=%d",
            roadmap_step_id, difficulty, is_active, skip, limit,
        )

        # ── Base query ──────────────────────────────────────────────────── #
        stmt = select(Task)
        count_stmt = select(func.count()).select_from(Task)

        # ── Apply filters ───────────────────────────────────────────────── #
        if roadmap_step_id is not None:
            stmt = stmt.where(Task.roadmap_step_id == roadmap_step_id)
            count_stmt = count_stmt.where(Task.roadmap_step_id == roadmap_step_id)

        if difficulty is not None:
            stmt = stmt.where(Task.difficulty == difficulty)
            count_stmt = count_stmt.where(Task.difficulty == difficulty)

        if is_active is not None:
            stmt = stmt.where(Task.is_active == is_active)
            count_stmt = count_stmt.where(Task.is_active == is_active)

        # ── Total count (before pagination) ─────────────────────────────── #
        total: int = self._session.execute(count_stmt).scalar() or 0

        # ── Paginate + order ────────────────────────────────────────────── #
        stmt = stmt.order_by(Task.order_no.asc()).offset(skip).limit(limit)
        tasks: list[Task] = list(self._session.execute(stmt).scalars().all())

        return tasks, total

    # =====================================================================
    #  Write operations
    # =====================================================================

    def create(self, task: Task) -> Task:
        """Persist a new task row.

        Args:
            task: A populated ``Task`` ORM instance (PK may already be set).

        Returns:
            The same instance with server-side defaults resolved.

        Raises:
            IntegrityError: If a constraint violation occurs (e.g. FK missing).
        """
        logger.debug("create | task.title=%s", task.title)
        try:
            self._session.add(task)
            self._session.flush()
            self._session.refresh(task)
            return task
        except SQLAlchemyError as exc:
            logger.error("Failed to create task: %s", exc, exc_info=True)
            self._session.rollback()
            raise

    def update(self, task: Task) -> Task:
        """Flush pending changes on an existing task.

        The caller modifies attributes on the ORM instance before calling
        this method.  ``flush()`` pushes changes to the DB and surfaces
        any constraint violations.

        Args:
            task: The ``Task`` ORM instance with modified attributes.

        Returns:
            The same instance with server-side defaults refreshed.
        """
        logger.debug("update | task.id=%s", task.id)
        try:
            self._session.flush()
            self._session.refresh(task)
            return task
        except SQLAlchemyError as exc:
            logger.error("Failed to update task: %s", exc, exc_info=True)
            self._session.rollback()
            raise

    def delete(self, task: Task) -> None:
        """Hard-delete a task row (cascades to submissions).

        Args:
            task: The ``Task`` ORM instance to remove.
        """
        logger.debug("delete | task.id=%s", task.id)
        try:
            self._session.delete(task)
            self._session.flush()
        except SQLAlchemyError as exc:
            logger.error("Failed to delete task: %s", exc, exc_info=True)
            self._session.rollback()
            raise


# =========================================================================== #
#  TaskSubmissionRepository                                                      #
# =========================================================================== #


class TaskSubmissionRepository:
    """Data-access layer for the ``task_submissions`` table.

    Args:
        session: An active SQLAlchemy ``Session``.

    Example::

        repo = TaskSubmissionRepository(db)
        submission = repo.get_by_user_and_task(user_id, task_id)
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # =====================================================================
    #  Read operations
    # =====================================================================

    def get_by_id(self, submission_id: uuid.UUID) -> Optional[TaskSubmission]:
        """Fetch a submission by UUID primary key.

        Args:
            submission_id: The UUID PK.

        Returns:
            The matching ``TaskSubmission`` or ``None``.
        """
        logger.debug("get_by_id | submission_id=%s", submission_id)
        return self._session.get(TaskSubmission, submission_id)

    def get_by_user_and_task(
        self,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
    ) -> Optional[TaskSubmission]:
        """Fetch the submission for a specific user + task pair.

        Due to the UNIQUE constraint, at most one row exists.

        Args:
            user_id: UUID of the user.
            task_id: UUID of the task.

        Returns:
            The matching ``TaskSubmission`` or ``None``.
        """
        logger.debug(
            "get_by_user_and_task | user=%s task=%s", user_id, task_id
        )
        stmt = (
            select(TaskSubmission)
            .where(TaskSubmission.user_id == user_id)
            .where(TaskSubmission.task_id == task_id)
        )
        return self._session.execute(stmt).scalars().first()

    def list_by_user(
        self,
        user_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[TaskSubmission], int]:
        """Return paginated submissions for a specific user.

        Args:
            user_id: UUID of the user whose submissions to list.
            skip: Number of rows to skip (offset).
            limit: Maximum number of rows to return.

        Returns:
            Tuple of (list of ``TaskSubmission`` instances, total count).
        """
        logger.debug("list_by_user | user=%s skip=%d limit=%d", user_id, skip, limit)

        base = select(TaskSubmission).where(TaskSubmission.user_id == user_id)
        count_stmt = (
            select(func.count())
            .select_from(TaskSubmission)
            .where(TaskSubmission.user_id == user_id)
        )

        total: int = self._session.execute(count_stmt).scalar() or 0
        stmt = base.order_by(TaskSubmission.submitted_at.desc()).offset(skip).limit(limit)
        items: list[TaskSubmission] = list(self._session.execute(stmt).scalars().all())

        return items, total

    def list_by_task(
        self,
        task_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[TaskSubmission], int]:
        """Return paginated submissions for a specific task.

        Args:
            task_id: UUID of the task.
            skip: Offset.
            limit: Max results.

        Returns:
            Tuple of (list of submissions, total count).
        """
        logger.debug("list_by_task | task=%s skip=%d limit=%d", task_id, skip, limit)

        base = select(TaskSubmission).where(TaskSubmission.task_id == task_id)
        count_stmt = (
            select(func.count())
            .select_from(TaskSubmission)
            .where(TaskSubmission.task_id == task_id)
        )

        total: int = self._session.execute(count_stmt).scalar() or 0
        stmt = base.order_by(TaskSubmission.submitted_at.desc()).offset(skip).limit(limit)
        items: list[TaskSubmission] = list(self._session.execute(stmt).scalars().all())

        return items, total

    # =====================================================================
    #  Write operations
    # =====================================================================

    def create(self, submission: TaskSubmission) -> TaskSubmission:
        """Persist a new submission row.

        Args:
            submission: A populated ``TaskSubmission`` ORM instance.

        Returns:
            The same instance with server-side defaults resolved.

        Raises:
            IntegrityError: If the UNIQUE(user_id, task_id) constraint is
                violated (user has already submitted for this task).
        """
        logger.debug(
            "create | user=%s task=%s", submission.user_id, submission.task_id
        )
        try:
            self._session.add(submission)
            self._session.flush()
            self._session.refresh(submission)
            return submission
        except SQLAlchemyError as exc:
            logger.error("Failed to create submission: %s", exc, exc_info=True)
            self._session.rollback()
            raise

    def update(self, submission: TaskSubmission) -> TaskSubmission:
        """Flush pending changes on an existing submission.

        Args:
            submission: The ``TaskSubmission`` instance with modified attributes.

        Returns:
            The same instance with server-side defaults refreshed.
        """
        logger.debug("update | submission.id=%s", submission.id)
        try:
            self._session.flush()
            self._session.refresh(submission)
            return submission
        except SQLAlchemyError as exc:
            logger.error("Failed to update submission: %s", exc, exc_info=True)
            self._session.rollback()
            raise
