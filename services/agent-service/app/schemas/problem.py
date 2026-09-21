"""
services/agent-service/app/schemas/problem.py
-----------------------------------------------
Pydantic schemas for Agent 2 — Problem generation.
"""
from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, Literal


class ProblemGenerateRequest(BaseModel):
    student_id: uuid.UUID
    difficulty: Literal["easy", "medium", "hard"]
    count: int = Field(default=3, ge=1, le=10)


class ProblemOut(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    title: str
    description: str
    difficulty: str
    tech_stack: Optional[str]
    estimated_hours: int
    requirements: Optional[str]       # JSON list
    acceptance_criteria: Optional[str]  # JSON list
    is_assigned: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ProblemAssignRequest(BaseModel):
    student_id: uuid.UUID
    problem_id: uuid.UUID
