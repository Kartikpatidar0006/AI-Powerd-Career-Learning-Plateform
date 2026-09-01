"""services/interview-service/app/db/base.py — Base model registry."""
from __future__ import annotations
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

# Import models so Base.metadata registers them
from app.models.interview import Interview  # noqa: F401, E402
from app.models.interview_question import InterviewQuestion, InterviewAnswer  # noqa: F401, E402
from app.models.interview_feedback import InterviewFeedback  # noqa: F401, E402

