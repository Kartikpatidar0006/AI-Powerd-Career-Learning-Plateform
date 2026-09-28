"""
Anthropic Claude LLM Provider implementation.

Wraps the official Anthropic AsyncAnthropic client with JSON extraction,
strict timeout controls, and structured error mapping.
"""

import json
import logging
import re
from app.core.config import settings
from app.core.llm.base import BaseLLMProvider, LLMProviderError, LLMTimeoutError
from app.core.llm.mock_provider import MockLLMProvider

logger = logging.getLogger("profile-agent.anthropic-llm")


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude API wrapper implementing BaseLLMProvider."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.model = model or settings.ANTHROPIC_MODEL
        self.timeout = settings.LLM_TIMEOUT_SECONDS
        self._fallback_mock = MockLLMProvider()

    def _is_placeholder_key(self) -> bool:
        """Check if API key is unconfigured or a placeholder."""
        if not self.api_key:
            return True
        key = self.api_key.strip().lower()
        return key.startswith("your-") or key.startswith("change") or key == "test"

    async def generate_json(self, system_prompt: str, user_prompt: str) -> str:
        """
        Invoke Anthropic Messages API requesting strict JSON output.

        Falls back gracefully to MockLLMProvider if the API key is not yet configured.
        """
        if self._is_placeholder_key():
            logger.warning(
                "ANTHROPIC_API_KEY is not configured or contains placeholder. "
                "Using MockLLMProvider for offline deterministic execution."
            )
            return await self._fallback_mock.generate_json(system_prompt, user_prompt)

        try:
            from anthropic import AsyncAnthropic, APIConnectionError, APITimeoutError, APIError

            client = AsyncAnthropic(api_key=self.api_key, timeout=self.timeout)

            # Ensure system prompt commands strict JSON return
            full_system = f"{system_prompt}\nIMPORTANT: You MUST respond ONLY with valid JSON. Do not include markdown codeblocks or conversational text."

            response = await client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=full_system,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.2,
            )

            first_block = response.content[0]
            text = first_block.text if hasattr(first_block, "text") else str(first_block)

            # Clean any possible markdown ```json formatting
            text = text.strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*", "", text)
                text = re.sub(r"\s*```$", "", text)

            return text.strip()

        except ImportError:
            logger.error("anthropic package is not installed; falling back to MockLLMProvider")
            return await self._fallback_mock.generate_json(system_prompt, user_prompt)
        except APITimeoutError as exc:
            logger.error("Anthropic API request timed out after %s seconds: %s", self.timeout, exc)
            raise LLMTimeoutError(f"Anthropic request timed out after {self.timeout}s", str(exc)) from exc
        except APIConnectionError as exc:
            logger.error("Anthropic API connection failed: %s", exc)
            raise LLMProviderError("Could not connect to Anthropic API", str(exc)) from exc
        except APIError as exc:
            logger.error("Anthropic API error [%s]: %s", getattr(exc, "status_code", "unknown"), exc.message)
            raise LLMProviderError(f"Anthropic API error: {exc.message}", str(exc)) from exc
        except Exception as exc:
            logger.exception("Unexpected error communicating with Anthropic: %s", exc)
            raise LLMProviderError(f"Unexpected Anthropic error: {str(exc)}") from exc
