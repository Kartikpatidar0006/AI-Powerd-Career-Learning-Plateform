"""
backend/app/api/v1/skills/router.py
=====================================
FastAPI router for the Skill CRUD API.

Endpoints
---------
  POST   /api/v1/skills/              Create a new skill.
  GET    /api/v1/skills/              List skills (paginated + filtered).
  GET    /api/v1/skills/{id}          Get a skill by UUID.
  PATCH  /api/v1/skills/{id}          Partially update a skill.
  DELETE /api/v1/skills/{id}          Hard-delete a skill.

Query-parameter filters for GET /api/v1/skills/
  profession_id — limit to one profession's skills.
  difficulty    — 'Beginner' | 'Intermediate' | 'Advanced'.
  category      — case-sensitive equality filter.
  skip / limit  — standard offset pagination.

Architecture contract
---------------------
  ✓ Delegates all business logic to ``SkillService``.
  ✓ Maps ``SkillError`` domain exceptions to ``HTTPException`` via a
    lookup table — no scattered ``if/elif`` chains.
  ✗ No raw SQL, no password/JWT handling, no schema validation beyond DI.

Error code → HTTP status
------------------------
  not_found           → 404 Not Found
  profession_not_found→ 404 Not Found
  name_taken          → 409 Conflict
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.skill import (
    DifficultyLevel,
    SkillCreate,
    SkillResponse,
    SkillUpdate,
)
from app.services.skill import SkillError, SkillService

logger: logging.Logger = logging.getLogger(__name__)

router = APIRouter()

# ─────────────────────────────────────────────────────────────────────────────
# Error code → HTTP status mapping
# ─────────────────────────────────────────────────────────────────────────────

_SKILL_ERROR_STATUS: dict[str, int] = {
    SkillError.NOT_FOUND:           status.HTTP_404_NOT_FOUND,
    SkillError.PROFESSION_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    SkillError.NAME_TAKEN:          status.HTTP_409_CONFLICT,
}


def _raise_http(exc: SkillError) -> None:
    """Convert a ``SkillError`` into an ``HTTPException`` and raise it.

    Falls back to 500 for any unknown code, logging at ERROR level so that
    unmapped codes are caught in monitoring before they reach users.

    Args:
        exc: The domain exception raised by ``SkillService``.

    Raises:
        HTTPException: Always — never returns normally.
    """
    http_status = _SKILL_ERROR_STATUS.get(
        exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR
    )
    if http_status == status.HTTP_500_INTERNAL_SERVER_ERROR:
        logger.error(
            "Unmapped SkillError code '%s' fell through to 500: %s",
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
    response_model=SkillResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new skill",
    description=(
        "Create a new skill and associate it with an existing profession via "
        "``profession_id``.\n\n"
        "Skill names must be **unique within a profession** — the same name "
        "can appear under different professions.  For example, both "
        "\"Data Engineering\" and \"Machine Learning\" may list \"Python\" "
        "as a skill.\n\n"
        "**Required fields:** ``name``, ``difficulty``, ``profession_id``.\n"
        "**Optional fields:** ``description``, ``category``."
    ),
    responses={
        201: {"description": "Skill created successfully."},
        404: {"description": "The referenced profession was not found."},
        409: {"description": "A skill with this name already exists for the profession."},
        422: {"description": "Request body failed schema validation."},
    },
)
def create_skill(
    payload: SkillCreate,
    db: DbDep,
) -> SkillResponse:
    """Create a new skill.

    Args:
        payload: Validated ``SkillCreate`` request body.
        db: Injected database session.

    Returns:
        Full ``SkillResponse`` for the newly created skill.

    Raises:
        HTTPException 404: If the referenced ``profession_id`` does not exist.
        HTTPException 409: If the skill name is already taken in this profession.
        HTTPException 422: If request body is invalid (handled by FastAPI).
    """
    logger.info(
        "POST /skills | name=%s | profession_id=%s",
        payload.name, payload.profession_id,
    )
    try:
        return SkillService(db).create_skill(payload)
    except SkillError as exc:
        _raise_http(exc)


@router.get(
    "/",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="List all skills",
    description=(
        "Return a paginated list of skills.  Use ``profession_id``, "
        "``difficulty``, and ``category`` query parameters to filter results.\n\n"
        "**Pagination:** use ``skip`` (offset) and ``limit`` (max results, "
        "1–200) to page through results.\n\n"
        "**Response shape:**\n"
        "```json\n"
        "{ \"items\": [...], \"total\": 42, \"skip\": 0, \"limit\": 50 }\n"
        "```\n"
        "``items`` contains slim ``SkillListResponse`` objects "
        "(no ``description``) for bandwidth efficiency. "
        "Fetch the full record from ``GET /skills/{id}`` when needed."
    ),
    responses={
        200: {"description": "Paginated skill list returned."},
    },
)
def list_skills(
    db: DbDep,
    profession_id: Annotated[
        Optional[uuid.UUID],
        Query(description="Filter to skills belonging to this profession UUID."),
    ] = None,
    difficulty: Annotated[
        Optional[DifficultyLevel],
        Query(description="Filter by difficulty: Beginner, Intermediate, or Advanced."),
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
    """List skills with optional filtering and pagination.

    Args:
        db: Injected database session.
        profession_id: Filter to skills of a specific profession.
        difficulty: Filter by difficulty level enum value.
        category: Filter by category string.
        skip: Pagination offset.
        limit: Max rows per page.

    Returns:
        Pagination envelope with ``items``, ``total``, ``skip``, and ``limit``.
    """
    logger.debug(
        "GET /skills | profession_id=%s | difficulty=%s | category=%s"
        " | skip=%d | limit=%d",
        profession_id, difficulty, category, skip, limit,
    )
    return SkillService(db).list_skills(
        profession_id=profession_id,
        difficulty=difficulty.value if difficulty is not None else None,
        category=category,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{skill_id}",
    response_model=SkillResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a skill by ID",
    description=(
        "Retrieve the full skill record — including ``description`` — "
        "by its UUID primary key."
    ),
    responses={
        200: {"description": "Skill found and returned."},
        404: {"description": "No skill with the given UUID exists."},
        422: {"description": "The provided ID is not a valid UUID."},
    },
)
def get_skill(
    skill_id: uuid.UUID,
    db: DbDep,
) -> SkillResponse:
    """Retrieve a skill by UUID.

    Args:
        skill_id: UUID of the skill to retrieve.
        db: Injected database session.

    Returns:
        Full ``SkillResponse``.

    Raises:
        HTTPException 404: If no skill with the given ID exists.
    """
    logger.debug("GET /skills/%s", skill_id)
    try:
        return SkillService(db).get_skill(skill_id)
    except SkillError as exc:
        _raise_http(exc)


@router.patch(
    "/{skill_id}",
    response_model=SkillResponse,
    status_code=status.HTTP_200_OK,
    summary="Partially update a skill",
    description=(
        "Apply a partial update to an existing skill (PATCH semantics — "
        "only supplied fields are changed; omitted fields remain unchanged).\n\n"
        "**Name uniqueness:** if a new ``name`` is provided it must not already "
        "be used by another skill within the same profession.\n\n"
        "**Re-parenting:** ``profession_id`` cannot be changed after creation "
        "— it is excluded from this endpoint."
    ),
    responses={
        200: {"description": "Skill updated successfully."},
        404: {"description": "Skill not found."},
        409: {"description": "New name conflicts with an existing skill in this profession."},
        422: {"description": "Request body failed schema validation."},
    },
)
def update_skill(
    skill_id: uuid.UUID,
    payload: SkillUpdate,
    db: DbDep,
) -> SkillResponse:
    """Partially update a skill.

    Args:
        skill_id: UUID of the skill to update.
        payload: ``SkillUpdate`` body (all fields optional).
        db: Injected database session.

    Returns:
        Updated ``SkillResponse``.

    Raises:
        HTTPException 404: If the skill does not exist.
        HTTPException 409: If the new name is already taken in this profession.
    """
    logger.info("PATCH /skills/%s", skill_id)
    try:
        return SkillService(db).update_skill(skill_id, payload)
    except SkillError as exc:
        _raise_http(exc)


@router.delete(
    "/{skill_id}",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Delete a skill",
    description=(
        "Permanently remove a skill record from the database.\n\n"
        "Unlike the Profession domain, Skills support full hard-DELETE since "
        "they are granular competency entries without deep referential "
        "dependencies.\n\n"
        "Returns a confirmation envelope with the deleted skill's ``id`` "
        "and ``name``."
    ),
    responses={
        200: {"description": "Skill deleted. Confirmation envelope returned."},
        404: {"description": "Skill not found."},
    },
)
def delete_skill(
    skill_id: uuid.UUID,
    db: DbDep,
) -> dict[str, Any]:
    """Hard-delete a skill.

    Args:
        skill_id: UUID of the skill to delete.
        db: Injected database session.

    Returns:
        Confirmation envelope::

            {
                "deleted": true,
                "id": "<uuid>",
                "name": "<skill name>"
            }

    Raises:
        HTTPException 404: If the skill does not exist.
    """
    logger.info("DELETE /skills/%s", skill_id)
    try:
        return SkillService(db).delete_skill(skill_id)
    except SkillError as exc:
        _raise_http(exc)
