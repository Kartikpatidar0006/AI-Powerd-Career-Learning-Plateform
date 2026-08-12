"""
backend/app/repositories/career_roadmap.py
============================================
Repository pattern implementations for ``career_roadmaps`` and
``roadmap_steps`` tables.

Architecture contract
---------------------
- **Single responsibility**: SQL only.  No business logic, no schema
  validation, no password or JWT handling.
- **Session ownership**: the caller (service or ``get_db`` dependency) owns
  commit / rollback / close.  This repository calls ``flush()`` after
  mutating operations to surface ``IntegrityError`` early and resolve
  server-side defaults before returning.
- **Returns ORM objects only**: ORM instances or ``list`` or primitives
  (``bool``, ``int``).
- **Rollback on failure**: every mutating method wraps its work in
  ``try/except SQLAlchemyError`` → rollback → re-raise.

Two repository classes are defined here:
  ``CareerRoadmapRepository`` — CRUD for ``career_roadmaps``.
  ``RoadmapStepRepository``   — CRUD for ``roadmap_steps``.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.career_roadmap import CareerRoadmap, RoadmapStep

logger: logging.Logger = logging.getLogger(__name__)


# =========================================================================== #
#  CareerRoadmapRepository                                                      #
# =========================================================================== #


class CareerRoadmapRepository:
    """Data-access layer for the ``career_roadmaps`` table.

    All public methods issue exactly one logical SQL statement per call.
    PATCH semantics (only non-``None`` fields updated) are handled in
    ``update_roadmap`` so that the service layer passes values directly.

    Args:
        session: An active SQLAlchemy ``Session``.  The caller is responsible
            for committing or rolling back after each service-level operation.

    Example::

        repo = CareerRoadmapRepository(db)
        roadmap = repo.get_by_id(some_uuid)
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # =========================================================================
    #  Read operations
    # =========================================================================

    def get_by_id(self, roadmap_id: uuid.UUID) -> Optional[CareerRoadmap]:
        """Fetch a roadmap by UUID primary key using the identity map.

        Args:
            roadmap_id: The UUID PK of the roadmap to retrieve.

        Returns:
            The matching ``CareerRoadmap`` ORM instance, or ``None``.
        """
        logger.debug("get_by_id | roadmap_id=%s", roadmap_id)
        return self._session.get(CareerRoadmap, roadmap_id)

    def title_exists_for_profession(
        self,
        profession_id: uuid.UUID,
        title: str,
        *,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> bool:
        """Check whether a roadmap title is already used within a profession.

        Uniqueness is scoped to the profession — two different professions can
        share the same roadmap title.

        Args:
            profession_id: Scope the check to this profession UUID.
            title: The title to test (case-sensitive).
            exclude_id: UUID of the roadmap to exclude (for update checks).

        Returns:
            ``True`` if the title is already in use for this profession.
        """
        logger.debug(
            "title_exists_for_profession | profession_id=%s | title=%s"
            " | exclude_id=%s",
            profession_id, title, exclude_id,
        )
        stmt = (
            select(func.count())
            .select_from(CareerRoadmap)
            .where(CareerRoadmap.profession_id == profession_id)
            .where(CareerRoadmap.title == title)
        )
        if exclude_id is not None:
            stmt = stmt.where(CareerRoadmap.id != exclude_id)
        return self._session.execute(stmt).scalar_one() > 0

    def list_roadmaps(
        self,
        *,
        profession_id: Optional[uuid.UUID] = None,
        difficulty: Optional[str] = None,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[CareerRoadmap]:
        """Return a paginated list of roadmaps with optional filters.

        Results are ordered by ``title`` ascending for deterministic paging.

        Args:
            profession_id: Filter to roadmaps belonging to this profession.
                ``None`` = return across all professions.
            difficulty: Filter by difficulty level string.
                ``None`` = return all difficulty levels.
            is_active: Filter by active/inactive status.
                ``None`` = return both active and inactive.
            skip: Row offset for pagination.  Must be >= 0.
            limit: Max rows to return.  Defaults to 50.

        Returns:
            A (possibly empty) list of ``CareerRoadmap`` ORM instances.
        """
        logger.debug(
            "list_roadmaps | profession_id=%s | difficulty=%s | is_active=%s"
            " | skip=%d | limit=%d",
            profession_id, difficulty, is_active, skip, limit,
        )
        stmt = select(CareerRoadmap).order_by(CareerRoadmap.title.asc())

        if profession_id is not None:
            stmt = stmt.where(CareerRoadmap.profession_id == profession_id)
        if difficulty is not None:
            stmt = stmt.where(CareerRoadmap.difficulty == difficulty)
        if is_active is not None:
            stmt = stmt.where(CareerRoadmap.is_active == is_active)

        stmt = stmt.offset(skip).limit(limit)
        return list(self._session.execute(stmt).scalars().all())

    def count_roadmaps(
        self,
        *,
        profession_id: Optional[uuid.UUID] = None,
        difficulty: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> int:
        """Return the total count matching the given filters.

        Used alongside ``list_roadmaps`` to build pagination metadata.

        Args:
            profession_id: Same filter semantics as ``list_roadmaps``.
            difficulty: Same filter semantics as ``list_roadmaps``.
            is_active: Same filter semantics as ``list_roadmaps``.

        Returns:
            Integer count of matching rows.
        """
        stmt = select(func.count()).select_from(CareerRoadmap)
        if profession_id is not None:
            stmt = stmt.where(CareerRoadmap.profession_id == profession_id)
        if difficulty is not None:
            stmt = stmt.where(CareerRoadmap.difficulty == difficulty)
        if is_active is not None:
            stmt = stmt.where(CareerRoadmap.is_active == is_active)
        return self._session.execute(stmt).scalar_one()

    # =========================================================================
    #  Write operations
    # =========================================================================

    def create_roadmap(
        self,
        *,
        profession_id: uuid.UUID,
        title: str,
        difficulty: str,
        description: Optional[str] = None,
        estimated_months: int = 1,
        is_active: bool = True,
    ) -> CareerRoadmap:
        """Persist a new roadmap row and return the ORM instance.

        Calls ``flush()`` so that server-side defaults are resolved before
        returning.  The caller must commit the session.

        Args:
            profession_id: UUID of the owning Profession (FK).
            title: Roadmap display title.
            difficulty: Difficulty level string.
            description: Optional Markdown description.
            estimated_months: Estimated months to completion (>= 1).
            is_active: Initial visibility flag.

        Returns:
            The freshly created ``CareerRoadmap`` ORM instance.

        Raises:
            sqlalchemy.exc.IntegrityError: On FK or uniqueness violation.
            sqlalchemy.exc.SQLAlchemyError: For any other DB-level error.
            Both raised after session rollback.
        """
        logger.debug(
            "create_roadmap | profession_id=%s | title=%s | difficulty=%s",
            profession_id, title, difficulty,
        )
        roadmap = CareerRoadmap(
            profession_id=profession_id,
            title=title,
            description=description,
            estimated_months=estimated_months,
            difficulty=difficulty,
            is_active=is_active,
        )
        try:
            self._session.add(roadmap)
            self._session.flush()
            logger.info(
                "CareerRoadmap created | id=%s | title=%s | profession_id=%s",
                roadmap.id, roadmap.title, roadmap.profession_id,
            )
            return roadmap
        except IntegrityError:
            logger.warning(
                "create_roadmap failed — constraint violation | title=%s"
                " | profession_id=%s",
                title, profession_id,
            )
            self._session.rollback()
            raise
        except SQLAlchemyError:
            logger.exception("create_roadmap failed | title=%s", title)
            self._session.rollback()
            raise

    def update_roadmap(
        self,
        roadmap: CareerRoadmap,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        estimated_months: Optional[int] = None,
        difficulty: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> CareerRoadmap:
        """Apply a partial update to an existing roadmap row (PATCH semantics).

        Only keyword arguments that are **not** ``None`` are written.

        Args:
            roadmap: The ``CareerRoadmap`` ORM instance to update.
            title: New title, or ``None`` to leave unchanged.
            description: New description, or ``None`` to leave unchanged.
            estimated_months: New duration, or ``None`` to leave unchanged.
            difficulty: New difficulty string, or ``None`` to leave unchanged.
            is_active: New visibility flag, or ``None`` to leave unchanged.

        Returns:
            The updated ``CareerRoadmap`` ORM instance.

        Raises:
            sqlalchemy.exc.SQLAlchemyError: For any DB-level error (after
                session rollback).
        """
        logger.debug("update_roadmap | id=%s", roadmap.id)

        if title is not None:
            roadmap.title = title
        if description is not None:
            roadmap.description = description
        if estimated_months is not None:
            roadmap.estimated_months = estimated_months
        if difficulty is not None:
            roadmap.difficulty = difficulty
        if is_active is not None:
            roadmap.is_active = is_active

        try:
            self._session.flush()
            logger.info("CareerRoadmap updated | id=%s", roadmap.id)
            return roadmap
        except IntegrityError:
            logger.warning(
                "update_roadmap failed — constraint violation | id=%s", roadmap.id
            )
            self._session.rollback()
            raise
        except SQLAlchemyError:
            logger.exception("update_roadmap failed | id=%s", roadmap.id)
            self._session.rollback()
            raise

    def delete_roadmap(self, roadmap: CareerRoadmap) -> None:
        """Hard-delete a roadmap row from the database.

        ``RoadmapStep`` rows are cascade-deleted by the FK constraint.

        Args:
            roadmap: The ``CareerRoadmap`` ORM instance to delete.

        Raises:
            sqlalchemy.exc.SQLAlchemyError: On any DB-level failure (after
                session rollback).
        """
        logger.debug(
            "delete_roadmap | id=%s | title=%s", roadmap.id, roadmap.title
        )
        try:
            self._session.delete(roadmap)
            self._session.flush()
            logger.info(
                "CareerRoadmap deleted | id=%s | title=%s",
                roadmap.id, roadmap.title,
            )
        except SQLAlchemyError:
            logger.exception("delete_roadmap failed | id=%s", roadmap.id)
            self._session.rollback()
            raise


# =========================================================================== #
#  RoadmapStepRepository                                                        #
# =========================================================================== #


class RoadmapStepRepository:
    """Data-access layer for the ``roadmap_steps`` table.

    Args:
        session: An active SQLAlchemy ``Session``.

    Example::

        repo = RoadmapStepRepository(db)
        step = repo.get_by_id(some_uuid)
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # =========================================================================
    #  Read operations
    # =========================================================================

    def get_by_id(self, step_id: uuid.UUID) -> Optional[RoadmapStep]:
        """Fetch a roadmap step by UUID primary key.

        Args:
            step_id: The UUID PK of the step to retrieve.

        Returns:
            The matching ``RoadmapStep`` ORM instance, or ``None``.
        """
        logger.debug("get_by_id | step_id=%s", step_id)
        return self._session.get(RoadmapStep, step_id)

    def order_exists_in_roadmap(
        self,
        roadmap_id: uuid.UUID,
        step_order: int,
        *,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> bool:
        """Check whether a step_order is already used within a roadmap.

        Args:
            roadmap_id: Scope the uniqueness check to this roadmap.
            step_order: The order value to test.
            exclude_id: UUID of the step to exclude (for update validations).

        Returns:
            ``True`` if the step_order is taken, else ``False``.
        """
        logger.debug(
            "order_exists_in_roadmap | roadmap_id=%s | step_order=%d"
            " | exclude_id=%s",
            roadmap_id, step_order, exclude_id,
        )
        stmt = (
            select(func.count())
            .select_from(RoadmapStep)
            .where(RoadmapStep.roadmap_id == roadmap_id)
            .where(RoadmapStep.step_order == step_order)
        )
        if exclude_id is not None:
            stmt = stmt.where(RoadmapStep.id != exclude_id)
        return self._session.execute(stmt).scalar_one() > 0

    def skill_exists_in_roadmap(
        self,
        roadmap_id: uuid.UUID,
        skill_id: uuid.UUID,
        *,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> bool:
        """Check whether a skill is already used as a step within a roadmap.

        Args:
            roadmap_id: Scope the check to this roadmap.
            skill_id: UUID of the skill to test.
            exclude_id: UUID of the step to exclude (for update validations).

        Returns:
            ``True`` if the skill is already in the roadmap, else ``False``.
        """
        logger.debug(
            "skill_exists_in_roadmap | roadmap_id=%s | skill_id=%s"
            " | exclude_id=%s",
            roadmap_id, skill_id, exclude_id,
        )
        stmt = (
            select(func.count())
            .select_from(RoadmapStep)
            .where(RoadmapStep.roadmap_id == roadmap_id)
            .where(RoadmapStep.skill_id == skill_id)
        )
        if exclude_id is not None:
            stmt = stmt.where(RoadmapStep.id != exclude_id)
        return self._session.execute(stmt).scalar_one() > 0

    def list_steps(
        self,
        *,
        roadmap_id: Optional[uuid.UUID] = None,
        skill_id: Optional[uuid.UUID] = None,
        required: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[RoadmapStep]:
        """Return a paginated list of roadmap steps with optional filters.

        Results are ordered by ``step_order`` ascending — the natural
        traversal order of a roadmap.

        Args:
            roadmap_id: Filter to steps in this roadmap.
                ``None`` = return across all roadmaps.
            skill_id: Filter to steps referencing this skill.
                ``None`` = return all skills.
            required: Filter by required flag.
                ``None`` = return both required and optional.
            skip: Row offset for pagination.
            limit: Max rows to return.  Defaults to 100 (steps are usually few).

        Returns:
            A (possibly empty) list of ``RoadmapStep`` ORM instances.
        """
        logger.debug(
            "list_steps | roadmap_id=%s | skill_id=%s | required=%s"
            " | skip=%d | limit=%d",
            roadmap_id, skill_id, required, skip, limit,
        )
        stmt = select(RoadmapStep).order_by(RoadmapStep.step_order.asc())

        if roadmap_id is not None:
            stmt = stmt.where(RoadmapStep.roadmap_id == roadmap_id)
        if skill_id is not None:
            stmt = stmt.where(RoadmapStep.skill_id == skill_id)
        if required is not None:
            stmt = stmt.where(RoadmapStep.required == required)

        stmt = stmt.offset(skip).limit(limit)
        return list(self._session.execute(stmt).scalars().all())

    def count_steps(
        self,
        *,
        roadmap_id: Optional[uuid.UUID] = None,
        skill_id: Optional[uuid.UUID] = None,
        required: Optional[bool] = None,
    ) -> int:
        """Return the total count of steps matching the given filters.

        Args:
            roadmap_id: Same filter semantics as ``list_steps``.
            skill_id: Same filter semantics as ``list_steps``.
            required: Same filter semantics as ``list_steps``.

        Returns:
            Integer count of matching rows.
        """
        stmt = select(func.count()).select_from(RoadmapStep)
        if roadmap_id is not None:
            stmt = stmt.where(RoadmapStep.roadmap_id == roadmap_id)
        if skill_id is not None:
            stmt = stmt.where(RoadmapStep.skill_id == skill_id)
        if required is not None:
            stmt = stmt.where(RoadmapStep.required == required)
        return self._session.execute(stmt).scalar_one()

    # =========================================================================
    #  Write operations
    # =========================================================================

    def create_step(
        self,
        *,
        roadmap_id: uuid.UUID,
        skill_id: uuid.UUID,
        step_order: int,
        required: bool = True,
        estimated_hours: float = 0.0,
    ) -> RoadmapStep:
        """Persist a new roadmap step row and return the ORM instance.

        Calls ``flush()`` so that server-side defaults are resolved before
        returning.  The caller must commit the session.

        Args:
            roadmap_id: UUID of the owning CareerRoadmap (FK).
            skill_id: UUID of the referenced Skill (FK).
            step_order: 1-based position within the roadmap.
            required: Whether this step is mandatory.
            estimated_hours: Expected hours to complete.

        Returns:
            The freshly created ``RoadmapStep`` ORM instance.

        Raises:
            sqlalchemy.exc.IntegrityError: On FK or uniqueness constraint
                violation.
            sqlalchemy.exc.SQLAlchemyError: For any other DB-level error.
            Both raised after session rollback.
        """
        logger.debug(
            "create_step | roadmap_id=%s | skill_id=%s | step_order=%d",
            roadmap_id, skill_id, step_order,
        )
        step = RoadmapStep(
            roadmap_id=roadmap_id,
            skill_id=skill_id,
            step_order=step_order,
            required=required,
            estimated_hours=estimated_hours,
        )
        try:
            self._session.add(step)
            self._session.flush()
            logger.info(
                "RoadmapStep created | id=%s | roadmap_id=%s | skill_id=%s"
                " | step_order=%d",
                step.id, step.roadmap_id, step.skill_id, step.step_order,
            )
            return step
        except IntegrityError:
            logger.warning(
                "create_step failed — constraint violation | roadmap_id=%s"
                " | skill_id=%s | step_order=%d",
                roadmap_id, skill_id, step_order,
            )
            self._session.rollback()
            raise
        except SQLAlchemyError:
            logger.exception(
                "create_step failed | roadmap_id=%s", roadmap_id
            )
            self._session.rollback()
            raise

    def update_step(
        self,
        step: RoadmapStep,
        *,
        step_order: Optional[int] = None,
        required: Optional[bool] = None,
        estimated_hours: Optional[float] = None,
    ) -> RoadmapStep:
        """Apply a partial update to an existing step row (PATCH semantics).

        Only keyword arguments that are **not** ``None`` are written.

        Args:
            step: The ``RoadmapStep`` ORM instance to update.
            step_order: New step position, or ``None`` to leave unchanged.
            required: New required flag, or ``None`` to leave unchanged.
            estimated_hours: New estimated hours, or ``None`` to leave unchanged.

        Returns:
            The updated ``RoadmapStep`` ORM instance.

        Raises:
            sqlalchemy.exc.IntegrityError: On uniqueness constraint violation
                (e.g. duplicate step_order within roadmap).
            sqlalchemy.exc.SQLAlchemyError: For any other DB-level error.
        """
        logger.debug("update_step | id=%s", step.id)

        if step_order is not None:
            step.step_order = step_order
        if required is not None:
            step.required = required
        if estimated_hours is not None:
            step.estimated_hours = estimated_hours

        try:
            self._session.flush()
            logger.info("RoadmapStep updated | id=%s", step.id)
            return step
        except IntegrityError:
            logger.warning(
                "update_step failed — constraint violation | id=%s", step.id
            )
            self._session.rollback()
            raise
        except SQLAlchemyError:
            logger.exception("update_step failed | id=%s", step.id)
            self._session.rollback()
            raise

    def delete_step(self, step: RoadmapStep) -> None:
        """Hard-delete a roadmap step row.

        Args:
            step: The ``RoadmapStep`` ORM instance to delete.

        Raises:
            sqlalchemy.exc.SQLAlchemyError: On any DB-level failure (after
                session rollback).
        """
        logger.debug(
            "delete_step | id=%s | roadmap_id=%s | step_order=%d",
            step.id, step.roadmap_id, step.step_order,
        )
        try:
            self._session.delete(step)
            self._session.flush()
            logger.info("RoadmapStep deleted | id=%s", step.id)
        except SQLAlchemyError:
            logger.exception("delete_step failed | id=%s", step.id)
            self._session.rollback()
            raise
