"""
Live verification script demonstrating Agent 3 (GitHub Repository Evaluator)
against a real public repository on GitHub (octocat/Hello-World).

Flow:
1. Initialize GitHubClient
2. Fetch repo metadata (check public/exists)
3. Fetch git tree (recursive file listing)
4. Fetch curated files (README)
5. Fetch commit history
6. Run pure deterministic checks
7. Run LLM review with delimiter protection
8. Compose final score and mentor feedback
"""

import asyncio
import os
import sys

# Ensure UTF-8 output on Windows terminal
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure evaluator service app is in sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "evaluator-agent-service"))

from app.core.llm.mock_provider import MockLLMProvider
from app.services.checks import (
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
from app.services.github_client import GitHubClient, parse_github_url
from app.services.llm_reviewer import (
    apply_llm_score_cap,
    compute_final_score,
    generate_feedback_summary,
    run_llm_review,
)


async def main() -> None:
    repo_url = "https://github.com/navdeep-G/samplemod"
    print("=" * 65)
    print(f"AGENT 3 LIVE REPO EVALUATION: {repo_url}")
    print("=" * 65)

    owner, repo = parse_github_url(repo_url)
    print(f"1. Parsed GitHub repository: owner='{owner}', repo='{repo}'")

    print("\n2. Fetching repository data from GitHub REST API (httpx async)...")
    async with GitHubClient() as github:
        meta = await github.get_repo_metadata(owner, repo)
        print(f"   [OK] Metadata: default_branch='{meta.default_branch}', private={meta.private}")

        tree = await github.get_file_tree(owner, repo, meta.default_branch)
        print(f"   [OK] File tree: {len(tree)} total objects found in git tree")
        for entry in tree[:5]:
            print(f"     - {entry.type}: {entry.path} ({entry.size} bytes)")

        readme_content = await github.get_readme(owner, repo, meta.default_branch)
        print(f"   [OK] README: {'Found (' + str(len(readme_content or '')) + ' chars)' if readme_content else 'Not found'}")

        file_contents = await github.fetch_relevant_files(
            owner, repo, meta.default_branch, tree, skills_targeted=["python"], readme_content=readme_content
        )
        print(f"   [OK] Fetched curated source files: {list(file_contents.keys())}")

        commits = await github.get_commit_history(owner, repo, meta.default_branch, limit=10)
        print(f"   [OK] Fetched commit history: {len(commits)} commits")
        for c in commits[:3]:
            print(f"     - [{c.timestamp[:10]}] {c.author}: {c.message.splitlines()[0][:50]}")

    print("\n3. Running Deterministic Checks (pure functions, no LLM):")
    primary_lang = _detect_primary_language(tree)
    task_started_at = "2010-01-01T00:00:00Z"  # For demonstration

    checks = [
        check_repo_exists_and_public(repo_accessible=True),
        check_commits_after_task_start(commits, task_started_at),
        check_minimum_commit_count(commits, minimum=2),
        check_readme_present(readme_content, min_chars=50),
        check_relevant_files_present(tree, skills_targeted=["python"]),
        check_no_giant_single_commit_dump(commits, tree),
        check_basic_lint_score(file_contents, primary_lang),
    ]

    for c in checks:
        icon = "[PASS]" if c.passed else "[FAIL]"
        print(f"   {icon:6} {c.check_name:28} | {c.score_contribution:4.1f}/{c.weight_pct:4.1f} pts | {c.detail[:60]}")

    det_score = compute_deterministic_score(checks)
    print(f"\n   -> Deterministic Score: {det_score:.1f} / 100.0 (weight: 65%)")

    print("\n4. Running LLM Code Review (with delimiter isolation & injection defense):")
    # Using MockLLMProvider for offline deterministic execution
    llm_provider = MockLLMProvider()
    review = await run_llm_review(
        llm_provider=llm_provider,
        skills_targeted=["python"],
        file_contents=file_contents,
        commits=commits,
        deterministic_score=det_score,
        deterministic_checks=checks,
    )
    print(f"   [OK] LLM Raw Quality Score: {review.quality_score:.1f} (weight: 35%)")
    print(f"   [OK] Strengths: {review.strengths}")
    print(f"   [OK] Weaknesses: {review.weaknesses}")
    print(f"   [OK] Suggestions: {review.suggestions}")

    capped_llm, was_capped = apply_llm_score_cap(review.quality_score, det_score)
    if was_capped:
        print(f"   [WARN] LLM Score capped from {review.quality_score} to {capped_llm} (defense cap rule)")
    else:
        print(f"   [OK] LLM Score within permitted cap: {capped_llm}")

    final_score = compute_final_score(det_score, capped_llm)
    passed = final_score >= 60.0

    print(f"\n5. Final Evaluation Composition:")
    print(f"   Formula: ({det_score:.1f} * 0.65) + ({capped_llm:.1f} * 0.35) = {final_score:.1f}")
    print(f"   Status:  {'PASSED (>= 60)' if passed else 'NEEDS IMPROVEMENT (< 60)'}")

    feedback = generate_feedback_summary(
        deterministic_score=det_score,
        deterministic_checks=checks,
        llm_review=review,
        final_score=final_score,
        passed=passed,
        pass_score=60.0,
    )
    print(f"\n6. Student Mentor Feedback:")
    print(f"   \"{feedback}\"")
    print("\n" + "=" * 65)
    print("DEMONSTRATION COMPLETED SUCCESSFULLY")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())
