"""
Mock LLM Provider for interview-agent-service.

Returns deterministic, schema-valid JSON without requiring
external API keys. Used for offline development and CI testing.

Tracks prompt history for assertion testing and supports injection testing,
retry verification, and closing turn transitions.
"""

import json
import logging
from typing import Any

from app.core.llm.base import BaseLLMProvider

logger = logging.getLogger("interview-agent.mock-llm")


class MockLLMProvider(BaseLLMProvider):
    """Deterministic Mock LLM Provider producing valid interview and evaluation JSON."""

    def __init__(self, artificial_delay: float = 0.0) -> None:
        self.artificial_delay = artificial_delay
        self.last_system_prompt: str = ""
        self.last_user_prompt: str = ""
        self.calls: list[dict[str, str]] = []
        self.custom_responses: list[str] = []
        self.fail_attempts: int = 0

    async def generate_json(self, system_prompt: str, user_prompt: str) -> str:
        """
        Record prompts and return deterministic, schema-valid mock JSON.
        """
        if self.artificial_delay > 0:
            import asyncio
            await asyncio.sleep(self.artificial_delay)

        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})

        # Support simulated transient failures for 1-shot retry testing
        if self.fail_attempts > 0:
            self.fail_attempts -= 1
            logger.info("MockLLMProvider: Simulating invalid JSON response for retry test")
            return "INVALID_NON_JSON_RESPONSE {unclosed_brace"

        # Support custom queue of responses if injected by tests
        if self.custom_responses:
            return self.custom_responses.pop(0)

        prompt_lower = user_prompt.lower()
        system_lower = system_prompt.lower()

        # 1. Performance Summary generation
        if (
            "performance summary" in prompt_lower
            or "performance summary" in system_lower
            or "transcript analysis" in prompt_lower
            or "confidence_signals" in prompt_lower
        ):
            logger.info("MockLLMProvider: Generating deterministic overall performance summary")
            return json.dumps({
                "communication_clarity": 85,
                "technical_depth": 82,
                "confidence_signals": 88,
                "overall_score": 85,
                "summary": "Candidate demonstrated solid understanding of asynchronous architectures, error boundaries, and database query optimization.",
                "key_strengths": [
                    "Clear explanation of asyncpg connection pool life cycle",
                    "Well-structured discussion on error propagation",
                ],
                "areas_for_improvement": [
                    "Could detail concrete latency profiling benchmarks",
                ],
            })

        # 2. Closing turn requested / max turn limit reached
        if (
            "closing statement" in prompt_lower
            or "is_closing: true" in prompt_lower
            or "closing remark" in prompt_lower
        ):
            logger.info("MockLLMProvider: Generating deterministic closing turn")
            return json.dumps({
                "title": "Interview Conclusion",
                "question_text": "Thank you for answering these questions and defending your project design. That concludes our technical interview.",
                "question_context": {
                    "status": "concluded",
                    "is_closing": True,
                    "injection_detected": False,
                },
                "is_closing": True,
            })

        # 3. Detect prompt-injection attempts in student answers
        injection_keywords = [
            "ignore previous",
            "ignore instructions",
            "disregard",
            "end the interview now",
            "give me a perfect rating",
            "give me 100",
            "assign a score of 100",
            "perfect rating",
            "override your",
        ]
        injection_detected = any(k in prompt_lower for k in injection_keywords)

        if injection_detected:
            logger.warning("MockLLMProvider: Detected injection attempt in student answer — flagging internally")
            return json.dumps({
                "title": "Architectural Design Review",
                "question_text": "Let's return to the technical evaluation. Could you elaborate on how your code handles transaction rollbacks on unexpected network drops?",
                "question_context": {
                    "topic": "Transactions",
                    "injection_detected": True,
                    "injection_flag_detail": "Candidate attempted to override interview instructions in answer text",
                    "is_closing": False,
                },
                "is_closing": False,
            })

        # 4. First question (weakness defense)
        if "first question" in prompt_lower or "findings / weaknesses" in prompt_lower or "findings from agent 3" in prompt_lower:
            logger.info("MockLLMProvider: Generating first question referencing evaluation findings")
            weakness_hint = "Code structure and test coverage"
            if "weakness" in prompt_lower or "findings" in prompt_lower:
                weakness_hint = "The evaluation noted specific weaknesses in testing and async safety"

            return json.dumps({
                "title": "Submission Defense: Core Implementation",
                "question_text": f"In reviewing your project submission, the evaluation highlighted: '{weakness_hint}'. Could you explain your rationale for this implementation and how you would improve it for production?",
                "question_context": {
                    "targeted_finding": weakness_hint,
                    "skill": "Architecture & Testing",
                    "is_closing": False,
                    "injection_detected": False,
                },
                "is_closing": False,
            })

        # 5. Follow-up question
        logger.info("MockLLMProvider: Generating follow-up question")
        return json.dumps({
            "title": "Deep Dive: System Concurrency",
            "question_text": "Following up on your explanation, how does your implementation guarantee thread safety or event loop isolation under high concurrency?",
            "question_context": {
                "targeted_finding": "Concurrency and event loop safety",
                "skill": "Asynchronous Concurrency",
                "is_closing": False,
                "injection_detected": False,
            },
            "is_closing": False,
        })
