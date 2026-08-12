"""
backend/app/api/v1/courses/router.py
=====================================
FastAPI router for the Course CRUD API.

Endpoints
---------
  POST   /api/v1/courses/              Create a new course.
  GET    /api/v1/courses/              List courses (paginated + filtered).
  GET    /api/v1/courses/{id}          Get a course by UUID.
  PATCH  /api/v1/courses/{id}          Partially update a course.
  DELETE /api/v1/courses/{id}          Hard-delete a course.

Query-parameter filters for GET /api/v1/courses/
  skill_id    — limit to one skill's courses.
  difficulty  — 'Beginner' | 'Intermediate' | 'Advanced'.
  provider    — case-sensitive provider name filter.
  is_free     — boolean filter for free/paid courses.
  skip / limit — standard offset pagination.

Architecture contract
---------------------
  ✓ Delegates all business logic to ``CourseService``.
  ✓ Maps ``CourseError`` domain exceptions to ``HTTPException`` via a
    lookup table — no scattered ``if/elif`` chains.
  ✗ No raw SQL, no password/JWT handling, no schema validation beyond DI.

Error code → HTTP status
------------------------
  not_found     → 404 Not Found
  skill_not_found → 404 Not Found
  url_taken     → 409 Conflict
  invalid_rating → 422 Unprocessable Entity
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.course import (
    CourseDifficultyLevel,
    CourseCreate,
    CourseResponse,
    CourseUpdate,
)
from app.services.course import CourseError, CourseService

logger: logging.Logger = logging.getLogger(__name__)

router = APIRouter()

# ─────────────────────────────────────────────────────────────────────────────
# Error code → HTTP status mapping
# ─────────────────────────────────────────────────────────────────────────────

_COURSE_ERROR_STATUS: dict[str, int] = {
    CourseError.NOT_FOUND:       status.HTTP_404_NOT_FOUND,
    CourseError.SKILL_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    CourseError.URL_TAKEN:       status.HTTP_409_CONFLICT,
    CourseError.INVALID_RATING:  status.HTTP_422_UNPROCESSABLE_ENTITY,
}


def _raise_http(exc: CourseError) -> None:
    """Convert a ``CourseError`` into an ``HTTPException`` and raise it.

    Falls back to 500 for any unknown code, logging at ERROR level so that
    unmapped codes are caught in monitoring before they reach users.

    Args:
        exc: The domain exception raised by ``CourseService``.

    Raises:
        HTTPException: Always — never returns normally.
    """
    http_status = _COURSE_ERROR_STATUS.get(
        exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR
    )
    if http_status == status.HTTP_500_INTERNAL_SERVER_ERROR:
        logger.error(
            "Unmapped CourseError code '%s' fell through to 500: %s",
            exc.code, exc.message,
        )
    raise HTTPException(status_code=http_status, detail=exc.message)


# ─────────────────────────────────────────────────────────────────────────────
# Dependency alias
# ─────────────────────────────────────────────────────────────────────────────

DbDep = Annotated[Session, Depends(get_db)]


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/",
    response_model=CourseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new course",
    description=(
        "Create a new course and associate it with an existing skill via "
        "``skill_id``.\n\n"
        "Course URLs must be **unique within a skill** — the same URL "
        "can appear under different skills.  For example, a Python intro "
        "course may be linked to both 'Python Basics' and 'Data Science'.\n\n"
        "**Required fields:** ``title``, ``difficulty``, ``course_url``, ``skill_id``.\n"
        "**Optional fields:** ``description``, ``provider``, ``thumbnail_url``, "
        "``duration_hours``, ``is_free``, ``rating``."
    ),
    responses={
        201: {"description": "Course created successfully."},
        404: {"description": "The referenced skill was not found."},
        409: {"description": "A course with this URL already exists for the skill."},
        422: {"description": "Request body failed schema validation."},
    },
)
def create_course(
    payload: CourseCreate,
    db: DbDep,
) -> CourseResponse:
    """Create a new course.

    Args:
        payload: Validated ``CourseCreate`` request body.
        db: Injected database session.

    Returns:
        Full ``CourseResponse`` for the newly created course.

    Raises:
        HTTPException 404: If the referenced ``skill_id`` does not exist.
        HTTPException 409: If the course URL is already taken for this skill.
        HTTPException 422: If request body is invalid (handled by FastAPI).
    """
    logger.info(
        "POST /courses | title=%s | skill_id=%s",
        payload.title, payload.skill_id,
    )
    try:
        return CourseService(db).create_course(payload)
    except CourseError as exc:
        _raise_http(exc)


@router.get(
    "/",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="List all courses",
    description=(
        "Return a paginated list of courses.  Use ``skill_id``, "
        "``difficulty``, ``provider``, and ``is_free`` query parameters "
        "to filter results.\n\n"
        "**Pagination:** use ``skip`` (offset) and ``limit`` (max results, "
        "1–200) to page through results.\n\n"
        "**Response shape:**\n"
        "```json\n"
        "{ \"items\": [...], \"total\": 42, \"skip\": 0, \"limit\": 50 }\n"
        "```\n"
        "``items`` contains slim ``CourseListResponse`` objects "
        "(no ``description``) for bandwidth efficiency. "
        "Fetch the full record from ``GET /courses/{id}`` when needed."
    ),
    responses={
        200: {"description": "Paginated course list returned."},
    },
)
def list_courses(
    db: DbDep,
    skill_id: Annotated[
        Optional[uuid.UUID],
        Query(description="Filter to courses belonging to this skill UUID."),
    ] = None,
    difficulty: Annotated[
        Optional[CourseDifficultyLevel],
        Query(description="Filter by difficulty: Beginner, Intermediate, or Advanced."),
    ] = None,
    provider: Annotated[
        Optional[str],
        Query(max_length=255, description="Filter by provider name (case-sensitive)."),
    ] = None,
    is_free: Annotated[
        Optional[bool],
        Query(description="Filter by free (true) or paid (false) courses."),
    ] = None,
    skip: Annotated[
        int,
        Query(ge=0, description="Pagination offset (number of rows to skip)."),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=200, description="Maximum rows to return (1–200)."),
    ] = 50,
) -> dict[str, Any]:
    """List courses with optional filtering and pagination.

    Args:
        db: Injected database session.
        skill_id: Filter to courses of a specific skill.
        difficulty: Filter by difficulty level enum value.
        provider: Filter by provider name string.
        is_free: Filter by free/paid status.
        skip: Pagination offset.
        limit: Max rows per page.

    Returns:
        Pagination envelope with ``items``, ``total``, ``skip``, and ``limit``.
    """
    logger.debug(
        "GET /courses | skill_id=%s | difficulty=%s | provider=%s"
        " | is_free=%s | skip=%d | limit=%d",
        skill_id, difficulty, provider, is_free, skip, limit,
    )
    return CourseService(db).list_courses(
        skill_id=skill_id,
        difficulty=difficulty.value if difficulty is not None else None,
        provider=provider,
        is_free=is_free,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{course_id}",
    response_model=CourseResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a course by ID",
    description=(
        "Retrieve the full course record — including ``description`` — "
        "by its UUID primary key."
    ),
    responses={
        200: {"description": "Course found and returned."},
        404: {"description": "No course with the given UUID exists."},
        422: {"description": "The provided ID is not a valid UUID."},
    },
)
def get_course(
    course_id: uuid.UUID,
    db: DbDep,
) -> CourseResponse:
    """Retrieve a course by UUID.

    Args:
        course_id: UUID of the course to retrieve.
        db: Injected database session.

    Returns:
        Full ``CourseResponse``.

    Raises:
        HTTPException 404: If no course with the given ID exists.
    """
    logger.debug("GET /courses/%s", course_id)
    try:
        return CourseService(db).get_course(course_id)
    except CourseError as exc:
        _raise_http(exc)


@router.patch(
    "/{course_id}",
    response_model=CourseResponse,
    status_code=status.HTTP_200_OK,
    summary="Partially update a course",
    description=(
        "Apply a partial update to an existing course (PATCH semantics — "
        "only supplied fields are changed; omitted fields remain unchanged).\n\n"
        "**URL uniqueness:** if a new ``course_url`` is provided it must not "
        "already be used by another course within the same skill.\n\n"
        "**Re-parenting:** ``skill_id`` cannot be changed after creation "
        "— it is excluded from this endpoint."
    ),
    responses={
        200: {"description": "Course updated successfully."},
        404: {"description": "Course not found."},
        409: {"description": "New URL conflicts with an existing course for this skill."},
        422: {"description": "Request body failed schema validation."},
    },
)
def update_course(
    course_id: uuid.UUID,
    payload: CourseUpdate,
    db: DbDep,
) -> CourseResponse:
    """Partially update a course.

    Args:
        course_id: UUID of the course to update.
        payload: ``CourseUpdate`` body (all fields optional).
        db: Injected database session.

    Returns:
        Updated ``CourseResponse``.

    Raises:
        HTTPException 404: If the course does not exist.
        HTTPException 409: If the new URL is already taken for this skill.
    """
    logger.info("PATCH /courses/%s", course_id)
    try:
        return CourseService(db).update_course(course_id, payload)
    except CourseError as exc:
        _raise_http(exc)


@router.delete(
    "/{course_id}",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Delete a course",
    description=(
        "Permanently remove a course record from the database.\n\n"
        "Courses support full hard-DELETE since they are external resource "
        "catalogue entries without deep referential dependencies.\n\n"
        "Returns a confirmation envelope with the deleted course's ``id`` "
        "and ``title``."
    ),
    responses={
        200: {"description": "Course deleted. Confirmation envelope returned."},
        404: {"description": "Course not found."},
    },
)
def delete_course(
    course_id: uuid.UUID,
    db: DbDep,
) -> dict[str, Any]:
    """Hard-delete a course.

    Args:
        course_id: UUID of the course to delete.
        db: Injected database session.

    Returns:
        Confirmation envelope::

            {
                "deleted": true,
                "id": "<uuid>",
                "title": "<course title>"
            }

    Raises:
        HTTPException 404: If the course does not exist.
    """
    logger.info("DELETE /courses/%s", course_id)
    try:
        return CourseService(db).delete_course(course_id)
    except CourseError as exc:
        _raise_http(exc)
