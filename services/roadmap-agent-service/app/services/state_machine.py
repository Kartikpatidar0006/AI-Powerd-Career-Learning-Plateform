"""
Task State Machine — the single authority for all task status transitions.

All state transitions MUST go through this module. No router or service
may set task.status directly without calling TaskStateMachine.

Valid transitions:
    ASSIGNED -> IN_PROGRESS       (POST /tasks/{id}/start)
    IN_PROGRESS -> SUBMITTED      (POST /tasks/{id}/submit)
    SUBMITTED -> SUBMITTED        (POST /tasks/{id}/submit re-submission, link fix)
    SUBMITTED -> EVALUATING       (POST /internal/tasks/{id}/claim-evaluation)
    EVALUATING -> EVALUATED       (POST /internal/tasks/{id}/evaluation — Agent 3)
    EVALUATING -> SUBMITTED       (On evaluator failure/fallback)

All other transitions are illegal and raise TaskTransitionError.
Re-submission of the GitHub URL is allowed only in SUBMITTED, never in EVALUATING.
"""

import logging
from app.models.task import TaskStatus

logger = logging.getLogger("roadmap-agent.state-machine")

# Complete transition matrix — maps current status to allowed next statuses
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    TaskStatus.ASSIGNED: {TaskStatus.IN_PROGRESS},
    TaskStatus.IN_PROGRESS: {TaskStatus.SUBMITTED},
    TaskStatus.SUBMITTED: {TaskStatus.SUBMITTED, TaskStatus.EVALUATING},
    TaskStatus.EVALUATING: {TaskStatus.EVALUATED, TaskStatus.SUBMITTED},
    TaskStatus.EVALUATED: set(),  # Terminal state
}


class TaskTransitionError(Exception):
    """Raised when an illegal state transition is attempted."""

    def __init__(self, current: str, attempted: str) -> None:
        super().__init__(
            f"Cannot transition task from '{current}' to '{attempted}'. "
            f"Allowed transitions from '{current}': "
            f"{ALLOWED_TRANSITIONS.get(current, set())}"
        )
        self.current = current
        self.attempted = attempted


class TaskStateMachine:
    """
    Enforces the task lifecycle state machine.

    This class is the ONLY place that validates and applies status transitions.
    It never touches the database — callers are responsible for persistence.

    Usage:
        machine = TaskStateMachine()
        machine.transition(task, TaskStatus.IN_PROGRESS)  # Mutates task.status
    """

    def transition(self, task: "Task", new_status: str) -> None:  # type: ignore[name-defined]  # noqa
        """
        Validate and apply a status transition.

        Args:
            task: The ORM Task object whose status will be updated.
            new_status: The target status (must be a TaskStatus value).

        Raises:
            TaskTransitionError: If the transition is not in the allowed matrix.
        """
        current = task.status
        allowed = ALLOWED_TRANSITIONS.get(current, set())

        if new_status not in allowed:
            logger.warning(
                "Illegal task transition attempted: %s -> %s for task %s",
                current, new_status, task.id,
            )
            raise TaskTransitionError(current, new_status)

        logger.info(
            "Task %s transitioning: %s -> %s", task.id, current, new_status
        )
        task.status = new_status

    def can_transition(self, current_status: str, new_status: str) -> bool:
        """
        Check if a transition is valid without applying it.

        Args:
            current_status: Current task status string.
            new_status: Desired target status string.

        Returns:
            True if transition is allowed, False otherwise.
        """
        return new_status in ALLOWED_TRANSITIONS.get(current_status, set())
