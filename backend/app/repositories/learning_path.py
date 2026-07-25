"""
backend/app/repositories/learning_path.py
==========================================
Repository pattern implementation for the ``learning_paths`` table.

Architecture contract
---------------------
- **Single responsibility**: SQL only.  No business logic, no schema
  validation, no password or JWT handling.
- **Session ownership**: the caller (service or ``get_db`` dependency) owns
  commit / rollback / close.  This repository calls ``flush()`` after
  mutating operations to surface ``IntegrityError`` early and resolve
  server-side defaults before returning.
- **Returns ORM objects only**: ``LearningPath`` instances or
  ``list[LearningPath]`` or primitives (``bool``, ``int``).
- **Rollback on failure**: every mutating method wraps its work in
  ``try/except SQLAlchemyError`` → rollback → re-raise.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.learning_path import LearningPath

logger: logging.Logger = logging.getLogger(__name__)


class LearningPathRepository:
    """Data-access layer for the ``learning_paths`` table.

    All public methods issue exactly one logical SQL statement per call.
    PATCH semantics (only non-``None`` fields updated) are handled in
    ``update_learning_path`` so that the service layer passes values
    directly.

    Args:
        session: An active SQLAlchemy ``Session``.  The caller is responsible
            for committing or rolling back after each service-level operation.

    Example::

        repo = LearningPathRepository(db)
        entry = repo.get_by_id(some_uuid)
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # =========================================================================
    #  Read operations
    # =========================================================================

    def get_by_id(self, learning_path_id: uuid.UUID) -> Optional[LearningPath]:
        """Fetch a learning path entry by UUID primary key.

        Args:
            learning_path_id: The UUID PK of the entry to retrieve.

        Returns:
            The matching ``LearningPath`` ORM instance, or ``None``.
        """
        logger.debug("get_by_id | learning_path_id=%s", learning_path_id)
        return self._session.get(LearningPath, learning_path_id)

    def get_by_profession_and_skill(
        self,
        profession_id: uuid.UUID,
        skill_id: uuid.UUID,
    ) -> Optional[LearningPath]:
        """Fetch the entry linking a specific profession and skill.

        Used for duplicate-entry checking before INSERT.

        Args:
            profession_id: UUID of the profession.
            skill_id: UUID of the skill.

        Returns:
            The matching ``LearningPath`` ORM instance, or ``None``.
        """
        logger.debug(
            "get_by_profession_and_skill | profession_id=%s | skill_id=%s",
            profession_id, skill_id,
        )
        stmt = (
            select(LearningPath)
            .where(LearningPath.profession_id == profession_id)
            .where(LearningPath.skill_id == skill_id)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def sequence_exists(
        self,
        profession_id: uuid.UUID,
        sequence: int,
        *,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> bool:
        """Check whether a sequence number is already taken in a profession.

        Args:
            profession_id: Scope the check to this profession.
            sequence: The sequence number to test.
            exclude_id: UUID of the entry to exclude (for update validations).

        Returns:
            ``True`` if the sequence is taken by another entry, else ``False``.
        """
        logger.debug(
            "sequence_exists | profession_id=%s | sequence=%d | exclude_id=%s",
            profession_id, sequence, exclude_id,
        )
        stmt = (
            select(func.count())
            .select_from(LearningPath)
            .where(LearningPath.profession_id == profession_id)
            .where(LearningPath.sequence == sequence)
        )
        if exclude_id is not None:
            stmt = stmt.where(LearningPath.id != exclude_id)
        count: int = self._session.execute(stmt).scalar_one()
        return count > 0

    def skill_in_path(
        self,
        profession_id: uuid.UUID,
        skill_id: uuid.UUID,
        *,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> bool:
        """Check whether a skill is already present in a profession's path.

        Args:
            profession_id: Scope the check to this profession.
            skill_id: UUID of the skill to test.
            exclude_id: UUID of the entry to exclude (for update validations).

        Returns:
            ``True`` if the skill is already in the path, else ``False``.
        """
        logger.debug(
            "skill_in_path | profession_id=%s | skill_id=%s | exclude_id=%s",
            profession_id, skill_id, exclude_id,
        )
        stmt = (
            select(func.count())
            .select_from(LearningPath)
            .where(LearningPath.profession_id == profession_id)
            .where(LearningPath.skill_id == skill_id)
        )
        if exclude_id is not None:
            stmt = stmt.where(LearningPath.id != exclude_id)
        count: int = self._session.execute(stmt).scalar_one()
        return count > 0

    def list_learning_paths(
        self,
        *,
        profession_id: Optional[uuid.UUID] = None,
        skill_id: Optional[uuid.UUID] = None,
        is_required: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[LearningPath]:
        """Return a paginated list of learning path entries with optional filters.

        Results are ordered by ``profession_id`` then ``sequence`` for a
        stable, deterministic page order.

        Args:
            profession_id: Filter to entries belonging to this profession.
                ``None`` = return entries across all professions.
            skill_id: Filter to entries referencing this skill.
                ``None`` = return all skills.
            is_required: Filter by required flag.  ``None`` = return all.
            skip: Row offset for pagination.  Must be >= 0.
            limit: Max rows to return.  Defaults to 50; capped by the caller.

        Returns:
            A (possibly empty) list of ``LearningPath`` ORM instances.
        """
        logger.debug(
            "list_learning_paths | profession_id=%s | skill_id=%s"
            " | is_required=%s | skip=%d | limit=%d",
            profession_id, skill_id, is_required, skip, limit,
        )
        stmt = (
            select(LearningPath)
            .order_by(LearningPath.profession_id, LearningPath.sequence.asc())
        )

        if profession_id is not None:
            stmt = stmt.where(LearningPath.profession_id == profession_id)
        if skill_id is not None:
            stmt = stmt.where(LearningPath.skill_id == skill_id)
        if is_required is not None:
            stmt = stmt.where(LearningPath.is_required == is_required)

        stmt = stmt.offset(skip).limit(limit)
        return list(self._session.execute(stmt).scalars().all())

    def count_learning_paths(
        self,
        *,
        profession_id: Optional[uuid.UUID] = None,
        skill_id: Optional[uuid.UUID] = None,
        is_required: Optional[bool] = None,
    ) -> int:
        """Return the total count matching the given filters.

        Used alongside ``list_learning_paths`` to build pagination metadata.

        Args:
            profession_id: Same filter semantics as ``list_learning_paths``.
            skill_id: Same filter semantics as ``list_learning_paths``.
            is_required: Same filter semantics as ``list_learning_paths``.

        Returns:
            Integer count of matching rows.
        """
        stmt = select(func.count()).select_from(LearningPath)
        if profession_id is not None:
            stmt = stmt.where(LearningPath.profession_id == profession_id)
        if skill_id is not None:
            stmt = stmt.where(LearningPath.skill_id == skill_id)
        if is_required is not None:
            stmt = stmt.where(LearningPath.is_required == is_required)
        return self._session.execute(stmt).scalar_one()

    # =========================================================================
    #  Write operations
    # =========================================================================

    def create_learning_path(
        self,
        *,
        profession_id: uuid.UUID,
        skill_id: uuid.UUID,
        sequence: int,
        estimated_weeks: int = 1,
        is_required: bool = True,
    ) -> LearningPath:
        """Persist a new learning path entry and return the ORM instance.

        Calls ``flush()`` so that server-side defaults (``created_at``,
        ``updated_at``) are written back to the object before returning.
        The caller must commit the session.

        Args:
            profession_id: UUID of the owning Profession (FK).
            skill_id: UUID of the linked Skill (FK).
            sequence: 1-based step number (unique per profession).
            estimated_weeks: Expected weeks to complete this step.
            is_required: Whether this step is mandatory.

        Returns:
            The freshly created ``LearningPath`` ORM instance with all
            DB-populated fields resolved.

        Raises:
            sqlalchemy.exc.IntegrityError: On FK violation or UNIQUE constraint
                violation (profession_id+sequence or profession_id+skill_id).
            sqlalchemy.exc.SQLAlchemyError: For any other DB-level error.
            Both exceptions are raised after session rollback.
        """
        logger.debug(
            "create_learning_path | profession_id=%s | skill_id=%s | sequence=%d",
            profession_id, skill_id, sequence,
        )
        entry = LearningPath(
            profession_id=profession_id,
            skill_id=skill_id,
            sequence=sequence,
            estimated_weeks=estimated_weeks,
            is_required=is_required,
        )
        try:
            self._session.add(entry)
            self._session.flush()
            logger.info(
                "LearningPath created | id=%s | profession_id=%s | skill_id=%s | seq=%d",
                entry.id, entry.profession_id, entry.skill_id, entry.sequence,
            )
            return entry
        except IntegrityError:
            logger.warning(
                "create_learning_path failed — constraint violation"
                " | profession_id=%s | skill_id=%s | sequence=%d",
                profession_id, skill_id, sequence,
            )
            self._session.rollback()
            raise
        except SQLAlchemyError:
            logger.exception(
                "create_learning_path failed | profession_id=%s", profession_id
            )
            self._session.rollback()
            raise

    def update_learning_path(
        self,
        entry: LearningPath,
        *,
        sequence: Optional[int] = None,
        estimated_weeks: Optional[int] = None,
        is_required: Optional[bool] = None,
    ) -> LearningPath:
        """Apply a partial update to an existing entry (PATCH semantics).

        Only keyword arguments that are **not** ``None`` are written.  The
        method flushes after mutation so that ``updated_at`` is refreshed and
        the object reflects the current DB state.

        Args:
            entry: The ``LearningPath`` ORM instance to update (must be
                attached to this session).
            sequence: New step number, or ``None`` to leave unchanged.
            estimated_weeks: New estimated weeks, or ``None`` to leave unchanged.
            is_required: New required flag, or ``None`` to leave unchanged.

        Returns:
            The updated ``LearningPath`` ORM instance.

        Raises:
            sqlalchemy.exc.IntegrityError: If the new sequence conflicts with
                an existing entry in the same profession.
            sqlalchemy.exc.SQLAlchemyError: For any other DB-level error.
            Both exceptions raised after session rollback.
        """
        logger.debug("update_learning_path | id=%s", entry.id)

        if sequence is not None:
            entry.sequence = sequence
        if estimated_weeks is not None:
            entry.estimated_weeks = estimated_weeks
        if is_required is not None:
            entry.is_required = is_required

        try:
            self._session.flush()
            logger.info("LearningPath updated | id=%s", entry.id)
            return entry
        except IntegrityError:
            logger.warning(
                "update_learning_path failed — constraint violation | id=%s", entry.id
            )
            self._session.rollback()
            raise
        except SQLAlchemyError:
            logger.exception("update_learning_path failed | id=%s", entry.id)
            self._session.rollback()
            raise

    def delete_learning_path(self, entry: LearningPath) -> None:
        """Hard-delete a learning path entry.

        Learning path entries are structural metadata — they have no user-
        generated content and no deep referential dependencies, so hard DELETE
        is appropriate here.

        Args:
            entry: The ``LearningPath`` ORM instance to delete (must be
                attached to this session).

        Raises:
            sqlalchemy.exc.SQLAlchemyError: On any DB-level failure (after
                session rollback).
        """
        logger.debug("delete_learning_path | id=%s", entry.id)
        try:
            self._session.delete(entry)
            self._session.flush()
            logger.info("LearningPath deleted | id=%s", entry.id)
        except SQLAlchemyError:
            logger.exception("delete_learning_path failed | id=%s", entry.id)
            self._session.rollback()
            raise
