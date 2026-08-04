"""
backend/app/services/dashboard.py
==================================
Business-logic service layer for Student Dashboard.

Aggregates all relevant entity states for the learner's dashboard view:
  1. Learner Profile & Profession
  2. Active Career Roadmap & Current Task
  3. Latest Task Feedback
  4. Upcoming Scheduled Interview
  5. Latest Interview Feedback
  6. Overall Platform Progress
  7. Unread Notification Count
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.career_roadmap import CareerRoadmap
from app.models.interview import Interview
from app.models.interview_feedback import InterviewFeedback
from app.models.profession import Profession
from app.models.task import Task, TaskSubmission
from app.models.task_feedback import TaskFeedback
from app.models.user import User
from app.repositories.notification import NotificationRepository
from app.services.progress import ProgressService

logger: logging.Logger = logging.getLogger(__name__)


class DashboardService:
    """Service producing aggregated dashboard payload for learners.

    Args:
        db: An active SQLAlchemy ``Session``.
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._progress_svc = ProgressService(db)
        self._notif_repo = NotificationRepository(db)

    def get_student_dashboard(self, user_id: uuid.UUID) -> dict:
        """Aggregate student dashboard state.

        Args:
            user_id: UUID of user.

        Returns:
            Dict matching ``StudentDashboardResponse`` fields.
        """
        logger.debug("get_student_dashboard | user_id=%s", user_id)
        user = self._db.get(User, user_id)
        if user is None:
            raise ValueError(f"User with id '{user_id}' not found.")

        # Profession
        profession_id = getattr(user, "profession_id", None)
        profession = self._db.get(Profession, profession_id) if profession_id else None

        # Roadmap (Active roadmap for assigned profession only)
        roadmap = None
        current_task = None

        if profession_id:
            rm_stmt = (
                select(CareerRoadmap)
                .where(CareerRoadmap.profession_id == profession_id)
                .where(CareerRoadmap.is_active == True)  # noqa: E712
            )
            roadmap = self._db.execute(rm_stmt).scalars().first()

            if roadmap:
                # Fetch first active task under roadmap's steps
                task_stmt = (
                    select(Task)
                    .join(RoadmapStep, Task.roadmap_step_id == RoadmapStep.id)
                    .where(RoadmapStep.roadmap_id == roadmap.id)
                    .where(Task.is_active == True)  # noqa: E712
                    .order_by(RoadmapStep.step_order.asc(), Task.order_no.asc())
                    .limit(1)
                )
                current_task = self._db.execute(task_stmt).scalars().first()

        # Latest Task Feedback
        latest_task_fb = None
        tfb_stmt = (
            select(TaskFeedback)
            .join(TaskSubmission, TaskFeedback.submission_id == TaskSubmission.id)
            .where(TaskSubmission.user_id == user_id)
            .order_by(TaskFeedback.created_at.desc())
            .limit(1)
        )
        latest_task_fb = self._db.execute(tfb_stmt).scalars().first()

        # Upcoming Interview
        upcoming_interview = None
        int_stmt = (
            select(Interview)
            .where(Interview.user_id == user_id)
            .where(Interview.status == "Scheduled")
            .order_by(Interview.scheduled_at.asc())
            .limit(1)
        )
        upcoming_interview = self._db.execute(int_stmt).scalars().first()

        # Latest Interview Feedback
        latest_int_fb = None
        ifb_stmt = (
            select(InterviewFeedback)
            .join(Interview, InterviewFeedback.interview_id == Interview.id)
            .where(Interview.user_id == user_id)
            .order_by(InterviewFeedback.created_at.desc())
            .limit(1)
        )
        latest_int_fb = self._db.execute(ifb_stmt).scalars().first()

        # Progress
        progress = self._progress_svc.get_user_overall_progress(user_id)

        # Unread notifications
        _, _, unread_count = self._notif_repo.list_by_user(user_id, skip=0, limit=1)

        return {
            "user": user,
            "profession": profession,
            "roadmap": roadmap,
            "current_task": current_task,
            "latest_task_feedback": latest_task_fb,
            "upcoming_interview": upcoming_interview,
            "latest_interview_feedback": latest_int_fb,
            "progress": progress,
            "unread_notification_count": unread_count,
        }
