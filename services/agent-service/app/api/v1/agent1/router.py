"""
services/agent-service/app/api/v1/agent1/router.py
----------------------------------------------------
Agent 1 API — Student onboarding & dashboard.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.agent1_student import student_agent
from app.db.session import get_db
from app.schemas.student import DashboardOut, StudentCreate, StudentOut, StudentUpdate

router = APIRouter()


@router.post(
    "/students",
    response_model=StudentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Agent 1 — Onboard a new student",
)
def onboard_student(payload: StudentCreate, db: Session = Depends(get_db)) -> StudentOut:
    """
    **Agent 1**: Collects student details and creates their profile.
    If a student with the same email already exists, it updates the profile.
    """
    student = student_agent.create_or_update_student(db, payload)
    return StudentOut.model_validate(student)


@router.get(
    "/students/{student_id}",
    response_model=StudentOut,
    summary="Get student profile",
)
def get_student(student_id: uuid.UUID, db: Session = Depends(get_db)) -> StudentOut:
    student = student_agent.get_student_by_id(db, student_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    return StudentOut.model_validate(student)


@router.patch(
    "/students/{student_id}",
    response_model=StudentOut,
    summary="Update student profile",
)
def update_student(
    student_id: uuid.UUID, payload: StudentUpdate, db: Session = Depends(get_db)
) -> StudentOut:
    student = student_agent.update_student(db, student_id, payload)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    return StudentOut.model_validate(student)


@router.get(
    "/students/{student_id}/dashboard",
    response_model=DashboardOut,
    summary="Agent 1 — Get student dashboard",
)
def get_dashboard(student_id: uuid.UUID, db: Session = Depends(get_db)) -> DashboardOut:
    """
    **Agent 1**: Returns a comprehensive dashboard with all progress metrics.
    """
    dashboard = student_agent.build_dashboard(db, student_id)
    if not dashboard:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    return dashboard
