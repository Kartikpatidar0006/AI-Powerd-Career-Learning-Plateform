"""
backend/app/repositories/__init__.py
======================================
Public re-export surface for all repository classes.

Import from here to keep call-sites decoupled from internal file layout::

    from app.repositories import UserRepository
"""

from app.repositories.user import UserRepository
from app.repositories.profession import ProfessionRepository

__all__: list[str] = ["UserRepository", "ProfessionRepository"]
