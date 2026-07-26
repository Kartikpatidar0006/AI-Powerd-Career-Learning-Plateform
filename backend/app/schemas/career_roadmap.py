"""
backend/app/schemas/career_roadmap.py
========================================
Pydantic v2 schemas for the CareerRoadmap and RoadmapStep domains.

Schema hierarchy
----------------
::

  RoadmapDifficultyLevel           — shared enum for both domains

  RoadmapStepBase                  — shared validated fields for a step
    └── RoadmapStepCreate          — write schema for step INSERT
    └── RoadmapStepUpdate          — PATCH schema: all fields optional

  RoadmapStepResponse              — full step row → JSON response
  RoadmapStepListResponse          — slim step schema for nested lists

  CareerRoadmapBase                — shared validated fields for a roadmap
    └── CareerRoadmapCreate        — write schema for roadmap INSERT
    └── CareerRoadmapUpdate        — PATCH schema: all fields optional

  CareerRoadmapResponse            — full roadmap → JSON response (with steps)
  CareerRoadmapListResponse        — slim roadmap schema for collection endpoints

Design notes
------------
- ``difficulty`` is validated against ``RoadmapDifficultyLevel``.
- ``step_order`` must be >= 1.
- ``estimated_hours`` must be >= 0.
- ``estimated_months`` must be >= 1.
- ``CareerRoadmapResponse`` includes the full list of ``RoadmapStepResponse``
  objects so a single GET returns the complete roadmap tree.
- ``profession_id`` is required on ``CareerRoadmapCreate`` and immutable
  on update.
- ``roadmap_id`` is required on ``RoadmapStepCreate`` and immutable on update.
- No business logic, no database access — pure data contracts.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ─────────────────────────────────────────────────────────────────────────────
# Difficulty enum
# ─────────────────────────────────────────────────────────────────────────────


class RoadmapDifficultyLevel(str, Enum):
    """Allowed difficulty levels for a career roadmap.

    Inheriting from ``str`` makes the enum JSON-serialisable without extra
    configuration — FastAPI serialises it as the plain string value.
    """

    BEGINNER = "Beginner"
    INTERMEDIATE = "Intermediate"
    ADVANCED = "Advanced"


# ─────────────────────────────────────────────────────────────────────────────
# RoadmapStep schemas
# ─────────────────────────────────────────────────────────────────────────────


class RoadmapStepBase(BaseModel):
    """Shared, validated fields for RoadmapStep request schemas.

    Attributes:
        step_order: 1-based position of this step in the roadmap (>= 1).
        required: Whether this step is mandatory for roadmap completion.
        estimated_hours: Expected hours to complete this step (>= 0).
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    step_order: int = Field(
        ...,
        ge=1,
        description="1-based position of this step within the roadmap.",
        examples=[1, 2, 3],
    )
    required: bool = Field(
        default=True,
        description="True = mandatory step. False = optional enrichment.",
        examples=[True, False],
    )
    estimated_hours: float = Field(
        default=0.0,
        ge=0.0,
        description="Estimated hours to complete this step. Must be >= 0.",
        examples=[8.0, 20.5, 0.0],
    )


class RoadmapStepCreate(RoadmapStepBase):
    """Request body for creating a new roadmap step
    (``POST /api/v1/roadmap-steps``).

    Inherits all fields from ``RoadmapStepBase``.  ``roadmap_id`` and
    ``skill_id`` are required — every step must belong to exactly one
    roadmap and reference exactly one skill.

    Example JSON::

        {
            "roadmap_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "skill_id":   "7cb92a33-4812-5671-c4de-3d074e77bfa7",
            "step_order": 1,
            "required": true,
            "estimated_hours": 20.0
        }
    """

    roadmap_id: uuid.UUID = Field(
        ...,
        description="UUID of the CareerRoadmap this step belongs to.",
        examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
    )
    skill_id: uuid.UUID = Field(
        ...,
        description="UUID of the Skill covered at this step.",
        examples=["7cb92a33-4812-5671-c4de-3d074e77bfa7"],
    )


class RoadmapStepUpdate(BaseModel):
    """Request body for a partial step update
    (``PATCH /api/v1/roadmap-steps/{id}``).

    All fields are optional.  ``roadmap_id`` and ``skill_id`` are excluded —
    steps cannot be re-parented or re-assigned to a different skill.

    Example JSON (change only the order)::

        { "step_order": 3 }
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    step_order: Optional[int] = Field(
        default=None,
        ge=1,
        description="New 1-based step position.",
    )
    required: Optional[bool] = Field(
        default=None,
        description="New required/optional flag.",
    )
    estimated_hours: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="New estimated hours (>= 0).",
    )


class RoadmapStepResponse(BaseModel):
    """Full roadmap step record returned by the API.

    ``ConfigDict(from_attributes=True)`` enables direct coercion from a
    ``RoadmapStep`` ORM instance.

    Attributes:
        id: UUID primary key.
        roadmap_id: UUID of the parent CareerRoadmap.
        skill_id: UUID of the referenced Skill.
        step_order: 1-based position within the roadmap.
        required: Whether this step is mandatory.
        estimated_hours: Expected hours to complete.
        created_at: UTC creation timestamp.
        updated_at: UTC last-modification timestamp.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="UUID primary key.")
    roadmap_id: uuid.UUID = Field(..., description="UUID of the parent roadmap.")
    skill_id: uuid.UUID = Field(..., description="UUID of the skill.")
    step_order: int = Field(..., description="1-based step position.")
    required: bool = Field(..., description="Whether this step is mandatory.")
    estimated_hours: float = Field(..., description="Estimated hours to complete.")
    created_at: datetime = Field(..., description="UTC creation timestamp.")
    updated_at: datetime = Field(..., description="UTC last-modified timestamp.")


class RoadmapStepListResponse(BaseModel):
    """Slim step record for nested roadmap responses.

    Omits ``created_at`` and ``updated_at`` to keep roadmap detail payloads
    concise.

    Attributes:
        id: UUID primary key.
        roadmap_id: UUID of the parent roadmap.
        skill_id: UUID of the referenced Skill.
        step_order: 1-based step position.
        required: Whether this step is mandatory.
        estimated_hours: Expected hours to complete.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="UUID primary key.")
    roadmap_id: uuid.UUID = Field(..., description="UUID of the parent roadmap.")
    skill_id: uuid.UUID = Field(..., description="UUID of the skill.")
    step_order: int = Field(..., description="1-based step position.")
    required: bool = Field(..., description="Whether this step is mandatory.")
    estimated_hours: float = Field(..., description="Estimated hours to complete.")


# ─────────────────────────────────────────────────────────────────────────────
# CareerRoadmap schemas
# ─────────────────────────────────────────────────────────────────────────────


class CareerRoadmapBase(BaseModel):
    """Shared, validated fields for CareerRoadmap request schemas.

    Attributes:
        title: Human-readable roadmap title (1–500 characters).
        description: Optional Markdown description.
        estimated_months: Estimated months to complete (>= 1).
        difficulty: Categorical level — Beginner / Intermediate / Advanced.
        is_active: Visibility flag (True = visible to learners).
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Human-readable roadmap title.",
        examples=["Full-Stack Web Developer Path", "Data Science Accelerator"],
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional Markdown description of the roadmap.",
        examples=["A comprehensive 12-month journey from HTML basics to…"],
    )
    estimated_months: int = Field(
        default=1,
        ge=1,
        description="Estimated calendar months to complete this roadmap. Must be >= 1.",
        examples=[6, 12, 18],
    )
    difficulty: RoadmapDifficultyLevel = Field(
        ...,
        description="Difficulty level: 'Beginner', 'Intermediate', or 'Advanced'.",
        examples=["Intermediate"],
    )
    is_active: bool = Field(
        default=True,
        description="True = roadmap is visible to learners.",
        examples=[True],
    )

    @field_validator("title", mode="before")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        """Ensure title is not blank after stripping whitespace.

        Args:
            value: Raw title string from the request body.

        Returns:
            Stripped, non-empty title string.

        Raises:
            ValueError: If the title is blank after stripping.
        """
        stripped = str(value).strip()
        if not stripped:
            raise ValueError("title must not be blank.")
        return stripped


class CareerRoadmapCreate(CareerRoadmapBase):
    """Request body for creating a new career roadmap
    (``POST /api/v1/career-roadmaps``).

    Inherits all validated fields from ``CareerRoadmapBase``.
    ``profession_id`` is required.

    Example JSON::

        {
            "profession_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "title": "Full-Stack Developer Path",
            "description": "12-month path from HTML to deployment…",
            "estimated_months": 12,
            "difficulty": "Intermediate",
            "is_active": true
        }
    """

    profession_id: uuid.UUID = Field(
        ...,
        description="UUID of the Profession this roadmap belongs to.",
        examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
    )


class CareerRoadmapUpdate(BaseModel):
    """Request body for a partial roadmap update
    (``PATCH /api/v1/career-roadmaps/{id}``).

    All fields are optional.  ``profession_id`` is excluded — roadmaps cannot
    be re-assigned to a different profession.

    Example JSON (deactivate a roadmap)::

        { "is_active": false }
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    title: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=500,
        description="New roadmap title.",
    )
    description: Optional[str] = Field(
        default=None,
        description="New description.",
    )
    estimated_months: Optional[int] = Field(
        default=None,
        ge=1,
        description="New estimated duration in months.",
    )
    difficulty: Optional[RoadmapDifficultyLevel] = Field(
        default=None,
        description="New difficulty level.",
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="New visibility flag.",
    )

    @field_validator("title", mode="before")
    @classmethod
    def title_must_not_be_blank(cls, value: Optional[str]) -> Optional[str]:
        """Ensure title is not blank after stripping if provided.

        Args:
            value: Raw title string or ``None``.

        Returns:
            Stripped non-empty title, or ``None``.

        Raises:
            ValueError: If provided but blank after stripping.
        """
        if value is None:
            return value
        stripped = str(value).strip()
        if not stripped:
            raise ValueError("title must not be blank.")
        return stripped


class CareerRoadmapResponse(BaseModel):
    """Full career roadmap record returned by the API, including steps.

    ``ConfigDict(from_attributes=True)`` enables direct coercion from a
    ``CareerRoadmap`` ORM instance::

        orm_obj = db.get(CareerRoadmap, roadmap_id)
        return CareerRoadmapResponse.model_validate(orm_obj)

    Attributes:
        id: UUID primary key.
        profession_id: UUID of the owning Profession.
        title: Roadmap display title.
        description: Markdown description (or ``None``).
        estimated_months: Estimated months to completion.
        difficulty: Difficulty level string.
        is_active: Visibility flag.
        steps: Ordered list of ``RoadmapStepListResponse`` objects.
        created_at: UTC creation timestamp.
        updated_at: UTC last-modification timestamp.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="UUID primary key.")
    profession_id: uuid.UUID = Field(..., description="UUID of the owning Profession.")
    title: str = Field(..., description="Roadmap display title.")
    description: Optional[str] = Field(default=None, description="Markdown description.")
    estimated_months: int = Field(..., description="Estimated months to completion.")
    difficulty: str = Field(..., description="Difficulty level.")
    is_active: bool = Field(..., description="Visibility flag.")
    steps: list[RoadmapStepListResponse] = Field(
        default_factory=list,
        description="Ordered list of steps in this roadmap.",
    )
    created_at: datetime = Field(..., description="UTC creation timestamp.")
    updated_at: datetime = Field(..., description="UTC last-modified timestamp.")


class CareerRoadmapListResponse(BaseModel):
    """Slim career roadmap record for list endpoints.

    Omits ``description`` and ``steps`` to keep collection payloads
    lightweight.  Clients fetch the full record from
    ``GET /career-roadmaps/{id}`` when they need those.

    Attributes:
        id: UUID primary key.
        profession_id: UUID of the owning Profession.
        title: Roadmap display title.
        estimated_months: Estimated months to completion.
        difficulty: Difficulty level string.
        is_active: Visibility flag.
        step_count: Number of steps in this roadmap (pre-computed).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="UUID primary key.")
    profession_id: uuid.UUID = Field(..., description="UUID of the owning Profession.")
    title: str = Field(..., description="Roadmap display title.")
    estimated_months: int = Field(..., description="Estimated months to completion.")
    difficulty: str = Field(..., description="Difficulty level.")
    is_active: bool = Field(..., description="Visibility flag.")
