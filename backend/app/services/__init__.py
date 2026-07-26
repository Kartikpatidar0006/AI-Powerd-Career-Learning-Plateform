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

__all__: list[str] = [
    "AuthService", "AuthError",
    "ProfessionService", "ProfessionError",
    "SkillService", "SkillError",
    "LearningPathService", "LearningPathError",
    "CourseService", "CourseError",
    "UserProgressService", "UserProgressError",
    "CareerRoadmapService", "RoadmapStepService", "CareerRoadmapError",
    "SkillGapService", "SkillGapError",
]
