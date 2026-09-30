"""
Evaluator API router — all endpoints for Agent 3.

Internal (X-Internal-Token protected, NOT routed via gateway):
- POST /internal/evaluate  — Trigger full evaluation pipeline (fire-and-forget)

Public (via gateway, JWT-protected):
- GET  /evaluations/{task_id}  — Student-facing evaluation result

Dev only (APP_ENV=development):
- POST /dev/evaluations/trigger/{task_id}  — Manual trigger for local testing
"""

import hmac
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.llm import get_llm_provider
from app.db.session import get_db
from app.schemas.evaluation import (
    CheckResultResponse,
    EvaluationResponse,
    TriggerEvaluationRequest,
)
from app.services.evaluator_service import EvaluationInProgressError, EvaluatorService

logger = logging.getLogger("evaluator-agent.router")


# ──────────────────────────────────────────────────────────────────────
# Shared Dependencies
# ──────────────────────────────────────────────────────────────────────

def get_evaluator_service() -> EvaluatorService:
    """Dependency providing a configured EvaluatorService instance."""
    provider = get_llm_provider()
    return EvaluatorService(llm_provider=provider)


def verify_internal_token(
    x_internal_token: Annotated[str | None, Header(alias="X-Internal-Token")] = None,
) -> None:
    """
    Verify the shared internal service token using constant-time comparison.

    Protects internal endpoints from external access.
    """
    if not x_internal_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Internal authentication required",
        )
    if not hmac.compare_digest(x_internal_token, settings.INTERNAL_SERVICE_TOKEN):
        logger.warning("Invalid internal token attempt on /internal/evaluate")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid internal authentication token",
        )


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


# ──────────────────────────────────────────────────────────────────────
# Internal Endpoints
# ──────────────────────────────────────────────────────────────────────

internal_router = APIRouter(prefix="/internal", tags=["Internal — Service-to-Service"])


@internal_router.post(
    "/evaluate",
    status_code=status.HTTP_200_OK,
    summary="[Internal] Trigger evaluation pipeline (fire-and-forget)",
    description=(
        "Called by roadmap-agent-service when a task is submitted. "
        "Creates an evaluation record and runs the full pipeline as a background task. "
        "Returns 200 OK immediately — the evaluation runs asynchronously. "
        "Returns 409 if an evaluation for this task is already IN_PROGRESS."
    ),
)
async def trigger_evaluation(
    body: TriggerEvaluationRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[EvaluatorService, Depends(get_evaluator_service)],
    _: Annotated[None, Depends(verify_internal_token)],
) -> dict:
    """Trigger a full evaluation pipeline for a submitted task."""
    try:
        evaluation = await service.trigger_evaluation(db=db, request=body)
        await db.commit()
    except EvaluationInProgressError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    # Fire-and-forget: background task runs after response is sent with its own DB session
    background_tasks.add_task(
        service.run_full_pipeline,
        evaluation_id=evaluation.id,
        request=body,
    )

    return {
        "message": "Evaluation started",
        "evaluation_id": str(evaluation.id),
        "task_id": str(body.task_id),
        "status": "IN_PROGRESS",
    }


# ──────────────────────────────────────────────────────────────────────
# Public (User-Facing) Endpoints
# ──────────────────────────────────────────────────────────────────────

public_router = APIRouter(prefix="/evaluations", tags=["Evaluations — Agent 3"])


@public_router.get(
    "/{task_id}",
    response_model=EvaluationResponse,
    summary="Get evaluation result for a task",
    description=(
        "Returns the latest evaluation for the specified task. "
        "User must own the task (user_id from JWT must match evaluation.user_id). "
        "Safe to call while evaluation is still IN_PROGRESS — status field indicates state. "
        "Does NOT expose internal red_flags (injection attempt details are internal-only)."
    ),
)
async def get_evaluation(
    task_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[EvaluatorService, Depends(get_evaluator_service)],
) -> EvaluationResponse:
    """Return the latest evaluation for a task (user-scoped)."""
    evaluation = await service.get_latest_evaluation(db=db, task_id=task_id, user_id=user_id)

    if evaluation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No evaluation found for task {task_id}.",
        )

    # Convert deterministic_checks to response schema (exclude gate check from student view)
    check_responses = None
    if evaluation.deterministic_checks:
        check_responses = [
            CheckResultResponse(**c)
            for c in evaluation.deterministic_checks
            if isinstance(c, dict) and c.get("check_name") != "repo_exists_and_public"
        ]

    # Extract safe LLM review fields (NOT red_flags — those are internal-only)
    llm = evaluation.llm_review or {}
    llm_strengths = llm.get("strengths") if llm else None
    llm_weaknesses = llm.get("weaknesses") if llm else None
    llm_suggestions = llm.get("suggestions") if llm else None
    # red_flags intentionally NOT included in response (injection attempt details are internal)

    return EvaluationResponse(
        id=evaluation.id,
        task_id=evaluation.task_id,
        user_id=evaluation.user_id,
        github_repo_url=evaluation.github_repo_url,
        status=evaluation.status,
        final_score=evaluation.final_score,
        passed=evaluation.passed,
        reuse_suspected=bool(getattr(evaluation, "reuse_suspected", False)),
        deterministic_score=evaluation.deterministic_score,
        deterministic_checks=check_responses,
        feedback_summary=evaluation.feedback_summary,
        llm_strengths=llm_strengths,
        llm_weaknesses=llm_weaknesses,
        llm_suggestions=llm_suggestions,
        error_detail=evaluation.error_detail if evaluation.status == "FAILED" else None,
        created_at=evaluation.created_at,
        completed_at=evaluation.completed_at,
    )


# ──────────────────────────────────────────────────────────────────────
# Dev-Only Endpoints
# ──────────────────────────────────────────────────────────────────────

dev_router = APIRouter(prefix="/dev", tags=["Dev Only — Testing"])


@dev_router.post(
    "/evaluations/trigger/{task_id}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="[DEV ONLY] Manually trigger evaluation for a task",
    description=(
        "Fires a manual evaluation trigger without requiring roadmap-agent-service "
        "to call /internal/evaluate. "
        "Only registered when APP_ENV=development. "
        "Requires github_repo_url and user_id as query parameters."
    ),
)
async def dev_trigger_evaluation(
    task_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[EvaluatorService, Depends(get_evaluator_service)],
    github_repo_url: str = "https://github.com/example/repo",
    user_id: str = "00000000-0000-0000-0000-000000000001",
    skills_targeted: str = "python,fastapi",
    task_started_at: str | None = None,
) -> dict:
    """[DEV ONLY] Manually trigger an evaluation for testing without going through the full flow."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid user_id UUID format",
        )

    skills = [s.strip() for s in skills_targeted.split(",") if s.strip()]

    request = TriggerEvaluationRequest(
        task_id=task_id,
        user_id=uid,
        github_repo_url=github_repo_url,
        task_started_at=task_started_at,
        skills_targeted=skills,
    )

    try:
        evaluation = await service.trigger_evaluation(db=db, request=request)
        await db.commit()
    except EvaluationInProgressError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    background_tasks.add_task(
        service.run_full_pipeline,
        evaluation_id=evaluation.id,
        request=request,
    )

    return {
        "message": "[DEV] Evaluation triggered",
        "evaluation_id": str(evaluation.id),
        "task_id": str(task_id),
        "github_repo_url": github_repo_url,
        "note": "Poll GET /evaluations/{task_id} to see results (user_id header required via gateway)",
    }
