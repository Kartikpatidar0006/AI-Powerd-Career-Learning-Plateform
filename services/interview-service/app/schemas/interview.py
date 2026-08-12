"""
backend/app/schemas/interview.py
=================================
Pydantic v2 schemas for the Interview Scheduling feature.

This module defines request and response contracts for interviews:

  InterviewStatus       — Enum: 'Scheduled' | 'Completed' | 'Cancelled' | 'Missed'.
  InterviewResponse     — Single interview representation in API responses.
  InterviewListResponse — Paginated list of interviews.

Design notes:
  - ``ConfigDict(from_attributes=True)`` enables ORM → Pydantic conversion.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class InterviewStatus(str, Enum):
    """Allowed lifecycle statuses for an ``Interview``."""

    SCHEDULED = "Scheduled"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    MISSED = "Missed"


class InterviewResponse(BaseModel):
    """API response schema representing interview details.

    Attributes:
        id: UUID primary key.
        user_id: UUID of the learner.
        task_id: UUID of the associated task.
        scheduled_at: Scheduled start time in UTC.
        duration_minutes: Interview duration in minutes.
        status: Lifecycle status string.
        meeting_link: Meeting room URL (may be null).
        created_at: Creation timestamp.
        updated_at: Last modification timestamp.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    task_id: uuid.UUID
    scheduled_at: datetime
    duration_minutes: int
    status: str
    meeting_link: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class InterviewListResponse(BaseModel):
    """Paginated list of interviews.

    Attributes:
        items: List of ``InterviewResponse`` objects.
        total: Total number of matching records before pagination.
        skip: Pagination offset.
        limit: Maximum results returned.
    """

    items: list[InterviewResponse]
    total: int
    skip: int
    limit: int
