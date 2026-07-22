"""
backend/app/services/__init__.py
=================================
Public re-export surface for all service classes.

Import from here to keep call-sites decoupled from internal file layout::

    from app.services import AuthService, AuthError
"""

from app.services.auth import AuthError, AuthService
from app.services.profession import ProfessionError, ProfessionService

__all__: list[str] = ["AuthService", "AuthError", "ProfessionService", "ProfessionError"]
