"""
backend/app/api/v1/user_progress/router.py
============================================
FastAPI router for the UserProgress CRUD API.

Endpoints
---------
  POST   /api/v1/user-progress/                    Create a new progress record.
  GET    /api/v1/user-progress/                    List records (paginated + filtered).
  GET    /api/v1/user-progress/{id}                Get a record by UUID.
  GET    /api/v1/user-progress/by-skill            Get by user_id + skill_id query params.
  GET    /api/v1/user-progress/stats/{user_id}     Aggregated stats for a user.
  PATCH  /api/v1/user-progress/{id}                Partially update a record.
  DELETE /api/v1/user-progress/{id}                Hard-delete a record.

Query-parameter filters for GET /api/v1/user-progress/
  user_id    — limit to one user's progress records.
  skill_id   — limit to one skill's progress records.
  status     — 'NOT_STARTED' | 'IN_PROGRESS' | 'COMPLETED'.
  skip / limit — standard offset pagination.

Architecture contract
---------------------
  ✓ Delegates all business logic to ``UserProgressService``.
  ✓ Maps ``UserProgressError`` domain exceptions to ``HTTPException`` via a
    lookup table — no scattered ``if/elif`` chains.
  ✗ No raw SQL, no password/JWT handling, no schema validation beyond DI.

Error code → HTTP status
------------------------
  not_found          → 404 Not Found
  user_not_found     → 404 Not Found
  skill_not_found    → 404 Not Found
  already_exists     → 409 Conflict
  invalid_transition → 422 Unprocessable Entity
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.user_progress import (
    ProgressStatus,
    UserProgressCreate,
    UserProgressResponse,
    UserProgressUpdate,
)
from app.services.user_progress import UserProgressError, UserProgressService

logger: logging.Logger = logging.getLogger(__name__)

router = APIRouter()

# ─────────────────────────────────────────────────────────────────────────────
# Error code → HTTP status mapping
# ─────────────────────────────────────────────────────────────────────────────

_PROGRESS_ERROR_STATUS: dict[str, int] = {
    UserProgressError.NOT_FOUND:          status.HTTP_404_NOT_FOUND,
    UserProgressError.USER_NOT_FOUND:     status.HTTP_404_NOT_FOUND,
    UserProgressError.SKILL_NOT_FOUND:    status.HTTP_404_NOT_FOUND,
    UserProgressError.ALREADY_EXISTS:     status.HTTP_409_CONFLICT,
    UserProgressError.INVALID_TRANSITION: status.HTTP_422_UNPROCESSABLE_ENTITY,
}


def _raise_http(exc: UserProgressError) -> None:
    """Convert a ``UserProgressError`` into an ``HTTPException`` and raise it.

    Falls back to 500 for any unknown code, logging at ERROR level so that
    unmapped codes are caught in monitoring before they reach users.

    Args:
        exc: The domain exception raised by ``UserProgressService``.

    Raises:
        HTTPException: Always — never returns normally.
    """
    http_status = _PROGRESS_ERROR_STATUS.get(
        exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR
    )
    if http_status == status.HTTP_500_INTERNAL_SERVER_ERROR:
        logger.error(
            "Unmapped UserProgressError code '%s' fell through to 500: %s",
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
    response_model=UserProgressResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new progress record",
    description=(
        "Create a user progress record linking a learner to a skill.\n\n"
        "The ``(user_id, skill_id)`` pair must be **unique** — only one progress "
        "record is allowed per learner per skill.  Use ``PATCH`` to update an "
        "existing record.\n\n"
        "**Auto-managed fields:**\n"
        "- ``started_at`` — set automatically to NOW when status is not "
        "``NOT_STARTED``.\n"
        "- ``completed_at`` — set automatically to NOW when status is "
        "``COMPLETED``.\n"
        "- ``last_accessed`` — always set to NOW on create.\n\n"
        "**Required fields:** ``user_id``, ``skill_id``.\n"
        "**Optional fields:** ``status``, ``progress_percentage``, "
        "``time_spent_minutes``, and the timestamp fields."
    ),
    responses={
        201: {"description": "Progress record created successfully."},
        404: {"description": "The referenced user or skill was not found."},
        409: {
            "description": "A progress record already exists for this user + skill."
        },
        422: {"description": "Request body failed schema validation."},
    },
)
def create_progress(
    payload: UserProgressCreate,
    db: DbDep,
) -> UserProgressResponse:
    """Create a new user progress record.

    Args:
        payload: Validated ``UserProgressCreate`` request body.
        db: Injected database session.

    Returns:
        Full ``UserProgressResponse`` for the newly created record.

    Raises:
        HTTPException 404: If the referenced user or skill does not exist.
        HTTPException 409: If a progress record already exists for the pair.
        HTTPException 422: If request body is invalid (handled by FastAPI).
    """
    logger.info(
        "POST /user-progress | user_id=%s | skill_id=%s",
        payload.user_id, payload.skill_id,
    )
    try:
        return UserProgressService(db).create_progress(payload)
    except UserProgressError as exc:
        _raise_http(exc)


@router.get(
    "/",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="List progress records",
    description=(
        "Return a paginated list of user progress records.  Use ``user_id``, "
        "``skill_id``, and ``status`` to filter results.\n\n"
        "**Pagination:** use ``skip`` (offset) and ``limit`` (1–200) to page "
        "through results.\n\n"
        "**Response shape:**\n"
        "```json\n"
        "{ \"items\": [...], \"total\": 42, \"skip\": 0, \"limit\": 50 }\n"
        "```\n"
        "``items`` contains slim ``UserProgressListResponse`` objects. "
        "Fetch the full record from ``GET /user-progress/{id}`` when needed."
    ),
    responses={
        200: {"description": "Paginated progress list returned."},
    },
)
def list_progress(
    db: DbDep,
    user_id: Annotated[
        Optional[uuid.UUID],
        Query(description="Filter to progress records for this user UUID."),
    ] = None,
    skill_id: Annotated[
        Optional[uuid.UUID],
        Query(description="Filter to progress records for this skill UUID."),
    ] = None,
    status_filter: Annotated[
        Optional[ProgressStatus],
        Query(
            alias="status",
            description="Filter by status: NOT_STARTED, IN_PROGRESS, or COMPLETED.",
        ),
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
    """List progress records with optional filtering and pagination.

    Args:
        db: Injected database session.
        user_id: Filter to one user's records.
        skill_id: Filter to one skill's records.
        status_filter: Filter by lifecycle status enum value.
        skip: Pagination offset.
        limit: Max rows per page.

    Returns:
        Pagination envelope with ``items``, ``total``, ``skip``, and ``limit``.
    """
    logger.debug(
        "GET /user-progress | user_id=%s | skill_id=%s | status=%s"
        " | skip=%d | limit=%d",
        user_id, skill_id, status_filter, skip, limit,
    )
    return UserProgressService(db).list_progress(
        user_id=user_id,
        skill_id=skill_id,
        status=status_filter.value if status_filter is not None else None,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/by-skill",
    response_model=UserProgressResponse,
    status_code=status.HTTP_200_OK,
    summary="Get progress by user and skill",
    description=(
        "Retrieve a progress record by the ``(user_id, skill_id)`` query "
        "parameter pair — useful when the client knows the user and skill but "
        "not the progress record UUID.\n\n"
        "**Both parameters are required.**"
    ),
    responses={
        200: {"description": "Progress record found and returned."},
        404: {"description": "No progress record exists for this user + skill pair."},
        422: {"description": "Missing or invalid query parameters."},
    },
)
def get_progress_by_user_skill(
    db: DbDep,
    user_id: Annotated[
        uuid.UUID,
        Query(description="UUID of the learner."),
    ],
    skill_id: Annotated[
        uuid.UUID,
        Query(description="UUID of the skill."),
    ],
) -> UserProgressResponse:
    """Retrieve a progress record by (user_id, skill_id) pair.

    Args:
        db: Injected database session.
        user_id: UUID of the learner.
        skill_id: UUID of the skill.

    Returns:
        Full ``UserProgressResponse``.

    Raises:
        HTTPException 404: If no matching progress record exists.
    """
    logger.debug(
        "GET /user-progress/by-skill | user_id=%s | skill_id=%s",
        user_id, skill_id,
    )
    try:
        return UserProgressService(db).get_progress_by_user_skill(
            user_id, skill_id
        )
    except UserProgressError as exc:
        _raise_http(exc)


@router.get(
    "/stats/{user_id}",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get completion statistics for a user",
    description=(
        "Return aggregated skill-status counts for a given learner.\n\n"
        "**Response shape:**\n"
        "```json\n"
        "{\n"
        "  \"user_id\": \"<uuid>\",\n"
        "  \"total\": 20,\n"
        "  \"not_started\": 5,\n"
        "  \"in_progress\": 10,\n"
        "  \"completed\": 5,\n"
        "  \"completion_rate\": 25.0\n"
        "}\n"
        "```\n"
        "``completion_rate`` is expressed as a percentage (0.0–100.0)."
    ),
    responses={
        200: {"description": "Aggregated statistics returned."},
        404: {"description": "User not found."},
    },
)
def get_user_stats(
    user_id: uuid.UUID,
    db: DbDep,
) -> dict[str, Any]:
    """Return aggregated progress statistics for a user.

    Args:
        user_id: UUID of the user to summarise.
        db: Injected database session.

    Returns:
        Dict with total, per-status counts, and completion_rate.

    Raises:
        HTTPException 404: If the user does not exist.
    """
    logger.debug("GET /user-progress/stats/%s", user_id)
    try:
        return UserProgressService(db).get_user_stats(user_id)
    except UserProgressError as exc:
        _raise_http(exc)


@router.get(
    "/{progress_id}",
    response_model=UserProgressResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a progress record by ID",
    description=(
        "Retrieve the full progress record — including all lifecycle timestamps "
        "— by its UUID primary key."
    ),
    responses={
        200: {"description": "Progress record found and returned."},
        404: {"description": "No progress record with the given UUID exists."},
        422: {"description": "The provided ID is not a valid UUID."},
    },
)
def get_progress(
    progress_id: uuid.UUID,
    db: DbDep,
) -> UserProgressResponse:
    """Retrieve a progress record by UUID.

    Args:
        progress_id: UUID of the record to retrieve.
        db: Injected database session.

    Returns:
        Full ``UserProgressResponse``.

    Raises:
        HTTPException 404: If no record with the given ID exists.
    """
    logger.debug("GET /user-progress/%s", progress_id)
    try:
        return UserProgressService(db).get_progress(progress_id)
    except UserProgressError as exc:
        _raise_http(exc)


@router.patch(
    "/{progress_id}",
    response_model=UserProgressResponse,
    status_code=status.HTTP_200_OK,
    summary="Partially update a progress record",
    description=(
        "Apply a partial update to an existing progress record (PATCH semantics "
        "— only supplied fields are changed; omitted fields remain unchanged).\n\n"
        "**Business rules enforced:**\n"
        "- ``status = 'COMPLETED'`` requires ``progress_percentage = 100``.\n"
        "- ``progress_percentage = 100`` with ``status = 'NOT_STARTED'`` "
        "is rejected.\n"
        "- ``completed_at`` cannot be set when transitioning away from "
        "``COMPLETED``.\n\n"
        "**Auto-managed fields (no need to supply manually):**\n"
        "- ``started_at`` — set to NOW on first transition from NOT_STARTED.\n"
        "- ``completed_at`` — set to NOW when transitioning to COMPLETED.\n"
        "- ``last_accessed`` — always updated to NOW.\n\n"
        "**Immutable:** ``user_id`` and ``skill_id`` cannot be changed."
    ),
    responses={
        200: {"description": "Progress record updated successfully."},
        404: {"description": "Progress record not found."},
        422: {
            "description": "Request body failed validation or invalid state transition."
        },
    },
)
def update_progress(
    progress_id: uuid.UUID,
    payload: UserProgressUpdate,
    db: DbDep,
) -> UserProgressResponse:
    """Partially update a progress record.

    Args:
        progress_id: UUID of the record to update.
        payload: ``UserProgressUpdate`` body (all fields optional).
        db: Injected database session.

    Returns:
        Updated ``UserProgressResponse``.

    Raises:
        HTTPException 404: If the record does not exist.
        HTTPException 422: If the status/percentage transition is invalid.
    """
    logger.info("PATCH /user-progress/%s", progress_id)
    try:
        return UserProgressService(db).update_progress(progress_id, payload)
    except UserProgressError as exc:
        _raise_http(exc)


@router.delete(
    "/{progress_id}",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Delete a progress record",
    description=(
        "Permanently remove a user progress record from the database.\n\n"
        "Returns a confirmation envelope with the deleted record's ``id``, "
        "``user_id``, and ``skill_id``."
    ),
    responses={
        200: {"description": "Record deleted. Confirmation envelope returned."},
        404: {"description": "Progress record not found."},
    },
)
def delete_progress(
    progress_id: uuid.UUID,
    db: DbDep,
) -> dict[str, Any]:
    """Hard-delete a progress record.

    Args:
        progress_id: UUID of the record to delete.
        db: Injected database session.

    Returns:
        Confirmation envelope::

            {
                "deleted": true,
                "id": "<uuid>",
                "user_id": "<uuid>",
                "skill_id": "<uuid>"
            }

    Raises:
        HTTPException 404: If the record does not exist.
    """
    logger.info("DELETE /user-progress/%s", progress_id)
    try:
        return UserProgressService(db).delete_progress(progress_id)
    except UserProgressError as exc:
        _raise_http(exc)
