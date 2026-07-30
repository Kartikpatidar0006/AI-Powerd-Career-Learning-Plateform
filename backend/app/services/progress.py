"""
backend/app/services/progress.py
=================================
Business-logic service layer for the Progress Engine.

What this module does
---------------------
Provides ``ProgressService`` to orchestrate user progression:
  1. Evaluating task & interview milestone completion.
  2. Updating ``UserProgress`` records (completed_tasks, completed_interviews,
     progress_percentage, current_step_id).
  3. Unlocking subsequent tasks/steps when score >= 70.
  4. Automatically generating notifications for success or retry reminders.
  5. Calculating platform overall and roadmap-specific progress metrics.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.career_roadmap import CareerRoadmap, RoadmapStep
from app.models.interview import Interview
from app.models.skill import Skill
from app.models.task import Task, TaskSubmission
from app.models.user_progress import UserProgress
from app.repositories.user_progress import UserProgressRepository
from app.schemas.progress import RoadmapProgressResponse, UserOverallProgressResponse
from app.services.notification import NotificationService

logger: logging.Logger = logging.getLogger(__name__)


class ProgressError(Exception):
    """Business-rule violation raised by ProgressService.

    Code constants:
        ``NOT_FOUND``    — entity not found.
        ``UNAUTHORIZED`` — unauthorized access.
    """

    NOT_FOUND: str = "not_found"
    UNAUTHORIZED: str = "unauthorized"

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code

    def __repr__(self) -> str:
        return f"ProgressError(code={self.code!r}, message={self.message!r})"


class ProgressService:
    """Service managing learner progress calculations, milestone unlocks, and notifications.

    Args:
        db: An active SQLAlchemy ``Session``.
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._progress_repo = UserProgressRepository(db)
        self._notification_svc = NotificationService(db)

    # =========================================================================
    #  Automated Progress Engine Update
    # =========================================================================

    def process_evaluation_result(
        self,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
        overall_score: int,
    ) -> None:
        """Process evaluation score and update progress engine state.

        Business Rules:
          When score >= 70:
            - Mark current task completed
            - Update completed_tasks count
            - Update completed_interviews count
            - Calculate progress_percentage
            - Unlock next task / update current_step_id if required
            - Create success notification

          When score < 70:
            - Do not unlock next task
            - Create retry reminder notification

        Args:
            user_id: UUID of user.
            task_id: UUID of task.
            overall_score: Integer evaluation score (0-100).
        """
        task = self._db.get(Task, task_id)
        if task is None:
            logger.warning("process_evaluation_result | Task %s not found", task_id)
            return

        step = self._db.get(RoadmapStep, task.roadmap_step_id) if task.roadmap_step_id else None

        if overall_score >= 70:
            # 1. Fetch or create UserProgress for the step's skill
            skill_id = step.skill_id if step else None
            if skill_id:
                prog = self._progress_repo.get_by_user_and_skill(user_id, skill_id)
                if prog is None:
                    prog = UserProgress(
                        user_id=user_id,
                        skill_id=skill_id,
                        status="IN_PROGRESS",
                        progress_percentage=0,
                        completed_tasks=1,
                        completed_interviews=1,
                    )
                    self._db.add(prog)
                else:
                    prog.completed_tasks += 1
                    prog.completed_interviews += 1
                    prog.status = "IN_PROGRESS"

                # Calculate progress percentage for this skill based on step tasks
                total_tasks_stmt = (
                    select(func.count(Task.id))
                    .join(RoadmapStep, Task.roadmap_step_id == RoadmapStep.id)
                    .where(RoadmapStep.skill_id == skill_id)
                )
                total_skill_tasks = self._db.execute(total_tasks_stmt).scalar() or 1
                new_pct = min(100, int((prog.completed_tasks / total_skill_tasks) * 100))
                prog.progress_percentage = new_pct
                if new_pct >= 100:
                    prog.status = "COMPLETED"

                # Update current_step_id
                if step:
                    prog.current_step_id = step.id

                self._db.flush()

            self._db.commit()

            # 2. Trigger notification for success & unlocked next step
            self._notification_svc.create_notification(
                user_id=user_id,
                title="Task & Interview Passed! 🎉",
                message=(
                    f"Congratulations! You scored {overall_score}% on '{task.title}'. "
                    "Your progress has been updated and the next step is unlocked."
                ),
                type_="Progress",
            )
            logger.info("Processed passing score (%d%%) for user=%s task=%s", overall_score, user_id, task_id)

        else:
            # Score < 70 — Do not unlock next task, send retry reminder notification
            self._notification_svc.create_notification(
                user_id=user_id,
                title="Evaluation Score Update",
                message=(
                    f"Your score for '{task.title}' was {overall_score}%. "
                    "A minimum score of 70% is required to unlock the next task. Keep practicing and try again!"
                ),
                type_="Reminder",
            )
            logger.info("Processed failing score (%d%%) for user=%s task=%s", overall_score, user_id, task_id)

    # =========================================================================
    #  Read Progress APIs
    # =========================================================================

    def get_user_overall_progress(self, user_id: uuid.UUID) -> UserOverallProgressResponse:
        """Calculate overall platform progress for a user.

        Args:
            user_id: UUID of user.

        Returns:
            ``UserOverallProgressResponse``.
        """
        # Count total submissions & completed interviews
        completed_tasks_stmt = (
            select(func.count(TaskSubmission.id))
            .where(TaskSubmission.user_id == user_id)
            .where(TaskSubmission.status == "Reviewed")
        )
        completed_tasks = self._db.execute(completed_tasks_stmt).scalar() or 0

        completed_interviews_stmt = (
            select(func.count(Interview.id))
            .where(Interview.user_id == user_id)
            .where(Interview.status == "Completed")
        )
        completed_interviews = self._db.execute(completed_interviews_stmt).scalar() or 0

        # Skill progress counts
        completed_skills_stmt = (
            select(func.count(UserProgress.id))
            .where(UserProgress.user_id == user_id)
            .where(UserProgress.status == "COMPLETED")
        )
        total_skills_completed = self._db.execute(completed_skills_stmt).scalar() or 0

        in_progress_skills_stmt = (
            select(func.count(UserProgress.id))
            .where(UserProgress.user_id == user_id)
            .where(UserProgress.status == "IN_PROGRESS")
        )
        total_skills_in_progress = self._db.execute(in_progress_skills_stmt).scalar() or 0

        # Calculate overall percentage
        all_skills_stmt = select(func.count(Skill.id))
        total_skills = self._db.execute(all_skills_stmt).scalar() or 1

        avg_pct_stmt = (
            select(func.avg(UserProgress.progress_percentage))
            .where(UserProgress.user_id == user_id)
        )
        avg_pct = self._db.execute(avg_pct_stmt).scalar() or 0.0

        return UserOverallProgressResponse(
            user_id=user_id,
            completed_tasks=completed_tasks,
            completed_interviews=completed_interviews,
            total_skills_completed=total_skills_completed,
            total_skills_in_progress=total_skills_in_progress,
            overall_progress_percentage=round(float(avg_pct), 2),
        )

    def get_roadmap_progress(
        self,
        user_id: uuid.UUID,
        roadmap_id: uuid.UUID,
    ) -> RoadmapProgressResponse:
        """Calculate detailed progress metrics for a specific career roadmap.

        Args:
            user_id: UUID of user.
            roadmap_id: UUID of CareerRoadmap.

        Returns:
            ``RoadmapProgressResponse``.

        Raises:
            ProgressError: NOT_FOUND if roadmap missing.
        """
        roadmap = self._db.get(CareerRoadmap, roadmap_id)
        if roadmap is None:
            raise ProgressError(
                f"Career roadmap with id '{roadmap_id}' not found.",
                code=ProgressError.NOT_FOUND,
            )

        # Fetch roadmap steps
        steps_stmt = select(RoadmapStep).where(RoadmapStep.roadmap_id == roadmap_id).order_by(RoadmapStep.step_order.asc())
        steps = list(self._db.execute(steps_stmt).scalars().all())
        total_steps = len(steps)

        if total_steps == 0:
            return RoadmapProgressResponse(
                roadmap_id=roadmap_id,
                roadmap_title=roadmap.title,
                current_step_id=None,
                completed_steps=0,
                total_steps=0,
                completed_tasks=0,
                total_tasks=0,
                progress_percentage=0.0,
                status="NOT_STARTED",
            )

        step_ids = [s.id for s in steps]

        # Total tasks under roadmap
        tasks_stmt = select(Task).where(Task.roadmap_step_id.in_(step_ids))
        all_tasks = list(self._db.execute(tasks_stmt).scalars().all())
        total_tasks = len(all_tasks)

        # Completed tasks by user under roadmap
        completed_tasks_count = 0
        if total_tasks > 0:
            task_ids = [t.id for t in all_tasks]
            comp_tasks_stmt = (
                select(func.count(TaskSubmission.id))
                .where(TaskSubmission.user_id == user_id)
                .where(TaskSubmission.task_id.in_(task_ids))
                .where(TaskSubmission.status == "Reviewed")
            )
            completed_tasks_count = self._db.execute(comp_tasks_stmt).scalar() or 0

        # Calculate completed steps (step completed if all its tasks completed or user progress completed)
        completed_steps_count = 0
        current_step_id = steps[0].id if steps else None

        for s in steps:
            # Check user progress for skill
            prog = self._progress_repo.get_by_user_and_skill(user_id, s.skill_id)
            if prog and prog.status == "COMPLETED":
                completed_steps_count += 1
            elif prog and prog.status == "IN_PROGRESS":
                current_step_id = s.id

        progress_pct = (
            round((completed_tasks_count / total_tasks) * 100.0, 2)
            if total_tasks > 0
            else round((completed_steps_count / total_steps) * 100.0, 2)
        )

        status_str = "NOT_STARTED"
        if progress_pct >= 100.0:
            status_str = "COMPLETED"
        elif progress_pct > 0.0 or completed_tasks_count > 0:
            status_str = "IN_PROGRESS"

        return RoadmapProgressResponse(
            roadmap_id=roadmap_id,
            roadmap_title=roadmap.title,
            current_step_id=current_step_id,
            completed_steps=completed_steps_count,
            total_steps=total_steps,
            completed_tasks=completed_tasks_count,
            total_tasks=total_tasks,
            progress_percentage=min(100.0, progress_pct),
            status=status_str,
        )
