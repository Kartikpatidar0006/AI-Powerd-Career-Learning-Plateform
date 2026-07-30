"""
backend/app/services/interview.py
==================================
Business-logic service layer for Interview Scheduling.

What this module does
---------------------
Provides ``InterviewSchedulerService`` and ``InterviewService`` to handle:
  1. Automated scheduling of 10-minute interviews based on task eligibility.
  2. Retrieving interview details by ID or listing user interviews.
  3. Cancelling scheduled interviews.

Eligibility Rules
-----------------
An interview can ONLY be scheduled if:
  - TaskSubmission exists for the user + task.
  - TaskFeedback.status == "Generated".
  - TaskFeedback.overall_score >= 70.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.interview import Interview
from app.repositories.interview import InterviewRepository
from app.repositories.task import TaskRepository, TaskSubmissionRepository
from app.repositories.task_feedback import TaskFeedbackRepository

logger: logging.Logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Domain exception
# ─────────────────────────────────────────────────────────────────────────────


class InterviewError(Exception):
    """Business-rule violation raised by Interview services.

    Code constants:
        ``TASK_NOT_FOUND``        — task UUID does not exist.
        ``SUBMISSION_NOT_FOUND``  — task submission missing for user + task.
        ``NOT_ELIGIBLE``          — feedback missing, not generated, or overall_score < 70.
        ``ALREADY_SCHEDULED``     — active interview already scheduled for task.
        ``INTERVIEW_NOT_FOUND``   — interview UUID does not exist.
        ``UNAUTHORIZED``          — user does not have permission.
    """

    TASK_NOT_FOUND: str = "task_not_found"
    SUBMISSION_NOT_FOUND: str = "submission_not_found"
    NOT_ELIGIBLE: str = "not_eligible"
    ALREADY_SCHEDULED: str = "already_scheduled"
    INTERVIEW_NOT_FOUND: str = "interview_not_found"
    UNAUTHORIZED: str = "unauthorized"

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code

    def __repr__(self) -> str:
        return f"InterviewError(code={self.code!r}, message={self.message!r})"


# =========================================================================== #
#  InterviewSchedulerService                                                  #
# =========================================================================== #


class InterviewSchedulerService:
    """Service responsible for evaluating eligibility and scheduling interviews.

    Args:
        db: An active SQLAlchemy ``Session``.
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._task_repo = TaskRepository(db)
        self._sub_repo = TaskSubmissionRepository(db)
        self._feedback_repo = TaskFeedbackRepository(db)
        self._interview_repo = InterviewRepository(db)

    def schedule_interview(
        self,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Interview:
        """Evaluate task evaluation score and schedule a 10-minute interview.

        Eligibility requirements:
          1. Task exists.
          2. User submitted work for the task.
          3. TaskFeedback has status == 'Generated' AND overall_score >= 70.

        Args:
            task_id: UUID of the task.
            user_id: UUID of the learner requesting the interview.

        Returns:
            The created ``Interview`` ORM instance.

        Raises:
            InterviewError: TASK_NOT_FOUND if task missing.
            InterviewError: SUBMISSION_NOT_FOUND if user hasn't submitted task.
            InterviewError: NOT_ELIGIBLE if feedback missing or overall_score < 70.
            InterviewError: ALREADY_SCHEDULED if an active interview already exists.
        """
        # 1. Validate task
        task = self._task_repo.get_by_id(task_id)
        if task is None:
            raise InterviewError(
                f"Task with id '{task_id}' not found.",
                code=InterviewError.TASK_NOT_FOUND,
            )

        # 2. Validate submission
        submission = self._sub_repo.get_by_user_and_task(user_id, task_id)
        if submission is None:
            raise InterviewError(
                f"No submission found for task '{task.title}'. Complete and submit the task first.",
                code=InterviewError.SUBMISSION_NOT_FOUND,
            )

        # 3. Validate feedback & eligibility score
        feedback = self._feedback_repo.get_by_submission_id(submission.id)
        if feedback is None or feedback.status != "Generated":
            raise InterviewError(
                "Task submission has not been evaluated yet. Please evaluate the task first.",
                code=InterviewError.NOT_ELIGIBLE,
            )

        if feedback.overall_score < 70:
            raise InterviewError(
                f"Overall score is {feedback.overall_score}%. A minimum score of 70% is required to qualify for an interview.",
                code=InterviewError.NOT_ELIGIBLE,
            )

        # 4. Check for existing active interview
        existing = self._interview_repo.get_by_user_and_task(user_id, task_id)
        if existing is not None:
            raise InterviewError(
                f"An interview is already {existing.status.lower()} for this task.",
                code=InterviewError.ALREADY_SCHEDULED,
            )

        # 5. Schedule 10-minute interview (Default time: UTC current time + 1 hour)
        scheduled_time = datetime.now(timezone.utc) + timedelta(hours=1)
        meeting_room_link = f"https://meet.careerhub.ai/room/{uuid.uuid4()}"

        interview = Interview(
            user_id=user_id,
            task_id=task_id,
            scheduled_at=scheduled_time,
            duration_minutes=10,
            status="Scheduled",
            meeting_link=meeting_room_link,
        )

        interview = self._interview_repo.create(interview)
        self._db.commit()
        logger.info("Scheduled interview id=%s for user=%s task=%s", interview.id, user_id, task_id)
        return interview


# =========================================================================== #
#  InterviewService                                                           #
# =========================================================================== #


class InterviewService:
    """Service for managing existing interview records.

    Args:
        db: An active SQLAlchemy ``Session``.
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._interview_repo = InterviewRepository(db)

    def get_by_id(
        self,
        interview_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Interview:
        """Fetch an interview by ID with ownership validation.

        Args:
            interview_id: UUID of the interview.
            user_id: UUID of the requesting user.

        Returns:
            The ``Interview`` ORM instance.

        Raises:
            InterviewError: INTERVIEW_NOT_FOUND if missing.
            InterviewError: UNAUTHORIZED if user does not own the interview.
        """
        interview = self._interview_repo.get_by_id(interview_id)
        if interview is None:
            raise InterviewError(
                f"Interview with id '{interview_id}' not found.",
                code=InterviewError.INTERVIEW_NOT_FOUND,
            )

        if interview.user_id != user_id:
            raise InterviewError(
                "You do not have permission to view this interview.",
                code=InterviewError.UNAUTHORIZED,
            )

        return interview

    def list_user_interviews(
        self,
        user_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Interview], int]:
        """List all interviews for a given user.

        Args:
            user_id: UUID of the user.
            skip: Pagination offset.
            limit: Maximum results.

        Returns:
            Tuple of (list of ``Interview`` instances, total count).
        """
        return self._interview_repo.list_by_user(user_id, skip=skip, limit=limit)

    def cancel_interview(
        self,
        interview_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Interview:
        """Cancel a scheduled interview.

        Args:
            interview_id: UUID of the interview to cancel.
            user_id: UUID of the requesting user.

        Returns:
            The updated ``Interview`` ORM instance.

        Raises:
            InterviewError: INTERVIEW_NOT_FOUND if missing.
            InterviewError: UNAUTHORIZED if not owned by user.
        """
        interview = self._interview_repo.get_by_id(interview_id)
        if interview is None:
            raise InterviewError(
                f"Interview with id '{interview_id}' not found.",
                code=InterviewError.INTERVIEW_NOT_FOUND,
            )

        if interview.user_id != user_id:
            raise InterviewError(
                "You do not have permission to cancel this interview.",
                code=InterviewError.UNAUTHORIZED,
            )

        interview.status = "Cancelled"
        interview = self._interview_repo.update(interview)
        self._db.commit()
        logger.info("Cancelled interview id=%s for user=%s", interview_id, user_id)
        return interview
