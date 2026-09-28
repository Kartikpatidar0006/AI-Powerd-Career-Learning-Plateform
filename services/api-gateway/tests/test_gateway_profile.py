"""
Tests for API Gateway JWT verification and /profile/* proxying.
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
        self.client = TestClient(app)
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


if __name__ == "__main__":
    unittest.main()
