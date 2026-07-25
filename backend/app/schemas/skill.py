"""
backend/app/schemas/skill.py
==============================
Pydantic v2 schemas for the Skill domain.

Schema hierarchy
----------------
::

  SkillBase          — shared validated fields (name, description, difficulty, …)
    └── SkillCreate  — write schema: all required fields for INSERT
    └── SkillUpdate  — PATCH schema: all fields optional

  SkillResponse      — read schema: full row → JSON response
  SkillListResponse  — slim read schema for list endpoints

Design notes
------------
- ``difficulty`` is validated against the ``DifficultyLevel`` string enum
  (``'Beginner'``, ``'Intermediate'``, ``'Advanced'``) on both create and update.
- ``profession_id`` is a required UUID FK on ``SkillCreate`` and read-only
  (immutable) on ``SkillUpdate`` — skills cannot be reassigned to a different
  profession after creation.
- ``SkillResponse`` uses ``ConfigDict(from_attributes=True)`` for direct
  ORM → schema coercion.
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


class DifficultyLevel(str, Enum):
    """Allowed difficulty levels for a skill.

    Inheriting from ``str`` makes the enum JSON-serialisable without extra
    configuration — FastAPI serialises it as the plain string value.
    """

    BEGINNER = "Beginner"
    INTERMEDIATE = "Intermediate"
    ADVANCED = "Advanced"


# ─────────────────────────────────────────────────────────────────────────────
# Base — shared validated fields
# ─────────────────────────────────────────────────────────────────────────────


class SkillBase(BaseModel):
    """Shared, validated fields for both request and response schemas.

    ``SkillBase`` is never used directly as a request or response body —
    it is a mixin that keeps ``SkillCreate`` and ``SkillUpdate`` DRY.

    Attributes:
        name: Human-readable skill name (e.g. ``"Python"``, ``"React"``).
            1–255 characters, leading/trailing whitespace is stripped.
        description: Optional Markdown description of the skill.
        difficulty: Categorical difficulty — must be one of ``'Beginner'``,
            ``'Intermediate'``, or ``'Advanced'``.
        category: Optional grouping category (e.g. ``"Programming"``).
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable skill name.",
        examples=["Python", "React", "Data Structures"],
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional Markdown description of the skill.",
        examples=["A high-level, general-purpose programming language…"],
    )
    difficulty: DifficultyLevel = Field(
        ...,
        description="Difficulty level: 'Beginner', 'Intermediate', or 'Advanced'.",
        examples=["Intermediate"],
    )
    category: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Grouping category e.g. 'Programming', 'Soft Skills', 'DevOps'.",
        examples=["Programming"],
    )

    @field_validator("name", mode="before")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        """Ensure name is not blank after stripping whitespace.

        Args:
            value: Raw name string from the request body.

        Returns:
            Stripped, non-empty name string.

        Raises:
            ValueError: If the name is blank after stripping.
        """
        stripped = str(value).strip()
        if not stripped:
            raise ValueError("name must not be blank.")
        return stripped


# ─────────────────────────────────────────────────────────────────────────────
# Create — write schema for POST /skills
# ─────────────────────────────────────────────────────────────────────────────


class SkillCreate(SkillBase):
    """Request body for creating a new skill (``POST /api/v1/skills``).

    Inherits all validated fields from ``SkillBase``.  ``profession_id`` is
    required — every skill must belong to exactly one profession.

    Example JSON::

        {
            "name": "Python",
            "description": "A high-level programming language…",
            "difficulty": "Intermediate",
            "category": "Programming",
            "profession_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        }
    """

    profession_id: uuid.UUID = Field(
        ...,
        description="UUID of the Profession this skill belongs to.",
        examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Update — PATCH schema: all fields optional
# ─────────────────────────────────────────────────────────────────────────────


class SkillUpdate(BaseModel):
    """Request body for a partial skill update (``PATCH /api/v1/skills/{id}``).

    All fields are optional — only supplied fields are applied.  ``None``
    means "leave unchanged".

    ``profession_id`` is intentionally excluded — skills cannot be
    re-parented after creation.

    Example JSON (change only the difficulty)::

        { "difficulty": "Advanced" }
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="New skill name.",
    )
    description: Optional[str] = Field(
        default=None,
        description="New description.",
    )
    difficulty: Optional[DifficultyLevel] = Field(
        default=None,
        description="New difficulty level.",
    )
    category: Optional[str] = Field(
        default=None,
        max_length=100,
        description="New category.",
    )

    @field_validator("name", mode="before")
    @classmethod
    def name_must_not_be_blank(cls, value: Optional[str]) -> Optional[str]:
        """Ensure name is not blank after stripping if provided.

        Args:
            value: Raw name string or ``None``.

        Returns:
            Stripped, non-empty name string, or ``None``.

        Raises:
            ValueError: If provided but blank after stripping.
        """
        if value is None:
            return value
        stripped = str(value).strip()
        if not stripped:
            raise ValueError("name must not be blank.")
        return stripped


# ─────────────────────────────────────────────────────────────────────────────
# Response — full row serialisation for single-resource endpoints
# ─────────────────────────────────────────────────────────────────────────────


class SkillResponse(BaseModel):
    """Full skill record returned by the API.

    ``ConfigDict(from_attributes=True)`` enables direct coercion from a
    ``Skill`` ORM instance::

        orm_obj = db.get(Skill, skill_id)
        return SkillResponse.model_validate(orm_obj)

    Attributes:
        id: UUID primary key.
        name: Skill display name.
        description: Markdown description (or ``None``).
        difficulty: Difficulty level string.
        category: Grouping category (or ``None``).
        profession_id: UUID of the owning Profession.
        created_at: UTC creation timestamp.
        updated_at: UTC last-modification timestamp.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="UUID primary key.")
    name: str = Field(..., description="Skill display name.")
    description: Optional[str] = Field(default=None, description="Markdown description.")
    difficulty: str = Field(..., description="Difficulty level.")
    category: Optional[str] = Field(default=None, description="Grouping category.")
    profession_id: uuid.UUID = Field(..., description="UUID of the owning Profession.")
    created_at: datetime = Field(..., description="UTC creation timestamp.")
    updated_at: datetime = Field(..., description="UTC last-modified timestamp.")


# ─────────────────────────────────────────────────────────────────────────────
# List response — slim read schema for collection endpoints
# ─────────────────────────────────────────────────────────────────────────────


class SkillListResponse(BaseModel):
    """Slim skill record for list endpoints.

    Used as ``response_model`` for ``GET /api/v1/skills`` to keep collection
    responses lightweight.  Omits ``description`` which can be large.
    Clients fetch the full record from ``GET /api/v1/skills/{id}`` when
    they need ``description``.

    Attributes:
        id: UUID primary key.
        name: Skill display name.
        difficulty: Difficulty level string.
        category: Grouping category (or ``None``).
        profession_id: UUID of the owning Profession.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="UUID primary key.")
    name: str = Field(..., description="Skill display name.")
    difficulty: str = Field(..., description="Difficulty level.")
    category: Optional[str] = Field(default=None, description="Grouping category.")
    profession_id: uuid.UUID = Field(..., description="UUID of the owning Profession.")
