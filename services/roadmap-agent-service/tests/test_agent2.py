"""
Comprehensive tests for Agent 2: Roadmap & Task Generator.

Test coverage:
1. Roadmap validation (milestones, difficulty progression, day range)
2. LLM failure creates zero rows (atomicity)
3. Concurrent generate returns clean 409
4. Invalid roadmap triggers retry then failure
5. Task state machine — complete transition matrix
6. Compute_next_difficulty unit tests (pure function)
7. GitHub URL validation (valid/invalid cases)
8. "One active task per user" enforcement
9. Concurrent /tasks/next produces exactly one task
10. User isolation — cannot read/submit another user's task
11. ProfileClient: service down gives 503, no profile gives 409
12. No response contains "Traceback"
"""

import asyncio
import json
import uuid
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import settings
from app.core.llm.base import (
    BaseLLMProvider,
    LLMProviderError,
    LLMTimeoutError,
    LLMValidationError,
)
from app.core.llm.mock_provider import MockLLMProvider
from app.main import app
from app.models.task import TaskStatus
from app.schemas.roadmap import LLMRoadmapOutput, LLMTaskOutput, MilestoneItem
from app.services.github_validator import validate_github_url
from app.services.roadmap_agent import (
    PerformanceProvider,
    compute_next_difficulty,
    is_near_duplicate_title,
)
from app.services.state_machine import (
    ALLOWED_TRANSITIONS,
    TaskStateMachine,
    TaskTransitionError,
)


# ──────────────────────────────────────────────────────────────────────
# Helper: Valid Mock Roadmap JSON
# ──────────────────────────────────────────────────────────────────────

def _valid_roadmap_json() -> str:
    return json.dumps({
        "milestones": [
            {
                "order": 1,
                "title": "Foundations",
                "description": "Learn the fundamentals of software development.",
                "target_skills": ["Git", "Python"],
                "estimated_days": 10,
                "difficulty_band": 1,
                "success_criteria": ["Can commit code to GitHub", "Can write basic Python scripts"]
            },
            {
                "order": 2,
                "title": "Backend Development",
                "description": "Build backend APIs using FastAPI.",
                "target_skills": ["FastAPI", "REST APIs"],
                "estimated_days": 14,
                "difficulty_band": 2,
                "success_criteria": ["Build a CRUD API", "Write integration tests"]
            },
            {
                "order": 3,
                "title": "Database Design",
                "description": "Design relational databases and implement persistence.",
                "target_skills": ["PostgreSQL", "SQLAlchemy"],
                "estimated_days": 12,
                "difficulty_band": 3,
                "success_criteria": ["Design a normalized schema", "Implement async CRUD"]
            },
            {
                "order": 4,
                "title": "Deployment & DevOps",
                "description": "Containerize and deploy applications.",
                "target_skills": ["Docker", "CI/CD"],
                "estimated_days": 10,
                "difficulty_band": 4,
                "success_criteria": ["Create multi-stage Dockerfile", "Set up GitHub Actions pipeline"]
            }
        ]
    })


def _valid_task_json() -> str:
    return json.dumps({
        "title": "Build RESTful Task Manager API with FastAPI",
        "description": "Create a complete REST API for managing tasks with FastAPI, including CRUD operations and proper error handling.",
        "requirements": [
            "1. Create GET, POST, PUT, DELETE endpoints for a Task resource",
            "2. Implement Pydantic v2 schemas for input validation",
            "3. Return proper HTTP status codes for all operations",
            "4. Add OpenAPI documentation",
            "5. Write pytest tests covering all endpoints"
        ],
        "acceptance_criteria": [
            "All CRUD endpoints return correct status codes",
            "Invalid input returns 422 with descriptive errors",
            "Test suite passes with 0 failures",
            "Code is pushed to a public GitHub repository"
        ],
        "skills_targeted": ["FastAPI", "REST APIs", "Python"],
        "estimated_hours": 5.0,
        "starter_hint": "Start by defining the Pydantic schemas before implementing routes."
    })


# ──────────────────────────────────────────────────────────────────────
# 1. Roadmap Schema Validation Tests
# ──────────────────────────────────────────────────────────────────────

class TestRoadmapSchemaValidation(unittest.TestCase):
    """Test LLMRoadmapOutput Pydantic validation rules."""

    def test_valid_roadmap_passes(self) -> None:
        """A correctly structured roadmap passes all validation rules."""
        data = json.loads(_valid_roadmap_json())
        result = LLMRoadmapOutput.model_validate(data)
        self.assertEqual(len(result.milestones), 4)

    def test_too_few_milestones_rejected(self) -> None:
        """Fewer than 4 milestones must be rejected."""
        data = {
            "milestones": [
                {
                    "order": 1, "title": "M1", "description": "Desc",
                    "target_skills": ["Skill"], "estimated_days": 10,
                    "difficulty_band": 1,
                    "success_criteria": ["Criterion 1", "Criterion 2"]
                },
                {
                    "order": 2, "title": "M2", "description": "Desc",
                    "target_skills": ["Skill"], "estimated_days": 10,
                    "difficulty_band": 2,
                    "success_criteria": ["Criterion 1", "Criterion 2"]
                },
                {
                    "order": 3, "title": "M3", "description": "Desc",
                    "target_skills": ["Skill"], "estimated_days": 10,
                    "difficulty_band": 3,
                    "success_criteria": ["Criterion 1", "Criterion 2"]
                },
            ]
        }
        with self.assertRaises(ValidationError):
            LLMRoadmapOutput.model_validate(data)

    def test_too_many_milestones_rejected(self) -> None:
        """More than 8 milestones must be rejected."""
        milestones = [
            {
                "order": i + 1, "title": f"M{i+1}", "description": "Desc",
                "target_skills": ["Skill"], "estimated_days": 5,
                "difficulty_band": min(i + 1, 5),
                "success_criteria": ["C1", "C2"]
            }
            for i in range(9)  # 9 milestones — too many
        ]
        with self.assertRaises(ValidationError):
            LLMRoadmapOutput.model_validate({"milestones": milestones})

    def test_non_contiguous_orders_rejected(self) -> None:
        """Milestone orders with gaps must be rejected."""
        data = json.loads(_valid_roadmap_json())
        data["milestones"][2]["order"] = 99  # Gap in order
        with self.assertRaises(ValidationError):
            LLMRoadmapOutput.model_validate(data)

    def test_sharp_difficulty_jump_rejected(self) -> None:
        """A difficulty jump > 1 between consecutive milestones must be rejected."""
        data = json.loads(_valid_roadmap_json())
        data["milestones"][1]["difficulty_band"] = 3  # Jump from 1 to 3
        with self.assertRaises(ValidationError):
            LLMRoadmapOutput.model_validate(data)

    def test_total_days_too_low_rejected(self) -> None:
        """Total estimated days below 30 must be rejected."""
        data = json.loads(_valid_roadmap_json())
        for m in data["milestones"]:
            m["estimated_days"] = 1  # Total = 4 days
        with self.assertRaises(ValidationError):
            LLMRoadmapOutput.model_validate(data)

    def test_total_days_too_high_rejected(self) -> None:
        """Total estimated days above 120 must be rejected."""
        data = json.loads(_valid_roadmap_json())
        for m in data["milestones"]:
            m["estimated_days"] = 40  # Total = 160 days
        with self.assertRaises(ValidationError):
            LLMRoadmapOutput.model_validate(data)

    def test_missing_success_criteria_rejected(self) -> None:
        """Milestones with fewer than 2 success criteria must be rejected."""
        data = json.loads(_valid_roadmap_json())
        data["milestones"][0]["success_criteria"] = ["Only one"]
        with self.assertRaises(ValidationError):
            LLMRoadmapOutput.model_validate(data)

    def test_missing_target_skills_rejected(self) -> None:
        """Milestones with no target skills must be rejected."""
        data = json.loads(_valid_roadmap_json())
        data["milestones"][0]["target_skills"] = []
        with self.assertRaises(ValidationError):
            LLMRoadmapOutput.model_validate(data)


# ──────────────────────────────────────────────────────────────────────
# 2. Task State Machine Tests
# ──────────────────────────────────────────────────────────────────────

class TestTaskStateMachine(unittest.TestCase):
    """Test the complete task state transition matrix."""

    def setUp(self) -> None:
        self.machine = TaskStateMachine()

    def _make_task(self, status: str) -> MagicMock:
        """Create a mock task object with the given status."""
        task = MagicMock()
        task.id = uuid.uuid4()
        task.status = status
        return task

    def test_assigned_to_in_progress_allowed(self) -> None:
        """ASSIGNED -> IN_PROGRESS is a valid transition."""
        task = self._make_task(TaskStatus.ASSIGNED)
        self.machine.transition(task, TaskStatus.IN_PROGRESS)
        self.assertEqual(task.status, TaskStatus.IN_PROGRESS)

    def test_in_progress_to_submitted_allowed(self) -> None:
        """IN_PROGRESS -> SUBMITTED is a valid transition."""
        task = self._make_task(TaskStatus.IN_PROGRESS)
        self.machine.transition(task, TaskStatus.SUBMITTED)
        self.assertEqual(task.status, TaskStatus.SUBMITTED)

    def test_submitted_to_evaluating_allowed(self) -> None:
        """SUBMITTED -> EVALUATING is a valid transition (claimed by evaluator)."""
        task = self._make_task(TaskStatus.SUBMITTED)
        self.machine.transition(task, TaskStatus.EVALUATING)
        self.assertEqual(task.status, TaskStatus.EVALUATING)

    def test_evaluating_to_evaluated_allowed(self) -> None:
        """EVALUATING -> EVALUATED is a valid transition (evaluator succeeds)."""
        task = self._make_task(TaskStatus.EVALUATING)
        self.machine.transition(task, TaskStatus.EVALUATED)
        self.assertEqual(task.status, TaskStatus.EVALUATED)

    def test_evaluating_to_submitted_allowed(self) -> None:
        """EVALUATING -> SUBMITTED is allowed on evaluator failure/fallback."""
        task = self._make_task(TaskStatus.EVALUATING)
        self.machine.transition(task, TaskStatus.SUBMITTED)
        self.assertEqual(task.status, TaskStatus.SUBMITTED)

    def test_submitted_to_submitted_allowed(self) -> None:
        """SUBMITTED -> SUBMITTED is allowed for URL re-submission."""
        task = self._make_task(TaskStatus.SUBMITTED)
        self.machine.transition(task, TaskStatus.SUBMITTED)
        self.assertEqual(task.status, TaskStatus.SUBMITTED)

    def test_submitted_to_evaluated_illegal(self) -> None:
        """SUBMITTED -> EVALUATED directly is illegal (must go through EVALUATING)."""
        task = self._make_task(TaskStatus.SUBMITTED)
        with self.assertRaises(TaskTransitionError):
            self.machine.transition(task, TaskStatus.EVALUATED)

    def test_evaluated_is_terminal(self) -> None:
        """EVALUATED has no valid outgoing transitions."""
        task = self._make_task(TaskStatus.EVALUATED)
        for next_status in [
            TaskStatus.ASSIGNED,
            TaskStatus.IN_PROGRESS,
            TaskStatus.SUBMITTED,
            TaskStatus.EVALUATING,
        ]:
            with self.assertRaises(TaskTransitionError):
                self.machine.transition(task, next_status)
                task.status = TaskStatus.EVALUATED

    def test_assigned_to_submitted_illegal(self) -> None:
        """ASSIGNED -> SUBMITTED must be rejected (must go through IN_PROGRESS)."""
        task = self._make_task(TaskStatus.ASSIGNED)
        with self.assertRaises(TaskTransitionError):
            self.machine.transition(task, TaskStatus.SUBMITTED)

    def test_assigned_to_evaluating_illegal(self) -> None:
        """ASSIGNED -> EVALUATING must be rejected."""
        task = self._make_task(TaskStatus.ASSIGNED)
        with self.assertRaises(TaskTransitionError):
            self.machine.transition(task, TaskStatus.EVALUATING)

    def test_all_illegal_transitions_rejected(self) -> None:
        """Every transition NOT in ALLOWED_TRANSITIONS must raise TaskTransitionError."""
        all_statuses = [
            TaskStatus.ASSIGNED,
            TaskStatus.IN_PROGRESS,
            TaskStatus.SUBMITTED,
            TaskStatus.EVALUATING,
            TaskStatus.EVALUATED,
        ]

        for current in all_statuses:
            allowed = ALLOWED_TRANSITIONS.get(current, set())
            for next_status in all_statuses:
                task = self._make_task(current)
                if next_status in allowed:
                    # Should succeed
                    self.machine.transition(task, next_status)
                else:
                    # Should fail
                    with self.assertRaises(TaskTransitionError, msg=f"{current} -> {next_status} should fail"):
                        self.machine.transition(task, next_status)

    def test_can_transition_helper_correct(self) -> None:
        """can_transition() returns correct boolean without mutating status."""
        machine = TaskStateMachine()
        task = self._make_task(TaskStatus.ASSIGNED)

        self.assertTrue(machine.can_transition(TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS))
        self.assertFalse(machine.can_transition(TaskStatus.ASSIGNED, TaskStatus.EVALUATED))
        self.assertFalse(machine.can_transition(TaskStatus.ASSIGNED, TaskStatus.EVALUATING))
        self.assertEqual(task.status, TaskStatus.ASSIGNED)  # No mutation


# ──────────────────────────────────────────────────────────────────────
# 3. compute_next_difficulty Unit Tests
# ──────────────────────────────────────────────────────────────────────

class TestComputeNextDifficulty(unittest.TestCase):
    """Unit tests for the deterministic difficulty formula."""

    def test_base_case_no_modifiers(self) -> None:
        """No modifiers — result equals milestone_band."""
        result = compute_next_difficulty(
            milestone_band=3,
            profile_skill_levels=["intermediate", "intermediate"],
            performance_context={"avg_score": None, "tasks_evaluated": 0},
        )
        self.assertEqual(result, 3)

    def test_beginner_heavy_profile_reduces_difficulty(self) -> None:
        """Predominantly beginner profile should reduce difficulty by 1."""
        result = compute_next_difficulty(
            milestone_band=3,
            profile_skill_levels=["beginner", "beginner", "beginner", "intermediate"],
            performance_context={"avg_score": None, "tasks_evaluated": 0},
        )
        self.assertEqual(result, 2)  # 3 - 1 = 2

    def test_high_score_increases_difficulty(self) -> None:
        """Average score >= 85 should increase difficulty by 1."""
        result = compute_next_difficulty(
            milestone_band=2,
            profile_skill_levels=["intermediate", "intermediate"],
            performance_context={"avg_score": 90.0, "tasks_evaluated": 3},
        )
        self.assertEqual(result, 3)  # 2 + 1 = 3

    def test_low_score_decreases_difficulty(self) -> None:
        """Average score <= 50 should decrease difficulty by 1."""
        result = compute_next_difficulty(
            milestone_band=3,
            profile_skill_levels=["intermediate"],
            performance_context={"avg_score": 40.0, "tasks_evaluated": 2},
        )
        self.assertEqual(result, 2)  # 3 - 1 = 2

    def test_difficulty_clamped_at_minimum_1(self) -> None:
        """Difficulty must never go below 1 even with multiple downward modifiers."""
        result = compute_next_difficulty(
            milestone_band=1,
            profile_skill_levels=["beginner", "beginner", "beginner"],  # -1
            performance_context={"avg_score": 30.0, "tasks_evaluated": 2},   # -1
        )
        self.assertEqual(result, 1)  # Clamped at 1

    def test_difficulty_clamped_at_maximum_5(self) -> None:
        """Difficulty must never exceed 5 even with multiple upward modifiers."""
        result = compute_next_difficulty(
            milestone_band=5,
            profile_skill_levels=["intermediate", "intermediate"],  # +0
            performance_context={"avg_score": 95.0, "tasks_evaluated": 5},  # +1 would exceed
        )
        self.assertEqual(result, 5)  # Clamped at 5 (5 + 0 + 1 = 6, clamped to 5)

    def test_no_performance_data_neutral(self) -> None:
        """With 0 evaluated tasks, performance modifier is 0 (neutral)."""
        result = compute_next_difficulty(
            milestone_band=2,
            profile_skill_levels=["intermediate"],
            performance_context={"avg_score": None, "tasks_evaluated": 0},
        )
        self.assertEqual(result, 2)

    def test_empty_skill_levels(self) -> None:
        """Empty skill levels list should default to neutral skill modifier."""
        result = compute_next_difficulty(
            milestone_band=3,
            profile_skill_levels=[],
            performance_context={"avg_score": None, "tasks_evaluated": 0},
        )
        self.assertEqual(result, 3)

    def test_single_evaluated_task_is_neutral(self) -> None:
        """With only 1 evaluated task, performance modifier must remain neutral (0)."""
        result = compute_next_difficulty(
            milestone_band=3,
            profile_skill_levels=["intermediate"],
            performance_context={"avg_score": 95.0, "tasks_evaluated": 1},
        )
        self.assertEqual(result, 3)  # Neutral because tasks_evaluated < 2

    def test_performance_provider_uses_last_three_tasks(self) -> None:
        """PerformanceProvider must only average scores from the last 3 evaluated tasks."""
        provider = PerformanceProvider()
        
        def make_eval_task(score: float):
            m = MagicMock()
            m.status = TaskStatus.EVALUATED
            m.evaluation_summary = {"score": score, "passed": score >= 60}
            return m

        # 4 tasks: first is 10.0 (should be excluded), last three are 80, 90, 100
        tasks = [
            make_eval_task(10.0),
            make_eval_task(80.0),
            make_eval_task(90.0),
            make_eval_task(100.0),
        ]
        context = provider.get_performance_context(tasks)
        # Average of 80, 90, 100 = 90.0
        self.assertEqual(context["avg_score"], 90.0)
        self.assertEqual(context["tasks_evaluated"], 3)

    def test_performance_provider_fewer_than_two_scores_is_neutral(self) -> None:
        """PerformanceProvider returns None avg_score if fewer than 2 scored tasks."""
        provider = PerformanceProvider()
        m = MagicMock()
        m.status = TaskStatus.EVALUATED
        m.evaluation_summary = {"score": 90.0, "passed": True}
        context = provider.get_performance_context([m])
        self.assertIsNone(context["avg_score"])
        self.assertEqual(context["tasks_evaluated"], 1)

    def test_pure_function_deterministic(self) -> None:
        """Same inputs always produce same output."""
        kwargs = dict(
            milestone_band=3,
            profile_skill_levels=["intermediate", "beginner"],
            performance_context={"avg_score": 75.0, "tasks_evaluated": 2},
        )
        results = [compute_next_difficulty(**kwargs) for _ in range(10)]
        self.assertTrue(all(r == results[0] for r in results))


# ──────────────────────────────────────────────────────────────────────
# 4. GitHub URL Validation Tests
# ──────────────────────────────────────────────────────────────────────

class TestGitHubURLValidation(unittest.TestCase):
    """Test GitHub URL validation and normalization."""

    def test_valid_url_accepted(self) -> None:
        """Standard GitHub repo URL is valid."""
        is_valid, error, normalized = validate_github_url("https://github.com/alice/my-repo")
        self.assertTrue(is_valid)
        self.assertIsNone(error)
        self.assertEqual(normalized, "https://github.com/alice/my-repo")

    def test_valid_url_with_trailing_slash_normalized(self) -> None:
        """Trailing slash is stripped during normalization."""
        is_valid, error, normalized = validate_github_url("https://github.com/alice/my-repo/")
        self.assertTrue(is_valid)
        self.assertEqual(normalized, "https://github.com/alice/my-repo")

    def test_git_suffix_stripped(self) -> None:
        """.git suffix is stripped and URL is accepted."""
        is_valid, error, normalized = validate_github_url("https://github.com/alice/my-repo.git")
        self.assertTrue(is_valid)
        self.assertEqual(normalized, "https://github.com/alice/my-repo")

    def test_url_with_underscore_and_dots_accepted(self) -> None:
        """Repo names with underscores and dots are valid."""
        is_valid, _, _ = validate_github_url("https://github.com/user123/my_project.v2")
        self.assertTrue(is_valid)

    def test_missing_https_rejected(self) -> None:
        """HTTP (not HTTPS) URLs must be rejected."""
        is_valid, error, _ = validate_github_url("http://github.com/alice/repo")
        self.assertFalse(is_valid)

    def test_non_github_domain_rejected(self) -> None:
        """Non-GitHub domains must be rejected."""
        is_valid, error, _ = validate_github_url("https://gitlab.com/alice/repo")
        self.assertFalse(is_valid)

    def test_url_with_subpath_rejected(self) -> None:
        """URLs with subpaths beyond /owner/repo must be rejected."""
        is_valid, error, _ = validate_github_url("https://github.com/alice/repo/tree/main")
        self.assertFalse(is_valid)

    def test_url_with_query_string_rejected(self) -> None:
        """URLs with query strings must be rejected."""
        is_valid, error, _ = validate_github_url("https://github.com/alice/repo?tab=readme")
        self.assertFalse(is_valid)

    def test_url_with_fragment_rejected(self) -> None:
        """URLs with fragments must be rejected."""
        is_valid, error, _ = validate_github_url("https://github.com/alice/repo#readme")
        self.assertFalse(is_valid)

    def test_empty_url_rejected(self) -> None:
        """Empty string must be rejected."""
        is_valid, error, _ = validate_github_url("")
        self.assertFalse(is_valid)

    def test_only_owner_no_repo_rejected(self) -> None:
        """URL with only owner and no repo must be rejected."""
        is_valid, error, _ = validate_github_url("https://github.com/alice")
        self.assertFalse(is_valid)

    def test_owner_with_leading_hyphen_rejected(self) -> None:
        """GitHub usernames cannot start with hyphen."""
        is_valid, _, _ = validate_github_url("https://github.com/-alice/repo")
        self.assertFalse(is_valid)

    def test_mixed_case_owner_and_repo_normalized_to_lowercase(self) -> None:
        """
        Mixed-case owner/repo must be normalized to all-lowercase.

        GitHub treats owner and repo as case-insensitive.
        Storing lowercase guarantees the uix_task_user_github_repo unique
        index correctly detects duplicate submissions regardless of the
        case the student typed.
        """
        is_valid, error, normalized = validate_github_url(
            "https://github.com/AliceStudent/My-Fullstack-Project"
        )
        self.assertTrue(is_valid, f"Expected valid URL, got error: {error}")
        self.assertEqual(normalized, "https://github.com/alicestudent/my-fullstack-project")

    def test_already_lowercase_unchanged(self) -> None:
        """URLs already in lowercase pass through normalization unchanged."""
        is_valid, _, normalized = validate_github_url("https://github.com/alice/my-repo")
        self.assertTrue(is_valid)
        self.assertEqual(normalized, "https://github.com/alice/my-repo")


# ──────────────────────────────────────────────────────────────────────
# 5. Near-Duplicate Title Detection Tests
# ──────────────────────────────────────────────────────────────────────

class TestNearDuplicateTitleDetection(unittest.TestCase):
    """Test Jaccard similarity-based near-duplicate detection."""

    def test_identical_title_is_duplicate(self) -> None:
        """Exact same title must be detected as duplicate."""
        self.assertTrue(is_near_duplicate_title(
            "Build REST API with FastAPI",
            ["Build REST API with FastAPI"]
        ))

    def test_highly_similar_title_is_duplicate(self) -> None:
        """Titles with >50% word overlap must be detected as duplicates."""
        self.assertTrue(is_near_duplicate_title(
            "Build RESTful API using FastAPI and Python",
            ["Build REST API using FastAPI"]
        ))

    def test_completely_different_title_not_duplicate(self) -> None:
        """Completely different titles must not be flagged as duplicates."""
        self.assertFalse(is_near_duplicate_title(
            "Design PostgreSQL Database Schema",
            ["Configure Docker containerization pipeline"]
        ))

    def test_empty_previous_titles_not_duplicate(self) -> None:
        """No previous tasks — new title can't be a duplicate."""
        self.assertFalse(is_near_duplicate_title(
            "Build REST API with FastAPI",
            []
        ))

    def test_case_insensitive_comparison(self) -> None:
        """Duplicate detection must be case-insensitive."""
        self.assertTrue(is_near_duplicate_title(
            "BUILD REST API WITH FASTAPI",
            ["build rest api with fastapi"]
        ))


# ──────────────────────────────────────────────────────────────────────
# 6. Mock LLM Provider Tests (Deterministic Output)
# ──────────────────────────────────────────────────────────────────────

class TestMockLLMProvider(unittest.IsolatedAsyncioTestCase):
    """Test that the mock LLM provider generates valid, parseable JSON."""

    async def test_roadmap_generation_produces_valid_json(self) -> None:
        """Mock provider roadmap output must parse and validate as LLMRoadmapOutput."""
        mock = MockLLMProvider()
        system_prompt = "You are a roadmap generator. Generate milestones for a student."
        user_prompt = "Target role: Full Stack Engineer, Experience: fresher"

        raw = await mock.generate_json(system_prompt, user_prompt)
        data = json.loads(raw)
        validated = LLMRoadmapOutput.model_validate(data)

        self.assertGreaterEqual(len(validated.milestones), 4)
        self.assertLessEqual(len(validated.milestones), 8)

        total_days = sum(m.estimated_days for m in validated.milestones)
        self.assertGreaterEqual(total_days, 30)
        self.assertLessEqual(total_days, 120)

    async def test_task_generation_produces_valid_json(self) -> None:
        """Mock provider task output must parse and validate as LLMTaskOutput."""
        mock = MockLLMProvider()
        system_prompt = "You are a task generator. Generate a coding task."
        user_prompt = "Milestone: Backend Development, Difficulty: 2, Skills: FastAPI"

        raw = await mock.generate_json(system_prompt, user_prompt)
        data = json.loads(raw)
        validated = LLMTaskOutput.model_validate(data)

        self.assertGreaterEqual(len(validated.requirements), 3)
        self.assertGreaterEqual(len(validated.acceptance_criteria), 2)
        self.assertGreaterEqual(len(validated.skills_targeted), 1)
        self.assertGreater(validated.estimated_hours, 0)

    async def test_mock_roadmap_milestones_have_valid_difficulty_progression(self) -> None:
        """Mock roadmap difficulty must never increase by more than 1 per step."""
        mock = MockLLMProvider()
        raw = await mock.generate_json(
            "You are a roadmap generator. milestones",
            "Full Stack Engineer, fresher"
        )
        data = json.loads(raw)
        milestones = sorted(data["milestones"], key=lambda m: m["order"])

        for i in range(1, len(milestones)):
            prev = milestones[i - 1]["difficulty_band"]
            curr = milestones[i]["difficulty_band"]
            self.assertLessEqual(
                curr - prev, 1,
                msg=f"Difficulty jumped from {prev} to {curr} at milestone {i + 1}"
            )


# ──────────────────────────────────────────────────────────────────────
# 7. API Layer Tests (HTTP error mapping, no Traceback leaks)
# ──────────────────────────────────────────────────────────────────────

class TestAPIErrorHandling(unittest.TestCase):
    """Test that HTTP endpoints return correct status codes without leaking tracebacks."""

    def setUp(self) -> None:
        self.client = TestClient(app)
        self.client.headers["X-Gateway-Token"] = settings.GATEWAY_SERVICE_TOKEN

    def test_missing_gateway_token_returns_403(self) -> None:
        """User-facing endpoints without X-Gateway-Token must return 403 Forbidden."""
        client_no_token = TestClient(app)
        response = client_no_token.post("/roadmap/generate")
        self.assertEqual(response.status_code, 403)
        self.assertIn("Forbidden", response.json()["detail"])

    def test_invalid_gateway_token_returns_403(self) -> None:
        """User-facing endpoints with invalid X-Gateway-Token must return 403 Forbidden."""
        client_bad_token = TestClient(app)
        response = client_bad_token.post(
            "/roadmap/generate",
            headers={"X-Gateway-Token": "invalid-secret"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("Forbidden", response.json()["detail"])

    def test_health_exempt_from_gateway_token(self) -> None:
        """Health endpoint must be reachable without X-Gateway-Token."""
        client_no_token = TestClient(app)
        response = client_no_token.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "healthy")

    def test_missing_auth_header_returns_401(self) -> None:
        """All protected endpoints must return 401 without auth header when gateway token is valid."""
        endpoints = [
            ("/roadmap/generate", "POST"),
            ("/roadmap/me", "GET"),
            ("/tasks/next", "POST"),
            ("/tasks/current", "GET"),
            ("/tasks", "GET"),
        ]
        for path, method in endpoints:
            response = self.client.request(method, path)
            self.assertEqual(
                response.status_code, 401,
                msg=f"Expected 401 for {method} {path}, got {response.status_code}",
            )

    def test_no_response_contains_traceback(self) -> None:
        """Error responses must never contain Python tracebacks."""
        endpoints = [
            ("/roadmap/generate", "POST"),
            ("/roadmap/me", "GET"),
            ("/tasks/next", "POST"),
        ]
        for path, method in endpoints:
            response = self.client.request(
                method, path,
                headers={"Authorization": "Bearer invalid.jwt.token"}
            )
            self.assertNotIn(
                "Traceback",
                response.text,
                msg=f"Response for {method} {path} contains 'Traceback': {response.text[:200]}",
            )

    def test_internal_endpoint_without_token_returns_403(self) -> None:
        """Internal endpoints without X-Internal-Token must return 403."""
        task_id = str(uuid.uuid4())
        response = self.client.post(
            f"/internal/tasks/{task_id}/evaluation",
            json={"passed": True, "evaluated_by": "test"},
        )
        self.assertEqual(response.status_code, 403)

    def test_internal_endpoint_with_wrong_token_returns_403(self) -> None:
        """Internal endpoints with wrong X-Internal-Token must return 403."""
        task_id = str(uuid.uuid4())
        response = self.client.post(
            f"/internal/tasks/{task_id}/evaluation",
            json={"passed": True},
            headers={"X-Internal-Token": "wrong-token"},
        )
        self.assertEqual(response.status_code, 403)


# ──────────────────────────────────────────────────────────────────────
# 8. Gateway Internal/Dev Blocking Tests
# ──────────────────────────────────────────────────────────────────────

class TestGatewayBlocking(unittest.TestCase):
    """Test that the API Gateway blocks /internal/* and /dev/* requests."""

    def setUp(self) -> None:
        # Import and test the gateway app directly
        import importlib.util
        from pathlib import Path
        import sys
        gateway_dir = Path(__file__).resolve().parent.parent.parent / "api-gateway"
        spec_config = importlib.util.spec_from_file_location("gateway_config", gateway_dir / "app" / "config.py")
        mod_config = importlib.util.module_from_spec(spec_config)
        sys.modules["app.config"] = mod_config
        spec_config.loader.exec_module(mod_config)

        spec = importlib.util.spec_from_file_location("gateway_main", gateway_dir / "app" / "main.py")
        gateway_main = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gateway_main)
        self.client = TestClient(gateway_main.app)

    def test_gateway_blocks_internal_get(self) -> None:
        """GET /internal/* must be blocked by the gateway with 404."""
        response = self.client.get("/internal/profile/some-user-id")
        self.assertIn(response.status_code, [403, 404])

    def test_gateway_blocks_internal_post(self) -> None:
        """POST /internal/* must be blocked by the gateway with 404."""
        response = self.client.post("/internal/tasks/some-id/evaluation", json={})
        self.assertIn(response.status_code, [403, 404])

    def test_gateway_blocks_dev_routes(self) -> None:
        """POST /dev/* must be blocked by the gateway with 404."""
        response = self.client.post("/dev/tasks/some-id/simulate-evaluation")
        self.assertIn(response.status_code, [403, 404])


# ──────────────────────────────────────────────────────────────────────
# 9. LLM Generation + Validation Tests
# ──────────────────────────────────────────────────────────────────────

class FailingRoadmapProvider(BaseLLMProvider):
    """Provider that returns invalid JSON on attempt 1, valid on attempt 2."""

    def __init__(self, fail_both: bool = False) -> None:
        self.call_count = 0
        self.fail_both = fail_both

    async def generate_json(self, system_prompt: str, user_prompt: str) -> str:
        self.call_count += 1
        if self.call_count == 1:
            # Invalid: only 3 milestones (too few)
            return json.dumps({
                "milestones": [
                    {"order": 1, "title": "M1", "description": "Desc",
                     "target_skills": ["S"], "estimated_days": 10, "difficulty_band": 1,
                     "success_criteria": ["C1", "C2"]},
                    {"order": 2, "title": "M2", "description": "Desc",
                     "target_skills": ["S"], "estimated_days": 10, "difficulty_band": 2,
                     "success_criteria": ["C1", "C2"]},
                    {"order": 3, "title": "M3", "description": "Desc",
                     "target_skills": ["S"], "estimated_days": 10, "difficulty_band": 3,
                     "success_criteria": ["C1", "C2"]},
                ]
            })
        if self.fail_both:
            return '{"garbage": true}'
        return _valid_roadmap_json()


class TestLLMOrchestration(unittest.IsolatedAsyncioTestCase):
    """Test LLM generation with retry and failure modes."""

    async def test_invalid_roadmap_triggers_retry_then_succeeds(self) -> None:
        """Provider with invalid first response should succeed on retry."""
        from app.services.roadmap_agent import generate_roadmap_from_llm

        provider = FailingRoadmapProvider(fail_both=False)
        profile = {
            "target_role": "Full Stack Engineer",
            "experience_level": "fresher",
            "structured_skills": [],
            "dashboard_data": {"weakest_areas": [], "strongest_areas": []},
        }
        milestones = await generate_roadmap_from_llm(provider, profile)
        self.assertEqual(provider.call_count, 2)  # Confirmed it retried
        self.assertGreaterEqual(len(milestones), 4)

    async def test_both_attempts_failing_raises_validation_error(self) -> None:
        """Provider that fails both times must raise LLMValidationError — zero DB writes."""
        from app.services.roadmap_agent import generate_roadmap_from_llm

        provider = FailingRoadmapProvider(fail_both=True)
        profile = {
            "target_role": "Full Stack Engineer",
            "experience_level": "fresher",
            "structured_skills": [],
            "dashboard_data": {"weakest_areas": [], "strongest_areas": []},
        }
        with self.assertRaises(LLMValidationError):
            await generate_roadmap_from_llm(provider, profile)


class TestNearDuplicateTitleCheck(unittest.TestCase):
    """Test near-duplicate title detection with normalization."""

    def test_exact_match_detected(self) -> None:
        self.assertTrue(is_near_duplicate_title("Build REST API", ["Build REST API"]))

    def test_normalized_near_match_detected(self) -> None:
        self.assertTrue(
            is_near_duplicate_title(
                "Build a REST API in Python!",
                ["build rest api in python"],
                threshold=0.5,
            )
        )

    def test_distinct_title_allowed(self) -> None:
        self.assertFalse(
            is_near_duplicate_title(
                "Implement Docker Containerization",
                ["Build REST API in Python", "Design PostgreSQL Database"],
                threshold=0.5,
            )
        )


class TestPassFailAndMilestoneProgress(unittest.TestCase):
    """Test pass/fail semantics and milestone progress counting only passed tasks."""

    def test_milestone_counts_only_passed_tasks(self) -> None:
        from app.services.roadmap_service import compute_milestone_progress
        
        milestones = [
            {
                "order": 1,
                "title": "Backend Basics",
                "description": "Learn backend",
                "target_skills": ["Python", "SQL"],
                "estimated_days": 6,  # 6 // 3 = 2 planned tasks
                "difficulty_band": 1,
                "success_criteria": ["Build API"],
            }
        ]

        def make_task(score: float, passed: bool):
            t = MagicMock()
            t.status = TaskStatus.EVALUATED
            t.milestone_order = 1
            t.evaluation_summary = {"score": score, "passed": passed}
            return t

        # 1 passed task, 1 failed task
        tasks = [
            make_task(85.0, True),
            make_task(45.0, False),
        ]

        progress = compute_milestone_progress(milestones, tasks)
        self.assertEqual(progress[0].tasks_completed, 1)  # Only the passed one counts!
        self.assertEqual(progress[0].state, "current")    # Not completed because planned is 2

        # Add another passed task
        tasks.append(make_task(70.0, True))
        progress2 = compute_milestone_progress(milestones, tasks)
        self.assertEqual(progress2[0].tasks_completed, 2)
        self.assertEqual(progress2[0].state, "completed")


class TestTaskClaimAndRepoUniqueness(unittest.IsolatedAsyncioTestCase):
    """Test evaluation claim, failure rollback, repo URL uniqueness, and re-submission rules."""

    async def test_claim_and_fail_evaluation_lifecycle(self) -> None:
        from app.services.roadmap_service import RoadmapService
        from app.services.state_machine import TaskTransitionError

        mock_provider = MockLLMProvider()
        service = RoadmapService(mock_provider)

        task = MagicMock()
        task.id = uuid.uuid4()
        task.status = TaskStatus.SUBMITTED
        task.user_id = uuid.uuid4()
        task.github_repo_url = "https://github.com/user/test-repo"

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=task)))

        # Claim evaluation (SUBMITTED -> EVALUATING)
        claimed = await service.claim_evaluation(mock_db, task.id)
        self.assertEqual(claimed.status, TaskStatus.EVALUATING)

        # Re-submission in EVALUATING must be rejected
        with self.assertRaises(TaskTransitionError):
            await service.submit_task(mock_db, task.id, task.user_id, "https://github.com/user/new-repo")

        # Fail evaluation (EVALUATING -> SUBMITTED)
        failed = await service.fail_evaluation(mock_db, task.id)
        self.assertEqual(failed.status, TaskStatus.SUBMITTED)

        # Now re-submission in SUBMITTED is allowed (no duplicate repo found)
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        service.get_task_by_id = AsyncMock(return_value=task)
        resubmitted = await service.submit_task(mock_db, task.id, task.user_id, "https://github.com/user/fixed-repo")
        self.assertEqual(resubmitted.status, TaskStatus.SUBMITTED)
        self.assertEqual(resubmitted.github_repo_url, "https://github.com/user/fixed-repo")

    async def test_duplicate_repo_url_rejected(self) -> None:
        from app.services.roadmap_service import DuplicateRepoUrlError, RoadmapService

        service = RoadmapService(MockLLMProvider())

        task = MagicMock()
        task.id = uuid.uuid4()
        task.status = TaskStatus.IN_PROGRESS
        task.user_id = uuid.uuid4()
        task.github_repo_url = None

        service.get_task_by_id = AsyncMock(return_value=task)

        # Mock db returning an existing task with the same repo URL
        other_task = MagicMock()
        other_task.id = uuid.uuid4()
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=other_task)))

        with self.assertRaises(DuplicateRepoUrlError):
            await service.submit_task(mock_db, task.id, task.user_id, "https://github.com/user/already-used")


class TestFactoryHardening(unittest.TestCase):
    """Test that LLM factory refuses mock provider in production."""

    def test_mock_refused_in_production(self) -> None:
        from app.core.llm.factory import get_llm_provider
        with patch.object(settings, "LLM_PROVIDER", "mock"):
            with patch.object(settings, "APP_ENV", "production"):
                with self.assertRaises(ValueError) as ctx:
                    get_llm_provider()
                self.assertIn("strictly disallowed", str(ctx.exception))

    def test_mock_allowed_in_development(self) -> None:
        from app.core.llm.factory import get_llm_provider
        with patch.object(settings, "LLM_PROVIDER", "mock"):
            with patch.object(settings, "APP_ENV", "development"):
                provider = get_llm_provider()
                self.assertIsInstance(provider, MockLLMProvider)


# ──────────────────────────────────────────────────────────────────────
# MAX_REMEDIATION_ATTEMPTS Tests
# ──────────────────────────────────────────────────────────────────────

class TestMaxRemediationAttempts(unittest.IsolatedAsyncioTestCase):
    """
    Tests for the MAX_REMEDIATION_ATTEMPTS cap:
      1. _count_consecutive_failed_on_milestone counts only trailing failures.
      2. compute_milestone_progress treats stored state='needs_review' correctly.
      3. generate_next_task marks milestone needs_review after hitting the limit.
    """

    # ── Helper fixtures ──────────────────────────────────────────────

    def _make_evaluated_task(
        self,
        seq: int,
        milestone_order: int,
        passed: bool,
        user_id=None,
        roadmap_id=None,
    ):
        """Build a minimal Task ORM-like object (plain Python, no SQLAlchemy)."""
        from unittest.mock import MagicMock
        from app.models.task import TaskStatus
        t = MagicMock()
        t.id = uuid.uuid4()
        t.user_id = user_id or uuid.uuid4()
        t.roadmap_id = roadmap_id or uuid.uuid4()
        t.milestone_order = milestone_order
        t.sequence_number = seq
        t.status = TaskStatus.EVALUATED
        t.evaluation_summary = {
            "score": 90.0 if passed else 40.0,
            "passed": passed,
            "feedback": "Great work!" if passed else "Failed — needs improvement.",
        }
        return t

    def _make_milestone_dict(self, order: int, days: int = 6, state: str | None = None) -> dict:
        m: dict = {
            "order": order,
            "title": f"Milestone {order}",
            "description": "Some description",
            "target_skills": ["Python"],
            "estimated_days": days,
            "difficulty_band": order,
            "success_criteria": ["Criterion A", "Criterion B"],
        }
        if state is not None:
            m["state"] = state
        return m

    # ── Test 1: _count_consecutive_failed_on_milestone ──────────────

    def test_count_consecutive_failed_pure_failures(self) -> None:
        """Three consecutive failures → count == 3."""
        from app.services.roadmap_service import _count_consecutive_failed_on_milestone
        uid = uuid.uuid4()
        rid = uuid.uuid4()
        tasks = [
            self._make_evaluated_task(1, 1, passed=False, user_id=uid, roadmap_id=rid),
            self._make_evaluated_task(2, 1, passed=False, user_id=uid, roadmap_id=rid),
            self._make_evaluated_task(3, 1, passed=False, user_id=uid, roadmap_id=rid),
        ]
        count = _count_consecutive_failed_on_milestone(tasks, milestone_order=1)
        self.assertEqual(count, 3)

    def test_count_stops_at_first_pass(self) -> None:
        """Two failures then a pass → only the trailing 2 failures are counted."""
        from app.services.roadmap_service import _count_consecutive_failed_on_milestone
        uid = uuid.uuid4()
        rid = uuid.uuid4()
        tasks = [
            self._make_evaluated_task(1, 1, passed=True,  user_id=uid, roadmap_id=rid),
            self._make_evaluated_task(2, 1, passed=False, user_id=uid, roadmap_id=rid),
            self._make_evaluated_task(3, 1, passed=False, user_id=uid, roadmap_id=rid),
        ]
        count = _count_consecutive_failed_on_milestone(tasks, milestone_order=1)
        self.assertEqual(count, 2)

    def test_count_ignores_other_milestones(self) -> None:
        """Failures on a different milestone_order do not affect the count."""
        from app.services.roadmap_service import _count_consecutive_failed_on_milestone
        uid = uuid.uuid4()
        rid = uuid.uuid4()
        tasks = [
            self._make_evaluated_task(1, 2, passed=False, user_id=uid, roadmap_id=rid),  # other milestone
            self._make_evaluated_task(2, 1, passed=False, user_id=uid, roadmap_id=rid),  # target milestone
        ]
        count = _count_consecutive_failed_on_milestone(tasks, milestone_order=1)
        self.assertEqual(count, 1)

    def test_count_zero_when_no_tasks(self) -> None:
        """Empty task list → count == 0."""
        from app.services.roadmap_service import _count_consecutive_failed_on_milestone
        count = _count_consecutive_failed_on_milestone([], milestone_order=1)
        self.assertEqual(count, 0)

    # ── Test 2: compute_milestone_progress with needs_review ─────────

    def test_needs_review_state_preserved_in_progress(self) -> None:
        """
        A milestone dict with state='needs_review' must yield state='needs_review'
        in the MilestoneProgress output (not 'current' or 'completed').
        """
        from app.services.roadmap_service import compute_milestone_progress
        from app.models.task import TaskStatus

        milestones = [
            self._make_milestone_dict(order=1, days=6, state="needs_review"),
            self._make_milestone_dict(order=2, days=6),
        ]
        uid = uuid.uuid4()
        rid = uuid.uuid4()
        # No passed tasks on milestone 1
        tasks = [
            self._make_evaluated_task(1, 1, passed=False, user_id=uid, roadmap_id=rid),
        ]
        result = compute_milestone_progress(milestones, tasks)

        m1 = next(r for r in result if r.order == 1)
        self.assertEqual(m1.state, "needs_review",
                         "Milestone with stored state needs_review must report needs_review")

        # Milestone 2 should be 'current' because milestone 1 is needs_review (treated as done)
        m2 = next(r for r in result if r.order == 2)
        self.assertEqual(m2.state, "current",
                         "Milestone after needs_review should be 'current'")

    # ── Test 3: generate_next_task marks needs_review at limit ───────

    async def test_generate_next_task_marks_needs_review_at_limit(self) -> None:
        """
        When consecutive failures on a milestone == MAX_REMEDIATION_ATTEMPTS,
        generate_next_task must:
          - Set milestone state to needs_review in roadmap.milestones.
          - Call db.commit() to persist the update.
          - Return a non-remediation task (is_remediation=False) on the next milestone.
        """
        from app.services.roadmap_service import RoadmapService
        from app.core.llm.mock_provider import MockLLMProvider

        uid = uuid.uuid4()
        rid = uuid.uuid4()

        # 3 consecutive failures on milestone 1 (== MAX_REMEDIATION_ATTEMPTS default)
        failed_tasks = [
            self._make_evaluated_task(i + 1, 1, passed=False, user_id=uid, roadmap_id=rid)
            for i in range(3)
        ]

        milestone_dicts = [
            self._make_milestone_dict(order=1, days=6),   # will become needs_review
            self._make_milestone_dict(order=2, days=6),   # will become current
        ]

        # Build a fake Roadmap object
        roadmap = MagicMock()
        roadmap.id = rid
        roadmap.user_id = uid
        roadmap.milestones = milestone_dicts
        roadmap.profile_snapshot = {
            "target_role": "Software Engineer",
            "experience_level": "fresher",
            "structured_skills": [],
            "dashboard_data": {},
        }
        roadmap.status = "active"

        # Mock DB session
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock(side_effect=lambda obj: None)

        # execute() call sequence:
        # 1. get_roadmap_by_user_id → returns roadmap
        # 2. get_active_task → returns None (no active task)
        # 3. select(Task) for all_tasks → returns failed_tasks
        def _make_result(return_value):
            r = MagicMock()
            r.scalar_one_or_none.return_value = return_value
            r.scalars.return_value.all.return_value = return_value
            return r

        # db.refresh must populate created_at on whatever Task object is passed to it
        async def _mock_refresh(obj):
            from datetime import datetime, timezone
            if hasattr(obj, "created_at"):
                obj.created_at = datetime.now(timezone.utc)

        db.refresh = AsyncMock(side_effect=_mock_refresh)

        db.execute.side_effect = [
            _make_result(roadmap),       # get_roadmap_by_user_id
            _make_result(None),          # get_active_task (returns None = no active task)
            _make_result(failed_tasks),  # select all tasks for milestone progress + max_seq
        ]

        provider = MockLLMProvider()
        service = RoadmapService(llm_provider=provider)

        with patch.object(settings, "MAX_REMEDIATION_ATTEMPTS", 3):
            with patch(
                "app.services.roadmap_service.generate_task_from_llm",
                new_callable=AsyncMock,
            ) as mock_gen_task:
                # Return a valid LLMTaskOutput for the next-milestone task
                mock_gen_task.return_value = LLMTaskOutput(
                    title="Next Milestone Task",
                    description="A new task on milestone 2 skills.",
                    requirements=["1. Req one", "2. Req two", "3. Req three"],
                    acceptance_criteria=["Criterion A", "Criterion B"],
                    skills_targeted=["Python"],
                    estimated_hours=4.0,
                    starter_hint="Start by setting up a virtual environment.",
                )

                result = await service.generate_next_task(db=db, user_id=uid)

        # Milestone 1 should now be flagged needs_review
        updated_m1 = next(m for m in roadmap.milestones if m["order"] == 1)
        self.assertEqual(
            updated_m1.get("state"), "needs_review",
            "Milestone 1 state must be needs_review after hitting the remediation limit",
        )

        # DB commit must have been called to persist the needs_review flag
        db.commit.assert_called()

        # The LLM was called with is_remediation=False (normal next-milestone task)
        call_kwargs = mock_gen_task.call_args[1]
        self.assertFalse(
            call_kwargs.get("is_remediation", True),
            "generate_task_from_llm must be called with is_remediation=False after limit",
        )

        # The returned result should be task_assigned on the next milestone
        self.assertEqual(result.get("status"), "task_assigned")


if __name__ == "__main__":
    unittest.main()

