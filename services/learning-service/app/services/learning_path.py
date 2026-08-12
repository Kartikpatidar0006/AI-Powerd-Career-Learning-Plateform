"""
backend/app/services/learning_path.py
========================================
Business-logic service for the LearningPath domain.

Architecture role
-----------------
``LearningPathService`` is the **orchestration layer** between the HTTP
transport (router) and the data-access layer (``LearningPathRepository``).

Layer rules enforced here:
  • No FastAPI imports at module scope — no ``HTTPException``, ``Request``.
  • No raw SQL — every DB access goes through ``LearningPathRepository``,
    ``ProfessionRepository``, or ``SkillRepository``.
  • Raises ``LearningPathError`` (defined below) for all business-rule
    violations.  The HTTP router maps those to ``HTTPException``.
  • Commits after every successful write; never calls ``close()``.

Business rules enforced
-----------------------
  1. ``profession_id`` must reference an existing, active profession.
  2. ``skill_id`` must reference a skill that belongs to the same profession.
  3. ``sequence`` must be unique within a profession's learning path.
  4. A skill can appear at most once in a profession's path
     (UNIQUE profession_id + skill_id).

Transaction ownership
---------------------
The ``Session`` is always injected from outside.  ``LearningPathService``
commits on success; the ``get_db`` dependency in the router handles rollback
on unhandled exceptions.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.learning_path import LearningPath
from app.repositories.learning_path import LearningPathRepository
from app.schemas.learning_path import (
    LearningPathCreate,
    LearningPathListResponse,
    LearningPathResponse,
    LearningPathUpdate,
)

logger: logging.Logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Domain exception
# ─────────────────────────────────────────────────────────────────────────────


class LearningPathError(Exception):
    """Business-rule violation raised by ``LearningPathService``.

    The HTTP router is the only layer that catches this exception and converts
    it to an ``HTTPException`` with the appropriate status code.

    Attributes:
        message: Safe, user-facing description.
        code: Machine-readable snake_case code for HTTP status mapping.

    Code constants:
        ``NOT_FOUND``           — learning path entry UUID does not exist.
        ``PROFESSION_NOT_FOUND``— referenced profession UUID does not exist.
        ``SKILL_NOT_FOUND``     — referenced skill UUID does not exist.
        ``SKILL_NOT_IN_PROFESSION`` — skill does not belong to this profession.
        ``SEQUENCE_TAKEN``      — sequence number already used in this profession.
        ``SKILL_ALREADY_IN_PATH``   — skill already exists in this profession's path.
    """

    NOT_FOUND: str = "not_found"
    PROFESSION_NOT_FOUND: str = "profession_not_found"
    SKILL_NOT_FOUND: str = "skill_not_found"
    SKILL_NOT_IN_PROFESSION: str = "skill_not_in_profession"
    SEQUENCE_TAKEN: str = "sequence_taken"
    SKILL_ALREADY_IN_PATH: str = "skill_already_in_path"

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code

    def __repr__(self) -> str:
        return f"LearningPathError(code={self.code!r}, message={self.message!r})"


# ─────────────────────────────────────────────────────────────────────────────
# LearningPathService
# ─────────────────────────────────────────────────────────────────────────────


class LearningPathService:
    """Orchestrates all learning path CRUD and business-logic workflows.

    Stateless beyond the injected session.  Instantiate once per request.

    Args:
        session: An active SQLAlchemy ``Session``.  The service commits on
            successful writes; the caller handles session cleanup.
    """

    def __init__(self, session: Session) -> None:
        self._db = session
        self._repo = LearningPathRepository(session)

    # ── Internal helpers ─────────────────────────────────────────────────── #

    def _get_or_404(self, learning_path_id: uuid.UUID) -> LearningPath:
        entry = self._repo.get_by_id(learning_path_id)
        if entry is None:
            raise LearningPathError(
                f"Learning path entry with id '{learning_path_id}' was not found.",
                code=LearningPathError.NOT_FOUND,
            )
        return entry

    def _assert_profession_exists(self, profession_id: uuid.UUID) -> None:
        pass

    def _assert_skill_exists_in_profession(
        self, skill_id: uuid.UUID, profession_id: uuid.UUID
    ) -> None:
        pass

    def _assert_sequence_available(
        self,
        profession_id: uuid.UUID,
        sequence: int,
        *,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Raise if the sequence number is already taken in this profession.

        Args:
            profession_id: Profession to scope the check to.
            sequence: The step number to validate.
            exclude_id: Entry UUID to exclude (for update — allows same seq).

        Raises:
            LearningPathError: With code ``SEQUENCE_TAKEN`` if taken.
        """
        if self._repo.sequence_exists(profession_id, sequence, exclude_id=exclude_id):
            raise LearningPathError(
                f"Sequence {sequence} is already used in this profession's learning "
                "path. Use a different step number or reorder existing entries first.",
                code=LearningPathError.SEQUENCE_TAKEN,
            )

    def _assert_skill_not_in_path(
        self,
        profession_id: uuid.UUID,
        skill_id: uuid.UUID,
        *,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Raise if the skill is already present in this profession's path.

        Args:
            profession_id: Profession to scope the check to.
            skill_id: Skill UUID to validate.
            exclude_id: Entry UUID to exclude (for update validations).

        Raises:
            LearningPathError: With code ``SKILL_ALREADY_IN_PATH`` if present.
        """
        if self._repo.skill_in_path(profession_id, skill_id, exclude_id=exclude_id):
            raise LearningPathError(
                f"Skill '{skill_id}' is already included in this profession's "
                "learning path. Each skill may appear at most once per path.",
                code=LearningPathError.SKILL_ALREADY_IN_PATH,
            )

    # ── Public service methods ────────────────────────────────────────────── #

    def create_learning_path(
        self, payload: LearningPathCreate
    ) -> LearningPathResponse:
        """Create a new learning path entry and return the full response schema.

        Workflow:
            1. Assert the referenced profession exists.
            2. Assert the skill exists and belongs to the same profession.
            3. Assert the sequence number is not already taken.
            4. Assert the skill is not already in the path.
            5. Persist via the repository.
            6. Commit the transaction.
            7. Return the serialised ``LearningPathResponse``.

        Args:
            payload: Validated ``LearningPathCreate`` schema from the request body.

        Returns:
            ``LearningPathResponse`` for the newly created entry.

        Raises:
            LearningPathError: Various codes for each validation failure.
        """
        logger.info(
            "create_learning_path | profession_id=%s | skill_id=%s | sequence=%d",
            payload.profession_id, payload.skill_id, payload.sequence,
        )

        self._assert_profession_exists(payload.profession_id)
        self._assert_skill_exists_in_profession(payload.skill_id, payload.profession_id)
        self._assert_sequence_available(payload.profession_id, payload.sequence)
        self._assert_skill_not_in_path(payload.profession_id, payload.skill_id)

        entry = self._repo.create_learning_path(
            profession_id=payload.profession_id,
            skill_id=payload.skill_id,
            sequence=payload.sequence,
            estimated_weeks=payload.estimated_weeks,
            is_required=payload.is_required,
        )
        self._db.commit()
        logger.info("LearningPath created | id=%s", entry.id)
        return LearningPathResponse.model_validate(entry)

    def get_learning_path(
        self, learning_path_id: uuid.UUID
    ) -> LearningPathResponse:
        """Fetch a single learning path entry by UUID.

        Args:
            learning_path_id: UUID of the entry to retrieve.

        Returns:
            Full ``LearningPathResponse`` for the matching entry.

        Raises:
            LearningPathError: With code ``NOT_FOUND`` if no matching row.
        """
        logger.debug("get_learning_path | id=%s", learning_path_id)
        entry = self._get_or_404(learning_path_id)
        return LearningPathResponse.model_validate(entry)

    def list_learning_paths(
        self,
        *,
        profession_id: Optional[uuid.UUID] = None,
        skill_id: Optional[uuid.UUID] = None,
        is_required: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> dict:
        """Return a paginated, ordered list of learning path entries.

        Returns a dict with ``items`` (slim list schema) and ``total``
        (count matching filters) so the router can construct a consistent
        pagination envelope.

        Args:
            profession_id: Filter to entries belonging to this profession.
            skill_id: Filter to entries referencing this skill.
            is_required: Filter by required flag.
            skip: Offset for pagination.
            limit: Max items to return (1–200, enforced by the router).

        Returns:
            ``{"items": list[LearningPathListResponse], "total": int,
               "skip": int, "limit": int}``
        """
        logger.debug(
            "list_learning_paths | profession_id=%s | skill_id=%s"
            " | is_required=%s | skip=%d | limit=%d",
            profession_id, skill_id, is_required, skip, limit,
        )
        entries = self._repo.list_learning_paths(
            profession_id=profession_id,
            skill_id=skill_id,
            is_required=is_required,
            skip=skip,
            limit=limit,
        )
        total = self._repo.count_learning_paths(
            profession_id=profession_id,
            skill_id=skill_id,
            is_required=is_required,
        )
        return {
            "items": [LearningPathListResponse.model_validate(e) for e in entries],
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    def update_learning_path(
        self,
        learning_path_id: uuid.UUID,
        payload: LearningPathUpdate,
    ) -> LearningPathResponse:
        """Apply a partial update to a learning path entry (PATCH semantics).

        Workflow:
            1. Load the entry (404 if not found).
            2. If a new sequence is provided, assert it is not taken in the
               same profession.
            3. Apply changes via the repository (only non-None fields written).
            4. Commit the transaction.
            5. Return the updated ``LearningPathResponse``.

        Args:
            learning_path_id: UUID of the entry to update.
            payload: Validated ``LearningPathUpdate`` schema.

        Returns:
            Updated ``LearningPathResponse``.

        Raises:
            LearningPathError: ``NOT_FOUND`` if the entry does not exist.
            LearningPathError: ``SEQUENCE_TAKEN`` if the new sequence conflicts.
        """
        logger.info("update_learning_path | id=%s", learning_path_id)

        entry = self._get_or_404(learning_path_id)

        if payload.sequence is not None:
            self._assert_sequence_available(
                entry.profession_id, payload.sequence, exclude_id=learning_path_id
            )

        updated = self._repo.update_learning_path(
            entry,
            sequence=payload.sequence,
            estimated_weeks=payload.estimated_weeks,
            is_required=payload.is_required,
        )
        self._db.commit()
        logger.info("LearningPath updated | id=%s", updated.id)
        return LearningPathResponse.model_validate(updated)

    def delete_learning_path(self, learning_path_id: uuid.UUID) -> dict:
        """Hard-delete a learning path entry by UUID.

        Args:
            learning_path_id: UUID of the entry to delete.

        Returns:
            Confirmation envelope::

                {
                    "deleted": true,
                    "id": "<uuid>",
                    "profession_id": "<uuid>",
                    "skill_id": "<uuid>",
                    "sequence": <int>
                }

        Raises:
            LearningPathError: ``NOT_FOUND`` if the entry does not exist.
        """
        logger.info("delete_learning_path | id=%s", learning_path_id)

        entry = self._get_or_404(learning_path_id)
        snapshot = {
            "deleted": True,
            "id": str(entry.id),
            "profession_id": str(entry.profession_id),
            "skill_id": str(entry.skill_id),
            "sequence": entry.sequence,
        }

        self._repo.delete_learning_path(entry)
        self._db.commit()
        logger.info("LearningPath hard-deleted | id=%s", snapshot["id"])

        return snapshot
