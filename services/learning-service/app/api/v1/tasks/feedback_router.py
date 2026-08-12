"""
services/learning-service/app/api/v1/tasks/feedback_router.py
---------------------------------------------------------------
FastAPI router for Task Evaluation & Task Feedback endpoints.
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.auth.router import get_current_user
from app.db.session import get_db
from app.schemas.task_feedback import TaskFeedbackListResponse, TaskFeedbackResponse
from app.schemas.user import UserResponse
from app.services.task_feedback import (
    TaskEvaluationService,
    TaskFeedbackError,
    TaskFeedbackService,
)

logger = logging.getLogger(__name__)

router = APIRouter()

DbDep = Annotated[Session, Depends(get_db)]
CurrentUserDep = Annotated[UserResponse, Depends(get_current_user)]


@router.post(
    "/submissions/{submission_id}/evaluate",
    response_model=TaskFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Evaluate a task submission using AI",
)
def evaluate_task_submission(
    submission_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUserDep,
) -> TaskFeedbackResponse:
    """Evaluate task submission using the evaluation service."""
    logger.info("POST /submissions/%s/evaluate | user=%s", submission_id, current_user.id)
    try:
        feedback = TaskEvaluationService(db).evaluate_submission(submission_id)
        return TaskFeedbackResponse.model_validate(feedback)
    except TaskFeedbackError as exc:
        code_to_status = {
            TaskFeedbackError.SUBMISSION_NOT_FOUND: status.HTTP_404_NOT_FOUND,
            TaskFeedbackError.FEEDBACK_ALREADY_EXISTS: status.HTTP_409_CONFLICT,
        }
        http_status = code_to_status.get(exc.code, status.HTTP_400_BAD_REQUEST)
        raise HTTPException(status_code=http_status, detail=exc.message) from exc


@router.get(
    "/submissions/{submission_id}/feedback",
    response_model=TaskFeedbackResponse,
    status_code=status.HTTP_200_OK,
    summary="Get feedback for a specific task submission",
)
def get_submission_feedback(
    submission_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUserDep,
) -> TaskFeedbackResponse:
    """Retrieve feedback for a specific submission."""
    logger.info("GET /submissions/%s/feedback | user=%s", submission_id, current_user.id)
    try:
        feedback = TaskFeedbackService(db).get_feedback_by_submission(submission_id)
        return TaskFeedbackResponse.model_validate(feedback)
    except TaskFeedbackError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc


@router.get(
    "/users/me/feedback",
    response_model=TaskFeedbackListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get all task feedback for logged-in user",
)
def get_user_task_feedback(
    db: DbDep,
    current_user: CurrentUserDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> TaskFeedbackListResponse:
    """Retrieve all task feedback for the authenticated user."""
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
