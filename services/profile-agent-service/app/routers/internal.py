"""
Internal router for profile-agent-service.

Exposes service-to-service endpoints protected by X-Internal-Token.
These routes are NOT exposed through the API gateway.

Endpoints:
- GET /internal/profile/{user_id} — Returns the locked profile for a given user ID.
  Used by roadmap-agent-service to fetch profile data during roadmap generation.
"""

import hmac
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.schemas.profile import StudentProfileResponse
from app.services.profile_service import ProfileService
from app.core.llm import get_llm_provider

logger = logging.getLogger("profile-agent.internal-router")

internal_router = APIRouter(prefix="/internal", tags=["Internal — Service-to-Service"])


def verify_internal_token(
    x_internal_token: Annotated[str | None, Header(alias="X-Internal-Token")] = None,
) -> None:
    """
    Verify the shared internal service token using constant-time comparison.

    Uses hmac.compare_digest to prevent timing attacks on secret comparison.
    """
    if not x_internal_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Internal authentication required",
        )
    if not hmac.compare_digest(x_internal_token, settings.INTERNAL_SERVICE_TOKEN):
        logger.warning(
            "Invalid internal token attempt on /internal/profile endpoint"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid internal authentication token",
        )


def get_profile_service() -> ProfileService:
    """Dependency providing a configured ProfileService instance."""
    provider = get_llm_provider()
    return ProfileService(llm_provider=provider)


@internal_router.get(
    "/profile/{user_id}",
    response_model=StudentProfileResponse,
    summary="[Internal] Get locked profile by user ID",
    description=(
        "Service-to-service endpoint for roadmap-agent-service to fetch a locked profile. "
        "Protected by X-Internal-Token header (compared with hmac.compare_digest). "
        "NOT routed through the API gateway — internal traffic only."
    ),
)
async def get_internal_profile(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[ProfileService, Depends(get_profile_service)],
    _: Annotated[None, Depends(verify_internal_token)],
) -> StudentProfileResponse:
    """
    Return the locked profile for the given user ID.

    Args:
        user_id: The user's UUID (from the path).
        db: Database session.
        service: ProfileService instance.

    Returns:
        StudentProfileResponse if profile exists.

    Raises:
        404: If no profile found for this user.
    """
    profile = await service.get_by_user_id(db=db, user_id=user_id)
    if profile is None:
        logger.info("Internal: Profile not found for user %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile not found for user {user_id}",
        )
    return StudentProfileResponse.model_validate(profile)
