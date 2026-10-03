"""
Interview Agent HTTP route handlers.

Endpoints:
Internal (service-to-service, X-Internal-Token protected):
- POST /internal/interview/create-session — Idempotent interview session creation

Public (student-facing via API Gateway, X-Gateway-Token and X-User-Id protected):
- GET  /interview/sessions/{task_id}        — Fetch interview session status with lazy expiry
- POST /interview/sessions/{task_id}/start  — Start session & generate first question turn
- POST /interview/sessions/{task_id}/answer — Submit answer, persist, and generate next turn / complete
- GET  /interview/sessions/{task_id}/resume — Resume an in-progress session with turn history
"""

import hmac
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.interview import InterviewSessionStatus
from app.schemas.interview import (
    AnswerSubmissionResponse,
    InternalCreateSessionRequest,
    InterviewResumeResponse,
    InterviewSessionResponse,
    InterviewStartResponse,
    InterviewTurnResponse,
    ProctoringEventCreate,
    ProctoringEventResponse,
    ProctoringEventSubmissionResponse,
    SubmitAnswerRequest,
)
from app.services.session_service import (
    ProctoringRateLimitExceededError,
    SessionConflictError,
    SessionNotFoundError,
    SessionService,
    SessionServiceUnavailableError,
    get_session_service,
)

logger = logging.getLogger("interview-agent.routers")


def verify_internal_token(
    x_internal_token: Annotated[str | None, Header(alias="X-Internal-Token")] = None,
) -> None:
    """Verify shared internal service token using constant-time comparison."""
    if not x_internal_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Internal authentication required",
        )
    if not hmac.compare_digest(x_internal_token, settings.INTERNAL_SERVICE_TOKEN):
        logger.warning("Invalid internal token attempt on /internal/interview/*")
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
# Internal Endpoints (Exempt from Gateway Token, Requires Internal Token)
# ──────────────────────────────────────────────────────────────────────

internal_router = APIRouter(prefix="/internal/interview", tags=["Internal — Interview"])


@internal_router.post(
    "/create-session",
    response_model=InterviewSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="[Internal] Create or retrieve interview session for a completed task",
    description=(
        "Called by Agent 3 (evaluator-agent-service) upon successful code evaluation. "
        "Creates an interview session with status=AVAILABLE and a 24-hour expiration window. "
        "Idempotent: if a session already exists for this task_id, returns the existing record."
    ),
    dependencies=[Depends(verify_internal_token)],
)
async def create_session(
    body: InternalCreateSessionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[SessionService, Depends(get_session_service)],
) -> InterviewSessionResponse:
    """Idempotently create or return an interview session for a task."""
    session = await service.create_or_get_session(db=db, request=body)
    return InterviewSessionResponse.model_validate(session)


# ──────────────────────────────────────────────────────────────────────
# Public (User-Facing) Endpoints (Via API Gateway)
# ──────────────────────────────────────────────────────────────────────

public_router = APIRouter(prefix="/interview/sessions", tags=["Interview Sessions"])


@public_router.get(
    "/{task_id}",
    response_model=InterviewSessionResponse,
    summary="Get interview session details for a task",
    description=(
        "Fetches interview session for the specified task. Enforces user ownership "
        "(returns 404 if not found or belongs to another user). Applies lazy expiry "
        "if the 24-hour window has lapsed."
    ),
)
async def get_session(
    task_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[SessionService, Depends(get_session_service)],
) -> InterviewSessionResponse:
    """Return interview session for a task with lazy expiry check."""
    try:
        session = await service.get_session_by_task_id(db=db, task_id=task_id, user_id=user_id)
        return InterviewSessionResponse.model_validate(session)
    except SessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No interview session found for this task",
        )


@public_router.post(
    "/{task_id}/start",
    response_model=InterviewStartResponse,
    summary="Start an available interview session & generate first question",
    description=(
        "Transitions session status from AVAILABLE to IN_PROGRESS, records started_at, "
        "and generates the first dynamic technical question based on Agent 3 evaluation findings. "
        "Returns 409 Conflict if expired, already in progress, or already completed. "
        "Returns 503 and rolls back to AVAILABLE if first question generation fails."
    ),
)
async def start_session(
    task_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[SessionService, Depends(get_session_service)],
) -> InterviewStartResponse:
    """Start an interview session and return the first question turn."""
    try:
        session, first_turn = await service.start_session(db=db, task_id=task_id, user_id=user_id)
        session_resp = InterviewSessionResponse.model_validate(session)
        turn_resp = InterviewTurnResponse.model_validate(first_turn)

        return InterviewStartResponse(
            session=session_resp,
            first_question=turn_resp,
            id=session_resp.id,
            user_id=session_resp.user_id,
            task_id=session_resp.task_id,
            evaluation_id=session_resp.evaluation_id,
            status=session_resp.status,
            available_from=session_resp.available_from,
            expires_at=session_resp.expires_at,
            started_at=session_resp.started_at,
            completed_at=session_resp.completed_at,
            violation_count=session_resp.violation_count,
            termination_reason=session_resp.termination_reason,
            overall_performance_summary=session_resp.overall_performance_summary,
            created_at=session_resp.created_at,
            time_remaining_seconds=session_resp.time_remaining_seconds,
        )
    except SessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No interview session found for this task",
        )
    except SessionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except SessionServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )


@public_router.post(
    "/{task_id}/answer",
    response_model=AnswerSubmissionResponse,
    summary="Submit candidate answer to current question",
    description=(
        "Submits an answer for the current unanswered turn. Persists the answer, "
        "then generates the next question or closing turn. Returns 409 if no active "
        "unanswered turn exists or if the interview is not in progress. Returns 503 "
        "if next question generation fails (answer remains safely persisted in DB)."
    ),
)
async def submit_answer(
    task_id: uuid.UUID,
    body: SubmitAnswerRequest,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[SessionService, Depends(get_session_service)],
) -> AnswerSubmissionResponse:
    """Submit an answer to the current turn and generate the next question or concluding summary."""
    try:
        session, answered_turn, next_turn, is_closing = await service.submit_answer(
            db=db,
            task_id=task_id,
            user_id=user_id,
            request=body,
        )
        return AnswerSubmissionResponse(
            session=InterviewSessionResponse.model_validate(session),
            answered_turn=InterviewTurnResponse.model_validate(answered_turn),
            next_turn=InterviewTurnResponse.model_validate(next_turn),
            is_closing=is_closing,
            status=session.status,
            overall_performance_summary=session.overall_performance_summary,
        )
    except SessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No interview session found for this task",
        )
    except SessionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except SessionServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )


@public_router.get(
    "/{task_id}/resume",
    response_model=InterviewResumeResponse,
    summary="Resume an in-progress interview session",
    description=(
        "Returns the session and all completed turns so the frontend can reconstruct "
        "where the candidate left off. Only valid when status is IN_PROGRESS."
    ),
)
async def resume_session(
    task_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[SessionService, Depends(get_session_service)],
) -> InterviewResumeResponse:
    """Resume an in-progress interview session with turn history."""
    try:
        session, turns = await service.resume_session(db=db, task_id=task_id, user_id=user_id)
        session_resp = InterviewSessionResponse.model_validate(session)
        turn_resps = [InterviewTurnResponse.model_validate(t) for t in turns]

        return InterviewResumeResponse(
            session=session_resp,
            turns=turn_resps,
            id=session_resp.id,
            user_id=session_resp.user_id,
            task_id=session_resp.task_id,
            evaluation_id=session_resp.evaluation_id,
            status=session_resp.status,
            available_from=session_resp.available_from,
            expires_at=session_resp.expires_at,
            started_at=session_resp.started_at,
            completed_at=session_resp.completed_at,
            violation_count=session_resp.violation_count,
            termination_reason=session_resp.termination_reason,
            overall_performance_summary=session_resp.overall_performance_summary,
            created_at=session_resp.created_at,
            time_remaining_seconds=session_resp.time_remaining_seconds,
        )
    except SessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No interview session found for this task",
        )
    except SessionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@public_router.post(
    "/{task_id}/proctoring-event",
    response_model=ProctoringEventSubmissionResponse,
    status_code=status.HTTP_200_OK,
    summary="Record a client-side proctoring event and enforce violation policy",
    description=(
        "Records anti-cheat and integrity events (TAB_BLUR, FULLSCREEN_EXIT, etc.). "
        "Atomically increments the session violation count. If the violation count reaches "
        "the configured threshold (default 3), automatically transitions status to "
        "TERMINATED_VIOLATION and records termination reason and completion timestamp."
    ),
)
async def record_proctoring_event(
    task_id: uuid.UUID,
    body: ProctoringEventCreate,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[SessionService, Depends(get_session_service)],
) -> ProctoringEventSubmissionResponse:
    """Record a proctoring violation event and return violation count and status."""
    try:
        session, event, terminated = await service.record_proctoring_event(
            db=db,
            task_id=task_id,
            user_id=user_id,
            request=body,
        )
        return ProctoringEventSubmissionResponse(
            event=ProctoringEventResponse.model_validate(event),
            session_status=InterviewSessionStatus(session.status),
            violation_count=session.violation_count,
            max_violations=settings.PROCTORING_MAX_VIOLATIONS,
            terminated=terminated,
            termination_reason=session.termination_reason,
        )
    except SessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No interview session found for this task",
        )
    except SessionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except ProctoringRateLimitExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers={"Retry-After": str(exc.retry_after)},
        )

