"""
backend/app/services/task_feedback.py
======================================
Business-logic service layer for Task Evaluation and Feedback.

What this module does
---------------------
Provides ``TaskEvaluationService`` and ``TaskFeedbackService`` to handle:
  1. Evaluating task submissions (currently rule-based / dummy scores, structured
     for future AI/LLM integration).
  2. Retrieving feedback records by submission ID or for a logged-in user.

Layer rules enforced here:
  • No FastAPI imports — raises domain-specific ``TaskFeedbackError``.
  • Database operations delegated to repositories.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.task import TaskSubmission
from app.models.task_feedback import TaskFeedback
from app.repositories.task import TaskSubmissionRepository
from app.repositories.task_feedback import TaskFeedbackRepository

logger: logging.Logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Domain exception
# ─────────────────────────────────────────────────────────────────────────────


class TaskFeedbackError(Exception):
    """Business-rule violation raised by ``TaskEvaluationService`` or ``TaskFeedbackService``.

    Code constants:
        ``SUBMISSION_NOT_FOUND`` — submission UUID does not exist.
        ``FEEDBACK_NOT_FOUND``   — feedback UUID / record does not exist.
        ``UNAUTHORIZED``         — user does not have permission to view/evaluate submission.
    """

    SUBMISSION_NOT_FOUND: str = "submission_not_found"
    FEEDBACK_NOT_FOUND: str = "feedback_not_found"
    UNAUTHORIZED: str = "unauthorized"

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code

    def __repr__(self) -> str:
        return f"TaskFeedbackError(code={self.code!r}, message={self.message!r})"


# =========================================================================== #
#  TaskEvaluationService                                                       #
# =========================================================================== #


class TaskEvaluationService:
    """Service dedicated to evaluating task submissions.

    Currently uses deterministic rule-based evaluation logic, designed to be swapped
    with an AI LLM evaluation pipeline in future phases.

    Args:
        db: An active SQLAlchemy ``Session``.
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._sub_repo = TaskSubmissionRepository(db)
        self._feedback_repo = TaskFeedbackRepository(db)

    def evaluate(
        self,
        submission_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> TaskFeedback:
        """Generate evaluation feedback for a task submission.

        If feedback already exists for this submission, it updates and returns
        the existing feedback record.

        Args:
            submission_id: UUID of the submission to evaluate.
            user_id: UUID of the user making the request (for ownership check).

        Returns:
            The created or updated ``TaskFeedback`` ORM instance.

        Raises:
            TaskFeedbackError: ``SUBMISSION_NOT_FOUND`` if submission does not exist.
            TaskFeedbackError: ``UNAUTHORIZED`` if user does not own the submission.
        """
        submission = self._sub_repo.get_by_id(submission_id)
        if submission is None:
            raise TaskFeedbackError(
                f"Task submission with id '{submission_id}' not found.",
                code=TaskFeedbackError.SUBMISSION_NOT_FOUND,
            )

        if submission.user_id != user_id:
            raise TaskFeedbackError(
                "You do not have permission to evaluate this submission.",
                code=TaskFeedbackError.UNAUTHORIZED,
            )

        # Check if feedback already exists for this submission
        existing_feedback = self._feedback_repo.get_by_submission_id(submission_id)

        # ── Call AI Provider Abstraction ──────────────────────────────────── #
        from app.ai.factory import get_ai_provider
        ai_provider = get_ai_provider()
        task_title = submission.task.title if submission.task else "Task"
        task_desc = submission.task.description if submission.task else None
        
        eval_res = ai_provider.evaluate_task_submission(
            task_title=task_title,
            task_description=task_desc,
            submission_text=submission.submission_text,
            github_url=submission.github_url,
        )

        overall_score = eval_res["overall_score"]
        technical_score = eval_res["technical_score"]
        logic_score = eval_res["logic_score"]
        code_quality_score = eval_res["code_quality_score"]

        strengths = eval_res["strengths"]
        weaknesses = eval_res["weaknesses"]
        suggestions = eval_res["suggestions"]
        status_val = eval_res.get("status", "Generated")

        # Update submission status to 'Reviewed'
        submission.status = "Reviewed"
        self._sub_repo.update(submission)

        if existing_feedback is not None:
            existing_feedback.overall_score = overall_score
            existing_feedback.technical_score = technical_score
            existing_feedback.logic_score = logic_score
            existing_feedback.code_quality_score = code_quality_score
            existing_feedback.strengths = strengths
            existing_feedback.weaknesses = weaknesses
            existing_feedback.suggestions = suggestions
            existing_feedback.status = status_val

            feedback = self._feedback_repo.update(existing_feedback)
            self._db.commit()
            logger.info("Re-evaluated feedback for submission id=%s", submission_id)
            return feedback

        feedback = TaskFeedback(
            submission_id=submission_id,
            overall_score=overall_score,
            technical_score=technical_score,
            logic_score=logic_score,
            code_quality_score=code_quality_score,
            strengths=strengths,
            weaknesses=weaknesses,
            suggestions=suggestions,
            status=status_val,
        )
        feedback = self._feedback_repo.create(feedback)
        self._db.commit()
        logger.info("Generated feedback for submission id=%s", submission_id)
        return feedback


# =========================================================================== #
#  TaskFeedbackService                                                         #
# =========================================================================== #


class TaskFeedbackService:
    """Service for querying task feedback records.

    Args:
        db: An active SQLAlchemy ``Session``.
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._sub_repo = TaskSubmissionRepository(db)
        self._feedback_repo = TaskFeedbackRepository(db)

    def get_by_submission(
        self,
        submission_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> TaskFeedback:
        """Retrieve feedback for a specific submission.

        Args:
            submission_id: UUID of the submission.
            user_id: UUID of the requesting user (for authorization).

        Returns:
            The ``TaskFeedback`` ORM instance.

        Raises:
            TaskFeedbackError: ``SUBMISSION_NOT_FOUND`` if submission does not exist.
            TaskFeedbackError: ``UNAUTHORIZED`` if submission belongs to another user.
            TaskFeedbackError: ``FEEDBACK_NOT_FOUND`` if no feedback generated yet.
        """
        submission = self._sub_repo.get_by_id(submission_id)
        if submission is None:
            raise TaskFeedbackError(
                f"Task submission with id '{submission_id}' not found.",
                code=TaskFeedbackError.SUBMISSION_NOT_FOUND,
            )

        if submission.user_id != user_id:
            raise TaskFeedbackError(
                "You do not have permission to view feedback for this submission.",
                code=TaskFeedbackError.UNAUTHORIZED,
            )

        feedback = self._feedback_repo.get_by_submission_id(submission_id)
        if feedback is None:
            raise TaskFeedbackError(
                f"No feedback has been generated for submission '{submission_id}' yet.",
                code=TaskFeedbackError.FEEDBACK_NOT_FOUND,
            )

        return feedback

    def list_user_feedback(
        self,
        user_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[TaskFeedback], int]:
        """Retrieve all feedback records for the authenticated user.

        Args:
            user_id: UUID of the user.
            skip: Pagination offset.
            limit: Maximum results.

        Returns:
            Tuple of (list of ``TaskFeedback`` instances, total count).
        """
        return self._feedback_repo.list_by_user_id(user_id, skip=skip, limit=limit)
