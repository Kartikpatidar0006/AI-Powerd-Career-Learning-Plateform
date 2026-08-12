"""
backend/app/services/career_roadmap.py
========================================
Business-logic services for the CareerRoadmap and RoadmapStep domains.

Architecture role
-----------------
``CareerRoadmapService`` and ``RoadmapStepService`` are the **orchestration
layer** between the HTTP transport (router) and the data-access layer
(``CareerRoadmapRepository`` / ``RoadmapStepRepository``).

Layer rules enforced here:
  • No FastAPI imports at module scope — no ``HTTPException``, ``Request``.
  • No raw SQL — every DB access goes through the repository layer.
  • Raises ``CareerRoadmapError`` for all business-rule violations.  The
    HTTP router maps those to ``HTTPException``.
  • Commits after every successful write operation; never calls ``close()``.

Transaction ownership
---------------------
The ``Session`` is always injected from outside.  Services commit on success;
the ``get_db`` dependency in the router handles rollback on unhandled
exceptions.

Usage example::

    svc = CareerRoadmapService(db)
    roadmap = svc.create_roadmap(payload)

    step_svc = RoadmapStepService(db)
    step = step_svc.create_step(step_payload)
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.career_roadmap import CareerRoadmap, RoadmapStep
from app.repositories.career_roadmap import (
    CareerRoadmapRepository,
    RoadmapStepRepository,
)
from app.repositories.profession import ProfessionRepository
from app.repositories.skill import SkillRepository
from app.schemas.career_roadmap import (
    CareerRoadmapCreate,
    CareerRoadmapListResponse,
    CareerRoadmapResponse,
    CareerRoadmapUpdate,
    RoadmapStepCreate,
    RoadmapStepListResponse,
    RoadmapStepResponse,
    RoadmapStepUpdate,
)

logger: logging.Logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Domain exception
# ─────────────────────────────────────────────────────────────────────────────


class CareerRoadmapError(Exception):
    """Business-rule violation raised by career roadmap services.

    The HTTP router is the only layer that catches this exception and converts
    it to an ``HTTPException`` with the appropriate status code.

    Attributes:
        message: Safe, user-facing description.
        code: Machine-readable snake_case code for HTTP status mapping.

    Code constants:
        ``NOT_FOUND``            — roadmap/step UUID does not exist.
        ``PROFESSION_NOT_FOUND`` — referenced profession UUID does not exist.
        ``SKILL_NOT_FOUND``      — referenced skill UUID does not exist.
        ``TITLE_TAKEN``          — roadmap title already exists for this profession.
        ``ORDER_TAKEN``          — step_order already in use within this roadmap.
        ``SKILL_DUPLICATE``      — skill already appears as a step in this roadmap.
        ``ROADMAP_NOT_FOUND``    — step's roadmap_id references a missing roadmap.
    """

    NOT_FOUND: str = "not_found"
    PROFESSION_NOT_FOUND: str = "profession_not_found"
    SKILL_NOT_FOUND: str = "skill_not_found"
    TITLE_TAKEN: str = "title_taken"
    ORDER_TAKEN: str = "order_taken"
    SKILL_DUPLICATE: str = "skill_duplicate"
    ROADMAP_NOT_FOUND: str = "roadmap_not_found"

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code

    def __repr__(self) -> str:
        return (
            f"CareerRoadmapError(code={self.code!r},"
            f" message={self.message!r})"
        )


# ─────────────────────────────────────────────────────────────────────────────
# CareerRoadmapService
# ─────────────────────────────────────────────────────────────────────────────


class CareerRoadmapService:
    """Orchestrates all CareerRoadmap CRUD and business-logic workflows.

    Args:
        session: An active SQLAlchemy ``Session``.
    """

    def __init__(self, session: Session) -> None:
        self._db = session
        self._repo = CareerRoadmapRepository(session)
        self._profession_repo = ProfessionRepository(session)

    # ── Internal helpers ─────────────────────────────────────────────────── #

    def _get_or_404(self, roadmap_id: uuid.UUID) -> CareerRoadmap:
        """Load a roadmap or raise ``CareerRoadmapError(NOT_FOUND)``.

        Args:
            roadmap_id: UUID of the roadmap to load.

        Returns:
            The ``CareerRoadmap`` ORM instance.

        Raises:
            CareerRoadmapError: With code ``NOT_FOUND`` if no row matches.
        """
        roadmap = self._repo.get_by_id(roadmap_id)
        if roadmap is None:
            raise CareerRoadmapError(
                f"Career roadmap with id '{roadmap_id}' was not found.",
                code=CareerRoadmapError.NOT_FOUND,
            )
        return roadmap

    def _assert_profession_exists(self, profession_id: uuid.UUID) -> None:
        """Raise ``CareerRoadmapError(PROFESSION_NOT_FOUND)`` if missing.

        Args:
            profession_id: UUID of the profession to validate.

        Raises:
            CareerRoadmapError: With code ``PROFESSION_NOT_FOUND``.
        """
        if self._profession_repo.get_by_id(profession_id) is None:
            raise CareerRoadmapError(
                f"Profession with id '{profession_id}' was not found.",
                code=CareerRoadmapError.PROFESSION_NOT_FOUND,
            )

    def _assert_title_available(
        self,
        profession_id: uuid.UUID,
        title: str,
        *,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Raise ``CareerRoadmapError(TITLE_TAKEN)`` if the title is taken.

        Uniqueness is scoped to the profession.

        Args:
            profession_id: Scope the check to this profession.
            title: Roadmap title to check.
            exclude_id: UUID to exclude from the check (for update).

        Raises:
            CareerRoadmapError: With code ``TITLE_TAKEN``.
        """
        if self._repo.title_exists_for_profession(
            profession_id, title, exclude_id=exclude_id
        ):
            raise CareerRoadmapError(
                f"A roadmap titled '{title}' already exists for this profession.",
                code=CareerRoadmapError.TITLE_TAKEN,
            )

    # ── Public service methods ────────────────────────────────────────────── #

    def create_roadmap(
        self, payload: CareerRoadmapCreate
    ) -> CareerRoadmapResponse:
        """Create a new career roadmap.

        Workflow:
            1. Assert the referenced profession exists.
            2. Assert the title is not already used for this profession.
            3. Persist the new roadmap via the repository.
            4. Commit the transaction.
            5. Return the serialised ``CareerRoadmapResponse``.

        Args:
            payload: Validated ``CareerRoadmapCreate`` schema.

        Returns:
            ``CareerRoadmapResponse`` for the newly created roadmap.

        Raises:
            CareerRoadmapError: ``PROFESSION_NOT_FOUND`` if FK is invalid.
            CareerRoadmapError: ``TITLE_TAKEN`` if title conflicts.
        """
        logger.info(
            "create_roadmap | profession_id=%s | title=%s | difficulty=%s",
            payload.profession_id, payload.title, payload.difficulty,
        )
        self._assert_profession_exists(payload.profession_id)
        self._assert_title_available(payload.profession_id, payload.title)

        roadmap = self._repo.create_roadmap(
            profession_id=payload.profession_id,
            title=payload.title,
            description=payload.description,
            estimated_months=payload.estimated_months,
            difficulty=payload.difficulty.value,
            is_active=payload.is_active,
        )
        self._db.commit()
        logger.info("CareerRoadmap created | id=%s", roadmap.id)
        return CareerRoadmapResponse.model_validate(roadmap)

    def get_roadmap(self, roadmap_id: uuid.UUID) -> CareerRoadmapResponse:
        """Fetch a single roadmap by UUID.

        Args:
            roadmap_id: UUID of the roadmap to retrieve.

        Returns:
            Full ``CareerRoadmapResponse`` (includes steps).

        Raises:
            CareerRoadmapError: With code ``NOT_FOUND`` if missing.
        """
        logger.debug("get_roadmap | id=%s", roadmap_id)
        roadmap = self._get_or_404(roadmap_id)
        return CareerRoadmapResponse.model_validate(roadmap)

    def list_roadmaps(
        self,
        *,
        profession_id: Optional[uuid.UUID] = None,
        difficulty: Optional[str] = None,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> dict:
        """Return a paginated list of roadmaps with total count.

        Args:
            profession_id: Filter to roadmaps for this profession.
            difficulty: Filter by difficulty level.
            is_active: Filter by active/inactive status.
            skip: Pagination offset.
            limit: Max items per page.

        Returns:
            ``{"items": list[CareerRoadmapListResponse], "total": int,
               "skip": int, "limit": int}``
        """
        logger.debug(
            "list_roadmaps | profession_id=%s | difficulty=%s | is_active=%s"
            " | skip=%d | limit=%d",
            profession_id, difficulty, is_active, skip, limit,
        )
        roadmaps = self._repo.list_roadmaps(
            profession_id=profession_id,
            difficulty=difficulty,
            is_active=is_active,
            skip=skip,
            limit=limit,
        )
        total = self._repo.count_roadmaps(
            profession_id=profession_id,
            difficulty=difficulty,
            is_active=is_active,
        )
        return {
            "items": [
                CareerRoadmapListResponse.model_validate(r) for r in roadmaps
            ],
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    def update_roadmap(
        self,
        roadmap_id: uuid.UUID,
        payload: CareerRoadmapUpdate,
    ) -> CareerRoadmapResponse:
        """Apply a partial update to a career roadmap (PATCH semantics).

        Workflow:
            1. Load the roadmap (404 if not found).
            2. If a new title is provided, assert it is not taken within the
               same profession.
            3. Apply changes via the repository.
            4. Commit the transaction.
            5. Return the updated ``CareerRoadmapResponse``.

        Args:
            roadmap_id: UUID of the roadmap to update.
            payload: Validated ``CareerRoadmapUpdate`` schema.

        Returns:
            Updated ``CareerRoadmapResponse``.

        Raises:
            CareerRoadmapError: ``NOT_FOUND`` if the roadmap does not exist.
            CareerRoadmapError: ``TITLE_TAKEN`` if the new title conflicts.
        """
        logger.info("update_roadmap | id=%s", roadmap_id)
        roadmap = self._get_or_404(roadmap_id)

        if payload.title is not None:
            self._assert_title_available(
                roadmap.profession_id, payload.title, exclude_id=roadmap_id
            )

        updated = self._repo.update_roadmap(
            roadmap,
            title=payload.title,
            description=payload.description,
            estimated_months=payload.estimated_months,
            difficulty=payload.difficulty.value if payload.difficulty else None,
            is_active=payload.is_active,
        )
        self._db.commit()
        logger.info("CareerRoadmap updated | id=%s", updated.id)
        return CareerRoadmapResponse.model_validate(updated)

    def delete_roadmap(self, roadmap_id: uuid.UUID) -> dict:
        """Hard-delete a career roadmap by UUID.

        All associated ``RoadmapStep`` rows are cascade-deleted.

        Args:
            roadmap_id: UUID of the roadmap to delete.

        Returns:
            Confirmation envelope::

                {
                    "deleted": true,
                    "id": "<uuid>",
                    "title": "<roadmap title>"
                }

        Raises:
            CareerRoadmapError: ``NOT_FOUND`` if the roadmap does not exist.
        """
        logger.info("delete_roadmap | id=%s", roadmap_id)
        roadmap = self._get_or_404(roadmap_id)
        roadmap_id_str = str(roadmap.id)
        roadmap_title = roadmap.title

        self._repo.delete_roadmap(roadmap)
        self._db.commit()
        logger.info(
            "CareerRoadmap hard-deleted | id=%s | title=%s",
            roadmap_id_str, roadmap_title,
        )
        return {
            "deleted": True,
            "id": roadmap_id_str,
            "title": roadmap_title,
        }


# ─────────────────────────────────────────────────────────────────────────────
# RoadmapStepService
# ─────────────────────────────────────────────────────────────────────────────


class RoadmapStepService:
    """Orchestrates all RoadmapStep CRUD and business-logic workflows.

    Args:
        session: An active SQLAlchemy ``Session``.
    """

    def __init__(self, session: Session) -> None:
        self._db = session
        self._repo = RoadmapStepRepository(session)
        self._roadmap_repo = CareerRoadmapRepository(session)
        self._skill_repo = SkillRepository(session)

    # ── Internal helpers ─────────────────────────────────────────────────── #

    def _get_or_404(self, step_id: uuid.UUID) -> RoadmapStep:
        """Load a step or raise ``CareerRoadmapError(NOT_FOUND)``.

        Args:
            step_id: UUID of the step to load.

        Returns:
            The ``RoadmapStep`` ORM instance.

        Raises:
            CareerRoadmapError: With code ``NOT_FOUND`` if no row matches.
        """
        step = self._repo.get_by_id(step_id)
        if step is None:
            raise CareerRoadmapError(
                f"Roadmap step with id '{step_id}' was not found.",
                code=CareerRoadmapError.NOT_FOUND,
            )
        return step

    def _assert_roadmap_exists(self, roadmap_id: uuid.UUID) -> None:
        """Raise ``CareerRoadmapError(ROADMAP_NOT_FOUND)`` if missing.

        Args:
            roadmap_id: UUID of the roadmap to validate.

        Raises:
            CareerRoadmapError: With code ``ROADMAP_NOT_FOUND``.
        """
        if self._roadmap_repo.get_by_id(roadmap_id) is None:
            raise CareerRoadmapError(
                f"Career roadmap with id '{roadmap_id}' was not found.",
                code=CareerRoadmapError.ROADMAP_NOT_FOUND,
            )

    def _assert_skill_exists(self, skill_id: uuid.UUID) -> None:
        """Raise ``CareerRoadmapError(SKILL_NOT_FOUND)`` if missing.

        Args:
            skill_id: UUID of the skill to validate.

        Raises:
            CareerRoadmapError: With code ``SKILL_NOT_FOUND``.
        """
        if self._skill_repo.get_by_id(skill_id) is None:
            raise CareerRoadmapError(
                f"Skill with id '{skill_id}' was not found.",
                code=CareerRoadmapError.SKILL_NOT_FOUND,
            )

    def _assert_order_available(
        self,
        roadmap_id: uuid.UUID,
        step_order: int,
        *,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Raise ``CareerRoadmapError(ORDER_TAKEN)`` if step_order is in use.

        Args:
            roadmap_id: Scope to this roadmap.
            step_order: The order value to validate.
            exclude_id: UUID to exclude from the check (for updates).

        Raises:
            CareerRoadmapError: With code ``ORDER_TAKEN``.
        """
        if self._repo.order_exists_in_roadmap(
            roadmap_id, step_order, exclude_id=exclude_id
        ):
            raise CareerRoadmapError(
                f"Step order {step_order} is already taken in this roadmap.",
                code=CareerRoadmapError.ORDER_TAKEN,
            )

    def _assert_skill_not_duplicate(
        self,
        roadmap_id: uuid.UUID,
        skill_id: uuid.UUID,
        *,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Raise ``CareerRoadmapError(SKILL_DUPLICATE)`` if skill is already a step.

        Args:
            roadmap_id: Scope to this roadmap.
            skill_id: UUID of the skill to check.
            exclude_id: UUID to exclude from the check (for updates).

        Raises:
            CareerRoadmapError: With code ``SKILL_DUPLICATE``.
        """
        if self._repo.skill_exists_in_roadmap(
            roadmap_id, skill_id, exclude_id=exclude_id
        ):
            raise CareerRoadmapError(
                f"Skill '{skill_id}' is already a step in this roadmap.",
                code=CareerRoadmapError.SKILL_DUPLICATE,
            )

    # ── Public service methods ────────────────────────────────────────────── #

    def create_step(
        self, payload: RoadmapStepCreate
    ) -> RoadmapStepResponse:
        """Create a new roadmap step.

        Workflow:
            1. Assert the referenced roadmap exists.
            2. Assert the referenced skill exists.
            3. Assert step_order is not already taken within the roadmap.
            4. Assert the skill does not already appear in the roadmap.
            5. Persist the new step via the repository.
            6. Commit and return the serialised ``RoadmapStepResponse``.

        Args:
            payload: Validated ``RoadmapStepCreate`` schema.

        Returns:
            ``RoadmapStepResponse`` for the newly created step.

        Raises:
            CareerRoadmapError: ``ROADMAP_NOT_FOUND`` if roadmap FK invalid.
            CareerRoadmapError: ``SKILL_NOT_FOUND`` if skill FK invalid.
            CareerRoadmapError: ``ORDER_TAKEN`` if step_order conflicts.
            CareerRoadmapError: ``SKILL_DUPLICATE`` if skill already in roadmap.
        """
        logger.info(
            "create_step | roadmap_id=%s | skill_id=%s | step_order=%d",
            payload.roadmap_id, payload.skill_id, payload.step_order,
        )
        self._assert_roadmap_exists(payload.roadmap_id)
        self._assert_skill_exists(payload.skill_id)
        self._assert_order_available(payload.roadmap_id, payload.step_order)
        self._assert_skill_not_duplicate(payload.roadmap_id, payload.skill_id)

        step = self._repo.create_step(
            roadmap_id=payload.roadmap_id,
            skill_id=payload.skill_id,
            step_order=payload.step_order,
            required=payload.required,
            estimated_hours=payload.estimated_hours,
        )
        self._db.commit()
        logger.info("RoadmapStep created | id=%s", step.id)
        return RoadmapStepResponse.model_validate(step)

    def get_step(self, step_id: uuid.UUID) -> RoadmapStepResponse:
        """Fetch a single roadmap step by UUID.

        Args:
            step_id: UUID of the step to retrieve.

        Returns:
            Full ``RoadmapStepResponse``.

        Raises:
            CareerRoadmapError: With code ``NOT_FOUND`` if missing.
        """
        logger.debug("get_step | id=%s", step_id)
        step = self._get_or_404(step_id)
        return RoadmapStepResponse.model_validate(step)

    def list_steps(
        self,
        *,
        roadmap_id: Optional[uuid.UUID] = None,
        skill_id: Optional[uuid.UUID] = None,
        required: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> dict:
        """Return a paginated list of roadmap steps with total count.

        Args:
            roadmap_id: Filter to steps in this roadmap.
            skill_id: Filter to steps referencing this skill.
            required: Filter by required/optional flag.
            skip: Pagination offset.
            limit: Max items per page.

        Returns:
            ``{"items": list[RoadmapStepResponse], "total": int,
               "skip": int, "limit": int}``
        """
        logger.debug(
            "list_steps | roadmap_id=%s | skill_id=%s | required=%s"
            " | skip=%d | limit=%d",
            roadmap_id, skill_id, required, skip, limit,
        )
        steps = self._repo.list_steps(
            roadmap_id=roadmap_id,
            skill_id=skill_id,
            required=required,
            skip=skip,
            limit=limit,
        )
        total = self._repo.count_steps(
            roadmap_id=roadmap_id,
            skill_id=skill_id,
            required=required,
        )
        return {
            "items": [RoadmapStepResponse.model_validate(s) for s in steps],
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    def update_step(
        self,
        step_id: uuid.UUID,
        payload: RoadmapStepUpdate,
    ) -> RoadmapStepResponse:
        """Apply a partial update to a roadmap step (PATCH semantics).

        Validates step_order uniqueness within the roadmap if a new order
        is supplied.

        Args:
            step_id: UUID of the step to update.
            payload: Validated ``RoadmapStepUpdate`` schema.

        Returns:
            Updated ``RoadmapStepResponse``.

        Raises:
            CareerRoadmapError: ``NOT_FOUND`` if the step does not exist.
            CareerRoadmapError: ``ORDER_TAKEN`` if the new order conflicts.
        """
        logger.info("update_step | id=%s", step_id)
        step = self._get_or_404(step_id)

        if payload.step_order is not None:
            self._assert_order_available(
                step.roadmap_id, payload.step_order, exclude_id=step_id
            )

        updated = self._repo.update_step(
            step,
            step_order=payload.step_order,
            required=payload.required,
            estimated_hours=payload.estimated_hours,
        )
        self._db.commit()
        logger.info("RoadmapStep updated | id=%s", updated.id)
        return RoadmapStepResponse.model_validate(updated)

    def delete_step(self, step_id: uuid.UUID) -> dict:
        """Hard-delete a roadmap step by UUID.

        Args:
            step_id: UUID of the step to delete.

        Returns:
            Confirmation envelope::

                {
                    "deleted": true,
                    "id": "<uuid>",
                    "roadmap_id": "<uuid>",
                    "step_order": 1
                }

        Raises:
            CareerRoadmapError: ``NOT_FOUND`` if the step does not exist.
        """
        logger.info("delete_step | id=%s", step_id)
        step = self._get_or_404(step_id)
        step_id_str = str(step.id)
        roadmap_id_str = str(step.roadmap_id)
        step_order = step.step_order

        self._repo.delete_step(step)
        self._db.commit()
        logger.info(
            "RoadmapStep hard-deleted | id=%s | roadmap_id=%s | step_order=%d",
            step_id_str, roadmap_id_str, step_order,
        )
        return {
            "deleted": True,
            "id": step_id_str,
            "roadmap_id": roadmap_id_str,
            "step_order": step_order,
        }
