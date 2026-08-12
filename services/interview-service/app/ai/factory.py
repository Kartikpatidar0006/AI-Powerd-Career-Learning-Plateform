"""
backend/app/ai/factory.py
==========================
Factory pattern function for instantiating AI evaluation providers.

Design
------
Reads configuration to instantiate and return a ``BaseAIProvider`` instance.
Currently defaults to ``DummyAIProvider``. When OpenAI/Gemini/LangChain providers
are added, they can be selected seamlessly via environment configuration.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.ai.base_provider import BaseAIProvider
from app.ai.dummy_provider import DummyAIProvider

logger: logging.Logger = logging.getLogger(__name__)

_provider_instance: Optional[BaseAIProvider] = None


def get_ai_provider() -> BaseAIProvider:
    """Return the configured AI provider singleton.

    Returns:
        Instance implementing ``BaseAIProvider``.
    """
    global _provider_instance
    if _provider_instance is None:
        logger.info("Initializing DummyAIProvider singleton")
        _provider_instance = DummyAIProvider()
    return _provider_instance
