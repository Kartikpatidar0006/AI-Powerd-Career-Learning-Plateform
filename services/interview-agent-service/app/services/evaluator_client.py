"""
EvaluatorClient: Service-to-service HTTP client for fetching evaluation records
from evaluator-agent-service via the internal API.

Security: Uses X-Internal-Token header for service-to-service authentication.
Resilience: Async httpx with timeout and 1 retry with exponential backoff.
Never queries the evaluator database directly — preserves strict microservice boundaries.
"""

import asyncio
import logging
import uuid
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger("interview-agent.evaluator-client")


class EvaluatorServiceUnavailableError(Exception):
    """Raised when the evaluator service cannot be reached."""
    pass


class EvaluatorClient:
    """
    Async HTTP client for fetching evaluation records from evaluator-agent-service.

    Uses internal service-to-service authentication (X-Internal-Token).
    """

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float = 3.0,
    ) -> None:
        self.base_url = (base_url or settings.EVALUATOR_SERVICE_INTERNAL_URL).rstrip("/")
        self.token = token or settings.INTERNAL_SERVICE_TOKEN
        self.timeout = timeout

    async def get_evaluation_by_task(self, task_id: uuid.UUID) -> dict[str, Any] | None:
        """
        Fetch the full evaluation record for the given task_id from evaluator-agent-service.

        Calls GET /internal/evaluations/by-task/{task_id} with X-Internal-Token.
        Returns dict containing weaknesses, red_flags, skills_targeted, deterministic_checks,
        or None if not found or unreachable.
        """
        url = f"{self.base_url}/internal/evaluations/by-task/{task_id}"
        headers = {"X-Internal-Token": self.token}

        for attempt in range(2):
            if attempt > 0:
                await asyncio.sleep(0.1)
                logger.info("EvaluatorClient: Retry attempt %d for task evaluation %s", attempt + 1, task_id)

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url, headers=headers)

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    logger.info("EvaluatorClient: No evaluation found for task %s", task_id)
                    return None
                else:
                    logger.warning(
                        "EvaluatorClient: Unexpected status %d from %s: %s",
                        response.status_code,
                        url,
                        response.text[:200],
                    )
            except Exception as exc:
                logger.warning(
                    "EvaluatorClient: Attempt %d failed connecting to %s: %s",
                    attempt + 1,
                    url,
                    exc,
                )

        return None

    async def get_evaluation(self, evaluation_id: uuid.UUID) -> dict[str, Any] | None:
        """
        Fetch the full evaluation record for the given evaluation_id.

        Calls GET /internal/evaluations/{evaluation_id} with X-Internal-Token.
        """
        url = f"{self.base_url}/internal/evaluations/{evaluation_id}"
        headers = {"X-Internal-Token": self.token}

        for attempt in range(2):  # 1 retry
            if attempt > 0:
                await asyncio.sleep(0.1)
                logger.info("EvaluatorClient: Retry attempt %d for evaluation %s", attempt + 1, evaluation_id)

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url, headers=headers)

                if response.status_code == 200:
                    return response.json()
                elif response.status_code in (404, 405):
                    logger.warning(
                        "EvaluatorClient: GET %s returned %d. Note: Evaluator Agent Service "
                        "does not yet expose GET /internal/evaluations/{id} (blocking dependency). "
                        "Falling back to session evaluation context.",
                        url,
                        response.status_code,
                    )
                    return None
                else:
                    logger.warning(
                        "EvaluatorClient: Unexpected status %d from %s: %s",
                        response.status_code,
                        url,
                        response.text[:200],
                    )
            except Exception as exc:
                logger.warning(
                    "EvaluatorClient: Attempt %d failed connecting to %s: %s",
                    attempt + 1,
                    url,
                    exc,
                )

        return None


# Singleton client instance
evaluator_client = EvaluatorClient()


def get_evaluator_client() -> EvaluatorClient:
    """FastAPI dependency injecting EvaluatorClient."""
    return evaluator_client
