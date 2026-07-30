"""
backend/app/services/task.py
==============================
Business-logic service layer for the Task Engine.

What this module does
---------------------
``TaskService`` and ``TaskSubmissionService`` orchestrate task management and
submission workflows, sitting between the HTTP transport (FastAPI routes) and
the data-access layer (repositories).

Architecture role
-----------------
  ┌─────────────────────────────────────────────────┐
  │  HTTP Layer  (app/api/v1/tasks/router.py)       │
  │  - Receives HTTP request, validates input       │
  │  - Calls TaskService / TaskSubmissionService    │
  │  - Converts TaskError → HTTPException           │
  ├─────────────────────────────────────────────────┤
  │  TaskService / TaskSubmissionService (this file) │
  │  - Business logic: validation, existence checks │
  │  - All DB access via repositories               │
  │  - Raises TaskError (NOT HTTPException)         │
  ├─────────────────────────────────────────────────┤
  │  TaskRepository / TaskSubmissionRepository       │
  │  - SQL queries only                             │
  │  - Returns ORM objects                          │
  ├─────────────────────────────────────────────────┤
  │  SQLAlchemy Session  /  PostgreSQL               │
  └─────────────────────────────────────────────────┘

Layer rules enforced here:
  • No ``FastAPI`` imports — no ``HTTPException``, ``Request``, ``Depends``.
  • No raw SQL — every DB access goes through repositories.
  • Raises domain-specific ``TaskError`` for all business rule violations.

Transaction ownership:
  The ``Session`` is injected from outside.  Services commit after
  successful write operations.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.task import Task, TaskSubmission
from app.repositories.task import TaskRepository, TaskSubmissionRepository
from app.schemas.task import (
    TaskCreate,
    TaskSubmissionCreate,
    TaskUpdate,
)

logger: logging.Logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Domain exception
# ─────────────────────────────────────────────────────────────────────────────


class TaskError(Exception):
    """Business-rule violation raised by ``TaskService`` or
    ``TaskSubmissionService``.

    The HTTP router maps these to ``HTTPException`` via a lookup table.

    Attributes:
        message: Safe, user-facing description.
        code: Machine-readable snake_case code for HTTP status mapping.

    Code constants:
        ``NOT_FOUND``              — task UUID does not exist.
        ``STEP_NOT_FOUND``         — roadmap step UUID does not exist.
        ``ALREADY_SUBMITTED``      — user has already submitted for this task.
        ``SUBMISSION_NOT_FOUND``   — submission UUID does not exist.
        ``TASK_INACTIVE``          — task is soft-deleted / hidden.
    """

    NOT_FOUND: str = "not_found"
    STEP_NOT_FOUND: str = "step_not_found"
    ALREADY_SUBMITTED: str = "already_submitted"
    SUBMISSION_NOT_FOUND: str = "submission_not_found"
    TASK_INACTIVE: str = "task_inactive"

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code

    def __repr__(self) -> str:
        return f"TaskError(code={self.code!r}, message={self.message!r})"


# =========================================================================== #
#  TaskService                                                                  #
# =========================================================================== #


class TaskService:
    """Business-logic service for task management.

    Handles task creation, retrieval, updating, and deletion.  Every method
    that validates a related entity (e.g. RoadmapStep) checks for existence
    and raises ``TaskError`` if the entity is missing.

    Args:
        db: An active SQLAlchemy ``Session``.

    Example::

        svc = TaskService(db)
        task = svc.get_by_id(task_uuid)
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = TaskRepository(db)

    # =====================================================================
    #  Read operations
    # =====================================================================

    def get_by_id(self, task_id: uuid.UUID) -> Task:
        """Fetch a task by UUID.

        Args:
            task_id: The UUID of the task.

        Returns:
            The ``Task`` ORM instance.

        Raises:
            TaskError: ``NOT_FOUND`` if no task exists with this UUID.
        """
        task = self._repo.get_by_id(task_id)
        if task is None:
            raise TaskError(
                f"Task with id '{task_id}' not found.",
                code=TaskError.NOT_FOUND,
            )
        return task

    def list_tasks(
        self,
        *,
        roadmap_step_id: Optional[uuid.UUID] = None,
        difficulty: Optional[str] = None,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Task], int]:
        """List tasks with optional filtering and pagination.

        Args:
            roadmap_step_id: Filter by parent roadmap step.
            difficulty: Filter by difficulty level.
            is_active: Filter by visibility flag.
            skip: Offset for pagination.
            limit: Maximum results.

        Returns:
            Tuple of (list of tasks, total count).
        """
        return self._repo.list_tasks(
            roadmap_step_id=roadmap_step_id,
            difficulty=difficulty,
            is_active=is_active,
            skip=skip,
            limit=limit,
        )

    def list_by_step(
        self,
        roadmap_step_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Task], int]:
        """List active tasks for a specific roadmap step.

        Args:
            roadmap_step_id: UUID of the RoadmapStep.
            skip: Offset for pagination.
            limit: Maximum results.

        Returns:
            Tuple of (list of tasks, total count).

        Raises:
            TaskError: ``STEP_NOT_FOUND`` if the RoadmapStep does not exist.
        """
        # ── Validate step exists ────────────────────────────────────────── #
        from app.models.career_roadmap import RoadmapStep
        step = self._db.get(RoadmapStep, roadmap_step_id)
        if step is None:
            raise TaskError(
                f"RoadmapStep with id '{roadmap_step_id}' not found.",
                code=TaskError.STEP_NOT_FOUND,
            )

        return self._repo.list_tasks(
            roadmap_step_id=roadmap_step_id,
            is_active=True,
            skip=skip,
            limit=limit,
        )

    # =====================================================================
    #  Write operations
    # =====================================================================

    def create(self, payload: TaskCreate) -> Task:
        """Create a new task.

        Validates that the referenced ``RoadmapStep`` exists before persisting.

        Args:
            payload: Validated ``TaskCreate`` schema.

        Returns:
            The created ``Task`` ORM instance.

        Raises:
            TaskError: ``STEP_NOT_FOUND`` if the RoadmapStep does not exist.
        """
        # ── Validate step exists ────────────────────────────────────────── #
        from app.models.career_roadmap import RoadmapStep
        step = self._db.get(RoadmapStep, payload.roadmap_step_id)
        if step is None:
            raise TaskError(
                f"RoadmapStep with id '{payload.roadmap_step_id}' not found.",
                code=TaskError.STEP_NOT_FOUND,
            )

        task = Task(
            title=payload.title,
            description=payload.description,
            instructions=payload.instructions,
            difficulty=payload.difficulty.value,
            estimated_minutes=payload.estimated_minutes,
            order_no=payload.order_no,
            is_active=payload.is_active,
            roadmap_step_id=payload.roadmap_step_id,
        )
        task = self._repo.create(task)
        self._db.commit()
        logger.info("Created task '%s' (id=%s)", task.title, task.id)
        return task

    def update(self, task_id: uuid.UUID, payload: TaskUpdate) -> Task:
        """Partially update a task.

        Only non-``None`` fields from the payload are applied.

        Args:
            task_id: UUID of the task to update.
            payload: Validated ``TaskUpdate`` schema.

        Returns:
            The updated ``Task`` ORM instance.

        Raises:
            TaskError: ``NOT_FOUND`` if no task with this UUID exists.
        """
        task = self._repo.get_by_id(task_id)
        if task is None:
            raise TaskError(
                f"Task with id '{task_id}' not found.",
                code=TaskError.NOT_FOUND,
            )

        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "difficulty" and value is not None:
                setattr(task, field, value.value if hasattr(value, "value") else value)
            else:
                setattr(task, field, value)

        task = self._repo.update(task)
        self._db.commit()
        logger.info("Updated task id=%s", task.id)
        return task

    def delete(self, task_id: uuid.UUID) -> None:
        """Hard-delete a task and its submissions.

        Args:
            task_id: UUID of the task to delete.

        Raises:
            TaskError: ``NOT_FOUND`` if no task with this UUID exists.
        """
        task = self._repo.get_by_id(task_id)
        if task is None:
            raise TaskError(
                f"Task with id '{task_id}' not found.",
                code=TaskError.NOT_FOUND,
            )

        self._repo.delete(task)
        self._db.commit()
        logger.info("Deleted task id=%s", task_id)


# =========================================================================== #
#  TaskSubmissionService                                                         #
# =========================================================================== #


class TaskSubmissionService:
    """Business-logic service for task submissions.

    Handles the full submission lifecycle: creating a submission, listing
    a user's submissions, and checking for duplicate submissions.

    Args:
        db: An active SQLAlchemy ``Session``.

    Example::

        svc = TaskSubmissionService(db)
        submission = svc.submit(user_id, task_id, payload)
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._task_repo = TaskRepository(db)
        self._sub_repo = TaskSubmissionRepository(db)

    # =====================================================================
    #  Read operations
    # =====================================================================

    def list_user_submissions(
        self,
        user_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[TaskSubmission], int]:
        """List all submissions for a specific user.

        Args:
            user_id: UUID of the user.
            skip: Offset for pagination.
            limit: Maximum results.

        Returns:
            Tuple of (list of submissions, total count).
        """
        return self._sub_repo.list_by_user(user_id, skip=skip, limit=limit)

    # =====================================================================
    #  Write operations
    # =====================================================================

    def submit(
        self,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
        payload: TaskSubmissionCreate,
    ) -> TaskSubmission:
        """Create or update a submission for a task.

        If the user has already submitted for this task, the existing
        submission is updated with the new deliverables and the status
        is set back to ``Submitted``.  Otherwise a new row is created.

        Args:
            user_id: UUID of the submitting user.
            task_id: UUID of the task being submitted.
            payload: Validated ``TaskSubmissionCreate`` schema.

        Returns:
            The created or updated ``TaskSubmission`` ORM instance.

        Raises:
            TaskError: ``NOT_FOUND`` if the task does not exist.
            TaskError: ``TASK_INACTIVE`` if the task is soft-deleted.
        """
        # ── Validate task exists and is active ──────────────────────────── #
        task = self._task_repo.get_by_id(task_id)
        if task is None:
            raise TaskError(
                f"Task with id '{task_id}' not found.",
                code=TaskError.NOT_FOUND,
            )
        if not task.is_active:
            raise TaskError(
                f"Task '{task.title}' is currently inactive.",
                code=TaskError.TASK_INACTIVE,
            )

        # ── Check for existing submission ───────────────────────────────── #
        existing = self._sub_repo.get_by_user_and_task(user_id, task_id)
        if existing is not None:
            # ── Update existing submission ──────────────────────────────── #
            existing.github_url = payload.github_url
            existing.submission_text = payload.submission_text
            existing.file_url = payload.file_url
            existing.status = "Submitted"
            submission = self._sub_repo.update(existing)
            self._db.commit()
            logger.info(
                "Updated submission id=%s for user=%s task=%s",
                submission.id, user_id, task_id,
            )
            return submission

        # ── Create new submission ───────────────────────────────────────── #
        submission = TaskSubmission(
            user_id=user_id,
            task_id=task_id,
            github_url=payload.github_url,
            submission_text=payload.submission_text,
            file_url=payload.file_url,
            status="Submitted",
        )
        submission = self._sub_repo.create(submission)
        self._db.commit()
        logger.info(
            "Created submission id=%s for user=%s task=%s",
            submission.id, user_id, task_id,
        )
        return submission
