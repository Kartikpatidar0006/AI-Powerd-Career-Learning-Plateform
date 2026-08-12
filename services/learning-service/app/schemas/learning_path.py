"""
backend/app/schemas/learning_path.py
=======================================
Pydantic v2 schemas for the LearningPath domain.

Schema hierarchy
----------------
::

  LearningPathBase          — shared validated fields
    └── LearningPathCreate  — write schema for INSERT
    └── LearningPathUpdate  — PATCH schema: all fields optional

  LearningPathResponse      — full row → JSON response
  LearningPathListResponse  — slim response for list / ordered-path endpoints

Design notes
------------
- ``sequence`` must be >= 1 (1-based ordering).
- ``estimated_weeks`` must be >= 1.
- ``profession_id`` and ``skill_id`` are required on ``LearningPathCreate``
  and immutable (excluded from ``LearningPathUpdate``) — re-parenting is a
  delete + re-create operation.
- ``LearningPathResponse`` uses ``ConfigDict(from_attributes=True)`` for
  direct ORM → schema coercion without extra mappers.
- No business logic, no database access — pure data contracts.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ─────────────────────────────────────────────────────────────────────────────
# Base — shared validated fields
# ─────────────────────────────────────────────────────────────────────────────


class LearningPathBase(BaseModel):
    """Shared, validated fields for both request and response schemas.

    ``LearningPathBase`` is never used directly as a request or response body —
    it is a mixin that keeps ``LearningPathCreate`` and ``LearningPathUpdate``
    DRY.

    Attributes:
        sequence: 1-based step number within the profession learning path.
            Must be >= 1.
        estimated_weeks: Expected number of weeks to complete this step.
            Must be >= 1.
        is_required: ``True`` = mandatory for path completion;
            ``False`` = optional enrichment material.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    sequence: int = Field(
        ...,
        ge=1,
        description="1-based step number within the profession learning path.",
        examples=[1, 2, 3],
    )
    estimated_weeks: int = Field(
        default=1,
        ge=1,
        description="Expected number of study weeks to complete this step.",
        examples=[2, 4],
    )
    is_required: bool = Field(
        default=True,
        description="True = mandatory for completion. False = optional enrichment.",
        examples=[True],
    )

    @field_validator("sequence", mode="before")
    @classmethod
    def sequence_must_be_positive(cls, value: int) -> int:
        """Coerce and validate that sequence is a positive integer.

        Args:
            value: Raw sequence value from the request body.

        Returns:
            Validated positive integer.

        Raises:
            ValueError: If the value is less than 1.
        """
        value = int(value)
        if value < 1:
            raise ValueError("sequence must be >= 1 (1-based ordering).")
        return value

    @field_validator("estimated_weeks", mode="before")
    @classmethod
    def estimated_weeks_must_be_positive(cls, value: int) -> int:
        """Coerce and validate that estimated_weeks is a positive integer.

        Args:
            value: Raw weeks value from the request body.

        Returns:
            Validated positive integer.

        Raises:
            ValueError: If the value is less than 1.
        """
        value = int(value)
        if value < 1:
            raise ValueError("estimated_weeks must be >= 1.")
        return value


# ─────────────────────────────────────────────────────────────────────────────
# Create — write schema for POST /learning-paths
# ─────────────────────────────────────────────────────────────────────────────


class LearningPathCreate(LearningPathBase):
    """Request body for creating a new learning path entry.

    ``POST /api/v1/learning-paths``

    Both ``profession_id`` and ``skill_id`` are required at creation time and
    cannot be changed afterwards — use DELETE + POST to re-parent an entry.

    Example JSON::

        {
            "profession_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "skill_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
            "sequence": 1,
            "estimated_weeks": 3,
            "is_required": true
        }
    """

    profession_id: uuid.UUID = Field(
        ...,
        description="UUID of the Profession this step belongs to.",
        examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
    )
    skill_id: uuid.UUID = Field(
        ...,
        description="UUID of the Skill to learn at this step.",
        examples=["7c9e6679-7425-40de-944b-e07fc1f90ae7"],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Update — PATCH schema: all fields optional
# ─────────────────────────────────────────────────────────────────────────────


class LearningPathUpdate(BaseModel):
    """Request body for a partial learning path update.

    ``PATCH /api/v1/learning-paths/{id}``

    All fields are optional — only supplied fields are applied.  ``None``
    means "leave unchanged".

    ``profession_id`` and ``skill_id`` are intentionally excluded — the
    entry cannot be re-parented after creation.

    Example JSON (bump sequence and estimated time)::

        { "sequence": 2, "estimated_weeks": 4 }
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    sequence: Optional[int] = Field(
        default=None,
        ge=1,
        description="New 1-based step number.",
    )
    estimated_weeks: Optional[int] = Field(
        default=None,
        ge=1,
        description="New estimated weeks to complete this step.",
    )
    is_required: Optional[bool] = Field(
        default=None,
        description="New required status.",
    )

    @field_validator("sequence", mode="before")
    @classmethod
    def sequence_must_be_positive(cls, value: Optional[int]) -> Optional[int]:
        """Validate sequence if provided.

        Args:
            value: Raw sequence value or ``None``.

        Returns:
            Validated positive integer or ``None``.
        """
        if value is None:
            return value
        value = int(value)
        if value < 1:
            raise ValueError("sequence must be >= 1 (1-based ordering).")
        return value

    @field_validator("estimated_weeks", mode="before")
    @classmethod
    def estimated_weeks_must_be_positive(cls, value: Optional[int]) -> Optional[int]:
        """Validate estimated_weeks if provided.

        Args:
            value: Raw weeks value or ``None``.

        Returns:
            Validated positive integer or ``None``.
        """
        if value is None:
            return value
        value = int(value)
        if value < 1:
            raise ValueError("estimated_weeks must be >= 1.")
        return value


# ─────────────────────────────────────────────────────────────────────────────
# Response — full row serialisation for single-resource endpoints
# ─────────────────────────────────────────────────────────────────────────────


class LearningPathResponse(BaseModel):
    """Full learning path record returned by the API.

    ``ConfigDict(from_attributes=True)`` enables direct coercion from a
    ``LearningPath`` ORM instance::

        orm_obj = db.get(LearningPath, lp_id)
        return LearningPathResponse.model_validate(orm_obj)

    Attributes:
        id: UUID primary key.
        profession_id: UUID of the owning Profession.
        skill_id: UUID of the linked Skill.
        sequence: Step number within the profession path.
        estimated_weeks: Estimated weeks to complete this step.
        is_required: Whether this step is mandatory.
        created_at: UTC creation timestamp.
        updated_at: UTC last-modification timestamp.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="UUID primary key.")
    profession_id: uuid.UUID = Field(..., description="UUID of the owning Profession.")
    skill_id: uuid.UUID = Field(..., description="UUID of the linked Skill.")
    sequence: int = Field(..., description="1-based step number.")
    estimated_weeks: int = Field(..., description="Estimated weeks for this step.")
    is_required: bool = Field(..., description="True = mandatory for path completion.")
    created_at: datetime = Field(..., description="UTC creation timestamp.")
    updated_at: datetime = Field(..., description="UTC last-modified timestamp.")


# ─────────────────────────────────────────────────────────────────────────────
# List response — slim read schema for collection endpoints
# ─────────────────────────────────────────────────────────────────────────────


class LearningPathListResponse(BaseModel):
    """Slim learning path record for list / ordered-path endpoints.

    Omits timestamps to reduce payload size for collection responses.
    Used by ``GET /api/v1/learning-paths?profession_id=...`` which returns
    the full ordered sequence for a profession.

    Attributes:
        id: UUID primary key.
        profession_id: UUID of the owning Profession.
        skill_id: UUID of the linked Skill.
        sequence: Step number within the profession path.
        estimated_weeks: Estimated weeks for this step.
        is_required: Whether this step is mandatory.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="UUID primary key.")
    profession_id: uuid.UUID = Field(..., description="UUID of the owning Profession.")
    skill_id: uuid.UUID = Field(..., description="UUID of the linked Skill.")
    sequence: int = Field(..., description="1-based step number.")
    estimated_weeks: int = Field(..., description="Estimated weeks for this step.")
    is_required: bool = Field(..., description="True = mandatory.")
