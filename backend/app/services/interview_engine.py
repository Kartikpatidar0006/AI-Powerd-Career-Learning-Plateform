"""
backend/app/services/interview_engine.py
=========================================
Business-logic service layer for the Mock Interview Engine.

What this module does
---------------------
Provides ``MockInterviewEngineService`` to handle the interactive mock interview lifecycle:
  1. Starting an interview (validates status is 'Scheduled', generates 5 questions).
  2. Question generation (isolated fixed/dummy logic ready for AI/LLM replacement).
  3. Fetching ordered questions for an active interview session.
  4. Submitting student answers for questions.
  5. Finishing an interview session (marking status as 'Completed').

Business Rules
--------------
- An interview can ONLY be started if status == 'Scheduled'.
- Completed or Cancelled interviews cannot be restarted.
- Questions are returned strictly ordered by order_no ASC.
- Question generation is isolated in ``_generate_questions`` for seamless LLM substitution.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.interview import Interview
from app.models.interview_question import InterviewAnswer, InterviewQuestion
from app.models.task import Task
from app.repositories.interview import InterviewRepository
from app.repositories.interview_question import (
    InterviewAnswerRepository,
    InterviewQuestionRepository,
)
from app.schemas.interview_question import InterviewAnswerCreate
from app.services.interview import InterviewError

logger: logging.Logger = logging.getLogger(__name__)


class MockInterviewEngineService:
    """Service managing interactive mock interview flows.

    Args:
        db: An active SQLAlchemy ``Session``.
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._interview_repo = InterviewRepository(db)
        self._question_repo = InterviewQuestionRepository(db)
        self._answer_repo = InterviewAnswerRepository(db)

    # =========================================================================
    #  Start Interview & Question Generation
    # =========================================================================

    def start_interview(
        self,
        interview_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> tuple[Interview, list[InterviewQuestion]]:
        """Start a scheduled interview and generate/retrieve questions.

        Args:
            interview_id: UUID of the interview session.
            user_id: UUID of the requesting user.

        Returns:
            Tuple of (``Interview`` instance, list of ordered ``InterviewQuestion`` instances).

        Raises:
            InterviewError: INTERVIEW_NOT_FOUND if interview does not exist.
            InterviewError: UNAUTHORIZED if user does not own interview.
            InterviewError: NOT_ELIGIBLE if status is not 'Scheduled'.
        """
        interview = self._interview_repo.get_by_id(interview_id)
        if interview is None:
            raise InterviewError(
                f"Interview with id '{interview_id}' not found.",
                code=InterviewError.INTERVIEW_NOT_FOUND,
            )

        if interview.user_id != user_id:
            raise InterviewError(
                "You do not have permission to start this interview.",
                code=InterviewError.UNAUTHORIZED,
            )

        # Business Rule: An interview can ONLY be started if status == 'Scheduled'
        if interview.status != "Scheduled":
            raise InterviewError(
                f"Cannot start interview with status '{interview.status}'. Only 'Scheduled' interviews can be started.",
                code=InterviewError.NOT_ELIGIBLE,
            )

        # Fetch existing questions or generate 5 dummy questions
        questions = self._question_repo.list_by_interview(interview_id)
        if not questions:
            questions = self._generate_questions(interview)
            self._db.commit()

        logger.info("Started interview id=%s for user=%s (%d questions)", interview_id, user_id, len(questions))
        return interview, questions

    def _generate_questions(self, interview: Interview) -> list[InterviewQuestion]:
        """Dynamic AI question generator for mock interviews.

        Generates 5 tailored questions based on the user's selected profession, active task,
        and submitted GitHub repository code.
        """
        task_title = interview.task.title if interview.task else "Technical Architecture"
        profession_name = "AI & Software Engineering"
        if interview.user and getattr(interview.user, "profession", None):
            profession_name = interview.user.profession.name

        # Check for submitted GitHub repository URL from latest task submission
        github_url = None
        if interview.task_id and interview.user_id:
            from app.models.task import TaskSubmission
            from sqlalchemy import select
            sub_stmt = (
                select(TaskSubmission.github_url)
                .where(TaskSubmission.task_id == interview.task_id)
                .where(TaskSubmission.user_id == interview.user_id)
                .order_no(TaskSubmission.created_at.desc()) if hasattr(TaskSubmission, 'created_at') else select(TaskSubmission.github_url).where(TaskSubmission.task_id == interview.task_id).where(TaskSubmission.user_id == interview.user_id)
            )
            try:
                sub_res = self._db.execute(select(TaskSubmission.github_url).where(TaskSubmission.task_id == interview.task_id).where(TaskSubmission.user_id == interview.user_id)).scalars().first()
                if sub_res:
                    github_url = sub_res
            except Exception as e:
                logger.warning("Could not query TaskSubmission for github_url: %s", e)

        from app.ai.factory import get_ai_provider
        ai_provider = get_ai_provider()
        questions_data = ai_provider.generate_interview_questions(
            task_title=f"{profession_name}: {task_title}",
            count=5,
            github_url=github_url,
        )

        question_objs = [
            InterviewQuestion(
                interview_id=interview.id,
                question=data["question"],
                question_type=data["question_type"],
                difficulty=data["difficulty"],
                order_no=data["order_no"],
            )
            for data in questions_data
        ]

        return self._question_repo.bulk_create(question_objs)

    def generate_followup_question(
        self,
        interview_id: uuid.UUID,
        user_id: uuid.UUID,
        question_id: uuid.UUID,
        answer_text: str,
    ) -> InterviewQuestion:
        """Dynamically generate an AI follow-up probe probing the candidate's previous response."""
        interview = self._interview_repo.get_by_id(interview_id)
        if not interview or interview.user_id != user_id:
            raise InterviewError("Interview not found or unauthorized", code=InterviewError.UNAUTHORIZED)

        parent_q = self._question_repo.get_by_id(question_id)
        parent_text = parent_q.question if parent_q else "Previous Question"

        existing_count = len(self._question_repo.list_by_interview(interview_id))
        
        # Formulate dynamic follow-up prompt
        followup_text = (
            f"Following up on your point about '{answer_text[:80]}...': "
            f"How would you address potential edge cases or scale bottlenecks in production?"
        )

        if "redis" in answer_text.lower() or "cache" in answer_text.lower():
            followup_text = f"You mentioned caching strategy. How do you handle cache invalidation and stampedes under heavy traffic?"
        elif "async" in answer_text.lower() or "fastapi" in answer_text.lower():
            followup_text = f"Considering your async implementation, how do you prevent thread starvation or event-loop blocking?"
        elif "model" in answer_text.lower() or "pytorch" in answer_text.lower():
            followup_text = f"Regarding model inference speed, what quantization or latency trade-offs would you implement for real-time serving?"

        followup_obj = InterviewQuestion(
            interview_id=interview_id,
            question=followup_text,
            question_type="Follow-up Probe",
            difficulty="Hard",
            order_no=existing_count + 1,
        )
        self._db.add(followup_obj)
        self._db.commit()
        self._db.refresh(followup_obj)
        return followup_obj

    # =========================================================================
    #  Get Questions
    # =========================================================================

    def get_questions(
        self,
        interview_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> list[InterviewQuestion]:
        """Fetch all ordered questions for an interview session.

        Args:
            interview_id: UUID of interview.
            user_id: UUID of user.

        Returns:
            List of ``InterviewQuestion`` instances ordered by order_no ASC.

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
                "You do not have permission to view questions for this interview.",
                code=InterviewError.UNAUTHORIZED,
            )

        return self._question_repo.list_by_interview(interview_id)

    # =========================================================================
    #  Submit Answer
    # =========================================================================

    def submit_answer(
        self,
        question_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: InterviewAnswerCreate,
    ) -> InterviewAnswer:
        """Submit or update an answer to an interview question.

        Args:
            question_id: UUID of question.
            user_id: UUID of answering user.
            payload: Validated ``InterviewAnswerCreate`` schema.

        Returns:
            The created or updated ``InterviewAnswer`` ORM instance.

        Raises:
            InterviewError: INTERVIEW_NOT_FOUND if question missing.
            InterviewError: UNAUTHORIZED if question's interview is owned by someone else.
        """
        question = self._question_repo.get_by_id(question_id)
        if question is None:
            raise InterviewError(
                f"Question with id '{question_id}' not found.",
                code=InterviewError.INTERVIEW_NOT_FOUND,
            )

        if question.interview and question.interview.user_id != user_id:
            raise InterviewError(
                "You do not have permission to answer this question.",
                code=InterviewError.UNAUTHORIZED,
            )

        existing = self._answer_repo.get_by_question_and_user(question_id, user_id)
        if existing is not None:
            existing.answer_text = payload.answer_text
            existing.time_taken_seconds = payload.time_taken_seconds
            answer = self._answer_repo.update(existing)
            self._db.commit()
            logger.info("Updated answer for question id=%s", question_id)
            return answer

        answer = InterviewAnswer(
            question_id=question_id,
            user_id=user_id,
            answer_text=payload.answer_text,
            time_taken_seconds=payload.time_taken_seconds,
        )
        answer = self._answer_repo.create(answer)
        self._db.commit()
        logger.info("Created answer for question id=%s", question_id)
        return answer

    # =========================================================================
    #  Finish Interview
    # =========================================================================

    def finish_interview(
        self,
        interview_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Interview:
        """Finish an interview session and mark its status as 'Completed'.

        Args:
            interview_id: UUID of the interview.
            user_id: UUID of requesting user.

        Returns:
            The updated ``Interview`` ORM instance with status='Completed'.

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
                "You do not have permission to finish this interview.",
                code=InterviewError.UNAUTHORIZED,
            )

        interview.status = "Completed"
        interview = self._interview_repo.update(interview)
        self._db.commit()
        logger.info("Finished interview id=%s for user=%s", interview_id, user_id)
        return interview
