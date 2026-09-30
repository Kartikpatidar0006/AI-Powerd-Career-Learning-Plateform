"""
Unit tests for all 7 deterministic checks in evaluator-agent-service.

Requirements:
- Each check is an isolated unit test with crafted fixture repo data
- No real GitHub calls
- Tests all boundary cases and weights
"""

import unittest
from datetime import datetime, timezone

from app.schemas.evaluation import CommitInfo, FileEntry
from app.services.checks import (
    check_basic_lint_score,
    check_commits_after_task_start,
    check_minimum_commit_count,
    check_no_giant_single_commit_dump,
    check_readme_present,
    check_relevant_files_present,
    check_repo_exists_and_public,
    compute_deterministic_score,
)


class TestDeterministicChecks(unittest.TestCase):
    """Isolated unit tests for each deterministic check function."""

    # ── Check 1: repo_exists_and_public ─────────────────────────────────
    def test_repo_exists_and_public_pass(self) -> None:
        result = check_repo_exists_and_public(repo_accessible=True)
        self.assertTrue(result.passed)
        self.assertEqual(result.check_name, "repo_exists_and_public")
        self.assertEqual(result.score_contribution, 0.0)

    def test_repo_exists_and_public_fail(self) -> None:
        result = check_repo_exists_and_public(repo_accessible=False, error_reason="Repository not found")
        self.assertFalse(result.passed)
        self.assertIn("not found", result.detail.lower())

    # ── Check 2: commits_after_task_start (30 pts) ──────────────────────
    def test_commits_after_task_start_pass(self) -> None:
        task_started = "2026-01-10T10:00:00Z"
        commits = [
            CommitInfo(sha="111", author="student", message="Initial commit", timestamp="2026-01-10T09:00:00Z"),
            CommitInfo(sha="222", author="student", message="Work on task", timestamp="2026-01-10T11:00:00Z"),
        ]
        result = check_commits_after_task_start(commits, task_started)
        self.assertTrue(result.passed)
        self.assertEqual(result.score_contribution, 30.0)
        self.assertEqual(result.weight_pct, 30.0)
        self.assertIn("1 commit(s) found after task start", result.detail)

    def test_commits_after_task_start_fail_reuse_flagged(self) -> None:
        task_started = "2026-01-10T10:00:00Z"
        # All commits happened BEFORE task start (pre-existing repo reused)
        commits = [
            CommitInfo(sha="111", author="student", message="Old project", timestamp="2025-12-01T10:00:00Z"),
            CommitInfo(sha="222", author="student", message="Old commit", timestamp="2025-12-02T10:00:00Z"),
        ]
        result = check_commits_after_task_start(commits, task_started)
        self.assertFalse(result.passed)
        self.assertEqual(result.score_contribution, 0.0)
        self.assertIn("pre-existing or reused", result.detail.lower())

    def test_commits_after_task_start_missing_task_timestamp(self) -> None:
        commits = [
            CommitInfo(sha="111", author="student", message="Commit", timestamp="2026-01-10T11:00:00Z")
        ]
        result = check_commits_after_task_start(commits, None)
        self.assertTrue(result.passed)
        self.assertEqual(result.score_contribution, 15.0)  # Partial credit

    # ── Check 3: minimum_commit_count (15 pts) ──────────────────────────
    def test_minimum_commit_count_pass(self) -> None:
        commits = [
            CommitInfo(sha="111", author="student", message="First", timestamp="2026-01-10T10:00:00Z"),
            CommitInfo(sha="222", author="student", message="Second", timestamp="2026-01-10T11:00:00Z"),
        ]
        result = check_minimum_commit_count(commits, minimum=2)
        self.assertTrue(result.passed)
        self.assertEqual(result.score_contribution, 15.0)

    def test_minimum_commit_count_fail_single_commit(self) -> None:
        commits = [
            CommitInfo(sha="111", author="student", message="Dump everything", timestamp="2026-01-10T10:00:00Z"),
        ]
        result = check_minimum_commit_count(commits, minimum=2)
        self.assertFalse(result.passed)
        self.assertEqual(result.score_contribution, 0.0)
        self.assertIn("iterative development", result.detail.lower())

    # ── Check 4: readme_present (15 pts) ────────────────────────────────
    def test_readme_present_pass(self) -> None:
        content = "# Project Title\nThis is a complete and descriptive README with more than 50 characters."
        result = check_readme_present(content, min_chars=50)
        self.assertTrue(result.passed)
        self.assertEqual(result.score_contribution, 15.0)

    def test_readme_present_missing(self) -> None:
        result = check_readme_present(None)
        self.assertFalse(result.passed)
        self.assertEqual(result.score_contribution, 0.0)
        self.assertIn("no readme file found", result.detail.lower())

    def test_readme_present_trivial(self) -> None:
        result = check_readme_present("# Hi", min_chars=50)
        self.assertFalse(result.passed)
        self.assertEqual(result.score_contribution, 0.0)
        self.assertIn("minimum: 50", result.detail.lower())

    # ── Check 5: relevant_files_present (25 pts) ────────────────────────
    def test_relevant_files_present_python_pass(self) -> None:
        tree = [
            FileEntry(path="README.md", type="blob", size=100),
            FileEntry(path="app/main.py", type="blob", size=200),
        ]
        result = check_relevant_files_present(tree, skills_targeted=["python", "fastapi"])
        self.assertTrue(result.passed)
        self.assertEqual(result.score_contribution, 25.0)

    def test_relevant_files_present_python_fail(self) -> None:
        # Student submitted only a text file and README for a python task
        tree = [
            FileEntry(path="README.md", type="blob", size=100),
            FileEntry(path="notes.txt", type="blob", size=50),
        ]
        result = check_relevant_files_present(tree, skills_targeted=["python"])
        self.assertFalse(result.passed)
        self.assertEqual(result.score_contribution, 0.0)
        self.assertIn("no files with extensions", result.detail.lower())

    # ── Check 6: no_giant_single_commit_dump (10 pts) ───────────────────
    def test_no_giant_single_commit_dump_pass(self) -> None:
        commits = [
            CommitInfo(sha="1", author="s", message="m1", timestamp="2026-01-01T00:00:00Z"),
            CommitInfo(sha="2", author="s", message="m2", timestamp="2026-01-01T01:00:00Z"),
        ]
        tree = [FileEntry(path=f"file{i}.py", type="blob", size=10) for i in range(10)]
        result = check_no_giant_single_commit_dump(commits, tree)
        self.assertTrue(result.passed)
        self.assertEqual(result.score_contribution, 10.0)

    def test_no_giant_single_commit_dump_fail(self) -> None:
        # 1 commit with 6 files -> flagged as bulk dump
        commits = [
            CommitInfo(sha="1", author="s", message="Dump all code", timestamp="2026-01-01T00:00:00Z"),
        ]
        tree = [FileEntry(path=f"file{i}.py", type="blob", size=10) for i in range(6)]
        result = check_no_giant_single_commit_dump(commits, tree)
        self.assertFalse(result.passed)
        self.assertEqual(result.score_contribution, 0.0)
        self.assertIn("bulk upload", result.detail.lower())

    # ── Check 7: basic_lint_score (5 pts) ───────────────────────────────
    def test_basic_lint_score_clean_python(self) -> None:
        files = {
            "app/main.py": "def add(a: int, b: int) -> int:\n    return a + b\n"
        }
        result = check_basic_lint_score(files, primary_language="python")
        self.assertTrue(result.passed)
        self.assertEqual(result.score_contribution, 5.0)

    def test_basic_lint_score_penalties(self) -> None:
        # Bare excepts and long lines
        bad_code = "try:\n    pass\nexcept:\n    pass\n" * 5
        bad_code += ("x = '" + "a" * 130 + "'\n") * 10
        files = {"app/main.py": bad_code}
        result = check_basic_lint_score(files, primary_language="python")
        self.assertLess(result.score_contribution, 5.0)

    def test_basic_lint_score_non_python_neutral(self) -> None:
        files = {"src/App.tsx": "export const App = () => <div>Hello</div>;"}
        result = check_basic_lint_score(files, primary_language="typescript")
        self.assertTrue(result.passed)
        self.assertEqual(result.score_contribution, 2.5)  # Neutral 2.5 pts

    # ── Aggregate score sum ─────────────────────────────────────────────
    def test_compute_deterministic_score_total(self) -> None:
        task_started = "2026-01-10T10:00:00Z"
        commits = [
            CommitInfo(sha="1", author="s", message="m1", timestamp="2026-01-10T10:30:00Z"),
            CommitInfo(sha="2", author="s", message="m2", timestamp="2026-01-10T11:00:00Z"),
        ]
        tree = [
            FileEntry(path="README.md", type="blob", size=200),
            FileEntry(path="main.py", type="blob", size=300),
        ]
        readme = "# Readme\n" + "This is a great documentation for the project." * 3
        files = {"main.py": "def test():\n    return 42\n"}

        checks = [
            check_repo_exists_and_public(True),
            check_commits_after_task_start(commits, task_started),  # 30
            check_minimum_commit_count(commits),                    # 15
            check_readme_present(readme),                           # 15
            check_relevant_files_present(tree, ["python"]),          # 25
            check_no_giant_single_commit_dump(commits, tree),       # 10
            check_basic_lint_score(files, "python"),                # 5
        ]

        total = compute_deterministic_score(checks)
        self.assertEqual(total, 100.0)


if __name__ == "__main__":
    unittest.main()
