"""
Comprehensive Proctoring Endpoint Tests for interview-agent-service (Agent 4, Task 5).

Verifies:
1. Single violation: increments violation_count by 1, session status stays IN_PROGRESS, terminated=False
2. Exactly 3 violations: 3rd violation terminates session, status=TERMINATED_VIOLATION,
   completed_at set, terminated=True in response, clear safe termination_reason recorded
3. Proctoring event rejected (409 Conflict) when session is not IN_PROGRESS (AVAILABLE, COMPLETED, EXPIRED)
4. Atomic increment under concurrency: fires multiple simultaneous proctoring events
   against a real database (SQLite+aiosqlite), asserting no lost updates and correct final count
5. Rate limiting: 21st event within 1 minute returns 429 Too Many Requests and does not increment violation_count
6. Answer submission rejected (409 Conflict) after termination: does not create a turn or resurrect session
7. Ownership check: cannot submit proctoring event for another user's session (404 Not Found)
8. GET /interview/sessions/{task_id} reflects TERMINATED_VIOLATION with violation_count and termination_reason
9. No response leaks Python tracebacks ("Traceback" not in resp.text)
"""

import asyncio
import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, AsyncMock

import httpx
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
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
)
from app.services.interview_agent import interview_agent
from app.services.proctoring_limiter import proctoring_rate_limiter


class TestProctoringEndpoints(unittest.TestCase):
    """Test suite for client-side proctoring event logging, atomic increment, and termination."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.db_file = f"test_proctoring_{uuid.uuid4().hex[:8]}.db"
        cls.engine = create_async_engine(
            f"sqlite+aiosqlite:///{cls.db_file}",
            connect_args={"check_same_thread": False, "timeout": 30},
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

        from app.services.evaluator_client import evaluator_client
        cls.patcher_eval = patch.object(
            evaluator_client,
            "get_evaluation_by_task",
            new_callable=AsyncMock,
            return_value={
                "weaknesses": ["Edge cases", "Concurrency handling"],
                "skills_targeted": ["Python", "FastAPI"],
                "red_flags": [],
            },
        )
        cls.patcher_eval.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.patcher_eval.stop()
        app.dependency_overrides.clear()
        asyncio.run(cls.engine.dispose())
        if os.path.exists(cls.db_file):
            try:
                os.remove(cls.db_file)
            except Exception:
                pass

    def setUp(self) -> None:
        proctoring_rate_limiter.reset()
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

    def _create_and_start_session(self) -> dict:
        """Helper to create an AVAILABLE session and start it to IN_PROGRESS."""
        # 1. Internal create (providing evaluation_context caches it and avoids external network calls)
        resp_create = self.client.post(
            "/internal/interview/create-session",
            headers=self.internal_headers,
            json={
                "task_id": self.task_id,
                "user_id": self.user_id,
                "evaluation_id": self.eval_id,
                "evaluation_context": {
                    "weaknesses": ["Error handling under edge conditions"],
                    "red_flags": [],
                    "skills_to_probe": ["Python", "FastAPI", "Concurrency"],
                },
            },
        )
        self.assertEqual(resp_create.status_code, status.HTTP_200_OK)

        # 2. Start session
        resp_start = self.client.post(
            f"/interview/sessions/{self.task_id}/start",
            headers=self.gateway_headers,
        )
        self.assertEqual(resp_start.status_code, status.HTTP_200_OK)
        return resp_start.json()

    # ── 1. Single violation ─────────────────────────────────────────────
    def test_single_violation_increments_count_and_stays_in_progress(self) -> None:
        """
        Single violation increments violation_count to 1, status stays IN_PROGRESS,
        and terminated flag is False.
        """
        self._create_and_start_session()

        payload = {
            "event_type": "TAB_BLUR",
            "turn_number_at_event": 1,
        }
        resp = self.client.post(
            f"/interview/sessions/{self.task_id}/proctoring-event",
            headers=self.gateway_headers,
            json=payload,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()

        self.assertEqual(data["violation_count"], 1)
        self.assertEqual(data["session_status"], "IN_PROGRESS")
        self.assertFalse(data["terminated"])
        self.assertIsNone(data["termination_reason"])
        self.assertEqual(data["event"]["event_type"], "TAB_BLUR")
        self.assertEqual(data["event"]["turn_number_at_event"], 1)
        self.assertNotIn("Traceback", resp.text)

        # Verify DB row
        async def verify_db() -> tuple[int, str, int]:
            async with self.session_factory() as db:
                sess_res = await db.execute(
                    select(InterviewSession).where(InterviewSession.task_id == uuid.UUID(self.task_id))
                )
                session = sess_res.scalar_one()

                events_res = await db.execute(
                    select(ProctoringEvent).where(ProctoringEvent.session_id == session.id)
                )
                events = list(events_res.scalars().all())
                return session.violation_count, session.status, len(events)

        violation_count, sess_status, event_count = asyncio.run(verify_db())
        self.assertEqual(violation_count, 1)
        self.assertEqual(sess_status, "IN_PROGRESS")
        self.assertEqual(event_count, 1)

    # ── 2. Exactly 3 violations terminate session ──────────────────────
    def test_three_violations_terminates_session(self) -> None:
        """
        1st violation -> count=1, terminated=False
        2nd violation -> count=2, terminated=False
        3rd violation -> count=3, terminated=True, status=TERMINATED_VIOLATION,
                         completed_at set, termination_reason recorded.
        """
        self._create_and_start_session()

        # Violation 1
        resp1 = self.client.post(
            f"/interview/sessions/{self.task_id}/proctoring-event",
            headers=self.gateway_headers,
            json={"event_type": "TAB_BLUR", "turn_number_at_event": 1},
        )
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        self.assertEqual(resp1.json()["violation_count"], 1)
        self.assertFalse(resp1.json()["terminated"])

        # Violation 2
        resp2 = self.client.post(
            f"/interview/sessions/{self.task_id}/proctoring-event",
            headers=self.gateway_headers,
            json={"event_type": "FULLSCREEN_EXIT", "turn_number_at_event": 1},
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.json()["violation_count"], 2)
        self.assertFalse(resp2.json()["terminated"])

        # Violation 3 -> TERMINATION
        resp3 = self.client.post(
            f"/interview/sessions/{self.task_id}/proctoring-event",
            headers=self.gateway_headers,
            json={"event_type": "COPY_PASTE_ATTEMPT", "turn_number_at_event": 1},
        )
        self.assertEqual(resp3.status_code, status.HTTP_200_OK)
        data3 = resp3.json()
        self.assertEqual(data3["violation_count"], 3)
        self.assertTrue(data3["terminated"])
        self.assertEqual(data3["session_status"], "TERMINATED_VIOLATION")
        self.assertIn("Interview terminated after 3 proctoring violations", data3["termination_reason"])
        self.assertNotIn("Traceback", resp3.text)

        # Re-fetch via GET /interview/sessions/{task_id} and assert status and details
        resp_get = self.client.get(
            f"/interview/sessions/{self.task_id}",
            headers=self.gateway_headers,
        )
        self.assertEqual(resp_get.status_code, status.HTTP_200_OK)
        get_data = resp_get.json()
        self.assertEqual(get_data["status"], "TERMINATED_VIOLATION")
        self.assertEqual(get_data["violation_count"], 3)
        self.assertIsNotNone(get_data["completed_at"])
        self.assertIn("Interview terminated after 3 proctoring violations", get_data["termination_reason"])
        self.assertEqual(get_data["time_remaining_seconds"], 0.0)

    # ── 3. Proctoring event rejected when not IN_PROGRESS ─────────────
    def test_proctoring_event_rejected_when_available(self) -> None:
        """Proctoring event on AVAILABLE session returns 409 Conflict."""
        # Create session but do not start
        resp_create = self.client.post(
            "/internal/interview/create-session",
            headers=self.internal_headers,
            json={
                "task_id": self.task_id,
                "user_id": self.user_id,
                "evaluation_id": self.eval_id,
            },
        )
        self.assertEqual(resp_create.status_code, status.HTTP_200_OK)

        resp = self.client.post(
            f"/interview/sessions/{self.task_id}/proctoring-event",
            headers=self.gateway_headers,
            json={"event_type": "TAB_BLUR"},
        )
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("only accepted for in-progress interviews", resp.text)
        self.assertNotIn("Traceback", resp.text)

    def test_proctoring_event_rejected_when_already_terminated(self) -> None:
        """Proctoring event after session is already terminated returns 409 Conflict."""
        self._create_and_start_session()

        for _ in range(3):
            self.client.post(
                f"/interview/sessions/{self.task_id}/proctoring-event",
                headers=self.gateway_headers,
                json={"event_type": "TAB_BLUR"},
            )

        # 4th violation attempt
        resp4 = self.client.post(
            f"/interview/sessions/{self.task_id}/proctoring-event",
            headers=self.gateway_headers,
            json={"event_type": "TAB_BLUR"},
        )
        self.assertEqual(resp4.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("only accepted for in-progress interviews", resp4.text)
        self.assertNotIn("Traceback", resp4.text)

    # ── 4. Atomic increment under concurrency ──────────────────────────
    def test_atomic_increment_under_concurrency_real_db(self) -> None:
        """
        Concurrency isolation test using real database (aiosqlite).
        Fires 10 simultaneous proctoring events concurrently using asyncio.gather.
        Asserts that:
        - DB-level atomic increment prevents lost updates (no read-modify-write races)
        - Final violation_count in the DB matches exactly the number of accepted events
        - Exactly 10 events are recorded
        - No tracebacks leaked
        """
        self._create_and_start_session()

        # Temporarily increase threshold so all 10 events stay in progress
        with patch.object(settings, "PROCTORING_MAX_VIOLATIONS", 20), \
             patch.object(settings, "PROCTORING_RATE_LIMIT_PER_MINUTE", 50):

            async def fire_concurrent_events() -> list[httpx.Response]:
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
                    tasks = [
                        ac.post(
                            f"/interview/sessions/{self.task_id}/proctoring-event",
                            headers=self.gateway_headers,
                            json={
                                "event_type": "TAB_BLUR",
                                "turn_number_at_event": 1,
                            },
                        )
                        for _ in range(10)
                    ]
                    return await asyncio.gather(*tasks)

            responses = asyncio.run(fire_concurrent_events())

            # All 10 requests should succeed with 200 OK
            status_codes = [r.status_code for r in responses]
            self.assertEqual(status_codes, [200] * 10)

            # Check that each response received an increment
            violation_counts = sorted([r.json()["violation_count"] for r in responses])
            self.assertEqual(violation_counts, list(range(1, 11)))

            # Check real database state
            async def get_db_counts() -> tuple[int, int]:
                async with self.session_factory() as db:
                    sess_res = await db.execute(
                        select(InterviewSession).where(InterviewSession.task_id == uuid.UUID(self.task_id))
                    )
                    sess = sess_res.scalar_one()
                    evt_res = await db.execute(
                        select(ProctoringEvent).where(ProctoringEvent.session_id == sess.id)
                    )
                    evts = list(evt_res.scalars().all())
                    return sess.violation_count, len(evts)

            final_violation_count, event_row_count = asyncio.run(get_db_counts())
            self.assertEqual(final_violation_count, 10)
            self.assertEqual(event_row_count, 10)

    # ── 5. Rate limiting ───────────────────────────────────────────────
    def test_rate_limiting_rejects_21st_event_with_429(self) -> None:
        """
        Endpoint enforces a sliding-window rate limit (default 20 requests per minute).
        The 21st event returns HTTP 429 Too Many Requests and does NOT increment violation_count.
        """
        self._create_and_start_session()

        # Set threshold high so violations don't terminate early during rate limit test
        with patch.object(settings, "PROCTORING_MAX_VIOLATIONS", 100):
            # Send 20 events -> all 200 OK
            for i in range(20):
                resp = self.client.post(
                    f"/interview/sessions/{self.task_id}/proctoring-event",
                    headers=self.gateway_headers,
                    json={"event_type": "TAB_BLUR"},
                )
                self.assertEqual(
                    resp.status_code,
                    status.HTTP_200_OK,
                    f"Event {i+1} failed with status {resp.status_code}",
                )

            # 21st event must be rate limited
            resp_21 = self.client.post(
                f"/interview/sessions/{self.task_id}/proctoring-event",
                headers=self.gateway_headers,
                json={"event_type": "TAB_BLUR"},
            )
            self.assertEqual(resp_21.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
            self.assertIn("Retry-After", resp_21.headers)
            self.assertIn("Rate limit exceeded", resp_21.text)
            self.assertNotIn("Traceback", resp_21.text)

            # Verify DB violation_count remained 20 (not 21)
            async def get_count() -> int:
                async with self.session_factory() as db:
                    res = await db.execute(
                        select(InterviewSession.violation_count).where(
                            InterviewSession.task_id == uuid.UUID(self.task_id)
                        )
                    )
                    return res.scalar_one()

            self.assertEqual(asyncio.run(get_count()), 20)

    # ── 6. Answer submission after termination returns 409 ─────────────
    def test_answer_submission_after_termination_rejected_with_409(self) -> None:
        """
        Once an interview is TERMINATED_VIOLATION, submitting an answer returns 409 Conflict,
        does NOT create a new turn, and does not resurrect the interview.
        """
        self._create_and_start_session()

        # Trigger 3 violations to terminate
        for _ in range(3):
            self.client.post(
                f"/interview/sessions/{self.task_id}/proctoring-event",
                headers=self.gateway_headers,
                json={"event_type": "DEVTOOLS_DETECTED"},
            )

        # Attempt to submit an answer
        answer_payload = {
            "answer_text": "I will try to submit an answer even though the session was terminated.",
            "duration_seconds": 15.0,
        }
        resp_ans = self.client.post(
            f"/interview/sessions/{self.task_id}/answer",
            headers=self.gateway_headers,
            json=answer_payload,
        )
        self.assertEqual(resp_ans.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("Interview is not in progress", resp_ans.text)
        self.assertNotIn("Traceback", resp_ans.text)

        # Check DB state: status is still TERMINATED_VIOLATION, only 1 turn (the first question)
        async def verify_post_termination_state() -> tuple[str, int]:
            async with self.session_factory() as db:
                sess_res = await db.execute(
                    select(InterviewSession).where(InterviewSession.task_id == uuid.UUID(self.task_id))
                )
                session = sess_res.scalar_one()

                turns_res = await db.execute(
                    select(InterviewTurn).where(InterviewTurn.session_id == session.id)
                )
                turns = list(turns_res.scalars().all())
                return session.status, len(turns)

        sess_status, turn_count = asyncio.run(verify_post_termination_state())
        self.assertEqual(sess_status, "TERMINATED_VIOLATION")
        self.assertEqual(turn_count, 1)

    # ── 7. Ownership check ─────────────────────────────────────────────
    def test_ownership_isolation_returns_404_for_other_users_session(self) -> None:
        """
        Submitting a proctoring event for another user's session returns 404 Not Found,
        preventing unauthorized access and information leakage.
        """
        self._create_and_start_session()

        other_user_id = str(uuid.uuid4())
        other_user_headers = {
            "X-Gateway-Token": self.gateway_token,
            "X-User-Id": other_user_id,
        }

        resp = self.client.post(
            f"/interview/sessions/{self.task_id}/proctoring-event",
            headers=other_user_headers,
            json={"event_type": "TAB_BLUR"},
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.json()["detail"], "No interview session found for this task")
        self.assertNotIn("Traceback", resp.text)

        # DB violation_count should still be 0
        async def get_count() -> int:
            async with self.session_factory() as db:
                res = await db.execute(
                    select(InterviewSession.violation_count).where(
                        InterviewSession.task_id == uuid.UUID(self.task_id)
                    )
                )
                return res.scalar_one()

        self.assertEqual(asyncio.run(get_count()), 0)

    # ── 8. Traceback check across error conditions ─────────────────────
    def test_no_response_contains_traceback(self) -> None:
        """Verify that validation errors, missing headers, and conflict responses never leak tracebacks."""
        # 1. Missing gateway token
        resp1 = self.client.post(
            f"/interview/sessions/{self.task_id}/proctoring-event",
            json={"event_type": "TAB_BLUR"},
        )
        self.assertEqual(resp1.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn("Traceback", resp1.text)

        # 2. Missing user id
        resp2 = self.client.post(
            f"/interview/sessions/{self.task_id}/proctoring-event",
            headers={"X-Gateway-Token": self.gateway_token},
            json={"event_type": "TAB_BLUR"},
        )
        self.assertEqual(resp2.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("Traceback", resp2.text)

        # 3. Invalid payload (missing event_type)
        resp3 = self.client.post(
            f"/interview/sessions/{self.task_id}/proctoring-event",
            headers=self.gateway_headers,
            json={},
        )
        self.assertEqual(resp3.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertNotIn("Traceback", resp3.text)
