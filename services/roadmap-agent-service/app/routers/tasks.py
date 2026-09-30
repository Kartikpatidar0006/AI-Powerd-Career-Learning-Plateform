"""
Task API router — handles the full task lifecycle.

Public (via gateway, JWT-protected):
- POST /tasks/next         — Get or generate the next task
- GET  /tasks/current      — Get active task
- GET  /tasks              — Task history (paginated)
- GET  /tasks/{id}         — Task detail
- POST /tasks/{id}/start   — ASSIGNED -> IN_PROGRESS
- POST /tasks/{id}/submit  — IN_PROGRESS/SUBMITTED -> SUBMITTED (with GitHub URL)

Internal (X-Internal-Token protected, NOT routed via gateway):
- POST /internal/tasks/{id}/evaluation — SUBMITTED -> EVALUATED (Agent 3 stub)

Dev only (APP_ENV=development):
- POST /dev/tasks/{id}/simulate-evaluation — Fake evaluation for testing
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.llm import (
    LLMProviderError,
    LLMTimeoutError,
    LLMValidationError,
    get_llm_provider,
)
from app.db.session import get_db
from app.schemas.roadmap import (
    EvaluationRequest,
    NextTaskResponse,
    SubmitTaskRequest,
    TaskListResponse,
    TaskResponse,
)
from app.services.roadmap_service import (
    ActiveTaskExistsError,
    DuplicateRepoUrlError,
    RoadmapNotFoundError,
    RoadmapService,
    TaskNotFoundError,
)
from app.services.state_machine import TaskTransitionError

logger = logging.getLogger("roadmap-agent.router.tasks")

router = APIRouter(prefix="/tasks", tags=["Tasks — Agent 2"])
internal_router = APIRouter(prefix="/internal", tags=["Internal — Service-to-Service"])


# ──────────────────────────────────────────────────────────────────────
# Shared Dependencies
# ──────────────────────────────────────────────────────────────────────

def get_current_user_id(
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> uuid.UUID:
    """Extract and validate authenticated user UUID from trusted gateway header."""
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
        )
    try:
        return uuid.UUID(x_user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identification header",
        )


def get_roadmap_service() -> RoadmapService:
    """Dependency providing a configured RoadmapService instance."""
    provider = get_llm_provider()
    return RoadmapService(llm_provider=provider)


def verify_internal_token(
    x_internal_token: Annotated[str | None, Header(alias="X-Internal-Token")] = None,
) -> None:
    """
    Verify the shared internal service token using constant-time comparison.
    
    Protects internal endpoints from external access.
    """
    import hmac
    if not x_internal_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Internal authentication required",
        )
    # hmac.compare_digest prevents timing attacks
    if not hmac.compare_digest(x_internal_token, settings.INTERNAL_SERVICE_TOKEN):
        logger.warning("Invalid internal token attempt on internal endpoint")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid internal authentication token",
        )


# ──────────────────────────────────────────────────────────────────────
# Public Task Endpoints
# ──────────────────────────────────────────────────────────────────────

@router.post(
    "/next",
    response_model=NextTaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Get the next task or check roadmap completion",
    description=(
        "Generates the next task for the current milestone if no active task exists. "
        "Difficulty is computed deterministically — the LLM never chooses it. "
        "Returns {'status': 'roadmap_completed'} when all milestones are done."
    ),
)
async def get_next_task(
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[RoadmapService, Depends(get_roadmap_service)],
) -> NextTaskResponse:
    """Generate and return the next task for the user."""
    logger.info("Received /tasks/next request for user %s", user_id)

    try:
        result = await service.generate_next_task(db=db, user_id=user_id)

        if result["status"] == "roadmap_completed":
            return NextTaskResponse(status="roadmap_completed", task=None)

        return NextTaskResponse(status="task_assigned", task=result["task"])

    except RoadmapNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except ActiveTaskExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.message,
        )
    except LLMTimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI Agent timed out generating your task. Please try again.",
        )
    except LLMValidationError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI Agent produced an invalid task after retry. Please try again.",
        )
    except LLMProviderError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is currently unavailable. Please try again later.",
        )
    except Exception as exc:
        logger.exception("Unexpected error in /tasks/next for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while generating your task.",
        )


@router.get(
    "/current",
    response_model=TaskResponse | None,
    summary="Get the current active task",
)
async def get_current_task(
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[RoadmapService, Depends(get_roadmap_service)],
) -> TaskResponse | None:
    """Return the user's current active task (ASSIGNED/IN_PROGRESS/SUBMITTED), or null."""
    task = await service.get_active_task(db=db, user_id=user_id)
    if task is None:
        return None
    return TaskResponse.model_validate(task)


@router.get(
    "",
    response_model=TaskListResponse,
    summary="Get task history (paginated)",
)
async def get_task_history(
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[RoadmapService, Depends(get_roadmap_service)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> TaskListResponse:
    """Return paginated task history for the authenticated user."""
    result = await service.get_task_history(
        db=db, user_id=user_id, page=page, page_size=page_size
    )
    return TaskListResponse(**result)


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Get task detail",
)
async def get_task_detail(
    task_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[RoadmapService, Depends(get_roadmap_service)],
) -> TaskResponse:
    """Return a specific task by ID — must belong to the requesting user."""
    try:
        task = await service.get_task_by_id(db=db, task_id=task_id, user_id=user_id)
        return TaskResponse.model_validate(task)
    except TaskNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found.",
        )


@router.post(
    "/{task_id}/start",
    response_model=TaskResponse,
    summary="Start a task (ASSIGNED -> IN_PROGRESS)",
)
async def start_task(
    task_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[RoadmapService, Depends(get_roadmap_service)],
) -> TaskResponse:
    """Mark a task as IN_PROGRESS."""
    try:
        task = await service.start_task(db=db, task_id=task_id, user_id=user_id)
        return TaskResponse.model_validate(task)
    except TaskNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found.")
    except TaskTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post(
    "/{task_id}/submit",
    response_model=TaskResponse,
    summary="Submit task with GitHub URL (IN_PROGRESS/SUBMITTED -> SUBMITTED)",
    description=(
        "Validates the GitHub URL strictly (https://github.com/<owner>/<repo>), "
        "normalizes it, and records submission. Re-submission is allowed while SUBMITTED "
        "(before evaluation) to allow students to fix a wrong URL."
    ),
)
async def submit_task(
    task_id: uuid.UUID,
    body: SubmitTaskRequest,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[RoadmapService, Depends(get_roadmap_service)],
) -> TaskResponse:
    """Submit a task with a GitHub repository URL."""
    from app.services.github_validator import validate_github_url
    from app.services.evaluator_client import EvaluatorClient

    is_valid, error_msg, normalized_url = validate_github_url(body.github_repo_url)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid GitHub URL: {error_msg}",
        )

    try:
        task = await service.submit_task(
            db=db,
            task_id=task_id,
            user_id=user_id,
            github_repo_url=normalized_url,
        )
    except TaskNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found.")
    except (TaskTransitionError, DuplicateRepoUrlError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    # Fire-and-forget: trigger Agent 3 (evaluator-agent-service) asynchronously.
    # We do NOT await — the student gets their response immediately.
    # If the trigger fails, task remains SUBMITTED and can be re-triggered.
    import asyncio

    async def _trigger() -> None:
        evaluator = EvaluatorClient()
        started_at_str = task.started_at.isoformat() if task.started_at else None
        skills = list(task.skills_targeted) if task.skills_targeted else []
        await evaluator.trigger_evaluation(
            task_id=task.id,
            user_id=task.user_id,
            github_repo_url=normalized_url,
            task_started_at=started_at_str,
            skills_targeted=skills,
        )

    asyncio.create_task(_trigger())
    logger.info("Task %s submitted — evaluation trigger fired (fire-and-forget)", task_id)

    return TaskResponse.model_validate(task)


# ──────────────────────────────────────────────────────────────────────
# Internal Endpoints (Agent 3 ↔ Agent 2 callbacks)
# ──────────────────────────────────────────────────────────────────────

@internal_router.post(
    "/tasks/{task_id}/claim-evaluation",
    response_model=TaskResponse,
    summary="[Internal] Claim task for evaluation (SUBMITTED -> EVALUATING)",
    description=(
        "Called by Agent 3 evaluator worker to claim a submitted task for evaluation. "
        "Transitions SUBMITTED -> EVALUATING. Protected by X-Internal-Token."
    ),
)
async def claim_evaluation(
    task_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[RoadmapService, Depends(get_roadmap_service)],
    _: Annotated[None, Depends(verify_internal_token)],
) -> TaskResponse:
    """Claim a task for evaluation."""
    try:
        task = await service.claim_evaluation(db=db, task_id=task_id)
        return TaskResponse.model_validate(task)
    except TaskNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found.")
    except TaskTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@internal_router.post(
    "/tasks/{task_id}/fail-evaluation",
    response_model=TaskResponse,
    summary="[Internal] Rollback evaluation on evaluator failure (EVALUATING -> SUBMITTED)",
    description=(
        "Called by Agent 3 if evaluator crashes/fails to reset task to SUBMITTED state. "
        "Protected by X-Internal-Token."
    ),
)
async def fail_evaluation(
    task_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[RoadmapService, Depends(get_roadmap_service)],
    _: Annotated[None, Depends(verify_internal_token)],
) -> TaskResponse:
    """Rollback task status on evaluator failure."""
    try:
        task = await service.fail_evaluation(db=db, task_id=task_id)
        return TaskResponse.model_validate(task)
    except TaskNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found.")
    except TaskTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@internal_router.post(
    "/tasks/{task_id}/evaluation",
    response_model=TaskResponse,
    summary="[Internal] Apply evaluation result (EVALUATING -> EVALUATED)",
    description=(
        "Called by Agent 3 after code review. Protected by X-Internal-Token. "
        "Not routed through the API gateway. This is a stub for Week 4."
    ),
)
async def apply_evaluation(
    task_id: uuid.UUID,
    body: EvaluationRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[RoadmapService, Depends(get_roadmap_service)],
    _: Annotated[None, Depends(verify_internal_token)],
) -> TaskResponse:
    """Apply evaluation summary from Agent 3 and transition task to EVALUATED."""
    try:
        task = await service.apply_evaluation(
            db=db,
            task_id=task_id,
            evaluation_summary=body.model_dump(),
        )
        return TaskResponse.model_validate(task)
    except TaskNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found.")
    except TaskTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


# ──────────────────────────────────────────────────────────────────────
# Dev-Only Endpoints (APP_ENV=development only)
# ──────────────────────────────────────────────────────────────────────

dev_router = APIRouter(prefix="/dev", tags=["Dev Only — Simulation"])


@dev_router.post(
    "/tasks/{task_id}/simulate-evaluation",
    response_model=TaskResponse,
    summary="[DEV ONLY] Simulate evaluation to close the full loop",
    description=(
        "Forces a task to EVALUATED status with simulated evaluation data. "
        "Only registered when APP_ENV=development. "
        "Use this to test the full task lifecycle without Agent 3."
    ),
)
async def simulate_evaluation(
    task_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[RoadmapService, Depends(get_roadmap_service)],
    score: float = Query(default=85.0, ge=0.0, le=100.0),
    feedback: str | None = Query(default=None),
) -> TaskResponse:
    """Simulate an evaluation result for testing the full task loop."""
    fake_summary = {
        "score": score,
        "feedback": feedback or (
            "[SIMULATED] Task completed successfully. All acceptance criteria met."
            if score >= settings.PASS_SCORE
            else "[SIMULATED] Task failed acceptance criteria. Needs remediation on milestone skills."
        ),
        "criteria_results": [
            {"criterion": "Acceptance criterion 1", "passed": score >= settings.PASS_SCORE},
            {"criterion": "Acceptance criterion 2", "passed": score >= settings.PASS_SCORE},
        ],
        "passed": score >= settings.PASS_SCORE,
        "evaluated_by": "simulate-evaluation-dev",
        "simulated": True,
    }

    try:
        task = await service.apply_evaluation(
            db=db,
            task_id=task_id,
            evaluation_summary=fake_summary,
        )
        return TaskResponse.model_validate(task)
    except TaskNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found.")
    except TaskTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot simulate evaluation: {exc}",
        )
