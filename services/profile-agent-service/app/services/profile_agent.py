"""
Agent 1: Profile & Dashboard Agent Core Logic.

This module encapsulates all prompt engineering, LLM orchestration, structured
schema validation with 1-shot retry, and deterministic dashboard metric calculation.

Architecture & Separation of Concerns:
- LLM prompting and schema parsing are isolated here, completely decoupled
  from the HTTP router and database layers.
- The readiness score calculation is 100% deterministic, explainable, and reproducible
  (no stochastic AI scoring for quantitative metrics).
"""

import json
import logging
from typing import Any

from pydantic import ValidationError

from app.core.llm.base import (
    BaseLLMProvider,
    LLMError,
    LLMProviderError,
    LLMTimeoutError,
    LLMValidationError,
)
from app.schemas.profile import (
    DashboardData,
    EducationInfo,
    SkillItem,
    StructuredSkillsOutput,
)

logger = logging.getLogger("profile-agent.service")

# ──────────────────────────────────────────────────────────────────────
# LLM Prompt Templates
# ──────────────────────────────────────────────────────────────────────

AGENT1_SYSTEM_PROMPT = """You are an elite Technical Screener and AI Career Strategist specializing in developer talent assessment.
Your job is to analyze a candidate's educational background, raw skills description, target career role, and experience level, and extract a structured, canonical inventory of technical and professional skills.

CRITICAL INSTRUCTIONS:
1. Extract ALL explicit technical skills mentioned (programming languages, frameworks, libraries, databases, devops tools, system concepts).
2. Infer reasonable foundational competencies implied by projects (e.g. if the candidate built a React app with REST API, infer 'REST APIs', 'HTTP', and 'Git' if context supports it).
3. Normalize each skill name to its standard industry casing (e.g. 'react.js' -> 'React', 'postgres' -> 'PostgreSQL', 'js' -> 'JavaScript').
4. Categorize each skill into one of these standard domains:
   - 'Frontend'
   - 'Backend'
   - 'Databases'
   - 'DevOps & Cloud'
   - 'Languages'
   - 'AI & Data'
   - 'Core CS'
   - 'Tools & Architecture'
5. Determine proficiency level based strictly on the candidate's description and experience:
   - 'beginner': Academic exposure, tutorials, basic syntax, introductory projects.
   - 'intermediate': Built functional full-stack/service features, integrates third-party libraries, comfortable with idioms and best practices.
   - 'advanced': In-depth production knowledge, performance optimization, architectural patterns, deep debugging.
6. Assign a confidence_score between 0.00 and 1.00 indicating certainty based on how clearly the skill was evidenced.

OUTPUT FORMAT REQUIREMENTS:
You MUST respond with a STRICT JSON object matching this exact structure:
{
  "skills": [
    {
      "skill_name": "Python",
      "category": "Languages",
      "proficiency_level": "intermediate",
      "confidence_score": 0.90
    }
  ]
}

Do NOT wrap the JSON in conversational text or commentary. Output valid JSON ONLY.
"""

AGENT1_USER_PROMPT_TEMPLATE = """Please analyze the following candidate's onboarding submission and extract their structured skills:

Target Role: {target_role}
Experience Level: {experience_level}

Education:
- Degree: {degree} ({branch})
- Institution: {institution}
- Graduation Year: {year}

Raw Background & Skills Description:
\"\"\"{skills_description}\"\"\"

Generate the structured JSON skills inventory now according to the system specification.
"""

AGENT1_RETRY_PROMPT_TEMPLATE = """Your previous response failed validation against our strict Pydantic schema.

Schema Validation Errors:
{validation_errors}

Candidate Information:
Target Role: {target_role}
Experience Level: {experience_level}
Raw Background:
\"\"\"{skills_description}\"\"\"

Please fix the error and output valid, properly formatted JSON adhering strictly to:
{{
  "skills": [
    {{
      "skill_name": "string",
      "category": "string",
      "proficiency_level": "beginner" | "intermediate" | "advanced",
      "confidence_score": float (between 0.0 and 1.0)
    }}
  ]
}}

Output valid JSON ONLY.
"""


# ──────────────────────────────────────────────────────────────────────
# LLM Orchestration & Validation with 1-shot Retry
# ──────────────────────────────────────────────────────────────────────

async def extract_structured_skills(
    llm_provider: BaseLLMProvider,
    education: EducationInfo,
    skills_description: str,
    target_role: str,
    experience_level: str,
) -> list[SkillItem]:
    """
    Extract structured technical skills using the LLM with strict Pydantic validation.

    Prompt Strategy:
        1. Formats the raw onboarding inputs into a structured prompt targeting the
           system persona.
        2. Calls the configured LLM provider expecting valid JSON conforming to
           StructuredSkillsOutput.
        3. Parses and validates with Pydantic v2.
        4. If validation fails (e.g. malformed JSON, missing keys, invalid enum value),
           retries ONCE with an error-correction prompt containing the exact Pydantic error.
        5. If retry also fails, raises LLMValidationError with specific details. Never
           silently stores corrupted or incomplete data.

    Args:
        llm_provider: Configured BaseLLMProvider instance.
        education: User's educational background.
        skills_description: Free-text narrative written by the student.
        target_role: Desired job role (e.g. Full Stack Engineer).
        experience_level: Experience bracket ('student', 'fresher', '1-2yrs', '2+yrs').

    Returns:
        List of validated SkillItem objects.

    Raises:
        LLMValidationError: When LLM output cannot be validated after retry.
        LLMTimeoutError: When LLM request times out.
        LLMProviderError: When provider API fails.
    """
    user_prompt = AGENT1_USER_PROMPT_TEMPLATE.format(
        target_role=target_role,
        experience_level=experience_level,
        degree=education.degree,
        branch=education.branch,
        institution=education.institution,
        year=education.year,
        skills_description=skills_description,
    )

    logger.info("Agent 1: Requesting structured skills extraction from LLM provider")
    raw_response = await llm_provider.generate_json(
        system_prompt=AGENT1_SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    # Attempt 1: Parse and validate
    validation_error_str: str = ""
    try:
        data = _clean_and_parse_json(raw_response)
        validated_output = StructuredSkillsOutput.model_validate(data)
        logger.info(
            "Agent 1: Successfully extracted %d skills on primary attempt",
            len(validated_output.skills),
        )
        return validated_output.skills
    except (json.JSONDecodeError, ValidationError) as err:
        validation_error_str = str(err)
        logger.warning(
            "Agent 1: Primary extraction validation failed (%s). Triggering 1-shot error correction retry.",
            validation_error_str,
        )

    # Attempt 2: Error-correction retry prompt
    retry_prompt = AGENT1_RETRY_PROMPT_TEMPLATE.format(
        validation_errors=validation_error_str,
        target_role=target_role,
        experience_level=experience_level,
        skills_description=skills_description,
    )

    retry_raw_response = await llm_provider.generate_json(
        system_prompt=AGENT1_SYSTEM_PROMPT,
        user_prompt=retry_prompt,
    )

    try:
        data = _clean_and_parse_json(retry_raw_response)
        validated_output = StructuredSkillsOutput.model_validate(data)
        logger.info(
            "Agent 1: Successfully extracted %d skills after error-correction retry",
            len(validated_output.skills),
        )
        return validated_output.skills
    except Exception as retry_err:
        logger.error(
            "Agent 1: Fatal validation failure after retry. Raw response: %s | Error: %s",
            retry_raw_response[:200],
            retry_err,
        )
        raise LLMValidationError(
            message="LLM output failed strict schema validation after error-correction retry",
            detail=str(retry_err),
        ) from retry_err


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
# Deterministic Readiness Score & Dashboard Calculations
# ──────────────────────────────────────────────────────────────────────

"""
Readiness Score Formula Specification:
---------------------------------------
The readiness score is a deterministic, explainable 0-100 metric calculated
without any stochastic LLM hallucinations. It comprises three transparent components:

1. Skill Depth & Volume (Weight: 45 points max)
   - Evaluates total technical strength based on proficiency level and confidence:
     - beginner     = 1.0 point
     - intermediate = 2.5 points
     - advanced     = 4.0 points
   - Effective Points = SUM(proficiency_points * confidence_score)
   - Normalized score = min(45, round((Effective Points / 15.0) * 45))
   - Benchmarked such that demonstrating 6-8 solid intermediate skills achieves top marks.

2. Category Diversity & Domain Breadth (Weight: 25 points max)
   - Evaluates coverage across distinct computer science / software engineering domains
     (Languages, Frontend, Backend, Databases, DevOps & Cloud, etc.).
   - Distinct Categories C (capped at 5):
     - Diversity Points = min(25, C * 5)
   - Encourages holistic developer competency rather than isolated one-dimensional skills.

3. Experience Level Baseline (Weight: 30 points max)
   - Establishes a calibrated baseline aligned with market seniority expectations:
     - 'student':  12 points
     - 'fresher':  18 points
     - '1-2yrs':   24 points
     - '2+yrs':    30 points

Total Readiness Score = Skill Depth (0-45) + Category Diversity (0-25) + Experience Baseline (0-30)
Clamped between 0 and 100.
"""

PROFICIENCY_WEIGHTS = {
    "beginner": 1.0,
    "intermediate": 2.5,
    "advanced": 4.0,
}

EXPERIENCE_BASELINES = {
    "student": 12,
    "fresher": 18,
    "1-2yrs": 24,
    "2+yrs": 30,
}


def calculate_dashboard_data(
    skills: list[SkillItem],
    experience_level: str,
    target_role: str,
) -> DashboardData:
    """
    Compute explainable, deterministic dashboard metrics from structured skills.

    Args:
        skills: List of validated SkillItem objects.
        experience_level: 'student', 'fresher', '1-2yrs', or '2+yrs'.
        target_role: Candidate's target role.

    Returns:
        DashboardData schema with distribution, averages, strongest/weakest areas,
        and the weighted readiness score.
    """
    # 1. Skill distribution by category
    distribution: dict[str, int] = {}
    category_scores: dict[str, list[float]] = {}

    for skill in skills:
        cat = skill.category
        distribution[cat] = distribution.get(cat, 0) + 1

        prof_val = 1.0 if skill.proficiency_level == "beginner" else (
            2.0 if skill.proficiency_level == "intermediate" else 3.0
        )
        if cat not in category_scores:
            category_scores[cat] = []
        category_scores[cat].append(prof_val * skill.confidence_score)

    # 2. Category averages (1.0 to 3.0 scale)
    category_averages: dict[str, float] = {}
    for cat, scores in category_scores.items():
        category_averages[cat] = round(sum(scores) / len(scores), 2)

    # 3. Strongest and Weakest skill areas
    # Sort categories by average proficiency score descending
    sorted_categories = sorted(
        category_averages.keys(),
        key=lambda c: (category_averages[c], distribution.get(c, 0)),
        reverse=True,
    )
    strongest_areas = sorted_categories[:2]
    weakest_areas = sorted_categories[-2:] if len(sorted_categories) > 2 else []

    # 4. Readiness Score Calculation
    # Factor A: Skill Depth (0-45)
    effective_pts = sum(
        PROFICIENCY_WEIGHTS.get(s.proficiency_level, 1.0) * s.confidence_score
        for s in skills
    )
    skill_depth_score = min(45, round((effective_pts / 15.0) * 45))

    # Factor B: Category Diversity (0-25)
    unique_cats = len(distribution)
    diversity_score = min(25, unique_cats * 5)

    # Factor C: Experience Level Baseline (0-30)
    exp_baseline = EXPERIENCE_BASELINES.get(experience_level, 15)

    readiness_score = min(100, max(0, skill_depth_score + diversity_score + exp_baseline))

    # Summary explanation for auditability and UI display
    summary = (
        f"Readiness Score: {readiness_score}/100. "
        f"Breakdown: Skill Competency Depth ({skill_depth_score}/45 pts across {len(skills)} skills), "
        f"Domain Diversity ({diversity_score}/25 pts spanning {unique_cats} categories), "
        f"Experience Baseline ({exp_baseline}/30 pts for '{experience_level}' tier)."
    )

    return DashboardData(
        skill_distribution=distribution,
        category_averages=category_averages,
        strongest_areas=strongest_areas,
        weakest_areas=weakest_areas,
        readiness_score=readiness_score,
        readiness_summary=summary,
    )
