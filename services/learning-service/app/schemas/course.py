"""
backend/app/schemas/course.py
==============================
Pydantic v2 schemas for the Course domain.

Schema hierarchy
----------------
::

  CourseBase          — shared validated fields (title, difficulty, course_url, …)
    └── CourseCreate  — write schema: all required fields for INSERT
    └── CourseUpdate  — PATCH schema: all fields optional

  CourseResponse      — read schema: full row → JSON response
  CourseListResponse  — slim read schema for list endpoints

Design notes
------------
- ``difficulty`` is validated against the ``CourseDifficultyLevel`` string enum
  (``'Beginner'``, ``'Intermediate'``, ``'Advanced'``) on both create and update.
- ``skill_id`` is a required UUID FK on ``CourseCreate`` and read-only
  (immutable) on ``CourseUpdate`` — courses cannot be reassigned to a different
  skill after creation.
- ``rating`` is validated to be in the range 0.00–5.00.
- ``course_url`` is validated to be a non-blank URL string.
- ``CourseResponse`` uses ``ConfigDict(from_attributes=True)`` for direct
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


class CourseDifficultyLevel(str, Enum):
    """Allowed difficulty levels for a course.

    Inheriting from ``str`` makes the enum JSON-serialisable without extra
    configuration — FastAPI serialises it as the plain string value.
    """

    BEGINNER = "Beginner"
    INTERMEDIATE = "Intermediate"
    ADVANCED = "Advanced"


# ─────────────────────────────────────────────────────────────────────────────
# Base — shared validated fields
# ─────────────────────────────────────────────────────────────────────────────


class CourseBase(BaseModel):
    """Shared, validated fields for both request and response schemas.

    ``CourseBase`` is never used directly as a request or response body —
    it is a mixin that keeps ``CourseCreate`` and ``CourseUpdate`` DRY.

    Attributes:
        title: Human-readable course title (e.g. ``"Python for Everybody"``).
            1–500 characters, leading/trailing whitespace is stripped.
        description: Optional Markdown description of the course.
        provider: Optional publishing platform (e.g. ``"Coursera"``).
        course_url: Canonical URL to the course page. Required, non-blank.
        thumbnail_url: Optional URL to the course cover image / thumbnail.
        difficulty: Categorical difficulty — must be one of ``'Beginner'``,
            ``'Intermediate'``, or ``'Advanced'``.
        duration_hours: Estimated hours to complete. Must be > 0 if provided.
        is_free: Whether the course is free of charge.
        rating: Average rating 0.00–5.00. ``None`` if not yet rated.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Human-readable course title.",
        examples=["Python for Everybody", "The Complete JavaScript Bootcamp"],
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional Markdown description of the course.",
        examples=["Learn Python from scratch with hands-on projects…"],
    )
    provider: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Publishing platform or instructor (e.g. 'Coursera', 'Udemy').",
        examples=["Coursera", "Udemy", "YouTube"],
    )
    course_url: str = Field(
        ...,
        min_length=1,
        description="Canonical URL to the course page.",
        examples=["https://www.coursera.org/learn/python"],
    )
    thumbnail_url: Optional[str] = Field(
        default=None,
        description="URL to the course cover image / thumbnail.",
        examples=["https://img.example.com/python-thumb.jpg"],
    )
    difficulty: CourseDifficultyLevel = Field(
        ...,
        description="Difficulty level: 'Beginner', 'Intermediate', or 'Advanced'.",
        examples=["Intermediate"],
    )
    duration_hours: Optional[float] = Field(
        default=None,
        gt=0,
        description="Estimated hours to complete the course. Must be > 0.",
        examples=[12.5, 40.0],
    )
    is_free: bool = Field(
        default=False,
        description="True if the course is free of charge.",
        examples=[False, True],
    )
    rating: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=5.0,
        description="Average community rating on a 0.00–5.00 scale.",
        examples=[4.75, 3.5],
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

    @field_validator("course_url", mode="before")
    @classmethod
    def course_url_must_not_be_blank(cls, value: str) -> str:
        """Ensure course_url is not blank after stripping whitespace.

        Args:
            value: Raw URL string from the request body.

        Returns:
            Stripped, non-empty URL string.

        Raises:
            ValueError: If the URL is blank after stripping.
        """
        stripped = str(value).strip()
        if not stripped:
            raise ValueError("course_url must not be blank.")
        return stripped


# ─────────────────────────────────────────────────────────────────────────────
# Create — write schema for POST /courses
# ─────────────────────────────────────────────────────────────────────────────


class CourseCreate(CourseBase):
    """Request body for creating a new course (``POST /api/v1/courses``).

    Inherits all validated fields from ``CourseBase``.  ``skill_id`` is
    required — every course must belong to exactly one skill.

    Example JSON::

        {
            "title": "Python for Everybody",
            "description": "Learn Python from scratch…",
            "provider": "Coursera",
            "course_url": "https://www.coursera.org/learn/python",
            "thumbnail_url": "https://img.example.com/python-thumb.jpg",
            "difficulty": "Beginner",
            "duration_hours": 24.0,
            "is_free": false,
            "rating": 4.8,
            "skill_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        }
    """

    skill_id: uuid.UUID = Field(
        ...,
        description="UUID of the Skill this course belongs to.",
        examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Update — PATCH schema: all fields optional
# ─────────────────────────────────────────────────────────────────────────────


class CourseUpdate(BaseModel):
    """Request body for a partial course update (``PATCH /api/v1/courses/{id}``).

    All fields are optional — only supplied fields are applied.  ``None``
    means "leave unchanged".

    ``skill_id`` is intentionally excluded — courses cannot be
    re-parented after creation.

    Example JSON (change only the rating)::

        { "rating": 4.9 }
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    title: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=500,
        description="New course title.",
    )
    description: Optional[str] = Field(
        default=None,
        description="New description.",
    )
    provider: Optional[str] = Field(
        default=None,
        max_length=255,
        description="New provider name.",
    )
    course_url: Optional[str] = Field(
        default=None,
        min_length=1,
        description="New canonical course URL.",
    )
    thumbnail_url: Optional[str] = Field(
        default=None,
        description="New thumbnail URL.",
    )
    difficulty: Optional[CourseDifficultyLevel] = Field(
        default=None,
        description="New difficulty level.",
    )
    duration_hours: Optional[float] = Field(
        default=None,
        gt=0,
        description="New estimated duration in hours.",
    )
    is_free: Optional[bool] = Field(
        default=None,
        description="New free/paid status.",
    )
    rating: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=5.0,
        description="New average rating (0.00–5.00).",
    )

    @field_validator("title", mode="before")
    @classmethod
    def title_must_not_be_blank(cls, value: Optional[str]) -> Optional[str]:
        """Ensure title is not blank after stripping if provided.

        Args:
            value: Raw title string or ``None``.

        Returns:
            Stripped, non-empty title string, or ``None``.

        Raises:
            ValueError: If provided but blank after stripping.
        """
        if value is None:
            return value
        stripped = str(value).strip()
        if not stripped:
            raise ValueError("title must not be blank.")
        return stripped

    @field_validator("course_url", mode="before")
    @classmethod
    def course_url_must_not_be_blank(cls, value: Optional[str]) -> Optional[str]:
        """Ensure course_url is not blank after stripping if provided.

        Args:
            value: Raw URL string or ``None``.

        Returns:
            Stripped, non-empty URL string, or ``None``.

        Raises:
            ValueError: If provided but blank after stripping.
        """
        if value is None:
            return value
        stripped = str(value).strip()
        if not stripped:
            raise ValueError("course_url must not be blank.")
        return stripped


# ─────────────────────────────────────────────────────────────────────────────
# Response — full row serialisation for single-resource endpoints
# ─────────────────────────────────────────────────────────────────────────────


class CourseResponse(BaseModel):
    """Full course record returned by the API.

    ``ConfigDict(from_attributes=True)`` enables direct coercion from a
    ``Course`` ORM instance::

        orm_obj = db.get(Course, course_id)
        return CourseResponse.model_validate(orm_obj)

    Attributes:
        id: UUID primary key.
        title: Course display title.
        description: Markdown description (or ``None``).
        provider: Publishing platform name (or ``None``).
        course_url: Canonical URL to the course.
        thumbnail_url: Cover image URL (or ``None``).
        difficulty: Difficulty level string.
        duration_hours: Estimated hours to complete (or ``None``).
        is_free: Whether the course is free.
        rating: Average rating 0.00–5.00 (or ``None``).
        skill_id: UUID of the owning Skill.
        created_at: UTC creation timestamp.
        updated_at: UTC last-modification timestamp.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="UUID primary key.")
    title: str = Field(..., description="Course display title.")
    description: Optional[str] = Field(default=None, description="Markdown description.")
    provider: Optional[str] = Field(default=None, description="Publishing platform.")
    course_url: str = Field(..., description="Canonical URL to the course.")
    thumbnail_url: Optional[str] = Field(default=None, description="Cover image URL.")
    difficulty: str = Field(..., description="Difficulty level.")
    duration_hours: Optional[float] = Field(default=None, description="Estimated hours.")
    is_free: bool = Field(..., description="Whether the course is free of charge.")
    rating: Optional[float] = Field(default=None, description="Average rating 0–5.")
    skill_id: uuid.UUID = Field(..., description="UUID of the owning Skill.")
    created_at: datetime = Field(..., description="UTC creation timestamp.")
    updated_at: datetime = Field(..., description="UTC last-modified timestamp.")


# ─────────────────────────────────────────────────────────────────────────────
# List response — slim read schema for collection endpoints
# ─────────────────────────────────────────────────────────────────────────────


class CourseListResponse(BaseModel):
    """Slim course record for list endpoints.

    Used as ``response_model`` for ``GET /api/v1/courses`` to keep collection
    responses lightweight.  Omits ``description`` which can be large.
    Clients fetch the full record from ``GET /api/v1/courses/{id}`` when
    they need ``description``.

    Attributes:
        id: UUID primary key.
        title: Course display title.
        provider: Publishing platform name (or ``None``).
        course_url: Canonical URL to the course.
        difficulty: Difficulty level string.
        duration_hours: Estimated hours to complete (or ``None``).
        is_free: Whether the course is free.
        rating: Average rating 0.00–5.00 (or ``None``).
        skill_id: UUID of the owning Skill.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="UUID primary key.")
    title: str = Field(..., description="Course display title.")
    provider: Optional[str] = Field(default=None, description="Publishing platform.")
    course_url: str = Field(..., description="Canonical URL to the course.")
    difficulty: str = Field(..., description="Difficulty level.")
    duration_hours: Optional[float] = Field(default=None, description="Estimated hours.")
    is_free: bool = Field(..., description="Whether the course is free of charge.")
    rating: Optional[float] = Field(default=None, description="Average rating 0–5.")
    skill_id: uuid.UUID = Field(..., description="UUID of the owning Skill.")
