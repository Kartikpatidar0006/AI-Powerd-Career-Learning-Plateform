"""
Tests for API Gateway — Interview Agent Service Routing & Security (Agent 4, Task 6).

Verifies:
1. All /interview/* endpoints require valid JWT authentication (401 without it, 401 on invalid/expired/refresh token)
2. Gateway reverse proxies /interview/sessions/{task_id}* to interview-agent-service (port 8005)
3. Header security & isolation:
   - Injects verified X-User-Id extracted from JWT 'sub' claim
   - Injects verified X-Gateway-Token for defense-in-depth downstream authentication
   - Strips client-supplied spoofed X-User-Id and X-Gateway-Token headers
4. Blocking of /internal/*:
   - Calls to /internal/interview/create-session or /internal/* are blocked at gateway level (404)
5. Service failure handling:
   - Returns 503 Service Unavailable on connection error
   - Returns 504 Gateway Timeout on timeout
6. No error or validation response contains "Traceback"
"""

from datetime import datetime, timedelta, timezone
import unittest
import uuid
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
import httpx
from jose import jwt

from app.config import settings
from app.main import app


class TestGatewayInterviewProxy(unittest.TestCase):
    """Test suite for API Gateway reverse proxying to interview-agent-service."""

    def setUp(self) -> None:
        self.client = TestClient(app)
        app.state.http_client = httpx.AsyncClient()
        self.user_id = str(uuid.uuid4())
        self.task_id = str(uuid.uuid4())

    def _create_token(self, sub: str, token_type: str = "access", expired: bool = False) -> str:
        delta = timedelta(minutes=-5) if expired else timedelta(minutes=30)
        exp = datetime.now(timezone.utc) + delta
        claims = {
            "sub": sub,
            "type": token_type,
            "exp": exp,
        }
        return jwt.encode(claims, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    # ── 1. Authentication Enforcement (401) ────────────────────────────

    def test_get_session_missing_jwt_rejected_401(self) -> None:
        """GET /interview/sessions/{task_id} without JWT returns 401."""
        response = self.client.get(f"/interview/sessions/{self.task_id}")
        self.assertEqual(response.status_code, 401)
        self.assertIn("Authentication credentials were not provided", response.json()["detail"])
        self.assertNotIn("Traceback", response.text)

    def test_start_session_missing_jwt_rejected_401(self) -> None:
        """POST /interview/sessions/{task_id}/start without JWT returns 401."""
        response = self.client.post(f"/interview/sessions/{self.task_id}/start")
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("Traceback", response.text)

    def test_answer_session_missing_jwt_rejected_401(self) -> None:
        """POST /interview/sessions/{task_id}/answer without JWT returns 401."""
        response = self.client.post(
            f"/interview/sessions/{self.task_id}/answer",
            json={"answer_text": "testing", "duration_seconds": 10.0},
        )
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("Traceback", response.text)

    def test_proctoring_event_missing_jwt_rejected_401(self) -> None:
        """POST /interview/sessions/{task_id}/proctoring-event without JWT returns 401."""
        response = self.client.post(
            f"/interview/sessions/{self.task_id}/proctoring-event",
            json={"event_type": "TAB_BLUR"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("Traceback", response.text)

    def test_resume_session_missing_jwt_rejected_401(self) -> None:
        """GET /interview/sessions/{task_id}/resume without JWT returns 401."""
        response = self.client.get(f"/interview/sessions/{self.task_id}/resume")
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("Traceback", response.text)

    def test_expired_token_rejected_401(self) -> None:
        """Expired access token is rejected with 401."""
        token = self._create_token(self.user_id, expired=True)
        response = self.client.get(
            f"/interview/sessions/{self.task_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("Invalid or expired authentication token", response.json()["detail"])
        self.assertNotIn("Traceback", response.text)

    def test_refresh_token_rejected_401(self) -> None:
        """Refresh token cannot be used to access interview endpoints."""
        token = self._create_token(self.user_id, token_type="refresh")
        response = self.client.get(
            f"/interview/sessions/{self.task_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("access token required", response.json()["detail"])
        self.assertNotIn("Traceback", response.text)

    # ── 2. Header Injection & Spoof Stripping ──────────────────────────

    def test_gateway_injects_headers_and_strips_client_spoofed_headers(self) -> None:
        """
        Gateway forwards to interview service with:
        - Verified X-User-Id from JWT
        - Verified X-Gateway-Token from configuration
        - Client-supplied X-User-Id and X-Gateway-Token stripped
        """
        token = self._create_token(self.user_id)
        spoofed_user_id = str(uuid.uuid4())
        spoofed_gateway_token = "attacker-fake-gateway-token"

        mock_backend_response = httpx.Response(
            status_code=200,
            json={
                "id": str(uuid.uuid4()),
                "task_id": self.task_id,
                "user_id": self.user_id,
                "status": "AVAILABLE",
            },
            headers={"content-type": "application/json"},
        )

        with patch.object(self.client.app.state.http_client, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_backend_response

            headers = {
                "Authorization": f"Bearer {token}",
                "X-User-Id": spoofed_user_id,
                "X-Gateway-Token": spoofed_gateway_token,
            }
            resp = self.client.get(f"/interview/sessions/{self.task_id}", headers=headers)

            self.assertEqual(resp.status_code, 200)
            self.assertTrue(mock_req.called)

            called_url = str(mock_req.call_args[1]["url"])
            expected_url = f"{settings.INTERVIEW_SERVICE_URL}/interview/sessions/{self.task_id}"
            self.assertEqual(called_url, expected_url)

            forwarded_headers = mock_req.call_args[1]["headers"]
            # 1. Must inject real verified user_id, NOT spoofed one
            self.assertEqual(forwarded_headers.get("X-User-Id"), self.user_id)
            self.assertNotEqual(forwarded_headers.get("X-User-Id"), spoofed_user_id)

            # 2. Must inject real gateway token, NOT spoofed one
            self.assertEqual(forwarded_headers.get("X-Gateway-Token"), settings.GATEWAY_SERVICE_TOKEN)
            self.assertNotEqual(forwarded_headers.get("X-Gateway-Token"), spoofed_gateway_token)

    # ── 3. Proxying Payload & Methods ──────────────────────────────────

    def test_proctoring_event_proxied_with_body(self) -> None:
        """POST /interview/sessions/{task_id}/proctoring-event proxies payload to downstream."""
        token = self._create_token(self.user_id)
        mock_backend_response = httpx.Response(
            status_code=200,
            json={
                "event": {
                    "id": str(uuid.uuid4()),
                    "session_id": str(uuid.uuid4()),
                    "event_type": "TAB_BLUR",
                    "timestamp": "2026-10-02T10:00:00Z",
                    "turn_number_at_event": 1,
                },
                "session_status": "IN_PROGRESS",
                "violation_count": 1,
                "max_violations": 3,
                "terminated": False,
                "termination_reason": None,
            },
            headers={"content-type": "application/json"},
        )

        with patch.object(self.client.app.state.http_client, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_backend_response

            payload = {"event_type": "TAB_BLUR", "turn_number_at_event": 1}
            resp = self.client.post(
                f"/interview/sessions/{self.task_id}/proctoring-event",
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            )

            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["violation_count"], 1)
            self.assertFalse(data["terminated"])

            # Verify downstream target and method
            called_url = str(mock_req.call_args[1]["url"])
            self.assertEqual(called_url, f"{settings.INTERVIEW_SERVICE_URL}/interview/sessions/{self.task_id}/proctoring-event")
            self.assertEqual(mock_req.call_args[1]["method"], "POST")

    # ── 4. Block /internal/interview/* at Gateway ──────────────────────

    def test_internal_interview_create_session_blocked_at_gateway(self) -> None:
        """
        POST /internal/interview/create-session must be blocked at gateway (404),
        preventing external clients from bypassing auth to create sessions.
        """
        resp = self.client.post(
            "/internal/interview/create-session",
            json={
                "task_id": self.task_id,
                "user_id": self.user_id,
                "evaluation_id": str(uuid.uuid4()),
            },
            headers={"X-Internal-Token": "secret"},
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["detail"], "Not found")
        self.assertNotIn("Traceback", resp.text)

    def test_internal_interview_any_path_blocked_at_gateway(self) -> None:
        """GET /internal/interview/* must be blocked at gateway (404)."""
        resp = self.client.get(
            f"/internal/interview/{self.task_id}",
            headers={"X-Internal-Token": "secret"},
        )
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn("Traceback", resp.text)

    # ── 5. Downstream Failure Handling (503 and 504) ────────────────────

    def test_downstream_service_unavailable_returns_503(self) -> None:
        """Connection error to interview service returns 503 Service Unavailable."""
        token = self._create_token(self.user_id)

        with patch.object(self.client.app.state.http_client, "request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = httpx.ConnectError("Failed to connect")

            resp = self.client.get(
                f"/interview/sessions/{self.task_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(resp.status_code, 503)
            self.assertIn("Interview agent service is unavailable", resp.json()["detail"])
            self.assertNotIn("Traceback", resp.text)

    def test_downstream_service_timeout_returns_504(self) -> None:
        """Timeout connecting to interview service returns 504 Gateway Timeout."""
        token = self._create_token(self.user_id)

        with patch.object(self.client.app.state.http_client, "request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = httpx.TimeoutException("Read timed out")

            resp = self.client.get(
                f"/interview/sessions/{self.task_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(resp.status_code, 504)
            self.assertIn("Interview agent service request timed out", resp.json()["detail"])
            self.assertNotIn("Traceback", resp.text)

    # ── 6. Traceback check across routes ───────────────────────────────

    def test_no_response_contains_traceback(self) -> None:
        """All interview error responses must never leak Python tracebacks."""
        test_routes = [
            ("GET", f"/interview/sessions/{self.task_id}"),
            ("POST", f"/interview/sessions/{self.task_id}/start"),
            ("POST", f"/interview/sessions/{self.task_id}/answer"),
            ("POST", f"/interview/sessions/{self.task_id}/proctoring-event"),
            ("GET", f"/interview/sessions/{self.task_id}/resume"),
        ]
        for method, path in test_routes:
            resp = self.client.request(method, path)
            self.assertNotIn(
                "Traceback",
                resp.text,
                msg=f"Response for {method} {path} contains 'Traceback': {resp.text[:200]}",
            )


if __name__ == "__main__":
    unittest.main()
