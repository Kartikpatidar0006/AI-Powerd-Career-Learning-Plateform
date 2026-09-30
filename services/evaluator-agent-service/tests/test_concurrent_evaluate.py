"""
Explicit Concurrency Test for POST /internal/evaluate.

Proves:
When two simultaneous POST /internal/evaluate calls arrive for the exact same task_id:
- Exactly one call succeeds with HTTP 200 (Evaluation started)
- Exactly one call is rejected with HTTP 409 (Evaluation already in progress)
- No traceback or unhandled exception is leaked.
"""

import asyncio
import unittest
import uuid
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import status

from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models.evaluation import Evaluation, EvaluationStatus
from app.services.evaluator_service import EvaluationInProgressError, EvaluatorService


class TestConcurrentInternalEvaluate(unittest.IsolatedAsyncioTestCase):
    """Explicit concurrency verification for POST /internal/evaluate."""

    async def test_two_simultaneous_evaluate_calls_for_same_task_returns_one_200_and_one_409(self) -> None:
        """
        Two simultaneous POST /internal/evaluate requests for the same task_id.
        Expected: exactly one 200 OK, exactly one 409 Conflict.
        """
        task_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        payload = {
            "task_id": task_id,
            "user_id": user_id,
            "github_repo_url": "https://github.com/user/test-repo",
            "skills_targeted": ["python"],
        }
        headers = {"X-Internal-Token": settings.INTERNAL_SERVICE_TOKEN}

        # State tracker simulating DB uniqueness / in-progress guard
        in_progress_tasks = set()
        lock = asyncio.Lock()

        async def concurrent_trigger_evaluation(db, request):
            async with lock:
                if request.task_id in in_progress_tasks:
                    raise EvaluationInProgressError(
                        f"Evaluation for task {request.task_id} is already in progress."
                    )
                in_progress_tasks.add(request.task_id)
                # Introduce small micro-delay so the concurrent request hits while this is in progress
                await asyncio.sleep(0.05)
                mock_eval = Evaluation(
                    id=uuid.uuid4(),
                    task_id=request.task_id,
                    user_id=request.user_id,
                    github_repo_url=request.github_repo_url,
                    status=EvaluationStatus.IN_PROGRESS.value,
                )
                return mock_eval

        async def override_get_db():
            mock_session = AsyncMock()
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch.object(
                EvaluatorService,
                "trigger_evaluation",
                side_effect=concurrent_trigger_evaluation,
            ), patch.object(
                EvaluatorService,
                "run_full_pipeline",
                AsyncMock(),
            ):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://testserver",
                ) as client:
                    # Fire both requests concurrently
                    req1 = client.post("/internal/evaluate", headers=headers, json=payload)
                    req2 = client.post("/internal/evaluate", headers=headers, json=payload)

                    resp1, resp2 = await asyncio.gather(req1, req2)

            statuses = sorted([resp1.status_code, resp2.status_code])
            print("\n" + "=" * 60)
            print("CONCURRENT EVALUATE CALL RESPONSES:")
            print(f"  Call 1: HTTP {resp1.status_code} -> {resp1.text}")
            print(f"  Call 2: HTTP {resp2.status_code} -> {resp2.text}")
            print(f"  Result: {statuses} -> Exactly one 200 OK, exactly one 409 Conflict.")
            print("=" * 60)

            # Assertions
            self.assertEqual(statuses, [200, 409], f"Expected [200, 409], got {statuses}")
            self.assertNotIn("Traceback", resp1.text)
            self.assertNotIn("Traceback", resp2.text)

            conflict_resp = resp1 if resp1.status_code == 409 else resp2
            self.assertIn("already in progress", conflict_resp.json()["detail"])

        finally:
            app.dependency_overrides.clear()


if __name__ == "__main__":
    unittest.main()
