"""services/agent-service/app/db/base.py — Base model registry."""
from __future__ import annotations
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import models so Base.metadata registers them
from app.models.student import Student          # noqa: F401, E402
from app.models.problem import Problem          # noqa: F401, E402
from app.models.evaluation import Evaluation    # noqa: F401, E402
from app.models.interview import Interview      # noqa: F401, E402
from app.models.guidance import Guidance        # noqa: F401, E402
