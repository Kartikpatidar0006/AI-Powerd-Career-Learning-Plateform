"""services/learning-service/app/db/base.py — Base model registry."""
from __future__ import annotations
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

# Import models so Base.metadata registers them
from app.models.learning_path import LearningPath  # noqa: F401, E402
from app.models.course import Course  # noqa: F401, E402
from app.models.task import Task  # noqa: F401, E402
from app.models.task_feedback import TaskFeedback  # noqa: F401, E402

