"""
Tests for Profile Agent Service defense-in-depth: X-Gateway-Token verification.

Downstream service must reject user-facing requests lacking a valid X-Gateway-Token with 403 Forbidden.
Health check and internal routes must remain exempt.
"""

import unittest
import uuid
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.services.profile_service import ProfileService


class TestProfileGatewayDefense(unittest.TestCase):
    """Test defense-in-depth X-Gateway-Token enforcement on Profile Agent Service."""

    def setUp(self) -> None:
        self.client = TestClient(app)
        self.user_id = str(uuid.uuid4())

    def test_health_check_exempt_without_gateway_token(self) -> None:
        """Health probe must return 200 without X-Gateway-Token."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)

    def test_profile_me_missing_gateway_token_returns_403(self) -> None:
        """GET /profile/me without X-Gateway-Token must return 403 Forbidden."""
        response = self.client.get(
            "/profile/me",
            headers={"X-User-Id": self.user_id},
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("Forbidden", response.json().get("detail", ""))

    def test_profile_me_invalid_gateway_token_returns_403(self) -> None:
        """GET /profile/me with invalid X-Gateway-Token must return 403 Forbidden."""
        response = self.client.get(
            "/profile/me",
            headers={"X-User-Id": self.user_id, "X-Gateway-Token": "bad-token"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("Forbidden", response.json().get("detail", ""))

    def test_onboarding_missing_gateway_token_returns_403(self) -> None:
        """POST /profile/onboarding without X-Gateway-Token must return 403 Forbidden."""
        response = self.client.post(
            "/profile/onboarding",
            headers={"X-User-Id": self.user_id},
            json={},
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("Forbidden", response.json().get("detail", ""))

    def test_internal_profile_exempt_from_gateway_token(self) -> None:
        """Internal service-to-service route /internal/* must not require X-Gateway-Token."""
        with patch.object(ProfileService, "get_by_user_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            response = self.client.get(
                f"/internal/profile/{self.user_id}",
                headers={"X-Internal-Token": settings.INTERNAL_SERVICE_TOKEN},
            )
            # 404 because profile doesn't exist, NOT 403 (verifies middleware did not block it)
            self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
