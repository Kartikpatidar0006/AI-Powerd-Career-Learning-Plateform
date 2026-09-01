"""services/notification-service/app/db/base.py — Base model registry."""
from __future__ import annotations
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

# Import models so Base.metadata registers them
from app.models.notification import Notification  # noqa: F401, E402

