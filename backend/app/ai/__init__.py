"""
backend/app/ai/__init__.py
==========================
AI Provider Module.

Re-exports BaseAIProvider, DummyAIProvider, and get_ai_provider factory function.
"""

from app.ai.base_provider import BaseAIProvider
from app.ai.dummy_provider import DummyAIProvider
from app.ai.factory import get_ai_provider

__all__ = [
    "BaseAIProvider",
    "DummyAIProvider",
    "get_ai_provider",
]
