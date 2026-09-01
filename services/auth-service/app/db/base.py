"""services/auth-service/app/db/base.py — Base model registry."""
from __future__ import annotations
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

# Import models so Base.metadata registers them
from app.models.role import Role  # noqa: F401, E402
from app.models.user import User  # noqa: F401, E402
from app.models.user_activity import UserActivity  # noqa: F401, E402

