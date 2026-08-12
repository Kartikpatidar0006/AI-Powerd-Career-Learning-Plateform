"""
backend/app/services/interview_evaluation.py
=============================================
Business-logic service layer for Interview Evaluation & Feedback.

What this module does
---------------------
Provides ``InterviewEvaluationService`` to handle:
  1. Evaluating completed mock interviews (reads student answers and generates scores).
  2. Isolated evaluation logic ready for seamless substitution with AI/LLM providers (Gemini/OpenAI).
  3. Querying interview evaluation feedback records for learners.

Business Rules
--------------
- Interview MUST be marked as 'Completed' before generating feedback.
- Prevent duplicate evaluations (if feedback already exists, update and return it).
- Evaluation logic is strictly isolated in ``_generate_evaluation()``.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.interview import Interview
from app.models.interview_feedback import InterviewFeedback
from app.repositories.interview import InterviewRepository
from app.repositories.interview_feedback import InterviewFeedbackRepository
from app.repositories.interview_question import (
    InterviewAnswerRepository,
    InterviewQuestionRepository,
)
from app.services.interview import InterviewError

logger: logging.Logger = logging.getLogger(__name__)


class InterviewEvaluationService:
    """Service managing interview evaluations and feedback retrieval.

    Args:
        db: An active SQLAlchemy ``Session``.
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._interview_repo = InterviewRepository(db)
        self._question_repo = InterviewQuestionRepository(db)
        self._answer_repo = InterviewAnswerRepository(db)
        self._feedback_repo = InterviewFeedbackRepository(db)

    # =========================================================================
    #  Evaluate Interview
    # =========================================================================

    def evaluate(
        self,
        interview_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> InterviewFeedback:
        """Evaluate a completed interview and generate feedback scores.

        Args:
            interview_id: UUID of the interview session.
            user_id: UUID of the requesting user.

        Returns:
            The created or updated ``InterviewFeedback`` ORM instance.

        Raises:
            InterviewError: INTERVIEW_NOT_FOUND if interview missing.
            InterviewError: UNAUTHORIZED if not owned by user.
            InterviewError: NOT_ELIGIBLE if interview status != 'Completed'.
        """
        interview = self._interview_repo.get_by_id(interview_id)
        if interview is None:
            raise InterviewError(
                f"Interview with id '{interview_id}' not found.",
                code=InterviewError.INTERVIEW_NOT_FOUND,
            )

        if interview.user_id != user_id:
            raise InterviewError(
                "You do not have permission to evaluate this interview.",
                code=InterviewError.UNAUTHORIZED,
            )

        # Business Rule: Interview must be Completed before evaluation
        if interview.status != "Completed":
            raise InterviewError(
                f"Interview status is '{interview.status}'. Interview must be Completed before generating feedback.",
                code=InterviewError.NOT_ELIGIBLE,
            )

        # Read all questions and student answers
        questions = self._question_repo.list_by_interview(interview_id)
        answers = []
        for q in questions:
            ans = self._answer_repo.get_by_question_and_user(q.id, user_id)
            if ans:
                answers.append(ans)

        # Check if feedback already exists for this interview
        existing = self._feedback_repo.get_by_interview_id(interview_id)

        # Generate evaluation scores (isolated function for future LLM replacement)
        eval_data = self._generate_evaluation(interview, questions, answers)

        if existing is not None:
            existing.overall_score = eval_data["overall_score"]
            existing.technical_score = eval_data["technical_score"]
            existing.communication_score = eval_data["communication_score"]
            existing.confidence_score = eval_data["confidence_score"]
            existing.problem_solving_score = eval_data["problem_solving_score"]
            existing.strengths = eval_data["strengths"]
            existing.weaknesses = eval_data["weaknesses"]
            existing.suggestions = eval_data["suggestions"]
            existing.recommendation = eval_data["recommendation"]
            existing.status = "Generated"

            feedback = self._feedback_repo.update(existing)
            self._db.commit()
            logger.info("Re-evaluated feedback for interview id=%s", interview_id)
            return feedback

        feedback = InterviewFeedback(
            interview_id=interview_id,
            overall_score=eval_data["overall_score"],
            technical_score=eval_data["technical_score"],
            communication_score=eval_data["communication_score"],
            confidence_score=eval_data["confidence_score"],
            problem_solving_score=eval_data["problem_solving_score"],
            strengths=eval_data["strengths"],
            weaknesses=eval_data["weaknesses"],
            suggestions=eval_data["suggestions"],
            recommendation=eval_data["recommendation"],
            status="Generated",
        )
        feedback = self._feedback_repo.create(feedback)
        self._db.commit()
        logger.info("Generated evaluation feedback for interview id=%s", interview_id)

        # Trigger Progress Engine update & notification
        try:
            from app.services.progress import ProgressService
            ProgressService(self._db).process_evaluation_result(
                user_id=user_id,
                task_id=interview.task_id,
                overall_score=eval_data["overall_score"],
            )
        except Exception as exc:
            logger.error("Failed to trigger Progress Engine update: %s", exc)

        return feedback

    def _generate_evaluation(
        self,
        interview: Interview,
        questions: list,
        answers: list,
    ) -> dict:
        """Isolated evaluation generator logic.

        Currently uses rule-based scoring, designed for direct drop-in substitution
        with an AI LLM provider (OpenAI/Gemini/LangChain) in future phases.

        Args:
            interview: The evaluated ``Interview`` instance.
            questions: List of ``InterviewQuestion`` instances.
            answers: List of student ``InterviewAnswer`` instances.

        Returns:
            Dict containing evaluation scores and qualitative feedback strings.
        """
        from app.ai.factory import get_ai_provider
        ai_provider = get_ai_provider()
        interview_title = interview.task.title if interview.task else "Interview"
        
        qa_data = [
            {
                "question": getattr(a, "question", None).question if getattr(a, "question", None) else "",
                "answer_text": a.answer_text,
                "time_taken_seconds": a.time_taken_seconds,
            }
            for a in answers
        ]

        return ai_provider.evaluate_interview_answers(
            interview_title=interview_title,
            questions_and_answers=qa_data,
        )

    # =========================================================================
    #  Get Feedback Operations
    # =========================================================================

    def get_by_interview(
        self,
        interview_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> InterviewFeedback:
        """Retrieve feedback for a specific interview session.

        Args:
            interview_id: UUID of the interview.
            user_id: UUID of requesting user.

        Returns:
            The ``InterviewFeedback`` ORM instance.

        Raises:
            InterviewError: INTERVIEW_NOT_FOUND if missing.
            InterviewError: UNAUTHORIZED if not owned by user.
            InterviewError: NOT_ELIGIBLE if feedback not yet generated.
        """
        interview = self._interview_repo.get_by_id(interview_id)
        if interview is None:
            raise InterviewError(
                f"Interview with id '{interview_id}' not found.",
                code=InterviewError.INTERVIEW_NOT_FOUND,
            )

        if interview.user_id != user_id:
            raise InterviewError(
                "You do not have permission to view feedback for this interview.",
                code=InterviewError.UNAUTHORIZED,
            )

        feedback = self._feedback_repo.get_by_interview_id(interview_id)
        if feedback is None:
            raise InterviewError(
                f"Feedback has not been generated for interview '{interview_id}' yet. Please evaluate the interview first.",
                code=InterviewError.NOT_ELIGIBLE,
            )

        return feedback

    def list_user_feedback(
        self,
        user_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[InterviewFeedback], int]:
        """List all interview feedback records for a user.

        Args:
            user_id: UUID of the user.
            skip: Pagination offset.
            limit: Maximum results.

        Returns:
            Tuple of (list of ``InterviewFeedback`` instances, total count).
        """
        return self._feedback_repo.list_by_user_id(user_id, skip=skip, limit=limit)
