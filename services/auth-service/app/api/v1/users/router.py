"""
backend/app/api/v1/users/router.py
===================================
FastAPI router for User management & onboarding endpoints.
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.auth.router import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.user_activity import UserActivity
from app.schemas.user import UserResponse

logger: logging.Logger = logging.getLogger(__name__)

router = APIRouter()

DbDep = Annotated[Session, Depends(get_db)]
CurrentUserDep = Annotated[UserResponse, Depends(get_current_user)]


class OnboardingSubmissionRequest(BaseModel):
    profession_id: Optional[uuid.UUID] = None
    profession_slug: Optional[str] = None
    assessment_score: int = Field(default=0, ge=0, le=100)
    ai_match_percentage: int = Field(default=0, ge=0, le=100)
    daily_study_time: Optional[str] = "1 hour"
    experience_level: Optional[str] = "Beginner"


@router.post(
    "/onboarding",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Complete user onboarding assessment & profile",
)
def complete_onboarding(
    payload: OnboardingSubmissionRequest,
    current_user: CurrentUserDep,
    db: DbDep,
) -> UserResponse:
    """Save onboarding responses, update DB user profile & set active profession."""
    user = db.get(User, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Resolve profession
    prof_id = payload.profession_id
    if prof_id:
        user.profession_id = prof_id

    user.onboarding_completed = True
    user.assessment_score = payload.assessment_score
    user.ai_match_percentage = payload.ai_match_percentage or 85
    user.daily_study_time = payload.daily_study_time
    user.experience_level = payload.experience_level

    # Record UserActivity for streak tracking
    activity = UserActivity(
        user_id=user.id,
        activity_type="ONBOARDING_COMPLETED",
        description=f"Completed career onboarding assessment with {user.ai_match_percentage}% AI match",
    )
    db.add(activity)
    db.commit()
    db.refresh(user)

    logger.info("User %s completed onboarding. Profession: %s", user.id, user.profession_id)
    return UserResponse.model_validate(user)
