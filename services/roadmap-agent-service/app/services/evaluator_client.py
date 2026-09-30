"""
EvaluatorClient: Service-to-service HTTP client for triggering evaluations
via evaluator-agent-service /internal/evaluate endpoint.

Called by roadmap-agent-service immediately after a task is submitted.
Uses X-Internal-Token authentication. Never goes through the API gateway.

Design: Fire-and-forget pattern — submit endpoint returns to the student
immediately after triggering evaluation. The evaluator handles the async
pipeline and will call back via /internal/tasks/{id}/evaluation when done.
"""

import asyncio
import logging
import uuid
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger("roadmap-agent.evaluator-client")


class EvaluatorServiceUnavailableError(Exception):
    """Raised when the evaluator service cannot be reached."""
    pass


class EvaluatorClient:
    """
    Async HTTP client for triggering evaluations in evaluator-agent-service.

    Implements fire-and-forget: if the evaluator service is unavailable,
    logs the error and returns without raising — the task remains in SUBMITTED
    state and can be re-triggered later or via manual ops.
    """

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = base_url or settings.EVALUATOR_SERVICE_INTERNAL_URL
        self.token = token or settings.INTERNAL_SERVICE_TOKEN
        self.timeout = timeout

    async def trigger_evaluation(
        self,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        github_repo_url: str,
        task_started_at: str | None,
        skills_targeted: list[str],
    ) -> bool:
        """
        Fire an evaluation trigger to evaluator-agent-service.

        Returns True on success, False on failure (caller may log but should not
        block the submit response to the student).

        Args:
            task_id: UUID of the submitted task.
            user_id: UUID of the submitting user.
            github_repo_url: Normalized GitHub repo URL.
            task_started_at: ISO8601 task start timestamp for commits check.
            skills_targeted: Skills list from the task (for relevant-files check).

        Returns:
            True if trigger was accepted (202), False otherwise.
        """
        url = f"{self.base_url}/internal/evaluate"
        headers = {"X-Internal-Token": self.token}
        body = {
            "task_id": str(task_id),
            "user_id": str(user_id),
            "github_repo_url": github_repo_url,
            "task_started_at": task_started_at,
            "skills_targeted": skills_targeted,
        }

        for attempt in range(2):  # 1 retry
            if attempt > 0:
                await asyncio.sleep(0.5)
                logger.info("EvaluatorClient: Retry attempt %d for task %s", attempt + 1, task_id)

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, headers=headers, json=body)

                if response.status_code in (200, 202):
                    logger.info(
                        "EvaluatorClient: Triggered evaluation for task %s — accepted", task_id
                    )
                    return True
                elif response.status_code == 409:
                    logger.warning(
                        "EvaluatorClient: Evaluation already in progress for task %s", task_id
                    )
                    return True  # Idempotent — already running is fine
                else:
                    logger.warning(
                        "EvaluatorClient: Unexpected status %d from evaluator for task %s: %s",
                        response.status_code, task_id, response.text[:200],
                    )

            except httpx.ConnectError as exc:
                logger.warning(
                    "EvaluatorClient: Connection error on attempt %d for task %s: %s",
                    attempt + 1, task_id, exc,
                )

            except httpx.TimeoutException as exc:
                logger.warning(
                    "EvaluatorClient: Timeout on attempt %d for task %s: %s",
                    attempt + 1, task_id, exc,
                )

            except httpx.HTTPError as exc:
                logger.warning(
                    "EvaluatorClient: HTTP error on attempt %d for task %s: %s",
                    attempt + 1, task_id, exc,
                )

        logger.error(
            "EvaluatorClient: Failed to trigger evaluation for task %s after retry. "
            "Task remains SUBMITTED — will need manual re-trigger or retry mechanism.",
            task_id,
        )
        return False
