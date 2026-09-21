"""
services/agent-service/app/agents/llm_client.py
-------------------------------------------------
Shared LLM client using OpenAI SDK.
Falls back to a mock response when no API key is configured.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


def _get_client():
    """Lazy-load the OpenAI client so the service starts even without a key."""
    try:
        from openai import OpenAI  # type: ignore
        if not settings.OPENAI_API_KEY:
            return None
        return OpenAI(api_key=settings.OPENAI_API_KEY)
    except ImportError:
        logger.warning("openai package not installed. Running in mock mode.")
        return None


def chat_complete(system_prompt: str, user_prompt: str) -> str:
    """
    Call the LLM and return the response text.
    Returns a JSON placeholder string in mock mode.
    """
    client = _get_client()
    if client is None:
        logger.info("LLM mock mode active — returning placeholder response.")
        return json.dumps({"mock": True, "message": "Configure OPENAI_API_KEY in .env to enable real AI responses."})

    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            max_tokens=settings.OPENAI_MAX_TOKENS,
            temperature=settings.OPENAI_TEMPERATURE,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content or ""
    except Exception as exc:
        logger.error("LLM call failed: %s", exc, exc_info=True)
        raise


def parse_json_response(raw: str) -> Any:
    """Extract JSON from the LLM response, stripping markdown fences if present."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first and last fence lines
        cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Could not parse LLM response as JSON, returning raw string.")
        return {"raw": cleaned}
