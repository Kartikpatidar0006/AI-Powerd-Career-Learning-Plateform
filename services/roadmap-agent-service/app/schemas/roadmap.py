"""
Pydantic v2 schemas for the Roadmap Agent Service.

Covers:
1. Milestone validation (LLM output schema)
2. Roadmap response schemas
3. Task schemas (request/response)
4. State machine type definitions
"""

import uuid
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


# ──────────────────────────────────────────────────────────────
# Milestone Schemas (LLM output validation)
# ──────────────────────────────────────────────────────────────

class MilestoneItem(BaseModel):
    """
    A single milestone within a learning roadmap.

    Validated by Pydantic when parsing LLM output. All fields required.
    """

    order: int = Field(..., ge=1, description="1-based sequential order of this milestone")
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10, max_length=1000)
    target_skills: list[str] = Field(..., min_length=1, description="At least 1 skill required")
    estimated_days: int = Field(..., ge=1, le=60, description="Days estimated for this milestone")
    difficulty_band: int = Field(..., ge=1, le=5, description="Difficulty 1 (easiest) to 5 (hardest)")
    success_criteria: list[str] = Field(
        ..., min_length=2, description="At least 2 measurable success criteria required"
    )


class LLMRoadmapOutput(BaseModel):
    """Strict schema required from the LLM roadmap generation response."""

    milestones: list[MilestoneItem] = Field(
        ...,
        min_length=4,
        max_length=8,
        description="Between 4 and 8 milestones required",
    )

    @model_validator(mode="after")
    def validate_roadmap_structure(self) -> "LLMRoadmapOutput":
        """
        Validate structural integrity rules beyond simple field constraints.

        Rules:
        - Orders must be contiguous starting from 1.
        - difficulty_band must never decrease by more than 1 between consecutive milestones
          (max jump of 1 level allowed going up OR down).
        - Total estimated days must be between 30 and 120.
        """
        milestones = self.milestones

        # Rule 1: Contiguous orders starting from 1
        orders = [m.order for m in milestones]
        expected = list(range(1, len(milestones) + 1))
        if sorted(orders) != expected:
            raise ValueError(
                f"Milestone orders must be contiguous from 1 to {len(milestones)}. "
                f"Got: {sorted(orders)}"
            )

        # Rule 2: Sort by order for sequential checks
        sorted_milestones = sorted(milestones, key=lambda m: m.order)

        # Rule 3: difficulty_band may not jump sharply (max 1 level between consecutive)
        for i in range(1, len(sorted_milestones)):
            prev = sorted_milestones[i - 1].difficulty_band
            curr = sorted_milestones[i].difficulty_band
            if curr - prev > 1:
                raise ValueError(
                    f"Difficulty band jump too sharp at milestone {sorted_milestones[i].order}: "
                    f"{prev} -> {curr}. Maximum allowed increase per step is 1."
                )

        # Rule 4: Total estimated days 30-120
        total_days = sum(m.estimated_days for m in milestones)
        if not (30 <= total_days <= 120):
            raise ValueError(
                f"Total estimated days must be between 30 and 120. Got: {total_days}"
            )

        return self


# ──────────────────────────────────────────────────────────────
# Task Schemas (LLM output validation)
# ──────────────────────────────────────────────────────────────

class LLMTaskOutput(BaseModel):
    """Strict schema required from the LLM task generation response."""

    title: str = Field(..., min_length=5, max_length=256)
    description: str = Field(..., min_length=20, max_length=2000)
    requirements: list[str] = Field(..., min_length=3, max_length=10)
    acceptance_criteria: list[str] = Field(..., min_length=2, max_length=8)
    skills_targeted: list[str] = Field(..., min_length=1)
    estimated_hours: float = Field(..., ge=1.0, le=20.0)
    starter_hint: str | None = Field(default=None, max_length=500)


# ──────────────────────────────────────────────────────────────
# API Response Schemas
# ──────────────────────────────────────────────────────────────

class MilestoneProgress(BaseModel):
    """Milestone with computed progress state."""

    order: int
    title: str
    description: str
    target_skills: list[str]
    estimated_days: int
    difficulty_band: int
    success_criteria: list[str]
    tasks_completed: int = 0
    tasks_planned: int = 0
    state: Literal["completed", "current", "upcoming", "needs_review"] = "upcoming"


class RoadmapResponse(BaseModel):
    """Complete roadmap response with computed milestone progress."""

    id: uuid.UUID
    user_id: uuid.UUID
    milestones: list[MilestoneProgress]
    status: str
    created_at: datetime
    profile_snapshot: dict[str, Any]

    model_config = {"from_attributes": True}


class TaskResponse(BaseModel):
    """Task detail response."""

    id: uuid.UUID
    user_id: uuid.UUID
    roadmap_id: uuid.UUID
    milestone_order: int
    sequence_number: int
    title: str
    description: str
    requirements: list[str]
    acceptance_criteria: list[str]
    skills_targeted: list[str]
    difficulty: int
    estimated_hours: float
    starter_hint: str | None
    status: str
    github_repo_url: str | None
    started_at: datetime | None = None
    submitted_at: datetime | None
    evaluated_at: datetime | None
    evaluation_summary: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    """Paginated task list response."""

    tasks: list[TaskResponse]
    total: int
    page: int
    page_size: int


class SubmitTaskRequest(BaseModel):
    """Request body for submitting a task with a GitHub repo URL."""

    github_repo_url: str = Field(
        ...,
        min_length=10,
        max_length=512,
        description="GitHub repository URL: https://github.com/<owner>/<repo>",
    )


class EvaluationRequest(BaseModel):
    """
    Internal request body for Agent 3 to post evaluation results.
    
    Contains score (0-100) and optional passed flag (defaults to score >= PASS_SCORE).
    """

    score: float = Field(..., ge=0.0, le=100.0, description="Evaluation score 0-100")
    feedback: str | None = Field(default=None, max_length=5000)
    criteria_results: list[dict[str, Any]] | None = None
    passed: bool | None = Field(default=None, description="Passed boolean. If omitted, computed from score >= PASS_SCORE")
    evaluated_by: str = "agent-3"


class NextTaskResponse(BaseModel):
    """Response for POST /tasks/next — either returns a task or roadmap_completed."""

    status: Literal["task_assigned", "roadmap_completed"]
    task: TaskResponse | None = None


class MessageResponse(BaseModel):
    """Standard message response."""

    message: str
    detail: str | None = None
