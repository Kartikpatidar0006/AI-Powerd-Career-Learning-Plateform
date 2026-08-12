"""
backend/app/schemas/task_feedback.py
====================================
Pydantic v2 schemas for the Task Feedback feature.

This module defines data structures for task feedback API responses and list responses:

  FeedbackStatus           — Enum: 'Pending' | 'Generated'.
  TaskFeedbackResponse     — Full feedback representation in API responses.
  TaskFeedbackListResponse — Paginated list of feedback records.

Design notes:
  - ``ConfigDict(from_attributes=True)`` enables ORM → Pydantic conversion.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class FeedbackStatus(str, Enum):
    """Allowed status values for ``TaskFeedback``."""

    PENDING = "Pending"
    GENERATED = "Generated"


class TaskFeedbackResponse(BaseModel):
    """API response schema representing task feedback details.

    Attributes:
        id: UUID primary key.
        submission_id: UUID of the evaluated TaskSubmission.
        overall_score: Overall aggregated score (0–100).
        technical_score: Technical implementation score (0–100).
        logic_score: Algorithm & logic score (0–100).
        code_quality_score: Code quality & style score (0–100).
        strengths: Markdown text describing strengths.
        weaknesses: Markdown text describing weaknesses.
        suggestions: Markdown text providing actionable suggestions.
        status: Evaluation status ('Pending' or 'Generated').
        created_at: Creation timestamp.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    submission_id: uuid.UUID
    overall_score: int = Field(..., ge=0, le=100)
    technical_score: int = Field(..., ge=0, le=100)
    logic_score: int = Field(..., ge=0, le=100)
    code_quality_score: int = Field(..., ge=0, le=100)
    strengths: Optional[str] = None
    weaknesses: Optional[str] = None
    suggestions: Optional[str] = None
    status: str
    created_at: datetime


class TaskFeedbackListResponse(BaseModel):
    """Paginated list of task feedback records.

    Attributes:
        items: List of ``TaskFeedbackResponse`` objects.
        total: Total count before pagination.
        skip: Offset skipped.
        limit: Limit count.
    """

    items: list[TaskFeedbackResponse]
    total: int
    skip: int
    limit: int
