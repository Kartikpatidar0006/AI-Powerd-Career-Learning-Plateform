"""
Deterministic Checks Engine for evaluator-agent-service.

Each check is a pure function: (repo_data) -> CheckResult.
No LLM calls, no side effects. Independently testable.

SCORING FORMULA (sum = 100 points for non-gate checks):
┌─────────────────────────────┬────────────┬──────────────────────────────────────────────┐
│ Check                       │ Weight %   │ Rationale                                    │
├─────────────────────────────┼────────────┼──────────────────────────────────────────────┤
│ repo_exists_and_public      │ GATE       │ Hard fail; blocks all further evaluation     │
│ commits_after_task_start    │ 30 pts     │ Primary reuse-prevention signal              │
│ minimum_commit_count        │ 15 pts     │ Discourages single-commit dump               │
│ readme_present              │ 15 pts     │ Documentation baseline                       │
│ relevant_files_present      │ 25 pts     │ Proves skill-relevant work exists            │
│ no_giant_single_commit      │ 10 pts     │ Catches squash/reuse even if timestamps ok   │
│ basic_lint_score            │  5 pts     │ Best-effort; neutral (2.5 pts) if skipped    │
└─────────────────────────────┴────────────┴──────────────────────────────────────────────┘

All inputs are UNTRUSTED (from GitHub API). Validators must be defensive.
"""

import logging
import re
from datetime import datetime, timezone

from app.schemas.evaluation import CheckResult, CommitInfo, FileEntry

logger = logging.getLogger("evaluator-agent.checks")

# ── Extension groups for language detection ──────────────────────────────
_LANG_EXTENSIONS: dict[str, set[str]] = {
    "python": {".py"},
    "javascript": {".js", ".mjs", ".cjs", ".jsx"},
    "typescript": {".ts", ".tsx"},
    "java": {".java"},
    "go": {".go"},
    "rust": {".rs"},
    "cpp": {".cpp", ".cxx", ".cc"},
}


def _detect_primary_language(tree: list[FileEntry]) -> str | None:
    """Detect primary language from file extensions. Returns language name or None."""
    counts: dict[str, int] = {}
    for entry in tree:
        ext = ""
        if "." in entry.path:
            ext = "." + entry.path.rsplit(".", 1)[-1].lower()
        for lang, exts in _LANG_EXTENSIONS.items():
            if ext in exts:
                counts[lang] = counts.get(lang, 0) + 1
    if not counts:
        return None
    return max(counts, key=lambda k: counts[k])


def _parse_iso_timestamp(ts: str | None) -> datetime | None:
    """Safely parse an ISO8601 timestamp string. Returns None on any failure."""
    if not ts:
        return None
    try:
        # GitHub returns e.g. "2024-01-15T10:30:00Z"
        ts = ts.strip().rstrip("Z")
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────────
# Check 1: GATE — repo_exists_and_public
# ──────────────────────────────────────────────────────────────────────────

def check_repo_exists_and_public(repo_accessible: bool, error_reason: str | None = None) -> CheckResult:
    """
    GATE CHECK: repository must exist and be public.

    This check short-circuits the entire evaluation if it fails.
    Score contribution is 0 (it's a gate, not a scored check).

    Args:
        repo_accessible: True if the repo was successfully accessed.
        error_reason: Human-readable reason if inaccessible.

    Returns:
        CheckResult with passed=True or passed=False (triggers FAILED status).
    """
    if repo_accessible:
        return CheckResult(
            check_name="repo_exists_and_public",
            passed=True,
            score_contribution=0.0,
            weight_pct=0.0,
            detail="Repository is publicly accessible via GitHub API.",
        )
    return CheckResult(
        check_name="repo_exists_and_public",
        passed=False,
        score_contribution=0.0,
        weight_pct=0.0,
        detail=error_reason or "Repository could not be accessed (not found or private).",
    )


# ──────────────────────────────────────────────────────────────────────────
# Check 2: commits_after_task_start (30 pts)
# ──────────────────────────────────────────────────────────────────────────

def check_commits_after_task_start(
    commits: list[CommitInfo],
    task_started_at: str | None,
) -> CheckResult:
    """
    PRIMARY ANTI-REUSE CHECK (30 pts).

    At least 1 commit must have a timestamp strictly AFTER the task's started_at.
    Zero such commits = repo likely pre-existed before the task was assigned.

    NOTE: Timestamp comparison is advisory — a determined student can backdate
    commits via git. Combined with check #6 (no_giant_single_commit_dump),
    this provides a meaningful signal for honest submissions.

    Args:
        commits: List of CommitInfo from the default branch.
        task_started_at: ISO8601 string of task started_at from roadmap-agent-service.

    Returns:
        CheckResult with 30-pt contribution on pass, 0 on fail.
    """
    WEIGHT_PCT = 30.0

    if not task_started_at:
        # Cannot verify timestamps — give neutral partial score, note it
        return CheckResult(
            check_name="commits_after_task_start",
            passed=True,  # Do not penalize when task timestamp unavailable
            score_contribution=WEIGHT_PCT * 0.5,
            weight_pct=WEIGHT_PCT,
            detail=(
                "Task start timestamp was not available; commit date verification skipped. "
                "Partial credit awarded."
            ),
        )

    task_start_dt = _parse_iso_timestamp(task_started_at)
    if task_start_dt is None:
        return CheckResult(
            check_name="commits_after_task_start",
            passed=True,
            score_contribution=WEIGHT_PCT * 0.5,
            weight_pct=WEIGHT_PCT,
            detail="Could not parse task start timestamp; partial credit awarded.",
        )

    commits_after = 0
    for commit in commits:
        commit_dt = _parse_iso_timestamp(commit.timestamp)
        if commit_dt and commit_dt > task_start_dt:
            commits_after += 1

    if commits_after == 0:
        return CheckResult(
            check_name="commits_after_task_start",
            passed=False,
            score_contribution=0.0,
            weight_pct=WEIGHT_PCT,
            detail=(
                f"No commits found after task start ({task_started_at}). "
                "This is a strong signal of a pre-existing or reused repository. "
                "All your work on this task must be committed AFTER starting it."
            ),
        )

    return CheckResult(
        check_name="commits_after_task_start",
        passed=True,
        score_contribution=WEIGHT_PCT,
        weight_pct=WEIGHT_PCT,
        detail=f"{commits_after} commit(s) found after task start ({task_started_at}). ✓",
    )


# ──────────────────────────────────────────────────────────────────────────
# Check 3: minimum_commit_count (15 pts)
# ──────────────────────────────────────────────────────────────────────────

def check_minimum_commit_count(commits: list[CommitInfo], minimum: int = 2) -> CheckResult:
    """
    COMMIT FREQUENCY CHECK (15 pts).

    Requires at least `minimum` total commits. Single-commit repos suggest
    a bulk dump rather than iterative development.

    Args:
        commits: List of CommitInfo fetched.
        minimum: Minimum required commits (default 2).

    Returns:
        CheckResult with 15-pt contribution on pass, 0 on fail.
    """
    WEIGHT_PCT = 15.0
    count = len(commits)

    if count >= minimum:
        return CheckResult(
            check_name="minimum_commit_count",
            passed=True,
            score_contribution=WEIGHT_PCT,
            weight_pct=WEIGHT_PCT,
            detail=f"{count} commits found (minimum required: {minimum}). ✓",
        )

    return CheckResult(
        check_name="minimum_commit_count",
        passed=False,
        score_contribution=0.0,
        weight_pct=WEIGHT_PCT,
        detail=(
            f"Only {count} commit(s) found (minimum required: {minimum}). "
            "Iterative development with meaningful commit messages is expected. "
            "Make incremental commits as you work rather than a single bulk commit."
        ),
    )


# ──────────────────────────────────────────────────────────────────────────
# Check 4: readme_present (15 pts)
# ──────────────────────────────────────────────────────────────────────────

def check_readme_present(readme_content: str | None, min_chars: int = 50) -> CheckResult:
    """
    DOCUMENTATION CHECK (15 pts).

    README must exist and have at least `min_chars` characters of content.
    A non-trivial README signals professional documentation habits.

    Args:
        readme_content: Raw README text, or None if not found.
        min_chars: Minimum character count for a non-trivial README (default 50).

    Returns:
        CheckResult with 15-pt contribution on pass, 0 on fail.
    """
    WEIGHT_PCT = 15.0

    if not readme_content:
        return CheckResult(
            check_name="readme_present",
            passed=False,
            score_contribution=0.0,
            weight_pct=WEIGHT_PCT,
            detail=(
                "No README file found. A README is required to document your project, "
                "explain its purpose, and provide usage instructions."
            ),
        )

    stripped = readme_content.strip()
    if len(stripped) < min_chars:
        return CheckResult(
            check_name="readme_present",
            passed=False,
            score_contribution=0.0,
            weight_pct=WEIGHT_PCT,
            detail=(
                f"README exists but has only {len(stripped)} characters (minimum: {min_chars}). "
                "A meaningful README should describe what the project does and how to use it."
            ),
        )

    return CheckResult(
        check_name="readme_present",
        passed=True,
        score_contribution=WEIGHT_PCT,
        weight_pct=WEIGHT_PCT,
        detail=f"README present with {len(stripped)} characters. ✓",
    )


# ──────────────────────────────────────────────────────────────────────────
# Check 5: relevant_files_present (25 pts)
# ──────────────────────────────────────────────────────────────────────────

_SKILL_EXTENSION_MAP: dict[str, list[str]] = {
    "python": [".py"],
    "fastapi": [".py"],
    "django": [".py"],
    "flask": [".py"],
    "javascript": [".js", ".mjs", ".jsx"],
    "typescript": [".ts", ".tsx"],
    "react": [".jsx", ".tsx"],
    "vue": [".vue"],
    "java": [".java"],
    "kotlin": [".kt"],
    "go": [".go"],
    "rust": [".rs"],
    "sql": [".sql"],
    "postgresql": [".sql"],
    "html": [".html", ".htm"],
    "css": [".css", ".scss"],
    "bash": [".sh"],
    "c++": [".cpp", ".hpp", ".cc"],
    "c": [".c", ".h"],
}


def check_relevant_files_present(
    tree: list[FileEntry],
    skills_targeted: list[str],
) -> CheckResult:
    """
    SKILL VALIDATION CHECK (25 pts).

    At least 1 file must match extensions relevant to the task's skills_targeted.
    Prevents submissions containing only a README with no actual code.

    Args:
        tree: Full file tree from GitHub.
        skills_targeted: Skills from the task specification.

    Returns:
        CheckResult with 25-pt contribution on pass, 0 on fail.
    """
    WEIGHT_PCT = 25.0

    if not skills_targeted:
        # No skills to validate against — award partial
        return CheckResult(
            check_name="relevant_files_present",
            passed=True,
            score_contribution=WEIGHT_PCT * 0.6,
            weight_pct=WEIGHT_PCT,
            detail="No specific skills targeted; generic source files accepted.",
        )

    expected_exts: set[str] = set()
    for skill in skills_targeted:
        expected_exts.update(_SKILL_EXTENSION_MAP.get(skill.lower(), []))

    if not expected_exts:
        # Skills found but no known mapping — award partial
        return CheckResult(
            check_name="relevant_files_present",
            passed=True,
            score_contribution=WEIGHT_PCT * 0.6,
            weight_pct=WEIGHT_PCT,
            detail=(
                f"Skills {skills_targeted} have no known file extension mapping; "
                "generic source file check passed."
            ),
        )

    matching = []
    for entry in tree:
        if entry.type != "blob":
            continue
        path_lower = entry.path.lower()
        ext = "." + path_lower.rsplit(".", 1)[-1] if "." in path_lower else ""
        if ext in expected_exts:
            matching.append(entry.path)

    if not matching:
        return CheckResult(
            check_name="relevant_files_present",
            passed=False,
            score_contribution=0.0,
            weight_pct=WEIGHT_PCT,
            detail=(
                f"No files with extensions {sorted(expected_exts)} found "
                f"for skills {skills_targeted}. "
                "Your repository must contain actual code relevant to the task's skill requirements."
            ),
        )

    return CheckResult(
        check_name="relevant_files_present",
        passed=True,
        score_contribution=WEIGHT_PCT,
        weight_pct=WEIGHT_PCT,
        detail=(
            f"{len(matching)} relevant file(s) found for skills {skills_targeted} "
            f"(e.g. {matching[:3]}). ✓"
        ),
    )


# ──────────────────────────────────────────────────────────────────────────
# Check 6: no_giant_single_commit_dump (10 pts)
# ──────────────────────────────────────────────────────────────────────────

def check_no_giant_single_commit_dump(
    commits: list[CommitInfo],
    tree: list[FileEntry],
) -> CheckResult:
    """
    REPO DUMP DETECTION (10 pts).

    If there is only 1 commit total AND the repository has significant files
    (>= 5 blobs), it is flagged. This catches squashed histories and repos
    uploaded in a single bulk operation.

    Args:
        commits: Commit history list.
        tree: File tree list.

    Returns:
        CheckResult with 10-pt contribution on pass, 0 on fail.
    """
    WEIGHT_PCT = 10.0

    commit_count = len(commits)
    blob_count = sum(1 for e in tree if e.type == "blob")

    if commit_count == 1 and blob_count >= 5:
        return CheckResult(
            check_name="no_giant_single_commit_dump",
            passed=False,
            score_contribution=0.0,
            weight_pct=WEIGHT_PCT,
            detail=(
                f"Repository has only 1 commit but {blob_count} files. "
                "This suggests a bulk upload rather than iterative development. "
                "Please develop your solution with incremental commits showing your progress."
            ),
        )

    return CheckResult(
        check_name="no_giant_single_commit_dump",
        passed=True,
        score_contribution=WEIGHT_PCT,
        weight_pct=WEIGHT_PCT,
        detail=(
            f"{commit_count} commit(s) with {blob_count} files — "
            "development pattern looks iterative. ✓"
        ),
    )


# ──────────────────────────────────────────────────────────────────────────
# Check 7: basic_lint_score (5 pts) — best-effort, neutral if skipped
# ──────────────────────────────────────────────────────────────────────────

_PYTHON_LONG_LINE_RE = re.compile(r"^.{121,}$", re.MULTILINE)
_PYTHON_BARE_EXCEPT_RE = re.compile(r"^\s*except\s*:", re.MULTILINE)
_PYTHON_PRINT_DEBUG_RE = re.compile(r"^\s*print\s*\(", re.MULTILINE)


def check_basic_lint_score(
    file_contents: dict[str, str],
    primary_language: str | None,
) -> CheckResult:
    """
    BEST-EFFORT LINT HEURISTIC (5 pts).

    Performs a simple line-based lint heuristic for Python repositories.
    For other languages, skips with neutral score (2.5 pts).
    Does NOT run any code or install tools — purely string pattern analysis.

    Python heuristics (all UNTRUSTED input, capped to prevent DoS):
    - Lines over 120 chars (PEP8 guideline)
    - Bare `except:` clauses (anti-pattern)
    - Excessive print() debug statements

    Args:
        file_contents: Dict of path -> contents (UNTRUSTED, already size-capped).
        primary_language: Detected language (from file extension analysis).

    Returns:
        CheckResult with score 0–5 based on lint quality, or neutral 2.5 if skipped.
    """
    WEIGHT_PCT = 5.0
    NEUTRAL_SCORE = WEIGHT_PCT / 2.0

    if not file_contents:
        return CheckResult(
            check_name="basic_lint_score",
            passed=True,
            score_contribution=NEUTRAL_SCORE,
            weight_pct=WEIGHT_PCT,
            detail="No source files available for lint analysis; neutral score awarded.",
        )

    if primary_language != "python":
        return CheckResult(
            check_name="basic_lint_score",
            passed=True,
            score_contribution=NEUTRAL_SCORE,
            weight_pct=WEIGHT_PCT,
            detail=(
                f"Language '{primary_language}' detected; Python-specific lint skipped. "
                "Neutral score awarded."
            ),
        )

    # Python lint analysis
    py_files = {p: c for p, c in file_contents.items() if p.endswith(".py")}

    if not py_files:
        return CheckResult(
            check_name="basic_lint_score",
            passed=True,
            score_contribution=NEUTRAL_SCORE,
            weight_pct=WEIGHT_PCT,
            detail="No .py files in fetched contents; neutral score awarded.",
        )

    total_lines = 0
    long_lines = 0
    bare_excepts = 0
    print_statements = 0

    for path, content in py_files.items():
        # Cap analysis to first 5000 lines per file (DoS prevention)
        lines = content.split("\n")[:5000]
        total_lines += len(lines)
        content_capped = "\n".join(lines)

        long_lines += len(_PYTHON_LONG_LINE_RE.findall(content_capped))
        bare_excepts += len(_PYTHON_BARE_EXCEPT_RE.findall(content_capped))
        print_statements += len(_PYTHON_PRINT_DEBUG_RE.findall(content_capped))

    issues = []
    penalty = 0.0

    if total_lines > 0:
        long_pct = long_lines / total_lines * 100
        if long_pct > 20:
            issues.append(f"{long_pct:.0f}% of lines exceed 120 chars (PEP8)")
            penalty += 1.5
        elif long_pct > 10:
            issues.append(f"{long_pct:.0f}% of lines exceed 120 chars")
            penalty += 0.5

    if bare_excepts > 2:
        issues.append(f"{bare_excepts} bare 'except:' clause(s) found (anti-pattern)")
        penalty += 1.0

    if print_statements > 10:
        issues.append(f"{print_statements} print() statements (consider using logging)")
        penalty += 0.5

    score = max(0.0, WEIGHT_PCT - penalty)
    passed = score >= (WEIGHT_PCT / 2.0)

    if not issues:
        detail = f"Python lint heuristic passed ({len(py_files)} file(s), {total_lines} lines). ✓"
    else:
        detail = f"Python lint heuristic: {'; '.join(issues)}. ({len(py_files)} file(s), {total_lines} lines)"

    return CheckResult(
        check_name="basic_lint_score",
        passed=passed,
        score_contribution=round(score, 2),
        weight_pct=WEIGHT_PCT,
        detail=detail,
    )


# ──────────────────────────────────────────────────────────────────────────
# Aggregate: run_all_deterministic_checks
# ──────────────────────────────────────────────────────────────────────────

class GateFailure(Exception):
    """Raised when the gate check (repo_exists_and_public) fails, short-circuiting evaluation."""
    def __init__(self, check: CheckResult) -> None:
        super().__init__(check.detail)
        self.check = check


def compute_deterministic_score(checks: list[CheckResult]) -> float:
    """
    Sum score contributions from all non-gate checks.

    Returns a float 0-100.
    """
    total = sum(c.score_contribution for c in checks if c.check_name != "repo_exists_and_public")
    return round(min(100.0, max(0.0, total)), 2)
