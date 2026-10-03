"""
Factory for creating LLM provider instances based on configuration.

Duplication of the LLM provider abstraction across microservices is intentional
for service independence and shared-nothing architecture. This could later move
to a shared common library in future phases.
"""

import logging
from app.core.config import settings
from app.core.llm.base import BaseLLMProvider
from app.core.llm.mock_provider import MockLLMProvider
from app.core.llm.openai_provider import OpenAIProvider
from app.core.llm.anthropic_provider import AnthropicProvider

logger = logging.getLogger("interview-agent.llm-factory")


def get_llm_provider() -> BaseLLMProvider:
    """
    Factory function returning the configured LLM provider instance.

    Controlled by the LLM_PROVIDER environment variable ('openai', 'anthropic', 'mock').
    Allows instant provider hot-swapping without touching business logic.
    """
    provider_type = settings.LLM_PROVIDER.lower().strip()

    if provider_type == "anthropic":
        logger.info("Initializing AnthropicProvider (model: %s)", settings.ANTHROPIC_MODEL)
        return AnthropicProvider()
    elif provider_type == "mock":
        if settings.APP_ENV == "production":
            raise ValueError(
                "Mock LLM provider is strictly disallowed when APP_ENV=production. "
                "Configure a real LLM provider (openai, anthropic) or set APP_ENV=development for offline testing."
            )
        logger.info("Initializing MockLLMProvider for offline deterministic execution")
        return MockLLMProvider()
    else:
        # Default to OpenAI
        logger.info("Initializing OpenAIProvider (model: %s)", settings.OPENAI_MODEL)
        return OpenAIProvider()
