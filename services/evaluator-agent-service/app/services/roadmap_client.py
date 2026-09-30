"""
RoadmapClient: Service-to-service HTTP client for interacting with roadmap-agent-service.

Called by evaluator-agent-service to:
1. Claim a task for evaluation (SUBMITTED -> EVALUATING)
2. Post evaluation result (EVALUATING -> EVALUATED)
3. Fail evaluation (EVALUATING -> SUBMITTED, allowing re-submission)

Security: Uses X-Internal-Token header for service-to-service authentication.
Never goes through the API gateway.
"""

import asyncio
import logging
import uuid
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger("evaluator-agent.roadmap-client")


class RoadmapServiceUnavailableError(Exception):
    """Raised when the roadmap service cannot be reached."""
    pass


class TaskNotFoundError(Exception):
    """Raised when the task does not exist in roadmap-agent-service."""
    pass


class TaskStateConflictError(Exception):
    """Raised when the task is in an unexpected state (e.g. already EVALUATING)."""
    pass


class RoadmapClient:
    """
    Async HTTP client for interacting with roadmap-agent-service internal API.

    All calls use X-Internal-Token authentication and target the internal
    service URL directly (never through the gateway).
    """

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float = 15.0,
    ) -> None:
        self.base_url = base_url or settings.ROADMAP_SERVICE_INTERNAL_URL
        self.token = token or settings.INTERNAL_SERVICE_TOKEN
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"X-Internal-Token": self.token}

    async def _request(
        self,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
        retries: int = 1,
    ) -> dict[str, Any]:
        """Make an authenticated internal API call with 1 retry on network failure."""
        url = f"{self.base_url}{path}"
        last_error: Exception | None = None

        for attempt in range(retries + 1):
            if attempt > 0:
                await asyncio.sleep(0.5)
                logger.info("RoadmapClient: Retry attempt %d for %s %s", attempt, method, url)

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=self._headers(),
                        json=json_body,
                    )

                if response.status_code == 200:
                    return response.json()

                if response.status_code == 404:
                    raise TaskNotFoundError(f"Task not found at {url}")

                if response.status_code == 409:
                    raise TaskStateConflictError(
                        f"Task state conflict at {url}: {response.text[:200]}"
                    )

                if response.status_code == 403:
                    raise RoadmapServiceUnavailableError(
                        "Internal token rejected by roadmap-agent-service"
                    )

                logger.warning(
                    "RoadmapClient: Unexpected status %d from %s", response.status_code, url
                )
                last_error = Exception(f"Unexpected status {response.status_code}: {response.text[:200]}")

            except (TaskNotFoundError, TaskStateConflictError):
                raise  # Do not retry these

            except httpx.ConnectError as exc:
                logger.warning("RoadmapClient: Connection error on attempt %d: %s", attempt + 1, exc)
                last_error = exc

            except httpx.TimeoutException as exc:
                logger.warning("RoadmapClient: Timeout on attempt %d: %s", attempt + 1, exc)
                last_error = exc

            except httpx.HTTPError as exc:
                logger.warning("RoadmapClient: HTTP error on attempt %d: %s", attempt + 1, exc)
                last_error = exc

        raise RoadmapServiceUnavailableError(
            f"Roadmap service unavailable after {retries + 1} attempt(s). Last error: {last_error}"
        )

    async def claim_evaluation(self, task_id: uuid.UUID) -> dict[str, Any]:
        """
        Claim a task for evaluation: SUBMITTED -> EVALUATING.

        Raises:
            TaskNotFoundError: Task does not exist.
            TaskStateConflictError: Task is not in SUBMITTED state (already claimed).
            RoadmapServiceUnavailableError: Service unreachable.
        """
        logger.info("RoadmapClient: Claiming task %s for evaluation", task_id)
        return await self._request("POST", f"/internal/tasks/{task_id}/claim-evaluation")

    async def post_evaluation_result(
        self,
        task_id: uuid.UUID,
        score: float,
        passed: bool,
        feedback: str,
        evaluated_by: str = "agent-3",
    ) -> dict[str, Any]:
        """
        Post evaluation result: EVALUATING -> EVALUATED.

        Raises:
            TaskNotFoundError: Task does not exist.
            TaskStateConflictError: Task is not in EVALUATING state.
            RoadmapServiceUnavailableError: Service unreachable.
        """
        logger.info(
            "RoadmapClient: Posting evaluation for task %s (score=%.1f, passed=%s)",
            task_id, score, passed,
        )
        return await self._request(
            "POST",
            f"/internal/tasks/{task_id}/evaluation",
            json_body={
                "score": round(score, 2),
                "passed": passed,
                "feedback": feedback,
                "evaluated_by": evaluated_by,
            },
        )

    async def fail_evaluation(self, task_id: uuid.UUID) -> dict[str, Any]:
        """
        Roll back task to SUBMITTED state after an evaluation pipeline error.
        EVALUATING -> SUBMITTED (allows student to re-submit).

        Raises:
            TaskNotFoundError: Task does not exist.
            RoadmapServiceUnavailableError: Service unreachable.
        """
        logger.info("RoadmapClient: Rolling back evaluation for task %s -> SUBMITTED", task_id)
        return await self._request("POST", f"/internal/tasks/{task_id}/fail-evaluation")
