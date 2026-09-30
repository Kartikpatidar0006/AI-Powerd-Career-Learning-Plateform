"""
Base LLM Provider abstraction and exceptions for evaluator-agent-service.

NOTE: This LLM abstraction layer is intentionally duplicated from profile-agent-service
and roadmap-agent-service for full service independence — each service is self-contained
with no shared code. In a future production hardening pass, this could move to a shared
internal library (e.g., 'career-platform-core') and be installed as a package dependency.
"""

from abc import ABC, abstractmethod


class LLMError(Exception):
    """Base exception for LLM provider errors."""

    def __init__(self, message: str, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class LLMTimeoutError(LLMError):
    """Raised when an external LLM request times out."""
    pass


class LLMProviderError(LLMError):
    """Raised when the LLM provider fails with an API error or bad status code."""
    pass


class LLMValidationError(LLMError):
    """Raised when the LLM output fails schema validation after retry."""
    pass


class BaseLLMProvider(ABC):
    """
    Abstract Base Class for LLM providers.

    All LLM client wrappers must implement this interface, ensuring
    interchangeability across OpenAI, Anthropic, or mock implementations.
    """

    @abstractmethod
    async def generate_json(self, system_prompt: str, user_prompt: str) -> str:
        """
        Send prompts to the LLM and return a raw JSON string response.

        Args:
            system_prompt: Guiding instructions and constraints for the LLM.
            user_prompt: Specific data to process or error retry instructions.

        Returns:
            Raw string containing the JSON response.

        Raises:
            LLMTimeoutError: If the call exceeds configured timeout.
            LLMProviderError: If the provider returns an API error or is unreachable.
        """
        pass
