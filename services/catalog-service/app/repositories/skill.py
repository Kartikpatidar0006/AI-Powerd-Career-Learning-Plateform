"""
backend/app/repositories/skill.py
===================================
Repository pattern implementation for the ``skills`` table.

Architecture contract
---------------------
- **Single responsibility**: SQL only.  No business logic, no schema
  validation, no password or JWT handling.
- **Session ownership**: the caller (service or ``get_db`` dependency) owns
  commit / rollback / close.  This repository calls ``flush()`` after
  mutating operations to surface ``IntegrityError`` early and resolve
  server-side defaults before returning.
- **Returns ORM objects only**: ``Skill`` instances or ``list[Skill]``
  or primitives (``bool``, ``int``).
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

from app.models.skill import Skill

logger: logging.Logger = logging.getLogger(__name__)


class SkillRepository:
    """Data-access layer for the ``skills`` table.

    All public methods issue exactly one logical SQL statement (SELECT, INSERT,
    UPDATE).  PATCH semantics (only non-``None`` fields updated) are handled
    in ``update_skill`` so that the service layer passes values directly.

    Args:
        session: An active SQLAlchemy ``Session``.  The caller is responsible
            for committing or rolling back after each service-level operation.

    Example::

        repo = SkillRepository(db)
        skill = repo.get_by_id(some_uuid)
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # =========================================================================
    #  Read operations
    # =========================================================================

    def get_by_id(self, skill_id: uuid.UUID) -> Optional[Skill]:
        """Fetch a skill by UUID primary key using the identity map.

        Args:
            skill_id: The UUID PK of the skill to retrieve.

        Returns:
            The matching ``Skill`` ORM instance, or ``None`` if not found.
        """
        logger.debug("get_by_id | skill_id=%s", skill_id)
        return self._session.get(Skill, skill_id)

    def name_exists_for_profession(
        self,
        name: str,
        profession_id: uuid.UUID,
        *,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> bool:
        """Check whether a skill name already exists within the given profession.

        Duplicate skill names are allowed across different professions but
        disallowed within the same profession.

        Args:
            name: The skill name to test (case-sensitive).
            profession_id: Scope the uniqueness check to this profession.
            exclude_id: UUID of the skill row to exclude from the check.
                Pass this when validating a name change on an existing row.

        Returns:
            ``True`` if the name is already taken within the profession,
            else ``False``.
        """
        logger.debug(
            "name_exists_for_profession | name=%s | profession_id=%s | exclude_id=%s",
            name, profession_id, exclude_id,
        )
        stmt = (
            select(func.count())
            .select_from(Skill)
            .where(Skill.name == name)
            .where(Skill.profession_id == profession_id)
        )
        if exclude_id is not None:
            stmt = stmt.where(Skill.id != exclude_id)
        count: int = self._session.execute(stmt).scalar_one()
        return count > 0

    def list_skills(
        self,
        *,
        profession_id: Optional[uuid.UUID] = None,
        difficulty: Optional[str] = None,
        category: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Skill]:
        """Return a paginated list of skills with optional filters.

        Results are ordered by ``name`` ascending for a stable, deterministic
        page order that does not change as new rows are inserted.

        Args:
            profession_id: Filter to skills belonging to this profession UUID.
                ``None`` = return skills across all professions.
            difficulty: Filter by difficulty level (e.g. ``'Beginner'``).
                ``None`` = return all difficulty levels.
            category: Filter by category (case-sensitive equality).
                ``None`` = return all categories.
            skip: Row offset for pagination.  Must be >= 0.
            limit: Max rows to return.  Defaults to 50; capped by the caller.

        Returns:
            A (possibly empty) list of ``Skill`` ORM instances.
        """
        logger.debug(
            "list_skills | profession_id=%s | difficulty=%s | category=%s"
            " | skip=%d | limit=%d",
            profession_id, difficulty, category, skip, limit,
        )
        stmt = select(Skill).order_by(Skill.name.asc())

        if profession_id is not None:
            stmt = stmt.where(Skill.profession_id == profession_id)
        if difficulty is not None:
            stmt = stmt.where(Skill.difficulty == difficulty)
        if category is not None:
            stmt = stmt.where(Skill.category == category)

        stmt = stmt.offset(skip).limit(limit)
        return list(self._session.execute(stmt).scalars().all())

    def count_skills(
        self,
        *,
        profession_id: Optional[uuid.UUID] = None,
        difficulty: Optional[str] = None,
        category: Optional[str] = None,
    ) -> int:
        """Return the total count matching the given filters.

        Used alongside ``list_skills`` to build pagination metadata.

        Args:
            profession_id: Same filter semantics as ``list_skills``.
            difficulty: Same filter semantics as ``list_skills``.
            category: Same filter semantics as ``list_skills``.

        Returns:
            Integer count of matching rows.
        """
        stmt = select(func.count()).select_from(Skill)
        if profession_id is not None:
            stmt = stmt.where(Skill.profession_id == profession_id)
        if difficulty is not None:
            stmt = stmt.where(Skill.difficulty == difficulty)
        if category is not None:
            stmt = stmt.where(Skill.category == category)
        return self._session.execute(stmt).scalar_one()

    # =========================================================================
    #  Write operations
    # =========================================================================

    def create_skill(
        self,
        *,
        name: str,
        profession_id: uuid.UUID,
        difficulty: str,
        description: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Skill:
        """Persist a new skill row and return the ORM instance.

        Calls ``flush()`` so that server-side defaults (``created_at``,
        ``updated_at``) are written back to the object before returning.
        The caller must commit the session.

        Args:
            name: Human-readable skill name.
            profession_id: UUID of the owning Profession (FK).
            difficulty: Difficulty level string — one of
                ``'Beginner'``, ``'Intermediate'``, ``'Advanced'``.
            description: Optional Markdown description.
            category: Optional category string.

        Returns:
            The freshly created ``Skill`` ORM instance with all
            DB-populated fields resolved.

        Raises:
            sqlalchemy.exc.IntegrityError: If the ``profession_id`` FK
                references a non-existent profession row.
            sqlalchemy.exc.SQLAlchemyError: For any other DB-level error.
            Both exceptions are raised after session rollback.
        """
        logger.debug(
            "create_skill | name=%s | profession_id=%s | difficulty=%s",
            name, profession_id, difficulty,
        )
        skill = Skill(
            name=name,
            description=description,
            difficulty=difficulty,
            category=category,
            profession_id=profession_id,
        )
        try:
            self._session.add(skill)
            self._session.flush()
            logger.info(
                "Skill created | id=%s | name=%s | profession_id=%s",
                skill.id, skill.name, skill.profession_id,
            )
            return skill
        except IntegrityError:
            logger.warning(
                "create_skill failed — constraint violation | name=%s"
                " | profession_id=%s",
                name, profession_id,
            )
            self._session.rollback()
            raise
        except SQLAlchemyError:
            logger.exception("create_skill failed | name=%s", name)
            self._session.rollback()
            raise

    def update_skill(
        self,
        skill: Skill,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        difficulty: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Skill:
        """Apply a partial update to an existing skill row (PATCH semantics).

        Only keyword arguments that are **not** ``None`` are written.  The
        method flushes after mutation so that ``updated_at`` is refreshed and
        the object reflects the current DB state.

        Args:
            skill: The ``Skill`` ORM instance to update (must be attached
                to this session).
            name: New display name, or ``None`` to leave unchanged.
            description: New description, or ``None`` to leave unchanged.
            difficulty: New difficulty level, or ``None`` to leave unchanged.
            category: New category, or ``None`` to leave unchanged.

        Returns:
            The updated ``Skill`` ORM instance.

        Raises:
            sqlalchemy.exc.SQLAlchemyError: For any DB-level error (after
                session rollback).
        """
        logger.debug("update_skill | id=%s", skill.id)

        if name is not None:
            skill.name = name
        if description is not None:
            skill.description = description
        if difficulty is not None:
            skill.difficulty = difficulty
        if category is not None:
            skill.category = category

        try:
            self._session.flush()
            logger.info("Skill updated | id=%s", skill.id)
            return skill
        except IntegrityError:
            logger.warning(
                "update_skill failed — constraint violation | id=%s", skill.id
            )
            self._session.rollback()
            raise
        except SQLAlchemyError:
            logger.exception("update_skill failed | id=%s", skill.id)
            self._session.rollback()
            raise

    def delete_skill(self, skill: Skill) -> None:
        """Hard-delete a skill row from the database.

        Unlike the Profession domain, Skills do not have a soft-delete
        ``is_active`` flag — they are reference data entries that can be
        cleanly removed when no longer relevant to a profession.

        Args:
            skill: The ``Skill`` ORM instance to delete (must be attached
                to this session).

        Raises:
            sqlalchemy.exc.SQLAlchemyError: On any DB-level failure (after
                session rollback).
        """
        logger.debug("delete_skill | id=%s | name=%s", skill.id, skill.name)
        try:
            self._session.delete(skill)
            self._session.flush()
            logger.info("Skill deleted | id=%s | name=%s", skill.id, skill.name)
        except SQLAlchemyError:
            logger.exception("delete_skill failed | id=%s", skill.id)
            self._session.rollback()
            raise
