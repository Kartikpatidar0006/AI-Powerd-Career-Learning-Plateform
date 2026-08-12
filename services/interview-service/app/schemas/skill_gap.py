"""
backend/app/schemas/skill_gap.py
===================================
Pydantic v2 schemas for the AI Skill Gap Analyzer API.

These are **read-only response schemas** — the analyzer performs no writes.
The API accepts only two path/query parameters (user_id, profession_id) and
returns a rich analysis payload.

Schema hierarchy
----------------
::

  SkillSummary              — slim skill record in the response lists
  SkillGapAnalysis          — the full analysis payload returned by the API

Design notes
------------
- All UUID fields use ``uuid.UUID`` for automatic validation and
  serialisation.
- ``career_readiness_percentage`` is a float 0.0–100.0.
- ``recommended_next_skill`` is ``None`` when the learner has already
  completed all required skills.
- ``estimated_completion_time`` is a human-readable string
  (e.g. ``"14 weeks"``).
- No business logic, no database access — pure data contracts.
"""

from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SkillSummary(BaseModel):
    """Slim representation of a skill used inside analysis lists.

    Attributes:
        id: UUID of the skill.
        name: Human-readable skill name.
        difficulty: Difficulty level string (e.g. ``'Beginner'``).
        category: Optional grouping category.
        sequence: 1-based position in the profession's learning path.
        estimated_weeks: Expected weeks to complete this skill (from LearningPath).
        is_required: Whether this skill is mandatory for the profession.
        progress_percentage: Learner's current completion percentage (0–100).
            ``0`` if the learner has no progress record for this skill.
        status: Learner's current status string (e.g. ``'NOT_STARTED'``).
            ``'NOT_STARTED'`` if no progress record exists.
    """

    model_config = ConfigDict(from_attributes=False)

    id: uuid.UUID = Field(..., description="UUID of the skill.")
    name: str = Field(..., description="Human-readable skill name.")
    difficulty: str = Field(..., description="Difficulty level.")
    category: Optional[str] = Field(default=None, description="Grouping category.")
    sequence: int = Field(..., description="1-based position in the learning path.")
    estimated_weeks: int = Field(
        ..., description="Expected weeks to complete (from LearningPath)."
    )
    is_required: bool = Field(..., description="Mandatory for path completion.")
    progress_percentage: int = Field(
        default=0,
        description="Learner's current completion percentage (0–100).",
    )
    status: str = Field(
        default="NOT_STARTED",
        description="Learner's current status for this skill.",
    )


class SkillGapAnalysis(BaseModel):
    """Full skill gap analysis payload returned by the analyzer API.

    Provides a comprehensive snapshot of the learner's readiness for the
    selected profession — suitable for rendering a career dashboard,
    personalised study plan, or progress report.

    Attributes:
        user_id: UUID of the analysed learner.
        profession_id: UUID of the target profession.
        profession_name: Display name of the profession.
        total_required_skills: Count of required skills in the learning path.
        total_path_skills: Count of all skills (required + optional) in the path.
        career_readiness_percentage: Float 0.0–100.0 representing the learner's
            progress through **required** skills only.
        completed_skills: Ordered list of ``SkillSummary`` objects where the
            learner's status is ``'COMPLETED'``.
        in_progress_skills: Ordered list of ``SkillSummary`` objects where the
            learner's status is ``'IN_PROGRESS'``.
        missing_skills: Ordered list of ``SkillSummary`` objects the learner
            has not yet started (``'NOT_STARTED'`` or no progress record).
        recommended_next_skill: The single highest-priority ``SkillSummary``
            the learner should tackle next — the first required, incomplete
            skill by LearningPath sequence order.  ``None`` if all required
            skills are completed.
        estimated_completion_time: Human-readable estimate for the remaining
            study time based on the sum of ``estimated_weeks`` for all
            incomplete required skills.
        completed_required_skills: Count of required skills with status
            ``'COMPLETED'``.
        analysis_note: A short contextual message tailored to the learner's
            current state (e.g. congratulations on completion, or an
            encouragement to continue).
    """

    model_config = ConfigDict(from_attributes=False)

    user_id: uuid.UUID = Field(..., description="UUID of the analysed learner.")
    profession_id: uuid.UUID = Field(
        ..., description="UUID of the target profession."
    )
    profession_name: str = Field(..., description="Display name of the profession.")
    total_required_skills: int = Field(
        ..., description="Total required skills in the profession's learning path."
    )
    total_path_skills: int = Field(
        ..., description="Total skills (required + optional) in the learning path."
    )
    career_readiness_percentage: float = Field(
        ...,
        description="Completion percentage over required skills only (0.0–100.0).",
        examples=[62.5, 100.0, 0.0],
    )
    completed_skills: list[SkillSummary] = Field(
        default_factory=list,
        description="Skills the learner has completed (status = 'COMPLETED').",
    )
    in_progress_skills: list[SkillSummary] = Field(
        default_factory=list,
        description="Skills currently in progress (status = 'IN_PROGRESS').",
    )
    missing_skills: list[SkillSummary] = Field(
        default_factory=list,
        description="Skills not yet started (no record or status = 'NOT_STARTED').",
    )
    recommended_next_skill: Optional[SkillSummary] = Field(
        default=None,
        description=(
            "The highest-priority incomplete required skill by LearningPath "
            "sequence.  None if all required skills are complete."
        ),
    )
    estimated_completion_time: str = Field(
        ...,
        description=(
            "Human-readable estimate for remaining study time based on "
            "incomplete required skills. E.g. '14 weeks', '0 weeks'."
        ),
        examples=["14 weeks", "6 weeks", "0 weeks"],
    )
    completed_required_skills: int = Field(
        ...,
        description="Count of required skills with status 'COMPLETED'.",
    )
    analysis_note: str = Field(
        ...,
        description="Short contextual message tailored to the learner's current state.",
        examples=[
            "🎉 Congratulations! You have completed all required skills.",
            "📈 Great progress! Keep going — you're 62.5% ready.",
            "🚀 Just getting started! Your first recommended skill is Python.",
        ],
    )
