"""
Unit and Integration tests for Agent 1 (Profile & Dashboard Agent).

Tests:
1. LLM structured extraction with valid responses.
2. 1-shot retry on schema validation failure.
3. Exception raising when retry also fails (no silent garbage storage).
4. Deterministic readiness score formula & explainable summary generation.
5. Profile locking & rejection of duplicate onboarding submissions.
6. Race condition safety: IntegrityError on concurrent insert returns 403.
7. Transaction atomicity: LLM failure ensures zero database inserts/commits.
8. End-to-end HTTP error mapping for LLM timeouts, provider errors, and validation errors.
"""

import asyncio
import json
import uuid
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core.llm.base import (
    BaseLLMProvider,
    LLMProviderError,
    LLMTimeoutError,
    LLMValidationError,
)
from app.core.llm.mock_provider import MockLLMProvider
from app.db.session import get_db
from app.main import app
from app.routers.profile import get_profile_service
from app.schemas.profile import (
    EducationInfo,
    OnboardingRequest,
    SkillItem,
    StructuredSkillsOutput,
)
from app.services.profile_agent import (
    calculate_dashboard_data,
    extract_structured_skills,
)
from app.services.profile_service import (
    ProfileAlreadyExistsError,
    ProfileService,
)


class DummyFailingProvider(BaseLLMProvider):
    """Provider that returns invalid JSON on attempt 1, and valid JSON on attempt 2."""

    def __init__(self, fail_both: bool = False) -> None:
        self.call_count = 0
        self.fail_both = fail_both

    async def generate_json(self, system_prompt: str, user_prompt: str) -> str:
        self.call_count += 1
        if self.call_count == 1:
            # Malformed JSON / missing required keys
            return '{"invalid_key": "not a list of skills"}'
        if self.fail_both:
            return "Totally unparseable garbage {{"
        # Valid JSON on retry
        return json.dumps({
            "skills": [
                {
                    "skill_name": "Python",
                    "category": "Languages",
                    "proficiency_level": "intermediate",
                    "confidence_score": 0.92,
                }
            ]
        })


class TestProfileAgentCoreLogic(unittest.IsolatedAsyncioTestCase):
    """Test Agent 1 LLM extraction, error correction retry, and scoring."""

    def setUp(self) -> None:
        self.education = EducationInfo(
            degree="B.Tech",
            branch="Computer Science",
            year=2025,
            institution="Indian Institute of Technology",
        )
        self.skills_desc = "I have built web apps using React and Python FastAPI, and used PostgreSQL."
        self.target_role = "Full Stack Engineer"
        self.experience_level = "fresher"

    async def test_mock_llm_provider_validity(self) -> None:
        """Verify MockLLMProvider produces JSON matching StructuredSkillsOutput."""
        provider = MockLLMProvider()
        raw_json = await provider.generate_json("system", self.skills_desc)
        data = json.loads(raw_json)
        validated = StructuredSkillsOutput.model_validate(data)
        self.assertGreater(len(validated.skills), 0)
        for s in validated.skills:
            self.assertIn(s.proficiency_level, ["beginner", "intermediate", "advanced"])
            self.assertTrue(0.0 <= s.confidence_score <= 1.0)

    async def test_extraction_success_primary_attempt(self) -> None:
        """Verify extraction succeeds on first attempt with mock provider."""
        provider = MockLLMProvider()
        skills = await extract_structured_skills(
            llm_provider=provider,
            education=self.education,
            skills_description=self.skills_desc,
            target_role=self.target_role,
            experience_level=self.experience_level,
        )
        self.assertIsInstance(skills, list)
        self.assertGreater(len(skills), 0)
        self.assertTrue(any(s.skill_name == "Python" for s in skills))
        self.assertTrue(any(s.skill_name == "React" for s in skills))

    async def test_one_shot_retry_on_validation_failure(self) -> None:
        """Verify 1-shot retry is triggered when primary response fails schema."""
        provider = DummyFailingProvider(fail_both=False)
        skills = await extract_structured_skills(
            llm_provider=provider,
            education=self.education,
            skills_description=self.skills_desc,
            target_role=self.target_role,
            experience_level=self.experience_level,
        )
        self.assertEqual(provider.call_count, 2)
        self.assertEqual(len(skills), 1)
        self.assertEqual(skills[0].skill_name, "Python")

    async def test_fatal_validation_failure_raises_exception(self) -> None:
        """Verify that if retry also fails, LLMValidationError is raised."""
        provider = DummyFailingProvider(fail_both=True)
        with self.assertRaises(LLMValidationError):
            await extract_structured_skills(
                llm_provider=provider,
                education=self.education,
                skills_description=self.skills_desc,
                target_role=self.target_role,
                experience_level=self.experience_level,
            )
        self.assertEqual(provider.call_count, 2)

    def test_deterministic_readiness_score(self) -> None:
        """Verify readiness score formula is deterministic, bounded, and explainable."""
        sample_skills = [
            SkillItem(skill_name="Python", category="Languages", proficiency_level="intermediate", confidence_score=0.9),
            SkillItem(skill_name="FastAPI", category="Backend", proficiency_level="intermediate", confidence_score=0.88),
            SkillItem(skill_name="PostgreSQL", category="Databases", proficiency_level="intermediate", confidence_score=0.85),
            SkillItem(skill_name="Docker", category="DevOps & Cloud", proficiency_level="beginner", confidence_score=0.8),
        ]
        dashboard_data = calculate_dashboard_data(
            skills=sample_skills,
            experience_level="fresher",
            target_role="Full Stack Engineer",
        )

        # Check bounds
        self.assertTrue(0 <= dashboard_data.readiness_score <= 100)
        # Check categories
        self.assertEqual(dashboard_data.skill_distribution["Languages"], 1)
        self.assertEqual(dashboard_data.skill_distribution["Backend"], 1)
        self.assertEqual(dashboard_data.skill_distribution["Databases"], 1)
        self.assertEqual(dashboard_data.skill_distribution["DevOps & Cloud"], 1)
        # Check explainability
        self.assertIn("Readiness Score:", dashboard_data.readiness_summary)
        self.assertIn("Skill Competency Depth", dashboard_data.readiness_summary)
        self.assertIn("Domain Diversity", dashboard_data.readiness_summary)
        self.assertIn("Experience Baseline", dashboard_data.readiness_summary)

    async def test_lock_mechanism_rejection(self) -> None:
        """Verify ProfileService rejects duplicate onboarding for existing locked profile."""
        mock_provider = MockLLMProvider()
        service = ProfileService(llm_provider=mock_provider)

        # Mock DB returning an existing locked profile
        fake_db = AsyncMock()
        existing_profile = MagicMock()
        existing_profile.is_locked = True
        service.get_by_user_id = AsyncMock(return_value=existing_profile)

        user_id = uuid.uuid4()
        req = OnboardingRequest(
            education=self.education,
            skills_description=self.skills_desc,
            target_role=self.target_role,
            experience_level="fresher",
        )

        with self.assertRaises(ProfileAlreadyExistsError) as ctx:
            await service.create_onboarding_profile(
                db=fake_db,
                user_id=user_id,
                request=req,
            )
        self.assertEqual(str(ctx.exception), "Profile already exists and is locked")

    async def test_race_condition_integrity_error_handling(self) -> None:
        """Verify race condition IntegrityError is caught and converted to 403 ProfileAlreadyExistsError."""
        mock_provider = MockLLMProvider()
        service = ProfileService(llm_provider=mock_provider)

        # Initial check returns None (race window)
        service.get_by_user_id = AsyncMock(return_value=None)

        # Simulated DB session where commit() raises IntegrityError
        fake_db = AsyncMock()
        fake_db.add = MagicMock()
        fake_db.commit = AsyncMock(
            side_effect=IntegrityError("duplicate key value violates unique constraint", params={}, orig=Exception())
        )
        fake_db.rollback = AsyncMock()

        user_id = uuid.uuid4()
        req = OnboardingRequest(
            education=self.education,
            skills_description=self.skills_desc,
            target_role=self.target_role,
            experience_level="fresher",
        )

        with self.assertRaises(ProfileAlreadyExistsError) as ctx:
            await service.create_onboarding_profile(
                db=fake_db,
                user_id=user_id,
                request=req,
            )

        self.assertEqual(ctx.exception.message, "Profile already exists and is locked")
        fake_db.rollback.assert_awaited_once()

    async def test_transaction_atomicity_on_llm_failure(self) -> None:
        """Confirm that if LLM call fails, NO row is inserted or committed to the database."""
        failing_provider = DummyFailingProvider(fail_both=True)
        service = ProfileService(llm_provider=failing_provider)
        service.get_by_user_id = AsyncMock(return_value=None)

        inserted_rows: list[MagicMock] = []
        fake_db = AsyncMock()

        def mock_add(row: MagicMock) -> None:
            inserted_rows.append(row)

        fake_db.add = MagicMock(side_effect=mock_add)
        fake_db.commit = AsyncMock()

        user_id = uuid.uuid4()
        req = OnboardingRequest(
            education=self.education,
            skills_description=self.skills_desc,
            target_role=self.target_role,
            experience_level="fresher",
        )

        # Expect LLMValidationError to abort the transaction
        with self.assertRaises(LLMValidationError):
            await service.create_onboarding_profile(
                db=fake_db,
                user_id=user_id,
                request=req,
            )

        # Assert zero rows were added or committed
        self.assertEqual(len(inserted_rows), 0)
        fake_db.add.assert_not_called()
        fake_db.commit.assert_not_called()


class TestLLMFailurePathsEndToEnd(unittest.TestCase):
    """Test client-facing HTTP status codes and clean error bodies for LLM failure modes."""

    def setUp(self) -> None:
        self.client = TestClient(app)
        self.user_id = str(uuid.uuid4())
        self.payload = {
            "education": {
                "degree": "B.Tech",
                "branch": "Computer Science",
                "year": 2025,
                "institution": "National Institute of Technology",
            },
            "skills_description": "Built web applications using React, Python, and PostgreSQL.",
            "target_role": "Full Stack Engineer",
            "experience_level": "fresher",
        }

        async def mock_get_db():
            yield AsyncMock()

        app.dependency_overrides[get_db] = mock_get_db

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_llm_timeout_returns_clean_504(self) -> None:
        """Simulate LLM API timeout and verify client gets clean 504 Gateway Timeout."""
        mock_service = MagicMock(spec=ProfileService)
        mock_service.create_onboarding_profile = AsyncMock(
            side_effect=LLMTimeoutError("OpenAI request timed out after 30s")
        )

        app.dependency_overrides[get_profile_service] = lambda: mock_service
        try:
            response = self.client.post(
                "/profile/onboarding",
                json=self.payload,
                headers={"X-User-Id": self.user_id},
            )
            self.assertEqual(response.status_code, 504)
            data = response.json()
            self.assertIn("AI Agent timed out", data["detail"])
            # Ensure no stack trace in response
            self.assertNotIn("Traceback", response.text)
        finally:
            app.dependency_overrides.clear()

    def test_llm_provider_error_returns_clean_503(self) -> None:
        """Simulate LLM invalid API key or provider outage and verify client gets clean 503."""
        mock_service = MagicMock(spec=ProfileService)
        mock_service.create_onboarding_profile = AsyncMock(
            side_effect=LLMProviderError("OpenAI API error: Incorrect API key provided")
        )

        app.dependency_overrides[get_profile_service] = lambda: mock_service
        try:
            response = self.client.post(
                "/profile/onboarding",
                json=self.payload,
                headers={"X-User-Id": self.user_id},
            )
            self.assertEqual(response.status_code, 503)
            data = response.json()
            self.assertIn("AI service is currently unavailable", data["detail"])
            self.assertNotIn("Traceback", response.text)
        finally:
            app.dependency_overrides.clear()

    def test_llm_validation_failure_returns_clean_502(self) -> None:
        """Simulate malformed LLM output persisting past retry and verify client gets clean 502."""
        mock_service = MagicMock(spec=ProfileService)
        mock_service.create_onboarding_profile = AsyncMock(
            side_effect=LLMValidationError("LLM output failed strict schema validation after retry")
        )

        app.dependency_overrides[get_profile_service] = lambda: mock_service
        try:
            response = self.client.post(
                "/profile/onboarding",
                json=self.payload,
                headers={"X-User-Id": self.user_id},
            )
            self.assertEqual(response.status_code, 502)
            data = response.json()
            self.assertIn("AI Agent produced an unparseable response after retry", data["detail"])
            self.assertNotIn("Traceback", response.text)
        finally:
            app.dependency_overrides.clear()

    def test_concurrent_integrity_error_returns_clean_403(self) -> None:
        """Simulate concurrent creation race and verify client gets 403 with locked profile message."""
        mock_service = MagicMock(spec=ProfileService)
        mock_service.create_onboarding_profile = AsyncMock(
            side_effect=ProfileAlreadyExistsError("Profile already exists and is locked")
        )

        app.dependency_overrides[get_profile_service] = lambda: mock_service
        try:
            response = self.client.post(
                "/profile/onboarding",
                json=self.payload,
                headers={"X-User-Id": self.user_id},
            )
            self.assertEqual(response.status_code, 403)
            data = response.json()
            self.assertEqual(data["detail"], "Profile already exists and is locked")
            self.assertNotIn("Traceback", response.text)
        finally:
            app.dependency_overrides.clear()


if __name__ == "__main__":
    unittest.main()
