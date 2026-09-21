"""
services/agent-service/app/schemas/interview.py
-------------------------------------------------
Pydantic schemas for Agent 4 — AI mock interview.
"""
from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class InterviewStartRequest(BaseModel):
    student_id: uuid.UUID
    evaluation_id: uuid.UUID


class AnswerRequest(BaseModel):
    interview_id: uuid.UUID
    question_index: int
    answer: str = Field(..., min_length=1, max_length=5000)


class InterviewOut(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    evaluation_id: uuid.UUID
    qa_transcript: Optional[str]      # JSON list of Q&A
    communication_score: int
    technical_score: int
    confidence_score: int
    overall_score: int
    current_question_index: int
    total_questions: int
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class NextQuestionOut(BaseModel):
    interview_id: uuid.UUID
    question_index: int
    question: str
    total_questions: int
    is_last: bool


class AnswerFeedbackOut(BaseModel):
    question: str
    your_answer: str
    score: int
    feedback: str
    next_question: Optional[str]
    is_complete: bool
