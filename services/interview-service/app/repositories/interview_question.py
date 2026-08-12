"""
backend/app/repositories/interview_question.py
================================================
Repository pattern implementations for ``interview_questions`` and
``interview_answers`` tables.

Architecture contract
---------------------
- **Single responsibility**: SQL queries only.
- **Session ownership**: caller (service/dependency) owns commit/rollback.
  Calls ``flush()`` after mutating operations.
- **Returns ORM objects only**.
- **Rollback on failure**: wraps mutating methods in try/except SQLAlchemyError → rollback → re-raise.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.interview_question import InterviewAnswer, InterviewQuestion

logger: logging.Logger = logging.getLogger(__name__)


class InterviewQuestionRepository:
    """Data-access layer for the ``interview_questions`` table.

    Args:
        session: An active SQLAlchemy ``Session``.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, question_id: uuid.UUID) -> Optional[InterviewQuestion]:
        """Fetch a question by UUID primary key.

        Args:
            question_id: UUID PK.

        Returns:
            The matching ``InterviewQuestion`` ORM instance, or ``None``.
        """
        logger.debug("get_by_id | question_id=%s", question_id)
        return self._session.get(InterviewQuestion, question_id)

    def list_by_interview(self, interview_id: uuid.UUID) -> list[InterviewQuestion]:
        """Fetch all questions for an interview, ordered by order_no ASC.

        Args:
            interview_id: UUID of parent interview.

        Returns:
            List of ``InterviewQuestion`` ORM instances in order sequence.
        """
        logger.debug("list_by_interview | interview_id=%s", interview_id)
        stmt = (
            select(InterviewQuestion)
            .where(InterviewQuestion.interview_id == interview_id)
            .order_by(InterviewQuestion.order_no.asc())
        )
        return list(self._session.execute(stmt).scalars().all())

    def bulk_create(self, questions: list[InterviewQuestion]) -> list[InterviewQuestion]:
        """Persist a list of new questions.

        Args:
            questions: List of populated ``InterviewQuestion`` instances.

        Returns:
            List of created instances.
        """
        logger.debug("bulk_create | count=%d", len(questions))
        try:
            self._session.add_all(questions)
            self._session.flush()
            for q in questions:
                self._session.refresh(q)
            return questions
        except SQLAlchemyError as exc:
            logger.error("Failed to bulk create questions: %s", exc, exc_info=True)
            self._session.rollback()
            raise


class InterviewAnswerRepository:
    """Data-access layer for the ``interview_answers`` table.

    Args:
        session: An active SQLAlchemy ``Session``.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_question_and_user(
        self,
        question_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Optional[InterviewAnswer]:
        """Fetch answer for a specific question + user pair.

        Args:
            question_id: UUID of question.
            user_id: UUID of user.

        Returns:
            Matching ``InterviewAnswer`` or ``None``.
        """
        logger.debug(
            "get_by_question_and_user | question=%s user=%s", question_id, user_id
        )
        stmt = (
            select(InterviewAnswer)
            .where(InterviewAnswer.question_id == question_id)
            .where(InterviewAnswer.user_id == user_id)
        )
        return self._session.execute(stmt).scalars().first()

    def create(self, answer: InterviewAnswer) -> InterviewAnswer:
        """Persist a new answer.

        Args:
            answer: Populated ``InterviewAnswer`` instance.

        Returns:
            Created instance with server defaults populated.
        """
        logger.debug(
            "create | question=%s user=%s", answer.question_id, answer.user_id
        )
        try:
            self._session.add(answer)
            self._session.flush()
            self._session.refresh(answer)
            return answer
        except SQLAlchemyError as exc:
            logger.error("Failed to create answer: %s", exc, exc_info=True)
            self._session.rollback()
            raise

    def update(self, answer: InterviewAnswer) -> InterviewAnswer:
        """Flush pending changes on an existing answer.

        Args:
            answer: Modified ``InterviewAnswer`` instance.

        Returns:
            Refreshed instance.
        """
        logger.debug("update | answer.id=%s", answer.id)
        try:
            self._session.flush()
            self._session.refresh(answer)
            return answer
        except SQLAlchemyError as exc:
            logger.error("Failed to update answer: %s", exc, exc_info=True)
            self._session.rollback()
            raise
