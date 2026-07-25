"""
backend/app/api/v1/learning_paths/router.py
============================================
FastAPI router for the Learning Path CRUD API.

Endpoints
---------
  POST   /api/v1/learning-paths/          Create a new learning path entry.
  GET    /api/v1/learning-paths/          List entries (paginated + filtered).
  GET    /api/v1/learning-paths/{id}      Get a single entry by UUID.
  PATCH  /api/v1/learning-paths/{id}      Partially update an entry.
  DELETE /api/v1/learning-paths/{id}      Hard-delete an entry.

Query-parameter filters for GET /api/v1/learning-paths/
  profession_id — limit to one profession's ordered path.
  skill_id      — find which profession paths include a skill.
  is_required   — filter by required / optional flag.
  skip / limit  — standard offset pagination.

Architecture contract
---------------------
  ✓ Delegates all business logic to ``LearningPathService``.
  ✓ Maps ``LearningPathError`` domain exceptions to ``HTTPException`` via a
    lookup table — no scattered ``if/elif`` chains.
  ✗ No raw SQL, no password/JWT handling, no schema validation beyond DI.

Error code → HTTP status
------------------------
  not_found               → 404 Not Found
  profession_not_found    → 404 Not Found
  skill_not_found         → 404 Not Found
  skill_not_in_profession → 422 Unprocessable Entity
  sequence_taken          → 409 Conflict
  skill_already_in_path   → 409 Conflict
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.learning_path import (
    LearningPathCreate,
    LearningPathResponse,
    LearningPathUpdate,
)
from app.services.learning_path import LearningPathError, LearningPathService

logger: logging.Logger = logging.getLogger(__name__)

router = APIRouter()

# ─────────────────────────────────────────────────────────────────────────────
# Error code → HTTP status mapping
# ─────────────────────────────────────────────────────────────────────────────

_LP_ERROR_STATUS: dict[str, int] = {
    LearningPathError.NOT_FOUND:              status.HTTP_404_NOT_FOUND,
    LearningPathError.PROFESSION_NOT_FOUND:   status.HTTP_404_NOT_FOUND,
    LearningPathError.SKILL_NOT_FOUND:        status.HTTP_404_NOT_FOUND,
    LearningPathError.SKILL_NOT_IN_PROFESSION: status.HTTP_422_UNPROCESSABLE_CONTENT,
    LearningPathError.SEQUENCE_TAKEN:         status.HTTP_409_CONFLICT,
    LearningPathError.SKILL_ALREADY_IN_PATH:  status.HTTP_409_CONFLICT,
}


def _raise_http(exc: LearningPathError) -> None:
    """Convert a ``LearningPathError`` into an ``HTTPException`` and raise it.

    Falls back to 500 for any unknown code, logging at ERROR level so that
    unmapped codes are caught in monitoring before they reach users.

    Args:
        exc: The domain exception raised by ``LearningPathService``.

    Raises:
        HTTPException: Always — never returns normally.
    """
    http_status = _LP_ERROR_STATUS.get(
        exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR
    )
    if http_status == status.HTTP_500_INTERNAL_SERVER_ERROR:
        logger.error(
            "Unmapped LearningPathError code '%s' fell through to 500: %s",
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
    response_model=LearningPathResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a learning path entry",
    description=(
        "Add a new ordered step to a profession's learning path.\n\n"
        "**Validation rules enforced:**\n"
        "- ``profession_id`` must reference an existing profession.\n"
        "- ``skill_id`` must reference a skill that belongs to the **same** "
        "profession (cross-profession skills are rejected with 422).\n"
        "- ``sequence`` must be unique within the profession's path "
        "(conflict returns 409).\n"
        "- A skill can appear **at most once** per profession path "
        "(duplicate returns 409).\n\n"
        "**Required fields:** ``profession_id``, ``skill_id``, ``sequence``.\n"
        "**Optional fields:** ``estimated_weeks`` (default 1), "
        "``is_required`` (default ``true``)."
    ),
    responses={
        201: {"description": "Learning path entry created successfully."},
        404: {"description": "Profession or skill UUID not found."},
        409: {"description": "Sequence number or skill already used in this path."},
        422: {"description": "Skill does not belong to the given profession, "
                             "or request body failed schema validation."},
    },
)
def create_learning_path(
    payload: LearningPathCreate,
    db: DbDep,
) -> LearningPathResponse:
    """Create a new learning path entry.

    Args:
        payload: Validated ``LearningPathCreate`` request body.
        db: Injected database session.

    Returns:
        Full ``LearningPathResponse`` for the newly created entry.

    Raises:
        HTTPException 404: If profession or skill UUID not found.
        HTTPException 409: If sequence or skill already in this path.
        HTTPException 422: If skill does not belong to the profession.
    """
    logger.info(
        "POST /learning-paths | profession_id=%s | skill_id=%s | sequence=%d",
        payload.profession_id, payload.skill_id, payload.sequence,
    )
    try:
        return LearningPathService(db).create_learning_path(payload)
    except LearningPathError as exc:
        _raise_http(exc)


@router.get(
    "/",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="List learning path entries",
    description=(
        "Return a paginated list of learning path entries.  The most common "
        "usage is filtering by ``profession_id`` to retrieve the **full ordered "
        "learning sequence** for one profession.\n\n"
        "**Pagination:** use ``skip`` (offset) and ``limit`` (max results, "
        "1–200) to page through results.\n\n"
        "**Response shape:**\n"
        "```json\n"
        "{ \"items\": [...], \"total\": 12, \"skip\": 0, \"limit\": 50 }\n"
        "```\n"
        "Results are ordered by ``profession_id`` then ``sequence`` ascending "
        "so the path renders in correct learning order."
    ),
    responses={
        200: {"description": "Paginated learning path list returned."},
    },
)
def list_learning_paths(
    db: DbDep,
    profession_id: Annotated[
        Optional[uuid.UUID],
        Query(description="Filter to entries belonging to this profession UUID."),
    ] = None,
    skill_id: Annotated[
        Optional[uuid.UUID],
        Query(description="Filter to entries referencing this skill UUID."),
    ] = None,
    is_required: Annotated[
        Optional[bool],
        Query(description="Filter by required flag. Omit to return all."),
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
    """List learning path entries with optional filtering and pagination.

    Args:
        db: Injected database session.
        profession_id: Filter to entries of a specific profession.
        skill_id: Filter to entries referencing a specific skill.
        is_required: Filter by required / optional flag.
        skip: Pagination offset.
        limit: Max rows per page.

    Returns:
        Pagination envelope with ``items``, ``total``, ``skip``, and ``limit``.
    """
    logger.debug(
        "GET /learning-paths | profession_id=%s | skill_id=%s"
        " | is_required=%s | skip=%d | limit=%d",
        profession_id, skill_id, is_required, skip, limit,
    )
    return LearningPathService(db).list_learning_paths(
        profession_id=profession_id,
        skill_id=skill_id,
        is_required=is_required,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{learning_path_id}",
    response_model=LearningPathResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a learning path entry by ID",
    description=(
        "Retrieve the full learning path entry record by its UUID primary key."
    ),
    responses={
        200: {"description": "Entry found and returned."},
        404: {"description": "No entry with the given UUID exists."},
        422: {"description": "The provided ID is not a valid UUID."},
    },
)
def get_learning_path(
    learning_path_id: uuid.UUID,
    db: DbDep,
) -> LearningPathResponse:
    """Retrieve a single learning path entry by UUID.

    Args:
        learning_path_id: UUID of the entry to retrieve.
        db: Injected database session.

    Returns:
        Full ``LearningPathResponse``.

    Raises:
        HTTPException 404: If no entry with the given ID exists.
    """
    logger.debug("GET /learning-paths/%s", learning_path_id)
    try:
        return LearningPathService(db).get_learning_path(learning_path_id)
    except LearningPathError as exc:
        _raise_http(exc)


@router.patch(
    "/{learning_path_id}",
    response_model=LearningPathResponse,
    status_code=status.HTTP_200_OK,
    summary="Partially update a learning path entry",
    description=(
        "Apply a partial update to an existing learning path entry "
        "(PATCH semantics — only supplied fields are changed).\n\n"
        "**Mutable fields:** ``sequence``, ``estimated_weeks``, ``is_required``.\n\n"
        "**Immutable fields:** ``profession_id`` and ``skill_id`` — re-parenting "
        "requires DELETE + POST.\n\n"
        "**Sequence uniqueness:** if a new ``sequence`` is provided, it must not "
        "already be used by another entry in the same profession."
    ),
    responses={
        200: {"description": "Entry updated successfully."},
        404: {"description": "Entry not found."},
        409: {"description": "New sequence conflicts with an existing step."},
        422: {"description": "Request body failed schema validation."},
    },
)
def update_learning_path(
    learning_path_id: uuid.UUID,
    payload: LearningPathUpdate,
    db: DbDep,
) -> LearningPathResponse:
    """Partially update a learning path entry.

    Args:
        learning_path_id: UUID of the entry to update.
        payload: ``LearningPathUpdate`` body (all fields optional).
        db: Injected database session.

    Returns:
        Updated ``LearningPathResponse``.

    Raises:
        HTTPException 404: If the entry does not exist.
        HTTPException 409: If the new sequence is already taken.
    """
    logger.info("PATCH /learning-paths/%s", learning_path_id)
    try:
        return LearningPathService(db).update_learning_path(learning_path_id, payload)
    except LearningPathError as exc:
        _raise_http(exc)


@router.delete(
    "/{learning_path_id}",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Delete a learning path entry",
    description=(
        "Permanently remove a learning path entry from the database.\n\n"
        "This is a hard-DELETE — the row is not recoverable after this "
        "operation.  Re-sequence remaining steps manually if required.\n\n"
        "Returns a confirmation envelope with the deleted entry's ``id``, "
        "``profession_id``, ``skill_id``, and ``sequence``."
    ),
    responses={
        200: {"description": "Entry deleted. Confirmation envelope returned."},
        404: {"description": "Entry not found."},
    },
)
def delete_learning_path(
    learning_path_id: uuid.UUID,
    db: DbDep,
) -> dict[str, Any]:
    """Hard-delete a learning path entry.

    Args:
        learning_path_id: UUID of the entry to delete.
        db: Injected database session.

    Returns:
        Confirmation envelope::

            {
                "deleted": true,
                "id": "<uuid>",
                "profession_id": "<uuid>",
                "skill_id": "<uuid>",
                "sequence": 3
            }

    Raises:
        HTTPException 404: If the entry does not exist.
    """
    logger.info("DELETE /learning-paths/%s", learning_path_id)
    try:
        return LearningPathService(db).delete_learning_path(learning_path_id)
    except LearningPathError as exc:
        _raise_http(exc)
