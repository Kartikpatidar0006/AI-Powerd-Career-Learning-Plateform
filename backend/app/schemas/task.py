"""
backend/app/schemas/task.py
=============================
Pydantic v2 schemas for the Task Engine feature.

This module defines request and response contracts for two domains:

  Tasks
  -----
  ``TaskCreate``        — request body for creating a new task.
  ``TaskUpdate``        — request body for partial task updates (PATCH).
  ``TaskResponse``      — single task in API responses.
  ``TaskListResponse``  — paginated list of tasks.

  Task Submissions
  ----------------
  ``TaskSubmissionCreate``   — request body when a learner submits work.
  ``TaskSubmissionResponse`` — single submission in API responses.
  ``TaskSubmissionListResponse`` — paginated list of submissions.

  Enums
  -----
  ``TaskDifficulty``    — Easy | Medium | Hard.
  ``SubmissionStatus``  — Pending | Submitted | Reviewed.

Design notes:
  - ``ConfigDict(from_attributes=True)`` enables ORM → Pydantic conversion.
  - ``TaskSubmissionCreate`` requires at least one deliverable field.
  - ``TaskUpdate`` makes all fields optional (PATCH semantics).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import Self


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────


class TaskDifficulty(str, Enum):
    """Allowed difficulty levels for a ``Task``."""

    EASY = "Easy"
    MEDIUM = "Medium"
    HARD = "Hard"


class SubmissionStatus(str, Enum):
    """Allowed lifecycle statuses for a ``TaskSubmission``."""

    PENDING = "Pending"
    SUBMITTED = "Submitted"
    REVIEWED = "Reviewed"


# ─────────────────────────────────────────────────────────────────────────────
# Task schemas
# ─────────────────────────────────────────────────────────────────────────────


class TaskCreate(BaseModel):
    """Request body for ``POST /api/v1/tasks/`` — create a new task.

    Attributes:
        title: Human-readable task title (1–500 chars).
        description: Optional Markdown description.
        instructions: Optional step-by-step instructions.
        difficulty: Difficulty level (defaults to Medium).
        estimated_minutes: Expected completion time in minutes (>= 1).
        order_no: 1-based position within the parent roadmap step.
        is_active: Visibility flag (defaults to True).
        roadmap_step_id: UUID of the parent ``RoadmapStep``.

    Example JSON::

        {
            "title": "Build a REST API with FastAPI",
            "description": "Create a CRUD API...",
            "difficulty": "Medium",
            "estimated_minutes": 120,
            "order_no": 1,
            "roadmap_step_id": "a1b2c3d4-..."
        }
    """

    title: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Human-readable task title.",
        examples=["Build a REST API with FastAPI"],
    )
    description: Optional[str] = Field(
        None,
        description="Optional Markdown description of the task.",
        examples=["Create a CRUD API using FastAPI with proper validation."],
    )
    instructions: Optional[str] = Field(
        None,
        description="Optional step-by-step instructions for the learner.",
    )
    difficulty: TaskDifficulty = Field(
        TaskDifficulty.MEDIUM,
        description="Difficulty level: Easy, Medium, or Hard.",
        examples=["Medium"],
    )
    estimated_minutes: int = Field(
        60,
        ge=1,
        description="Expected completion time in minutes. Must be >= 1.",
        examples=[120],
    )
    order_no: int = Field(
        1,
        ge=1,
        description="1-based position within the parent roadmap step.",
        examples=[1],
    )
    is_active: bool = Field(
        True,
        description="Visibility flag. False hides the task from learners.",
    )
    roadmap_step_id: uuid.UUID = Field(
        ...,
        description="UUID of the parent RoadmapStep.",
    )


class TaskUpdate(BaseModel):
    """Request body for ``PATCH /api/v1/tasks/{id}`` — partial update.

    All fields are optional.  Only non-``None`` fields are applied.

    Attributes:
        title: Updated task title.
        description: Updated description.
        instructions: Updated instructions.
        difficulty: Updated difficulty level.
        estimated_minutes: Updated estimated time.
        order_no: Updated ordering position.
        is_active: Updated visibility flag.
    """

    title: Optional[str] = Field(
        None, min_length=1, max_length=500,
        description="Updated task title.",
    )
    description: Optional[str] = Field(
        None, description="Updated description.",
    )
    instructions: Optional[str] = Field(
        None, description="Updated instructions.",
    )
    difficulty: Optional[TaskDifficulty] = Field(
        None, description="Updated difficulty level.",
    )
    estimated_minutes: Optional[int] = Field(
        None, ge=1, description="Updated estimated time in minutes.",
    )
    order_no: Optional[int] = Field(
        None, ge=1, description="Updated ordering position.",
    )
    is_active: Optional[bool] = Field(
        None, description="Updated visibility flag.",
    )


class TaskResponse(BaseModel):
    """Single task representation returned by the API.

    Attributes:
        id: UUID primary key.
        title: Task title.
        description: Markdown description (may be null).
        instructions: Step-by-step instructions (may be null).
        difficulty: Difficulty level string.
        estimated_minutes: Expected completion time in minutes.
        order_no: Position within the parent roadmap step.
        is_active: Visibility flag.
        roadmap_step_id: UUID of the parent RoadmapStep.
        created_at: Creation timestamp.
        updated_at: Last modification timestamp.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: Optional[str]
    instructions: Optional[str]
    difficulty: str
    estimated_minutes: int
    order_no: int
    is_active: bool
    roadmap_step_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    """Paginated list of tasks.

    Attributes:
        items: List of ``TaskResponse`` objects.
        total: Total number of matching records (before pagination).
        skip: Number of records skipped (offset).
        limit: Maximum number of records returned.
    """

    items: list[TaskResponse]
    total: int
    skip: int
    limit: int


# ─────────────────────────────────────────────────────────────────────────────
# TaskSubmission schemas
# ─────────────────────────────────────────────────────────────────────────────


class TaskSubmissionCreate(BaseModel):
    """Request body for ``POST /api/v1/tasks/{task_id}/submit``.

    At least one of ``github_url``, ``submission_text``, or ``file_url``
    must be provided — empty submissions are not allowed.

    Attributes:
        github_url: Optional URL to a GitHub repository.
        submission_text: Optional free-text answer or notes.
        file_url: Optional URL to an uploaded file.

    Example JSON::

        {
            "github_url": "https://github.com/user/project",
            "submission_text": "I implemented the API with..."
        }
    """

    github_url: Optional[str] = Field(
        None,
        max_length=2000,
        description="URL to the student's GitHub repository.",
        examples=["https://github.com/user/project"],
    )
    submission_text: Optional[str] = Field(
        None,
        description="Free-text answer, notes, or explanation.",
        examples=["I implemented the REST API using FastAPI with..."],
    )
    file_url: Optional[str] = Field(
        None,
        max_length=2000,
        description="URL to an uploaded file (S3 or local storage).",
    )

    @model_validator(mode="after")
    def at_least_one_deliverable(self) -> Self:
        """Ensure at least one deliverable field is provided."""
        if not self.github_url and not self.submission_text and not self.file_url:
            raise ValueError(
                "At least one of github_url, submission_text, or file_url "
                "must be provided."
            )
        return self


class TaskSubmissionResponse(BaseModel):
    """Single submission representation returned by the API.

    Attributes:
        id: UUID primary key.
        user_id: UUID of the submitting user.
        task_id: UUID of the submitted task.
        github_url: GitHub repository URL (may be null).
        submission_text: Free-text answer (may be null).
        file_url: Uploaded file URL (may be null).
        status: Lifecycle status string.
        submitted_at: Submission creation timestamp.
        updated_at: Last modification timestamp.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    task_id: uuid.UUID
    github_url: Optional[str]
    submission_text: Optional[str]
    file_url: Optional[str]
    status: str
    submitted_at: datetime
    updated_at: datetime


class TaskSubmissionListResponse(BaseModel):
    """Paginated list of task submissions.

    Attributes:
        items: List of ``TaskSubmissionResponse`` objects.
        total: Total number of matching records (before pagination).
        skip: Number of records skipped (offset).
        limit: Maximum number of records returned.
    """

    items: list[TaskSubmissionResponse]
    total: int
    skip: int
    limit: int
