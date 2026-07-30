"""
backend/app/schemas/student_dashboard.py
=========================================
Pydantic v2 schemas for the Student Dashboard API.

Aggregates complete state for a learner's personalized home dashboard.
"""

from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.career_roadmap import CareerRoadmapResponse
from app.schemas.interview import InterviewResponse
from app.schemas.interview_feedback import InterviewFeedbackResponse
from app.schemas.profession import ProfessionResponse
from app.schemas.progress import UserOverallProgressResponse
from app.schemas.task import TaskResponse
from app.schemas.task_feedback import TaskFeedbackResponse
from app.schemas.user import UserResponse


class StudentDashboardResponse(BaseModel):
    """API response schema for student home dashboard aggregation.

    Attributes:
        user: User profile summary.
        profession: Active chosen Profession (optional).
        roadmap: Active CareerRoadmap (optional).
        current_task: Next active task to work on (optional).
        latest_task_feedback: Latest evaluated TaskFeedback (optional).
        upcoming_interview: Next scheduled Interview (optional).
        latest_interview_feedback: Latest InterviewFeedback evaluation (optional).
        progress: Platform overall progress metrics.
        unread_notification_count: Unread notification count.
    """

    model_config = ConfigDict(from_attributes=True)

    user: UserResponse
    profession: Optional[ProfessionResponse] = None
    roadmap: Optional[CareerRoadmapResponse] = None
    current_task: Optional[TaskResponse] = None
    latest_task_feedback: Optional[TaskFeedbackResponse] = None
    upcoming_interview: Optional[InterviewResponse] = None
    latest_interview_feedback: Optional[InterviewFeedbackResponse] = None
    progress: UserOverallProgressResponse
    unread_notification_count: int = 0
