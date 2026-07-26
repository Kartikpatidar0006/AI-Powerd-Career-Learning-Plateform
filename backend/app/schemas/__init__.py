"""
backend/app/schemas/__init__.py
================================
Public re-export surface for all Pydantic v2 schemas.

Import from here rather than from individual modules to keep call-sites
concise and to decouple the rest of the codebase from internal file layout::

    from app.schemas import UserCreate, UserResponse, TokenResponse
    from app.schemas import ProfessionCreate, ProfessionResponse

"""

from app.schemas.auth import (
    LoginRequest,
    PasswordChangeRequest,
    PasswordResetRequest,
    RefreshTokenRequest,
)
from app.schemas.profession import (
    ProfessionCreate,
    ProfessionListResponse,
    ProfessionResponse,
    ProfessionUpdate,
)
from app.schemas.skill import (
    DifficultyLevel,
    SkillCreate,
    SkillListResponse,
    SkillResponse,
    SkillUpdate,
)
from app.schemas.learning_path import (
    LearningPathCreate,
    LearningPathListResponse,
    LearningPathResponse,
    LearningPathUpdate,
)
from app.schemas.course import (
    CourseDifficultyLevel,
    CourseCreate,
    CourseListResponse,
    CourseResponse,
    CourseUpdate,
)
from app.schemas.token import (
    AccessTokenResponse,
    TokenPayload,
    TokenResponse,
)
from app.schemas.user import (
    UserAdminUpdate,
    UserBase,
    UserCreate,
    UserPublicResponse,
    UserResponse,
    UserUpdate,
)
from app.schemas.user_progress import (
    ProgressStatus,
    UserProgressCreate,
    UserProgressListResponse,
    UserProgressResponse,
    UserProgressUpdate,
)
from app.schemas.career_roadmap import (
    RoadmapDifficultyLevel,
    CareerRoadmapCreate,
    CareerRoadmapUpdate,
    CareerRoadmapResponse,
    CareerRoadmapListResponse,
    RoadmapStepCreate,
    RoadmapStepUpdate,
    RoadmapStepResponse,
    RoadmapStepListResponse,
)
from app.schemas.skill_gap import SkillSummary, SkillGapAnalysis

__all__: list[str] = [
    # ── Auth request schemas ──────────────────────────────────────────── #
    "LoginRequest",
    "RefreshTokenRequest",
    "PasswordChangeRequest",
    "PasswordResetRequest",
    # ── Token response schemas ────────────────────────────────────────── #
    "TokenResponse",
    "AccessTokenResponse",
    "TokenPayload",
    # ── User schemas ──────────────────────────────────────────────────── #
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserAdminUpdate",
    "UserResponse",
    "UserPublicResponse",
    # ── Profession schemas ────────────────────────────────────────────── #
    "ProfessionCreate",
    "ProfessionUpdate",
    "ProfessionResponse",
    "ProfessionListResponse",
    # ── Skill schemas ─────────────────────────────────────────────────────────────── #
    "DifficultyLevel",
    "SkillCreate",
    "SkillUpdate",
    "SkillResponse",
    "SkillListResponse",
    # ── LearningPath schemas ──────────────────────────────────────────────────── #
    "LearningPathCreate",
    "LearningPathUpdate",
    "LearningPathResponse",
    "LearningPathListResponse",
    # ── Course schemas ────────────────────────────────────────────────────── #
    "CourseDifficultyLevel",
    "CourseCreate",
    "CourseUpdate",
    "CourseResponse",
    "CourseListResponse",
    # ── UserProgress schemas ───────────────────────────────────────────── #
    "ProgressStatus",
    "UserProgressCreate",
    "UserProgressUpdate",
    "UserProgressResponse",
    "UserProgressListResponse",
    # ── CareerRoadmap schemas ──────────────────────────────────────────── #
    "RoadmapDifficultyLevel",
    "CareerRoadmapCreate",
    "CareerRoadmapUpdate",
    "CareerRoadmapResponse",
    "CareerRoadmapListResponse",
    "RoadmapStepCreate",
    "RoadmapStepUpdate",
    "RoadmapStepResponse",
    "RoadmapStepListResponse",
    # ── AI Skill Gap schemas ───────────────────────────────────────────── #
    "SkillSummary",
    "SkillGapAnalysis",
]
