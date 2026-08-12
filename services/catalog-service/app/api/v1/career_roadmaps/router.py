"""
backend/app/api/v1/career_roadmaps/router.py
==============================================
FastAPI router for the Career Roadmap CRUD API.

This router exposes two sub-domains:
  • ``CareerRoadmap`` CRUD   — prefix ``/api/v1/career-roadmaps``
  • ``RoadmapStep``  CRUD   — prefix ``/api/v1/roadmap-steps``

Roadmap Endpoints
-----------------
  POST   /api/v1/career-roadmaps/                   Create a roadmap.
  GET    /api/v1/career-roadmaps/                   List roadmaps (paginated + filtered).
  GET    /api/v1/career-roadmaps/{id}               Get a roadmap by UUID (includes steps).
  PATCH  /api/v1/career-roadmaps/{id}               Partially update a roadmap.
  DELETE /api/v1/career-roadmaps/{id}               Hard-delete a roadmap + its steps.

Roadmap query-parameter filters
  profession_id  — limit to one profession's roadmaps.
  difficulty     — 'Beginner' | 'Intermediate' | 'Advanced'.
  is_active      — boolean visibility filter.
  skip / limit   — standard offset pagination.

Step Endpoints
--------------
  POST   /api/v1/roadmap-steps/                     Add a step to a roadmap.
  GET    /api/v1/roadmap-steps/                     List steps (paginated + filtered).
  GET    /api/v1/roadmap-steps/{id}                 Get a step by UUID.
  PATCH  /api/v1/roadmap-steps/{id}                 Partially update a step.
  DELETE /api/v1/roadmap-steps/{id}                 Hard-delete a step.

Step query-parameter filters
  roadmap_id — limit to steps of one roadmap.
  skill_id   — limit to steps referencing a specific skill.
  required   — boolean required/optional filter.
  skip / limit — standard offset pagination.

Architecture contract
---------------------
  ✓ Delegates all business logic to ``CareerRoadmapService`` /
    ``RoadmapStepService``.
  ✓ Maps ``CareerRoadmapError`` domain exceptions to ``HTTPException``
    via a lookup table — no scattered if/elif chains.

Error code → HTTP status
------------------------
  not_found            → 404 Not Found
  profession_not_found → 404 Not Found
  skill_not_found      → 404 Not Found
  roadmap_not_found    → 404 Not Found
  title_taken          → 409 Conflict
  order_taken          → 409 Conflict
  skill_duplicate      → 409 Conflict
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.career_roadmap import (
    CareerRoadmapCreate,
    CareerRoadmapResponse,
    CareerRoadmapUpdate,
    RoadmapDifficultyLevel,
    RoadmapStepCreate,
    RoadmapStepResponse,
    RoadmapStepUpdate,
)
from app.services.career_roadmap import (
    CareerRoadmapError,
    CareerRoadmapService,
    RoadmapStepService,
)

logger: logging.Logger = logging.getLogger(__name__)

# Two routers — one per sub-domain
roadmap_router = APIRouter()
step_router = APIRouter()

# ─────────────────────────────────────────────────────────────────────────────
# Error code → HTTP status mapping
# ─────────────────────────────────────────────────────────────────────────────

_ERROR_STATUS: dict[str, int] = {
    CareerRoadmapError.NOT_FOUND:            status.HTTP_404_NOT_FOUND,
    CareerRoadmapError.PROFESSION_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    CareerRoadmapError.SKILL_NOT_FOUND:      status.HTTP_404_NOT_FOUND,
    CareerRoadmapError.ROADMAP_NOT_FOUND:    status.HTTP_404_NOT_FOUND,
    CareerRoadmapError.TITLE_TAKEN:          status.HTTP_409_CONFLICT,
    CareerRoadmapError.ORDER_TAKEN:          status.HTTP_409_CONFLICT,
    CareerRoadmapError.SKILL_DUPLICATE:      status.HTTP_409_CONFLICT,
}


def _raise_http(exc: CareerRoadmapError) -> None:
    """Convert a ``CareerRoadmapError`` to an ``HTTPException`` and raise it.

    Falls back to 500 for any unmapped code, logging at ERROR level so that
    gaps are visible in monitoring before they reach users.

    Args:
        exc: The domain exception raised by a service.

    Raises:
        HTTPException: Always — never returns normally.
    """
    http_status = _ERROR_STATUS.get(
        exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR
    )
    if http_status == status.HTTP_500_INTERNAL_SERVER_ERROR:
        logger.error(
            "Unmapped CareerRoadmapError code '%s' fell through to 500: %s",
            exc.code, exc.message,
        )
    raise HTTPException(status_code=http_status, detail=exc.message)


# ─────────────────────────────────────────────────────────────────────────────
# Dependency alias
# ─────────────────────────────────────────────────────────────────────────────

DbDep = Annotated[Session, Depends(get_db)]


# ═════════════════════════════════════════════════════════════════════════════
#  CareerRoadmap endpoints
# ═════════════════════════════════════════════════════════════════════════════


@roadmap_router.post(
    "/",
    response_model=CareerRoadmapResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a career roadmap",
    description=(
        "Create a new career roadmap for an existing profession.\n\n"
        "Roadmap titles must be **unique within a profession** — the same "
        "title may appear under different professions.\n\n"
        "**Required fields:** ``profession_id``, ``title``, ``difficulty``.\n"
        "**Optional fields:** ``description``, ``estimated_months``, ``is_active``.\n\n"
        "The response includes the full roadmap including its (initially empty) "
        "``steps`` list."
    ),
    responses={
        201: {"description": "Roadmap created successfully."},
        404: {"description": "Referenced profession not found."},
        409: {"description": "A roadmap with this title already exists for the profession."},
        422: {"description": "Request body failed schema validation."},
    },
)
def create_roadmap(
    payload: CareerRoadmapCreate,
    db: DbDep,
) -> CareerRoadmapResponse:
    """Create a new career roadmap.

    Args:
        payload: Validated ``CareerRoadmapCreate`` request body.
        db: Injected database session.

    Returns:
        Full ``CareerRoadmapResponse`` (with empty steps list) for the new roadmap.

    Raises:
        HTTPException 404: If the referenced profession does not exist.
        HTTPException 409: If the title is already used for this profession.
    """
    logger.info(
        "POST /career-roadmaps | profession_id=%s | title=%s",
        payload.profession_id, payload.title,
    )
    try:
        return CareerRoadmapService(db).create_roadmap(payload)
    except CareerRoadmapError as exc:
        _raise_http(exc)


@roadmap_router.get(
    "/",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="List career roadmaps",
    description=(
        "Return a paginated list of career roadmaps.  Use ``profession_id``, "
        "``difficulty``, and ``is_active`` to filter results.\n\n"
        "**Response shape:**\n"
        "```json\n"
        "{ \"items\": [...], \"total\": 42, \"skip\": 0, \"limit\": 50 }\n"
        "```\n"
        "``items`` contains slim ``CareerRoadmapListResponse`` objects "
        "(no ``description`` or ``steps``).  Fetch the full record from "
        "``GET /career-roadmaps/{id}`` when needed."
    ),
    responses={
        200: {"description": "Paginated roadmap list returned."},
    },
)
def list_roadmaps(
    db: DbDep,
    profession_id: Annotated[
        Optional[uuid.UUID],
        Query(description="Filter to roadmaps for this profession UUID."),
    ] = None,
    difficulty: Annotated[
        Optional[RoadmapDifficultyLevel],
        Query(description="Filter by difficulty: Beginner, Intermediate, or Advanced."),
    ] = None,
    is_active: Annotated[
        Optional[bool],
        Query(description="Filter by active (true) or inactive (false) status."),
    ] = None,
    skip: Annotated[
        int,
        Query(ge=0, description="Pagination offset."),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=200, description="Maximum rows to return (1–200)."),
    ] = 50,
) -> dict[str, Any]:
    """List career roadmaps with optional filtering and pagination.

    Args:
        db: Injected database session.
        profession_id: Filter to one profession's roadmaps.
        difficulty: Filter by difficulty enum value.
        is_active: Filter by active/inactive status.
        skip: Pagination offset.
        limit: Max rows per page.

    Returns:
        Pagination envelope with ``items``, ``total``, ``skip``, ``limit``.
    """
    logger.debug(
        "GET /career-roadmaps | profession_id=%s | difficulty=%s"
        " | is_active=%s | skip=%d | limit=%d",
        profession_id, difficulty, is_active, skip, limit,
    )
    return CareerRoadmapService(db).list_roadmaps(
        profession_id=profession_id,
        difficulty=difficulty.value if difficulty else None,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )


@roadmap_router.get(
    "/{roadmap_id}",
    response_model=CareerRoadmapResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a career roadmap by ID",
    description=(
        "Retrieve the full career roadmap — including its ordered ``steps`` "
        "list — by UUID primary key."
    ),
    responses={
        200: {"description": "Roadmap found and returned."},
        404: {"description": "No roadmap with the given UUID exists."},
        422: {"description": "The provided ID is not a valid UUID."},
    },
)
def get_roadmap(
    roadmap_id: uuid.UUID,
    db: DbDep,
) -> CareerRoadmapResponse:
    """Retrieve a career roadmap by UUID.

    Args:
        roadmap_id: UUID of the roadmap.
        db: Injected database session.

    Returns:
        Full ``CareerRoadmapResponse`` including all steps.

    Raises:
        HTTPException 404: If no roadmap with the given ID exists.
    """
    logger.debug("GET /career-roadmaps/%s", roadmap_id)
    try:
        return CareerRoadmapService(db).get_roadmap(roadmap_id)
    except CareerRoadmapError as exc:
        _raise_http(exc)


@roadmap_router.patch(
    "/{roadmap_id}",
    response_model=CareerRoadmapResponse,
    status_code=status.HTTP_200_OK,
    summary="Partially update a career roadmap",
    description=(
        "Apply a partial update to an existing roadmap (PATCH semantics — "
        "only supplied fields are changed).\n\n"
        "**Title uniqueness:** if a new ``title`` is provided it must not "
        "already exist for this profession.\n\n"
        "**Immutable:** ``profession_id`` cannot be changed after creation."
    ),
    responses={
        200: {"description": "Roadmap updated successfully."},
        404: {"description": "Roadmap not found."},
        409: {"description": "New title conflicts with an existing roadmap for the profession."},
        422: {"description": "Request body failed schema validation."},
    },
)
def update_roadmap(
    roadmap_id: uuid.UUID,
    payload: CareerRoadmapUpdate,
    db: DbDep,
) -> CareerRoadmapResponse:
    """Partially update a career roadmap.

    Args:
        roadmap_id: UUID of the roadmap to update.
        payload: ``CareerRoadmapUpdate`` body (all fields optional).
        db: Injected database session.

    Returns:
        Updated ``CareerRoadmapResponse``.

    Raises:
        HTTPException 404: If the roadmap does not exist.
        HTTPException 409: If the new title conflicts.
    """
    logger.info("PATCH /career-roadmaps/%s", roadmap_id)
    try:
        return CareerRoadmapService(db).update_roadmap(roadmap_id, payload)
    except CareerRoadmapError as exc:
        _raise_http(exc)


@roadmap_router.delete(
    "/{roadmap_id}",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Delete a career roadmap",
    description=(
        "Permanently remove a career roadmap and **all its steps** "
        "(cascade-deleted via FK constraint).\n\n"
        "Returns a confirmation envelope with the deleted roadmap's ``id`` "
        "and ``title``."
    ),
    responses={
        200: {"description": "Roadmap deleted. Confirmation envelope returned."},
        404: {"description": "Roadmap not found."},
    },
)
def delete_roadmap(
    roadmap_id: uuid.UUID,
    db: DbDep,
) -> dict[str, Any]:
    """Hard-delete a career roadmap and all its steps.

    Args:
        roadmap_id: UUID of the roadmap to delete.
        db: Injected database session.

    Returns:
        Confirmation envelope::

            { "deleted": true, "id": "<uuid>", "title": "<title>" }

    Raises:
        HTTPException 404: If the roadmap does not exist.
    """
    logger.info("DELETE /career-roadmaps/%s", roadmap_id)
    try:
        return CareerRoadmapService(db).delete_roadmap(roadmap_id)
    except CareerRoadmapError as exc:
        _raise_http(exc)


# ═════════════════════════════════════════════════════════════════════════════
#  RoadmapStep endpoints
# ═════════════════════════════════════════════════════════════════════════════


@step_router.post(
    "/",
    response_model=RoadmapStepResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a step to a roadmap",
    description=(
        "Add a new step to an existing career roadmap.\n\n"
        "**Uniqueness constraints:**\n"
        "- ``step_order`` must be unique within the roadmap.\n"
        "- ``skill_id`` must appear **at most once** per roadmap.\n\n"
        "**Required fields:** ``roadmap_id``, ``skill_id``, ``step_order``.\n"
        "**Optional fields:** ``required``, ``estimated_hours``."
    ),
    responses={
        201: {"description": "Step created successfully."},
        404: {"description": "Referenced roadmap or skill not found."},
        409: {
            "description": (
                "step_order already taken in this roadmap, or "
                "skill already exists as a step."
            )
        },
        422: {"description": "Request body failed schema validation."},
    },
)
def create_step(
    payload: RoadmapStepCreate,
    db: DbDep,
) -> RoadmapStepResponse:
    """Add a new step to a career roadmap.

    Args:
        payload: Validated ``RoadmapStepCreate`` request body.
        db: Injected database session.

    Returns:
        Full ``RoadmapStepResponse`` for the newly created step.

    Raises:
        HTTPException 404: If the roadmap or skill does not exist.
        HTTPException 409: If the step_order or skill already exists in the roadmap.
    """
    logger.info(
        "POST /roadmap-steps | roadmap_id=%s | skill_id=%s | step_order=%d",
        payload.roadmap_id, payload.skill_id, payload.step_order,
    )
    try:
        return RoadmapStepService(db).create_step(payload)
    except CareerRoadmapError as exc:
        _raise_http(exc)


@step_router.get(
    "/",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="List roadmap steps",
    description=(
        "Return a paginated list of roadmap steps.  Use ``roadmap_id``, "
        "``skill_id``, and ``required`` to filter results.\n\n"
        "Results are ordered by ``step_order`` ascending — the natural "
        "traversal order of a roadmap.\n\n"
        "**Response shape:**\n"
        "```json\n"
        "{ \"items\": [...], \"total\": 10, \"skip\": 0, \"limit\": 100 }\n"
        "```"
    ),
    responses={
        200: {"description": "Paginated step list returned."},
    },
)
def list_steps(
    db: DbDep,
    roadmap_id: Annotated[
        Optional[uuid.UUID],
        Query(description="Filter to steps belonging to this roadmap UUID."),
    ] = None,
    skill_id: Annotated[
        Optional[uuid.UUID],
        Query(description="Filter to steps referencing this skill UUID."),
    ] = None,
    required: Annotated[
        Optional[bool],
        Query(description="Filter by required (true) or optional (false) steps."),
    ] = None,
    skip: Annotated[
        int,
        Query(ge=0, description="Pagination offset."),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=200, description="Maximum rows to return (1–200)."),
    ] = 100,
) -> dict[str, Any]:
    """List roadmap steps with optional filtering and pagination.

    Args:
        db: Injected database session.
        roadmap_id: Filter to one roadmap's steps.
        skill_id: Filter to steps using this skill.
        required: Filter by required/optional flag.
        skip: Pagination offset.
        limit: Max rows per page.

    Returns:
        Pagination envelope with ``items``, ``total``, ``skip``, ``limit``.
    """
    logger.debug(
        "GET /roadmap-steps | roadmap_id=%s | skill_id=%s | required=%s"
        " | skip=%d | limit=%d",
        roadmap_id, skill_id, required, skip, limit,
    )
    return RoadmapStepService(db).list_steps(
        roadmap_id=roadmap_id,
        skill_id=skill_id,
        required=required,
        skip=skip,
        limit=limit,
    )


@step_router.get(
    "/{step_id}",
    response_model=RoadmapStepResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a roadmap step by ID",
    description="Retrieve a full roadmap step record by its UUID primary key.",
    responses={
        200: {"description": "Step found and returned."},
        404: {"description": "No step with the given UUID exists."},
        422: {"description": "The provided ID is not a valid UUID."},
    },
)
def get_step(
    step_id: uuid.UUID,
    db: DbDep,
) -> RoadmapStepResponse:
    """Retrieve a roadmap step by UUID.

    Args:
        step_id: UUID of the step to retrieve.
        db: Injected database session.

    Returns:
        Full ``RoadmapStepResponse``.

    Raises:
        HTTPException 404: If no step with the given ID exists.
    """
    logger.debug("GET /roadmap-steps/%s", step_id)
    try:
        return RoadmapStepService(db).get_step(step_id)
    except CareerRoadmapError as exc:
        _raise_http(exc)


@step_router.patch(
    "/{step_id}",
    response_model=RoadmapStepResponse,
    status_code=status.HTTP_200_OK,
    summary="Partially update a roadmap step",
    description=(
        "Apply a partial update to a roadmap step (PATCH semantics).\n\n"
        "**Immutable:** ``roadmap_id`` and ``skill_id`` cannot be changed.\n\n"
        "If a new ``step_order`` is provided it must not conflict with "
        "another step in the same roadmap."
    ),
    responses={
        200: {"description": "Step updated successfully."},
        404: {"description": "Step not found."},
        409: {"description": "New step_order conflicts with an existing step."},
        422: {"description": "Request body failed schema validation."},
    },
)
def update_step(
    step_id: uuid.UUID,
    payload: RoadmapStepUpdate,
    db: DbDep,
) -> RoadmapStepResponse:
    """Partially update a roadmap step.

    Args:
        step_id: UUID of the step to update.
        payload: ``RoadmapStepUpdate`` body (all fields optional).
        db: Injected database session.

    Returns:
        Updated ``RoadmapStepResponse``.

    Raises:
        HTTPException 404: If the step does not exist.
        HTTPException 409: If the new step_order conflicts.
    """
    logger.info("PATCH /roadmap-steps/%s", step_id)
    try:
        return RoadmapStepService(db).update_step(step_id, payload)
    except CareerRoadmapError as exc:
        _raise_http(exc)


@step_router.delete(
    "/{step_id}",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Delete a roadmap step",
    description=(
        "Permanently remove a roadmap step.\n\n"
        "Returns a confirmation envelope with the deleted step's ``id``, "
        "``roadmap_id``, and ``step_order``."
    ),
    responses={
        200: {"description": "Step deleted. Confirmation envelope returned."},
        404: {"description": "Step not found."},
    },
)
def delete_step(
    step_id: uuid.UUID,
    db: DbDep,
) -> dict[str, Any]:
    """Hard-delete a roadmap step.

    Args:
        step_id: UUID of the step to delete.
        db: Injected database session.

    Returns:
        Confirmation envelope::

            {
                "deleted": true,
                "id": "<uuid>",
                "roadmap_id": "<uuid>",
                "step_order": 1
            }

    Raises:
        HTTPException 404: If the step does not exist.
    """
    logger.info("DELETE /roadmap-steps/%s", step_id)
    try:
        return RoadmapStepService(db).delete_step(step_id)
    except CareerRoadmapError as exc:
        _raise_http(exc)
