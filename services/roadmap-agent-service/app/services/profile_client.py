"""
ProfileClient: Service-to-service HTTP client for fetching locked profiles
from profile-agent-service via the internal /internal/profile/{user_id} endpoint.

Security: Uses X-Internal-Token header for service-to-service authentication.
Resilience: Async httpx with timeout and 1 retry with exponential backoff.
Never queries the profile database directly — strict service boundary.
"""

import asyncio
import logging
import uuid
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger("roadmap-agent.profile-client")


class ProfileServiceUnavailableError(Exception):
    """Raised when the profile service cannot be reached."""
    pass


class ProfileNotFoundError(Exception):
    """Raised when no profile exists for the given user (onboarding not complete)."""
    pass


class ProfileClient:
    """
    Async HTTP client for fetching student profiles from profile-agent-service.

    Uses the internal /internal/profile/{user_id} endpoint — NOT the public API
    or the gateway. This path is never exposed externally.

    Attributes:
        base_url: Internal URL of the profile-agent-service.
        token: Shared secret header value for service-to-service auth.
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = base_url or settings.PROFILE_SERVICE_INTERNAL_URL
        self.token = token or settings.INTERNAL_SERVICE_TOKEN
        self.timeout = timeout

    async def get_profile(self, user_id: uuid.UUID) -> dict[str, Any]:
        """
        Fetch a locked student profile for the given user_id.

        Retries once with 500ms backoff on network errors.

        Args:
            user_id: The authenticated user's UUID.

        Returns:
            The profile payload as a dict.

        Raises:
            ProfileNotFoundError: If HTTP 404 — user has not completed onboarding.
            ProfileServiceUnavailableError: On network failure or non-recoverable error.
        """
        url = f"{self.base_url}/internal/profile/{user_id}"
        headers = {"X-Internal-Token": self.token}

        last_error: Exception | None = None

        for attempt in range(2):  # 1 retry
            if attempt > 0:
                await asyncio.sleep(0.5)  # Backoff before retry
                logger.info("ProfileClient: Retry attempt %d for user %s", attempt + 1, user_id)

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url, headers=headers)

                if response.status_code == 200:
                    logger.info("ProfileClient: Successfully fetched profile for user %s", user_id)
                    return response.json()

                elif response.status_code == 404:
                    logger.info(
                        "ProfileClient: Profile not found for user %s (onboarding incomplete)",
                        user_id,
                    )
                    raise ProfileNotFoundError(f"No profile found for user {user_id}")

                elif response.status_code == 403:
                    logger.error(
                        "ProfileClient: Internal token rejected by profile service (%d)",
                        response.status_code,
                    )
                    raise ProfileServiceUnavailableError(
                        "Internal authentication rejected by profile service"
                    )

                else:
                    logger.warning(
                        "ProfileClient: Unexpected status %d from profile service",
                        response.status_code,
                    )
                    last_error = Exception(
                        f"Profile service returned unexpected status {response.status_code}"
                    )

            except ProfileNotFoundError:
                raise  # Don't retry on 404

            except httpx.ConnectError as exc:
                logger.warning("ProfileClient: Connection error on attempt %d: %s", attempt + 1, exc)
                last_error = exc

            except httpx.TimeoutException as exc:
                logger.warning("ProfileClient: Timeout on attempt %d: %s", attempt + 1, exc)
                last_error = exc

            except httpx.HTTPError as exc:
                logger.warning("ProfileClient: HTTP error on attempt %d: %s", attempt + 1, exc)
                last_error = exc

        logger.error(
            "ProfileClient: All attempts failed for user %s. Last error: %s",
            user_id,
            last_error,
        )
        raise ProfileServiceUnavailableError(
            f"Profile service is unavailable after retry. Last error: {last_error}"
        )
