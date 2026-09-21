"""
services/agent-service/app/schemas/guidance.py
------------------------------------------------
Pydantic schemas for Agent 5 — Career guidance & mentoring.
"""
from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class GuidanceOut(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    interview_id: Optional[uuid.UUID]
    readiness_score: int
    strengths: Optional[str]              # JSON list
    weak_areas: Optional[str]             # JSON list
    next_steps: Optional[str]             # JSON list
    recommended_resources: Optional[str]  # JSON list
    career_path_advice: Optional[str]
    summary: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
