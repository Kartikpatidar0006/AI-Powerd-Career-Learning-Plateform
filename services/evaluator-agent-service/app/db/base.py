"""SQLAlchemy declarative base for evaluator-agent-service models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models in this service."""
    pass
