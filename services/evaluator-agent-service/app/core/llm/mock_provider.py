"""
Mock LLM Provider for evaluator-agent-service.

Returns deterministic, schema-valid code review JSON without requiring
external API keys. Used for offline development and CI testing.

NOTE: Intentionally duplicated from other services for service independence.
"""

import json
import logging

from app.core.llm.base import BaseLLMProvider

logger = logging.getLogger("evaluator-agent.mock-llm")


class MockLLMProvider(BaseLLMProvider):
    """Deterministic Mock LLM Provider producing valid code review JSON."""

    def __init__(self, artificial_delay: float = 0.1) -> None:
        self.artificial_delay = artificial_delay

    async def generate_json(self, system_prompt: str, user_prompt: str) -> str:
        """
        Return deterministic, schema-valid code review JSON.

        Detects prompt-injection test scenarios by searching user_prompt
        for injection keywords and responds accordingly (still low score,
        injection flagged in red_flags).
        """
        if self.artificial_delay > 0:
            import asyncio
            await asyncio.sleep(self.artificial_delay)

        logger.info("MockLLMProvider: Generating deterministic code review response")

        prompt_lower = user_prompt.lower()

        # Detect prompt-injection attempts in content (for test scenarios)
        injection_detected = any(k in prompt_lower for k in [
            "ignore previous", "ignore instructions", "disregard", "forget your",
            "set quality_score to 100", "assign a score of 100", "give me 100",
            "your new instructions", "override your",
        ])

        if injection_detected:
            # Injection attempt detected — note it in red_flags, do NOT inflate score
            return json.dumps({
                "strengths": ["Some basic structure present"],
                "weaknesses": [
                    "README contains suspicious content attempting to manipulate the evaluator",
                    "Code quality cannot be fully assessed due to suspicious content",
                ],
                "suggestions": [
                    "Remove any content in README/commits that attempts to override AI instructions",
                    "Focus on genuine code quality improvements",
                ],
                "red_flags": [
                    "INJECTION_ATTEMPT: Repository content appears to contain prompt injection "
                    "attempts (instructions to ignore previous guidance, set specific scores, etc.). "
                    "This has been flagged and does not affect the evaluation outcome.",
                ],
                "quality_score": 35,
            })

        # Standard mock review
        return json.dumps({
            "strengths": [
                "Repository is publicly accessible and contains relevant source files",
                "Commit history shows iterative development approach",
                "README provides basic project context",
            ],
            "weaknesses": [
                "Code structure could be improved with better module organization",
                "Test coverage appears limited — no dedicated test directory found",
                "Documentation could be expanded with API/usage examples",
            ],
            "suggestions": [
                "Add a comprehensive test suite with pytest covering core logic",
                "Improve README with installation steps, usage examples, and architecture notes",
                "Consider adding type hints throughout the codebase for better maintainability",
            ],
            "red_flags": [],
            "quality_score": 68,
        })
