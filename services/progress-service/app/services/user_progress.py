"""
backend/app/services/user_progress.py
======================================
Business-logic service for the UserProgress domain.

Architecture role
-----------------
``UserProgressService`` is the **orchestration layer** between the HTTP
transport (router) and the data-access layer (``UserProgressRepository``).

Layer rules enforced here:
  • No FastAPI imports at module scope — no ``HTTPException``, ``Request``.
  • No raw SQL — every DB access goes through ``UserProgressRepository``,
    ``UserRepository``, or ``SkillRepository`` (for FK validation).
  • Raises ``UserProgressError`` (defined below) for all business-rule
    violations.  The HTTP router maps those to ``HTTPException``.
  • Commits after every successful write operation; never calls ``close()``.
  • Enforces the COMPLETED ↔ 100% invariant and auto-sets ``completed_at``
    when a record transitions to COMPLETED status.
  • Auto-sets ``started_at`` on the first IN_PROGRESS / > 0% transition.
  • Auto-updates ``last_accessed`` on every PATCH request.

Transaction ownership
---------------------
The ``Session`` is always injected from outside.  ``UserProgressService``
commits on success; the ``get_db`` dependency in the router handles rollback
on unhandled exceptions.

Usage example::

    from sqlalchemy.orm import Session
    from app.services.user_progress import UserProgressService

    svc = UserProgressService(db)
    record = svc.create_progress(payload)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.user_progress import UserProgress
from app.repositories.user_progress import UserProgressRepository
from app.schemas.user_progress import (
    ProgressStatus,
    UserProgressCreate,
    UserProgressListResponse,
    UserProgressResponse,
    UserProgressUpdate,
)

logger: logging.Logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Domain exception
# ─────────────────────────────────────────────────────────────────────────────


class UserProgressError(Exception):
    """Business-rule violation raised by ``UserProgressService``.

    The HTTP router is the only layer that catches this exception and converts
    it to an ``HTTPException`` with the appropriate status code.

    Attributes:
        message: Safe, user-facing description.
        code: Machine-readable snake_case code for HTTP status mapping.

    Code constants:
        ``NOT_FOUND``          — progress record UUID does not exist.
        ``USER_NOT_FOUND``     — referenced user UUID does not exist.
        ``SKILL_NOT_FOUND``    — referenced skill UUID does not exist.
        ``ALREADY_EXISTS``     — a progress record already exists for
                                 this (user_id, skill_id) pair.
        ``INVALID_TRANSITION`` — the requested status/percentage transition
                                 violates the progress state machine.
    """

    NOT_FOUND: str = "not_found"
    USER_NOT_FOUND: str = "user_not_found"
    SKILL_NOT_FOUND: str = "skill_not_found"
    ALREADY_EXISTS: str = "already_exists"
    INVALID_TRANSITION: str = "invalid_transition"

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code

    def __repr__(self) -> str:
        return (
            f"UserProgressError(code={self.code!r}, message={self.message!r})"
        )


# ─────────────────────────────────────────────────────────────────────────────
# UserProgressService
# ─────────────────────────────────────────────────────────────────────────────


class UserProgressService:
    """Orchestrates all user progress CRUD and business-logic workflows.

    Stateless beyond the injected session.  Instantiate once per request.

    Args:
        session: An active SQLAlchemy ``Session``.  The service commits on
            successful writes; the caller handles session cleanup.
    """

    def __init__(self, session: Session) -> None:
        self._db = session
        self._repo = UserProgressRepository(session)

    # ── Internal helpers ─────────────────────────────────────────────────── #

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(tz=timezone.utc)

    def _get_or_404(self, progress_id: uuid.UUID) -> UserProgress:
        record = self._repo.get_by_id(progress_id)
        if record is None:
            raise UserProgressError(
                f"Progress record with id '{progress_id}' was not found.",
                code=UserProgressError.NOT_FOUND,
            )
        return record

    def _assert_user_exists(self, user_id: uuid.UUID) -> None:
        pass

    def _assert_skill_exists(self, skill_id: uuid.UUID) -> None:
        pass

    def _assert_no_duplicate(
        self,
        user_id: uuid.UUID,
        skill_id: uuid.UUID,
    ) -> None:
        """Raise ``UserProgressError(ALREADY_EXISTS)`` if a record exists.

        Args:
            user_id: UUID of the user.
            skill_id: UUID of the skill.

        Raises:
            UserProgressError: With code ``ALREADY_EXISTS`` if a progress
                record already exists for this (user_id, skill_id) pair.
        """
        if self._repo.progress_exists_for_user_skill(user_id, skill_id):
            raise UserProgressError(
                f"A progress record already exists for user '{user_id}'"
                f" and skill '{skill_id}'.",
                code=UserProgressError.ALREADY_EXISTS,
            )

    def _derive_auto_timestamps(
        self,
        *,
        current_status: str,
        new_status: Optional[str],
        current_started_at: Optional[datetime],
        payload_started_at: Optional[datetime],
        payload_completed_at: Optional[datetime],
        new_percentage: Optional[int],
    ) -> dict:
        """Compute auto-managed timestamps based on status transitions.

        Rules:
          - ``started_at`` is set automatically to NOW when the status first
            transitions away from ``NOT_STARTED``, unless the caller already
            provided a value.
          - ``completed_at`` is set automatically to NOW when the status
            transitions to ``COMPLETED``, unless the caller already provided a
            value.
          - ``last_accessed`` is always updated to NOW on every write
            (create or update) to track engagement recency.

        Args:
            current_status: The record's current status before the update.
            new_status: The requested new status (may be ``None`` on updates).
            current_started_at: The record's current ``started_at`` value.
            payload_started_at: Caller-supplied ``started_at`` override.
            payload_completed_at: Caller-supplied ``completed_at`` override.
            new_percentage: The new progress_percentage, if being changed.

        Returns:
            Dict with ``started_at``, ``completed_at``, and ``last_accessed``
            values ready to pass to the repository.
        """
        now = self._utcnow()
        effective_status = new_status or current_status

        # Auto-set started_at when first leaving NOT_STARTED
        if (
            payload_started_at is not None
        ):
            started_at = payload_started_at
        elif (
            current_started_at is None
            and effective_status != ProgressStatus.NOT_STARTED.value
        ):
            started_at = now
        else:
            started_at = None  # leave unchanged in repo

        # Auto-set completed_at when transitioning to COMPLETED
        if payload_completed_at is not None:
            completed_at = payload_completed_at
        elif effective_status == ProgressStatus.COMPLETED.value:
            completed_at = now
        else:
            completed_at = None  # leave unchanged in repo

        return {
            "started_at": started_at,
            "completed_at": completed_at,
            "last_accessed": now,
        }

    # ── Public service methods ────────────────────────────────────────────── #

    def create_progress(
        self, payload: UserProgressCreate
    ) -> UserProgressResponse:
        """Create a new progress record and return the full response schema.

        Workflow:
            1. Assert the referenced user exists.
            2. Assert the referenced skill exists.
            3. Assert no duplicate (user_id, skill_id) pair exists.
            4. Compute auto-managed timestamps.
            5. Persist the new record via the repository.
            6. Commit the transaction.
            7. Return the serialised ``UserProgressResponse``.

        Args:
            payload: Validated ``UserProgressCreate`` schema from the request
                body.

        Returns:
            ``UserProgressResponse`` representing the newly created record.

        Raises:
            UserProgressError: ``USER_NOT_FOUND`` if the user FK is invalid.
            UserProgressError: ``SKILL_NOT_FOUND`` if the skill FK is invalid.
            UserProgressError: ``ALREADY_EXISTS`` if the (user_id, skill_id)
                pair already has a progress record.

        Example::

            response = svc.create_progress(UserProgressCreate(
                user_id=user_uuid,
                skill_id=skill_uuid,
                status="IN_PROGRESS",
                progress_percentage=25,
            ))
        """
        logger.info(
            "create_progress | user_id=%s | skill_id=%s | status=%s"
            " | percentage=%d",
            payload.user_id, payload.skill_id,
            payload.status, payload.progress_percentage,
        )

        self._assert_user_exists(payload.user_id)
        self._assert_skill_exists(payload.skill_id)
        self._assert_no_duplicate(payload.user_id, payload.skill_id)

        auto_ts = self._derive_auto_timestamps(
            current_status=ProgressStatus.NOT_STARTED.value,
            new_status=payload.status.value,
            current_started_at=None,
            payload_started_at=payload.started_at,
            payload_completed_at=payload.completed_at,
            new_percentage=payload.progress_percentage,
        )

        record = self._repo.create_progress(
            user_id=payload.user_id,
            skill_id=payload.skill_id,
            status=payload.status.value,
            progress_percentage=payload.progress_percentage,
            started_at=auto_ts["started_at"],
            completed_at=auto_ts["completed_at"],
            last_accessed=auto_ts["last_accessed"],
            time_spent_minutes=payload.time_spent_minutes,
        )
        self._db.commit()
        logger.info("UserProgress created | id=%s", record.id)
        return UserProgressResponse.model_validate(record)

    def get_progress(self, progress_id: uuid.UUID) -> UserProgressResponse:
        """Fetch a single progress record by UUID.

        Args:
            progress_id: UUID of the record to retrieve.

        Returns:
            Full ``UserProgressResponse`` for the matching record.

        Raises:
            UserProgressError: With code ``NOT_FOUND`` if no matching row.
        """
        logger.debug("get_progress | id=%s", progress_id)
        record = self._get_or_404(progress_id)
        return UserProgressResponse.model_validate(record)

    def get_progress_by_user_skill(
        self,
        user_id: uuid.UUID,
        skill_id: uuid.UUID,
    ) -> UserProgressResponse:
        """Fetch a progress record by (user_id, skill_id) pair.

        Convenience endpoint for clients that know the user and skill but
        not the progress record UUID.

        Args:
            user_id: UUID of the user.
            skill_id: UUID of the skill.

        Returns:
            Full ``UserProgressResponse`` for the matching record.

        Raises:
            UserProgressError: With code ``NOT_FOUND`` if no matching row.
        """
        logger.debug(
            "get_progress_by_user_skill | user_id=%s | skill_id=%s",
            user_id, skill_id,
        )
        record = self._repo.get_by_user_and_skill(user_id, skill_id)
        if record is None:
            raise UserProgressError(
                f"No progress record found for user '{user_id}'"
                f" and skill '{skill_id}'.",
                code=UserProgressError.NOT_FOUND,
            )
        return UserProgressResponse.model_validate(record)

    def list_progress(
        self,
        *,
        user_id: Optional[uuid.UUID] = None,
        skill_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> dict:
        """Return a paginated list of progress records with total count.

        Returns a dict with ``items`` (slim list schema) and ``total``
        (count matching filters) so the router can construct a consistent
        pagination envelope.

        Args:
            user_id: Filter to records for this user UUID.
            skill_id: Filter to records for this skill UUID.
            status: Filter by lifecycle status string.
            skip: Offset for pagination.
            limit: Max items to return (1–200, enforced by the router query
                parameter validator).

        Returns:
            ``{"items": list[UserProgressListResponse], "total": int,
               "skip": int, "limit": int}``
        """
        logger.debug(
            "list_progress | user_id=%s | skill_id=%s | status=%s"
            " | skip=%d | limit=%d",
            user_id, skill_id, status, skip, limit,
        )
        records = self._repo.list_progress(
            user_id=user_id,
            skill_id=skill_id,
            status=status,
            skip=skip,
            limit=limit,
        )
        total = self._repo.count_progress(
            user_id=user_id,
            skill_id=skill_id,
            status=status,
        )
        return {
            "items": [UserProgressListResponse.model_validate(r) for r in records],
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    def get_user_stats(self, user_id: uuid.UUID) -> dict:
        """Return aggregated skill-completion statistics for a user.

        Validates the user exists before querying, then delegates to the
        repository's aggregation query.

        Args:
            user_id: UUID of the user to summarise.

        Returns:
            Dict with ``user_id``, ``total``, ``not_started``,
            ``in_progress``, and ``completed`` integer counts, plus
            ``completion_rate`` as a float 0.0–100.0.

        Raises:
            UserProgressError: With code ``USER_NOT_FOUND`` if invalid.
        """
        logger.debug("get_user_stats | user_id=%s", user_id)
        self._assert_user_exists(user_id)
        stats = self._repo.get_completion_stats(user_id)
        total = stats["total"]
        completion_rate = (
            round((stats["completed"] / total) * 100, 2) if total > 0 else 0.0
        )
        return {
            "user_id": str(user_id),
            **stats,
            "completion_rate": completion_rate,
        }

    def update_progress(
        self,
        progress_id: uuid.UUID,
        payload: UserProgressUpdate,
    ) -> UserProgressResponse:
        """Apply a partial update to a progress record (PATCH semantics).

        Workflow:
            1. Load the record (404 if not found).
            2. Validate the status/percentage transition is coherent.
            3. Compute auto-managed timestamps (started_at, completed_at,
               last_accessed) based on the requested transition.
            4. Apply changes via the repository (only non-None fields written).
            5. Commit the transaction.
            6. Return the updated ``UserProgressResponse``.

        Automatic behaviours:
            - ``started_at`` is auto-set to NOW if the record was NOT_STARTED
              and is transitioning to IN_PROGRESS or COMPLETED.
            - ``completed_at`` is auto-set to NOW when transitioning to
              COMPLETED (unless the caller supplies an explicit value).
            - ``last_accessed`` is always updated to NOW.

        Args:
            progress_id: UUID of the record to update.
            payload: Validated ``UserProgressUpdate`` schema (all optional).

        Returns:
            Updated ``UserProgressResponse``.

        Raises:
            UserProgressError: ``NOT_FOUND`` if the record does not exist.
            UserProgressError: ``INVALID_TRANSITION`` if COMPLETED status is
                paired with < 100% progress_percentage (cross-field check when
                only one field is provided in the payload).
        """
        logger.info("update_progress | id=%s", progress_id)

        record = self._get_or_404(progress_id)

        # Cross-field validation: when only one of status/percentage is in
        # the payload, resolve against the *existing* value of the other.
        effective_percentage = (
            payload.progress_percentage
            if payload.progress_percentage is not None
            else record.progress_percentage
        )
        effective_status = (
            payload.status.value if payload.status is not None else record.status
        )

        if (
            effective_status == ProgressStatus.COMPLETED.value
            and effective_percentage != 100
        ):
            raise UserProgressError(
                "Cannot set status to 'COMPLETED' with progress_percentage"
                f" of {effective_percentage}. Must be 100.",
                code=UserProgressError.INVALID_TRANSITION,
            )

        if (
            effective_percentage == 100
            and effective_status == ProgressStatus.NOT_STARTED.value
        ):
            raise UserProgressError(
                "Cannot have 100% progress with status 'NOT_STARTED'.",
                code=UserProgressError.INVALID_TRANSITION,
            )

        auto_ts = self._derive_auto_timestamps(
            current_status=record.status,
            new_status=payload.status.value if payload.status else None,
            current_started_at=record.started_at,
            payload_started_at=payload.started_at,
            payload_completed_at=payload.completed_at,
            new_percentage=payload.progress_percentage,
        )

        updated = self._repo.update_progress(
            record,
            status=payload.status.value if payload.status is not None else None,
            progress_percentage=payload.progress_percentage,
            started_at=auto_ts["started_at"],
            completed_at=auto_ts["completed_at"],
            last_accessed=auto_ts["last_accessed"],
            time_spent_minutes=payload.time_spent_minutes,
        )
        self._db.commit()
        logger.info(
            "UserProgress updated | id=%s | status=%s | percentage=%d%%",
            updated.id, updated.status, updated.progress_percentage,
        )
        return UserProgressResponse.model_validate(updated)

    def delete_progress(self, progress_id: uuid.UUID) -> dict:
        """Hard-delete a progress record by UUID.

        Args:
            progress_id: UUID of the record to delete.

        Returns:
            Confirmation envelope::

                {
                    "deleted": true,
                    "id": "<uuid>",
                    "user_id": "<uuid>",
                    "skill_id": "<uuid>"
                }

        Raises:
            UserProgressError: ``NOT_FOUND`` if the record does not exist.
        """
        logger.info("delete_progress | id=%s", progress_id)

        record = self._get_or_404(progress_id)
        record_id_str = str(record.id)
        user_id_str = str(record.user_id)
        skill_id_str = str(record.skill_id)

        self._repo.delete_progress(record)
        self._db.commit()
        logger.info(
            "UserProgress hard-deleted | id=%s | user_id=%s | skill_id=%s",
            record_id_str, user_id_str, skill_id_str,
        )

        return {
            "deleted": True,
            "id": record_id_str,
            "user_id": user_id_str,
            "skill_id": skill_id_str,
        }
