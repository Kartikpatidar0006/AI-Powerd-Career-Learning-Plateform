"""
Session lifecycle API endpoint tests for interview-agent-service (Agent 4).

Verifies:
1. POST /internal/interview/create-session:
   - Requires valid X-Internal-Token (403 on missing/invalid)
   - Idempotent: duplicate calls with same task_id return the same session id and do not duplicate rows
   - Concurrency race condition: handles IntegrityError gracefully and returns existing session without 500
2. GET /interview/sessions/{task_id}:
   - Requires valid X-Gateway-Token and X-User-Id
   - 404 for nonexistent session
   - 404 for another user's session (ownership isolation — never leaks existence)
   - Lazy expiry: transitions AVAILABLE/IN_PROGRESS to EXPIRED when expires_at is past
3. POST /interview/sessions/{task_id}/start:
   - Success path: AVAILABLE -> IN_PROGRESS, records started_at
   - 409 Conflict when already IN_PROGRESS ("Interview already in progress, use resume")
   - 409 Conflict when EXPIRED ("This interview window has expired")
   - 409 Conflict when COMPLETED or TERMINATED_VIOLATION ("This interview has already concluded")
   - Lazy expiry: re-checked at start time, rejects expired sessions with 409
4. GET /interview/sessions/{task_id}/resume:
   - 409 Conflict when session is not IN_PROGRESS
   - Returns session and full ordered list of turns when turns exist
5. Security:
   - No response contains "Traceback"
"""

import asyncio
import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.interview import (
    InterviewSession,
    InterviewSessionStatus,
    InterviewTurn,
)
from app.schemas.interview import InternalCreateSessionRequest


class TestSessionLifecycleEndpoints(unittest.TestCase):
    """Test suite for session creation, start, resume, and lazy expiry."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.db_file = f"test_sessions_{uuid.uuid4().hex[:8]}.db"
        cls.engine = create_async_engine(
            f"sqlite+aiosqlite:///{cls.db_file}",
            connect_args={"check_same_thread": False},
        )
        cls.session_factory = async_sessionmaker(
            cls.engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

        async def init_tables() -> None:
            async with cls.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

        asyncio.run(init_tables())

        async def override_get_db():
            async with cls.session_factory() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise
                finally:
                    await session.close()

        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app, raise_server_exceptions=False)
        cls.gateway_token = settings.GATEWAY_SERVICE_TOKEN
        cls.internal_token = settings.INTERNAL_SERVICE_TOKEN

    @classmethod
    def tearDownClass(cls) -> None:
        app.dependency_overrides.clear()
        asyncio.run(cls.engine.dispose())
        if os.path.exists(cls.db_file):
            try:
                os.remove(cls.db_file)
            except Exception:
                pass

    def setUp(self) -> None:
        self.user_id = str(uuid.uuid4())
        self.task_id = str(uuid.uuid4())
        self.eval_id = str(uuid.uuid4())
        self.gateway_headers = {
            "X-Gateway-Token": self.gateway_token,
            "X-User-Id": self.user_id,
        }
        self.internal_headers = {
            "X-Internal-Token": self.internal_token,
        }

    # ── 1. POST /internal/interview/create-session Tests ────────────────
    def test_create_session_internal_token_required(self) -> None:
        """POST /internal/interview/create-session requires X-Internal-Token."""
        resp = self.client.post(
            "/internal/interview/create-session",
            json={"task_id": self.task_id, "user_id": self.user_id, "evaluation_id": self.eval_id},
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn("Traceback", resp.text)

    def test_create_session_invalid_internal_token_rejected(self) -> None:
        """POST /internal/interview/create-session with wrong token returns 403."""
        resp = self.client.post(
            "/internal/interview/create-session",
            headers={"X-Internal-Token": "wrong-secret-token"},
            json={"task_id": self.task_id, "user_id": self.user_id, "evaluation_id": self.eval_id},
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn("Traceback", resp.text)

    def test_create_session_success_and_idempotency(self) -> None:
        """
        Calling create-session twice with the same task_id returns the same session id,
        and only a single row exists in the database.
        """
        payload = {
            "task_id": self.task_id,
            "user_id": self.user_id,
            "evaluation_id": self.eval_id,
        }

        # First call: creates session
        resp1 = self.client.post(
            "/internal/interview/create-session",
            headers=self.internal_headers,
            json=payload,
        )
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        data1 = resp1.json()
        self.assertEqual(data1["task_id"], self.task_id)
        self.assertEqual(data1["user_id"], self.user_id)
        self.assertEqual(data1["status"], "AVAILABLE")
        self.assertAlmostEqual(data1["time_remaining_seconds"], 24 * 3600, delta=10.0)

        # Second call: idempotent return of existing session
        resp2 = self.client.post(
            "/internal/interview/create-session",
            headers=self.internal_headers,
            json=payload,
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        data2 = resp2.json()
        self.assertEqual(data1["id"], data2["id"])

        # Verify only 1 row exists in DB
        async def count_rows() -> int:
            async with self.session_factory() as session:
                res = await session.execute(
                    select(InterviewSession).where(InterviewSession.task_id == uuid.UUID(self.task_id))
                )
                return len(res.scalars().all())

        self.assertEqual(asyncio.run(count_rows()), 1)

    def test_create_session_handles_race_condition(self) -> None:
        """
        Simulate a concurrent race condition where db.commit() raises IntegrityError.
        Confirm it rolls back, fetches, and returns the existing session instead of a 500.
        """
        task_id = str(uuid.uuid4())
        payload = {
            "task_id": task_id,
            "user_id": self.user_id,
            "evaluation_id": self.eval_id,
        }

        # First create the existing session
        resp1 = self.client.post(
            "/internal/interview/create-session",
            headers=self.internal_headers,
            json=payload,
        )
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        existing_id = resp1.json()["id"]

        # Call service create_or_get_session with commit patched to raise IntegrityError
        from app.services.session_service import session_service

        async def run_race_test() -> str:
            async with self.session_factory() as db:
                orig_commit = db.commit
                first_attempt = True

                async def mock_commit():
                    nonlocal first_attempt
                    if first_attempt:
                        first_attempt = False
                        raise IntegrityError("UNIQUE constraint failed", orig=None, params=None)
                    await orig_commit()

                with patch.object(db, "commit", side_effect=mock_commit):
                    session = await session_service.create_or_get_session(
                        db=db,
                        request=InternalCreateSessionRequest(
                            task_id=uuid.UUID(task_id),
                            user_id=uuid.UUID(self.user_id),
                            evaluation_id=uuid.UUID(self.eval_id),
                        ),
                    )
                    return str(session.id)

        returned_id = asyncio.run(run_race_test())
        self.assertEqual(returned_id, existing_id)

    # ── 2. GET /interview/sessions/{task_id} Tests ─────────────────────
    def test_get_session_missing_gateway_token_forbidden(self) -> None:
        """GET /interview/sessions/{task_id} without gateway token returns 403."""
        resp = self.client.get(
            f"/interview/sessions/{self.task_id}",
            headers={"X-User-Id": self.user_id},
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn("Traceback", resp.text)

    def test_get_session_missing_user_id_unauthorized(self) -> None:
        """GET /interview/sessions/{task_id} without X-User-Id returns 401."""
        resp = self.client.get(
            f"/interview/sessions/{self.task_id}",
            headers={"X-Gateway-Token": self.gateway_token},
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("Traceback", resp.text)

    def test_get_session_nonexistent_returns_404(self) -> None:
        """GET /interview/sessions/{task_id} for nonexistent task returns 404."""
        resp = self.client.get(
            f"/interview/sessions/{uuid.uuid4()}",
            headers=self.gateway_headers,
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("No interview session found", resp.json().get("detail", ""))
        self.assertNotIn("Traceback", resp.text)

    def test_get_session_ownership_isolation_returns_404(self) -> None:
        """
        GET /interview/sessions/{task_id} for a session owned by another user returns 404,
        never leaking the existence of the other user's session.
        """
        # Create session for User A
        task_id = str(uuid.uuid4())
        self.client.post(
            "/internal/interview/create-session",
            headers=self.internal_headers,
            json={"task_id": task_id, "user_id": self.user_id, "evaluation_id": self.eval_id},
        )

        # User B attempts to access User A's session
        other_user_id = str(uuid.uuid4())
        resp = self.client.get(
            f"/interview/sessions/{task_id}",
            headers={"X-Gateway-Token": self.gateway_token, "X-User-Id": other_user_id},
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("No interview session found", resp.json().get("detail", ""))

    def test_get_session_lazy_expiry_transition(self) -> None:
        """
        If status is AVAILABLE or IN_PROGRESS and expires_at is past,
        GET /interview/sessions/{task_id} transitions the record to EXPIRED in DB.
        """
        task_id = uuid.uuid4()
        user_uuid = uuid.UUID(self.user_id)
        past_time = datetime.now(timezone.utc) - timedelta(hours=2)

        async def insert_expired_session() -> None:
            async with self.session_factory() as session:
                sess = InterviewSession(
                    user_id=user_uuid,
                    task_id=task_id,
                    evaluation_id=uuid.uuid4(),
                    status="AVAILABLE",
                    available_from=past_time - timedelta(hours=24),
                    expires_at=past_time,
                )
                session.add(sess)
                await session.commit()

        asyncio.run(insert_expired_session())

        # Read session via GET endpoint
        resp = self.client.get(
            f"/interview/sessions/{task_id}",
            headers=self.gateway_headers,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(data["status"], "EXPIRED")
        self.assertEqual(data["time_remaining_seconds"], 0.0)

        # Confirm the DB record itself was updated to EXPIRED
        async def check_db_status() -> str:
            async with self.session_factory() as session:
                res = await session.execute(
                    select(InterviewSession).where(InterviewSession.task_id == task_id)
                )
                return res.scalar_one().status

        self.assertEqual(asyncio.run(check_db_status()), "EXPIRED")

    # ── 3. POST /interview/sessions/{task_id}/start Tests ───────────────
    def test_start_session_success(self) -> None:
        """Starting an AVAILABLE session sets status=IN_PROGRESS and started_at=now."""
        task_id = str(uuid.uuid4())
        self.client.post(
            "/internal/interview/create-session",
            headers=self.internal_headers,
            json={"task_id": task_id, "user_id": self.user_id, "evaluation_id": self.eval_id},
        )

        resp = self.client.post(
            f"/interview/sessions/{task_id}/start",
            headers=self.gateway_headers,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(data["status"], "IN_PROGRESS")
        self.assertIsNotNone(data["started_at"])
        self.assertGreater(data["time_remaining_seconds"], 0.0)

    def test_start_session_conflict_when_already_in_progress(self) -> None:
        """Starting an already IN_PROGRESS session returns 409 with specific message."""
        task_id = str(uuid.uuid4())
        self.client.post(
            "/internal/interview/create-session",
            headers=self.internal_headers,
            json={"task_id": task_id, "user_id": self.user_id, "evaluation_id": self.eval_id},
        )
        # First start succeeds
        self.client.post(f"/interview/sessions/{task_id}/start", headers=self.gateway_headers)

        # Second start returns 409
        resp = self.client.post(f"/interview/sessions/{task_id}/start", headers=self.gateway_headers)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("Interview already in progress, use resume", resp.json()["detail"])

    def test_start_session_conflict_when_expired(self) -> None:
        """Starting an EXPIRED session returns 409 'This interview window has expired'."""
        task_id = uuid.uuid4()
        user_uuid = uuid.UUID(self.user_id)
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)

        async def insert_expired() -> None:
            async with self.session_factory() as session:
                sess = InterviewSession(
                    user_id=user_uuid,
                    task_id=task_id,
                    evaluation_id=uuid.uuid4(),
                    status="EXPIRED",
                    available_from=past_time - timedelta(hours=24),
                    expires_at=past_time,
                )
                session.add(sess)
                await session.commit()

        asyncio.run(insert_expired())

        resp = self.client.post(f"/interview/sessions/{task_id}/start", headers=self.gateway_headers)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("This interview window has expired", resp.json()["detail"])

    def test_start_session_lazy_expiry_at_start_time(self) -> None:
        """An AVAILABLE session whose expires_at has passed is lazily expired and rejected at start."""
        task_id = uuid.uuid4()
        user_uuid = uuid.UUID(self.user_id)
        past_time = datetime.now(timezone.utc) - timedelta(minutes=5)

        async def insert_lapsed_available() -> None:
            async with self.session_factory() as session:
                sess = InterviewSession(
                    user_id=user_uuid,
                    task_id=task_id,
                    evaluation_id=uuid.uuid4(),
                    status="AVAILABLE",
                    available_from=past_time - timedelta(hours=24),
                    expires_at=past_time,
                )
                session.add(sess)
                await session.commit()

        asyncio.run(insert_lapsed_available())

        resp = self.client.post(f"/interview/sessions/{task_id}/start", headers=self.gateway_headers)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("This interview window has expired", resp.json()["detail"])

    def test_start_session_conflict_when_completed(self) -> None:
        """Starting a COMPLETED or TERMINATED_VIOLATION session returns 409 'already concluded'."""
        task_id = uuid.uuid4()
        user_uuid = uuid.UUID(self.user_id)
        now = datetime.now(timezone.utc)

        async def insert_completed() -> None:
            async with self.session_factory() as session:
                sess = InterviewSession(
                    user_id=user_uuid,
                    task_id=task_id,
                    evaluation_id=uuid.uuid4(),
                    status="COMPLETED",
                    available_from=now - timedelta(hours=1),
                    expires_at=now + timedelta(hours=23),
                    completed_at=now,
                )
                session.add(sess)
                await session.commit()

        asyncio.run(insert_completed())

        resp = self.client.post(f"/interview/sessions/{task_id}/start", headers=self.gateway_headers)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("This interview has already concluded", resp.json()["detail"])

    # ── 4. GET /interview/sessions/{task_id}/resume Tests ──────────────
    def test_resume_session_conflict_when_not_in_progress(self) -> None:
        """Resuming a session that is AVAILABLE returns 409 directing to GET status."""
        task_id = str(uuid.uuid4())
        self.client.post(
            "/internal/interview/create-session",
            headers=self.internal_headers,
            json={"task_id": task_id, "user_id": self.user_id, "evaluation_id": self.eval_id},
        )

        resp = self.client.get(
            f"/interview/sessions/{task_id}/resume",
            headers=self.gateway_headers,
        )
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("Interview is not in progress", resp.json()["detail"])
        self.assertIn(f"/interview/sessions/{task_id}", resp.json()["detail"])

    def test_resume_session_success_with_turns(self) -> None:
        """
        Resuming an IN_PROGRESS session returns the session details plus
        all existing turns in chronological order.
        """
        task_id = uuid.uuid4()
        user_uuid = uuid.UUID(self.user_id)
        now = datetime.now(timezone.utc)

        async def create_session_with_turns() -> uuid.UUID:
            async with self.session_factory() as session:
                sess = InterviewSession(
                    user_id=user_uuid,
                    task_id=task_id,
                    evaluation_id=uuid.uuid4(),
                    status="IN_PROGRESS",
                    available_from=now - timedelta(minutes=10),
                    expires_at=now + timedelta(hours=23),
                    started_at=now - timedelta(minutes=10),
                )
                session.add(sess)
                await session.flush()

                turn1 = InterviewTurn(
                    session_id=sess.id,
                    turn_number=1,
                    question_text="Explain async/await in FastAPI.",
                    question_context={"skill": "FastAPI"},
                    answer_text="Async/await uses non-blocking coroutines on the event loop.",
                    answer_duration_seconds=32.5,
                )
                turn2 = InterviewTurn(
                    session_id=sess.id,
                    turn_number=2,
                    question_text="How would you handle DB connection pooling with asyncpg?",
                    question_context={"skill": "PostgreSQL"},
                    answer_text=None,  # Candidate is currently on this question
                )
                session.add_all([turn1, turn2])
                await session.commit()
                return sess.id

        session_id = asyncio.run(create_session_with_turns())

        resp = self.client.get(
            f"/interview/sessions/{task_id}/resume",
            headers=self.gateway_headers,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()

        # Both top-level and nested session representations are accessible
        self.assertEqual(data["status"], "IN_PROGRESS")
        self.assertEqual(data["session"]["status"], "IN_PROGRESS")
        self.assertEqual(str(data["session"]["id"]), str(session_id))

        turns = data["turns"]
        self.assertEqual(len(turns), 2)
        self.assertEqual(turns[0]["turn_number"], 1)
        self.assertEqual(turns[0]["question_text"], "Explain async/await in FastAPI.")
        self.assertEqual(turns[0]["answer_duration_seconds"], 32.5)
        self.assertEqual(turns[1]["turn_number"], 2)
        self.assertIsNone(turns[1]["answer_text"])


if __name__ == "__main__":
    unittest.main()
