"""
backend/app/api/v1/tasks/feedback_router.py
=============================================
FastAPI router for the Task Feedback feature.

Endpoints
---------
  POST /submissions/{submission_id}/evaluate  Generate feedback for a submission.
  GET  /submissions/{submission_id}/feedback  Return generated feedback for a submission.
  GET  /users/me/feedback                     Return all feedback for the logged-in user.

Architecture contract
---------------------
  ✓ Delegates logic to ``TaskEvaluationService`` and ``TaskFeedbackService``.
  ✓ Maps ``TaskFeedbackError`` domain exceptions to ``HTTPException``.
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
from app.schemas.interview_question import InterviewAnswerCreate, InterviewAnswerResponse
from app.schemas.notification import NotificationListResponse, NotificationResponse
from app.schemas.progress import RoadmapProgressResponse, UserOverallProgressResponse
from app.schemas.task_feedback import TaskFeedbackListResponse, TaskFeedbackResponse
from app.schemas.user import UserResponse
from app.services.interview import InterviewError, InterviewService
from app.services.interview_engine import MockInterviewEngineService
from app.services.interview_evaluation import InterviewEvaluationService
from app.services.notification import NotificationService
from app.services.progress import ProgressError, ProgressService
from app.services.task_feedback import (
    TaskEvaluationService,
    TaskFeedbackError,
    TaskFeedbackService,
)

logger: logging.Logger = logging.getLogger(__name__)

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Error code → HTTP status mapping
# ─────────────────────────────────────────────────────────────────────────────

_FEEDBACK_ERROR_STATUS: dict[str, int] = {
    TaskFeedbackError.SUBMISSION_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    TaskFeedbackError.FEEDBACK_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    TaskFeedbackError.UNAUTHORIZED: status.HTTP_403_FORBIDDEN,
}


def _raise_http(exc: TaskFeedbackError) -> None:
    """Convert a ``TaskFeedbackError`` into an ``HTTPException`` and raise it.

    Args:
        exc: The domain exception raised by services.

    Raises:
        HTTPException: Always.
    """
    http_status = _FEEDBACK_ERROR_STATUS.get(
        exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR
    )
    if http_status == status.HTTP_500_INTERNAL_SERVER_ERROR:
        logger.error(
            "Unmapped TaskFeedbackError code '%s' fell through to 500: %s",
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
    "/submissions/{submission_id}/evaluate",
    response_model=TaskFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Evaluate a task submission",
    description=(
        "Generate evaluation feedback for a task submission.\n\n"
        "**Requires authentication** — user must own the submission.\n\n"
        "### Error responses\n\n"
        "| Code | Meaning |\n"
        "|------|--------|\n"
        "| 401  | Not authenticated |\n"
        "| 403  | Submission belongs to another user |\n"
        "| 404  | Submission not found |"
    ),
    responses={
        201: {"description": "Feedback generated successfully."},
        401: {"description": "Not authenticated."},
        403: {"description": "Submission belongs to another user."},
        404: {"description": "Submission not found."},
    },
)
def evaluate_submission(
    submission_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUserDep,
) -> TaskFeedbackResponse:
    """Generate feedback for a submission.

    Args:
        submission_id: UUID of the submission to evaluate.
        db: Injected database session.
        current_user: Authenticated user.

    Returns:
        The generated ``TaskFeedbackResponse``.

    Raises:
        HTTPException: 403 if unauthorized, 404 if submission missing.
    """
    logger.info("POST /submissions/%s/evaluate | user=%s", submission_id, current_user.id)
    try:
        feedback = TaskEvaluationService(db).evaluate(
            submission_id=submission_id,
            user_id=current_user.id,
        )
        return TaskFeedbackResponse.model_validate(feedback)
    except TaskFeedbackError as exc:
        _raise_http(exc)


@router.get(
    "/submissions/{submission_id}/feedback",
    response_model=TaskFeedbackResponse,
    status_code=status.HTTP_200_OK,
    summary="Get feedback for a submission",
    description=(
        "Retrieve the generated feedback for a specific task submission.\n\n"
        "**Requires authentication** — user must own the submission.\n\n"
        "### Error responses\n\n"
        "| Code | Meaning |\n"
        "|------|--------|\n"
        "| 401  | Not authenticated |\n"
        "| 403  | Submission belongs to another user |\n"
        "| 404  | Submission or feedback not found |"
    ),
    responses={
        200: {"description": "Feedback retrieved successfully."},
        401: {"description": "Not authenticated."},
        403: {"description": "Submission belongs to another user."},
        404: {"description": "Submission or feedback not found."},
    },
)
def get_submission_feedback(
    submission_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUserDep,
) -> TaskFeedbackResponse:
    """Retrieve feedback for a submission.

    Args:
        submission_id: UUID of the submission.
        db: Injected database session.
        current_user: Authenticated user.

    Returns:
        The ``TaskFeedbackResponse``.

    Raises:
        HTTPException: 403 if unauthorized, 404 if not found.
    """
    logger.info("GET /submissions/%s/feedback | user=%s", submission_id, current_user.id)
    try:
        feedback = TaskFeedbackService(db).get_by_submission(
            submission_id=submission_id,
            user_id=current_user.id,
        )
        return TaskFeedbackResponse.model_validate(feedback)
    except TaskFeedbackError as exc:
        _raise_http(exc)


@router.get(
    "/users/me/feedback",
    response_model=TaskFeedbackListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get all feedback for logged-in user",
    description=(
        "Retrieve a paginated list of all evaluation feedback records for the "
        "authenticated user.\n\n"
        "**Requires authentication**."
    ),
    responses={
        200: {"description": "User feedback list returned."},
        401: {"description": "Not authenticated."},
    },
)
def get_user_feedback(
    db: DbDep,
    current_user: CurrentUserDep,
    skip: int = Query(0, ge=0, description="Offset for pagination."),
    limit: int = Query(20, ge=1, le=100, description="Max results."),
) -> TaskFeedbackListResponse:
    """Retrieve all feedback records for the authenticated user.

    Args:
        db: Injected database session.
        current_user: Authenticated user.
        skip: Pagination offset.
        limit: Pagination limit.

    Returns:
        ``TaskFeedbackListResponse``.
    """
    logger.info("GET /users/me/feedback | user=%s", current_user.id)
    items, total = TaskFeedbackService(db).list_user_feedback(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    return TaskFeedbackListResponse(
        items=[TaskFeedbackResponse.model_validate(f) for f in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/users/me/interviews",
    response_model=InterviewListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get all interviews for logged-in user",
    description=(
        "Retrieve a paginated list of all interviews scheduled for the "
        "authenticated user.\n\n"
        "**Requires authentication**."
    ),
    responses={
        200: {"description": "User interviews returned."},
        401: {"description": "Not authenticated."},
    },
)
def get_user_interviews(
    db: DbDep,
    current_user: CurrentUserDep,
    skip: int = Query(0, ge=0, description="Offset for pagination."),
    limit: int = Query(20, ge=1, le=100, description="Max results."),
) -> InterviewListResponse:
    """Retrieve all interviews for the authenticated user.

    Args:
        db: Injected database session.
        current_user: Authenticated user.
        skip: Pagination offset.
        limit: Pagination limit.

    Returns:
        ``InterviewListResponse``.
    """
    logger.info("GET /users/me/interviews | user=%s", current_user.id)
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
def submit_question_answer_direct(
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
    logger.info("POST /questions/%s/answer | user=%s", question_id, current_user.id)
    try:
        answer = MockInterviewEngineService(db).submit_answer(
            question_id=question_id,
            user_id=current_user.id,
            payload=payload,
        )
        return InterviewAnswerResponse.model_validate(answer)
    except InterviewError as exc:
        _raise_http(TaskFeedbackError(exc.message, code=exc.code))


@router.get(
    "/users/me/interview-feedback",
    response_model=InterviewFeedbackListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get all interview feedback for logged-in user",
    description=(
        "Retrieve a paginated list of all interview evaluation feedback records for the "
        "authenticated user.\n\n"
        "**Requires authentication**."
    ),
    responses={
        200: {"description": "User interview feedback list returned."},
        401: {"description": "Not authenticated."},
    },
)
def get_user_interview_feedback(
    db: DbDep,
    current_user: CurrentUserDep,
    skip: int = Query(0, ge=0, description="Offset for pagination."),
    limit: int = Query(20, ge=1, le=100, description="Max results."),
) -> InterviewFeedbackListResponse:
    """Retrieve all interview feedback records for the authenticated user.

    Args:
        db: Injected database session.
        current_user: Authenticated user.
        skip: Pagination offset.
        limit: Pagination limit.

    Returns:
        ``InterviewFeedbackListResponse``.
    """
    logger.info("GET /users/me/interview-feedback | user=%s", current_user.id)
    items, total = InterviewEvaluationService(db).list_user_feedback(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    return InterviewFeedbackListResponse(
        items=[InterviewFeedbackResponse.model_validate(f) for f in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/users/me/progress",
    response_model=UserOverallProgressResponse,
    status_code=status.HTTP_200_OK,
    summary="Get overall progress for logged-in user",
    description=(
        "Retrieve aggregated platform progress for the authenticated user.\n\n"
        "**Requires authentication**."
    ),
    responses={
        200: {"description": "Overall user progress returned."},
        401: {"description": "Not authenticated."},
    },
)
def get_user_overall_progress(
    db: DbDep,
    current_user: CurrentUserDep,
) -> UserOverallProgressResponse:
    """Retrieve overall platform progress for the authenticated user.

    Args:
        db: Injected database session.
        current_user: Authenticated user.

    Returns:
        ``UserOverallProgressResponse``.
    """
    logger.info("GET /users/me/progress | user=%s", current_user.id)
    return ProgressService(db).get_user_overall_progress(user_id=current_user.id)


@router.get(
    "/roadmaps/{roadmap_id}/progress",
    response_model=RoadmapProgressResponse,
    status_code=status.HTTP_200_OK,
    summary="Get progress for a specific career roadmap",
    description=(
        "Retrieve progress metrics for a specific career roadmap for the authenticated user.\n\n"
        "**Requires authentication**."
    ),
    responses={
        200: {"description": "Roadmap progress metrics returned."},
        401: {"description": "Not authenticated."},
        404: {"description": "Roadmap not found."},
    },
)
def get_roadmap_progress(
    roadmap_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUserDep,
) -> RoadmapProgressResponse:
    """Retrieve progress metrics for a specific career roadmap.

    Args:
        roadmap_id: UUID of CareerRoadmap.
        db: Injected database session.
        current_user: Authenticated user.

    Returns:
        ``RoadmapProgressResponse``.

    Raises:
        HTTPException 404: If roadmap missing.
    """
    logger.info("GET /roadmaps/%s/progress | user=%s", roadmap_id, current_user.id)
    try:
        return ProgressService(db).get_roadmap_progress(
            user_id=current_user.id,
            roadmap_id=roadmap_id,
        )
    except ProgressError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)


@router.get(
    "/users/me/notifications",
    response_model=NotificationListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get all notifications for logged-in user",
    description=(
        "Retrieve a paginated list of notifications for the authenticated user, "
        "including total count and unread count.\n\n"
        "**Requires authentication**."
    ),
    responses={
        200: {"description": "User notifications list returned."},
        401: {"description": "Not authenticated."},
    },
)
def get_user_notifications(
    db: DbDep,
    current_user: CurrentUserDep,
    skip: int = Query(0, ge=0, description="Offset for pagination."),
    limit: int = Query(20, ge=1, le=100, description="Max results."),
) -> NotificationListResponse:
    """Retrieve notifications for the authenticated user.

    Args:
        db: Injected database session.
        current_user: Authenticated user.
        skip: Pagination offset.
        limit: Pagination limit.

    Returns:
        ``NotificationListResponse``.
    """
    logger.info("GET /users/me/notifications | user=%s", current_user.id)
    items, total, unread_count = NotificationService(db).list_user_notifications(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in items],
        total=total,
        unread_count=unread_count,
        skip=skip,
        limit=limit,
    )
