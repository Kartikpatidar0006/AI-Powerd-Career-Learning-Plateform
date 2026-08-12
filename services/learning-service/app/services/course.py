"""
backend/app/services/course.py
================================
Business-logic service for the Course domain.

Architecture role
-----------------
``CourseService`` is the **orchestration layer** between the HTTP
transport (router) and the data-access layer (``CourseRepository``).

Layer rules enforced here:
  • No FastAPI imports at module scope — no ``HTTPException``, ``Request``.
  • No raw SQL — every DB access goes through ``CourseRepository`` or
    ``SkillRepository`` (for FK existence validation).
  • Raises ``CourseError`` (defined below) for all business-rule
    violations.  The HTTP router maps those to ``HTTPException``.
  • Commits after every successful write operation; never calls ``close()``.

Transaction ownership
---------------------
The ``Session`` is always injected from outside.  ``CourseService``
commits on success; the ``get_db`` dependency in the router handles rollback
on unhandled exceptions.

Usage example::

    from sqlalchemy.orm import Session
    from app.services.course import CourseService

    svc = CourseService(db)
    course = svc.create_course(payload)
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.course import Course
from app.repositories.course import CourseRepository
from app.schemas.course import (
    CourseCreate,
    CourseListResponse,
    CourseResponse,
    CourseUpdate,
)

logger: logging.Logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Domain exception
# ─────────────────────────────────────────────────────────────────────────────


class CourseError(Exception):
    """Business-rule violation raised by ``CourseService``.

    The HTTP router is the only layer that catches this exception and converts
    it to an ``HTTPException`` with the appropriate status code.

    Attributes:
        message: Safe, user-facing description.
        code: Machine-readable snake_case code for HTTP status mapping.

    Code constants:
        ``NOT_FOUND``       — course UUID does not exist.
        ``SKILL_NOT_FOUND`` — referenced skill UUID does not exist.
        ``URL_TAKEN``       — course URL already registered for this skill.
        ``INVALID_RATING``  — rating value outside the 0.00–5.00 range.
    """

    NOT_FOUND: str = "not_found"
    SKILL_NOT_FOUND: str = "skill_not_found"
    URL_TAKEN: str = "url_taken"
    INVALID_RATING: str = "invalid_rating"

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code

    def __repr__(self) -> str:
        return f"CourseError(code={self.code!r}, message={self.message!r})"


# ─────────────────────────────────────────────────────────────────────────────
# CourseService
# ─────────────────────────────────────────────────────────────────────────────


class CourseService:
    """Orchestrates all course CRUD and business-logic workflows.

    Stateless beyond the injected session.  Instantiate once per request.

    Args:
        session: An active SQLAlchemy ``Session``.  The service commits on
            successful writes; the caller handles session cleanup.
    """

    def __init__(self, session: Session) -> None:
        self._db = session
        self._repo = CourseRepository(session)

    # ── Internal helpers ─────────────────────────────────────────────────── #

    def _get_or_404(self, course_id: uuid.UUID) -> Course:
        course = self._repo.get_by_id(course_id)
        if course is None:
            raise CourseError(
                f"Course with id '{course_id}' was not found.",
                code=CourseError.NOT_FOUND,
            )
        return course

    def _assert_skill_exists(self, skill_id: uuid.UUID) -> None:
        pass

    def _assert_url_available(
        self,
        course_url: str,
        skill_id: uuid.UUID,
        *,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Raise ``CourseError(URL_TAKEN)`` if the URL is already in use for this skill.

        Uniqueness is scoped to the skill — two different skills can share the
        same course URL (e.g. a Python intro course may be relevant to both
        "Python Basics" and "Data Science" skills).

        Args:
            course_url: The URL to check.
            skill_id: Scope the check to this skill.
            exclude_id: UUID to exclude (for updates — allows saving the
                same URL without triggering a false conflict).

        Raises:
            CourseError: With code ``URL_TAKEN`` if taken.
        """
        if self._repo.url_exists_for_skill(
            course_url, skill_id, exclude_id=exclude_id
        ):
            raise CourseError(
                f"A course with URL '{course_url}' already exists for this skill.",
                code=CourseError.URL_TAKEN,
            )

    # ── Public service methods ────────────────────────────────────────────── #

    def create_course(self, payload: CourseCreate) -> CourseResponse:
        """Create a new course and return the full response schema.

        Workflow:
            1. Assert the referenced skill exists.
            2. Assert the course URL is not already registered for this skill.
            3. Persist the new course via the repository.
            4. Commit the transaction.
            5. Return the serialised ``CourseResponse``.

        Args:
            payload: Validated ``CourseCreate`` schema from the request body.

        Returns:
            ``CourseResponse`` representing the newly created course.

        Raises:
            CourseError: With code ``SKILL_NOT_FOUND`` if the FK is invalid.
            CourseError: With code ``URL_TAKEN`` if the URL conflicts within
                the same skill.

        Example::

            response = svc.create_course(CourseCreate(
                title="Python for Everybody",
                difficulty="Beginner",
                course_url="https://coursera.org/learn/python",
                skill_id=some_uuid,
            ))
        """
        logger.info(
            "create_course | title=%s | skill_id=%s | difficulty=%s",
            payload.title, payload.skill_id, payload.difficulty,
        )

        self._assert_skill_exists(payload.skill_id)
        self._assert_url_available(payload.course_url, payload.skill_id)

        course = self._repo.create_course(
            title=payload.title,
            description=payload.description,
            provider=payload.provider,
            course_url=payload.course_url,
            thumbnail_url=payload.thumbnail_url,
            difficulty=payload.difficulty.value,
            duration_hours=payload.duration_hours,
            is_free=payload.is_free,
            rating=payload.rating,
            skill_id=payload.skill_id,
        )
        self._db.commit()
        logger.info("Course created | id=%s", course.id)
        return CourseResponse.model_validate(course)

    def get_course(self, course_id: uuid.UUID) -> CourseResponse:
        """Fetch a single course by UUID.

        Args:
            course_id: UUID of the course to retrieve.

        Returns:
            Full ``CourseResponse`` for the matching course.

        Raises:
            CourseError: With code ``NOT_FOUND`` if no matching row.
        """
        logger.debug("get_course | id=%s", course_id)
        course = self._get_or_404(course_id)
        return CourseResponse.model_validate(course)

    def list_courses(
        self,
        *,
        skill_id: Optional[uuid.UUID] = None,
        difficulty: Optional[str] = None,
        provider: Optional[str] = None,
        is_free: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> dict:
        """Return a paginated list of courses with total count.

        Returns a dict with ``items`` (slim list schema) and ``total``
        (count matching filters) so the router can construct a consistent
        pagination envelope.

        Args:
            skill_id: Filter to courses belonging to this skill UUID.
            difficulty: Filter by difficulty level.
            provider: Filter by provider name (case-sensitive).
            is_free: Filter by free/paid status.
            skip: Offset for pagination.
            limit: Max items to return (1–200, enforced by the router query
                parameter validator).

        Returns:
            ``{"items": list[CourseListResponse], "total": int,
               "skip": int, "limit": int}``
        """
        logger.debug(
            "list_courses | skill_id=%s | difficulty=%s | provider=%s"
            " | is_free=%s | skip=%d | limit=%d",
            skill_id, difficulty, provider, is_free, skip, limit,
        )
        courses = self._repo.list_courses(
            skill_id=skill_id,
            difficulty=difficulty,
            provider=provider,
            is_free=is_free,
            skip=skip,
            limit=limit,
        )
        total = self._repo.count_courses(
            skill_id=skill_id,
            difficulty=difficulty,
            provider=provider,
            is_free=is_free,
        )
        return {
            "items": [CourseListResponse.model_validate(c) for c in courses],
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    def update_course(
        self,
        course_id: uuid.UUID,
        payload: CourseUpdate,
    ) -> CourseResponse:
        """Apply a partial update to a course (PATCH semantics).

        Workflow:
            1. Load the course (404 if not found).
            2. If a new ``course_url`` is provided, assert it is not taken
               within the same skill.
            3. Apply changes via the repository (only non-None fields written).
            4. Commit the transaction.
            5. Return the updated ``CourseResponse``.

        Args:
            course_id: UUID of the course to update.
            payload: Validated ``CourseUpdate`` schema (all fields optional).

        Returns:
            Updated ``CourseResponse``.

        Raises:
            CourseError: ``NOT_FOUND`` if the course does not exist.
            CourseError: ``URL_TAKEN`` if the new URL conflicts within the
                same skill.
        """
        logger.info("update_course | id=%s", course_id)

        course = self._get_or_404(course_id)

        if payload.course_url is not None:
            self._assert_url_available(
                payload.course_url, course.skill_id, exclude_id=course_id
            )

        updated = self._repo.update_course(
            course,
            title=payload.title,
            description=payload.description,
            provider=payload.provider,
            course_url=payload.course_url,
            thumbnail_url=payload.thumbnail_url,
            difficulty=payload.difficulty.value if payload.difficulty is not None else None,
            duration_hours=payload.duration_hours,
            is_free=payload.is_free,
            rating=payload.rating,
        )
        self._db.commit()
        logger.info("Course updated | id=%s", updated.id)
        return CourseResponse.model_validate(updated)

    def delete_course(self, course_id: uuid.UUID) -> dict:
        """Hard-delete a course by UUID.

        Courses support full hard-DELETE since they are resource catalogue
        entries without deep referential dependencies.  The deleted course's
        ``id`` and ``title`` are returned in the confirmation envelope.

        Args:
            course_id: UUID of the course to delete.

        Returns:
            Confirmation envelope::

                {
                    "deleted": true,
                    "id": "<uuid>",
                    "title": "<course title>"
                }

        Raises:
            CourseError: ``NOT_FOUND`` if the course does not exist.
        """
        logger.info("delete_course | id=%s", course_id)

        course = self._get_or_404(course_id)
        course_id_str = str(course.id)
        course_title = course.title

        self._repo.delete_course(course)
        self._db.commit()
        logger.info(
            "Course hard-deleted | id=%s | title=%s", course_id_str, course_title
        )

        return {
            "deleted": True,
            "id": course_id_str,
            "title": course_title,
        }
