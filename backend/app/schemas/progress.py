"""
backend/app/schemas/progress.py
================================
Pydantic v2 schemas for the Progress Engine feature.

This module defines response schemas for learner progress tracking:

  UserOverallProgressResponse — Aggregated platform progress for the logged-in user.
  RoadmapProgressResponse      — Detailed progress metrics for a specific career roadmap.

Design notes:
  - ``ConfigDict(from_attributes=True)`` enables ORM → Pydantic conversion.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UserOverallProgressResponse(BaseModel):
    """API response schema for user overall platform progress.

    Attributes:
        user_id: UUID of the user.
        completed_tasks: Total tasks completed by user.
        completed_interviews: Total interviews completed by user.
        total_skills_completed: Skills marked completed (100%).
        total_skills_in_progress: Skills currently in progress.
        overall_progress_percentage: Aggregated progress percentage.
    """

    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    completed_tasks: int
    completed_interviews: int
    total_skills_completed: int
    total_skills_in_progress: int
    overall_progress_percentage: float = Field(..., ge=0.0, le=100.0)
    study_streak: int = 0
    job_readiness_score: int = 0


class RoadmapProgressResponse(BaseModel):
    """API response schema for progress against a specific career roadmap.

    Attributes:
        roadmap_id: UUID of the CareerRoadmap.
        roadmap_title: Title of the roadmap.
        current_step_id: UUID of current RoadmapStep (may be null if not started/completed).
        completed_steps: Count of completed steps.
        total_steps: Total steps in the roadmap.
        completed_tasks: Count of completed tasks under this roadmap.
        total_tasks: Total tasks under this roadmap.
        progress_percentage: Completion percentage (0.0 to 100.0).
        status: Progress status ('NOT_STARTED', 'IN_PROGRESS', 'COMPLETED').
    """

    model_config = ConfigDict(from_attributes=True)

    roadmap_id: uuid.UUID
    roadmap_title: str
    current_step_id: Optional[uuid.UUID] = None
    completed_steps: int
    total_steps: int
    completed_tasks: int
    total_tasks: int
    progress_percentage: float = Field(..., ge=0.0, le=100.0)
    status: str
