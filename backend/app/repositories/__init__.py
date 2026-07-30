"""
backend/app/repositories/__init__.py
======================================
Public re-export surface for all repository classes.

Import from here to keep call-sites decoupled from internal file layout::

    from app.repositories import UserRepository
"""

from app.repositories.user import UserRepository
from app.repositories.profession import ProfessionRepository
from app.repositories.skill import SkillRepository
from app.repositories.learning_path import LearningPathRepository
from app.repositories.course import CourseRepository
from app.repositories.user_progress import UserProgressRepository
from app.repositories.career_roadmap import (
    CareerRoadmapRepository,
    RoadmapStepRepository,
)
from app.repositories.task import (
    TaskRepository,
    TaskSubmissionRepository,
)
from app.repositories.task_feedback import TaskFeedbackRepository
from app.repositories.interview import InterviewRepository
from app.repositories.interview_question import (
    InterviewQuestionRepository,
    InterviewAnswerRepository,
)
from app.repositories.interview_feedback import InterviewFeedbackRepository as InterviewEvaluationFeedbackRepository
from app.repositories.notification import NotificationRepository

__all__: list[str] = [
    "UserRepository",
    "ProfessionRepository",
    "SkillRepository",
    "LearningPathRepository",
    "CourseRepository",
    "UserProgressRepository",
    "CareerRoadmapRepository",
    "RoadmapStepRepository",
    "TaskRepository",
    "TaskSubmissionRepository",
    "TaskFeedbackRepository",
    "InterviewRepository",
    "InterviewQuestionRepository",
    "InterviewAnswerRepository",
    "InterviewEvaluationFeedbackRepository",
    "NotificationRepository",
]

