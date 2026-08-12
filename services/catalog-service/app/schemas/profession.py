"""
backend/app/schemas/profession.py
===================================
Pydantic v2 schemas for the Profession domain.

Schema hierarchy
----------------
::

  ProfessionBase          — shared validated fields (name, slug, …)
    └── ProfessionCreate  — write schema: all required fields for INSERT
    └── ProfessionUpdate  — PATCH schema: all fields optional

  ProfessionResponse      — read schema: full row → JSON response
  ProfessionListResponse  — slim read schema for list endpoints

Design notes
------------
- ``slug`` is always normalised to lowercase + hyphens via a validator in
  ``ProfessionCreate`` and ``ProfessionUpdate``.
- ``required_skills`` and ``roadmap`` are typed as ``list[str]`` and ``dict``
  respectively — match the JSONB column defaults in the ORM model.
- ``ProfessionResponse`` uses ``ConfigDict(from_attributes=True)`` for
  direct ORM → schema coercion.
- No business logic, no database access — pure data contracts.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _normalise_slug(value: str) -> str:
    """Convert an arbitrary string to a URL-safe slug.

    Lowercases, replaces whitespace / underscores / dots with hyphens, and
    strips leading / trailing hyphens.

    Args:
        value: Raw string input.

    Returns:
        Slug-safe lowercase string.
    """
    slug = value.strip().lower()
    slug = re.sub(r"[\s_\.]+", "-", slug)
    slug = re.sub(r"[^a-z0-9\-]", "", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug


# ─────────────────────────────────────────────────────────────────────────────
# Base — shared validated fields
# ─────────────────────────────────────────────────────────────────────────────


class ProfessionBase(BaseModel):
    """Shared, validated fields for both request and response schemas.

    ``ProfessionBase`` is never used directly as a request or response body —
    it is a mixin that keeps ``ProfessionCreate`` and ``ProfessionUpdate`` DRY.

    Attributes:
        name: Human-readable profession name (e.g. "Machine Learning Engineer").
            1–255 characters.
        slug: URL-safe lowercase identifier (e.g. "machine-learning-engineer").
            Auto-normalised by the ``normalise_slug`` validator.
        description: Optional Markdown description.
        category: Optional grouping category (e.g. "Engineering").
        average_salary: Indicative annual salary in USD. Must be >= 0 if
            provided.
        growth_rate: Projected YoY growth percentage. Must be between -100
            and 10,000 if provided.
        required_skills: Ordered list of required skill strings.
        roadmap: Arbitrary structured JSON representing the learning roadmap.
        is_active: Whether the profession is visible to learners.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable profession name.",
        examples=["Machine Learning Engineer"],
    )
    slug: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="URL-safe lowercase identifier (auto-normalised).",
        examples=["machine-learning-engineer"],
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional Markdown description of the profession.",
        examples=["Machine learning engineers design and build ML systems…"],
    )
    category: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Grouping category e.g. 'Engineering', 'Design'.",
        examples=["Engineering"],
    )
    average_salary: Optional[float] = Field(
        default=None,
        ge=0,
        description="Indicative annual salary in USD. Omit if unknown.",
        examples=[145000.00],
    )
    growth_rate: Optional[float] = Field(
        default=None,
        ge=-100,
        le=10000,
        description="Projected YoY growth rate (%). Omit if unknown.",
        examples=[22.5],
    )
    required_skills: list[str] = Field(
        default_factory=list,
        description="Ordered list of required skill strings.",
        examples=[["Python", "Machine Learning", "PyTorch"]],
    )
    roadmap: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured JSON learning roadmap. Schema is flexible.",
        examples=[{"beginner": ["Python basics"], "intermediate": ["ML theory"]}],
    )
    is_active: bool = Field(
        default=True,
        description="True = visible to learners. False = hidden / soft-deleted.",
        examples=[True],
    )

    @field_validator("slug", mode="before")
    @classmethod
    def normalise_slug(cls, value: str) -> str:
        """Lowercase and slugify the slug value before validation.

        Args:
            value: Raw slug string from the request body.

        Returns:
            Normalised slug string.

        Raises:
            ValueError: If the normalised slug is empty.
        """
        normalised = _normalise_slug(str(value))
        if not normalised:
            raise ValueError("slug must contain at least one alphanumeric character.")
        return normalised

    @field_validator("required_skills", mode="before")
    @classmethod
    def skills_must_be_strings(cls, value: list) -> list[str]:
        """Ensure every item in required_skills is a non-empty string.

        Args:
            value: Raw list from the request body.

        Returns:
            List of stripped, non-empty strings.

        Raises:
            ValueError: If any item is empty after stripping.
        """
        result = []
        for i, item in enumerate(value):
            s = str(item).strip()
            if not s:
                raise ValueError(f"required_skills[{i}] must not be empty.")
            result.append(s)
        return result


# ─────────────────────────────────────────────────────────────────────────────
# Create — write schema for POST /professions
# ─────────────────────────────────────────────────────────────────────────────


class ProfessionCreate(ProfessionBase):
    """Request body for creating a new profession (``POST /api/v1/professions``).

    Inherits all validated fields from ``ProfessionBase``.  All fields that
    are required for a meaningful profession record must be present.

    Example JSON::

        {
            "name": "Machine Learning Engineer",
            "slug": "machine-learning-engineer",
            "description": "Designs and deploys ML models…",
            "category": "Engineering",
            "average_salary": 145000,
            "growth_rate": 22.5,
            "required_skills": ["Python", "PyTorch", "Statistics"],
            "roadmap": {"beginner": ["Python basics"]},
            "is_active": true
        }
    """


# ─────────────────────────────────────────────────────────────────────────────
# Update — PATCH schema: all fields optional
# ─────────────────────────────────────────────────────────────────────────────


class ProfessionUpdate(BaseModel):
    """Request body for a partial profession update (``PATCH /api/v1/professions/{id}``).

    All fields are optional — only supplied fields are applied.  ``None``
    means "leave unchanged".

    Example JSON (change only the salary)::

        { "average_salary": 155000 }
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    name: Optional[str] = Field(
        default=None, min_length=1, max_length=255, description="New name.",
    )
    slug: Optional[str] = Field(
        default=None, min_length=1, max_length=255, description="New slug.",
    )
    description: Optional[str] = Field(default=None, description="New description.")
    category: Optional[str] = Field(
        default=None, max_length=100, description="New category.",
    )
    average_salary: Optional[float] = Field(
        default=None, ge=0, description="New average salary in USD.",
    )
    growth_rate: Optional[float] = Field(
        default=None, ge=-100, le=10000, description="New growth rate %.",
    )
    required_skills: Optional[list[str]] = Field(
        default=None, description="Replacement required_skills list.",
    )
    roadmap: Optional[dict[str, Any]] = Field(
        default=None, description="Replacement roadmap object.",
    )
    is_active: Optional[bool] = Field(
        default=None, description="New active status.",
    )

    @field_validator("slug", mode="before")
    @classmethod
    def normalise_slug(cls, value: Optional[str]) -> Optional[str]:
        """Normalise slug if provided.

        Args:
            value: Raw slug string or ``None``.

        Returns:
            Normalised slug or ``None``.
        """
        if value is None:
            return value
        normalised = _normalise_slug(str(value))
        if not normalised:
            raise ValueError("slug must contain at least one alphanumeric character.")
        return normalised

    @field_validator("required_skills", mode="before")
    @classmethod
    def skills_must_be_strings(cls, value: Optional[list]) -> Optional[list[str]]:
        """Validate skill strings if provided.

        Args:
            value: Raw list or ``None``.

        Returns:
            Validated list of skill strings, or ``None``.
        """
        if value is None:
            return value
        result = []
        for i, item in enumerate(value):
            s = str(item).strip()
            if not s:
                raise ValueError(f"required_skills[{i}] must not be empty.")
            result.append(s)
        return result


# ─────────────────────────────────────────────────────────────────────────────
# Response — full row serialisation for single-resource endpoints
# ─────────────────────────────────────────────────────────────────────────────


class ProfessionResponse(BaseModel):
    """Full profession record returned by the API.

    ``ConfigDict(from_attributes=True)`` enables direct coercion from a
    ``Profession`` ORM instance::

        orm_obj = db.get(Profession, profession_id)
        return ProfessionResponse.model_validate(orm_obj)

    Attributes:
        id: UUID primary key.
        name: Profession display name.
        slug: URL-safe identifier.
        description: Markdown description (or ``None``).
        category: Grouping category (or ``None``).
        average_salary: Annual salary in USD (or ``None``).
        growth_rate: YoY growth rate % (or ``None``).
        required_skills: Ordered skill list.
        roadmap: Learning roadmap JSON.
        is_active: Visibility flag.
        created_at: Creation timestamp.
        updated_at: Last modification timestamp.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="UUID primary key.")
    name: str = Field(..., description="Profession display name.")
    slug: str = Field(..., description="URL-safe identifier.")
    description: Optional[str] = Field(default=None, description="Markdown description.")
    category: Optional[str] = Field(default=None, description="Grouping category.")
    average_salary: Optional[float] = Field(default=None, description="Annual salary (USD).")
    growth_rate: Optional[float] = Field(default=None, description="YoY growth rate %.")
    required_skills: list[str] = Field(default_factory=list, description="Required skills.")
    roadmap: dict[str, Any] = Field(default_factory=dict, description="Learning roadmap.")
    is_active: bool = Field(..., description="Visibility flag.")
    created_at: datetime = Field(..., description="UTC creation timestamp.")
    updated_at: datetime = Field(..., description="UTC last-modified timestamp.")


# ─────────────────────────────────────────────────────────────────────────────
# List response — slim read schema for collection endpoints
# ─────────────────────────────────────────────────────────────────────────────


class ProfessionListResponse(BaseModel):
    """Slim profession record for list endpoints (omits heavy JSON fields).

    Used as ``response_model`` for ``GET /api/v1/professions`` to keep
    collection responses lightweight.  Clients fetch the full response
    from ``GET /api/v1/professions/{id}`` when they need ``roadmap`` /
    ``required_skills``.

    Attributes:
        id: UUID primary key.
        name: Profession display name.
        slug: URL-safe identifier.
        category: Grouping category (or ``None``).
        average_salary: Annual salary in USD (or ``None``).
        growth_rate: YoY growth rate % (or ``None``).
        is_active: Visibility flag.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="UUID primary key.")
    name: str = Field(..., description="Profession display name.")
    slug: str = Field(..., description="URL-safe identifier.")
    category: Optional[str] = Field(default=None, description="Grouping category.")
    average_salary: Optional[float] = Field(default=None, description="Annual salary (USD).")
    growth_rate: Optional[float] = Field(default=None, description="YoY growth rate %.")
    is_active: bool = Field(..., description="Visibility flag.")
