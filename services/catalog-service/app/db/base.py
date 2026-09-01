"""services/catalog-service/app/db/base.py — Base model registry."""
from __future__ import annotations
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

# Import models so Base.metadata registers them
from app.models.profession import Profession  # noqa: F401, E402
from app.models.skill import Skill  # noqa: F401, E402
from app.models.career_roadmap import CareerRoadmap, RoadmapStep  # noqa: F401, E402

