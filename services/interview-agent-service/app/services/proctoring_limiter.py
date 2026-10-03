"""
Proctoring Rate Limiter module.

Implements an in-memory thread-safe sliding-window rate limiter
per interview session to guard against buggy frontend loops or event spamming.
"""

import threading
import time


from app.core.config import settings


class ProctoringRateLimiter:
    """Thread-safe sliding-window rate limiter per session ID."""

    def __init__(self, max_requests: int | None = None, window_seconds: float = 60.0) -> None:
        self.max_requests = max_requests if max_requests is not None else settings.PROCTORING_RATE_LIMIT_PER_MINUTE
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._history: dict[str, list[float]] = {}

    def is_allowed(self, session_id: str, max_requests: int | None = None) -> tuple[bool, int]:
        """
        Check if an event is allowed for this session_id.

        Returns:
            (allowed: bool, retry_after_seconds: int)
        """
        limit = max_requests if max_requests is not None else self.max_requests
        now = time.time()
        with self._lock:
            timestamps = self._history.get(session_id, [])
            cutoff = now - self.window_seconds
            valid = [t for t in timestamps if t > cutoff]

            if len(valid) >= limit:
                retry_after = max(1, int(self.window_seconds - (now - valid[0])))
                self._history[session_id] = valid
                return False, retry_after

            valid.append(now)
            self._history[session_id] = valid
            return True, 0

    def reset(self, session_id: str | None = None) -> None:
        """Reset history for tests or cleanup."""
        with self._lock:
            if session_id:
                self._history.pop(session_id, None)
            else:
                self._history.clear()


proctoring_rate_limiter = ProctoringRateLimiter(
    max_requests=settings.PROCTORING_RATE_LIMIT_PER_MINUTE,
    window_seconds=60.0,
)


def get_proctoring_rate_limiter() -> ProctoringRateLimiter:
    """FastAPI dependency injecting the singleton rate limiter."""
    return proctoring_rate_limiter

