"""Schemas package — exports all Pydantic request/response models."""

from app.schemas.profile import (
    DashboardData,
    EducationInfo,
    MessageResponse,
    OnboardingRequest,
    SkillItem,
    StructuredSkillsOutput,
    StudentProfileResponse,
)

__all__ = [
    "DashboardData",
    "EducationInfo",
    "MessageResponse",
    "OnboardingRequest",
    "SkillItem",
    "StructuredSkillsOutput",
    "StudentProfileResponse",
]
