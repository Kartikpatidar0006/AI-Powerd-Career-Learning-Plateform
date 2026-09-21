"""
services/agent-service/app/schemas/evaluation.py
--------------------------------------------------
Pydantic schemas for Agent 3 — Task evaluation & question generation.
"""
from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional


class EvaluationRequest(BaseModel):
    student_id: uuid.UUID
    github_url: str = Field(..., examples=["https://github.com/username/repo"])
    problem_id: Optional[uuid.UUID] = None


class EvaluationOut(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    problem_id: Optional[uuid.UUID]
    github_url: str
    code_quality_score: int
    functionality_score: int
    documentation_score: int
    best_practices_score: int
    overall_score: int
    strengths: Optional[str]       # JSON list
    improvements: Optional[str]    # JSON list
    interview_questions: Optional[str]  # JSON list of 8-15 questions
    raw_analysis: Optional[str]
    status: str
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}
