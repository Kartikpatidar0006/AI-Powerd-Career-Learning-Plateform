"""
backend/app/api/v1/tasks/router.py
=====================================
FastAPI router for the Task Engine.

Endpoints
---------
  POST   /api/v1/tasks/                          Create a new task.
  GET    /api/v1/tasks/                          List tasks (paginated + filtered).
  GET    /api/v1/tasks/my-submissions            Current user's submissions (auth).
  GET    /api/v1/tasks/by-step/{roadmap_step_id} Tasks for a specific roadmap step.
  GET    /api/v1/tasks/{task_id}                 Get a task by UUID.
  PATCH  /api/v1/tasks/{task_id}                 Partially update a task.
  DELETE /api/v1/tasks/{task_id}                 Delete a task.
  POST   /api/v1/tasks/{task_id}/submit          Submit work for a task (auth).

Query-parameter filters for GET /api/v1/tasks/
  roadmap_step_id — limit to one roadmap step's tasks.
  difficulty      — 'Easy' | 'Medium' | 'Hard'.
  is_active       — boolean visibility filter.
  skip / limit    — standard offset pagination.

Architecture contract
---------------------
  ✓ Delegates all business logic to ``TaskService`` / ``TaskSubmissionService``.
  ✓ Maps ``TaskError`` domain exceptions to ``HTTPException`` via a
    lookup table — no scattered ``if/elif`` chains.
  ✗ No raw SQL, no password/JWT handling, no schema validation beyond DI.

Error code → HTTP status
------------------------
  not_found          → 404 Not Found
  step_not_found     → 404 Not Found
  already_submitted  → 409 Conflict
  submission_not_found → 404 Not Found
  task_inactive      → 403 Forbidden
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.auth.router import get_current_user
from app.db.session import get_db
from app.schemas.task import (
    TaskCreate,
    TaskListResponse,
    TaskResponse,
    TaskSubmissionCreate,
    TaskSubmissionListResponse,
    TaskSubmissionResponse,
    TaskUpdate,
)
from app.schemas.user import UserResponse
from app.services.task import TaskError, TaskService, TaskSubmissionService

logger: logging.Logger = logging.getLogger(__name__)

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Error code → HTTP status mapping
# ─────────────────────────────────────────────────────────────────────────────

_TASK_ERROR_STATUS: dict[str, int] = {
    TaskError.NOT_FOUND:            status.HTTP_404_NOT_FOUND,
    TaskError.STEP_NOT_FOUND:       status.HTTP_404_NOT_FOUND,
    TaskError.ALREADY_SUBMITTED:    status.HTTP_409_CONFLICT,
    TaskError.SUBMISSION_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    TaskError.TASK_INACTIVE:        status.HTTP_403_FORBIDDEN,
}


def _raise_http(exc: TaskError) -> None:
    """Convert a ``TaskError`` into an ``HTTPException`` and raise it.

    Falls back to 500 for any unknown code, logging at ERROR level so that
    unmapped codes are caught in monitoring before they reach users.

    Args:
        exc: The domain exception raised by ``TaskService``.

    Raises:
        HTTPException: Always — never returns normally.
    """
    http_status = _TASK_ERROR_STATUS.get(
        exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR
    )
    if http_status == status.HTTP_500_INTERNAL_SERVER_ERROR:
        logger.error(
            "Unmapped TaskError code '%s' fell through to 500: %s",
            exc.code, exc.message,
        )
    raise HTTPException(status_code=http_status, detail=exc.message)


# ─────────────────────────────────────────────────────────────────────────────
# Dependency aliases
# ─────────────────────────────────────────────────────────────────────────────

DbDep = Annotated[Session, Depends(get_db)]
CurrentUserDep = Annotated[UserResponse, Depends(get_current_user)]


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new task",
    description=(
        "Create a new task linked to a roadmap step.  The referenced "
        "``roadmap_step_id`` must exist.\n\n"
        "### Error responses\n\n"
        "| Code | Meaning |\n"
        "|------|--------|\n"
        "| 404  | Roadmap step not found |\n"
        "| 422  | Validation error |"
    ),
    responses={
        201: {"description": "Task created successfully."},
        404: {"description": "Referenced roadmap step not found."},
        422: {"description": "Validation error in request body."},
    },
)
def create_task(
    payload: TaskCreate,
    db: DbDep,
) -> TaskResponse:
    """Create a new task.

    Args:
        payload: Validated ``TaskCreate`` schema.
        db: Injected database session.

    Returns:
        The created ``TaskResponse``.

    Raises:
        HTTPException 404: If the roadmap step does not exist.
    """
    logger.info("POST /tasks/ | title=%s", payload.title)
    try:
        task = TaskService(db).create(payload)
        return TaskResponse.model_validate(task)
    except TaskError as exc:
        _raise_http(exc)


@router.get(
    "/",
    response_model=TaskListResponse,
    status_code=status.HTTP_200_OK,
    summary="List tasks",
    description=(
        "Return a paginated, filtered list of tasks.\n\n"
        "### Available filters\n"
        "- ``roadmap_step_id`` — limit to tasks under one roadmap step.\n"
        "- ``difficulty`` — ``Easy``, ``Medium``, or ``Hard``.\n"
        "- ``is_active`` — filter by visibility.\n"
        "- ``skip`` / ``limit`` — standard offset pagination."
    ),
    responses={
        200: {"description": "Paginated task list returned."},
    },
)
def list_tasks(
    db: DbDep,
    roadmap_step_id: Optional[uuid.UUID] = Query(
        None, description="Filter by parent roadmap step UUID.",
    ),
    difficulty: Optional[str] = Query(
        None, description="Filter by difficulty: Easy, Medium, Hard.",
    ),
    is_active: Optional[bool] = Query(
        None, description="Filter by visibility flag.",
    ),
    skip: int = Query(0, ge=0, description="Offset for pagination."),
    limit: int = Query(20, ge=1, le=100, description="Max results."),
) -> TaskListResponse:
    """List tasks with optional filtering.

    Args:
        db: Injected database session.
        roadmap_step_id: Optional filter by roadmap step.
        difficulty: Optional filter by difficulty.
        is_active: Optional filter by visibility.
        skip: Pagination offset.
        limit: Pagination limit.

    Returns:
        ``TaskListResponse`` with items, total, skip, and limit.
    """
    logger.info(
        "GET /tasks/ | step=%s difficulty=%s active=%s skip=%d limit=%d",
        roadmap_step_id, difficulty, is_active, skip, limit,
    )
    tasks, total = TaskService(db).list_tasks(
        roadmap_step_id=roadmap_step_id,
        difficulty=difficulty,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )
    return TaskListResponse(
        items=[TaskResponse.model_validate(t) for t in tasks],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/my-submissions",
    response_model=TaskSubmissionListResponse,
    status_code=status.HTTP_200_OK,
    summary="Current user's submissions",
    description=(
        "Return a paginated list of the authenticated user's task submissions.\n\n"
        "**Requires authentication** — send a valid ``Bearer`` token in the "
        "``Authorization`` header."
    ),
    responses={
        200: {"description": "User's submissions returned."},
        401: {"description": "Not authenticated."},
    },
)
def get_my_submissions(
    db: DbDep,
    current_user: CurrentUserDep,
    skip: int = Query(0, ge=0, description="Offset for pagination."),
    limit: int = Query(20, ge=1, le=100, description="Max results."),
) -> TaskSubmissionListResponse:
    """List the current user's task submissions.

    Args:
        db: Injected database session.
        current_user: Authenticated user (injected via ``get_current_user``).
        skip: Pagination offset.
        limit: Pagination limit.

    Returns:
        ``TaskSubmissionListResponse`` with items, total, skip, and limit.
    """
    logger.info("GET /tasks/my-submissions | user=%s", current_user.id)
    items, total = TaskSubmissionService(db).list_user_submissions(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    return TaskSubmissionListResponse(
        items=[TaskSubmissionResponse.model_validate(s) for s in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/by-step/{roadmap_step_id}",
    response_model=TaskListResponse,
    status_code=status.HTTP_200_OK,
    summary="Tasks for a roadmap step",
    description=(
        "Return active tasks belonging to a specific roadmap step.\n\n"
        "### Error responses\n\n"
        "| Code | Meaning |\n"
        "|------|--------|\n"
        "| 404  | Roadmap step not found |\n"
        "| 422  | Invalid UUID format |"
    ),
    responses={
        200: {"description": "Tasks for the step returned."},
        404: {"description": "Roadmap step not found."},
        422: {"description": "Path parameter is not a valid UUID."},
    },
)
def get_tasks_by_step(
    roadmap_step_id: uuid.UUID,
    db: DbDep,
    skip: int = Query(0, ge=0, description="Offset for pagination."),
    limit: int = Query(20, ge=1, le=100, description="Max results."),
) -> TaskListResponse:
    """List active tasks for a specific roadmap step.

    Args:
        roadmap_step_id: UUID of the parent RoadmapStep.
        db: Injected database session.
        skip: Pagination offset.
        limit: Pagination limit.

    Returns:
        ``TaskListResponse`` with active tasks for the step.

    Raises:
        HTTPException 404: If the roadmap step does not exist.
    """
    logger.info("GET /tasks/by-step/%s", roadmap_step_id)
    try:
        tasks, total = TaskService(db).list_by_step(
            roadmap_step_id=roadmap_step_id,
            skip=skip,
            limit=limit,
        )
        return TaskListResponse(
            items=[TaskResponse.model_validate(t) for t in tasks],
            total=total,
            skip=skip,
            limit=limit,
        )
    except TaskError as exc:
        _raise_http(exc)


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a task by UUID",
    description=(
        "Return the full details of a single task.\n\n"
        "### Error responses\n\n"
        "| Code | Meaning |\n"
        "|------|--------|\n"
        "| 404  | Task not found |\n"
        "| 422  | Invalid UUID format |"
    ),
    responses={
        200: {"description": "Task returned successfully."},
        404: {"description": "Task not found."},
        422: {"description": "Path parameter is not a valid UUID."},
    },
)
def get_task(
    task_id: uuid.UUID,
    db: DbDep,
) -> TaskResponse:
    """Get a task by UUID.

    Args:
        task_id: UUID of the task.
        db: Injected database session.

    Returns:
        ``TaskResponse`` for the requested task.

    Raises:
        HTTPException 404: If no task with this UUID exists.
    """
    logger.info("GET /tasks/%s", task_id)
    try:
        task = TaskService(db).get_by_id(task_id)
        return TaskResponse.model_validate(task)
    except TaskError as exc:
        _raise_http(exc)


@router.patch(
    "/{task_id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Partially update a task",
    description=(
        "Update one or more fields of an existing task.  Only fields "
        "present in the request body are modified — omitted fields remain "
        "unchanged (PATCH semantics).\n\n"
        "### Error responses\n\n"
        "| Code | Meaning |\n"
        "|------|--------|\n"
        "| 404  | Task not found |\n"
        "| 422  | Validation error |"
    ),
    responses={
        200: {"description": "Task updated successfully."},
        404: {"description": "Task not found."},
        422: {"description": "Validation error in request body."},
    },
)
def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    db: DbDep,
) -> TaskResponse:
    """Partially update a task.

    Args:
        task_id: UUID of the task to update.
        payload: Validated ``TaskUpdate`` schema.
        db: Injected database session.

    Returns:
        The updated ``TaskResponse``.

    Raises:
        HTTPException 404: If the task does not exist.
    """
    logger.info("PATCH /tasks/%s", task_id)
    try:
        task = TaskService(db).update(task_id, payload)
        return TaskResponse.model_validate(task)
    except TaskError as exc:
        _raise_http(exc)


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task",
    description=(
        "Hard-delete a task and all its submissions.\n\n"
        "### Error responses\n\n"
        "| Code | Meaning |\n"
        "|------|--------|\n"
        "| 404  | Task not found |"
    ),
    responses={
        204: {"description": "Task deleted."},
        404: {"description": "Task not found."},
    },
)
def delete_task(
    task_id: uuid.UUID,
    db: DbDep,
) -> None:
    """Delete a task and its submissions.

    Args:
        task_id: UUID of the task to delete.
        db: Injected database session.

    Raises:
        HTTPException 404: If the task does not exist.
    """
    logger.info("DELETE /tasks/%s", task_id)
    try:
        TaskService(db).delete(task_id)
    except TaskError as exc:
        _raise_http(exc)


@router.post(
    "/{task_id}/submit",
    response_model=TaskSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit work for a task",
    description=(
        "Submit deliverables (GitHub URL, text answer, or file) for a task.\n\n"
        "**Requires authentication** — send a valid ``Bearer`` token.\n\n"
        "At least one of ``github_url``, ``submission_text``, or ``file_url`` "
        "must be provided.\n\n"
        "If the user has already submitted for this task, the existing "
        "submission is updated with the new deliverables and the status is "
        "reset to ``Submitted``.\n\n"
        "### Error responses\n\n"
        "| Code | Meaning |\n"
        "|------|--------|\n"
        "| 401  | Not authenticated |\n"
        "| 403  | Task is inactive |\n"
        "| 404  | Task not found |\n"
        "| 422  | Validation error |"
    ),
    responses={
        201: {"description": "Submission created or updated."},
        401: {"description": "Not authenticated."},
        403: {"description": "Task is inactive."},
        404: {"description": "Task not found."},
        422: {"description": "Validation error in request body."},
    },
)
def submit_task(
    task_id: uuid.UUID,
    payload: TaskSubmissionCreate,
    db: DbDep,
    current_user: CurrentUserDep,
) -> TaskSubmissionResponse:
    """Submit work for a task.

    Creates a new submission or updates an existing one if the user has
    already submitted for this task.

    Args:
        task_id: UUID of the task to submit.
        payload: Validated ``TaskSubmissionCreate`` schema.
        db: Injected database session.
        current_user: Authenticated user.

    Returns:
        The created or updated ``TaskSubmissionResponse``.

    Raises:
        HTTPException 401: If not authenticated.
        HTTPException 403: If the task is inactive.
        HTTPException 404: If the task does not exist.
    """
    logger.info("POST /tasks/%s/submit | user=%s", task_id, current_user.id)
    try:
        submission = TaskSubmissionService(db).submit(
            user_id=current_user.id,
            task_id=task_id,
            payload=payload,
        )
        return TaskSubmissionResponse.model_validate(submission)
    except TaskError as exc:
        _raise_http(exc)
