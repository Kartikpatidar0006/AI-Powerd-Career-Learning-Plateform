"""
backend/app/services/profession.py
=====================================
Business-logic service for the Profession domain.

Architecture role
-----------------
``ProfessionService`` is the **orchestration layer** between the HTTP
transport (router) and the data-access layer (``ProfessionRepository``).

Layer rules enforced here:
  • No FastAPI imports at module scope — no ``HTTPException``, ``Request``.
  • No raw SQL — every DB access goes through ``ProfessionRepository``.
  • Raises ``ProfessionError`` (defined below) for all business-rule
    violations.  The HTTP router maps those to ``HTTPException``.
  • Commits after every successful write operation; never calls ``close()``.

Transaction ownership
---------------------
The ``Session`` is always injected from outside.  ``ProfessionService``
commits on success; the ``get_db`` dependency in the router handles rollback
on unhandled exceptions.

Usage example::

    from sqlalchemy.orm import Session
    from app.services.profession import ProfessionService

    svc = ProfessionService(db)
    profession = svc.create_profession(payload)
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.profession import Profession
from app.repositories.profession import ProfessionRepository
from app.schemas.profession import (
    ProfessionCreate,
    ProfessionListResponse,
    ProfessionResponse,
    ProfessionUpdate,
)

logger: logging.Logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Domain exception
# ─────────────────────────────────────────────────────────────────────────────


class ProfessionError(Exception):
    """Business-rule violation raised by ``ProfessionService``.

    The HTTP router is the only layer that catches this exception and converts
    it to an ``HTTPException`` with the appropriate status code.

    Attributes:
        message: Safe, user-facing description.
        code: Machine-readable snake_case code for HTTP status mapping.

    Code constants:
        ``NOT_FOUND``     — profession UUID does not exist.
        ``SLUG_TAKEN``    — slug already in use by another profession.
        ``NAME_TAKEN``    — name already in use by another profession.
        ``ALREADY_DELETED`` — profession is already inactive.
    """

    NOT_FOUND: str = "not_found"
    SLUG_TAKEN: str = "slug_taken"
    NAME_TAKEN: str = "name_taken"
    ALREADY_DELETED: str = "already_deleted"

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code

    def __repr__(self) -> str:
        return f"ProfessionError(code={self.code!r}, message={self.message!r})"


# ─────────────────────────────────────────────────────────────────────────────
# ProfessionService
# ─────────────────────────────────────────────────────────────────────────────


class ProfessionService:
    """Orchestrates all profession CRUD and business-logic workflows.

    Stateless beyond the injected session.  Instantiate once per request.

    Args:
        session: An active SQLAlchemy ``Session``.  The service commits on
            successful writes; the caller handles session cleanup.
    """

    def __init__(self, session: Session) -> None:
        self._db = session
        self._repo = ProfessionRepository(session)

    # ── Internal helpers ─────────────────────────────────────────────────── #

    def _get_or_404(self, profession_id: uuid.UUID) -> Profession:
        """Load a profession by ID or raise ``ProfessionError(NOT_FOUND)``.

        Args:
            profession_id: UUID of the profession to load.

        Returns:
            The ``Profession`` ORM instance.

        Raises:
            ProfessionError: With code ``NOT_FOUND`` if no row matches.
        """
        profession = self._repo.get_by_id(profession_id)
        if profession is None:
            raise ProfessionError(
                f"Profession with id '{profession_id}' was not found.",
                code=ProfessionError.NOT_FOUND,
            )
        return profession

    def _assert_slug_available(
        self, slug: str, *, exclude_id: Optional[uuid.UUID] = None
    ) -> None:
        """Raise ``ProfessionError(SLUG_TAKEN)`` if the slug is already in use.

        Args:
            slug: The slug to check.
            exclude_id: UUID to exclude (for updates — allows saving same slug).

        Raises:
            ProfessionError: With code ``SLUG_TAKEN`` if taken.
        """
        if self._repo.slug_exists(slug, exclude_id=exclude_id):
            raise ProfessionError(
                f"The slug '{slug}' is already in use by another profession.",
                code=ProfessionError.SLUG_TAKEN,
            )

    def _assert_name_available(
        self, name: str, *, exclude_id: Optional[uuid.UUID] = None
    ) -> None:
        """Raise ``ProfessionError(NAME_TAKEN)`` if the name is already in use.

        Args:
            name: The name to check.
            exclude_id: UUID to exclude (for updates).

        Raises:
            ProfessionError: With code ``NAME_TAKEN`` if taken.
        """
        if self._repo.name_exists(name, exclude_id=exclude_id):
            raise ProfessionError(
                f"The profession name '{name}' is already in use.",
                code=ProfessionError.NAME_TAKEN,
            )

    # ── Public service methods ────────────────────────────────────────────── #

    def create_profession(self, payload: ProfessionCreate) -> ProfessionResponse:
        """Create a new profession and return the full response schema.

        Workflow:
            1. Assert the name is not already taken.
            2. Assert the slug is not already taken.
            3. Persist the new profession via the repository.
            4. Commit the transaction.
            5. Return the serialised ``ProfessionResponse``.

        Args:
            payload: Validated ``ProfessionCreate`` schema from the request body.

        Returns:
            ``ProfessionResponse`` representing the newly created profession.

        Raises:
            ProfessionError: With code ``NAME_TAKEN`` if the name conflicts.
            ProfessionError: With code ``SLUG_TAKEN`` if the slug conflicts.

        Example::

            response = svc.create_profession(ProfessionCreate(
                name="Data Engineer",
                slug="data-engineer",
                category="Engineering",
            ))
        """
        logger.info("create_profession | name=%s | slug=%s", payload.name, payload.slug)

        self._assert_name_available(payload.name)
        self._assert_slug_available(payload.slug)

        profession = self._repo.create_profession(
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
            category=payload.category,
            average_salary=payload.average_salary,
            growth_rate=payload.growth_rate,
            required_skills=payload.required_skills,
            roadmap=payload.roadmap,
            is_active=payload.is_active,
        )
        self._db.commit()
        logger.info("Profession created | id=%s", profession.id)
        return ProfessionResponse.model_validate(profession)

    def get_profession(self, profession_id: uuid.UUID) -> ProfessionResponse:
        """Fetch a single profession by UUID.

        Args:
            profession_id: UUID of the profession to retrieve.

        Returns:
            Full ``ProfessionResponse`` for the matching profession.

        Raises:
            ProfessionError: With code ``NOT_FOUND`` if no matching row.
        """
        logger.debug("get_profession | id=%s", profession_id)
        profession = self._get_or_404(profession_id)
        return ProfessionResponse.model_validate(profession)

    def get_profession_by_slug(self, slug: str) -> ProfessionResponse:
        """Fetch a single profession by slug.

        Args:
            slug: The URL-safe slug of the profession.

        Returns:
            Full ``ProfessionResponse`` for the matching profession.

        Raises:
            ProfessionError: With code ``NOT_FOUND`` if no matching row.
        """
        logger.debug("get_profession_by_slug | slug=%s", slug)
        profession = self._repo.get_by_slug(slug)
        if profession is None:
            raise ProfessionError(
                f"Profession with slug '{slug}' was not found.",
                code=ProfessionError.NOT_FOUND,
            )
        return ProfessionResponse.model_validate(profession)

    def list_professions(
        self,
        *,
        is_active: Optional[bool] = None,
        category: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> dict:
        """Return a paginated list of professions with total count.

        Returns a dict with ``items`` (slim list schema) and ``total``
        (count matching filters) so the router can construct a consistent
        pagination envelope.

        Args:
            is_active: Filter by active status (``None`` = all).
            category: Filter by category (``None`` = all).
            skip: Offset for pagination.
            limit: Max items to return (1–200, enforced by the router query
                parameter validator).

        Returns:
            ``{"items": list[ProfessionListResponse], "total": int,
               "skip": int, "limit": int}``
        """
        logger.debug(
            "list_professions | is_active=%s | category=%s | skip=%d | limit=%d",
            is_active, category, skip, limit,
        )
        professions = self._repo.list_professions(
            is_active=is_active,
            category=category,
            skip=skip,
            limit=limit,
        )
        total = self._repo.count_professions(
            is_active=is_active,
            category=category,
        )
        return {
            "items": [ProfessionListResponse.model_validate(p) for p in professions],
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    def update_profession(
        self,
        profession_id: uuid.UUID,
        payload: ProfessionUpdate,
    ) -> ProfessionResponse:
        """Apply a partial update to a profession (PATCH semantics).

        Workflow:
            1. Load the profession (404 if not found).
            2. If a new name is provided, assert it is not taken by another row.
            3. If a new slug is provided, assert it is not taken by another row.
            4. Apply changes via the repository (only non-None fields written).
            5. Commit the transaction.
            6. Return the updated ``ProfessionResponse``.

        Args:
            profession_id: UUID of the profession to update.
            payload: Validated ``ProfessionUpdate`` schema (all fields optional).

        Returns:
            Updated ``ProfessionResponse``.

        Raises:
            ProfessionError: ``NOT_FOUND`` if the profession does not exist.
            ProfessionError: ``NAME_TAKEN`` if the new name conflicts.
            ProfessionError: ``SLUG_TAKEN`` if the new slug conflicts.
        """
        logger.info("update_profession | id=%s", profession_id)

        profession = self._get_or_404(profession_id)

        if payload.name is not None:
            self._assert_name_available(payload.name, exclude_id=profession_id)
        if payload.slug is not None:
            self._assert_slug_available(payload.slug, exclude_id=profession_id)

        updated = self._repo.update_profession(
            profession,
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
            category=payload.category,
            average_salary=payload.average_salary,
            growth_rate=payload.growth_rate,
            required_skills=payload.required_skills,
            roadmap=payload.roadmap,
            is_active=payload.is_active,
        )
        self._db.commit()
        logger.info("Profession updated | id=%s", updated.id)
        return ProfessionResponse.model_validate(updated)

    def delete_profession(self, profession_id: uuid.UUID) -> ProfessionResponse:
        """Soft-delete a profession by setting ``is_active = False``.

        Hard DELETE is deliberately not supported — other tables (user
        profiles, interviews, tasks) may reference professions; removing the
        row would violate referential integrity or cascade unwanted deletes.

        Args:
            profession_id: UUID of the profession to soft-delete.

        Returns:
            The updated ``ProfessionResponse`` with ``is_active=False``.

        Raises:
            ProfessionError: ``NOT_FOUND`` if the profession does not exist.
            ProfessionError: ``ALREADY_DELETED`` if ``is_active`` is already
                ``False`` (idempotent guard — prevents redundant commits).
        """
        logger.info("delete_profession | id=%s", profession_id)

        profession = self._get_or_404(profession_id)

        if not profession.is_active:
            raise ProfessionError(
                "This profession is already inactive.",
                code=ProfessionError.ALREADY_DELETED,
            )

        deleted = self._repo.soft_delete_profession(profession)
        self._db.commit()
        logger.info("Profession soft-deleted | id=%s", deleted.id)
        return ProfessionResponse.model_validate(deleted)
