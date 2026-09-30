"""
Roadmap Service — Business logic for roadmap generation, task management,
milestone progress, and the "one active task per user" enforcement.

Enforcement layers for "one active task per user":
1. Application check: Query for existing active task before generating new one.
2. DB partial unique index: uix_one_active_task_per_user catches concurrent inserts.
3. IntegrityError handler: Concurrent requests that slip past check are caught at DB commit.
"""

import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm.base import BaseLLMProvider
from app.core.config import settings
from app.models.roadmap import Roadmap
from app.models.task import Task, TaskStatus
from app.schemas.roadmap import (
    LLMTaskOutput,
    MilestoneItem,
    MilestoneProgress,
    RoadmapResponse,
    TaskResponse,
)
from app.services.roadmap_agent import (
    PerformanceProvider,
    compute_next_difficulty,
    generate_roadmap_from_llm,
    generate_task_from_llm,
)
from app.services.state_machine import TaskStateMachine, TaskTransitionError

logger = logging.getLogger("roadmap-agent.roadmap-service")

# Planned tasks per milestone: estimated from estimated_days / 3 (roughly 3 days per task)
DAYS_PER_TASK = 3


class RoadmapAlreadyExistsError(Exception):
    """Raised when a roadmap already exists for this user (idempotency guard)."""
    pass


class RoadmapNotFoundError(Exception):
    """Raised when no roadmap exists for this user."""
    pass


class ActiveTaskExistsError(Exception):
    """Raised when a user already has an active task and requests another."""

    def __init__(self, message: str = "You already have an active task. Complete or submit it first.") -> None:
        super().__init__(message)
        self.message = message


class TaskNotFoundError(Exception):
    """Raised when a task does not exist or does not belong to the requesting user."""
    pass


class DuplicateRepoUrlError(Exception):
    """Raised when a user attempts to submit a GitHub repo URL already used for another task."""
    pass


# ──────────────────────────────────────────────────────────────────────
# Milestone Progress Logic
# ──────────────────────────────────────────────────────────────────────

def compute_milestone_progress(
    milestone_dicts: list[dict[str, Any]],
    tasks: list[Task],
) -> list[MilestoneProgress]:
    """
    Compute the progress state of each milestone from the student's task history.

    A milestone is COMPLETED when the number of PASSED EVALUATED tasks for it reaches
    or exceeds the planned task count (estimated_days // DAYS_PER_TASK, min 1).
    Milestone progress counts ONLY passed tasks (evaluation_summary['passed'] is True).
    A milestone with state 'needs_review' in the stored dict is treated as completed
    (the remediation attempt limit was reached; the student may advance).
    The CURRENT milestone is the first incomplete one. All after that are UPCOMING.

    Args:
        milestone_dicts: Raw milestone dicts from the Roadmap.milestones JSONB column.
        tasks: All tasks for this user (any status).

    Returns:
        List of MilestoneProgress objects with computed states.
    """
    milestones = sorted(milestone_dicts, key=lambda m: m["order"])

    # Count only PASSED evaluated tasks per milestone_order
    passed_by_milestone: dict[int, int] = {}
    for task in tasks:
        if task.status == TaskStatus.EVALUATED:
            summary = task.evaluation_summary or {}
            if summary.get("passed") is True:
                order = task.milestone_order
                passed_by_milestone[order] = passed_by_milestone.get(order, 0) + 1

    results: list[MilestoneProgress] = []
    # past_all_done: True while we are still consuming completed/needs_review milestones.
    # found_current: True once we have assigned 'current' to a milestone.
    past_all_done = True
    found_current = False

    for m in milestones:
        order = m["order"]
        planned = max(1, m.get("estimated_days", DAYS_PER_TASK) // DAYS_PER_TASK)
        completed_count = passed_by_milestone.get(order, 0)

        stored_state = m.get("state")
        # A milestone is "done" if it has enough passed tasks OR if it has been
        # flagged needs_review (remediation attempt limit reached).
        is_done = (completed_count >= planned) or (stored_state == "needs_review")

        if stored_state == "needs_review":
            state = "needs_review"
            # Stays done; past_all_done remains True if it already was
        elif completed_count >= planned:
            state = "completed"
        elif past_all_done and not found_current:
            # First non-done milestone after all preceding done milestones → current
            state = "current"
            found_current = True
            past_all_done = False
        else:
            state = "upcoming"

        # If this milestone is not done, the "all done" streak ends
        if not is_done:
            past_all_done = False

        results.append(MilestoneProgress(
            order=order,
            title=m["title"],
            description=m["description"],
            target_skills=m.get("target_skills", []),
            estimated_days=m.get("estimated_days", 10),
            difficulty_band=m.get("difficulty_band", 1),
            success_criteria=m.get("success_criteria", []),
            tasks_completed=completed_count,
            tasks_planned=planned,
            state=state,
        ))

    return results


def _count_consecutive_failed_on_milestone(
    all_tasks: list[Task],
    milestone_order: int,
) -> int:
    """
    Count the number of consecutive FAILED evaluated tasks on a given milestone.

    Sorted by sequence_number descending, counts failures until a passed task
    or a task on a different milestone is found.

    Args:
        all_tasks: All tasks for the user.
        milestone_order: The milestone order to count failures for.

    Returns:
        Count of consecutive trailing failures on this milestone.
    """
    milestone_tasks = [
        t for t in all_tasks
        if t.milestone_order == milestone_order and t.status == TaskStatus.EVALUATED
    ]
    # Sort by sequence_number descending (most recent first)
    milestone_tasks.sort(key=lambda t: t.sequence_number, reverse=True)

    count = 0
    for task in milestone_tasks:
        summary = task.evaluation_summary or {}
        if summary.get("passed") is False:
            count += 1
        else:
            break  # stop on first pass
    return count


# ──────────────────────────────────────────────────────────────────────
# RoadmapService
# ──────────────────────────────────────────────────────────────────────

class RoadmapService:
    """Service handling all roadmap and task domain operations."""

    def __init__(self, llm_provider: BaseLLMProvider) -> None:
        self.llm_provider = llm_provider
        self.state_machine = TaskStateMachine()
        self.performance_provider = PerformanceProvider()

    # ── Roadmap Operations ─────────────────────────────────────────

    async def get_roadmap_by_user_id(
        self, db: AsyncSession, user_id: uuid.UUID
    ) -> Roadmap | None:
        """Fetch the roadmap for a user, or None if not found."""
        stmt = select(Roadmap).where(Roadmap.user_id == user_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def generate_roadmap(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        profile: dict[str, Any],
    ) -> RoadmapResponse:
        """
        Generate and persist an idempotent roadmap for the user.

        Idempotency: If a roadmap already exists, returns 409.
        Atomicity: Roadmap is only inserted AFTER successful LLM validation.
        Race safety: IntegrityError on UNIQUE(user_id) is caught and returns 409.

        Args:
            db: Active database session.
            user_id: Authenticated user UUID.
            profile: Full profile dict from profile-agent-service.

        Returns:
            RoadmapResponse with milestone progress.

        Raises:
            RoadmapAlreadyExistsError: If roadmap exists (application or DB level).
            LLMValidationError, LLMTimeoutError, LLMProviderError: From LLM layer.
        """
        # Application-level idempotency check
        existing = await self.get_roadmap_by_user_id(db, user_id)
        if existing is not None:
            raise RoadmapAlreadyExistsError("Roadmap already exists for this user.")

        # 1. Call LLM and validate — NO DB write until successful
        logger.info("Generating roadmap for user %s", user_id)
        milestones = await generate_roadmap_from_llm(
            llm_provider=self.llm_provider,
            profile=profile,
        )

        # 2. Persist roadmap — only after successful validation
        new_roadmap = Roadmap(
            id=uuid.uuid4(),
            user_id=user_id,
            profile_snapshot=profile,
            milestones=[m.model_dump() for m in milestones],
            status="active",
        )

        try:
            db.add(new_roadmap)
            await db.commit()
            await db.refresh(new_roadmap)
        except IntegrityError as exc:
            await db.rollback()
            logger.warning(
                "IntegrityError inserting roadmap for user %s (concurrent creation): %s",
                user_id, exc,
            )
            raise RoadmapAlreadyExistsError(
                "Roadmap already exists (concurrent creation detected)."
            ) from exc

        logger.info(
            "Created roadmap %s for user %s with %d milestones",
            new_roadmap.id, user_id, len(milestones),
        )

        return await self._build_roadmap_response(db, new_roadmap)

    async def get_roadmap_response(
        self, db: AsyncSession, user_id: uuid.UUID
    ) -> RoadmapResponse | None:
        """Get roadmap with computed milestone progress."""
        roadmap = await self.get_roadmap_by_user_id(db, user_id)
        if roadmap is None:
            return None
        return await self._build_roadmap_response(db, roadmap)

    async def _build_roadmap_response(
        self, db: AsyncSession, roadmap: Roadmap
    ) -> RoadmapResponse:
        """Build a RoadmapResponse with computed milestone progress."""
        # Fetch all tasks for this user
        stmt = select(Task).where(Task.user_id == roadmap.user_id)
        result = await db.execute(stmt)
        tasks = list(result.scalars().all())

        milestone_progresses = compute_milestone_progress(roadmap.milestones, tasks)

        return RoadmapResponse(
            id=roadmap.id,
            user_id=roadmap.user_id,
            milestones=milestone_progresses,
            status=roadmap.status,
            created_at=roadmap.created_at,
            profile_snapshot=roadmap.profile_snapshot,
        )

    # ── Task Operations ─────────────────────────────────────────

    async def get_active_task(
        self, db: AsyncSession, user_id: uuid.UUID
    ) -> Task | None:
        """
        Get the user's current active task (ASSIGNED, IN_PROGRESS, SUBMITTED, or EVALUATING).

        A user should never have more than one — enforced by the DB partial unique index.
        """
        stmt = select(Task).where(
            and_(
                Task.user_id == user_id,
                Task.status.in_([
                    TaskStatus.ASSIGNED,
                    TaskStatus.IN_PROGRESS,
                    TaskStatus.SUBMITTED,
                    TaskStatus.EVALUATING,
                ]),
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def generate_next_task(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> dict[str, Any]:
        """
        Generate the next task for the user, or return roadmap_completed status.

        Pre-conditions (all enforced before any DB write):
        - Roadmap must exist.
        - No active task may exist (ASSIGNED/IN_PROGRESS/SUBMITTED/EVALUATING).
        - If last task failed evaluation (passed=False), next task is a REMEDIATION task
          on the same skills with previous feedback included.

        Returns:
            Dict with 'status' key: 'task_assigned' or 'roadmap_completed'.
            If task_assigned, includes the task response.

        Raises:
            RoadmapNotFoundError: No roadmap for this user.
            ActiveTaskExistsError: User has an unfinished task.
            LLMValidationError, LLMTimeoutError, LLMProviderError: From LLM.
        """
        # 1. Ensure roadmap exists
        roadmap = await self.get_roadmap_by_user_id(db, user_id)
        if roadmap is None:
            raise RoadmapNotFoundError("Generate your roadmap first.")

        # 2. Ensure no active task (application-level guard — DB index is the final safety net)
        active = await self.get_active_task(db, user_id)
        if active is not None:
            raise ActiveTaskExistsError(
                f"You already have an active task ('{active.title}', status: {active.status}). "
                "Complete, start, and submit it before requesting the next task."
            )

        # 3. Determine current milestone from progress
        stmt = select(Task).where(Task.user_id == user_id)
        result = await db.execute(stmt)
        all_tasks = list(result.scalars().all())

        milestone_progresses = compute_milestone_progress(roadmap.milestones, all_tasks)

        # Find all evaluated tasks sorted by sequence number
        evaluated_tasks = [t for t in all_tasks if t.status == TaskStatus.EVALUATED]
        evaluated_tasks.sort(key=lambda t: t.sequence_number)

        # Check if the last evaluated task failed (Item 4: remediation task)
        is_remediation = False
        previous_feedback = None
        remediation_milestone_order = None

        if evaluated_tasks:
            last_evaluated = evaluated_tasks[-1]
            last_summary = last_evaluated.evaluation_summary or {}
            if last_summary.get("passed") is False:
                is_remediation = True
                previous_feedback = last_summary.get("feedback") or "Previous task failed acceptance criteria."
                remediation_milestone_order = last_evaluated.milestone_order

        # MAX_REMEDIATION_ATTEMPTS: if the student has failed too many times on this
        # milestone, mark it as needs_review and let them advance to the next milestone.
        if is_remediation and remediation_milestone_order is not None:
            consecutive_failures = _count_consecutive_failed_on_milestone(
                all_tasks, remediation_milestone_order
            )
            if consecutive_failures >= settings.MAX_REMEDIATION_ATTEMPTS:
                logger.warning(
                    "User %s has hit MAX_REMEDIATION_ATTEMPTS (%d) on milestone %d. "
                    "Marking needs_review and allowing advancement.",
                    user_id,
                    settings.MAX_REMEDIATION_ATTEMPTS,
                    remediation_milestone_order,
                )
                # Mutate the milestone's stored state to needs_review
                new_milestones = []
                for m in roadmap.milestones:
                    if m["order"] == remediation_milestone_order:
                        m = dict(m)  # copy to avoid mutating the cached ORM dict
                        m["state"] = "needs_review"
                    new_milestones.append(m)
                roadmap.milestones = new_milestones
                await db.commit()
                await db.refresh(roadmap)

                # Reset remediation flag — treat as normal next-task request
                is_remediation = False
                previous_feedback = None
                remediation_milestone_order = None

                # Recompute milestone progress with the updated roadmap
                milestone_progresses = compute_milestone_progress(roadmap.milestones, all_tasks)

        # Find the current (non-completed) milestone
        current_milestone_progress = next(
            (mp for mp in milestone_progresses if mp.state == "current"), None
        )

        # All milestones completed (or needs_review — remediation limit reached)?
        # A needs_review milestone is treated as completed for advancement purposes.
        all_completed = all(mp.state in ("completed", "needs_review") for mp in milestone_progresses)
        if all_completed and not is_remediation:
            logger.info("All milestones completed for user %s — roadmap is done!", user_id)
            return {"status": "roadmap_completed"}

        target_order = remediation_milestone_order if is_remediation else (
            current_milestone_progress.order if current_milestone_progress else None
        )

        if target_order is None:
            logger.error("No target milestone found for user %s — possible data inconsistency", user_id)
            return {"status": "roadmap_completed"}

        # Find the raw milestone dict for this order
        current_milestone_dict = next(
            (m for m in roadmap.milestones if m["order"] == target_order),
            None,
        )
        if current_milestone_dict is None:
            logger.error("Milestone dict missing for order %d", target_order)
            return {"status": "roadmap_completed"}

        current_milestone = MilestoneItem.model_validate(current_milestone_dict)

        # 4. Compute deterministic difficulty
        # Skill modifier uses only current milestone's target_skills (fallback: all skills)
        profile = roadmap.profile_snapshot
        structured_skills = profile.get("structured_skills", [])

        target_skill_names = {s.lower() for s in current_milestone.target_skills}
        matching_skills = [
            s.get("proficiency_level", "beginner")
            for s in structured_skills
            if s.get("name", "").lower() in target_skill_names
            or s.get("skill_name", "").lower() in target_skill_names
        ]
        if matching_skills:
            skill_levels = matching_skills
        else:
            skill_levels = [s.get("proficiency_level", "beginner") for s in structured_skills]

        perf_context = self.performance_provider.get_performance_context(evaluated_tasks)

        difficulty = compute_next_difficulty(
            milestone_band=current_milestone.difficulty_band,
            profile_skill_levels=skill_levels,
            performance_context=perf_context,
        )

        # Estimated hours: base on difficulty (2h per difficulty point)
        estimated_hours = float(max(2.0, min(12.0, difficulty * 2.5)))

        # 5. Build previous task context for the prompt
        previous_tasks_context = [
            {
                "title": t.title,
                "skills_targeted": t.skills_targeted,
            }
            for t in sorted(all_tasks, key=lambda t: t.sequence_number)
        ]

        # 6. Call LLM — NO DB write until success
        logger.info(
            "Generating next task for user %s, milestone %d, difficulty %d (remediation=%s)",
            user_id, current_milestone.order, difficulty, is_remediation,
        )
        task_output: LLMTaskOutput = await generate_task_from_llm(
            llm_provider=self.llm_provider,
            milestone=current_milestone,
            difficulty=difficulty,
            estimated_hours=estimated_hours,
            target_role=profile.get("target_role", "Software Engineer"),
            student_skills=structured_skills,
            previous_tasks=previous_tasks_context,
            performance_context=perf_context,
            is_remediation=is_remediation,
            previous_feedback=previous_feedback,
        )

        # 7. Compute next sequence number
        if all_tasks:
            max_seq = max(t.sequence_number for t in all_tasks)
        else:
            max_seq = 0

        new_task = Task(
            id=uuid.uuid4(),
            user_id=user_id,
            roadmap_id=roadmap.id,
            milestone_order=current_milestone.order,
            sequence_number=max_seq + 1,
            title=task_output.title,
            description=task_output.description,
            requirements=task_output.requirements,
            acceptance_criteria=task_output.acceptance_criteria,
            skills_targeted=task_output.skills_targeted,
            difficulty=difficulty,
            estimated_hours=task_output.estimated_hours,
            starter_hint=task_output.starter_hint,
            status=TaskStatus.ASSIGNED,
        )

        # 8. Persist — partial unique index handles concurrent duplicates
        try:
            db.add(new_task)
            await db.commit()
            await db.refresh(new_task)
        except IntegrityError as exc:
            await db.rollback()
            logger.warning(
                "IntegrityError inserting task for user %s (concurrent /tasks/next): %s",
                user_id, exc,
            )
            raise ActiveTaskExistsError(
                "A task was just created by a concurrent request. Refresh to see your current task."
            ) from exc

        logger.info(
            "Created task %s (seq %d, difficulty %d) for user %s in milestone %d",
            new_task.id, new_task.sequence_number, difficulty, user_id, current_milestone.order,
        )

        return {
            "status": "task_assigned",
            "task": TaskResponse.model_validate(new_task),
        }

    async def get_task_by_id(
        self, db: AsyncSession, task_id: uuid.UUID, user_id: uuid.UUID
    ) -> Task:
        """
        Fetch a specific task, ensuring it belongs to the requesting user.

        Raises:
            TaskNotFoundError: If task not found or belongs to another user.
        """
        stmt = select(Task).where(
            and_(Task.id == task_id, Task.user_id == user_id)
        )
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        if task is None:
            raise TaskNotFoundError(f"Task {task_id} not found.")
        return task

    async def get_task_history(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """Get paginated task history for a user."""
        offset = (page - 1) * page_size

        count_stmt = select(func.count(Task.id)).where(Task.user_id == user_id)
        count_result = await db.execute(count_stmt)
        total = count_result.scalar_one()

        stmt = (
            select(Task)
            .where(Task.user_id == user_id)
            .order_by(Task.sequence_number)
            .offset(offset)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        tasks = list(result.scalars().all())

        return {
            "tasks": [TaskResponse.model_validate(t) for t in tasks],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def start_task(
        self, db: AsyncSession, task_id: uuid.UUID, user_id: uuid.UUID
    ) -> Task:
        """Transition task from ASSIGNED to IN_PROGRESS and record started_at."""
        task = await self.get_task_by_id(db, task_id, user_id)
        self.state_machine.transition(task, TaskStatus.IN_PROGRESS)
        task.started_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(task)
        return task

    async def submit_task(
        self,
        db: AsyncSession,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        github_repo_url: str,
    ) -> Task:
        """
        Transition task from IN_PROGRESS or SUBMITTED to SUBMITTED with GitHub URL.

        Re-submission of the GitHub URL is allowed only in SUBMITTED, never in EVALUATING.
        Enforces unique GitHub repo URL per user — returns DuplicateRepoUrlError on collision.
        """
        task = await self.get_task_by_id(db, task_id, user_id)

        # Explicit requirement: re-submission allowed only in SUBMITTED, never in EVALUATING
        if task.status == TaskStatus.EVALUATING:
            raise TaskTransitionError(task.status, TaskStatus.SUBMITTED)

        if task.status not in (TaskStatus.IN_PROGRESS, TaskStatus.SUBMITTED):
            raise TaskTransitionError(task.status, TaskStatus.SUBMITTED)

        # Check for duplicate repo URL across other tasks of this user
        dup_stmt = select(Task).where(
            and_(
                Task.user_id == user_id,
                Task.github_repo_url == github_repo_url,
                Task.id != task_id,
            )
        )
        dup_result = await db.execute(dup_stmt)
        if dup_result.scalar_one_or_none() is not None:
            raise DuplicateRepoUrlError(
                f"Repository '{github_repo_url}' has already been submitted for another task."
            )

        self.state_machine.transition(task, TaskStatus.SUBMITTED)

        old_url = task.github_repo_url
        task.github_repo_url = github_repo_url
        task.submitted_at = datetime.now(timezone.utc)

        if old_url and old_url != github_repo_url:
            logger.info(
                "Task %s re-submitted with new URL by user %s. Old: %s -> New: %s",
                task_id, user_id, old_url, github_repo_url,
            )

        try:
            await db.commit()
            await db.refresh(task)
            return task
        except IntegrityError as exc:
            await db.rollback()
            raise DuplicateRepoUrlError(
                f"Repository '{github_repo_url}' has already been submitted for another task."
            ) from exc

    async def claim_evaluation(
        self, db: AsyncSession, task_id: uuid.UUID
    ) -> Task:
        """
        Claim task for evaluation (SUBMITTED -> EVALUATING).
        Service-to-service call protected by X-Internal-Token.
        """
        stmt = select(Task).where(Task.id == task_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        if task is None:
            raise TaskNotFoundError(f"Task {task_id} not found.")

        self.state_machine.transition(task, TaskStatus.EVALUATING)
        await db.commit()
        await db.refresh(task)
        logger.info("Task %s claimed for evaluation (status: EVALUATING)", task_id)
        return task

    async def fail_evaluation(
        self, db: AsyncSession, task_id: uuid.UUID
    ) -> Task:
        """
        Rollback task on evaluation failure (EVALUATING -> SUBMITTED).
        Service-to-service call protected by X-Internal-Token.
        """
        stmt = select(Task).where(Task.id == task_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        if task is None:
            raise TaskNotFoundError(f"Task {task_id} not found.")

        self.state_machine.transition(task, TaskStatus.SUBMITTED)
        await db.commit()
        await db.refresh(task)
        logger.info("Task %s evaluation failed, returned to SUBMITTED", task_id)
        return task

    async def apply_evaluation(
        self,
        db: AsyncSession,
        task_id: uuid.UUID,
        evaluation_summary: dict[str, Any],
    ) -> Task:
        """
        Apply evaluation result from Agent 3 (internal endpoint).

        Fetches task without user ownership check (internal call).
        Transitions EVALUATING -> EVALUATED (or SUBMITTED -> EVALUATING -> EVALUATED).
        Enforces score (0-100) and passed (bool, default threshold PASS_SCORE).
        """
        stmt = select(Task).where(Task.id == task_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        if task is None:
            raise TaskNotFoundError(f"Task {task_id} not found.")

        # Ensure pass/fail semantics (Item 4)
        raw_score = evaluation_summary.get("score", 0.0)
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            score = 0.0
        score = max(0.0, min(100.0, score))
        evaluation_summary["score"] = score

        if "passed" not in evaluation_summary or evaluation_summary["passed"] is None:
            evaluation_summary["passed"] = score >= settings.PASS_SCORE
        else:
            evaluation_summary["passed"] = bool(evaluation_summary["passed"])

        # State transition: SUBMITTED -> EVALUATING -> EVALUATED
        if task.status == TaskStatus.SUBMITTED:
            self.state_machine.transition(task, TaskStatus.EVALUATING)
            self.state_machine.transition(task, TaskStatus.EVALUATED)
        else:
            self.state_machine.transition(task, TaskStatus.EVALUATED)

        task.evaluation_summary = evaluation_summary
        task.evaluated_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(task)
        logger.info(
            "Task %s evaluated: score=%.1f, passed=%s",
            task_id, score, evaluation_summary["passed"],
        )
        return task
