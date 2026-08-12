"""
backend/app/repositories/profession.py
========================================
Repository pattern implementation for the ``professions`` table.

Architecture contract
---------------------
- **Single responsibility**: SQL only.  No business logic, no schema
  validation, no password or JWT handling.
- **Session ownership**: the caller (service or ``get_db`` dependency) owns
  commit / rollback / close.  This repository calls ``flush()`` after
  mutating operations to surface ``IntegrityError`` early and resolve
  server-side defaults before returning.
- **Returns ORM objects only**: ``Profession`` instances or ``list[Profession]``
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

from app.models.profession import Profession

logger: logging.Logger = logging.getLogger(__name__)


class ProfessionRepository:
    """Data-access layer for the ``professions`` table.

    All public methods issue exactly one logical SQL statement (SELECT, INSERT,
    UPDATE).  PATCH semantics (only non-``None`` fields updated) are handled
    in ``update_profession`` so that the service layer passes values directly.

    Args:
        session: An active SQLAlchemy ``Session``.  The caller is responsible
            for committing or rolling back after each service-level operation.

    Example::

        repo = ProfessionRepository(db)
        profession = repo.get_by_id(some_uuid)
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # =========================================================================
    #  Read operations
    # =========================================================================

    def get_by_id(self, profession_id: uuid.UUID) -> Optional[Profession]:
        """Fetch a profession by UUID primary key using the identity map.

        Args:
            profession_id: The UUID PK of the profession to retrieve.

        Returns:
            The matching ``Profession`` ORM instance, or ``None`` if not found.
        """
        logger.debug("get_by_id | profession_id=%s", profession_id)
        return self._session.get(Profession, profession_id)

    def get_by_slug(self, slug: str) -> Optional[Profession]:
        """Fetch a profession by its URL-safe slug.

        Served by the unique index on ``professions.slug``.

        Args:
            slug: The normalised slug string to look up.

        Returns:
            The matching ``Profession`` ORM instance, or ``None``.
        """
        logger.debug("get_by_slug | slug=%s", slug)
        stmt = select(Profession).where(Profession.slug == slug)
        return self._session.execute(stmt).scalar_one_or_none()

    def slug_exists(self, slug: str, *, exclude_id: Optional[uuid.UUID] = None) -> bool:
        """Check whether a slug is already in use.

        Optionally excludes one row (used during update to allow re-saving
        the same slug without triggering a false duplicate error).

        Args:
            slug: The slug to test.
            exclude_id: UUID of the profession row to exclude from the check.
                Pass this when validating a slug change on an existing row.

        Returns:
            ``True`` if the slug is already taken by another row, else ``False``.
        """
        logger.debug("slug_exists | slug=%s | exclude_id=%s", slug, exclude_id)
        stmt = select(func.count()).select_from(Profession).where(
            Profession.slug == slug
        )
        if exclude_id is not None:
            stmt = stmt.where(Profession.id != exclude_id)
        count: int = self._session.execute(stmt).scalar_one()
        return count > 0

    def name_exists(self, name: str, *, exclude_id: Optional[uuid.UUID] = None) -> bool:
        """Check whether a profession name is already in use.

        Args:
            name: The name to test (case-sensitive).
            exclude_id: UUID of the row to exclude (for update validations).

        Returns:
            ``True`` if the name is taken by another row, else ``False``.
        """
        logger.debug("name_exists | name=%s | exclude_id=%s", name, exclude_id)
        stmt = select(func.count()).select_from(Profession).where(
            Profession.name == name
        )
        if exclude_id is not None:
            stmt = stmt.where(Profession.id != exclude_id)
        count: int = self._session.execute(stmt).scalar_one()
        return count > 0

    def list_professions(
        self,
        *,
        is_active: Optional[bool] = None,
        category: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Profession]:
        """Return a paginated list of professions with optional filters.

        Results are ordered by ``name`` ascending for a stable, deterministic
        page order that does not change as new rows are inserted.

        Args:
            is_active: Filter by active status.  ``None`` = return all.
            category: Filter by category (case-sensitive equality).
                ``None`` = return all categories.
            skip: Row offset for pagination.  Must be >= 0.
            limit: Max rows to return.  Defaults to 50; capped by the caller.

        Returns:
            A (possibly empty) list of ``Profession`` ORM instances.
        """
        logger.debug(
            "list_professions | is_active=%s | category=%s | skip=%d | limit=%d",
            is_active, category, skip, limit,
        )
        stmt = select(Profession).order_by(Profession.name.asc())

        if is_active is not None:
            stmt = stmt.where(Profession.is_active == is_active)
        if category is not None:
            stmt = stmt.where(Profession.category == category)

        stmt = stmt.offset(skip).limit(limit)
        return list(self._session.execute(stmt).scalars().all())

    def count_professions(
        self,
        *,
        is_active: Optional[bool] = None,
        category: Optional[str] = None,
    ) -> int:
        """Return the total count matching the given filters.

        Used alongside ``list_professions`` to build pagination metadata.

        Args:
            is_active: Same filter semantics as ``list_professions``.
            category: Same filter semantics as ``list_professions``.

        Returns:
            Integer count of matching rows.
        """
        stmt = select(func.count()).select_from(Profession)
        if is_active is not None:
            stmt = stmt.where(Profession.is_active == is_active)
        if category is not None:
            stmt = stmt.where(Profession.category == category)
        return self._session.execute(stmt).scalar_one()

    # =========================================================================
    #  Write operations
    # =========================================================================

    def create_profession(
        self,
        *,
        name: str,
        slug: str,
        description: Optional[str] = None,
        category: Optional[str] = None,
        average_salary: Optional[float] = None,
        growth_rate: Optional[float] = None,
        required_skills: Optional[list[str]] = None,
        roadmap: Optional[dict] = None,
        is_active: bool = True,
    ) -> Profession:
        """Persist a new profession row and return the ORM instance.

        Calls ``flush()`` so that server-side defaults (``created_at``,
        ``updated_at``) are written back to the object before returning.
        The caller must commit the session.

        Args:
            name: Human-readable profession name (must be unique).
            slug: URL-safe identifier (must be unique, pre-normalised).
            description: Optional Markdown description.
            category: Optional category string.
            average_salary: Optional indicative annual salary (USD).
            growth_rate: Optional projected YoY growth %.
            required_skills: Ordered list of required skill strings.
            roadmap: Structured roadmap JSON.
            is_active: Whether the profession is active (default ``True``).

        Returns:
            The freshly created ``Profession`` ORM instance with all
            DB-populated fields resolved.

        Raises:
            sqlalchemy.exc.IntegrityError: If ``name`` or ``slug`` already
                exists (unique constraint violation).
            sqlalchemy.exc.SQLAlchemyError: For any other DB-level error.
            Both exceptions are raised after session rollback.
        """
        logger.debug("create_profession | name=%s | slug=%s", name, slug)
        profession = Profession(
            name=name,
            slug=slug,
            description=description,
            category=category,
            average_salary=average_salary,
            growth_rate=growth_rate,
            required_skills=required_skills or [],
            roadmap=roadmap or {},
            is_active=is_active,
        )
        try:
            self._session.add(profession)
            self._session.flush()
            logger.info(
                "Profession created | id=%s | name=%s", profession.id, profession.name
            )
            return profession
        except IntegrityError:
            logger.warning(
                "create_profession failed — constraint violation | name=%s | slug=%s",
                name, slug,
            )
            self._session.rollback()
            raise
        except SQLAlchemyError:
            logger.exception("create_profession failed | name=%s", name)
            self._session.rollback()
            raise

    def update_profession(
        self,
        profession: Profession,
        *,
        name: Optional[str] = None,
        slug: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        average_salary: Optional[float] = None,
        growth_rate: Optional[float] = None,
        required_skills: Optional[list[str]] = None,
        roadmap: Optional[dict] = None,
        is_active: Optional[bool] = None,
    ) -> Profession:
        """Apply a partial update to an existing profession row (PATCH semantics).

        Only keyword arguments that are **not** ``None`` are written.  The
        method flushes after mutation so that ``updated_at`` is refreshed and
        the object reflects the current DB state.

        Args:
            profession: The ``Profession`` ORM instance to update (must be
                attached to this session).
            name: New display name, or ``None`` to leave unchanged.
            slug: New slug, or ``None`` to leave unchanged.
            description: New description, or ``None`` to leave unchanged.
            category: New category, or ``None`` to leave unchanged.
            average_salary: New salary, or ``None`` to leave unchanged.
            growth_rate: New growth rate, or ``None`` to leave unchanged.
            required_skills: Replacement skill list, or ``None`` to leave unchanged.
            roadmap: Replacement roadmap, or ``None`` to leave unchanged.
            is_active: New active status, or ``None`` to leave unchanged.

        Returns:
            The updated ``Profession`` ORM instance.

        Raises:
            sqlalchemy.exc.IntegrityError: If the new name or slug conflicts
                with an existing row.
            sqlalchemy.exc.SQLAlchemyError: For any other DB-level error.
            Both exceptions raised after session rollback.
        """
        logger.debug("update_profession | id=%s", profession.id)

        if name is not None:
            profession.name = name
        if slug is not None:
            profession.slug = slug
        if description is not None:
            profession.description = description
        if category is not None:
            profession.category = category
        if average_salary is not None:
            profession.average_salary = average_salary
        if growth_rate is not None:
            profession.growth_rate = growth_rate
        if required_skills is not None:
            profession.required_skills = required_skills
        if roadmap is not None:
            profession.roadmap = roadmap
        if is_active is not None:
            profession.is_active = is_active

        try:
            self._session.flush()
            logger.info("Profession updated | id=%s", profession.id)
            return profession
        except IntegrityError:
            logger.warning(
                "update_profession failed — constraint violation | id=%s", profession.id
            )
            self._session.rollback()
            raise
        except SQLAlchemyError:
            logger.exception("update_profession failed | id=%s", profession.id)
            self._session.rollback()
            raise

    def soft_delete_profession(self, profession: Profession) -> Profession:
        """Soft-delete a profession by setting ``is_active = False``.

        Preserves the row for referential integrity and audit history.
        The profession will no longer appear in active listings.

        Args:
            profession: The ``Profession`` ORM instance to deactivate.

        Returns:
            The updated ``Profession`` ORM instance with ``is_active=False``.

        Raises:
            sqlalchemy.exc.SQLAlchemyError: On any DB-level failure (after
                session rollback).
        """
        logger.debug("soft_delete_profession | id=%s", profession.id)
        profession.is_active = False
        try:
            self._session.flush()
            logger.info(
                "Profession soft-deleted | id=%s | name=%s",
                profession.id, profession.name,
            )
            return profession
        except SQLAlchemyError:
            logger.exception("soft_delete_profession failed | id=%s", profession.id)
            self._session.rollback()
            raise
