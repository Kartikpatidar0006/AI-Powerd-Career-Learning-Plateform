"""
SQLAlchemy declarative base for all ORM models.

All models should inherit from this Base class to ensure
they are registered with Alembic for migration generation.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    pass
