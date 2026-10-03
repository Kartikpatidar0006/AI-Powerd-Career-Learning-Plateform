"""
Tests for InterviewClient and interview session trigger upon evaluation completion.
"""

import asyncio
import unittest
import uuid
from unittest.mock import AsyncMock, patch

import pytest
import httpx

from app.core.config import settings
from app.services.interview_client import InterviewClient


class TestInterviewClient(unittest.IsolatedAsyncioTestCase):
    """Test InterviewClient behavior and network error resilience."""

    def setUp(self) -> None:
        self.task_id = uuid.uuid4()
        self.user_id = uuid.uuid4()
        self.evaluation_id = uuid.uuid4()
        self.client = InterviewClient(
            base_url="http://interview-agent-service:8005",
            token="test-secret-token",
            timeout=2.0,
        )

    async def test_create_session_success(self) -> None:
        """create_session posts payload with X-Internal-Token and returns True on 200."""
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = httpx.Response(
                status_code=200,
                json={"id": str(uuid.uuid4()), "status": "AVAILABLE"},
                request=httpx.Request("POST", "http://interview-agent-service:8005/internal/interview/create-session"),
            )

            result = await self.client.create_session(
                task_id=self.task_id,
                user_id=self.user_id,
                evaluation_id=self.evaluation_id,
                evaluation_context={"weaknesses": ["missing error handling"]},
            )

            self.assertTrue(result)
            self.assertEqual(mock_post.call_count, 1)
            called_args, called_kwargs = mock_post.call_args
            self.assertEqual(called_args[0], "http://interview-agent-service:8005/internal/interview/create-session")
            self.assertEqual(called_kwargs["headers"]["X-Internal-Token"], "test-secret-token")
            self.assertEqual(called_kwargs["json"]["task_id"], str(self.task_id))
            self.assertEqual(called_kwargs["json"]["user_id"], str(self.user_id))
            self.assertEqual(called_kwargs["json"]["evaluation_id"], str(self.evaluation_id))
            self.assertEqual(called_kwargs["json"]["evaluation_context"]["weaknesses"], ["missing error handling"])

    async def test_create_session_resilience_on_failure(self) -> None:
        """create_session returns False on repeated connection error without raising."""
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection refused")

            result = await self.client.create_session(
                task_id=self.task_id,
                user_id=self.user_id,
                evaluation_id=self.evaluation_id,
            )

            self.assertFalse(result)
            self.assertEqual(mock_post.call_count, 2)  # Initial attempt + 1 retry
