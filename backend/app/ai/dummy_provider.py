"""
backend/app/ai/dummy_provider.py
=================================
Rule-based / Mock AI Provider implementation.

Provides deterministic, rule-based evaluation scores and questions without calling
external LLM APIs. Serves as default provider until Gemini/OpenAI are configured.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.ai.base_provider import BaseAIProvider

logger: logging.Logger = logging.getLogger(__name__)


class DummyAIProvider(BaseAIProvider):
    """Rule-based dummy AI provider for task and interview evaluation."""

    def evaluate_task_submission(
        self,
        task_title: str,
        task_description: Optional[str] = None,
        submission_text: Optional[str] = None,
        github_url: Optional[str] = None,
    ) -> dict[str, Any]:
        logger.debug("DummyAIProvider | evaluate_task_submission | title=%s", task_title)
        return {
            "overall_score": 85,
            "technical_score": 82,
            "logic_score": 88,
            "code_quality_score": 80,
            "strengths": "Good problem solving logic, clean structure, and effective implementation.",
            "weaknesses": "Could improve error handling documentation and unit test coverage.",
            "suggestions": "Use meaningful variable names, add docstrings, and handle edge cases explicitly.",
            "status": "Generated",
        }

    def evaluate_interview_answers(
        self,
        interview_title: str,
        questions_and_answers: list[dict[str, Any]],
    ) -> dict[str, Any]:
        logger.debug("DummyAIProvider | evaluate_interview_answers | title=%s", interview_title)
        return {
            "overall_score": 86,
            "technical_score": 84,
            "communication_score": 88,
            "confidence_score": 85,
            "problem_solving_score": 87,
            "strengths": "Clear technical explanations, structured problem-solving approach, and confident delivery.",
            "weaknesses": "Could provide more concrete, real-world code examples during behavioral questions.",
            "suggestions": "Practice detailing time/space complexity trade-offs and edge cases explicitly.",
            "recommendation": "Strong Hire",
            "status": "Generated",
        }

    def generate_interview_questions(
        self,
        task_title: str,
        count: int = 5,
    ) -> list[dict[str, Any]]:
        logger.debug("DummyAIProvider | generate_interview_questions | title=%s", task_title)
        return [
            {
                "question": f"Explain the core architecture and key technical decisions you made while completing '{task_title}'.",
                "question_type": "Technical",
                "difficulty": "Easy",
                "order_no": 1,
            },
            {
                "question": "How did you structure error handling, input validation, and edge case management in your code?",
                "question_type": "Technical",
                "difficulty": "Medium",
                "order_no": 2,
            },
            {
                "question": "If system load increased by 100x, how would you optimize performance, caching, and database queries for this solution?",
                "question_type": "Technical",
                "difficulty": "Hard",
                "order_no": 3,
            },
            {
                "question": "Describe a technical challenge or bug you encountered during this task and step-by-step how you resolved it.",
                "question_type": "Behavioral",
                "difficulty": "Medium",
                "order_no": 4,
            },
            {
                "question": "What key engineering best practices did you learn while completing this assignment?",
                "question_type": "Behavioral",
                "difficulty": "Easy",
                "order_no": 5,
            },
        ]
