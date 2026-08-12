"""
backend/app/api/v1/ai/router.py
=================================
FastAPI router for the AI-powered feature suite.

Current endpoints
-----------------
  GET  /api/v1/ai/skill-gap/{user_id}/{profession_id}
      Full skill gap analysis for a learner against a profession.

  GET  /api/v1/ai/skill-gap/{user_id}/{profession_id}/summary
      Lightweight summary (readiness %, counts, next skill only).

Architecture contract
---------------------
  ✓ Delegates all analysis logic to ``SkillGapService``.
  ✓ Maps ``SkillGapError`` domain exceptions to ``HTTPException`` via a
    lookup table — no scattered if/elif chains.
  ✓ No raw SQL, no writes — read-only analysis endpoints.

Error code → HTTP status
------------------------
  user_not_found       → 404 Not Found
  profession_not_found → 404 Not Found
  no_learning_path     → 404 Not Found  (path is empty / not configured)
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.skill_gap import SkillGapAnalysis
from app.services.skill_gap import SkillGapError, SkillGapService
from typing import Annotated

logger: logging.Logger = logging.getLogger(__name__)

router = APIRouter()

# ─────────────────────────────────────────────────────────────────────────────
# Error code → HTTP status mapping
# ─────────────────────────────────────────────────────────────────────────────

_SKILL_GAP_ERROR_STATUS: dict[str, int] = {
    SkillGapError.USER_NOT_FOUND:       status.HTTP_404_NOT_FOUND,
    SkillGapError.PROFESSION_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    SkillGapError.NO_LEARNING_PATH:     status.HTTP_404_NOT_FOUND,
}


def _raise_http(exc: SkillGapError) -> None:
    """Convert a ``SkillGapError`` into an ``HTTPException`` and raise it.

    Falls back to 500 for any unknown code, logging at ERROR level so that
    unmapped codes are caught in monitoring before they reach users.

    Args:
        exc: The domain exception raised by ``SkillGapService``.

    Raises:
        HTTPException: Always — never returns normally.
    """
    http_status = _SKILL_GAP_ERROR_STATUS.get(
        exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR
    )
    if http_status == status.HTTP_500_INTERNAL_SERVER_ERROR:
        logger.error(
            "Unmapped SkillGapError code '%s' fell through to 500: %s",
            exc.code, exc.message,
        )
    raise HTTPException(status_code=http_status, detail=exc.message)


# ─────────────────────────────────────────────────────────────────────────────
# Dependency alias
# ─────────────────────────────────────────────────────────────────────────────

DbDep = Annotated[Session, Depends(get_db)]


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/skill-gap/{user_id}/{profession_id}",
    response_model=SkillGapAnalysis,
    status_code=status.HTTP_200_OK,
    summary="Analyse skill gap for a learner",
    description=(
        "Run a full AI skill gap analysis for a learner against a target "
        "profession's learning path.\n\n"
        "### How it works\n\n"
        "1. The learner's completed skills (``UserProgress.status = 'COMPLETED'``) "
        "are matched against the profession's ordered ``LearningPath``.\n"
        "2. Skills are classified into **completed**, **in progress**, and "
        "**missing** buckets.\n"
        "3. ``career_readiness_percentage`` is computed over **required skills "
        "only** — optional enrichment skills do not dilute the metric.\n"
        "4. ``recommended_next_skill`` is the first required, incomplete skill "
        "by ``LearningPath.sequence`` order — prioritising **in-progress** "
        "skills over not-started ones so the learner finishes what they began.\n"
        "5. ``estimated_completion_time`` sums the ``estimated_weeks`` of all "
        "incomplete required skills.\n\n"
        "### Performance\n\n"
        "The analysis runs in **4 SQL round-trips** regardless of path length:\n"
        "1. User existence check\n"
        "2. Profession existence check\n"
        "3. Ordered LearningPath JOIN Skill query\n"
        "4. UserProgress IN query for those skill IDs\n\n"
        "### Error responses\n\n"
        "| Code | Meaning |\n"
        "|------|---------|\n"
        "| 404  | User not found |\n"
        "| 404  | Profession not found |\n"
        "| 404  | Profession has no learning path configured |\n"
        "| 422  | Invalid UUID format in path parameters |"
    ),
    responses={
        200: {"description": "Skill gap analysis returned successfully."},
        404: {
            "description": (
                "User not found, profession not found, or "
                "profession has no learning path."
            )
        },
        422: {"description": "Path parameter is not a valid UUID."},
    },
)
def analyse_skill_gap(
    user_id: uuid.UUID,
    profession_id: uuid.UUID,
    db: DbDep,
) -> SkillGapAnalysis:
    """Run a full skill gap analysis.

    Args:
        user_id: UUID of the learner to analyse.
        profession_id: UUID of the target profession.
        db: Injected database session.

    Returns:
        Full ``SkillGapAnalysis`` payload including:
            - ``career_readiness_percentage``
            - ``completed_skills`` / ``in_progress_skills`` / ``missing_skills``
            - ``recommended_next_skill``
            - ``estimated_completion_time``
            - ``analysis_note`` (personalised motivational message)

    Raises:
        HTTPException 404: If the user, profession, or learning path is missing.
        HTTPException 422: If either path parameter is not a valid UUID.
    """
    logger.info(
        "GET /ai/skill-gap/%s/%s", user_id, profession_id
    )
    try:
        return SkillGapService(db).analyse(
            user_id=user_id,
            profession_id=profession_id,
        )
    except SkillGapError as exc:
        _raise_http(exc)


@router.get(
    "/skill-gap/{user_id}/{profession_id}/summary",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Lightweight skill gap summary",
    description=(
        "Return a minimal skill gap summary — useful for dashboard widgets, "
        "cards, and progress bars that do not need the full skill lists.\n\n"
        "**Response shape:**\n"
        "```json\n"
        "{\n"
        "  \"user_id\": \"<uuid>\",\n"
        "  \"profession_id\": \"<uuid>\",\n"
        "  \"profession_name\": \"Full-Stack Developer\",\n"
        "  \"career_readiness_percentage\": 62.5,\n"
        "  \"completed_required_skills\": 5,\n"
        "  \"total_required_skills\": 8,\n"
        "  \"total_path_skills\": 10,\n"
        "  \"estimated_completion_time\": \"14 weeks\",\n"
        "  \"recommended_next_skill\": { ... } | null,\n"
        "  \"analysis_note\": \"📈 Great progress! ...\"\n"
        "}\n"
        "```\n\n"
        "The full skill lists (``completed_skills``, ``in_progress_skills``, "
        "``missing_skills``) are omitted — fetch ``GET /skill-gap/{user_id}/"
        "{profession_id}`` for the complete analysis."
    ),
    responses={
        200: {"description": "Skill gap summary returned."},
        404: {
            "description": (
                "User not found, profession not found, or "
                "profession has no learning path."
            )
        },
        422: {"description": "Path parameter is not a valid UUID."},
    },
)
def skill_gap_summary(
    user_id: uuid.UUID,
    profession_id: uuid.UUID,
    db: DbDep,
) -> dict[str, Any]:
    """Return a lightweight skill gap summary for dashboard use.

    Runs the same underlying analysis as the full endpoint but omits the
    verbose skill lists from the response.

    Args:
        user_id: UUID of the learner to summarise.
        profession_id: UUID of the target profession.
        db: Injected database session.

    Returns:
        A slim dict containing readiness metrics, counts, the next
        recommended skill, and the analysis note — without the full
        ``completed_skills``, ``in_progress_skills``, or ``missing_skills``
        lists.

    Raises:
        HTTPException 404: If the user, profession, or learning path is missing.
        HTTPException 422: If either path parameter is not a valid UUID.
    """
    logger.info(
        "GET /ai/skill-gap/%s/%s/summary", user_id, profession_id
    )
    try:
        analysis = SkillGapService(db).analyse(
            user_id=user_id,
            profession_id=profession_id,
        )
        return {
            "user_id": str(analysis.user_id),
            "profession_id": str(analysis.profession_id),
            "profession_name": analysis.profession_name,
            "career_readiness_percentage": analysis.career_readiness_percentage,
            "completed_required_skills": analysis.completed_required_skills,
            "total_required_skills": analysis.total_required_skills,
            "total_path_skills": analysis.total_path_skills,
            "estimated_completion_time": analysis.estimated_completion_time,
            "recommended_next_skill": (
                analysis.recommended_next_skill.model_dump()
                if analysis.recommended_next_skill else None
            ),
            "analysis_note": analysis.analysis_note,
        }
    except SkillGapError as exc:
        _raise_http(exc)
