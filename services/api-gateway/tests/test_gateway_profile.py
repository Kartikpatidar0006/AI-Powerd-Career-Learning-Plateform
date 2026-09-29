"""
Tests for API Gateway — JWT verification, proxying, and route blocking.

Week 3 additions:
- Test that /internal/* returns 404 (blocked at gateway)
- Test that /dev/* returns 404 (blocked at gateway)
- Test that /roadmap/* and /tasks/* require JWT auth
"""

from datetime import datetime, timedelta, timezone
import unittest
import uuid

from fastapi import HTTPException
from fastapi.testclient import TestClient
from jose import jwt

from app.config import settings
from app.main import app, extract_and_verify_user_id


class TestGatewayProfileProxy(unittest.TestCase):
    """Test API Gateway JWT authentication enforcement before forwarding to profile service."""

    def setUp(self) -> None:
        import httpx
        self.client = TestClient(app)
        app.state.http_client = httpx.AsyncClient()
        self.user_id = str(uuid.uuid4())

    def _create_token(self, sub: str, token_type: str = "access", expired: bool = False) -> str:
        delta = timedelta(minutes=-5) if expired else timedelta(minutes=30)
        exp = datetime.now(timezone.utc) + delta
        claims = {
            "sub": sub,
            "type": token_type,
            "exp": exp,
        }
        return jwt.encode(claims, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    def test_missing_auth_header_rejected(self) -> None:
        """Requests without Authorization header must be rejected with 401."""
        response = self.client.get("/profile/me")
        self.assertEqual(response.status_code, 401)
        self.assertIn("Authentication credentials were not provided", response.json()["detail"])

    def test_invalid_token_rejected(self) -> None:
        """Requests with corrupted or invalid signature token must be rejected with 401."""
        response = self.client.get(
            "/profile/me",
            headers={"Authorization": "Bearer invalid.jwt.token"},
        )
        self.assertEqual(response.status_code, 401)

    def test_expired_token_rejected(self) -> None:
        """Requests with expired access token must be rejected with 401."""
        token = self._create_token(self.user_id, expired=True)
        response = self.client.get(
            "/profile/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 401)

    def test_refresh_token_rejected_for_api_route(self) -> None:
        """Passing a refresh token instead of access token must be rejected with 401."""
        token = self._create_token(self.user_id, token_type="refresh")
        response = self.client.get(
            "/profile/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("access token required", response.json()["detail"])

    def test_valid_token_extracts_correct_user_id(self) -> None:
        """Valid access token extracts the exact user UUID from the sub claim."""
        token = self._create_token(self.user_id)
        from fastapi import Request

        # Create mock request with Authorization header
        class DummyRequest:
            headers = {"Authorization": f"Bearer {token}"}

        extracted_id = extract_and_verify_user_id(DummyRequest())
        self.assertEqual(extracted_id, self.user_id)

    # ── Week 3: Internal/Dev Route Blocking ──────────────────────────

    def test_gateway_blocks_internal_profile_get(self) -> None:
        """GET /internal/* must be blocked at the gateway with 404."""
        response = self.client.get(
            f"/internal/profile/{self.user_id}",
            headers={"X-Internal-Token": "some-token"},
        )
        self.assertIn(
            response.status_code, [403, 404],
            msg=f"Expected 403/404 for /internal/*, got {response.status_code}",
        )

    def test_gateway_blocks_internal_post(self) -> None:
        """POST /internal/tasks/* must be blocked at the gateway with 404."""
        task_id = str(uuid.uuid4())
        response = self.client.post(
            f"/internal/tasks/{task_id}/evaluation",
            json={"passed": True},
            headers={"X-Internal-Token": "any-token"},
        )
        self.assertIn(
            response.status_code, [403, 404],
            msg=f"Expected 403/404 for /internal/*, got {response.status_code}",
        )

    def test_gateway_blocks_dev_simulate_evaluation(self) -> None:
        """POST /dev/* must be blocked at the gateway with 404."""
        task_id = str(uuid.uuid4())
        response = self.client.post(f"/dev/tasks/{task_id}/simulate-evaluation")
        self.assertIn(
            response.status_code, [403, 404],
            msg=f"Expected 403/404 for /dev/*, got {response.status_code}",
        )

    def test_gateway_blocks_dev_any_path(self) -> None:
        """Any /dev/* path must be blocked at the gateway."""
        response = self.client.get("/dev/anything")
        self.assertIn(response.status_code, [403, 404])

    # ── Week 3: Roadmap/Tasks JWT Enforcement ─────────────────────────

    def test_roadmap_generate_requires_jwt(self) -> None:
        """POST /roadmap/generate without JWT must return 401."""
        response = self.client.post("/roadmap/generate")
        self.assertEqual(response.status_code, 401)

    def test_roadmap_me_requires_jwt(self) -> None:
        """GET /roadmap/me without JWT must return 401."""
        response = self.client.get("/roadmap/me")
        self.assertEqual(response.status_code, 401)

    def test_tasks_next_requires_jwt(self) -> None:
        """POST /tasks/next without JWT must return 401."""
        response = self.client.post("/tasks/next")
        self.assertEqual(response.status_code, 401)

    def test_tasks_current_requires_jwt(self) -> None:
        """GET /tasks/current without JWT must return 401."""
        response = self.client.get("/tasks/current")
        self.assertEqual(response.status_code, 401)

    def test_no_response_contains_traceback(self) -> None:
        """Error responses must never contain Python tracebacks."""
        test_cases = [
            ("GET", "/profile/me", None),
            ("GET", "/roadmap/me", None),
            ("POST", "/roadmap/generate", None),
            ("POST", "/tasks/next", None),
            ("GET", "/tasks/current", None),
        ]
        for method, path, body in test_cases:
            response = self.client.request(method, path, json=body)
            self.assertNotIn(
                "Traceback",
                response.text,
                msg=f"Response for {method} {path} contains 'Traceback': {response.text[:200]}",
            )


    # ── Week 3: Rate Limiting & Gateway Token Hardening ───────────────

    def test_rate_limit_per_user_enforced(self) -> None:
        """
        4th request within a minute for an expensive LLM endpoint must return 429.
        Rate limiting must be per-user, not global.
        """
        from unittest.mock import AsyncMock, patch
        import httpx

        mock_resp = httpx.Response(
            status_code=200,
            content=b'{"status": "ok"}',
            headers={"content-type": "application/json"},
        )

        user_a = str(uuid.uuid4())
        user_b = str(uuid.uuid4())
        token_a = self._create_token(user_a)
        token_b = self._create_token(user_b)

        with patch.object(self.client.app.state.http_client, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_resp

            # User A: 3 requests allowed
            for i in range(3):
                r = self.client.post("/tasks/next", headers={"Authorization": f"Bearer {token_a}"})
                self.assertEqual(r.status_code, 200, f"User A request {i+1} should succeed")

            # User A: 4th request gets 429
            r4 = self.client.post("/tasks/next", headers={"Authorization": f"Bearer {token_a}"})
            self.assertEqual(r4.status_code, 429)
            self.assertIn("Rate limit exceeded", r4.json()["detail"])
            self.assertIn("Retry-After", r4.headers)

            # User B: 1st request succeeds (proves rate limit is PER-USER, not global)
            rb = self.client.post("/tasks/next", headers={"Authorization": f"Bearer {token_b}"})
            self.assertEqual(rb.status_code, 200, "User B should NOT be rate limited by User A")

    def test_gateway_token_injected_and_client_headers_stripped(self) -> None:
        """
        Gateway must inject verified X-Gateway-Token and X-User-Id downstream.
        Any client-sent X-Gateway-Token or X-User-Id must be stripped before forwarding.
        """
        from unittest.mock import AsyncMock, patch
        import httpx

        mock_resp = httpx.Response(
            status_code=200,
            content=b'{"status": "ok"}',
            headers={"content-type": "application/json"},
        )

        real_user = str(uuid.uuid4())
        token = self._create_token(real_user)

        with patch.object(self.client.app.state.http_client, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_resp

            spoofed_user = str(uuid.uuid4())
            spoofed_token = "spoofed-gateway-secret"

            # Client attempts to spoof X-User-Id and X-Gateway-Token
            headers = {
                "Authorization": f"Bearer {token}",
                "X-User-Id": spoofed_user,
                "X-Gateway-Token": spoofed_token,
            }
            response = self.client.get("/profile/me", headers=headers)
            self.assertEqual(response.status_code, 200)

            # Verify arguments sent to downstream service
            self.assertTrue(mock_req.called)
            forwarded_headers = mock_req.call_args[1]["headers"]

            # 1. Forwarded X-User-Id MUST be the verified JWT user, NOT the spoofed one
            self.assertEqual(forwarded_headers.get("X-User-Id"), real_user)
            self.assertNotEqual(forwarded_headers.get("X-User-Id"), spoofed_user)

            # 2. Forwarded X-Gateway-Token MUST be gateway's configured secret, NOT the spoofed one
            self.assertEqual(forwarded_headers.get("X-Gateway-Token"), settings.GATEWAY_SERVICE_TOKEN)
            self.assertNotEqual(forwarded_headers.get("X-Gateway-Token"), spoofed_token)


if __name__ == "__main__":
    unittest.main()
