"""
Profile Service — Business logic for StudentProfile creation and retrieval.

Enforces:
1. One profile per user (1:1 relationship with auth user).
2. Lock mechanism: Once created, is_locked=True is applied immediately,
   and no subsequent onboarding or modification is permitted.
3. Decoupled data persistence into the dedicated profile database.
"""

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm.base import BaseLLMProvider
from app.models.profile import StudentProfile
from app.schemas.profile import OnboardingRequest
from app.services.profile_agent import (
    calculate_dashboard_data,
    extract_structured_skills,
)

logger = logging.getLogger("profile-agent.profile-service")


class ProfileServiceError(Exception):
    """Base exception for profile service domain errors."""

    pass


class ProfileAlreadyExistsError(ProfileServiceError):
    """Raised when an onboarding request is received for an already finalized profile."""

    def __init__(self, message: str = "Profile already exists and is locked") -> None:
        super().__init__(message)
        self.message = message


class ProfileNotFoundError(ProfileServiceError):
    """Raised when querying a profile that does not exist."""

    def __init__(self, message: str = "Profile not found") -> None:
        super().__init__(message)
        self.message = message


class ProfileService:
    """Service handling StudentProfile domain operations."""

    def __init__(self, llm_provider: BaseLLMProvider) -> None:
        self.llm_provider = llm_provider

    async def get_by_user_id(
        self, db: AsyncSession, user_id: uuid.UUID
    ) -> StudentProfile | None:
        """
        Fetch a StudentProfile for a specific user ID.

        Args:
            db: Active async database session.
            user_id: UUID of the authenticated user.

        Returns:
            StudentProfile or None if not found.
        """
        stmt = select(StudentProfile).where(StudentProfile.user_id == user_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_onboarding_profile(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        request: OnboardingRequest,
    ) -> StudentProfile:
        """
        Execute Agent 1 AI analysis and finalize the immutable student profile.

        Lock Enforcement (Task 3) & Race Condition Safety:
        - Checks if a profile already exists for this user. If it does (and is locked),
          immediately raises ProfileAlreadyExistsError (which router translates to HTTP 403 Forbidden).
        - Executes Agent 1 LLM extraction and deterministic scoring.
        - Persists the profile with is_locked=True.
        - If a concurrent request created a profile in the meantime, the database unique
          constraint on user_id triggers an IntegrityError, which is caught and translated
          to the same 403 ProfileAlreadyExistsError instead of a 500 error.
        - No update/patch routes exist anywhere in the codebase.

        Args:
            db: Active async database session.
            user_id: Authenticated user UUID extracted from trusted gateway header.
            request: Validated onboarding input data.

        Returns:
            Persisted StudentProfile entity.

        Raises:
            ProfileAlreadyExistsError: If profile already exists and is locked.
            LLMValidationError: If LLM output fails schema validation.
            LLMTimeoutError: If LLM call times out.
            LLMProviderError: If external LLM service fails.
        """
        existing = await self.get_by_user_id(db, user_id)
        if existing is not None:
            logger.warning(
                "Rejected onboarding attempt for user %s: Profile already exists and is locked",
                user_id,
            )
            raise ProfileAlreadyExistsError("Profile already exists and is locked")

        # 1. Run Agent 1 extraction via LLM with strict validation and retry
        logger.info("Running Agent 1 extraction for user %s", user_id)
        skills = await extract_structured_skills(
            llm_provider=self.llm_provider,
            education=request.education,
            skills_description=request.skills_description,
            target_role=request.target_role,
            experience_level=request.experience_level,
        )

        # 2. Deterministically calculate dashboard metrics
        dashboard_metrics = calculate_dashboard_data(
            skills=skills,
            experience_level=request.experience_level,
            target_role=request.target_role,
        )

        # 3. Store raw input for audit/debugging alongside structured output
        raw_input_payload: dict[str, Any] = {
            "education": request.education.model_dump(),
            "skills_description": request.skills_description,
            "target_role": request.target_role,
            "experience_level": request.experience_level,
        }

        # 4. Construct and lock the new StudentProfile
        new_profile = StudentProfile(
            id=uuid.uuid4(),
            user_id=user_id,
            education=request.education.model_dump(),
            raw_input=raw_input_payload,
            structured_skills=[s.model_dump() for s in skills],
            target_role=request.target_role,
            experience_level=request.experience_level,
            dashboard_data=dashboard_metrics.model_dump(),
            is_locked=True,  # Lock immediately upon creation!
        )

        try:
            db.add(new_profile)
            await db.commit()
            await db.refresh(new_profile)
        except IntegrityError as exc:
            await db.rollback()
            logger.warning(
                "IntegrityError inserting profile for user %s (concurrent creation): %s",
                user_id,
                exc,
            )
            raise ProfileAlreadyExistsError("Profile already exists and is locked") from exc

        logger.info(
            "Created and locked StudentProfile %s for user %s with readiness score %d",
            new_profile.id,
            user_id,
            dashboard_metrics.readiness_score,
        )

        return new_profile
