"""
InterviewClient: Service-to-service HTTP client for triggering interview session creation
in interview-agent-service via the internal API.

Security: Uses X-Internal-Token header for service-to-service authentication.
Resilience: Fire-and-forget async httpx with timeout and 1 retry.
Never queries the interview database directly — preserves strict microservice boundaries.
"""

import asyncio
import logging
import uuid
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger("evaluator-agent.interview-client")


class InterviewServiceUnavailableError(Exception):
    """Raised when the interview service cannot be reached."""
    pass


class InterviewClient:
    """
    Async HTTP client for triggering interview session creation in interview-agent-service.
    """

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = (base_url or settings.INTERVIEW_SERVICE_INTERNAL_URL).rstrip("/")
        self.token = token or settings.INTERNAL_SERVICE_TOKEN
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"X-Internal-Token": self.token}

    async def create_session(
        self,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        evaluation_id: uuid.UUID,
        evaluation_context: dict[str, Any] | None = None,
    ) -> bool:
        """
        Trigger interview session creation in interview-agent-service.

        Calls POST /internal/interview/create-session with X-Internal-Token.
        Returns True on success (200 OK), False otherwise.
        """
        url = f"{self.base_url}/internal/interview/create-session"
        headers = self._headers()
        payload = {
            "task_id": str(task_id),
            "user_id": str(user_id),
            "evaluation_id": str(evaluation_id),
            "evaluation_context": evaluation_context,
        }

        for attempt in range(2):
            if attempt > 0:
                await asyncio.sleep(0.5)
                logger.info("InterviewClient: Retry attempt %d for task %s", attempt + 1, task_id)

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, headers=headers, json=payload)

                if response.status_code == 200:
                    logger.info("InterviewClient: Successfully created interview session for task %s", task_id)
                    return True
                else:
                    logger.warning(
                        "InterviewClient: Unexpected status %d for task %s: %s",
                        response.status_code, task_id, response.text[:200]
                    )
            except Exception as exc:
                logger.warning(
                    "InterviewClient: Request failed on attempt %d for task %s: %s",
                    attempt + 1, task_id, exc
                )

        return False
