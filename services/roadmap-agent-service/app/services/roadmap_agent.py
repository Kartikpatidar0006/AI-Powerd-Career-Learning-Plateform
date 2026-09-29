"""
Agent 2: Roadmap & Daily Task Generator — Core Logic.

This module encapsulates all prompt engineering, LLM orchestration, structured
schema validation with 1-shot retry, and deterministic difficulty calculation.

Architecture:
- All prompts are defined as module-level constants — testable without the API layer.
- The difficulty function is a pure function — no side effects, fully unit-testable.
- LLM prompting is completely decoupled from HTTP routers and database layers.
"""

import json
import logging
import re
import unicodedata
from typing import Any

from pydantic import ValidationError

from app.core.llm.base import (
    BaseLLMProvider,
    LLMProviderError,
    LLMTimeoutError,
    LLMValidationError,
)
from app.schemas.roadmap import LLMRoadmapOutput, LLMTaskOutput, MilestoneItem

logger = logging.getLogger("roadmap-agent.service")


# ──────────────────────────────────────────────────────────────────────
# LLM Prompt Templates — Roadmap Generation
# ──────────────────────────────────────────────────────────────────────

ROADMAP_SYSTEM_PROMPT = """You are an elite Career Learning Strategist and Technical Curriculum Designer.
Your task is to generate a structured, personalized learning roadmap for a software engineering student.

CRITICAL INSTRUCTIONS:
1. Generate between 4 and 8 milestones ONLY. Fewer than 4 or more than 8 will be rejected.
2. Milestones MUST have contiguous 'order' values starting from 1 (i.e., 1, 2, 3, ...).
3. Each milestone MUST have at least 1 target skill and at least 2 measurable success criteria.
4. difficulty_band must be integers 1 through 5. Difficulty may NEVER increase by more than 1 level between consecutive milestones.
5. Total estimated_days across ALL milestones MUST be between 30 and 120 days.
6. Skills the student already has at 'advanced' proficiency level should NOT be re-taught in early milestones. Focus on gaps and growth areas.
7. Each milestone must teach skills directly relevant to reaching the target_role.
8. Difficulty should progress logically from accessible (1-2) to challenging (4-5) as the roadmap advances.

OUTPUT FORMAT (strict JSON only, no markdown, no commentary):
{
  "milestones": [
    {
      "order": 1,
      "title": "Milestone Title",
      "description": "Clear description of what the student will learn and build.",
      "target_skills": ["Skill 1", "Skill 2"],
      "estimated_days": 10,
      "difficulty_band": 1,
      "success_criteria": [
        "Specific, measurable criterion 1",
        "Specific, measurable criterion 2"
      ]
    }
  ]
}

Output ONLY valid JSON. No markdown blocks, no explanations.
"""

ROADMAP_USER_PROMPT_TEMPLATE = """Generate a personalized learning roadmap for this student:

TARGET ROLE: {target_role}
EXPERIENCE LEVEL: {experience_level}

CURRENT SKILLS (with proficiency levels — do NOT re-teach 'advanced' skills):
{structured_skills}

WEAK AREAS (prioritize these in the roadmap for growth):
{weak_areas}

STRONGEST AREAS (may use these as foundations but don't over-emphasize):
{strong_areas}

STUDENT CONTEXT: The student aims to become a {target_role}. Focus on practical,
real-world skills that directly close the gap between their current abilities and
the requirements of the target role. Skills at 'advanced' level are already mastered;
do not dedicate full milestones to them. Focus on beginner/intermediate gaps
and skills missing entirely from the student's current profile.

Generate the JSON roadmap now.
"""

ROADMAP_RETRY_PROMPT_TEMPLATE = """Your previous roadmap JSON failed validation:

VALIDATION ERRORS:
{validation_errors}

ORIGINAL STUDENT CONTEXT:
TARGET ROLE: {target_role}
EXPERIENCE LEVEL: {experience_level}
SKILLS SUMMARY: {skills_summary}

CRITICAL RULES TO FIX:
- Milestones: exactly 4-8 milestones (you had {milestone_count})
- Orders must be 1, 2, 3, ... N (contiguous, no gaps)
- Each milestone needs at least 1 target_skill and 2 success_criteria
- difficulty_band can increase by AT MOST 1 between consecutive milestones
- Total estimated_days must be 30-120 (your total was {total_days})

Output ONLY corrected valid JSON matching the exact format. No commentary.
"""


# ──────────────────────────────────────────────────────────────────────
# LLM Prompt Templates — Task Generation
# ──────────────────────────────────────────────────────────────────────

TASK_SYSTEM_PROMPT = """You are a Senior Software Engineering Mentor designing real-world learning tasks.
Your task is to generate a single, practical coding task for a student to complete in their local development environment.

CRITICAL INSTRUCTIONS:
1. The task MUST be completable locally by a solo developer in the estimated hours (no cloud accounts, no paid services).
2. The student MUST push their work to a GitHub repository — make this explicit in the requirements.
3. Requirements must be numbered and specific (not vague like "improve the code").
4. Acceptance criteria must be objectively testable (not "code should be clean").
5. The task must teach the target milestone skills directly.
6. The difficulty level is PRE-DETERMINED — do NOT choose or change it.
7. Do NOT generate a task similar to the previous tasks listed.
8. Include a practical starter_hint that gives a concrete first step.

OUTPUT FORMAT (strict JSON only):
{
  "title": "Specific, descriptive task title",
  "description": "Clear description of what to build and why it matters for the target role.",
  "requirements": [
    "1. First numbered requirement (specific and actionable)",
    "2. Second numbered requirement",
    "3. Third numbered requirement"
  ],
  "acceptance_criteria": [
    "Acceptance criterion 1 (objectively testable)",
    "Acceptance criterion 2"
  ],
  "skills_targeted": ["Skill 1", "Skill 2"],
  "estimated_hours": 4.0,
  "starter_hint": "A concrete first step to get started."
}

Output ONLY valid JSON. No markdown, no extra text.
"""

TASK_USER_PROMPT_TEMPLATE = """Generate a learning task for this student:

TARGET ROLE: {target_role}
CURRENT MILESTONE: Milestone {milestone_order} — "{milestone_title}"
MILESTONE DESCRIPTION: {milestone_description}
MILESTONE SKILLS TO TEACH: {milestone_skills}
MILESTONE SUCCESS CRITERIA: {milestone_success_criteria}

TASK DIFFICULTY: {difficulty}/5 (PRE-DETERMINED — keep the task at exactly this difficulty level)
ESTIMATED HOURS: {estimated_hours} (keep the task completable in approximately this time)

STUDENT SKILL LEVELS:
{student_skills}

PREVIOUS TASKS (DO NOT REPEAT these topics or skills too heavily):
{previous_tasks_summary}

PERFORMANCE CONTEXT (adjust task pacing accordingly):
{performance_context}
{remediation_context}
Generate a fresh, real-world coding task that:
- Requires the student to push code to a public GitHub repository
- Has numbered, specific requirements
- Has objectively testable acceptance criteria
- Targets the milestone skills listed above
- Is at difficulty level {difficulty}/5
- Different scenario, progressively harder, same milestone skills

Output the JSON task now.
"""

TASK_RETRY_PROMPT_TEMPLATE = """Your previous task JSON failed validation:

VALIDATION ERRORS:
{validation_errors}

CONTEXT:
Milestone: {milestone_order} — {milestone_title}
Difficulty: {difficulty}/5
Target Skills: {milestone_skills}

PREVIOUS TASK TITLES (new task MUST have a different title):
{previous_titles}

RULES TO FIX:
- title: 5-256 characters (clear, specific)
- description: 20-2000 characters
- requirements: 3-10 items (numbered strings)
- acceptance_criteria: 2-8 items (objectively testable)
- skills_targeted: at least 1 item
- estimated_hours: 1.0-20.0 float
- starter_hint: optional string (max 500 chars)

Output ONLY corrected valid JSON.
"""


# ──────────────────────────────────────────────────────────────────────
# Deterministic Difficulty Formula
# ──────────────────────────────────────────────────────────────────────

def compute_next_difficulty(
    milestone_band: int,
    profile_skill_levels: list[str],
    performance_context: dict[str, Any],
) -> int:
    """
    Compute the next task's difficulty deterministically from three inputs.

    This is a PURE FUNCTION — no randomness, no side effects, fully unit-testable.
    The LLM is given this value and told to respect it; it never self-selects difficulty.

    Formula:
        base_difficulty = milestone_band (1-5)

        skill_modifier:
            - If majority (>60%) of target skills are 'beginner' -> -1 (easier start)
            - Otherwise -> 0 (stay at band level)

        performance_modifier (uses last 3 evaluated tasks, requires at least 2):
            - If avg_score >= 85 -> +1 (student acing it, increase challenge)
            - If avg_score <= 50 -> -1 (student struggling, reduce challenge)
            - Otherwise (or < 2 evaluated tasks) -> 0 (neutral)

        final = clamp(base + skill_modifier + performance_modifier, 1, 5)

    Args:
        milestone_band: The current milestone's difficulty_band (1-5).
        profile_skill_levels: List of proficiency strings from the student's profile
            matching the current milestone's target skills.
        performance_context: Dict with keys:
            - 'avg_score' (float | None): Average evaluation score 0-100 across last 3 tasks.
            - 'tasks_evaluated' (int): Number of scored tasks (>= 2 required for non-neutral).

    Returns:
        Integer difficulty in range [1, 5].
    """
    base = milestone_band

    # Skill modifier: adjust based on student's proficiency in milestone target skills
    if profile_skill_levels:
        level_counts = {
            "beginner": profile_skill_levels.count("beginner"),
            "intermediate": profile_skill_levels.count("intermediate"),
            "advanced": profile_skill_levels.count("advanced"),
        }
        total = sum(level_counts.values())
        if total > 0 and (level_counts["beginner"] / total) > 0.6:
            skill_modifier = -1
        else:
            skill_modifier = 0
    else:
        skill_modifier = 0

    # Performance modifier: requires at least 2 evaluated tasks from the last 3
    avg_score: float | None = performance_context.get("avg_score")
    tasks_evaluated: int = performance_context.get("tasks_evaluated", 0)

    if avg_score is not None and tasks_evaluated >= 2:
        if avg_score >= 85.0:
            perf_modifier = 1   # Excelling — increase challenge
        elif avg_score <= 50.0:
            perf_modifier = -1  # Struggling — reduce pressure
        else:
            perf_modifier = 0   # Normal pace
    else:
        # Fewer than 2 evaluated tasks — neutral (0)
        perf_modifier = 0

    final = max(1, min(5, base + skill_modifier + perf_modifier))

    logger.debug(
        "compute_next_difficulty: milestone_band=%d, skill_mod=%d, perf_mod=%d -> final=%d",
        milestone_band, skill_modifier, perf_modifier, final,
    )
    return final


# ──────────────────────────────────────────────────────────────────────
# PerformanceProvider Interface
# ──────────────────────────────────────────────────────────────────────

class PerformanceProvider:
    """
    Interface for reading student performance data.

    Calculates average score using the last 3 evaluated tasks.
    Requires at least 2 evaluated tasks; otherwise returns neutral (avg_score=None).
    """

    def get_performance_context(
        self,
        evaluated_tasks: list[Any],
    ) -> dict[str, Any]:
        """
        Derive performance context from completed task evaluations.

        Uses the last 3 evaluated tasks. Requires at least 2 to compute avg_score.

        Args:
            evaluated_tasks: List of Task ORM objects with status=EVALUATED.

        Returns:
            Dict with 'avg_score' (float | None) and 'tasks_evaluated' (int).
        """
        if not evaluated_tasks:
            return {"avg_score": None, "tasks_evaluated": 0}

        # Last 3 evaluated tasks only
        recent_tasks = evaluated_tasks[-3:]
        scores = []
        for task in recent_tasks:
            summary = task.evaluation_summary
            if summary and isinstance(summary, dict):
                score = summary.get("score")
                if score is not None:
                    try:
                        scores.append(float(score))
                    except (TypeError, ValueError):
                        pass

        if len(scores) >= 2:
            return {
                "avg_score": round(sum(scores) / len(scores), 2),
                "tasks_evaluated": len(scores),
            }

        # Fewer than 2 evaluated tasks — neutral
        return {"avg_score": None, "tasks_evaluated": len(scores)}


# ──────────────────────────────────────────────────────────────────────
# JSON Parsing Utility
# ──────────────────────────────────────────────────────────────────────

def _clean_and_parse_json(raw_text: str) -> dict[str, Any]:
    """Strip code fence wrappers if present and parse JSON."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return json.loads(cleaned)


# ──────────────────────────────────────────────────────────────────────
# Similarity Check (prevent near-duplicate tasks)
# ──────────────────────────────────────────────────────────────────────

def _normalize_title(title: str) -> str:
    """Normalize a title for similarity comparison."""
    # Lowercase, remove accents, strip punctuation, collapse whitespace
    nfkd = unicodedata.normalize("NFKD", title.lower())
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    no_punct = re.sub(r"[^\w\s]", " ", ascii_only)
    return " ".join(no_punct.split())


def _jaccard_similarity(a: str, b: str) -> float:
    """Compute Jaccard similarity between two normalized strings (word-level)."""
    set_a = set(a.split())
    set_b = set(b.split())
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def is_near_duplicate_title(
    new_title: str,
    previous_titles: list[str],
    threshold: float = 0.5,
) -> bool:
    """
    Check if a new task title is too similar to any previous task title.

    Uses Jaccard similarity on normalized word sets.
    Titles with similarity >= threshold are considered near-duplicates.

    Args:
        new_title: The candidate task title.
        previous_titles: List of existing task titles for this user.
        threshold: Similarity threshold (0.5 = 50% word overlap).

    Returns:
        True if the new title is a near-duplicate of any existing title.
    """
    normalized_new = _normalize_title(new_title)
    for prev in previous_titles:
        normalized_prev = _normalize_title(prev)
        if _jaccard_similarity(normalized_new, normalized_prev) >= threshold:
            return True
    return False


# ──────────────────────────────────────────────────────────────────────
# Roadmap Generation with LLM + Validation + 1-Shot Retry
# ──────────────────────────────────────────────────────────────────────

async def generate_roadmap_from_llm(
    llm_provider: BaseLLMProvider,
    profile: dict[str, Any],
) -> list[MilestoneItem]:
    """
    Generate and validate a personalized roadmap using the LLM.

    Flow:
    1. Build user prompt from profile data.
    2. Call LLM for JSON response.
    3. Validate with Pydantic (LLMRoadmapOutput) including structural rules.
    4. On validation failure, retry ONCE with error details in the prompt.
    5. On second failure, raise LLMValidationError — do NOT store partial data.

    Args:
        llm_provider: Configured BaseLLMProvider instance.
        profile: Student profile dict from profile-agent-service.

    Returns:
        List of validated MilestoneItem objects.

    Raises:
        LLMValidationError: When LLM output cannot be validated after retry.
        LLMTimeoutError: When LLM request times out.
        LLMProviderError: When provider API fails.
    """
    target_role = profile.get("target_role", "Software Engineer")
    experience_level = profile.get("experience_level", "fresher")
    structured_skills = profile.get("structured_skills", [])
    dashboard_data = profile.get("dashboard_data", {})

    # Format skills for the prompt
    skills_text = "\n".join(
        f"  - {s.get('skill_name', 'Unknown')} ({s.get('proficiency_level', 'beginner')}) "
        f"[{s.get('category', 'General')}]"
        for s in structured_skills
    ) or "  - No structured skills on record"

    weak_areas = dashboard_data.get("weakest_areas", [])
    strong_areas = dashboard_data.get("strongest_areas", [])
    weak_text = ", ".join(weak_areas) if weak_areas else "None identified"
    strong_text = ", ".join(strong_areas) if strong_areas else "None identified"

    user_prompt = ROADMAP_USER_PROMPT_TEMPLATE.format(
        target_role=target_role,
        experience_level=experience_level,
        structured_skills=skills_text,
        weak_areas=weak_text,
        strong_areas=strong_text,
    )

    logger.info("Agent 2 Roadmap: Requesting LLM generation for role '%s'", target_role)
    raw_response = await llm_provider.generate_json(ROADMAP_SYSTEM_PROMPT, user_prompt)

    # Attempt 1
    validation_error_str = ""
    try:
        data = _clean_and_parse_json(raw_response)
        validated = LLMRoadmapOutput.model_validate(data)
        logger.info("Agent 2 Roadmap: Validated %d milestones on first attempt", len(validated.milestones))
        return validated.milestones
    except (json.JSONDecodeError, ValidationError) as err:
        validation_error_str = str(err)
        logger.warning(
            "Agent 2 Roadmap: Primary validation failed (%s). Triggering 1-shot retry.",
            validation_error_str[:200],
        )

    # Extract metadata for retry prompt
    milestone_count = 0
    total_days = 0
    try:
        parsed_partial = json.loads(raw_response)
        milestones_partial = parsed_partial.get("milestones", [])
        milestone_count = len(milestones_partial)
        total_days = sum(m.get("estimated_days", 0) for m in milestones_partial)
    except Exception:
        pass

    skills_summary = f"{target_role} student at {experience_level} level"

    retry_prompt = ROADMAP_RETRY_PROMPT_TEMPLATE.format(
        validation_errors=validation_error_str[:1000],
        target_role=target_role,
        experience_level=experience_level,
        skills_summary=skills_summary,
        milestone_count=milestone_count,
        total_days=total_days,
    )

    logger.info("Agent 2 Roadmap: Sending error-correction retry to LLM")
    retry_raw = await llm_provider.generate_json(ROADMAP_SYSTEM_PROMPT, retry_prompt)

    try:
        data = _clean_and_parse_json(retry_raw)
        validated = LLMRoadmapOutput.model_validate(data)
        logger.info(
            "Agent 2 Roadmap: Validated %d milestones after retry", len(validated.milestones)
        )
        return validated.milestones
    except Exception as retry_err:
        logger.error(
            "Agent 2 Roadmap: Fatal validation after retry. Raw: %s... | Error: %s",
            retry_raw[:200],
            retry_err,
        )
        raise LLMValidationError(
            message="Roadmap LLM output failed schema validation after error-correction retry",
            detail=str(retry_err),
        ) from retry_err


# ──────────────────────────────────────────────────────────────────────
# Task Generation with LLM + Validation + 1-Shot Retry
# ──────────────────────────────────────────────────────────────────────

async def generate_task_from_llm(
    llm_provider: BaseLLMProvider,
    milestone: MilestoneItem,
    difficulty: int,
    estimated_hours: float,
    target_role: str,
    student_skills: list[dict[str, Any]],
    previous_tasks: list[dict[str, Any]],
    performance_context: dict[str, Any],
    is_remediation: bool = False,
    previous_feedback: str | None = None,
) -> LLMTaskOutput:
    """
    Generate and validate a single learning task using the LLM.

    The difficulty is PRE-COMPUTED by compute_next_difficulty() and passed to
    the LLM as a directive — the LLM never self-selects difficulty.

    Flow:
    1. Build user prompt with all context.
    2. Call LLM.
    3. Validate with Pydantic.
    4. Check for near-duplicate title.
    5. On failure, retry ONCE with error details and previous titles.
    6. On second failure, raise LLMValidationError.

    Args:
        llm_provider: Configured BaseLLMProvider instance.
        milestone: The current milestone (order, title, skills, etc.)
        difficulty: PRE-COMPUTED difficulty integer 1-5.
        estimated_hours: Suggested completion time.
        target_role: Student's target career role.
        student_skills: Student's structured_skills from profile.
        previous_tasks: List of previous task dicts with 'title' and 'skills_targeted'.
        performance_context: Dict from PerformanceProvider.
        is_remediation: True if this task is a remediation task after a failed task.
        previous_feedback: Previous evaluation feedback to include in remediation prompt.

    Returns:
        Validated LLMTaskOutput object.

    Raises:
        LLMValidationError: When LLM output cannot be validated after retry.
        LLMTimeoutError: When LLM request times out.
        LLMProviderError: When provider API fails.
    """
    # Format previous tasks summary for the prompt
    if previous_tasks:
        prev_summary = "\n".join(
            f"  - Task {i+1}: '{t.get('title', 'Unknown')}' "
            f"(Skills: {', '.join(t.get('skills_targeted', [])[:3])})"
            for i, t in enumerate(previous_tasks[-5:])  # Only last 5 for context window
        )
    else:
        prev_summary = "  - No previous tasks (this is the first task)"

    # Format student skills
    skills_text = "\n".join(
        f"  - {s.get('skill_name', 'Unknown')}: {s.get('proficiency_level', 'beginner')}"
        for s in student_skills[:15]  # Cap for context window
    ) or "  - No profile skills on record"

    # Format performance context
    avg_score = performance_context.get("avg_score")
    tasks_evaluated = performance_context.get("tasks_evaluated", 0)
    if avg_score is not None:
        perf_text = f"Average score: {avg_score}/100 across {tasks_evaluated} evaluated tasks"
    else:
        perf_text = "No evaluation data yet (first task or evaluations pending)"

    if is_remediation:
        remediation_context = (
            "\nREMEDIATION TASK:\n"
            "The student did not pass their previous task on these skills.\n"
            f"PREVIOUS EVALUATION FEEDBACK:\n{previous_feedback or 'Task did not satisfy acceptance criteria.'}\n"
            "INSTRUCTION: Create a targeted remediation task on the SAME skills with clearer scaffolding "
            "to help the student master the concepts they missed.\n"
        )
    else:
        remediation_context = ""

    user_prompt = TASK_USER_PROMPT_TEMPLATE.format(
        target_role=target_role,
        milestone_order=milestone.order,
        milestone_title=milestone.title,
        milestone_description=milestone.description,
        milestone_skills=", ".join(milestone.target_skills),
        milestone_success_criteria="\n".join(f"  - {c}" for c in milestone.success_criteria),
        difficulty=difficulty,
        estimated_hours=estimated_hours,
        student_skills=skills_text,
        previous_tasks_summary=prev_summary,
        performance_context=perf_text,
        remediation_context=remediation_context,
    )

    previous_titles = [t.get("title", "") for t in previous_tasks if t.get("title")]

    logger.info(
        "Agent 2 Task: Requesting LLM generation for milestone %d at difficulty %d (remediation=%s)",
        milestone.order, difficulty, is_remediation,
    )
    raw_response = await llm_provider.generate_json(TASK_SYSTEM_PROMPT, user_prompt)

    # Attempt 1
    validation_error_str = ""
    try:
        data = _clean_and_parse_json(raw_response)
        validated = LLMTaskOutput.model_validate(data)

        # Near-duplicate check
        if is_near_duplicate_title(validated.title, previous_titles):
            raise ValueError(
                f"Generated task title '{validated.title}' is too similar to a previous task. "
                "A unique title is required."
            )

        logger.info("Agent 2 Task: Validated task '%s' on first attempt", validated.title)
        return validated

    except (json.JSONDecodeError, ValidationError, ValueError) as err:
        validation_error_str = str(err)
        logger.warning(
            "Agent 2 Task: Primary validation failed (%s). Triggering 1-shot retry.",
            validation_error_str[:200],
        )

    titles_str = ", ".join(f"'{t}'" for t in previous_titles) if previous_titles else "None"

    retry_prompt = TASK_RETRY_PROMPT_TEMPLATE.format(
        validation_errors=validation_error_str[:1000],
        milestone_order=milestone.order,
        milestone_title=milestone.title,
        difficulty=difficulty,
        milestone_skills=", ".join(milestone.target_skills),
        previous_titles=titles_str,
    )

    logger.info("Agent 2 Task: Sending error-correction retry to LLM")
    retry_raw = await llm_provider.generate_json(TASK_SYSTEM_PROMPT, retry_prompt)

    try:
        data = _clean_and_parse_json(retry_raw)
        validated = LLMTaskOutput.model_validate(data)

        if is_near_duplicate_title(validated.title, previous_titles):
            raise ValueError(
                f"Retry task title '{validated.title}' is still too similar to a previous task."
            )

        logger.info(
            "Agent 2 Task: Validated task '%s' after retry", validated.title
        )
        return validated

    except Exception as retry_err:
        logger.error(
            "Agent 2 Task: Fatal validation after retry. Raw: %s... | Error: %s",
            retry_raw[:200],
            retry_err,
        )
        raise LLMValidationError(
            message="Task LLM output failed schema validation after error-correction retry",
            detail=str(retry_err),
        ) from retry_err
