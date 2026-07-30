"""
backend/app/api/v1/interviews/router.py
=========================================
FastAPI router for the Interview Scheduling & Mock Interview Engine.

Endpoints
---------
  POST  /api/v1/interviews/schedule/{task_id}  Automatically schedule an interview.
  GET   /api/v1/interviews/me                  List user's interviews (auth).
  GET   /api/v1/interviews/{interview_id}      Get interview details (auth).
  PATCH /api/v1/interviews/{interview_id}/cancel Cancel an interview (auth).
  POST  /api/v1/interviews/{interview_id}/start  Start an interview session & generate 5 questions.
  GET   /api/v1/interviews/{interview_id}/questions Get ordered questions for an interview.
  POST  /api/v1/interviews/{interview_id}/finish Mark interview as completed.
  POST  /api/v1/interviews/questions/{question_id}/answer Submit student answer for a question.

Architecture contract
---------------------
  ✓ Delegates logic to ``InterviewSchedulerService``, ``InterviewService``, and ``MockInterviewEngineService``.
  ✓ Maps ``InterviewError`` domain exceptions to ``HTTPException``.
  ✓ Enforces authentication via ``get_current_user``.
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.auth.router import get_current_user
from app.db.session import get_db
from app.schemas.interview import InterviewListResponse, InterviewResponse
from app.schemas.interview_feedback import (
    InterviewFeedbackListResponse,
    InterviewFeedbackResponse,
)
from app.schemas.interview_question import (
    InterviewAnswerCreate,
    InterviewAnswerResponse,
    InterviewQuestionListResponse,
    InterviewQuestionResponse,
    InterviewStartResponse,
)
from app.schemas.user import UserResponse
from app.services.interview import (
    InterviewError,
    InterviewSchedulerService,
    InterviewService,
)
from app.services.interview_engine import MockInterviewEngineService
from app.services.interview_evaluation import InterviewEvaluationService

logger: logging.Logger = logging.getLogger(__name__)

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Error code → HTTP status mapping
# ─────────────────────────────────────────────────────────────────────────────

_INTERVIEW_ERROR_STATUS: dict[str, int] = {
    InterviewError.TASK_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    InterviewError.SUBMISSION_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    InterviewError.NOT_ELIGIBLE: status.HTTP_400_BAD_REQUEST,
    InterviewError.ALREADY_SCHEDULED: status.HTTP_409_CONFLICT,
    InterviewError.INTERVIEW_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    InterviewError.UNAUTHORIZED: status.HTTP_403_FORBIDDEN,
}


def _raise_http(exc: InterviewError) -> None:
    """Convert an ``InterviewError`` into an ``HTTPException`` and raise it.

    Args:
        exc: The domain exception.

    Raises:
        HTTPException: Always.
    """
    http_status = _INTERVIEW_ERROR_STATUS.get(
        exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR
    )
    if http_status == status.HTTP_500_INTERNAL_SERVER_ERROR:
        logger.error(
            "Unmapped InterviewError code '%s' fell through to 500: %s",
            exc.code,
            exc.message,
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
    "/schedule/{task_id}",
    response_model=InterviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Schedule an interview for a task",
    description=(
        "Automatically schedule a 10-minute interview for a task if eligible.\n\n"
        "**Eligibility requirements**:\n"
        "- Learner submitted work for the task.\n"
        "- Task evaluation is complete (`status == 'Generated'`).\n"
        "- `overall_score` is 70% or higher.\n\n"
        "### Error responses\n\n"
        "| Code | Meaning |\n"
        "|------|--------|\n"
        "| 400  | Not eligible (missing feedback or score < 70) |\n"
        "| 401  | Not authenticated |\n"
        "| 404  | Task or submission not found |\n"
        "| 409  | Active interview already scheduled |"
    ),
    responses={
        201: {"description": "Interview scheduled successfully."},
        400: {"description": "Not eligible for interview."},
        401: {"description": "Not authenticated."},
        404: {"description": "Task or submission not found."},
        409: {"description": "Active interview already scheduled."},
    },
)
def schedule_interview(
    task_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUserDep,
) -> InterviewResponse:
    """Schedule an interview for a task.

    Args:
        task_id: UUID of the task.
        db: Injected database session.
        current_user: Authenticated user.

    Returns:
        The scheduled ``InterviewResponse``.

    Raises:
        HTTPException: 400 if ineligible, 404 if missing, 409 if duplicate.
    """
    logger.info("POST /interviews/schedule/%s | user=%s", task_id, current_user.id)
    try:
        interview = InterviewSchedulerService(db).schedule_interview(
            task_id=task_id,
            user_id=current_user.id,
        )
        return InterviewResponse.model_validate(interview)
    except InterviewError as exc:
        _raise_http(exc)


@router.get(
    "/me",
    response_model=InterviewListResponse,
    status_code=status.HTTP_200_OK,
    summary="List logged-in user's interviews",
    description=(
        "Return a paginated list of interviews scheduled for the authenticated user.\n\n"
        "**Requires authentication**."
    ),
    responses={
        200: {"description": "User interviews returned."},
        401: {"description": "Not authenticated."},
    },
)
def get_my_interviews(
    db: DbDep,
    current_user: CurrentUserDep,
    skip: int = Query(0, ge=0, description="Offset for pagination."),
    limit: int = Query(20, ge=1, le=100, description="Max results."),
) -> InterviewListResponse:
    """List interviews for the authenticated user.

    Args:
        db: Injected database session.
        current_user: Authenticated user.
        skip: Pagination offset.
        limit: Pagination limit.

    Returns:
        ``InterviewListResponse``.
    """
    logger.info("GET /interviews/me | user=%s", current_user.id)
    items, total = InterviewService(db).list_user_interviews(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    return InterviewListResponse(
        items=[InterviewResponse.model_validate(i) for i in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{interview_id}",
    response_model=InterviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Get interview details",
    description=(
        "Retrieve details for a specific scheduled interview.\n\n"
        "**Requires authentication** — user must own the interview.\n\n"
        "### Error responses\n\n"
        "| Code | Meaning |\n"
        "|------|--------|\n"
        "| 401  | Not authenticated |\n"
        "| 403  | Interview belongs to another user |\n"
        "| 404  | Interview not found |"
    ),
    responses={
        200: {"description": "Interview details returned."},
        401: {"description": "Not authenticated."},
        403: {"description": "Interview belongs to another user."},
        404: {"description": "Interview not found."},
    },
)
def get_interview(
    interview_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUserDep,
) -> InterviewResponse:
    """Get details for a specific interview.

    Args:
        interview_id: UUID of the interview.
        db: Injected database session.
        current_user: Authenticated user.

    Returns:
        The ``InterviewResponse``.

    Raises:
        HTTPException: 403 if unauthorized, 404 if missing.
    """
    logger.info("GET /interviews/%s | user=%s", interview_id, current_user.id)
    try:
        interview = InterviewService(db).get_by_id(
            interview_id=interview_id,
            user_id=current_user.id,
        )
        return InterviewResponse.model_validate(interview)
    except InterviewError as exc:
        _raise_http(exc)


@router.patch(
    "/{interview_id}/cancel",
    response_model=InterviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel a scheduled interview",
    description=(
        "Cancel a scheduled interview session.\n\n"
        "**Requires authentication** — user must own the interview.\n\n"
        "### Error responses\n\n"
        "| Code | Meaning |\n"
        "|------|--------|\n"
        "| 401  | Not authenticated |\n"
        "| 403  | Interview belongs to another user |\n"
        "| 404  | Interview not found |"
    ),
    responses={
        200: {"description": "Interview cancelled successfully."},
        401: {"description": "Not authenticated."},
        403: {"description": "Interview belongs to another user."},
        404: {"description": "Interview not found."},
    },
)
def cancel_interview(
    interview_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUserDep,
) -> InterviewResponse:
    """Cancel a scheduled interview.

    Args:
        interview_id: UUID of the interview to cancel.
        db: Injected database session.
        current_user: Authenticated user.

    Returns:
        The updated ``InterviewResponse``.

    Raises:
        HTTPException: 403 if unauthorized, 404 if missing.
    """
    logger.info("PATCH /interviews/%s/cancel | user=%s", interview_id, current_user.id)
    try:
        interview = InterviewService(db).cancel_interview(
            interview_id=interview_id,
            user_id=current_user.id,
        )
        return InterviewResponse.model_validate(interview)
    except InterviewError as exc:
        _raise_http(exc)


# ─────────────────────────────────────────────────────────────────────────────
# Mock Interview Engine Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/{interview_id}/start",
    response_model=InterviewStartResponse,
    status_code=status.HTTP_200_OK,
    summary="Start an interview session",
    description=(
        "Start an interview session. Generates 5 dummy interview questions (3 Technical, "
        "2 Behavioral) if they do not exist for this interview.\n\n"
        "**Business rule**: An interview can ONLY be started if status == 'Scheduled'.\n\n"
        "### Error responses\n\n"
        "| Code | Meaning |\n"
        "|------|--------|\n"
        "| 400  | Interview status is not Scheduled (e.g. Completed/Cancelled) |\n"
        "| 401  | Not authenticated |\n"
        "| 403  | Interview belongs to another user |\n"
        "| 404  | Interview not found |"
    ),
    responses={
        200: {"description": "Interview started and questions returned."},
        400: {"description": "Interview status is invalid for starting."},
        401: {"description": "Not authenticated."},
        403: {"description": "Interview belongs to another user."},
        404: {"description": "Interview not found."},
    },
)
def start_interview(
    interview_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUserDep,
) -> InterviewStartResponse:
    """Start an interview session and generate/retrieve questions.

    Args:
        interview_id: UUID of the interview.
        db: Injected database session.
        current_user: Authenticated user.

    Returns:
        ``InterviewStartResponse`` with interview ID, status, and questions.

    Raises:
        HTTPException: 400 if invalid status, 403 if unauthorized, 404 if missing.
    """
    logger.info("POST /interviews/%s/start | user=%s", interview_id, current_user.id)
    try:
        interview, questions = MockInterviewEngineService(db).start_interview(
            interview_id=interview_id,
            user_id=current_user.id,
        )
        return InterviewStartResponse(
            interview_id=interview.id,
            status=interview.status,
            questions=[InterviewQuestionResponse.model_validate(q) for q in questions],
        )
    except InterviewError as exc:
        _raise_http(exc)


@router.get(
    "/{interview_id}/questions",
    response_model=InterviewQuestionListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get ordered questions for an interview",
    description=(
        "Retrieve all interview questions in order sequence (`order_no` ASC).\n\n"
        "**Requires authentication** — user must own the interview."
    ),
    responses={
        200: {"description": "Ordered questions returned."},
        401: {"description": "Not authenticated."},
        403: {"description": "Interview belongs to another user."},
        404: {"description": "Interview not found."},
    },
)
def get_interview_questions(
    interview_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUserDep,
) -> InterviewQuestionListResponse:
    """Get questions for an interview in order sequence.

    Args:
        interview_id: UUID of interview.
        db: Injected database session.
        current_user: Authenticated user.

    Returns:
        ``InterviewQuestionListResponse``.
    """
    logger.info("GET /interviews/%s/questions | user=%s", interview_id, current_user.id)
    try:
        questions = MockInterviewEngineService(db).get_questions(
            interview_id=interview_id,
            user_id=current_user.id,
        )
        return InterviewQuestionListResponse(
            items=[InterviewQuestionResponse.model_validate(q) for q in questions],
            total=len(questions),
        )
    except InterviewError as exc:
        _raise_http(exc)


@router.post(
    "/{interview_id}/finish",
    response_model=InterviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark an interview as completed",
    description=(
        "Mark an interview session as 'Completed'.\n\n"
        "**Requires authentication** — user must own the interview."
    ),
    responses={
        200: {"description": "Interview completed successfully."},
        401: {"description": "Not authenticated."},
        403: {"description": "Interview belongs to another user."},
        404: {"description": "Interview not found."},
    },
)
def finish_interview(
    interview_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUserDep,
) -> InterviewResponse:
    """Mark an interview as completed.

    Args:
        interview_id: UUID of interview.
        db: Injected database session.
        current_user: Authenticated user.

    Returns:
        Updated ``InterviewResponse``.
    """
    logger.info("POST /interviews/%s/finish | user=%s", interview_id, current_user.id)
    try:
        interview = MockInterviewEngineService(db).finish_interview(
            interview_id=interview_id,
            user_id=current_user.id,
        )
        return InterviewResponse.model_validate(interview)
    except InterviewError as exc:
        _raise_http(exc)


@router.post(
    "/questions/{question_id}/answer",
    response_model=InterviewAnswerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit student's answer for a question",
    description=(
        "Save or update the student's answer text and time taken for a specific question.\n\n"
        "**Requires authentication**."
    ),
    responses={
        201: {"description": "Answer saved successfully."},
        401: {"description": "Not authenticated."},
        403: {"description": "Question belongs to another user's interview."},
        404: {"description": "Question not found."},
    },
)
def submit_question_answer(
    question_id: uuid.UUID,
    payload: InterviewAnswerCreate,
    db: DbDep,
    current_user: CurrentUserDep,
) -> InterviewAnswerResponse:
    """Submit student's answer for a question.

    Args:
        question_id: UUID of the question.
        payload: Validated ``InterviewAnswerCreate`` schema.
        db: Injected database session.
        current_user: Authenticated user.

    Returns:
        The created or updated ``InterviewAnswerResponse``.
    """
    logger.info("POST /interviews/questions/%s/answer | user=%s", question_id, current_user.id)
    try:
        answer = MockInterviewEngineService(db).submit_answer(
            question_id=question_id,
            user_id=current_user.id,
            payload=payload,
        )
        return InterviewAnswerResponse.model_validate(answer)
    except InterviewError as exc:
        _raise_http(exc)


@router.post(
    "/{interview_id}/evaluate",
    response_model=InterviewFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate evaluation feedback for a completed interview",
    description=(
        "Evaluate a completed interview session and generate detailed feedback.\n\n"
        "**Business rule**: Interview status MUST be 'Completed'.\n\n"
        "### Error responses\n\n"
        "| Code | Meaning |\n"
        "|------|--------|\n"
        "| 400  | Interview status is not Completed |\n"
        "| 401  | Not authenticated |\n"
        "| 403  | Interview belongs to another user |\n"
        "| 404  | Interview not found |"
    ),
    responses={
        201: {"description": "Evaluation feedback generated successfully."},
        400: {"description": "Interview status is not Completed."},
        401: {"description": "Not authenticated."},
        403: {"description": "Interview belongs to another user."},
        404: {"description": "Interview not found."},
    },
)
def evaluate_interview(
    interview_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUserDep,
) -> InterviewFeedbackResponse:
    """Evaluate a completed interview.

    Args:
        interview_id: UUID of the interview.
        db: Injected database session.
        current_user: Authenticated user.

    Returns:
        The generated ``InterviewFeedbackResponse``.
    """
    logger.info("POST /interviews/%s/evaluate | user=%s", interview_id, current_user.id)
    try:
        feedback = InterviewEvaluationService(db).evaluate(
            interview_id=interview_id,
            user_id=current_user.id,
        )
        return InterviewFeedbackResponse.model_validate(feedback)
    except InterviewError as exc:
        _raise_http(exc)


@router.get(
    "/{interview_id}/feedback",
    response_model=InterviewFeedbackResponse,
    status_code=status.HTTP_200_OK,
    summary="Get feedback for an interview",
    description=(
        "Retrieve evaluation feedback for a specific interview session.\n\n"
        "**Requires authentication** — user must own the interview."
    ),
    responses={
        200: {"description": "Feedback retrieved successfully."},
        401: {"description": "Not authenticated."},
        403: {"description": "Interview belongs to another user."},
        404: {"description": "Interview or feedback not found."},
    },
)
def get_interview_feedback(
    interview_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUserDep,
) -> InterviewFeedbackResponse:
    """Retrieve feedback for an interview.

    Args:
        interview_id: UUID of the interview.
        db: Injected database session.
        current_user: Authenticated user.

    Returns:
        The ``InterviewFeedbackResponse``.
    """
    logger.info("GET /interviews/%s/feedback | user=%s", interview_id, current_user.id)
    try:
        feedback = InterviewEvaluationService(db).get_by_interview(
            interview_id=interview_id,
            user_id=current_user.id,
        )
        return InterviewFeedbackResponse.model_validate(feedback)
    except InterviewError as exc:
        _raise_http(exc)
