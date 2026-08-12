"""
backend/app/services/skill.py
================================
Business-logic service for the Skill domain.

Architecture role
-----------------
``SkillService`` is the **orchestration layer** between the HTTP
transport (router) and the data-access layer (``SkillRepository``).

Layer rules enforced here:
  • No FastAPI imports at module scope — no ``HTTPException``, ``Request``.
  • No raw SQL — every DB access goes through ``SkillRepository`` or
    ``ProfessionRepository`` (for FK existence validation).
  • Raises ``SkillError`` (defined below) for all business-rule
    violations.  The HTTP router maps those to ``HTTPException``.
  • Commits after every successful write operation; never calls ``close()``.

Transaction ownership
---------------------
The ``Session`` is always injected from outside.  ``SkillService``
commits on success; the ``get_db`` dependency in the router handles rollback
on unhandled exceptions.

Usage example::

    from sqlalchemy.orm import Session
    from app.services.skill import SkillService

    svc = SkillService(db)
    skill = svc.create_skill(payload)
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.skill import Skill
from app.repositories.profession import ProfessionRepository
from app.repositories.skill import SkillRepository
from app.schemas.skill import (
    SkillCreate,
    SkillListResponse,
    SkillResponse,
    SkillUpdate,
)

logger: logging.Logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Domain exception
# ─────────────────────────────────────────────────────────────────────────────


class SkillError(Exception):
    """Business-rule violation raised by ``SkillService``.

    The HTTP router is the only layer that catches this exception and converts
    it to an ``HTTPException`` with the appropriate status code.

    Attributes:
        message: Safe, user-facing description.
        code: Machine-readable snake_case code for HTTP status mapping.

    Code constants:
        ``NOT_FOUND``          — skill UUID does not exist.
        ``PROFESSION_NOT_FOUND`` — referenced profession UUID does not exist.
        ``NAME_TAKEN``         — skill name already in use within the profession.
    """

    NOT_FOUND: str = "not_found"
    PROFESSION_NOT_FOUND: str = "profession_not_found"
    NAME_TAKEN: str = "name_taken"

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code

    def __repr__(self) -> str:
        return f"SkillError(code={self.code!r}, message={self.message!r})"


# ─────────────────────────────────────────────────────────────────────────────
# SkillService
# ─────────────────────────────────────────────────────────────────────────────


class SkillService:
    """Orchestrates all skill CRUD and business-logic workflows.

    Stateless beyond the injected session.  Instantiate once per request.

    Args:
        session: An active SQLAlchemy ``Session``.  The service commits on
            successful writes; the caller handles session cleanup.
    """

    def __init__(self, session: Session) -> None:
        self._db = session
        self._repo = SkillRepository(session)
        self._profession_repo = ProfessionRepository(session)

    # ── Internal helpers ─────────────────────────────────────────────────── #

    def _get_or_404(self, skill_id: uuid.UUID) -> Skill:
        """Load a skill by ID or raise ``SkillError(NOT_FOUND)``.

        Args:
            skill_id: UUID of the skill to load.

        Returns:
            The ``Skill`` ORM instance.

        Raises:
            SkillError: With code ``NOT_FOUND`` if no row matches.
        """
        skill = self._repo.get_by_id(skill_id)
        if skill is None:
            raise SkillError(
                f"Skill with id '{skill_id}' was not found.",
                code=SkillError.NOT_FOUND,
            )
        return skill

    def _assert_profession_exists(self, profession_id: uuid.UUID) -> None:
        """Raise ``SkillError(PROFESSION_NOT_FOUND)`` if the profession is missing.

        Args:
            profession_id: UUID of the profession to validate.

        Raises:
            SkillError: With code ``PROFESSION_NOT_FOUND`` if missing.
        """
        if self._profession_repo.get_by_id(profession_id) is None:
            raise SkillError(
                f"Profession with id '{profession_id}' was not found.",
                code=SkillError.PROFESSION_NOT_FOUND,
            )

    def _assert_name_available(
        self,
        name: str,
        profession_id: uuid.UUID,
        *,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Raise ``SkillError(NAME_TAKEN)`` if the name is already in use.

        Uniqueness is scoped to the profession — two different professions
        can share the same skill name (e.g. both "Data Engineering" and
        "Machine Learning" can have "Python").

        Args:
            name: The skill name to check.
            profession_id: Scope the check to this profession.
            exclude_id: UUID to exclude (for updates — allows saving the
                same name without triggering a false conflict).

        Raises:
            SkillError: With code ``NAME_TAKEN`` if taken.
        """
        if self._repo.name_exists_for_profession(
            name, profession_id, exclude_id=exclude_id
        ):
            raise SkillError(
                f"A skill named '{name}' already exists for this profession.",
                code=SkillError.NAME_TAKEN,
            )

    # ── Public service methods ────────────────────────────────────────────── #

    def create_skill(self, payload: SkillCreate) -> SkillResponse:
        """Create a new skill and return the full response schema.

        Workflow:
            1. Assert the referenced profession exists.
            2. Assert the skill name is not already taken in this profession.
            3. Persist the new skill via the repository.
            4. Commit the transaction.
            5. Return the serialised ``SkillResponse``.

        Args:
            payload: Validated ``SkillCreate`` schema from the request body.

        Returns:
            ``SkillResponse`` representing the newly created skill.

        Raises:
            SkillError: With code ``PROFESSION_NOT_FOUND`` if the FK is invalid.
            SkillError: With code ``NAME_TAKEN`` if the name conflicts within
                the same profession.

        Example::

            response = svc.create_skill(SkillCreate(
                name="Python",
                difficulty="Intermediate",
                category="Programming",
                profession_id=some_uuid,
            ))
        """
        logger.info(
            "create_skill | name=%s | profession_id=%s | difficulty=%s",
            payload.name, payload.profession_id, payload.difficulty,
        )

        self._assert_profession_exists(payload.profession_id)
        self._assert_name_available(payload.name, payload.profession_id)

        skill = self._repo.create_skill(
            name=payload.name,
            description=payload.description,
            difficulty=payload.difficulty.value,
            category=payload.category,
            profession_id=payload.profession_id,
        )
        self._db.commit()
        logger.info("Skill created | id=%s", skill.id)
        return SkillResponse.model_validate(skill)

    def get_skill(self, skill_id: uuid.UUID) -> SkillResponse:
        """Fetch a single skill by UUID.

        Args:
            skill_id: UUID of the skill to retrieve.

        Returns:
            Full ``SkillResponse`` for the matching skill.

        Raises:
            SkillError: With code ``NOT_FOUND`` if no matching row.
        """
        logger.debug("get_skill | id=%s", skill_id)
        skill = self._get_or_404(skill_id)
        return SkillResponse.model_validate(skill)

    def list_skills(
        self,
        *,
        profession_id: Optional[uuid.UUID] = None,
        difficulty: Optional[str] = None,
        category: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> dict:
        """Return a paginated list of skills with total count.

        Returns a dict with ``items`` (slim list schema) and ``total``
        (count matching filters) so the router can construct a consistent
        pagination envelope.

        Args:
            profession_id: Filter to skills belonging to this profession UUID.
            difficulty: Filter by difficulty level.
            category: Filter by category.
            skip: Offset for pagination.
            limit: Max items to return (1–200, enforced by the router query
                parameter validator).

        Returns:
            ``{"items": list[SkillListResponse], "total": int,
               "skip": int, "limit": int}``
        """
        logger.debug(
            "list_skills | profession_id=%s | difficulty=%s | category=%s"
            " | skip=%d | limit=%d",
            profession_id, difficulty, category, skip, limit,
        )
        skills = self._repo.list_skills(
            profession_id=profession_id,
            difficulty=difficulty,
            category=category,
            skip=skip,
            limit=limit,
        )
        total = self._repo.count_skills(
            profession_id=profession_id,
            difficulty=difficulty,
            category=category,
        )
        return {
            "items": [SkillListResponse.model_validate(s) for s in skills],
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    def update_skill(
        self,
        skill_id: uuid.UUID,
        payload: SkillUpdate,
    ) -> SkillResponse:
        """Apply a partial update to a skill (PATCH semantics).

        Workflow:
            1. Load the skill (404 if not found).
            2. If a new name is provided, assert it is not taken within
               the same profession.
            3. Apply changes via the repository (only non-None fields written).
            4. Commit the transaction.
            5. Return the updated ``SkillResponse``.

        Args:
            skill_id: UUID of the skill to update.
            payload: Validated ``SkillUpdate`` schema (all fields optional).

        Returns:
            Updated ``SkillResponse``.

        Raises:
            SkillError: ``NOT_FOUND`` if the skill does not exist.
            SkillError: ``NAME_TAKEN`` if the new name conflicts within the
                same profession.
        """
        logger.info("update_skill | id=%s", skill_id)

        skill = self._get_or_404(skill_id)

        if payload.name is not None:
            self._assert_name_available(
                payload.name, skill.profession_id, exclude_id=skill_id
            )

        updated = self._repo.update_skill(
            skill,
            name=payload.name,
            description=payload.description,
            difficulty=payload.difficulty.value if payload.difficulty is not None else None,
            category=payload.category,
        )
        self._db.commit()
        logger.info("Skill updated | id=%s", updated.id)
        return SkillResponse.model_validate(updated)

    def delete_skill(self, skill_id: uuid.UUID) -> dict:
        """Hard-delete a skill by UUID.

        Unlike the Profession domain, Skills support full hard-DELETE since
        they are granular competency entries without deep referential
        dependencies.  The deleted skill's ``id`` and ``name`` are returned
        in the confirmation envelope.

        Args:
            skill_id: UUID of the skill to delete.

        Returns:
            Confirmation envelope::

                {
                    "deleted": true,
                    "id": "<uuid>",
                    "name": "<skill name>"
                }

        Raises:
            SkillError: ``NOT_FOUND`` if the skill does not exist.
        """
        logger.info("delete_skill | id=%s", skill_id)

        skill = self._get_or_404(skill_id)
        skill_id_str = str(skill.id)
        skill_name = skill.name

        self._repo.delete_skill(skill)
        self._db.commit()
        logger.info("Skill hard-deleted | id=%s | name=%s", skill_id_str, skill_name)

        return {
            "deleted": True,
            "id": skill_id_str,
            "name": skill_name,
        }
