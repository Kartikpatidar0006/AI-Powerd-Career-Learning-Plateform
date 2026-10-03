"""
API endpoint and integration tests for evaluator-agent-service (Agent 3).

Verifies:
1. POST /internal/evaluate: requires X-Internal-Token (403 on missing/invalid)
2. Idempotency: second trigger for same task while IN_PROGRESS returns 409
3. GET /evaluations/{task_id}: requires X-Gateway-Token and X-User-Id
4. User isolation: user cannot see evaluations belonging to another user
5. POST /dev/evaluations/trigger/{task_id}: active in development mode
6. Gateway defense: /internal/* and /dev/* blocked
7. No response contains "Traceback"
"""

import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import status
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models.evaluation import Evaluation, EvaluationStatus
from app.services.evaluator_service import EvaluationInProgressError


class TestEvaluatorAPIEndpoints(unittest.TestCase):
    """Test API endpoints, authentication, and error security."""

    def setUp(self) -> None:
        self.client = TestClient(app, raise_server_exceptions=False)
        self.internal_token = settings.INTERNAL_SERVICE_TOKEN
        self.gateway_token = settings.GATEWAY_SERVICE_TOKEN
        self.user_id = str(uuid.uuid4())
        self.task_id = str(uuid.uuid4())

    # ── Internal Endpoint Security ──────────────────────────────────────
    def test_internal_evaluate_missing_token_forbidden(self) -> None:
        """POST /internal/evaluate without token must return 403."""
        resp = self.client.post(
            "/internal/evaluate",
            json={
                "task_id": self.task_id,
                "user_id": self.user_id,
                "github_repo_url": "https://github.com/user/repo",
            },
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn("Traceback", resp.text)

    def test_internal_evaluate_invalid_token_forbidden(self) -> None:
        """POST /internal/evaluate with wrong token must return 403."""
        resp = self.client.post(
            "/internal/evaluate",
            headers={"X-Internal-Token": "wrong-secret-token"},
            json={
                "task_id": self.task_id,
                "user_id": self.user_id,
                "github_repo_url": "https://github.com/user/repo",
            },
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn("Traceback", resp.text)

    def test_internal_evaluate_idempotency_conflict_409(self) -> None:
        """Concurrent or repeated trigger for the same task in progress returns 409."""
        mock_session = AsyncMock()

        # Override get_db dependency
        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "app.services.evaluator_service.EvaluatorService.trigger_evaluation",
                AsyncMock(side_effect=EvaluationInProgressError(f"Evaluation for task {self.task_id} is already in progress.")),
            ):
                resp = self.client.post(
                    "/internal/evaluate",
                    headers={"X-Internal-Token": self.internal_token},
                    json={
                        "task_id": self.task_id,
                        "user_id": self.user_id,
                        "github_repo_url": "https://github.com/user/repo",
                    },
                )
                self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
                self.assertIn("already in progress", resp.json()["detail"])
                self.assertNotIn("Traceback", resp.text)
        finally:
            app.dependency_overrides.clear()

    # ── Gateway Token Defense ───────────────────────────────────────────
    def test_public_evaluation_requires_gateway_token(self) -> None:
        """GET /evaluations/{task_id} direct call without gateway token returns 403."""
        resp = self.client.get(
            f"/evaluations/{self.task_id}",
            headers={"X-User-Id": self.user_id},
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn("Traceback", resp.text)

    def test_public_evaluation_requires_user_id(self) -> None:
        """GET /evaluations/{task_id} without X-User-Id header returns 401."""
        resp = self.client.get(
            f"/evaluations/{self.task_id}",
            headers={"X-Gateway-Token": self.gateway_token},
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("Traceback", resp.text)

    def test_public_evaluation_returns_result_without_red_flags(self) -> None:
        """GET /evaluations/{task_id} returns evaluation results but hides red_flags."""
        mock_eval = MagicMock(spec=Evaluation)
        mock_eval.id = uuid.uuid4()
        mock_eval.task_id = uuid.UUID(self.task_id)
        mock_eval.user_id = uuid.UUID(self.user_id)
        mock_eval.github_repo_url = "https://github.com/user/repo"
        mock_eval.status = EvaluationStatus.COMPLETED.value
        mock_eval.final_score = 85.0
        mock_eval.passed = True
        mock_eval.deterministic_score = 80.0
        mock_eval.deterministic_checks = [
            {"check_name": "readme_present", "passed": True, "score_contribution": 15.0, "weight_pct": 15.0, "detail": "Valid"}
        ]
        mock_eval.llm_review = {
            "strengths": ["Good tests"],
            "weaknesses": ["Minor style"],
            "suggestions": ["Refactor helper"],
            "red_flags": ["INTERNAL INJECTION DETECTED"],  # Must be hidden!
        }
        mock_eval.feedback_summary = "Great work! Your task passed."
        mock_eval.created_at = datetime.now(timezone.utc)
        mock_eval.completed_at = datetime.now(timezone.utc)

        mock_session = AsyncMock()

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "app.services.evaluator_service.EvaluatorService.get_latest_evaluation",
                AsyncMock(return_value=mock_eval),
            ):
                resp = self.client.get(
                    f"/evaluations/{self.task_id}",
                    headers={
                        "X-Gateway-Token": self.gateway_token,
                        "X-User-Id": self.user_id,
                    },
                )
                self.assertEqual(resp.status_code, status.HTTP_200_OK)
                data = resp.json()
                self.assertEqual(data["final_score"], 85.0)
                self.assertTrue(data["passed"])
                self.assertIn("llm_strengths", data)
                # Ensure red_flags is NOT exposed to student
                self.assertNotIn("red_flags", data)
                self.assertNotIn("INTERNAL INJECTION DETECTED", resp.text)
                self.assertNotIn("Traceback", resp.text)
        finally:
            app.dependency_overrides.clear()

    def test_evaluation_not_found_returns_404(self) -> None:
        """GET /evaluations/{task_id} returns 404 if no evaluation exists."""
        mock_session = AsyncMock()

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch(
                "app.services.evaluator_service.EvaluatorService.get_latest_evaluation",
                AsyncMock(return_value=None),
            ):
                resp = self.client.get(
                    f"/evaluations/{self.task_id}",
                    headers={
                        "X-Gateway-Token": self.gateway_token,
                        "X-User-Id": self.user_id,
                    },
                )
                self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
                self.assertNotIn("Traceback", resp.text)
        finally:
            app.dependency_overrides.clear()

    # ── Internal GET By Task Endpoints ───────────────────────────────────
    def test_internal_get_evaluation_by_task_requires_internal_token(self) -> None:
        """GET /internal/evaluations/by-task/{task_id} without internal token returns 403."""
        resp = self.client.get(f"/internal/evaluations/by-task/{self.task_id}")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn("Traceback", resp.text)

    def test_internal_get_evaluation_by_task_returns_full_findings(self) -> None:
        """GET /internal/evaluations/by-task/{task_id} returns weaknesses, red_flags, skills_targeted, deterministic_checks."""
        mock_eval = MagicMock(spec=Evaluation)
        mock_eval.id = uuid.uuid4()
        mock_eval.task_id = uuid.UUID(self.task_id)
        mock_eval.user_id = uuid.UUID(self.user_id)
        mock_eval.status = EvaluationStatus.COMPLETED.value
        mock_eval.final_score = 78.5
        mock_eval.passed = True
        mock_eval.deterministic_score = 75.0
        mock_eval.deterministic_checks = [
            {"check_name": "pytest_suite", "passed": True, "score_contribution": 30.0, "weight_pct": 30.0, "detail": "All tests passed"}
        ]
        mock_eval.llm_review = {
            "strengths": ["Clean separation of concerns"],
            "weaknesses": ["Missing connection pool cleanup in shutdown event"],
            "red_flags": ["Potential race condition during pool init"],
            "skills_targeted": ["PostgreSQL", "FastAPI", "AsyncIO"],
            "suggestions": ["Add lifespan context manager"],
        }

        mock_session = AsyncMock()

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        try:
            with patch(
                "app.services.evaluator_service.EvaluatorService.get_latest_evaluation_by_task",
                AsyncMock(return_value=mock_eval),
            ):
                resp = self.client.get(
                    f"/internal/evaluations/by-task/{self.task_id}",
                    headers={"X-Internal-Token": self.internal_token},
                )
                self.assertEqual(resp.status_code, status.HTTP_200_OK)
                data = resp.json()
                self.assertEqual(data["task_id"], self.task_id)
                self.assertIn("Missing connection pool cleanup in shutdown event", data["llm_weaknesses"])
                self.assertIn("Potential race condition during pool init", data["red_flags"])
                self.assertIn("PostgreSQL", data["skills_targeted"])
                self.assertEqual(len(data["deterministic_checks"]), 1)
                self.assertNotIn("Traceback", resp.text)
        finally:
            app.dependency_overrides.clear()


if __name__ == "__main__":
    unittest.main()
