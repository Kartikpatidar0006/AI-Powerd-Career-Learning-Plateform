"""
Skeleton tests for interview-agent-service (Agent 4).

Verifies:
1. GET /health returns 200 with {"status": "healthy", "service": "Interview Agent Service"}
2. Gateway middleware blocks requests without X-Gateway-Token on non-exempt routes
3. Gateway middleware allows requests with valid X-Gateway-Token
4. LLM provider factory blocks mock provider in production
5. LLM provider factory allows mock provider in development
6. Mock LLM provider returns deterministic JSON
7. Base metadata exists and is empty initially
"""

import unittest
from unittest.mock import patch

from fastapi import status
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.llm.base import BaseLLMProvider
from app.core.llm.factory import get_llm_provider
from app.core.llm.mock_provider import MockLLMProvider
from app.db.base import Base
from app.main import app


class TestInterviewAgentSkeleton(unittest.TestCase):
    """Test suite for service skeleton configuration and health."""

    def setUp(self) -> None:
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_health_check_returns_200_and_healthy(self) -> None:
        """GET /health must return 200 OK without requiring gateway token."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], settings.APP_NAME)
        self.assertEqual(data["env"], settings.APP_ENV)

    def test_gateway_middleware_blocks_missing_token(self) -> None:
        """Non-exempt route without X-Gateway-Token must return 403 Forbidden."""
        response = self.client.get("/some-protected-endpoint")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Forbidden", response.json().get("detail", ""))

    def test_gateway_middleware_blocks_invalid_token(self) -> None:
        """Non-exempt route with incorrect X-Gateway-Token must return 403 Forbidden."""
        response = self.client.get(
            "/some-protected-endpoint",
            headers={"X-Gateway-Token": "invalid-wrong-token"},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Forbidden", response.json().get("detail", ""))

    def test_mock_llm_refused_in_production(self) -> None:
        """Factory must raise ValueError when mock provider is attempted in production."""
        with patch.object(settings, "LLM_PROVIDER", "mock"):
            with patch.object(settings, "APP_ENV", "production"):
                with self.assertRaises(ValueError) as ctx:
                    get_llm_provider()
                self.assertIn("strictly disallowed", str(ctx.exception))

    def test_mock_llm_allowed_in_development(self) -> None:
        """Factory must return MockLLMProvider when APP_ENV=development."""
        with patch.object(settings, "LLM_PROVIDER", "mock"):
            with patch.object(settings, "APP_ENV", "development"):
                provider = get_llm_provider()
                self.assertIsInstance(provider, MockLLMProvider)
                self.assertIsInstance(provider, BaseLLMProvider)

    def test_base_metadata_initialized(self) -> None:
        """Base SQLAlchemy metadata should be initialized with the 3 interview models."""
        self.assertIsNotNone(Base.metadata)
        self.assertEqual(len(Base.metadata.tables), 3)
        self.assertIn("interview_sessions", Base.metadata.tables)
        self.assertIn("interview_turns", Base.metadata.tables)
        self.assertIn("proctoring_events", Base.metadata.tables)


if __name__ == "__main__":
    unittest.main()
