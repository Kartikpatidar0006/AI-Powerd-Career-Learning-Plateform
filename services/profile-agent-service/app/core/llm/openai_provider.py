"""
OpenAI LLM Provider implementation.

Wraps the official OpenAI AsyncOpenAI client with response_format: json_object,
strict timeout controls, and structured error mapping.
"""

import logging
from app.core.config import settings
from app.core.llm.base import BaseLLMProvider, LLMProviderError, LLMTimeoutError
from app.core.llm.mock_provider import MockLLMProvider

logger = logging.getLogger("profile-agent.openai-llm")


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API wrapper implementing BaseLLMProvider."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model or settings.OPENAI_MODEL
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
        Invoke OpenAI Chat Completions API requesting strict JSON output.

        Falls back gracefully to MockLLMProvider if the API key is not yet configured.
        """
        if self._is_placeholder_key():
            logger.warning(
                "OPENAI_API_KEY is not configured or contains placeholder. "
                "Using MockLLMProvider for offline deterministic execution."
            )
            return await self._fallback_mock.generate_json(system_prompt, user_prompt)

        try:
            from openai import AsyncOpenAI, APIConnectionError, APITimeoutError, APIError

            client = AsyncOpenAI(api_key=self.api_key, timeout=self.timeout)

            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,  # Low temperature for deterministic factual extraction
            )

            choice = response.choices[0]
            content = choice.message.content
            if not content:
                raise LLMProviderError("OpenAI returned an empty completion response")
            return content

        except ImportError:
            logger.error("openai package is not installed; falling back to MockLLMProvider")
            return await self._fallback_mock.generate_json(system_prompt, user_prompt)
        except APITimeoutError as exc:
            logger.error("OpenAI API request timed out after %s seconds: %s", self.timeout, exc)
            raise LLMTimeoutError(f"OpenAI request timed out after {self.timeout}s", str(exc)) from exc
        except APIConnectionError as exc:
            logger.error("OpenAI API connection failed: %s", exc)
            raise LLMProviderError("Could not connect to OpenAI API", str(exc)) from exc
        except APIError as exc:
            logger.error("OpenAI API error [%s]: %s", exc.code, exc.message)
            raise LLMProviderError(f"OpenAI API error: {exc.message}", str(exc)) from exc
        except Exception as exc:
            logger.exception("Unexpected error communicating with OpenAI: %s", exc)
            raise LLMProviderError(f"Unexpected OpenAI error: {str(exc)}") from exc
