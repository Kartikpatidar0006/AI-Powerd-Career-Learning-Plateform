"""
backend/app/schemas/interview_feedback.py
===========================================
Pydantic v2 schemas for the Interview Evaluation feature.

This module defines request and response schemas for interview evaluation feedback:

  InterviewFeedbackResponse     — Single interview evaluation feedback representation.
  InterviewFeedbackListResponse — Paginated list of interview evaluation feedback records.

Design notes:
  - ``ConfigDict(from_attributes=True)`` enables ORM → Pydantic conversion.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class InterviewFeedbackResponse(BaseModel):
    """API response schema representing interview evaluation feedback details.

    Attributes:
        id: UUID primary key.
        interview_id: UUID of evaluated Interview.
        overall_score: Aggregated overall score (0–100).
        technical_score: Technical competency score (0–100).
        communication_score: Communication clarity score (0–100).
        confidence_score: Confidence & delivery score (0–100).
        problem_solving_score: Problem-solving score (0–100).
        strengths: Markdown text describing strengths.
        weaknesses: Markdown text describing weaknesses.
        suggestions: Markdown text providing actionable advice.
        recommendation: Hiring recommendation text (e.g. 'Strong Hire').
        status: Evaluation status ('Pending' or 'Generated').
        created_at: Creation timestamp.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    interview_id: uuid.UUID
    overall_score: int = Field(..., ge=0, le=100)
    technical_score: int = Field(..., ge=0, le=100)
    communication_score: int = Field(..., ge=0, le=100)
    confidence_score: int = Field(..., ge=0, le=100)
    problem_solving_score: int = Field(..., ge=0, le=100)
    strengths: Optional[str] = None
    weaknesses: Optional[str] = None
    suggestions: Optional[str] = None
    recommendation: Optional[str] = None
    status: str
    created_at: datetime


class InterviewFeedbackListResponse(BaseModel):
    """Paginated list of interview evaluation feedback records.

    Attributes:
        items: List of ``InterviewFeedbackResponse`` objects.
        total: Total count before pagination.
        skip: Offset skipped.
        limit: Limit count.
    """

    items: list[InterviewFeedbackResponse]
    total: int
    skip: int
    limit: int
