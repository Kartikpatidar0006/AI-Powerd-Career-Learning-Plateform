"""
EvaluatorService — Main evaluation pipeline orchestrator.

Lifecycle:
1. Receive trigger (task_id, user_id, github_repo_url, skills_targeted, task_started_at)
2. Create Evaluation row with status=IN_PROGRESS
3. Claim task from roadmap-agent-service (SUBMITTED -> EVALUATING)
4. Fetch GitHub data (metadata, file tree, README, source files, commits)
5. Run deterministic checks (pure, no LLM)
6. If gate fails: mark FAILED, rollback task, done
7. Run LLM code review (only if deterministic gate passed)
8. Apply cap rule and compose final score
9. Generate feedback_summary
10. Write COMPLETED row, post result to roadmap-agent-service
11. On any unexpected error: mark FAILED, rollback task, do NOT leak stack trace

Idempotency: Concurrent triggers for the same task while one is IN_PROGRESS return 409.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.llm.base import BaseLLMProvider, LLMValidationError
from app.models.evaluation import Evaluation, EvaluationStatus
from app.schemas.evaluation import (
    CheckResult,
    CommitInfo,
    RepoSnapshot,
    TriggerEvaluationRequest,
)
from app.services.checks import (
    GateFailure,
    check_basic_lint_score,
    check_commits_after_task_start,
    check_minimum_commit_count,
    check_no_giant_single_commit_dump,
    check_readme_present,
    check_relevant_files_present,
    check_repo_exists_and_public,
    compute_deterministic_score,
    _detect_primary_language,
)
from app.services.github_client import (
    GitHubClient,
    GitHubAPIError,
    GitHubPrivateRepoError,
    GitHubRateLimitError,
    GitHubRepoNotFoundError,
    parse_github_url,
)
from app.services.llm_reviewer import (
    apply_integrity_gates,
    apply_llm_score_cap,
    compute_final_score,
    generate_feedback_summary,
    run_llm_review,
)
from app.services.roadmap_client import RoadmapClient, TaskStateConflictError

logger = logging.getLogger("evaluator-agent.service")


class EvaluationInProgressError(Exception):
    """Raised when an evaluation for this task is already IN_PROGRESS (idempotency guard)."""
    pass


class EvaluatorService:
    """
    Orchestrates the complete evaluation pipeline for a submitted task.

    Thread safety: Each FastAPI request gets its own service instance.
    The evaluation is run as a background task — the HTTP endpoint returns
    immediately while this runs asynchronously.
    """

    def __init__(self, llm_provider: BaseLLMProvider) -> None:
        self._llm = llm_provider
        self._roadmap_client = RoadmapClient()

    # ── Public API ────────────────────────────────────────────────────────

    async def trigger_evaluation(
        self,
        db: AsyncSession,
        request: TriggerEvaluationRequest,
    ) -> Evaluation:
        """
        Start an evaluation for a submitted task.

        Idempotent-safe: If an evaluation for this task is already IN_PROGRESS,
        raises EvaluationInProgressError (caller returns 409).

        Args:
            db: Async database session.
            request: Evaluation trigger request.

        Returns:
            Newly created Evaluation ORM object (status=IN_PROGRESS).

        Raises:
            EvaluationInProgressError: If already running.
        """
        # Check idempotency: is there already an IN_PROGRESS evaluation for this task?
        existing = await db.execute(
            select(Evaluation).where(
                and_(
                    Evaluation.task_id == request.task_id,
                    Evaluation.status == EvaluationStatus.IN_PROGRESS.value,
                )
            )
        )
        if existing.scalars().first() is not None:
            raise EvaluationInProgressError(
                f"Evaluation for task {request.task_id} is already in progress."
            )

        # Create evaluation record
        evaluation = Evaluation(
            task_id=request.task_id,
            user_id=request.user_id,
            github_repo_url=request.github_repo_url,
            status=EvaluationStatus.IN_PROGRESS.value,
        )
        db.add(evaluation)
        await db.flush()  # Get the ID without committing
        logger.info(
            "Created evaluation %s for task %s (user %s)",
            evaluation.id, request.task_id, request.user_id,
        )
        return evaluation

    async def run_full_pipeline(
        self,
        evaluation_id: uuid.UUID,
        request: TriggerEvaluationRequest,
        db: AsyncSession | None = None,
    ) -> None:
        """
        Run the complete evaluation pipeline asynchronously.

        Called as a FastAPI BackgroundTask after the trigger endpoint returns.
        Manages its own database session if none is provided.
        Handles ALL errors internally — never leaks exceptions to the caller.
        On any failure: marks evaluation FAILED and rolls back task state.
        """
        if db is not None:
            await self._run_pipeline_with_session(db, evaluation_id, request)
        else:
            from app.db.session import get_session_factory
            factory = get_session_factory()
            async with factory() as session:
                await self._run_pipeline_with_session(session, evaluation_id, request)

    async def _run_pipeline_with_session(
        self,
        db: AsyncSession,
        eval_id: uuid.UUID,
        request: TriggerEvaluationRequest,
    ) -> None:
        """Execute the pipeline steps within an active database session."""
        task_id = request.task_id

        try:
            # Step 1: Claim task in roadmap-agent-service
            try:
                await self._roadmap_client.claim_evaluation(task_id)
                logger.info("Claimed task %s for evaluation (SUBMITTED -> EVALUATING)", task_id)
            except TaskStateConflictError as exc:
                # Task already EVALUATING (race with another evaluator trigger)
                logger.warning("Task %s already claimed: %s. Aborting.", task_id, exc)
                await self._mark_failed(db, eval_id, f"Task already claimed for evaluation: {exc}")
                return
            except Exception as exc:
                logger.error("Failed to claim task %s: %s", task_id, exc)
                await self._mark_failed(db, eval_id, f"Could not claim task for evaluation: {str(exc)[:200]}")
                return

            # Fetch evaluation record within this active session
            result = await db.execute(select(Evaluation).where(Evaluation.id == eval_id))
            evaluation = result.scalars().first()
            if not evaluation:
                logger.error("Evaluation %s not found in DB for task %s", eval_id, task_id)
                return

            # Step 2: Run evaluation
            try:
                await self._execute_evaluation(db, evaluation, request)
            except Exception as exc:
                logger.exception("Evaluation pipeline error for task %s: %s", task_id, exc)
                error_msg = f"Evaluation pipeline encountered an unexpected error: {type(exc).__name__}"
                await self._mark_failed(db, eval_id, error_msg)
                # Roll back task to SUBMITTED so student can re-submit
                try:
                    await self._roadmap_client.fail_evaluation(task_id)
                    logger.info("Rolled back task %s to SUBMITTED after pipeline error", task_id)
                except Exception as rollback_exc:
                    logger.error("Failed to roll back task %s: %s", task_id, rollback_exc)

        except Exception as exc:
            # Outermost safety net — should not normally reach here
            logger.exception("Critical error in evaluation background task for task %s: %s", task_id, exc)

    async def get_latest_evaluation(
        self,
        db: AsyncSession,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Evaluation | None:
        """
        Get the latest evaluation for a task, scoped to the requesting user.

        Authorization: user_id must match evaluation.user_id.
        Returns None if no evaluation exists for this task/user.
        """
        result = await db.execute(
            select(Evaluation)
            .where(
                and_(
                    Evaluation.task_id == task_id,
                    Evaluation.user_id == user_id,
                )
            )
            .order_by(Evaluation.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def get_latest_evaluation_by_task(
        self,
        db: AsyncSession,
        task_id: uuid.UUID,
    ) -> Evaluation | None:
        """
        Get the latest evaluation for a task_id (internal service-to-service).
        """
        result = await db.execute(
            select(Evaluation)
            .where(Evaluation.task_id == task_id)
            .order_by(Evaluation.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    # ── Private Pipeline ─────────────────────────────────────────────────

    async def _execute_evaluation(
        self,
        db: AsyncSession,
        evaluation: Evaluation,
        request: TriggerEvaluationRequest,
    ) -> None:
        """Inner evaluation logic. Any exception propagates to run_full_pipeline."""
        owner, repo = parse_github_url(request.github_repo_url)
        skills = [s for s in request.skills_targeted if isinstance(s, str)][:20]

        # ── GitHub data fetch ─────────────────────────────────────────────
        repo_meta = None
        tree = []
        commits: list[CommitInfo] = []
        readme_content: str | None = None
        file_contents: dict[str, str] = {}
        github_error: str | None = None
        repo_accessible = True

        async with GitHubClient() as github:
            # Fetch metadata first (public/private check)
            try:
                repo_meta = await github.get_repo_metadata(owner, repo)
            except GitHubRepoNotFoundError as exc:
                repo_accessible = False
                github_error = f"Repository not found: {owner}/{repo}. Ensure the URL is correct and the repo is public."
                logger.warning("Repo not found: %s/%s — %s", owner, repo, exc)
            except GitHubPrivateRepoError as exc:
                repo_accessible = False
                github_error = f"Repository {owner}/{repo} is private. Make it public to submit for evaluation."
                logger.warning("Private repo: %s/%s", owner, repo)
            except GitHubRateLimitError as exc:
                repo_accessible = False
                retry_msg = f" (retry after {exc.retry_after}s)" if exc.retry_after else ""
                github_error = f"GitHub API rate limit exceeded{retry_msg}. Evaluation will be retried automatically."
                logger.error("GitHub rate limit hit: %s", exc)
            except GitHubAPIError as exc:
                repo_accessible = False
                github_error = f"GitHub API error: {str(exc)[:200]}"
                logger.error("GitHub API error for %s/%s: %s", owner, repo, exc)

            if repo_accessible and repo_meta:
                branch = repo_meta.default_branch
                # Fetch tree, commits, README, files concurrently
                tree = await github.get_file_tree(owner, repo, branch)
                commits = await github.get_commit_history(owner, repo, branch)
                readme_content = await github.get_readme(owner, repo, branch)
                file_contents = await github.fetch_relevant_files(
                    owner, repo, branch, tree, skills, readme_content
                )

        # ── Deterministic checks ──────────────────────────────────────────
        primary_language = _detect_primary_language(tree)

        # Gate check
        gate = check_repo_exists_and_public(repo_accessible, github_error)

        if not gate.passed:
            # Hard fail — store minimal data, mark FAILED
            evaluation.repo_snapshot = {"error": github_error}
            evaluation.deterministic_checks = [gate.model_dump()]
            evaluation.deterministic_score = 0.0
            evaluation.final_score = 0.0
            evaluation.passed = False
            evaluation.status = EvaluationStatus.FAILED.value
            evaluation.error_detail = github_error
            evaluation.feedback_summary = (
                f"Evaluation could not complete: {github_error} "
                "Please fix the issue and re-submit your task."
            )
            evaluation.completed_at = datetime.now(timezone.utc)
            await db.flush()
            await db.commit()

            # Roll back task so student can re-submit
            try:
                await self._roadmap_client.fail_evaluation(request.task_id)
            except Exception as exc:
                logger.error("Rollback failed for task %s: %s", request.task_id, exc)
            return

        # Remaining checks
        checks: list[CheckResult] = [gate]
        checks.append(check_commits_after_task_start(commits, request.task_started_at))
        checks.append(check_minimum_commit_count(commits))
        checks.append(check_readme_present(readme_content))
        checks.append(check_relevant_files_present(tree, skills))
        checks.append(check_no_giant_single_commit_dump(commits, tree))
        checks.append(check_basic_lint_score(file_contents, primary_language))

        det_score = compute_deterministic_score(checks)

        # Build repo snapshot (audit, no full contents)
        snapshot = RepoSnapshot(
            file_tree_count=len(tree),
            commit_count=len(commits),
            commit_timestamps=[c.timestamp for c in commits[:30]],
            readme_present=readme_content is not None,
            primary_language=primary_language,
            default_branch=repo_meta.default_branch if repo_meta else "main",
            pushed_at=repo_meta.pushed_at if repo_meta else None,
        )

        # ── LLM review ───────────────────────────────────────────────────
        llm_review = None
        llm_score_raw = 0.0
        llm_score_capped = 0.0
        llm_review_dict: dict[str, Any] = {}

        if det_score >= 0:  # Always attempt LLM review if gate passed
            try:
                llm_review = await run_llm_review(
                    llm_provider=self._llm,
                    skills_targeted=skills,
                    file_contents=file_contents,
                    commits=[c.model_dump() for c in commits],
                    deterministic_score=det_score,
                    deterministic_checks=checks,
                )
                llm_score_raw = llm_review.quality_score
                llm_score_capped, was_capped = apply_llm_score_cap(llm_score_raw, det_score)
                llm_review_dict = llm_review.model_dump()

                # Suspicious LLM score detection (injection heuristic)
                if (
                    llm_score_raw >= 99.0
                    and not llm_review.red_flags
                    and det_score < 40.0
                ):
                    logger.warning(
                        "SUSPICIOUS_LLM_SCORE: task=%s det_score=%.1f llm_raw=%.1f "
                        "— possible injection. Cap rule enforced.",
                        request.task_id, det_score, llm_score_raw,
                    )

            except LLMValidationError as exc:
                logger.error("LLM review failed after retry for task %s: %s", request.task_id, exc)
                # Non-fatal: use 0 LLM score, note in feedback
                llm_score_capped = 0.0
                llm_review_dict = {
                    "strengths": [],
                    "weaknesses": ["Automated code review could not be completed."],
                    "suggestions": ["Re-submit to trigger another evaluation attempt."],
                    "red_flags": [],
                    "quality_score": 0,
                }
            except Exception as exc:
                logger.exception("Unexpected LLM error for task %s: %s", request.task_id, exc)
                llm_score_capped = 0.0
                llm_review_dict = {
                    "strengths": [],
                    "weaknesses": ["Automated code review encountered an error."],
                    "suggestions": [],
                    "red_flags": [],
                    "quality_score": 0,
                }

        # ── Final score composition & integrity gates ───────────────────
        raw_final = compute_final_score(det_score, llm_score_capped)
        final, passed, reuse_suspected, single_dump_suspected = apply_integrity_gates(
            raw_final_score=raw_final,
            deterministic_checks=checks,
            pass_threshold=settings.PASS_SCORE,
            cap_score=35.0,
        )

        # Generate student-facing feedback
        feedback = generate_feedback_summary(
            deterministic_score=det_score,
            deterministic_checks=checks,
            llm_review=llm_review or _empty_llm_review(llm_review_dict),
            final_score=final,
            passed=passed,
            pass_score=settings.PASS_SCORE,
            reuse_suspected=reuse_suspected,
            single_dump_suspected=single_dump_suspected,
        )

        # ── Persist completed evaluation ──────────────────────────────────
        evaluation.repo_snapshot = snapshot.model_dump()
        evaluation.deterministic_checks = [c.model_dump() for c in checks]
        evaluation.deterministic_score = det_score
        evaluation.llm_review = llm_review_dict
        evaluation.llm_score = llm_score_capped
        evaluation.final_score = final
        evaluation.passed = passed
        evaluation.reuse_suspected = reuse_suspected
        evaluation.feedback_summary = feedback
        evaluation.status = EvaluationStatus.COMPLETED.value
        evaluation.completed_at = datetime.now(timezone.utc)
        await db.flush()
        await db.commit()

        logger.info(
            "Evaluation %s COMPLETED: task=%s final_score=%.1f passed=%s",
            evaluation.id, request.task_id, final, passed,
        )

        # ── Notify roadmap-agent-service ──────────────────────────────────
        try:
            await self._roadmap_client.post_evaluation_result(
                task_id=request.task_id,
                score=final,
                passed=passed,
                feedback=feedback,
            )
            logger.info("Notified roadmap-agent-service: task %s EVALUATED", request.task_id)
        except Exception as exc:
            # Non-fatal: evaluation row is complete, task remains EVALUATING
            # (ops team would need to reconcile if this happens in production)
            logger.error(
                "Failed to notify roadmap-agent-service for task %s: %s. "
                "Evaluation row is COMPLETED but task may remain EVALUATING.",
                request.task_id, exc,
            )

    async def _mark_failed(
        self,
        db: AsyncSession,
        eval_id: uuid.UUID,
        error_detail: str,
    ) -> None:
        """Mark an evaluation as FAILED with a safe error message."""
        try:
            result = await db.execute(
                select(Evaluation).where(Evaluation.id == eval_id)
            )
            evaluation = result.scalars().first()
            if evaluation:
                evaluation.status = EvaluationStatus.FAILED.value
                evaluation.error_detail = error_detail[:1000]  # Cap length
                evaluation.completed_at = datetime.now(timezone.utc)
                await db.flush()
                await db.commit()
        except Exception as exc:
            logger.error("Failed to mark evaluation %s as FAILED: %s", eval_id, exc)


def _empty_llm_review(review_dict: dict[str, Any]) -> Any:
    """Create a minimal LLMCodeReviewOutput from a dict for feedback generation."""
    from app.schemas.evaluation import LLMCodeReviewOutput
    return LLMCodeReviewOutput(
        strengths=review_dict.get("strengths", []),
        weaknesses=review_dict.get("weaknesses", []),
        suggestions=review_dict.get("suggestions", []),
        red_flags=review_dict.get("red_flags", []),
        quality_score=review_dict.get("quality_score", 0),
    )
