"""
backend/app/services/skill_gap.py
====================================
AI Skill Gap Analyzer service.

What this module does
---------------------
``SkillGapService`` analyses a learner's completed skills against the ordered
learning path of a chosen profession and returns a rich ``SkillGapAnalysis``
payload — covering career readiness, completed/missing skills, the single
highest-priority next skill, and an estimated completion time.

Architecture role
-----------------
This is a **pure analysis service** — it performs **no writes**.  Every
database read is issued through focused, efficient SQLAlchemy queries that
collect exactly the data needed in a minimal number of round-trips:

  Round-trip 1 — Validate user exists (session.get).
  Round-trip 2 — Validate profession exists (session.get).
  Round-trip 3 — Fetch all LearningPath rows for the profession, joined
                 to their Skill, ordered by sequence ASC.
  Round-trip 4 — Fetch all UserProgress rows for this user × the set of
                 skill IDs found in round-trip 3.

Total: **4 SQL statements** per analysis request — O(1) in number of
queries regardless of path length.

Layer rules enforced here:
  • No FastAPI imports at module scope.
  • No Pydantic imports beyond the schema types.
  • Raises ``SkillGapError`` for all business-rule violations.
  • Performs zero writes — no commit, no flush.

Analysis algorithm
------------------
1. Load the profession's ordered LearningPath rows (sequence ASC).
   These define WHAT skills are required and in what ORDER.

2. Load the user's UserProgress rows for exactly those skill_ids.
   Build a lookup dict ``{skill_id: UserProgress}``.

3. For each LearningPath step, classify the skill into:
   - COMPLETED   → UserProgress.status == 'COMPLETED'
   - IN_PROGRESS → UserProgress.status == 'IN_PROGRESS'
   - NOT_STARTED → no progress record  OR  status == 'NOT_STARTED'

4. ``career_readiness_percentage`` = (completed required skills
   / total required skills) × 100.  Optional skills are excluded from
   the percentage so the metric reflects true career readiness.

5. ``recommended_next_skill`` = the first required skill that is NOT
   completed, ordered by sequence.  This deliberately picks the earliest
   in-progress skill before any not-started skill so the learner finishes
   what they have already begun.

6. ``estimated_completion_time`` = sum of estimated_weeks for all
   required skills that are not yet completed.

7. ``analysis_note`` = a contextual message that reflects the learner's
   current state (all complete / good progress / just starting).
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.learning_path import LearningPath
from app.models.profession import Profession
from app.models.skill import Skill
from app.models.user import User
from app.models.user_progress import UserProgress
from app.schemas.skill_gap import SkillGapAnalysis, SkillSummary

logger: logging.Logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Domain exception
# ─────────────────────────────────────────────────────────────────────────────


class SkillGapError(Exception):
    """Business-rule violation raised by ``SkillGapService``.

    The HTTP router maps these to ``HTTPException`` via a lookup table.

    Attributes:
        message: Safe, user-facing description.
        code: Machine-readable snake_case code for HTTP status mapping.

    Code constants:
        ``USER_NOT_FOUND``       — user UUID does not exist.
        ``PROFESSION_NOT_FOUND`` — profession UUID does not exist.
        ``NO_LEARNING_PATH``     — the profession has no learning path defined.
    """

    USER_NOT_FOUND: str = "user_not_found"
    PROFESSION_NOT_FOUND: str = "profession_not_found"
    NO_LEARNING_PATH: str = "no_learning_path"

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code

    def __repr__(self) -> str:
        return f"SkillGapError(code={self.code!r}, message={self.message!r})"


# ─────────────────────────────────────────────────────────────────────────────
# Internal data-holder
# ─────────────────────────────────────────────────────────────────────────────


class _PathEntry:
    """Internal value object coupling a LearningPath step to its Skill.

    Used only within this service to avoid raw tuple unpacking across
    multiple methods.

    Args:
        lp: The ``LearningPath`` ORM instance.
        skill: The associated ``Skill`` ORM instance.
        progress: The ``UserProgress`` for this (user, skill) pair, or
            ``None`` if no record exists.
    """

    __slots__ = ("lp", "skill", "progress")

    def __init__(
        self,
        lp: LearningPath,
        skill: Skill,
        progress: Optional[UserProgress],
    ) -> None:
        self.lp = lp
        self.skill = skill
        self.progress = progress

    @property
    def status(self) -> str:
        """Return the learner's status for this skill.

        Returns:
            ``'COMPLETED'`` / ``'IN_PROGRESS'`` / ``'NOT_STARTED'``.
        """
        if self.progress is None:
            return "NOT_STARTED"
        return self.progress.status

    @property
    def progress_percentage(self) -> int:
        """Return the learner's completion percentage for this skill.

        Returns:
            Integer 0–100; ``0`` if no progress record exists.
        """
        if self.progress is None:
            return 0
        return self.progress.progress_percentage

    def is_completed(self) -> bool:
        """Return ``True`` if this skill's status is ``'COMPLETED'``."""
        return self.status == "COMPLETED"

    def to_skill_summary(self) -> SkillSummary:
        """Serialise this entry to a ``SkillSummary`` schema object.

        Returns:
            A fully populated ``SkillSummary`` instance.
        """
        return SkillSummary(
            id=self.skill.id,
            name=self.skill.name,
            difficulty=self.skill.difficulty,
            category=self.skill.category,
            sequence=self.lp.sequence,
            estimated_weeks=self.lp.estimated_weeks,
            is_required=self.lp.is_required,
            progress_percentage=self.progress_percentage,
            status=self.status,
        )


# ─────────────────────────────────────────────────────────────────────────────
# SkillGapService
# ─────────────────────────────────────────────────────────────────────────────


class SkillGapService:
    """Analyses a learner's skill gap against a target profession.

    Performs zero writes — every operation is a read-only analysis.
    Uses exactly 4 SQL round-trips per request regardless of the size of
    the learning path.

    Args:
        session: An active SQLAlchemy ``Session``.  Caller owns lifecycle.

    Example::

        svc = SkillGapService(db)
        analysis = svc.analyse(user_id=uid, profession_id=pid)
    """

    def __init__(self, session: Session) -> None:
        self._db = session

    # ── Private DB helpers (each = one SQL round-trip) ────────────────────── #

    def _load_user(self, user_id: uuid.UUID) -> User:
        """Load the User by PK or raise ``SkillGapError(USER_NOT_FOUND)``.

        Args:
            user_id: UUID of the user to load.

        Returns:
            The ``User`` ORM instance.

        Raises:
            SkillGapError: With code ``USER_NOT_FOUND`` if missing.
        """
        user = self._db.get(User, user_id)
        if user is None:
            raise SkillGapError(
                f"User with id '{user_id}' was not found.",
                code=SkillGapError.USER_NOT_FOUND,
            )
        return user

    def _load_profession(self, profession_id: uuid.UUID) -> Profession:
        """Load the Profession by PK or raise ``SkillGapError(PROFESSION_NOT_FOUND)``.

        Args:
            profession_id: UUID of the profession to load.

        Returns:
            The ``Profession`` ORM instance.

        Raises:
            SkillGapError: With code ``PROFESSION_NOT_FOUND`` if missing.
        """
        profession = self._db.get(Profession, profession_id)
        if profession is None:
            raise SkillGapError(
                f"Profession with id '{profession_id}' was not found.",
                code=SkillGapError.PROFESSION_NOT_FOUND,
            )
        return profession

    def _load_learning_path(
        self,
        profession_id: uuid.UUID,
    ) -> list[tuple[LearningPath, Skill]]:
        """Load all LearningPath rows for the profession, joined to Skill.

        Results are ordered by ``sequence`` ascending — the canonical study
        order.  A single JOIN query avoids N+1 lazy-load issues.

        Args:
            profession_id: UUID of the profession.

        Returns:
            List of ``(LearningPath, Skill)`` tuples ordered by sequence.

        Raises:
            SkillGapError: With code ``NO_LEARNING_PATH`` if the profession
                has no LearningPath entries.
        """
        stmt = (
            select(LearningPath, Skill)
            .join(Skill, LearningPath.skill_id == Skill.id)
            .where(LearningPath.profession_id == profession_id)
            .order_by(LearningPath.sequence.asc())
        )
        rows: list[tuple[LearningPath, Skill]] = (
            self._db.execute(stmt).all()  # type: ignore[assignment]
        )
        if not rows:
            raise SkillGapError(
                f"Profession '{profession_id}' has no learning path defined. "
                "Please add skills to the learning path before running gap analysis.",
                code=SkillGapError.NO_LEARNING_PATH,
            )
        return rows

    def _load_user_progress_map(
        self,
        user_id: uuid.UUID,
        skill_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, UserProgress]:
        """Load UserProgress rows for the user × given skill IDs.

        Single IN-query; returns a dict for O(1) lookup per skill.

        Args:
            user_id: UUID of the user.
            skill_ids: Exact set of skill UUIDs to fetch progress for.

        Returns:
            Dict mapping ``skill_id`` → ``UserProgress`` for records that
            exist.  Skills with no progress record are absent from the dict.
        """
        if not skill_ids:
            return {}

        stmt = (
            select(UserProgress)
            .where(UserProgress.user_id == user_id)
            .where(UserProgress.skill_id.in_(skill_ids))
        )
        rows: list[UserProgress] = list(
            self._db.execute(stmt).scalars().all()
        )
        return {row.skill_id: row for row in rows}

    # ── Private analysis helpers ──────────────────────────────────────────── #

    @staticmethod
    def _compute_readiness(
        entries: list[_PathEntry],
    ) -> tuple[int, int, float]:
        """Compute career readiness metrics over required skills only.

        Readiness is deliberately scoped to **required** skills so that
        optional enrichment material does not dilute the completion percentage.

        Args:
            entries: All path entries (required + optional).

        Returns:
            Tuple of ``(completed_required, total_required, readiness_pct)``
            where ``readiness_pct`` is 0.0–100.0.
        """
        required = [e for e in entries if e.lp.is_required]
        total = len(required)
        if total == 0:
            return 0, 0, 0.0
        completed = sum(1 for e in required if e.is_completed())
        pct = round((completed / total) * 100, 2)
        return completed, total, pct

    @staticmethod
    def _find_recommended(
        entries: list[_PathEntry],
    ) -> Optional[_PathEntry]:
        """Identify the single highest-priority next skill.

        Algorithm:
          1. From required, incomplete skills (ordered by sequence), prefer
             ``IN_PROGRESS`` over ``NOT_STARTED`` — finish what is started.
          2. If no in-progress skill exists, return the first ``NOT_STARTED``
             required skill.
          3. Return ``None`` if all required skills are complete.

        Args:
            entries: All path entries ordered by sequence ascending.

        Returns:
            The recommended ``_PathEntry``, or ``None``.
        """
        required_incomplete = [
            e for e in entries
            if e.lp.is_required and not e.is_completed()
        ]
        if not required_incomplete:
            return None

        # Prefer in-progress (pick lowest sequence among them)
        in_progress = [
            e for e in required_incomplete if e.status == "IN_PROGRESS"
        ]
        if in_progress:
            return in_progress[0]  # already sequence-ordered

        # Fall back to first not-started
        return required_incomplete[0]

    @staticmethod
    def _compute_remaining_weeks(
        entries: list[_PathEntry],
    ) -> int:
        """Sum estimated_weeks for all required, incomplete skills.

        Args:
            entries: All path entries.

        Returns:
            Total weeks remaining as an integer (>= 0).
        """
        return sum(
            e.lp.estimated_weeks
            for e in entries
            if e.lp.is_required and not e.is_completed()
        )

    @staticmethod
    def _build_analysis_note(
        readiness_pct: float,
        recommended: Optional[_PathEntry],
        learner_name: str,
    ) -> str:
        """Compose a personalised, motivational analysis note.

        The note adapts based on the learner's current readiness band:
          - 100%  → congratulations message.
          - 75–99% → nearly there encouragement.
          - 25–74% → keep-going message with next skill.
          - 0–24%  → getting-started message with first skill.

        Args:
            readiness_pct: Career readiness percentage (0.0–100.0).
            recommended: The next recommended ``_PathEntry``, or ``None``.
            learner_name: Display name of the learner for personalisation.

        Returns:
            A short, readable analysis note string.
        """
        first_name = learner_name.split()[0] if learner_name else "Learner"

        if readiness_pct >= 100.0:
            return (
                f"🎉 Congratulations, {first_name}! You have completed all "
                "required skills for this profession. Consider exploring the "
                "optional enrichment skills to deepen your expertise."
            )
        if readiness_pct >= 75.0:
            next_name = recommended.skill.name if recommended else "the final skills"
            return (
                f"🔥 Almost there, {first_name}! You're {readiness_pct:.1f}% "
                f"career-ready. Focus on '{next_name}' to push over the finish line."
            )
        if readiness_pct >= 25.0:
            next_name = recommended.skill.name if recommended else "the next skill"
            return (
                f"📈 Great progress, {first_name}! You're {readiness_pct:.1f}% "
                f"career-ready. Your next recommended skill is '{next_name}'."
            )
        # 0–24%
        if recommended:
            return (
                f"🚀 Your career journey begins, {first_name}! "
                f"Start with '{recommended.skill.name}' — "
                "it's the first step in your learning path."
            )
        return (
            f"🚀 Welcome, {first_name}! Begin your career journey by "
            "exploring the skills in the learning path."
        )

    @staticmethod
    def _format_weeks(weeks: int) -> str:
        """Format a week count as a human-readable string.

        Args:
            weeks: Integer number of weeks.

        Returns:
            E.g. ``"1 week"``, ``"14 weeks"``, ``"0 weeks"``.
        """
        if weeks == 0:
            return "0 weeks"
        if weeks == 1:
            return "1 week"
        return f"{weeks} weeks"

    # ── Public interface ──────────────────────────────────────────────────── #

    def analyse(
        self,
        user_id: uuid.UUID,
        profession_id: uuid.UUID,
    ) -> SkillGapAnalysis:
        """Run the full skill gap analysis for a learner against a profession.

        Workflow (4 DB round-trips):
            1. Validate user exists.
            2. Validate profession exists.
            3. Load the profession's ordered LearningPath + Skill rows (JOIN).
            4. Load the user's UserProgress rows for those skill IDs (IN query).

        Then classify each skill, compute metrics, and assemble the response.

        Args:
            user_id: UUID of the learner to analyse.
            profession_id: UUID of the target profession.

        Returns:
            A fully populated ``SkillGapAnalysis`` schema instance.

        Raises:
            SkillGapError: ``USER_NOT_FOUND`` if the user UUID is invalid.
            SkillGapError: ``PROFESSION_NOT_FOUND`` if the profession UUID
                is invalid.
            SkillGapError: ``NO_LEARNING_PATH`` if the profession has no
                LearningPath entries.

        Example::

            svc = SkillGapService(db)
            result = svc.analyse(user_id=uid, profession_id=pid)
            print(result.career_readiness_percentage)
        """
        logger.info(
            "analyse | user_id=%s | profession_id=%s", user_id, profession_id
        )

        # ── Round-trip 1: validate user ───────────────────────────────────── #
        user = self._load_user(user_id)

        # ── Round-trip 2: validate profession ────────────────────────────── #
        profession = self._load_profession(profession_id)

        # ── Round-trip 3: load ordered learning path (JOIN) ──────────────── #
        lp_rows: list[tuple[LearningPath, Skill]] = self._load_learning_path(
            profession_id
        )

        skill_ids: list[uuid.UUID] = [skill.id for _, skill in lp_rows]

        # ── Round-trip 4: load user progress for these skills (IN query) ─── #
        progress_map: dict[uuid.UUID, UserProgress] = (
            self._load_user_progress_map(user_id, skill_ids)
        )

        # ── Build _PathEntry list (in-memory, O(n)) ───────────────────────── #
        entries: list[_PathEntry] = [
            _PathEntry(
                lp=lp,
                skill=skill,
                progress=progress_map.get(skill.id),
            )
            for lp, skill in lp_rows
        ]

        # ── Classify skills ───────────────────────────────────────────────── #
        completed_entries: list[_PathEntry] = []
        in_progress_entries: list[_PathEntry] = []
        missing_entries: list[_PathEntry] = []

        for entry in entries:
            if entry.status == "COMPLETED":
                completed_entries.append(entry)
            elif entry.status == "IN_PROGRESS":
                in_progress_entries.append(entry)
            else:
                missing_entries.append(entry)

        # ── Compute metrics ───────────────────────────────────────────────── #
        completed_required, total_required, readiness_pct = (
            self._compute_readiness(entries)
        )
        recommended = self._find_recommended(entries)
        remaining_weeks = self._compute_remaining_weeks(entries)

        # ── Assemble response ─────────────────────────────────────────────── #
        analysis = SkillGapAnalysis(
            user_id=user_id,
            profession_id=profession_id,
            profession_name=profession.name,
            total_required_skills=total_required,
            total_path_skills=len(entries),
            career_readiness_percentage=readiness_pct,
            completed_skills=[e.to_skill_summary() for e in completed_entries],
            in_progress_skills=[e.to_skill_summary() for e in in_progress_entries],
            missing_skills=[e.to_skill_summary() for e in missing_entries],
            recommended_next_skill=(
                recommended.to_skill_summary() if recommended else None
            ),
            estimated_completion_time=self._format_weeks(remaining_weeks),
            completed_required_skills=completed_required,
            analysis_note=self._build_analysis_note(
                readiness_pct, recommended, user.full_name
            ),
        )

        logger.info(
            "analyse complete | user_id=%s | profession_id=%s"
            " | readiness=%.1f%% | completed=%d/%d | remaining=%s",
            user_id, profession_id, readiness_pct,
            completed_required, total_required,
            self._format_weeks(remaining_weeks),
        )
        return analysis
