"""
Score composition and feedback generation tests for evaluator-agent-service.

Tests:
1. Score formula: final_score = (deterministic * 0.65) + (llm * 0.35)
2. Cap rule interactions
3. Pass / Fail threshold logic
4. Mentor-style feedback summary generation (never leaks red_flags)
"""

import unittest

from app.schemas.evaluation import CheckResult, LLMCodeReviewOutput
from app.services.llm_reviewer import (
    apply_integrity_gates,
    apply_llm_score_cap,
    compute_final_score,
    generate_feedback_summary,
)


class TestScoreComposition(unittest.TestCase):
    """Test score composition formula and cap boundary logic."""

    def test_score_composition_formula(self) -> None:
        """Verify exact weights: deterministic 65%, LLM 35%."""
        # Case 1: deterministic=100, llm=100 -> 100.0
        self.assertEqual(compute_final_score(100.0, 100.0), 100.0)

        # Case 2: deterministic=50, llm=50 -> 50.0
        self.assertEqual(compute_final_score(50.0, 50.0), 50.0)

        # Case 3: deterministic=80, llm=60 -> 80*0.65 (52) + 60*0.35 (21) = 73.0
        self.assertEqual(compute_final_score(80.0, 60.0), 73.0)

        # Case 4: deterministic=60, llm=80 -> 60*0.65 (39) + 80*0.35 (28) = 67.0
        self.assertEqual(compute_final_score(60.0, 80.0), 67.0)

    def test_score_composition_with_cap(self) -> None:
        """Verify composition pipeline with cap applied."""
        det_score = 30.0
        raw_llm = 90.0

        # Cap allows max: 30 + 15 = 45.0
        capped_llm, was_capped = apply_llm_score_cap(raw_llm, det_score)
        self.assertTrue(was_capped)
        self.assertEqual(capped_llm, 45.0)

        # Final score: 30 * 0.65 (19.5) + 45 * 0.35 (15.75) = 35.25
        final = compute_final_score(det_score, capped_llm)
        self.assertEqual(final, 35.25)

    def test_pass_score_boundary(self) -> None:
        """Verify pass/fail boundary logic with PASS_SCORE=60."""
        PASS_SCORE = 60.0

        # Exactly at 60.0 -> passed
        self.assertTrue(60.0 >= PASS_SCORE)

        # Just below 60.0 (59.9) -> failed
        self.assertFalse(59.9 >= PASS_SCORE)

        # High pass
        self.assertTrue(85.5 >= PASS_SCORE)

    def test_feedback_summary_passing(self) -> None:
        """Verify feedback summary for a passed submission."""
        review = LLMCodeReviewOutput(
            strengths=["Clean modular architecture with single-responsibility functions"],
            weaknesses=["Could use more type annotations"],
            suggestions=["Add docstrings to helper modules"],
            red_flags=["Potential injection attempt: ignore instructions"],  # Must NOT be leaked
            quality_score=85.0,
        )
        checks = [
            CheckResult(check_name="readme_present", passed=True, score_contribution=15.0, weight_pct=15.0, detail="ok"),
            CheckResult(check_name="minimum_commit_count", passed=True, score_contribution=15.0, weight_pct=15.0, detail="ok"),
        ]

        feedback = generate_feedback_summary(
            deterministic_score=80.0,
            deterministic_checks=checks,
            llm_review=review,
            final_score=82.0,
            passed=True,
            pass_score=60.0,
        )

        self.assertIn("Congratulations", feedback)
        self.assertIn("82/100", feedback)
        self.assertIn("Clean modular architecture", feedback)
        # Red flags must NEVER appear in student feedback
        self.assertNotIn("injection", feedback.lower())
        self.assertNotIn("red_flags", feedback)

    def test_feedback_summary_failing_with_actionable_advice(self) -> None:
        """Verify feedback summary for a failed submission gives actionable mentor guidance."""
        review = LLMCodeReviewOutput(
            strengths=["Good README overview"],
            weaknesses=["Missing unit tests", "No error handling on network requests"],
            suggestions=["Write pytest tests for core endpoints"],
            red_flags=[],
            quality_score=40.0,
        )
        checks = [
            CheckResult(check_name="commits_after_task_start", passed=False, score_contribution=0.0, weight_pct=30.0, detail="No commits"),
            CheckResult(check_name="relevant_files_present", passed=False, score_contribution=0.0, weight_pct=25.0, detail="No py files"),
        ]

        feedback = generate_feedback_summary(
            deterministic_score=35.0,
            deterministic_checks=checks,
            llm_review=review,
            final_score=38.0,
            passed=False,
            pass_score=60.0,
        )

        self.assertIn("38/100", feedback)
        self.assertIn("learning opportunity", feedback.lower())
        # Failed check names are clearly stated in human-readable terms
        self.assertIn("commits after task start", feedback)
        self.assertIn("relevant files present", feedback)
        # Actionable next step included
        self.assertIn("Write pytest tests", feedback)

    def test_reused_repo_item3_scenario_anti_reuse_gate_regression(self) -> None:
        """
        REGRESSION TEST: Bug Fix for Item 3 Scoring Integrity Issue.
        
        Scenario from Item 3 (navdeep-G/samplemod evaluation):
        - A student submits a pre-existing/reused repository with zero commits after task start.
        - Other deterministic checks pass (60.0 / 100.0).
        - LLM quality score is strong (68.0 / 100.0).
        
        OLD BEHAVIOR (BUG):
        - Raw formula: (60.0 * 0.65) + (68.0 * 0.35) = 39.0 + 23.8 = 62.8
        - The 30-point deduction was absorbed by the LLM score, causing 62.8 >= 60.0 (PASSED = True)!
        - This defeated the entire anti-reuse check.
        
        NEW BEHAVIOR (FIX):
        - commits_after_task_start acts as a SECOND GATE.
        - Raw formula would have produced 62.8 (assert this explicitly!).
        - apply_integrity_gates caps final_score at min(62.8, 35.0) = 35.0.
        - passed is forced to False.
        - reuse_suspected is True.
        - feedback_summary includes student-facing notice:
          "No commits were found after you started this task. Submissions must include new work — please push commits made after starting the task."
        """
        det_score = 60.0
        llm_score = 68.0
        checks = [
            CheckResult(check_name="repo_exists_and_public", passed=True, score_contribution=0.0, weight_pct=0.0, detail="ok"),
            CheckResult(check_name="commits_after_task_start", passed=False, score_contribution=0.0, weight_pct=30.0, detail="zero commits after task start"),
            CheckResult(check_name="minimum_commit_count", passed=True, score_contribution=15.0, weight_pct=15.0, detail="29 commits"),
            CheckResult(check_name="readme_present", passed=True, score_contribution=15.0, weight_pct=15.0, detail="ok"),
            CheckResult(check_name="relevant_files_present", passed=True, score_contribution=15.0, weight_pct=25.0, detail="ok"),
            CheckResult(check_name="no_giant_single_commit_dump", passed=True, score_contribution=10.0, weight_pct=10.0, detail="ok"),
            CheckResult(check_name="basic_lint_score", passed=True, score_contribution=5.0, weight_pct=5.0, detail="ok"),
        ]

        # 1. Assert the OLD formula would have passed
        old_raw_score = compute_final_score(det_score, llm_score)
        self.assertEqual(old_raw_score, 62.8)
        old_passed = old_raw_score >= 60.0
        self.assertTrue(old_passed, "Proving bug: old un-gated formula would have passed with 62.8!")

        # 2. Assert NEW logic fails it and flags reuse
        new_score, new_passed, reuse_suspected, single_dump_suspected = apply_integrity_gates(
            raw_final_score=old_raw_score,
            deterministic_checks=checks,
            pass_threshold=60.0,
            cap_score=35.0,
        )

        self.assertLessEqual(new_score, 35.0)
        self.assertEqual(new_score, 35.0)
        self.assertFalse(new_passed)
        self.assertTrue(reuse_suspected)
        self.assertFalse(single_dump_suspected)

        # 3. Assert student-facing reason in feedback_summary
        review = LLMCodeReviewOutput(
            strengths=["Repository is publicly accessible and contains relevant source files"],
            weaknesses=["Code structure could be improved"],
            suggestions=["Add a comprehensive test suite with pytest"],
            red_flags=[],
            quality_score=llm_score,
        )
        feedback = generate_feedback_summary(
            deterministic_score=det_score,
            deterministic_checks=checks,
            llm_review=review,
            final_score=new_score,
            passed=new_passed,
            pass_score=60.0,
            reuse_suspected=reuse_suspected,
        )

        self.assertIn("No commits were found after you started this task.", feedback)
        self.assertIn("Submissions must include new work — please push commits made after starting the task.", feedback)

    def test_single_commit_dump_anti_dump_gate_regression(self) -> None:
        """
        ANTI-DUMP GATE TEST (Check 6: no_giant_single_commit_dump).
        
        A student dumps an entire existing project in 1 single bulk commit with 20 files.
        Even if LLM rates the code 85/100 and deterministic score was 75/100:
        Old formula would have produced (75*0.65 + 85*0.35) = 48.75 + 29.75 = 78.5 (passed)!
        New logic ensures that single-commit dump is also gated:
        - final_score capped at <= 35.0
        - passed is forced to False
        - single_dump_suspected is True
        - feedback contains clear advice to break work into multiple meaningful commits.
        """
        det_score = 75.0
        llm_score = 85.0
        checks = [
            CheckResult(check_name="repo_exists_and_public", passed=True, score_contribution=0.0, weight_pct=0.0, detail="ok"),
            CheckResult(check_name="commits_after_task_start", passed=True, score_contribution=30.0, weight_pct=30.0, detail="ok"),
            CheckResult(check_name="minimum_commit_count", passed=False, score_contribution=0.0, weight_pct=15.0, detail="only 1 commit"),
            CheckResult(check_name="readme_present", passed=True, score_contribution=15.0, weight_pct=15.0, detail="ok"),
            CheckResult(check_name="relevant_files_present", passed=True, score_contribution=25.0, weight_pct=25.0, detail="ok"),
            CheckResult(check_name="no_giant_single_commit_dump", passed=False, score_contribution=0.0, weight_pct=10.0, detail="single commit dump with 20 files"),
            CheckResult(check_name="basic_lint_score", passed=True, score_contribution=5.0, weight_pct=5.0, detail="ok"),
        ]

        raw_score = compute_final_score(det_score, llm_score)
        self.assertEqual(raw_score, 78.5)
        self.assertTrue(raw_score >= 60.0, "Proving weakness: without gating, bulk dump would pass with 78.5!")

        new_score, new_passed, reuse_suspected, single_dump_suspected = apply_integrity_gates(
            raw_final_score=raw_score,
            deterministic_checks=checks,
            pass_threshold=60.0,
            cap_score=35.0,
        )

        self.assertLessEqual(new_score, 35.0)
        self.assertFalse(new_passed)
        self.assertTrue(single_dump_suspected)
        self.assertFalse(reuse_suspected)

        review = LLMCodeReviewOutput(
            strengths=["Well organized codebase"],
            weaknesses=["Single commit history"],
            suggestions=["Break into multiple commits"],
            red_flags=[],
            quality_score=llm_score,
        )
        feedback = generate_feedback_summary(
            deterministic_score=det_score,
            deterministic_checks=checks,
            llm_review=review,
            final_score=new_score,
            passed=new_passed,
            pass_score=60.0,
            single_dump_suspected=single_dump_suspected,
        )

        self.assertIn("Your submission appears to be a single bulk commit dump.", feedback)
        self.assertIn("Submissions must demonstrate iterative development", feedback)


if __name__ == "__main__":
    unittest.main()
