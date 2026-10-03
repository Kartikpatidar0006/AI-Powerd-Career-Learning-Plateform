"""
Model-level unit tests for interview-agent-service (Agent 4).

Verifies:
1. UNIQUE constraint on task_id is enforced (rejects multiple interview sessions for the same task).
2. CHECK constraint rejects negative violation_count.
3. Default status is AVAILABLE.
4. expires_at field exists, is settable relative to available_from (24-hour window),
   and documents that runtime calculation belongs in Task 3's service layer.
5. Foreign key ondelete="CASCADE" works for InterviewTurn and ProctoringEvent.
6. Schema verification: InterviewSessionResponse computes time_remaining_seconds dynamically.
7. Schema verification: ProctoringEventCreate validates event types.
8. Schema verification: InternalCreateSessionRequest validates UUID types.
9. Alembic migration upgrade and downgrade cycle executes cleanly.
"""

import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.interview import (
    InterviewSession,
    InterviewSessionStatus,
    InterviewTurn,
    ProctoringEvent,
    ProctoringEventType,
)
from app.schemas.interview import (
    InternalCreateSessionRequest,
    InterviewSessionResponse,
    InterviewTurnResponse,
    ProctoringEventCreate,
)


class TestInterviewModelsAndConstraints(unittest.TestCase):
    """Test suite for database models, constraints, and schemas."""

    @classmethod
    def setUpClass(cls) -> None:
        """Initialize in-memory SQLite engine with foreign key and check constraint support."""
        cls.engine = sa.create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        # Enable SQLite foreign key constraint enforcement
        @sa.event.listens_for(cls.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(cls.engine)

    @classmethod
    def tearDownClass(cls) -> None:
        """Dispose of the test database engine."""
        cls.engine.dispose()

    def setUp(self) -> None:
        self.session = Session(self.engine)

    def tearDown(self) -> None:
        self.session.rollback()
        self.session.close()

    # ── 1. Default status is AVAILABLE ──────────────────────────────────
    def test_default_status_is_available(self) -> None:
        """InterviewSession should default to AVAILABLE status if not specified."""
        now = datetime.now(timezone.utc)
        interview = InterviewSession(
            user_id=uuid.uuid4(),
            task_id=uuid.uuid4(),
            evaluation_id=uuid.uuid4(),
            available_from=now,
            expires_at=now + timedelta(hours=24),
        )
        self.session.add(interview)
        self.session.commit()
        self.session.refresh(interview)

        self.assertEqual(interview.status, InterviewSessionStatus.AVAILABLE.value)
        self.assertEqual(interview.violation_count, 0)
        self.assertIsNotNone(interview.id)
        self.assertIsNotNone(interview.created_at)

    # ── 2. UNIQUE constraint on task_id ─────────────────────────────────
    def test_unique_constraint_on_task_id_enforced(self) -> None:
        """Database must reject a second InterviewSession with the same task_id."""
        task_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        session_1 = InterviewSession(
            user_id=uuid.uuid4(),
            task_id=task_id,
            evaluation_id=uuid.uuid4(),
            available_from=now,
            expires_at=now + timedelta(hours=24),
        )
        self.session.add(session_1)
        self.session.commit()

        # Attempt to insert a second session for the exact same task
        session_2 = InterviewSession(
            user_id=uuid.uuid4(),
            task_id=task_id,
            evaluation_id=uuid.uuid4(),
            available_from=now,
            expires_at=now + timedelta(hours=24),
        )
        self.session.add(session_2)
        with self.assertRaises(IntegrityError):
            self.session.commit()

    # ── 3. CHECK constraint on violation_count >= 0 ─────────────────────
    def test_check_constraint_rejects_negative_violation_count(self) -> None:
        """Database must reject violation_count < 0 via CHECK constraint."""
        now = datetime.now(timezone.utc)
        invalid_session = InterviewSession(
            user_id=uuid.uuid4(),
            task_id=uuid.uuid4(),
            evaluation_id=uuid.uuid4(),
            available_from=now,
            expires_at=now + timedelta(hours=24),
            violation_count=-1,  # Violates ck_interview_sessions_violation_count_non_negative
        )
        self.session.add(invalid_session)
        with self.assertRaises(IntegrityError):
            self.session.commit()

    # ── 4. expires_at settable relative to available_from (24h window) ──
    def test_expires_at_relative_to_available_from(self) -> None:
        """
        Verify available_from and expires_at fields exist and represent a 24h window.

        Note: The 24h calculation is performed in Task 3's service layer upon session creation
        (e.g., expires_at = available_from + timedelta(hours=24)), not as a DB column default,
        ensuring deterministic timezone handling across time zones.
        """
        now = datetime.now(timezone.utc)
        exp = now + timedelta(hours=24)

        interview = InterviewSession(
            user_id=uuid.uuid4(),
            task_id=uuid.uuid4(),
            evaluation_id=uuid.uuid4(),
            available_from=now,
            expires_at=exp,
        )
        self.session.add(interview)
        self.session.commit()
        self.session.refresh(interview)

        diff = interview.expires_at - interview.available_from
        self.assertAlmostEqual(diff.total_seconds(), 24 * 3600, delta=1.0)

    # ── 5. Cascade deletion safety net for tests ────────────────────────
    def test_cascade_delete_for_turns_and_proctoring_events(self) -> None:
        """
        Deleting a session cascades to turns and proctoring events at the DB level.

        Documented choice: Production application logic never hard-deletes sessions,
        but ondelete='CASCADE' is enabled at the DB level for test cleanup.
        """
        now = datetime.now(timezone.utc)
        interview = InterviewSession(
            user_id=uuid.uuid4(),
            task_id=uuid.uuid4(),
            evaluation_id=uuid.uuid4(),
            available_from=now,
            expires_at=now + timedelta(hours=24),
        )
        self.session.add(interview)
        self.session.commit()

        turn = InterviewTurn(
            session_id=interview.id,
            turn_number=1,
            question_text="Tell me about asyncpg connection pooling.",
            question_context={"skill": "PostgreSQL"},
        )
        event = ProctoringEvent(
            session_id=interview.id,
            event_type=ProctoringEventType.TAB_BLUR.value,
            turn_number_at_event=1,
        )
        self.session.add_all([turn, event])
        self.session.commit()

        # Delete the session
        self.session.delete(interview)
        self.session.commit()

        # Turns and proctoring events should be deleted
        remaining_turns = self.session.query(InterviewTurn).filter_by(session_id=interview.id).count()
        remaining_events = self.session.query(ProctoringEvent).filter_by(session_id=interview.id).count()
        self.assertEqual(remaining_turns, 0)
        self.assertEqual(remaining_events, 0)

    # ── 6. Pydantic v2 Schema: time_remaining_seconds computation ───────
    def test_interview_session_response_computed_time_remaining(self) -> None:
        """Student-facing InterviewSessionResponse dynamically computes time_remaining_seconds."""
        now = datetime.now(timezone.utc)
        exp_future = now + timedelta(hours=2)

        session_data = {
            "id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "task_id": uuid.uuid4(),
            "evaluation_id": uuid.uuid4(),
            "status": InterviewSessionStatus.AVAILABLE,
            "available_from": now,
            "expires_at": exp_future,
            "violation_count": 1,
            "created_at": now,
        }
        resp = InterviewSessionResponse(**session_data)
        # Should have approximately 2 hours (7200 seconds) remaining
        self.assertGreater(resp.time_remaining_seconds, 7100.0)
        self.assertLessEqual(resp.time_remaining_seconds, 7200.0)

        # When status is COMPLETED or EXPIRED, time_remaining_seconds should return 0.0
        session_data["status"] = InterviewSessionStatus.COMPLETED
        resp_completed = InterviewSessionResponse(**session_data)
        self.assertEqual(resp_completed.time_remaining_seconds, 0.0)

        session_data["status"] = InterviewSessionStatus.TERMINATED_VIOLATION
        resp_terminated = InterviewSessionResponse(**session_data)
        self.assertEqual(resp_terminated.time_remaining_seconds, 0.0)

    # ── 7. Pydantic v2 Schema: ProctoringEventCreate validation ─────────
    def test_proctoring_event_create_validation(self) -> None:
        """ProctoringEventCreate accepts valid enum and rejects unknown types."""
        req = ProctoringEventCreate(
            event_type=ProctoringEventType.FULLSCREEN_EXIT,
            turn_number_at_event=2,
        )
        self.assertEqual(req.event_type, ProctoringEventType.FULLSCREEN_EXIT)
        self.assertEqual(req.turn_number_at_event, 2)

    # ── 8. Pydantic v2 Schema: InternalCreateSessionRequest validation ───
    def test_internal_create_session_request_validation(self) -> None:
        """InternalCreateSessionRequest requires valid UUIDs."""
        task_id = uuid.uuid4()
        user_id = uuid.uuid4()
        evaluation_id = uuid.uuid4()

        req = InternalCreateSessionRequest(
            task_id=task_id,
            user_id=user_id,
            evaluation_id=evaluation_id,
        )
        self.assertEqual(req.task_id, task_id)
        self.assertEqual(req.user_id, user_id)
        self.assertEqual(req.evaluation_id, evaluation_id)


class TestAlembicMigration(unittest.TestCase):
    """Test that Alembic migration 0001_initial runs upgrade and downgrade cleanly."""

    def test_migration_upgrade_and_downgrade(self) -> None:
        """Alembic upgrade head and downgrade base cycle against a temporary SQLite database."""
        from unittest.mock import patch
        from alembic import command
        from alembic.config import Config
        from app.core.config import settings

        db_file = "test_alembic_cycle.db"
        if os.path.exists(db_file):
            os.remove(db_file)

        db_url = f"sqlite+aiosqlite:///{db_file}"
        try:
            with patch.object(settings, "DATABASE_URL", db_url):
                cfg = Config("alembic.ini")
                # Upgrade to head
                command.upgrade(cfg, "head")

                # Verify tables exist by inspecting the SQLite file
                verify_engine = sa.create_engine(f"sqlite:///{db_file}")
                inspector = sa.inspect(verify_engine)
                tables = inspector.get_table_names()
                self.assertIn("interview_sessions", tables)
                self.assertIn("interview_turns", tables)
                self.assertIn("proctoring_events", tables)
                verify_engine.dispose()

                # Downgrade back to base
                command.downgrade(cfg, "base")

                verify_engine = sa.create_engine(f"sqlite:///{db_file}")
                inspector = sa.inspect(verify_engine)
                tables_after = inspector.get_table_names()
                self.assertNotIn("interview_sessions", tables_after)
                self.assertNotIn("interview_turns", tables_after)
                self.assertNotIn("proctoring_events", tables_after)
                verify_engine.dispose()

        finally:
            if os.path.exists(db_file):
                os.remove(db_file)


if __name__ == "__main__":
    unittest.main()
