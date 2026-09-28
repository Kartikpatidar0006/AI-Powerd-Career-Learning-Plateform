"""
Pydantic v2 schemas for Profile Agent Service.

Defines schemas for:
1. User onboarding input validation
2. LLM structured JSON output schema validation
3. Dashboard data representation
4. Profile retrieval responses
"""

import uuid
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator


class EducationInfo(BaseModel):
    """Educational background information."""

    degree: str = Field(..., min_length=2, max_length=100, description="Degree name, e.g. B.Tech, B.S., M.S.")
    branch: str = Field(..., min_length=2, max_length=100, description="Field of study or branch, e.g. Computer Science")
    year: int = Field(..., ge=1970, le=2035, description="Year of graduation")
    institution: str = Field(..., min_length=2, max_length=200, description="Name of college/university")


class SkillItem(BaseModel):
    """An individual structured skill extracted by Agent 1."""

    skill_name: str = Field(..., min_length=1, max_length=100, description="Canonical skill name, e.g. React, Python")
    category: str = Field(..., min_length=2, max_length=100, description="Domain category, e.g. Frontend, Backend, Database")
    proficiency_level: Literal["beginner", "intermediate", "advanced"] = Field(
        ...,
        description="Assessed proficiency level: beginner, intermediate, or advanced",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="LLM confidence score between 0.0 and 1.0",
    )

    @field_validator("confidence_score")
    @classmethod
    def round_confidence(cls, v: float) -> float:
        """Round confidence score to 2 decimal places."""
        return round(v, 2)


class StructuredSkillsOutput(BaseModel):
    """Strict schema required from the LLM extraction response."""

    skills: list[SkillItem] = Field(
        ...,
        min_length=1,
        description="List of extracted structured skills with proficiencies and confidence",
    )


class DashboardData(BaseModel):
    """Computed dashboard summary metrics derived deterministically from structured skills."""

    skill_distribution: dict[str, int] = Field(
        ...,
        description="Category name mapped to skill count",
    )
    category_averages: dict[str, float] = Field(
        default_factory=dict,
        description="Category name mapped to average proficiency level (1.0 to 3.0)",
    )
    strongest_areas: list[str] = Field(
        default_factory=list,
        description="Top categories where student shows highest proficiency and confidence",
    )
    weakest_areas: list[str] = Field(
        default_factory=list,
        description="Categories with lowest proficiency or coverage for target role",
    )
    readiness_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Deterministic weighted readiness score (0-100)",
    )
    readiness_summary: str = Field(
        ...,
        description="Human-readable breakdown explaining the readiness score calculation",
    )


class OnboardingRequest(BaseModel):
    """Request payload submitted by user on the multi-step onboarding flow."""

    education: EducationInfo = Field(..., description="Education details")
    skills_description: str = Field(
        ...,
        min_length=10,
        max_length=4000,
        description="Free-text narrative of current skills, projects, and learning background",
    )
    target_role: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Target career role (e.g. Full Stack Engineer)",
    )
    experience_level: Literal["student", "fresher", "1-2yrs", "2+yrs"] = Field(
        ...,
        description="Experience level bracket",
    )


class StudentProfileResponse(BaseModel):
    """Complete profile response returned to client."""

    id: uuid.UUID
    user_id: uuid.UUID
    education: dict[str, Any]
    raw_input: dict[str, Any]
    structured_skills: list[dict[str, Any]]
    target_role: str
    experience_level: str
    dashboard_data: dict[str, Any]
    is_locked: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    """Standard message response."""

    message: str
    detail: str | None = None
