"""
Tests for Auth Service defense-in-depth: X-Gateway-Token verification.

Downstream service must reject user-facing requests lacking a valid X-Gateway-Token with 403 Forbidden.
Health check and docs routes must remain exempt.
"""

import unittest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings


class TestAuthGatewayDefense(unittest.TestCase):
    """Test defense-in-depth X-Gateway-Token enforcement on Auth Service."""

    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_check_exempt_without_gateway_token(self) -> None:
        """Health probe must return 200 without X-Gateway-Token."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)

    def test_signup_missing_gateway_token_returns_403(self) -> None:
        """POST /auth/signup without X-Gateway-Token must return 403 Forbidden."""
        response = self.client.post(
            "/auth/signup",
            json={"email": "hacker@example.com", "password": "Password123!", "full_name": "Hacker"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("Forbidden", response.json().get("detail", ""))

    def test_signup_invalid_gateway_token_returns_403(self) -> None:
        """POST /auth/signup with invalid X-Gateway-Token must return 403 Forbidden."""
        response = self.client.post(
            "/auth/signup",
            headers={"X-Gateway-Token": "wrong-token"},
            json={"email": "hacker@example.com", "password": "Password123!", "full_name": "Hacker"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("Forbidden", response.json().get("detail", ""))

    def test_login_missing_gateway_token_returns_403(self) -> None:
        """POST /auth/login without X-Gateway-Token must return 403 Forbidden."""
        response = self.client.post(
            "/auth/login",
            json={"email": "user@example.com", "password": "Password123!"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("Forbidden", response.json().get("detail", ""))

    def test_login_invalid_gateway_token_returns_403(self) -> None:
        """POST /auth/login with invalid X-Gateway-Token must return 403 Forbidden."""
        response = self.client.post(
            "/auth/login",
            headers={"X-Gateway-Token": "bad-token"},
            json={"email": "user@example.com", "password": "Password123!"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("Forbidden", response.json().get("detail", ""))

    def test_valid_gateway_token_passes_defense_middleware(self) -> None:
        """Requests with valid X-Gateway-Token pass the middleware (not 403)."""
        response = self.client.post(
            "/auth/signup",
            headers={"X-Gateway-Token": settings.GATEWAY_SERVICE_TOKEN},
            json={"email": "invalid-email", "password": "short"},  # Deliberately invalid schema
        )
        # Should be 422 Unprocessable Entity (from Pydantic validation), NOT 403 Forbidden
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
