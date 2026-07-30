"""
backend/app/schemas/interview_question.py
==========================================
Pydantic v2 schemas for the Mock Interview Engine feature.

This module defines request and response schemas for interview questions and answers:

  QuestionType                   — Enum: 'Technical' | 'Behavioral'.
  QuestionDifficulty             — Enum: 'Easy' | 'Medium' | 'Hard'.
  InterviewAnswerCreate          — Request payload when submitting a question answer.
  InterviewAnswerResponse        — Response schema representing a student's answer.
  InterviewQuestionResponse      — Response schema representing an interview question.
  InterviewQuestionListResponse  — List of ordered questions for an interview.
  InterviewStartResponse         — Response returned when starting an interview.

Design notes:
  - ``ConfigDict(from_attributes=True)`` enables ORM → Pydantic conversion.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class QuestionType(str, Enum):
    """Allowed question categories."""

    TECHNICAL = "Technical"
    BEHAVIORAL = "Behavioral"


class QuestionDifficulty(str, Enum):
    """Allowed question difficulty levels."""

    EASY = "Easy"
    MEDIUM = "Medium"
    HARD = "Hard"


class InterviewAnswerCreate(BaseModel):
    """Request payload for submitting an answer to an interview question.

    Attributes:
        answer_text: Student's free-text response.
        time_taken_seconds: Time spent answering in seconds (>= 0).
    """

    answer_text: Optional[str] = Field(
        None,
        description="Student's free-text answer or explanation.",
        examples=["I implemented a hash map to achieve O(1) time complexity."],
    )
    time_taken_seconds: int = Field(
        0,
        ge=0,
        description="Time spent answering in seconds. Must be >= 0.",
        examples=[45],
    )


class InterviewAnswerResponse(BaseModel):
    """API response schema for a question answer.

    Attributes:
        id: UUID primary key.
        question_id: UUID of the answered question.
        user_id: UUID of the learner.
        answer_text: Answer text provided (may be null).
        time_taken_seconds: Time spent in seconds.
        created_at: Submission timestamp.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    question_id: uuid.UUID
    user_id: uuid.UUID
    answer_text: Optional[str] = None
    time_taken_seconds: int
    created_at: datetime


class InterviewQuestionResponse(BaseModel):
    """API response schema representing an interview question.

    Attributes:
        id: UUID primary key.
        interview_id: UUID of parent interview.
        question: Question prompt text.
        question_type: Category ('Technical' or 'Behavioral').
        difficulty: Difficulty ('Easy', 'Medium', or 'Hard').
        order_no: 1-based order position.
        created_at: Creation timestamp.
        answers: Optional list of student answers.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    interview_id: uuid.UUID
    question: str
    question_type: str
    difficulty: str
    order_no: int
    created_at: datetime
    answers: Optional[list[InterviewAnswerResponse]] = None


class InterviewQuestionListResponse(BaseModel):
    """Response schema wrapping an ordered list of interview questions.

    Attributes:
        items: List of ``InterviewQuestionResponse`` objects.
        total: Total question count.
    """

    items: list[InterviewQuestionResponse]
    total: int


class InterviewStartResponse(BaseModel):
    """Response returned when an interview is started.

    Attributes:
        interview_id: UUID of the started interview.
        status: Updated status ('Scheduled').
        questions: Generated/retrieved questions in order.
    """

    interview_id: uuid.UUID
    status: str
    questions: list[InterviewQuestionResponse]
