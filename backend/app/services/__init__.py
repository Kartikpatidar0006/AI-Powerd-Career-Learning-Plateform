"""
backend/app/services/__init__.py
=================================
Public re-export surface for all service classes.

Import from here to keep call-sites decoupled from internal file layout::

    from app.services import AuthService, AuthError
"""

from app.services.auth import AuthError, AuthService
from app.services.profession import ProfessionError, ProfessionService
from app.services.skill import SkillError, SkillService
from app.services.learning_path import LearningPathError, LearningPathService
from app.services.course import CourseError, CourseService
from app.services.user_progress import UserProgressError, UserProgressService
from app.services.career_roadmap import (
    CareerRoadmapError,
    CareerRoadmapService,
    RoadmapStepService,
)
from app.services.skill_gap import SkillGapError, SkillGapService
from app.services.task import (
    TaskError,
    TaskService,
    TaskSubmissionService,
)
from app.services.task_feedback import (
    TaskFeedbackError,
    TaskEvaluationService,
    TaskFeedbackService,
)
from app.services.interview import (
    InterviewError,
    InterviewSchedulerService,
    InterviewService,
)
from app.services.interview_engine import MockInterviewEngineService
from app.services.interview_evaluation import InterviewEvaluationService
from app.services.notification import NotificationError, NotificationService
from app.services.progress import ProgressError, ProgressService

__all__: list[str] = [
    "AuthService", "AuthError",
    "ProfessionService", "ProfessionError",
    "SkillService", "SkillError",
    "LearningPathService", "LearningPathError",
    "CourseService", "CourseError",
    "UserProgressService", "UserProgressError",
    "CareerRoadmapService", "RoadmapStepService", "CareerRoadmapError",
    "SkillGapService", "SkillGapError",
    "TaskService", "TaskSubmissionService", "TaskError",
    "TaskEvaluationService", "TaskFeedbackService", "TaskFeedbackError",
    "InterviewSchedulerService", "InterviewService", "InterviewError",
    "MockInterviewEngineService",
    "InterviewEvaluationService",
    "NotificationService", "NotificationError",
    "ProgressService", "ProgressError",
]
