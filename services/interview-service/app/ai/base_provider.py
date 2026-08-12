"""
backend/app/ai/base_provider.py
================================
Abstract Base Class defining the contract for all AI evaluation providers.

Design
------
Any AI provider (Dummy, OpenAI, Gemini, Claude, LangChain) must implement this
interface. This keeps business services (TaskEvaluationService, InterviewEvaluationService,
MockInterviewEngineService) completely decoupled from AI provider implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseAIProvider(ABC):
    """Interface for AI task evaluation, interview question generation, and interview evaluation."""

    @abstractmethod
    def evaluate_task_submission(
        self,
        task_title: str,
        task_description: Optional[str] = None,
        submission_text: Optional[str] = None,
        github_url: Optional[str] = None,
    ) -> dict[str, Any]:
        """Evaluate a learner's task submission.

        Returns:
            Dict containing: overall_score, technical_score, logic_score,
            code_quality_score, strengths, weaknesses, suggestions, status.
        """
        pass

    @abstractmethod
    def evaluate_interview_answers(
        self,
        interview_title: str,
        questions_and_answers: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Evaluate a learner's completed mock interview session.

        Returns:
            Dict containing: overall_score, technical_score, communication_score,
            confidence_score, problem_solving_score, strengths, weaknesses,
            suggestions, recommendation, status.
        """
        pass

    @abstractmethod
    def generate_interview_questions(
        self,
        task_title: str,
        count: int = 5,
        github_url: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Generate structured interview questions for a task, optionally tailored to a submitted GitHub repository.

        Returns:
            List of dicts containing: question, question_type, difficulty, order_no.
        """
        pass
