"""
backend/app/repositories/course.py
=====================================
Repository pattern implementation for the ``courses`` table.

Architecture contract
---------------------
- **Single responsibility**: SQL only.  No business logic, no schema
  validation, no password or JWT handling.
- **Session ownership**: the caller (service or ``get_db`` dependency) owns
  commit / rollback / close.  This repository calls ``flush()`` after
  mutating operations to surface ``IntegrityError`` early and resolve
  server-side defaults before returning.
- **Returns ORM objects only**: ``Course`` instances or ``list[Course]``
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

from app.models.course import Course

logger: logging.Logger = logging.getLogger(__name__)


class CourseRepository:
    """Data-access layer for the ``courses`` table.

    All public methods issue exactly one logical SQL statement (SELECT, INSERT,
    UPDATE).  PATCH semantics (only non-``None`` fields updated) are handled
    in ``update_course`` so that the service layer passes values directly.

    Args:
        session: An active SQLAlchemy ``Session``.  The caller is responsible
            for committing or rolling back after each service-level operation.

    Example::

        repo = CourseRepository(db)
        course = repo.get_by_id(some_uuid)
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # =========================================================================
    #  Read operations
    # =========================================================================

    def get_by_id(self, course_id: uuid.UUID) -> Optional[Course]:
        """Fetch a course by UUID primary key using the identity map.

        Args:
            course_id: The UUID PK of the course to retrieve.

        Returns:
            The matching ``Course`` ORM instance, or ``None`` if not found.
        """
        logger.debug("get_by_id | course_id=%s", course_id)
        return self._session.get(Course, course_id)

    def url_exists_for_skill(
        self,
        course_url: str,
        skill_id: uuid.UUID,
        *,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> bool:
        """Check whether a course URL already exists within the given skill.

        Duplicate URLs are allowed across different skills but disallowed
        within the same skill to prevent redundant resource linking.

        Args:
            course_url: The course URL to test (case-sensitive).
            skill_id: Scope the uniqueness check to this skill.
            exclude_id: UUID of the course row to exclude from the check.
                Pass this when validating a URL change on an existing row.

        Returns:
            ``True`` if the URL is already registered for the skill,
            else ``False``.
        """
        logger.debug(
            "url_exists_for_skill | course_url=%s | skill_id=%s | exclude_id=%s",
            course_url, skill_id, exclude_id,
        )
        stmt = (
            select(func.count())
            .select_from(Course)
            .where(Course.course_url == course_url)
            .where(Course.skill_id == skill_id)
        )
        if exclude_id is not None:
            stmt = stmt.where(Course.id != exclude_id)
        count: int = self._session.execute(stmt).scalar_one()
        return count > 0

    def list_courses(
        self,
        *,
        skill_id: Optional[uuid.UUID] = None,
        difficulty: Optional[str] = None,
        provider: Optional[str] = None,
        is_free: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Course]:
        """Return a paginated list of courses with optional filters.

        Results are ordered by ``title`` ascending for a stable, deterministic
        page order that does not change as new rows are inserted.

        Args:
            skill_id: Filter to courses belonging to this skill UUID.
                ``None`` = return courses across all skills.
            difficulty: Filter by difficulty level (e.g. ``'Beginner'``).
                ``None`` = return all difficulty levels.
            provider: Filter by provider name (case-sensitive equality).
                ``None`` = return all providers.
            is_free: Filter by free/paid status. ``None`` = return all.
            skip: Row offset for pagination.  Must be >= 0.
            limit: Max rows to return.  Defaults to 50; capped by the caller.

        Returns:
            A (possibly empty) list of ``Course`` ORM instances.
        """
        logger.debug(
            "list_courses | skill_id=%s | difficulty=%s | provider=%s"
            " | is_free=%s | skip=%d | limit=%d",
            skill_id, difficulty, provider, is_free, skip, limit,
        )
        stmt = select(Course).order_by(Course.title.asc())

        if skill_id is not None:
            stmt = stmt.where(Course.skill_id == skill_id)
        if difficulty is not None:
            stmt = stmt.where(Course.difficulty == difficulty)
        if provider is not None:
            stmt = stmt.where(Course.provider == provider)
        if is_free is not None:
            stmt = stmt.where(Course.is_free == is_free)

        stmt = stmt.offset(skip).limit(limit)
        return list(self._session.execute(stmt).scalars().all())

    def count_courses(
        self,
        *,
        skill_id: Optional[uuid.UUID] = None,
        difficulty: Optional[str] = None,
        provider: Optional[str] = None,
        is_free: Optional[bool] = None,
    ) -> int:
        """Return the total count matching the given filters.

        Used alongside ``list_courses`` to build pagination metadata.

        Args:
            skill_id: Same filter semantics as ``list_courses``.
            difficulty: Same filter semantics as ``list_courses``.
            provider: Same filter semantics as ``list_courses``.
            is_free: Same filter semantics as ``list_courses``.

        Returns:
            Integer count of matching rows.
        """
        stmt = select(func.count()).select_from(Course)
        if skill_id is not None:
            stmt = stmt.where(Course.skill_id == skill_id)
        if difficulty is not None:
            stmt = stmt.where(Course.difficulty == difficulty)
        if provider is not None:
            stmt = stmt.where(Course.provider == provider)
        if is_free is not None:
            stmt = stmt.where(Course.is_free == is_free)
        return self._session.execute(stmt).scalar_one()

    # =========================================================================
    #  Write operations
    # =========================================================================

    def create_course(
        self,
        *,
        title: str,
        skill_id: uuid.UUID,
        difficulty: str,
        course_url: str,
        description: Optional[str] = None,
        provider: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
        duration_hours: Optional[float] = None,
        is_free: bool = False,
        rating: Optional[float] = None,
    ) -> Course:
        """Persist a new course row and return the ORM instance.

        Calls ``flush()`` so that server-side defaults (``created_at``,
        ``updated_at``) are written back to the object before returning.
        The caller must commit the session.

        Args:
            title: Human-readable course title.
            skill_id: UUID of the owning Skill (FK).
            difficulty: Difficulty level string — one of
                ``'Beginner'``, ``'Intermediate'``, ``'Advanced'``.
            course_url: Canonical URL to the course page.
            description: Optional Markdown description.
            provider: Optional publishing platform name.
            thumbnail_url: Optional cover image URL.
            duration_hours: Optional estimated hours to complete.
            is_free: Whether the course is free.
            rating: Optional average rating 0.00–5.00.

        Returns:
            The freshly created ``Course`` ORM instance with all
            DB-populated fields resolved.

        Raises:
            sqlalchemy.exc.IntegrityError: If the ``skill_id`` FK
                references a non-existent skill row.
            sqlalchemy.exc.SQLAlchemyError: For any other DB-level error.
            Both exceptions are raised after session rollback.
        """
        logger.debug(
            "create_course | title=%s | skill_id=%s | difficulty=%s",
            title, skill_id, difficulty,
        )
        course = Course(
            title=title,
            description=description,
            provider=provider,
            course_url=course_url,
            thumbnail_url=thumbnail_url,
            difficulty=difficulty,
            duration_hours=duration_hours,
            is_free=is_free,
            rating=rating,
            skill_id=skill_id,
        )
        try:
            self._session.add(course)
            self._session.flush()
            logger.info(
                "Course created | id=%s | title=%s | skill_id=%s",
                course.id, course.title, course.skill_id,
            )
            return course
        except IntegrityError:
            logger.warning(
                "create_course failed — constraint violation | title=%s"
                " | skill_id=%s",
                title, skill_id,
            )
            self._session.rollback()
            raise
        except SQLAlchemyError:
            logger.exception("create_course failed | title=%s", title)
            self._session.rollback()
            raise

    def update_course(
        self,
        course: Course,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        provider: Optional[str] = None,
        course_url: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
        difficulty: Optional[str] = None,
        duration_hours: Optional[float] = None,
        is_free: Optional[bool] = None,
        rating: Optional[float] = None,
    ) -> Course:
        """Apply a partial update to an existing course row (PATCH semantics).

        Only keyword arguments that are **not** ``None`` are written.  The
        method flushes after mutation so that ``updated_at`` is refreshed and
        the object reflects the current DB state.

        Args:
            course: The ``Course`` ORM instance to update (must be attached
                to this session).
            title: New display title, or ``None`` to leave unchanged.
            description: New description, or ``None`` to leave unchanged.
            provider: New provider name, or ``None`` to leave unchanged.
            course_url: New canonical URL, or ``None`` to leave unchanged.
            thumbnail_url: New thumbnail URL, or ``None`` to leave unchanged.
            difficulty: New difficulty level, or ``None`` to leave unchanged.
            duration_hours: New duration, or ``None`` to leave unchanged.
            is_free: New free/paid flag, or ``None`` to leave unchanged.
            rating: New rating value, or ``None`` to leave unchanged.

        Returns:
            The updated ``Course`` ORM instance.

        Raises:
            sqlalchemy.exc.SQLAlchemyError: For any DB-level error (after
                session rollback).
        """
        logger.debug("update_course | id=%s", course.id)

        if title is not None:
            course.title = title
        if description is not None:
            course.description = description
        if provider is not None:
            course.provider = provider
        if course_url is not None:
            course.course_url = course_url
        if thumbnail_url is not None:
            course.thumbnail_url = thumbnail_url
        if difficulty is not None:
            course.difficulty = difficulty
        if duration_hours is not None:
            course.duration_hours = duration_hours
        if is_free is not None:
            course.is_free = is_free
        if rating is not None:
            course.rating = rating

        try:
            self._session.flush()
            logger.info("Course updated | id=%s", course.id)
            return course
        except IntegrityError:
            logger.warning(
                "update_course failed — constraint violation | id=%s", course.id
            )
            self._session.rollback()
            raise
        except SQLAlchemyError:
            logger.exception("update_course failed | id=%s", course.id)
            self._session.rollback()
            raise

    def delete_course(self, course: Course) -> None:
        """Hard-delete a course row from the database.

        Courses do not have a soft-delete ``is_active`` flag — they are
        resource catalogue entries that can be cleanly removed when no
        longer relevant to a skill.

        Args:
            course: The ``Course`` ORM instance to delete (must be attached
                to this session).

        Raises:
            sqlalchemy.exc.SQLAlchemyError: On any DB-level failure (after
                session rollback).
        """
        logger.debug("delete_course | id=%s | title=%s", course.id, course.title)
        try:
            self._session.delete(course)
            self._session.flush()
            logger.info("Course deleted | id=%s | title=%s", course.id, course.title)
        except SQLAlchemyError:
            logger.exception("delete_course failed | id=%s", course.id)
            self._session.rollback()
            raise
