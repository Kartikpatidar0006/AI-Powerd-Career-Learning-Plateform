"""
services/agent-service/app/agents/agent1_student.py
-----------------------------------------------------
Agent 1: Student onboarding agent.
- Collects student details
- Creates / updates student profile in DB
- Builds dashboard summary data
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.student import Student
from app.models.problem import Problem
from app.models.evaluation import Evaluation
from app.models.interview import Interview
from app.models.guidance import Guidance
from app.schemas.student import StudentCreate, StudentOut, DashboardOut, StudentUpdate

logger = logging.getLogger(__name__)


class StudentAgent:
    """Agent 1 — manages student profile creation and dashboard."""

    def create_or_update_student(self, db: Session, payload: StudentCreate) -> Student:
        """
        Create a new student profile or update existing one by email.
        """
        existing = db.query(Student).filter(Student.email == payload.email).first()
        if existing:
            logger.info("Updating existing student profile: %s", payload.email)
            for field, value in payload.model_dump(exclude_unset=True).items():
                setattr(existing, field, value)
            db.commit()
            db.refresh(existing)
            return existing

        logger.info("Creating new student profile: %s", payload.email)
        student = Student(**payload.model_dump())
        db.add(student)
        db.commit()
        db.refresh(student)
        return student

    def get_student_by_id(self, db: Session, student_id: uuid.UUID) -> Student | None:
        return db.query(Student).filter(Student.id == student_id).first()

    def get_student_by_email(self, db: Session, email: str) -> Student | None:
        return db.query(Student).filter(Student.email == email).first()

    def update_student(self, db: Session, student_id: uuid.UUID, payload: StudentUpdate) -> Student | None:
        student = self.get_student_by_id(db, student_id)
        if not student:
            return None
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(student, field, value)
        db.commit()
        db.refresh(student)
        return student

    def build_dashboard(self, db: Session, student_id: uuid.UUID) -> DashboardOut | None:
        """Build a comprehensive dashboard summary for the student."""
        student = self.get_student_by_id(db, student_id)
        if not student:
            return None

        total_problems = db.query(Problem).filter(Problem.student_id == student_id).count()
        evaluations = db.query(Evaluation).filter(Evaluation.student_id == student_id).all()
        total_interviews = db.query(Interview).filter(Interview.student_id == student_id).count()

        avg_score = 0.0
        if evaluations:
            completed = [e for e in evaluations if e.status == "completed"]
            avg_score = sum(e.overall_score for e in completed) / len(completed) if completed else 0.0

        latest_guidance = (
            db.query(Guidance)
            .filter(Guidance.student_id == student_id)
            .order_by(Guidance.created_at.desc())
            .first()
        )
        readiness = latest_guidance.readiness_score if latest_guidance else 0

        # Build recent activity log
        recent: list[dict] = []
        for ev in sorted(evaluations, key=lambda e: e.created_at, reverse=True)[:5]:
            recent.append({
                "type": "evaluation",
                "id": str(ev.id),
                "github_url": ev.github_url,
                "overall_score": ev.overall_score,
                "status": ev.status,
                "date": ev.created_at.isoformat(),
            })

        return DashboardOut(
            student=StudentOut.model_validate(student),
            total_problems_assigned=total_problems,
            total_evaluations=len(evaluations),
            average_score=round(avg_score, 2),
            total_interviews=total_interviews,
            latest_readiness_score=readiness,
            recent_activity=recent,
        )


# Singleton
student_agent = StudentAgent()
