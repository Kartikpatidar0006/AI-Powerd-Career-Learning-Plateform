"""
Profile API router.

Exposes endpoints for onboarding and retrieving the student profile.
User identity is securely derived from the X-User-Id header injected by
the API Gateway after JWT verification.

Immutability & Lock Enforcement:
- POST /profile/onboarding: Validates input, runs Agent 1 AI extraction,
  and locks the profile immediately upon creation. If already locked,
  returns 403 Forbidden.
- GET /profile/me: Retrieves the student's own profile.
- Strictly NO PUT or PATCH endpoints are exposed for onboarding fields.
"""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import (
    LLMProviderError,
    LLMTimeoutError,
    LLMValidationError,
    get_llm_provider,
)
from app.db.session import get_db
from app.schemas.profile import OnboardingRequest, StudentProfileResponse
from app.services.profile_service import (
    ProfileAlreadyExistsError,
    ProfileService,
)

logger = logging.getLogger("profile-agent.router")

router = APIRouter(prefix="/profile", tags=["Student Profile & Agent 1"])


def get_current_user_id(
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> uuid.UUID:
    """
    Extract and validate authenticated user UUID from trusted gateway header.

    The API Gateway validates the JWT before forwarding and injects X-User-Id.
    Direct calls omitting this header or providing an invalid UUID are rejected with 401.

    Args:
        x_user_id: Injected user ID string.

    Returns:
        UUID of the authenticated user.

    Raises:
        HTTPException(401): If the header is missing or malformed.
    """
    if not x_user_id:
        logger.warning("Request rejected: Missing X-User-Id header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
        )
    try:
        return uuid.UUID(x_user_id)
    except ValueError:
        logger.warning("Request rejected: Malformed X-User-Id header '%s'", x_user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identification header",
        )


def get_profile_service() -> ProfileService:
    """Dependency providing a configured ProfileService instance."""
    provider = get_llm_provider()
    return ProfileService(llm_provider=provider)


@router.post(
    "/onboarding",
    response_model=StudentProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit onboarding, execute Agent 1, and lock profile",
    description=(
        "Processes raw onboarding input using Agent 1 (LLM structured skills extraction "
        "and deterministic readiness calculation) and creates an immutable, locked profile. "
        "Returns 403 Forbidden if a profile already exists for this user."
    ),
)
async def submit_onboarding(
    request: OnboardingRequest,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> StudentProfileResponse:
    """
    Handle student onboarding submission and Agent 1 execution.

    Args:
        request: Validated education, skills description, target role, and experience level.
        user_id: Verified user UUID from gateway header.
        db: Database session.
        service: ProfileService instance.

    Returns:
        Created and locked StudentProfileResponse.

    Raises:
        HTTPException 403: If profile already exists and is locked.
        HTTPException 502: If LLM output fails schema validation.
        HTTPException 503: If LLM service is unreachable.
        HTTPException 504: If LLM service times out.
    """
    logger.info("Received onboarding submission for user %s", user_id)

    try:
        profile = await service.create_onboarding_profile(
            db=db,
            user_id=user_id,
            request=request,
        )
        return StudentProfileResponse.model_validate(profile)

    except ProfileAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=exc.message,
        )
    except LLMTimeoutError as exc:
        logger.error("LLM timeout during onboarding for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI Agent timed out analyzing profile. Please try again in a few moments.",
        )
    except LLMValidationError as exc:
        logger.error("LLM validation failure for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI Agent produced an unparseable response after retry. Please try again.",
        )
    except LLMProviderError as exc:
        logger.error("LLM provider error for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is currently unavailable. Please try again later.",
        )
    except Exception as exc:
        logger.exception("Unexpected error during onboarding for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing your profile.",
        )


@router.get(
    "/me",
    response_model=StudentProfileResponse,
    summary="Get authenticated user's profile",
    description="Retrieves the locked student profile and dashboard data for the authenticated user.",
)
async def get_my_profile(
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> StudentProfileResponse:
    """
    Retrieve the current authenticated user's profile.

    Args:
        user_id: Verified user UUID from gateway header.
        db: Database session.
        service: ProfileService instance.

    Returns:
        StudentProfileResponse.

    Raises:
        HTTPException 404: If profile has not been created yet.
    """
    profile = await service.get_by_user_id(db=db, user_id=user_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found. Please complete the onboarding process.",
        )
    return StudentProfileResponse.model_validate(profile)
