"""
backend/app/api/v1/professions/router.py
==========================================
FastAPI router for the Profession CRUD API.

Endpoints
---------
  POST   /api/v1/professions/            Create a new profession.
  GET    /api/v1/professions/            List professions (paginated + filtered).
  GET    /api/v1/professions/{id}        Get a profession by UUID.
  GET    /api/v1/professions/slug/{slug} Get a profession by slug.
  PATCH  /api/v1/professions/{id}        Partially update a profession.
  DELETE /api/v1/professions/{id}        Soft-delete a profession.

Architecture contract
---------------------
  ✓ Delegates all business logic to ``ProfessionService``.
  ✓ Maps ``ProfessionError`` domain exceptions to ``HTTPException`` via a
    lookup table — no scattered ``if/elif`` chains.
  ✗ No raw SQL, no password/JWT handling, no schema validation beyond DI.

Error code → HTTP status
------------------------
  not_found       → 404 Not Found
  slug_taken      → 409 Conflict
  name_taken      → 409 Conflict
  already_deleted → 409 Conflict
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.profession import (
    ProfessionCreate,
    ProfessionResponse,
    ProfessionUpdate,
)
from app.services.profession import ProfessionError, ProfessionService

logger: logging.Logger = logging.getLogger(__name__)

router = APIRouter()

# ─────────────────────────────────────────────────────────────────────────────
# Error code → HTTP status mapping
# ─────────────────────────────────────────────────────────────────────────────

_PROFESSION_ERROR_STATUS: dict[str, int] = {
    ProfessionError.NOT_FOUND:       status.HTTP_404_NOT_FOUND,
    ProfessionError.SLUG_TAKEN:      status.HTTP_409_CONFLICT,
    ProfessionError.NAME_TAKEN:      status.HTTP_409_CONFLICT,
    ProfessionError.ALREADY_DELETED: status.HTTP_409_CONFLICT,
}


def _raise_http(exc: ProfessionError) -> None:
    """Convert a ``ProfessionError`` into a ``HTTPException`` and raise it.

    Falls back to 500 for any unknown code, logging at ERROR level so that
    unmapped codes are caught in monitoring before they reach users.

    Args:
        exc: The domain exception raised by ``ProfessionService``.

    Raises:
        HTTPException: Always — never returns normally.
    """
    http_status = _PROFESSION_ERROR_STATUS.get(
        exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR
    )
    if http_status == status.HTTP_500_INTERNAL_SERVER_ERROR:
        logger.error(
            "Unmapped ProfessionError code '%s' fell through to 500: %s",
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
    response_model=ProfessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new profession",
    description=(
        "Create a new career profession record in the catalogue.  "
        "Both ``name`` and ``slug`` must be unique across the platform.\n\n"
        "The ``slug`` is auto-normalised to lowercase + hyphens before "
        "uniqueness is checked, so ``'Machine Learning'`` and "
        "``'machine-learning'`` resolve to the same slug.\n\n"
        "**Required fields:** ``name``, ``slug``.\n"
        "**Optional fields:** ``description``, ``category``, "
        "``average_salary``, ``growth_rate``, ``required_skills``, ``roadmap``."
    ),
    responses={
        201: {"description": "Profession created successfully."},
        409: {"description": "Name or slug already in use by another profession."},
        422: {"description": "Request body failed schema validation."},
    },
)
def create_profession(
    payload: ProfessionCreate,
    db: DbDep,
) -> ProfessionResponse:
    """Create a new profession.

    Args:
        payload: Validated ``ProfessionCreate`` request body.
        db: Injected database session.

    Returns:
        Full ``ProfessionResponse`` for the newly created profession.

    Raises:
        HTTPException 409: If name or slug is already taken.
        HTTPException 422: If request body is invalid (handled by FastAPI).
    """
    logger.info("POST /professions | name=%s", payload.name)
    try:
        return ProfessionService(db).create_profession(payload)
    except ProfessionError as exc:
        _raise_http(exc)


@router.get(
    "/",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="List all professions",
    description=(
        "Return a paginated list of professions.  Use ``is_active`` and "
        "``category`` query parameters to filter results.\n\n"
        "**Pagination:** use ``skip`` (offset) and ``limit`` (max results, "
        "1–200) to page through results.\n\n"
        "**Response shape:**\n"
        "```json\n"
        "{ \"items\": [...], \"total\": 42, \"skip\": 0, \"limit\": 50 }\n"
        "```\n"
        "``items`` contains slim ``ProfessionListResponse`` objects "
        "(no ``roadmap`` / ``required_skills``) for bandwidth efficiency. "
        "Fetch the full record from ``GET /professions/{id}`` when needed."
    ),
    responses={
        200: {"description": "Paginated profession list returned."},
    },
)
def list_professions(
    db: DbDep,
    is_active: Annotated[
        Optional[bool],
        Query(description="Filter by active status. Omit to return all."),
    ] = None,
    category: Annotated[
        Optional[str],
        Query(max_length=100, description="Filter by category (case-sensitive)."),
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
    """List professions with optional filtering and pagination.

    Args:
        db: Injected database session.
        is_active: Filter by active status.
        category: Filter by category string.
        skip: Pagination offset.
        limit: Max rows per page.

    Returns:
        Pagination envelope with ``items``, ``total``, ``skip``, and ``limit``.
    """
    logger.debug("GET /professions | is_active=%s | category=%s | skip=%d | limit=%d",
                 is_active, category, skip, limit)
    return ProfessionService(db).list_professions(
        is_active=is_active,
        category=category,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/slug/{slug}",
    response_model=ProfessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a profession by slug",
    description=(
        "Retrieve the full profession record using its URL-safe slug "
        "(e.g. ``machine-learning-engineer``).  Slugs are unique and "
        "stable — safe to use as canonical URL segments."
    ),
    responses={
        200: {"description": "Profession found and returned."},
        404: {"description": "No profession with the given slug exists."},
    },
)
def get_profession_by_slug(
    slug: str,
    db: DbDep,
) -> ProfessionResponse:
    """Retrieve a profession by its slug.

    **Route placed before ``/{id}``** to avoid FastAPI matching the literal
    string ``"slug"`` as a UUID path parameter.

    Args:
        slug: The URL-safe slug of the profession.
        db: Injected database session.

    Returns:
        Full ``ProfessionResponse`` for the matching profession.

    Raises:
        HTTPException 404: If no profession with the given slug exists.
    """
    logger.debug("GET /professions/slug/%s", slug)
    try:
        return ProfessionService(db).get_profession_by_slug(slug)
    except ProfessionError as exc:
        _raise_http(exc)


@router.get(
    "/{profession_id}",
    response_model=ProfessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a profession by ID",
    description=(
        "Retrieve the full profession record — including ``required_skills`` "
        "and ``roadmap`` — by its UUID primary key."
    ),
    responses={
        200: {"description": "Profession found and returned."},
        404: {"description": "No profession with the given UUID exists."},
        422: {"description": "The provided ID is not a valid UUID."},
    },
)
def get_profession(
    profession_id: uuid.UUID,
    db: DbDep,
) -> ProfessionResponse:
    """Retrieve a profession by UUID.

    Args:
        profession_id: UUID of the profession to retrieve.
        db: Injected database session.

    Returns:
        Full ``ProfessionResponse``.

    Raises:
        HTTPException 404: If no profession with the given ID exists.
    """
    logger.debug("GET /professions/%s", profession_id)
    try:
        return ProfessionService(db).get_profession(profession_id)
    except ProfessionError as exc:
        _raise_http(exc)


@router.patch(
    "/{profession_id}",
    response_model=ProfessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Partially update a profession",
    description=(
        "Apply a partial update to an existing profession (PATCH semantics — "
        "only supplied fields are changed; omitted fields remain unchanged).\n\n"
        "**Uniqueness:** if a new ``name`` or ``slug`` is provided it must not "
        "already be used by another profession.\n\n"
        "**Slug normalisation:** slugs are auto-normalised to lowercase + "
        "hyphens before uniqueness is validated."
    ),
    responses={
        200: {"description": "Profession updated successfully."},
        404: {"description": "Profession not found."},
        409: {"description": "New name or slug conflicts with an existing profession."},
        422: {"description": "Request body failed schema validation."},
    },
)
def update_profession(
    profession_id: uuid.UUID,
    payload: ProfessionUpdate,
    db: DbDep,
) -> ProfessionResponse:
    """Partially update a profession.

    Args:
        profession_id: UUID of the profession to update.
        payload: ``ProfessionUpdate`` body (all fields optional).
        db: Injected database session.

    Returns:
        Updated ``ProfessionResponse``.

    Raises:
        HTTPException 404: If the profession does not exist.
        HTTPException 409: If the new name or slug is already taken.
    """
    logger.info("PATCH /professions/%s", profession_id)
    try:
        return ProfessionService(db).update_profession(profession_id, payload)
    except ProfessionError as exc:
        _raise_http(exc)


@router.delete(
    "/{profession_id}",
    response_model=ProfessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Soft-delete a profession",
    description=(
        "Deactivate a profession by setting ``is_active = false``.  The row "
        "is preserved in the database for referential integrity and audit "
        "history.  The profession will no longer appear in active listings.\n\n"
        "Attempting to delete an already-inactive profession returns **409 "
        "Conflict** (idempotent guard — prevents redundant commits).\n\n"
        "There is no hard-DELETE endpoint by design."
    ),
    responses={
        200: {"description": "Profession deactivated. Updated record returned."},
        404: {"description": "Profession not found."},
        409: {"description": "Profession is already inactive."},
    },
)
def delete_profession(
    profession_id: uuid.UUID,
    db: DbDep,
) -> ProfessionResponse:
    """Soft-delete a profession (set ``is_active = False``).

    Args:
        profession_id: UUID of the profession to deactivate.
        db: Injected database session.

    Returns:
        Updated ``ProfessionResponse`` with ``is_active=False``.

    Raises:
        HTTPException 404: If the profession does not exist.
        HTTPException 409: If the profession is already inactive.
    """
    logger.info("DELETE /professions/%s", profession_id)
    try:
        return ProfessionService(db).delete_profession(profession_id)
    except ProfessionError as exc:
        _raise_http(exc)
