"""
Pydantic v2 schemas for the Evaluator Agent Service.

Covers:
1. GitHub API data structures (repo metadata, file tree, commit)
2. Deterministic check result
3. LLM code review output (strict validation)
4. Internal request/response schemas (trigger, evaluation result)
5. Student-facing response schemas
"""

import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field, field_validator


# ──────────────────────────────────────────────────────────────
# GitHub API Data Structures
# ──────────────────────────────────────────────────────────────

class RepoMetadata(BaseModel):
    """Metadata fetched from the GitHub repository."""
    owner: str
    repo: str
    default_branch: str
    private: bool
    created_at: str | None
    pushed_at: str | None
    size_kb: int = 0
    description: str | None = None


class CommitInfo(BaseModel):
    """A single commit from the repository history."""
    sha: str
    author: str
    message: str
    timestamp: str


class FileEntry(BaseModel):
    """A single entry from the git tree."""
    path: str
    type: str  # "blob" or "tree"
    size: int = 0


class RepoSnapshot(BaseModel):
    """
    Compact audit snapshot of what was seen in the repository.
    Stored in JSONB; does NOT contain full file contents.
    """
    file_tree_count: int
    commit_count: int
    commit_timestamps: list[str]
    readme_present: bool
    primary_language: str | None
    default_branch: str
    pushed_at: str | None


# ──────────────────────────────────────────────────────────────
# Deterministic Check Result
# ──────────────────────────────────────────────────────────────

class CheckResult(BaseModel):
    """
    Result of a single deterministic check.

    Weight documentation (sum = 100 points):
      repo_exists_and_public     — GATE (pass/fail, no score contribution)
      commits_after_task_start   — 30 pts  (critical: prevents repo reuse)
      minimum_commit_count       — 15 pts  (discourages single-commit dumps)
      readme_present             — 15 pts  (documentation baseline)
      relevant_files_present     — 25 pts  (skill-relevant code exists)
      no_giant_single_commit     — 10 pts  (catches squash/reuse)
      basic_lint_score           —  5 pts  (best-effort, neutral if skipped)
    """
    check_name: str
    passed: bool
    score_contribution: float = Field(ge=0.0, le=30.0)
    weight_pct: float = Field(ge=0.0, le=30.0, description="This check's max % of the 100-pt pool")
    detail: str


# ──────────────────────────────────────────────────────────────
# LLM Code Review (strict output schema)
# ──────────────────────────────────────────────────────────────

class LLMCodeReviewOutput(BaseModel):
    """
    Strict schema required from the LLM code review response.

    Validated with Pydantic; 1-shot retry on parse failure.
    quality_score is raw LLM output — cap rule applied in service layer.
    """
    strengths: list[str] = Field(..., min_length=1, max_length=10)
    weaknesses: list[str] = Field(..., min_length=1, max_length=10)
    suggestions: list[str] = Field(..., min_length=1, max_length=10)
    red_flags: list[str] = Field(default_factory=list, max_length=10)
    quality_score: float = Field(..., ge=0.0, le=100.0)

    @field_validator("strengths", "weaknesses", "suggestions", mode="before")
    @classmethod
    def ensure_list_of_strings(cls, v: Any) -> list[str]:
        """Ensure each item is a non-empty string."""
        if not isinstance(v, list):
            raise ValueError("Must be a list")
        return [str(item).strip() for item in v if str(item).strip()]


# ──────────────────────────────────────────────────────────────
# Internal Request Schemas
# ──────────────────────────────────────────────────────────────

class TriggerEvaluationRequest(BaseModel):
    """
    Body for POST /internal/evaluate.
    Called by roadmap-agent-service (or dev trigger) to start evaluation.
    """
    task_id: uuid.UUID
    user_id: uuid.UUID
    github_repo_url: str = Field(..., min_length=10, max_length=512)
    task_started_at: str | None = Field(
        default=None,
        description="ISO8601 timestamp of when the task was started (for commits_after_task_start check)",
    )
    skills_targeted: list[str] = Field(
        default_factory=list,
        description="Skills from the task; used to select relevant file extensions",
    )


# ──────────────────────────────────────────────────────────────
# Student-Facing Response Schemas
# ──────────────────────────────────────────────────────────────

class CheckResultResponse(BaseModel):
    """Student-facing deterministic check result (safe to expose)."""
    check_name: str
    passed: bool
    score_contribution: float
    weight_pct: float
    detail: str


class EvaluationResponse(BaseModel):
    """
    Student-facing evaluation result for GET /evaluations/{task_id}.

    Intentionally excludes:
    - raw llm_review.red_flags (injection attempt details — internal only)
    - llm_review raw JSON (student sees feedback_summary instead)
    - Internal IDs or error detail beyond status

    Includes:
    - final_score, passed badge
    - deterministic_checks breakdown (fully explainable)
    - feedback_summary (mentor-style paragraph)
    - status (COMPLETED, FAILED, IN_PROGRESS, PENDING)
    """
    id: uuid.UUID
    task_id: uuid.UUID
    user_id: uuid.UUID
    github_repo_url: str
    status: str
    final_score: float | None
    passed: bool | None
    reuse_suspected: bool = False
    deterministic_score: float | None
    deterministic_checks: list[CheckResultResponse] | None
    feedback_summary: str | None
    # Safe subset of LLM review (no injection-attempt red_flags)
    llm_strengths: list[str] | None = None
    llm_weaknesses: list[str] | None = None
    llm_suggestions: list[str] | None = None
    error_detail: str | None = None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class EvaluationStatusResponse(BaseModel):
    """Lightweight status-only response (for polling)."""
    task_id: uuid.UUID
    status: str
    final_score: float | None = None
    passed: bool | None = None

    model_config = {"from_attributes": True}
