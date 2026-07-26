"""
backend/app/schemas/user_progress.py
======================================
Pydantic v2 schemas for the UserProgress domain.

Schema hierarchy
----------------
::

  UserProgressBase          — shared validated fields
    └── UserProgressCreate  — write schema: required fields for INSERT
    └── UserProgressUpdate  — PATCH schema: all fields optional

  UserProgressResponse      — read schema: full row → JSON response
  UserProgressListResponse  — slim read schema for list endpoints

Design notes
------------
- ``status`` is validated against the ``ProgressStatus`` string enum
  (``'NOT_STARTED'``, ``'IN_PROGRESS'``, ``'COMPLETED'``).
- ``progress_percentage`` is constrained to [0, 100] by Pydantic ``ge``/``le``.
- ``time_spent_minutes`` must be >= 0.
- ``user_id`` and ``skill_id`` are required on ``UserProgressCreate`` and
  read-only (immutable) on ``UserProgressUpdate`` — progress records cannot
  be reassigned to a different user or skill after creation.
- Business rule: if ``progress_percentage`` == 100, ``status`` should be
  ``COMPLETED``.  This is enforced in the service layer, not here — schemas
  are pure data contracts.
- ``UserProgressResponse`` uses ``ConfigDict(from_attributes=True)`` for
  direct ORM → schema coercion.
- No business logic, no database access — pure data contracts.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ─────────────────────────────────────────────────────────────────────────────
# Progress status enum
# ─────────────────────────────────────────────────────────────────────────────


class ProgressStatus(str, Enum):
    """Allowed lifecycle statuses for a user progress record.

    Inheriting from ``str`` makes the enum JSON-serialisable without extra
    configuration — FastAPI serialises it as the plain string value.
    """

    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


# ─────────────────────────────────────────────────────────────────────────────
# Base — shared validated fields
# ─────────────────────────────────────────────────────────────────────────────


class UserProgressBase(BaseModel):
    """Shared, validated fields for both request and response schemas.

    ``UserProgressBase`` is never used directly as a request or response body —
    it is a mixin that keeps ``UserProgressCreate`` and ``UserProgressUpdate``
    DRY.

    Attributes:
        status: Lifecycle status — must be one of ``'NOT_STARTED'``,
            ``'IN_PROGRESS'``, or ``'COMPLETED'``.
        progress_percentage: Integer 0–100 representing completion.
        started_at: UTC timestamp of the learner's first interaction.
        completed_at: UTC timestamp when the skill was completed.
        last_accessed: UTC timestamp of the most recent interaction.
        time_spent_minutes: Cumulative minutes spent on this skill (>= 0).
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    status: ProgressStatus = Field(
        default=ProgressStatus.NOT_STARTED,
        description="Lifecycle status: 'NOT_STARTED', 'IN_PROGRESS', or 'COMPLETED'.",
        examples=["IN_PROGRESS"],
    )
    progress_percentage: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Completion percentage (0–100 inclusive).",
        examples=[0, 50, 100],
    )
    started_at: Optional[datetime] = Field(
        default=None,
        description="UTC timestamp of the learner's first interaction.",
        examples=["2026-01-15T09:00:00Z"],
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="UTC timestamp when the skill was completed (100%).",
        examples=["2026-03-20T17:30:00Z"],
    )
    last_accessed: Optional[datetime] = Field(
        default=None,
        description="UTC timestamp of the most recent interaction.",
        examples=["2026-06-10T14:45:00Z"],
    )
    time_spent_minutes: int = Field(
        default=0,
        ge=0,
        description="Cumulative minutes spent on this skill. Must be >= 0.",
        examples=[0, 120, 480],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Create — write schema for POST /user-progress
# ─────────────────────────────────────────────────────────────────────────────


class UserProgressCreate(UserProgressBase):
    """Request body for creating a new progress record
    (``POST /api/v1/user-progress``).

    Inherits all validated fields from ``UserProgressBase``.  ``user_id``
    and ``skill_id`` are required — every progress record must belong to
    exactly one user and one skill.

    The combination (user_id, skill_id) must be unique — the API will reject
    duplicate progress records for the same user + skill pair.

    Example JSON::

        {
            "user_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "skill_id": "7cb92a33-4812-5671-c4de-3d074e77bfa7",
            "status": "NOT_STARTED",
            "progress_percentage": 0,
            "time_spent_minutes": 0
        }
    """

    user_id: uuid.UUID = Field(
        ...,
        description="UUID of the User this progress record belongs to.",
        examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
    )
    skill_id: uuid.UUID = Field(
        ...,
        description="UUID of the Skill being tracked.",
        examples=["7cb92a33-4812-5671-c4de-3d074e77bfa7"],
    )

    @model_validator(mode="after")
    def completed_at_requires_completed_status(self) -> "UserProgressCreate":
        """Ensure completed_at is only set when status is COMPLETED.

        Args:
            self: The fully initialised model instance.

        Returns:
            The validated model instance.

        Raises:
            ValueError: If ``completed_at`` is set but ``status`` is not
                ``COMPLETED``, or if ``status`` is ``COMPLETED`` but
                ``progress_percentage`` is not 100.
        """
        if self.completed_at is not None and self.status != ProgressStatus.COMPLETED:
            raise ValueError(
                "completed_at can only be set when status is 'COMPLETED'."
            )
        if self.status == ProgressStatus.COMPLETED and self.progress_percentage != 100:
            raise ValueError(
                "progress_percentage must be 100 when status is 'COMPLETED'."
            )
        return self


# ─────────────────────────────────────────────────────────────────────────────
# Update — PATCH schema: all fields optional
# ─────────────────────────────────────────────────────────────────────────────


class UserProgressUpdate(BaseModel):
    """Request body for a partial progress update
    (``PATCH /api/v1/user-progress/{id}``).

    All fields are optional — only supplied fields are applied.  ``None``
    means "leave unchanged".

    ``user_id`` and ``skill_id`` are intentionally excluded — progress records
    cannot be re-parented after creation.

    Example JSON (advance progress to 75%)::

        {
            "status": "IN_PROGRESS",
            "progress_percentage": 75,
            "last_accessed": "2026-07-20T10:00:00Z",
            "time_spent_minutes": 240
        }
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    status: Optional[ProgressStatus] = Field(
        default=None,
        description="New lifecycle status.",
    )
    progress_percentage: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="New completion percentage (0–100).",
    )
    started_at: Optional[datetime] = Field(
        default=None,
        description="Updated first-interaction timestamp.",
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="Updated completion timestamp.",
    )
    last_accessed: Optional[datetime] = Field(
        default=None,
        description="Updated last-access timestamp.",
    )
    time_spent_minutes: Optional[int] = Field(
        default=None,
        ge=0,
        description="New cumulative time in minutes (>= 0).",
    )

    @model_validator(mode="after")
    def validate_completed_consistency(self) -> "UserProgressUpdate":
        """Cross-field consistency checks for COMPLETED status on update.

        When both ``status`` and ``progress_percentage`` are supplied in the
        same request, enforce the COMPLETED ↔ 100% invariant.

        Args:
            self: The fully initialised model instance.

        Returns:
            The validated model instance.

        Raises:
            ValueError: If COMPLETED status is paired with < 100%, or if
                ``completed_at`` is set without COMPLETED status.
        """
        if (
            self.status == ProgressStatus.COMPLETED
            and self.progress_percentage is not None
            and self.progress_percentage != 100
        ):
            raise ValueError(
                "progress_percentage must be 100 when status is 'COMPLETED'."
            )
        if (
            self.completed_at is not None
            and self.status is not None
            and self.status != ProgressStatus.COMPLETED
        ):
            raise ValueError(
                "completed_at can only be set when status is 'COMPLETED'."
            )
        return self


# ─────────────────────────────────────────────────────────────────────────────
# Response — full row serialisation for single-resource endpoints
# ─────────────────────────────────────────────────────────────────────────────


class UserProgressResponse(BaseModel):
    """Full user progress record returned by the API.

    ``ConfigDict(from_attributes=True)`` enables direct coercion from a
    ``UserProgress`` ORM instance::

        orm_obj = db.get(UserProgress, progress_id)
        return UserProgressResponse.model_validate(orm_obj)

    Attributes:
        id: UUID primary key.
        user_id: UUID of the learner.
        skill_id: UUID of the skill being tracked.
        status: Lifecycle status string.
        progress_percentage: Integer 0–100.
        started_at: First-interaction timestamp (or ``None``).
        completed_at: Completion timestamp (or ``None``).
        last_accessed: Most-recent-interaction timestamp (or ``None``).
        time_spent_minutes: Cumulative minutes spent.
        created_at: UTC row-creation timestamp.
        updated_at: UTC last-modification timestamp.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="UUID primary key.")
    user_id: uuid.UUID = Field(..., description="UUID of the learner.")
    skill_id: uuid.UUID = Field(..., description="UUID of the skill.")
    status: str = Field(..., description="Lifecycle status.")
    progress_percentage: int = Field(..., description="Completion percentage 0–100.")
    started_at: Optional[datetime] = Field(
        default=None, description="First-interaction timestamp."
    )
    completed_at: Optional[datetime] = Field(
        default=None, description="Completion timestamp."
    )
    last_accessed: Optional[datetime] = Field(
        default=None, description="Most-recent-interaction timestamp."
    )
    time_spent_minutes: int = Field(..., description="Cumulative minutes spent.")
    created_at: datetime = Field(..., description="UTC creation timestamp.")
    updated_at: datetime = Field(..., description="UTC last-modified timestamp.")


# ─────────────────────────────────────────────────────────────────────────────
# List response — slim read schema for collection endpoints
# ─────────────────────────────────────────────────────────────────────────────


class UserProgressListResponse(BaseModel):
    """Slim progress record for list endpoints.

    Used as ``response_model`` for ``GET /api/v1/user-progress`` to keep
    collection responses lightweight.  Omits detailed timestamp fields.
    Clients fetch the full record from ``GET /api/v1/user-progress/{id}``
    when they need those.

    Attributes:
        id: UUID primary key.
        user_id: UUID of the learner.
        skill_id: UUID of the skill.
        status: Lifecycle status string.
        progress_percentage: Integer 0–100.
        time_spent_minutes: Cumulative minutes spent.
        last_accessed: Most-recent-interaction timestamp (or ``None``).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="UUID primary key.")
    user_id: uuid.UUID = Field(..., description="UUID of the learner.")
    skill_id: uuid.UUID = Field(..., description="UUID of the skill.")
    status: str = Field(..., description="Lifecycle status.")
    progress_percentage: int = Field(..., description="Completion percentage 0–100.")
    time_spent_minutes: int = Field(..., description="Cumulative minutes spent.")
    last_accessed: Optional[datetime] = Field(
        default=None, description="Most-recent-interaction timestamp."
    )
