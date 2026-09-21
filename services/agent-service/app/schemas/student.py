"""
services/agent-service/app/schemas/student.py
-----------------------------------------------
Pydantic schemas for Agent 1 — Student onboarding & dashboard.
"""
from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class StudentCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255, examples=["Kartik Patidar"])
    email: EmailStr
    profession: str = Field(..., min_length=2, max_length=255, examples=["Full Stack Developer"])
    experience_level: str = Field(default="beginner", examples=["beginner", "intermediate", "advanced"])
    goals: Optional[str] = Field(default=None, examples=["Get a job at a top tech company"])
    preferred_stack: Optional[str] = Field(default=None, examples=["React, FastAPI, PostgreSQL"])
    weekly_hours: int = Field(default=10, ge=1, le=80, examples=[15])
    user_id: Optional[uuid.UUID] = None  # linked auth-service user


class StudentUpdate(BaseModel):
    full_name: Optional[str] = None
    profession: Optional[str] = None
    experience_level: Optional[str] = None
    goals: Optional[str] = None
    preferred_stack: Optional[str] = None
    weekly_hours: Optional[int] = Field(default=None, ge=1, le=80)


class StudentOut(BaseModel):
    id: uuid.UUID
    user_id: Optional[uuid.UUID]
    full_name: str
    email: str
    profession: str
    experience_level: str
    goals: Optional[str]
    preferred_stack: Optional[str]
    weekly_hours: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DashboardOut(BaseModel):
    student: StudentOut
    total_problems_assigned: int
    total_evaluations: int
    average_score: float
    total_interviews: int
    latest_readiness_score: int
    recent_activity: list[dict]
