"""
Roadmap API router — handles roadmap generation and retrieval.

Endpoints:
- POST /roadmap/generate  — Generate roadmap (idempotent per user)
- GET  /roadmap/me        — Get current roadmap with milestone progress
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
from app.schemas.roadmap import RoadmapResponse
from app.services.profile_client import (
    ProfileClient,
    ProfileNotFoundError,
    ProfileServiceUnavailableError,
)
from app.services.roadmap_service import (
    RoadmapAlreadyExistsError,
    RoadmapNotFoundError,
    RoadmapService,
)

logger = logging.getLogger("roadmap-agent.router.roadmap")

router = APIRouter(prefix="/roadmap", tags=["Roadmap — Agent 2"])


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


@router.post(
    "/generate",
    response_model=RoadmapResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate AI-powered learning roadmap (idempotent)",
    description=(
        "Fetches the student's locked profile from profile-agent-service, runs Agent 2 "
        "LLM generation to create a personalized milestone roadmap, validates it strictly, "
        "and persists it. Returns 409 if a roadmap already exists (one roadmap per user)."
    ),
)
async def generate_roadmap(
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[RoadmapService, Depends(get_roadmap_service)],
) -> RoadmapResponse:
    """
    Generate and persist a personalized learning roadmap for the authenticated user.

    Returns:
        Created RoadmapResponse with milestones and progress.

    Raises:
        409: Roadmap already exists.
        409: Profile not found (onboarding incomplete).
        503: Profile service or LLM service unavailable.
        502: LLM validation failure.
        504: LLM timeout.
    """
    logger.info("Received roadmap generation request for user %s", user_id)

    # Fetch profile via internal service call
    profile_client = ProfileClient()
    try:
        profile = await profile_client.get_profile(user_id)
    except ProfileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete onboarding first",
        )
    except ProfileServiceUnavailableError as exc:
        logger.error("Profile service unavailable for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Profile service is currently unavailable. Please try again later.",
        )

    try:
        roadmap = await service.generate_roadmap(db=db, user_id=user_id, profile=profile)
        return roadmap

    except RoadmapAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A roadmap already exists for this user. Roadmaps are generated once.",
        )
    except LLMTimeoutError as exc:
        logger.error("LLM timeout generating roadmap for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI Agent timed out generating your roadmap. Please try again in a moment.",
        )
    except LLMValidationError as exc:
        logger.error("LLM validation failure for roadmap, user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI Agent produced an invalid roadmap after retry. Please try again.",
        )
    except LLMProviderError as exc:
        logger.error("LLM provider error for roadmap, user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is currently unavailable. Please try again later.",
        )
    except Exception as exc:
        logger.exception("Unexpected error generating roadmap for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while generating your roadmap.",
        )


@router.get(
    "/me",
    response_model=RoadmapResponse,
    summary="Get current user's roadmap with milestone progress",
)
async def get_my_roadmap(
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[RoadmapService, Depends(get_roadmap_service)],
) -> RoadmapResponse:
    """Retrieve the roadmap with computed milestone progress."""
    roadmap = await service.get_roadmap_response(db=db, user_id=user_id)
    if roadmap is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No roadmap found. Generate your roadmap first.",
        )
    return roadmap
