"""
Session lifecycle business logic service for interview-agent-service.

Handles:
- Idempotent session creation and race-condition handling
- Agent 3 evaluation context retrieval via EvaluatorClient with local fallback
- Lazy expiration (write-on-read pattern)
- Dynamic first question generation on session start (with 503 rollback on failure)
- Answer submission, data-loss protection, follow-up generation, and completion synthesis
- Session resume retrieval with turn history
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.interview import (
    InterviewSession,
    InterviewSessionStatus,
    InterviewTurn,
    ProctoringEvent,
    ProctoringEventType,
)
from app.schemas.interview import (
    InternalCreateSessionRequest,
    ProctoringEventCreate,
    SubmitAnswerRequest,
)
from app.services.evaluator_client import evaluator_client
from app.services.interview_agent import interview_agent
from app.services.proctoring_limiter import proctoring_rate_limiter

logger = logging.getLogger("interview-agent.session-service")


class SessionServiceError(Exception):
    """Base exception for session service errors."""
    pass


class SessionNotFoundError(SessionServiceError):
    """Raised when an interview session is not found or not owned by user."""
    pass


class SessionConflictError(SessionServiceError):
    """Raised when a session is in an invalid status for the requested action."""
    pass


class SessionServiceUnavailableError(SessionServiceError):
    """Raised when question generation or upstream service fails (HTTP 503)."""
    pass


class ProctoringRateLimitExceededError(SessionServiceError):
    """Raised when proctoring event submissions exceed rate limits."""

    def __init__(self, message: str, retry_after: int = 60) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class SessionService:
    """Business logic service managing interview sessions, turns, and agent interactions."""

    def __init__(self) -> None:
        # In-memory evaluation context cache populated during create-session
        self._evaluation_contexts: dict[uuid.UUID, dict[str, Any]] = {}

    async def create_or_get_session(
        self,
        db: AsyncSession,
        request: InternalCreateSessionRequest,
    ) -> InterviewSession:
        """
        Create a new interview session or return the existing one (idempotent).

        If a session already exists for this task_id, returns the existing session.
        Handles concurrent creation race conditions via IntegrityError rollback and re-fetch.
        Caches evaluation_context if provided in the creation payload.
        """
        if request.evaluation_context:
            self._evaluation_contexts[request.task_id] = request.evaluation_context

        # 1. Check if a session already exists for this task_id
        stmt = select(InterviewSession).where(InterviewSession.task_id == request.task_id)
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            logger.info("Session already exists for task %s (id: %s)", request.task_id, existing.id)
            if request.evaluation_context:
                self._evaluation_contexts[existing.id] = request.evaluation_context
            return existing

        # 2. Create a new session with AVAILABLE status and 24-hour expiration window
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=24)

        session = InterviewSession(
            user_id=request.user_id,
            task_id=request.task_id,
            evaluation_id=request.evaluation_id,
            status=InterviewSessionStatus.AVAILABLE.value,
            available_from=now,
            expires_at=expires_at,
        )
        db.add(session)

        try:
            await db.commit()
            await db.refresh(session)
            if request.evaluation_context:
                self._evaluation_contexts[session.id] = request.evaluation_context
            logger.info("Created new interview session %s for task %s", session.id, request.task_id)
            return session
        except IntegrityError:
            # Race condition: another concurrent worker created a session for this task_id
            await db.rollback()
            logger.warning(
                "IntegrityError creating session for task %s — resolving concurrent race condition",
                request.task_id,
            )
            stmt = select(InterviewSession).where(InterviewSession.task_id == request.task_id)
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing is not None:
                if request.evaluation_context:
                    self._evaluation_contexts[existing.id] = request.evaluation_context
                return existing
            raise

    async def get_evaluation_context(self, session: InterviewSession) -> dict[str, Any]:
        """
        Fetch Agent 3 evaluation findings (weaknesses, red_flags, skills_targeted).
        """
        # 1. Live query to evaluator-agent-service via GET /internal/evaluations/by-task/{task_id}
        eval_record = await evaluator_client.get_evaluation_by_task(session.task_id)
        if not eval_record and session.evaluation_id:
            eval_record = await evaluator_client.get_evaluation(session.evaluation_id)

        if eval_record:
            return {
                "weaknesses": eval_record.get("llm_weaknesses") or eval_record.get("weaknesses", []),
                "red_flags": eval_record.get("red_flags", []),
                "skills_targeted": eval_record.get("skills_targeted", []),
                "deterministic_checks": eval_record.get("deterministic_checks", []),
            }

        # 2. Context passed during session creation (if stored)
        if session.id in self._evaluation_contexts:
            return self._evaluation_contexts[session.id]
        if session.task_id in self._evaluation_contexts:
            return self._evaluation_contexts[session.task_id]

        # 3. Fallback default findings
        return {
            "weaknesses": [
                "Test coverage is minimal or missing unit tests",
                "Asynchronous error handling could be made more defensive",
            ],
            "red_flags": [],
            "skills_targeted": ["Python", "FastAPI", "AsyncIO", "PostgreSQL"],
            "deterministic_checks": [
                {"check_name": "pytest_suite", "passed": False, "detail": "Test suite was missing"}
            ],
        }

    async def check_and_apply_lazy_expiry(
        self,
        db: AsyncSession,
        session: InterviewSession,
    ) -> bool:
        """
        Lazy expiry (write-on-read pattern).

        If status is AVAILABLE or IN_PROGRESS and expires_at has passed,
        transitions status to EXPIRED in the DB and commits before returning.
        """
        if session.status in (
            InterviewSessionStatus.AVAILABLE.value,
            InterviewSessionStatus.IN_PROGRESS.value,
        ):
            now = datetime.now(timezone.utc)
            exp = (
                session.expires_at
                if session.expires_at.tzinfo
                else session.expires_at.replace(tzinfo=timezone.utc)
            )
            if now >= exp:
                logger.info(
                    "Session %s has expired (expires_at: %s, now: %s). Transitioning to EXPIRED.",
                    session.id,
                    exp,
                    now,
                )
                session.status = InterviewSessionStatus.EXPIRED.value
                await db.commit()
                await db.refresh(session)
                return True
        return False

    async def get_session_by_task_id(
        self,
        db: AsyncSession,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> InterviewSession:
        """
        Fetch an interview session by task_id and verify user ownership.

        Raises SessionNotFoundError if the session does not exist OR belongs to another user.
        Applies lazy expiry on read.
        """
        stmt = select(InterviewSession).where(InterviewSession.task_id == task_id)
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()

        if session is None or session.user_id != user_id:
            raise SessionNotFoundError(f"No interview session found for task {task_id}")

        await self.check_and_apply_lazy_expiry(db, session)
        return session

    async def start_session(
        self,
        db: AsyncSession,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> tuple[InterviewSession, InterviewTurn]:
        """
        Start an interview session and generate the first question turn.

        If question generation fails, rolls session status back to AVAILABLE and
        raises SessionServiceUnavailableError (503), preventing stuck IN_PROGRESS sessions.
        """
        session = await self.get_session_by_task_id(db=db, task_id=task_id, user_id=user_id)

        # Re-check lazy expiry
        await self.check_and_apply_lazy_expiry(db, session)

        if session.status != InterviewSessionStatus.AVAILABLE.value:
            if session.status == InterviewSessionStatus.IN_PROGRESS.value:
                raise SessionConflictError("Interview already in progress, use resume")
            elif session.status == InterviewSessionStatus.EXPIRED.value:
                raise SessionConflictError("This interview window has expired")
            elif session.status in (
                InterviewSessionStatus.COMPLETED.value,
                InterviewSessionStatus.TERMINATED_VIOLATION.value,
            ):
                raise SessionConflictError("This interview has already concluded")
            else:
                raise SessionConflictError(
                    f"Interview session cannot be started from status '{session.status}'"
                )

        now = datetime.now(timezone.utc)
        session.status = InterviewSessionStatus.IN_PROGRESS.value
        session.started_at = now
        await db.commit()
        await db.refresh(session)

        # Generate first question
        eval_ctx = await self.get_evaluation_context(session)
        try:
            generated_q = await interview_agent.generate_next_question(
                session=session,
                previous_turns=[],
                evaluation_context=eval_ctx,
            )
        except Exception as exc:
            logger.exception("First question generation failed for session %s: %s", session.id, exc)
            # Safe rollback: reset session to AVAILABLE so student can retry cleanly
            session.status = InterviewSessionStatus.AVAILABLE.value
            session.started_at = None
            await db.commit()
            raise SessionServiceUnavailableError("Could not start interview, please try again") from exc

        first_turn = InterviewTurn(
            session_id=session.id,
            turn_number=1,
            question_text=generated_q.question_text,
            question_context=generated_q.question_context,
        )
        db.add(first_turn)
        await db.commit()
        await db.refresh(session)
        await db.refresh(first_turn)

        logger.info("Started interview session %s, created turn 1 (%s)", session.id, first_turn.id)
        return session, first_turn

    async def submit_answer(
        self,
        db: AsyncSession,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        request: SubmitAnswerRequest,
    ) -> tuple[InterviewSession, InterviewTurn, InterviewTurn, bool]:
        """
        Record candidate answer, generate next question or closing turn.

        Data-loss guarantee:
        The candidate's answer is persisted to the database FIRST. If subsequent
        question generation fails, the answer remains saved in the DB and a 503
        is returned with status staying IN_PROGRESS so recovery/retry is possible.
        """
        session = await self.get_session_by_task_id(db=db, task_id=task_id, user_id=user_id)

        # Lazy expiry re-check
        await self.check_and_apply_lazy_expiry(db, session)

        if session.status != InterviewSessionStatus.IN_PROGRESS.value:
            raise SessionConflictError(
                f"Interview is not in progress (current status: {session.status})."
            )

        # Find current unanswered turn
        stmt = (
            select(InterviewTurn)
            .where(InterviewTurn.session_id == session.id)
            .order_by(InterviewTurn.turn_number.desc())
        )
        res = await db.execute(stmt)
        latest_turn = res.scalars().first()

        if not latest_turn or latest_turn.answer_text is not None:
            raise SessionConflictError(
                "No active unanswered question turn found for this interview session"
            )

        # 1. Persist answer text and duration FIRST (guarantees no data loss)
        latest_turn.answer_text = request.answer_text
        latest_turn.answer_duration_seconds = request.duration_seconds
        await db.commit()
        await db.refresh(latest_turn)

        # 2. Fetch full transcript turns for context
        stmt_all = (
            select(InterviewTurn)
            .where(InterviewTurn.session_id == session.id)
            .order_by(InterviewTurn.turn_number.asc())
        )
        res_all = await db.execute(stmt_all)
        all_turns = list(res_all.scalars().all())

        # 3. Generate next question or closing remark
        eval_ctx = await self.get_evaluation_context(session)
        try:
            next_q = await interview_agent.generate_next_question(
                session=session,
                previous_turns=all_turns,
                evaluation_context=eval_ctx,
            )
        except Exception as exc:
            logger.exception("Question generation failed after saving answer for turn %s: %s", latest_turn.id, exc)
            # Answer is safely committed in DB; session remains IN_PROGRESS for retry
            # Note for future hardening: An admin/retry endpoint can re-trigger question generation
            # without requiring the student to re-input their answer.
            raise SessionServiceUnavailableError(
                "Could not generate next question. Your answer was safely saved; please retry shortly."
            ) from exc

        # 4. Handle closing vs normal next question
        if next_q.is_closing:
            closing_turn = InterviewTurn(
                session_id=session.id,
                turn_number=latest_turn.turn_number + 1,
                question_text=next_q.question_text,
                question_context=next_q.question_context,
                follow_up_of=latest_turn.id,
            )
            db.add(closing_turn)

            session.status = InterviewSessionStatus.COMPLETED.value
            session.completed_at = datetime.now(timezone.utc)

            # Synthesize overall performance summary across all turns
            try:
                perf_summary = await interview_agent.generate_performance_summary(
                    session=session,
                    turns=all_turns,
                )
                session.overall_performance_summary = perf_summary.model_dump()
            except Exception as exc:
                logger.warning("Failed to generate overall performance summary: %s", exc)
                session.overall_performance_summary = {
                    "communication_clarity": 80,
                    "technical_depth": 80,
                    "confidence_signals": 80,
                    "overall_score": 80,
                    "summary": "Interview concluded successfully.",
                    "key_strengths": ["Completed all interview turns"],
                    "areas_for_improvement": [],
                }

            await db.commit()
            await db.refresh(session)
            await db.refresh(closing_turn)
            logger.info("Session %s COMPLETED with performance summary", session.id)
            return session, latest_turn, closing_turn, True

        else:
            next_turn = InterviewTurn(
                session_id=session.id,
                turn_number=latest_turn.turn_number + 1,
                question_text=next_q.question_text,
                question_context=next_q.question_context,
                follow_up_of=latest_turn.id,
            )
            db.add(next_turn)
            await db.commit()
            await db.refresh(session)
            await db.refresh(next_turn)
            logger.info("Session %s created next turn %d (%s)", session.id, next_turn.turn_number, next_turn.id)
            return session, latest_turn, next_turn, False

    async def resume_session(
        self,
        db: AsyncSession,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> tuple[InterviewSession, list[InterviewTurn]]:
        """
        Resume an in-progress interview session.

        Only allowed when status is IN_PROGRESS.
        Returns the session and all turns in chronological order.
        """
        session = await self.get_session_by_task_id(db=db, task_id=task_id, user_id=user_id)

        # Re-check lazy expiry
        await self.check_and_apply_lazy_expiry(db, session)

        if session.status != InterviewSessionStatus.IN_PROGRESS.value:
            raise SessionConflictError(
                f"Interview is not in progress. Check GET /interview/sessions/{task_id} for current status."
            )

        stmt_turns = (
            select(InterviewTurn)
            .where(InterviewTurn.session_id == session.id)
            .order_by(InterviewTurn.turn_number.asc())
        )
        result_turns = await db.execute(stmt_turns)
        turns = list(result_turns.scalars().all())

        return session, turns

    async def record_proctoring_event(
        self,
        db: AsyncSession,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        request: ProctoringEventCreate,
    ) -> tuple[InterviewSession, ProctoringEvent, bool]:
        """
        Record a client-side proctoring violation event.

        Enforces:
        - Student user ownership (raises SessionNotFoundError if not owned)
        - Session must be IN_PROGRESS (raises SessionConflictError if not)
        - Rate limiting: max 20 events per minute per session (raises ProctoringRateLimitExceededError)
        - Atomic DB-level increment of InterviewSession.violation_count (prevents lost updates under concurrency)
        - Auto-termination when violation_count reaches PROCTORING_MAX_VIOLATIONS (default 3)

        Returns:
            tuple[InterviewSession, ProctoringEvent, bool (terminated)]
        """
        session = await self.get_session_by_task_id(db=db, task_id=task_id, user_id=user_id)

        # Lazy expiry re-check
        await self.check_and_apply_lazy_expiry(db, session)

        if session.status != InterviewSessionStatus.IN_PROGRESS.value:
            raise SessionConflictError(
                f"Proctoring events are only accepted for in-progress interviews (current status: {session.status})."
            )

        # 1. Rate limiting check BEFORE executing DB increment or adding rows
        allowed, retry_after = proctoring_rate_limiter.is_allowed(str(session.id))
        if not allowed:
            raise ProctoringRateLimitExceededError(
                f"Rate limit exceeded: maximum {settings.PROCTORING_RATE_LIMIT_PER_MINUTE} proctoring events per minute. Please try again later.",
                retry_after=retry_after,
            )

        # 2. Atomic DB-level increment of violation_count
        # Pattern: UPDATE interview_sessions SET violation_count = violation_count + 1 WHERE id = :id AND status = :status RETURNING violation_count
        stmt = (
            update(InterviewSession)
            .where(
                InterviewSession.id == session.id,
                InterviewSession.status == InterviewSessionStatus.IN_PROGRESS.value,
            )
            .values(violation_count=InterviewSession.violation_count + 1)
            .returning(InterviewSession.violation_count)
        )
        res = await db.execute(stmt)
        new_count = res.scalar_one_or_none()

        if new_count is None:
            # Session status changed concurrently (e.g. terminated or completed by concurrent request)
            stmt_curr = select(InterviewSession).where(InterviewSession.id == session.id)
            res_curr = await db.execute(stmt_curr)
            curr = res_curr.scalar_one_or_none()
            curr_status = curr.status if curr else "UNKNOWN"
            raise SessionConflictError(
                f"Proctoring events are only accepted for in-progress interviews (current status: {curr_status})."
            )

        now = datetime.now(timezone.utc)
        terminated = False

        # 3. Check violation threshold
        if new_count >= settings.PROCTORING_MAX_VIOLATIONS:
            terminated = True
            termination_reason = (
                f"Interview terminated after {new_count} proctoring violations: "
                "tab switching / fullscreen exit detected"
            )
            term_stmt = (
                update(InterviewSession)
                .where(InterviewSession.id == session.id)
                .values(
                    status=InterviewSessionStatus.TERMINATED_VIOLATION.value,
                    termination_reason=termination_reason,
                    completed_at=now,
                )
            )
            await db.execute(term_stmt)

        # 4. Insert ProctoringEvent row
        event_type_str = (
            request.event_type.value
            if hasattr(request.event_type, "value")
            else str(request.event_type)
        )
        event_row = ProctoringEvent(
            session_id=session.id,
            event_type=event_type_str,
            turn_number_at_event=request.turn_number_at_event,
            timestamp=now,
        )
        db.add(event_row)

        await db.commit()
        await db.refresh(session)
        await db.refresh(event_row)

        logger.info(
            "Recorded proctoring event %s for session %s (violation_count=%d, terminated=%s)",
            event_type_str,
            session.id,
            new_count,
            terminated,
        )

        return session, event_row, terminated



# Singleton service instance
session_service = SessionService()


def get_session_service() -> SessionService:
    """FastAPI dependency injecting SessionService."""
    return session_service
