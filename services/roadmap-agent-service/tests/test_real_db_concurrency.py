"""
Real-DB Integration Tests for Concurrency & Isolation in Roadmap Agent Service.

Tests:
1. 10 parallel POST /roadmap/generate -> exactly 1 roadmap (201), 9 clean 409.
2. 10 parallel POST /tasks/next -> exactly 1 task (200), 9 clean 409.
3. Verification that DB contains exactly 1 row each, and no response contains Traceback.
"""

import asyncio
import uuid
import pytest
import httpx
from unittest.mock import patch, AsyncMock
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

from app.core.config import settings
from app.main import app
import app.db.session as session_module
from app.services.profile_client import ProfileClient

REAL_DB_URL = "postgresql+asyncpg://roadmap_user:roadmap_pass@localhost:5435/roadmap_db"


@pytest.fixture(scope="module", autouse=True)
def configure_real_db_settings():
    """Point configuration to the real PostgreSQL database for this module."""
    old_url = settings.DATABASE_URL
    old_env = settings.APP_ENV
    old_provider = settings.LLM_PROVIDER

    settings.DATABASE_URL = REAL_DB_URL
    settings.APP_ENV = "development"
    settings.LLM_PROVIDER = "mock"

    yield

    settings.DATABASE_URL = old_url
    settings.APP_ENV = old_env
    settings.LLM_PROVIDER = old_provider


async def reset_session_engine():
    """Ensure engine is created within the running test's event loop."""
    if session_module._engine is not None:
        await session_module._engine.dispose()
    session_module._engine = None
    session_module._session_factory = None


async def cleanup_test_user(user_id: uuid.UUID):
    """Helper to remove tasks and roadmap for a test user."""
    engine = create_async_engine(REAL_DB_URL)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM tasks WHERE user_id = :uid"), {"uid": str(user_id)})
            await conn.execute(text("DELETE FROM roadmaps WHERE user_id = :uid"), {"uid": str(user_id)})
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_roadmap_generate_real_db():
    """
    10 parallel POST /roadmap/generate requests for the same user against real PostgreSQL:
    - Exactly 1 returns HTTP 201 Created.
    - Exactly 9 return HTTP 409 Conflict.
    - Exactly 1 roadmap row is persisted in the database.
    - Zero responses leak Python tracebacks.
    """
    await reset_session_engine()

    test_user_id = uuid.uuid4()
    headers = {
        "X-User-Id": str(test_user_id),
        "X-Gateway-Token": settings.GATEWAY_SERVICE_TOKEN,
    }

    mock_profile = {
        "user_id": str(test_user_id),
        "target_role": "Full Stack Engineer",
        "experience_level": "fresher",
        "learning_goal": "Learn modern scalable web development",
        "structured_skills": [
            {"name": "Python", "proficiency_level": "beginner", "verified": False},
            {"name": "FastAPI", "proficiency_level": "beginner", "verified": False},
        ],
    }

    try:
        with patch.object(ProfileClient, "get_profile", new_callable=AsyncMock) as mock_get_profile:
            mock_get_profile.return_value = mock_profile

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                # Fire 10 parallel requests simultaneously
                tasks = [
                    client.post("/roadmap/generate", headers=headers)
                    for _ in range(10)
                ]
                responses = await asyncio.gather(*tasks)

        # Analyze status codes
        status_codes = [r.status_code for r in responses]
        count_201 = status_codes.count(201)
        count_409 = status_codes.count(409)

        # Verify no tracebacks leaked
        for r in responses:
            assert "Traceback" not in r.text, f"Response leaked traceback: {r.text}"

        assert count_201 == 1, f"Expected exactly 1 201 response, got {count_201}. Statuses: {status_codes}"
        assert count_409 == 9, f"Expected exactly 9 409 responses, got {count_409}. Statuses: {status_codes}"

        # Verify real database state
        engine = create_async_engine(REAL_DB_URL)
        try:
            async with engine.connect() as conn:
                res = await conn.execute(
                    text("SELECT count(*) FROM roadmaps WHERE user_id = :uid"),
                    {"uid": str(test_user_id)},
                )
                db_count = res.scalar()
        finally:
            await engine.dispose()

        assert db_count == 1, f"Expected exactly 1 roadmap in real DB, found {db_count}"

    finally:
        await cleanup_test_user(test_user_id)
        await reset_session_engine()


@pytest.mark.asyncio
async def test_concurrent_tasks_next_real_db():
    """
    10 parallel POST /tasks/next requests for the same user against real PostgreSQL:
    - Precondition: User has a valid roadmap in the real DB.
    - Exactly 1 returns HTTP 200 OK (with task assigned).
    - Exactly 9 return HTTP 409 Conflict (active task already exists).
    - Exactly 1 task row is persisted in the database.
    - Zero responses leak Python tracebacks.
    """
    await reset_session_engine()

    test_user_id = uuid.uuid4()
    headers = {
        "X-User-Id": str(test_user_id),
        "X-Gateway-Token": settings.GATEWAY_SERVICE_TOKEN,
    }

    mock_profile = {
        "user_id": str(test_user_id),
        "target_role": "Full Stack Engineer",
        "experience_level": "fresher",
        "learning_goal": "Learn modern scalable web development",
        "structured_skills": [
            {"name": "Python", "proficiency_level": "beginner", "verified": False},
            {"name": "FastAPI", "proficiency_level": "beginner", "verified": False},
        ],
    }

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Create the roadmap first
            with patch.object(ProfileClient, "get_profile", new_callable=AsyncMock) as mock_get_profile:
                mock_get_profile.return_value = mock_profile
                roadmap_resp = await client.post("/roadmap/generate", headers=headers)
                assert roadmap_resp.status_code == 201, f"Failed to setup roadmap: {roadmap_resp.text}"

            # 2. Fire 10 parallel requests to POST /tasks/next simultaneously
            tasks = [
                client.post("/tasks/next", headers=headers)
                for _ in range(10)
            ]
            responses = await asyncio.gather(*tasks)

        # Analyze status codes
        status_codes = [r.status_code for r in responses]
        count_200 = status_codes.count(200)
        count_409 = status_codes.count(409)

        # Verify no tracebacks leaked
        for r in responses:
            assert "Traceback" not in r.text, f"Response leaked traceback: {r.text}"

        assert count_200 == 1, f"Expected exactly 1 200 response, got {count_200}. Statuses: {status_codes}"
        assert count_409 == 9, f"Expected exactly 9 409 responses, got {count_409}. Statuses: {status_codes}"

        # Verify real database state
        engine = create_async_engine(REAL_DB_URL)
        try:
            async with engine.connect() as conn:
                res = await conn.execute(
                    text("SELECT count(*) FROM tasks WHERE user_id = :uid"),
                    {"uid": str(test_user_id)},
                )
                db_count = res.scalar()
        finally:
            await engine.dispose()

        assert db_count == 1, f"Expected exactly 1 task in real DB, found {db_count}"

    finally:
        await cleanup_test_user(test_user_id)
        await reset_session_engine()


@pytest.mark.asyncio
async def test_concurrent_tasks_next_bypassing_app_guard_proves_db_index():
    """
    PROVE DB PARTIAL UNIQUE INDEX (uix_one_active_task_per_user):
    Bypasses the application-level 'get_active_task' check by patching it to return None.
    Fires 10 parallel POST /tasks/next requests.
    With artificial LLM delay (200ms), all 10 requests race directly to the DB insert.
    - Exactly 1 succeeds (HTTP 200).
    - Exactly 9 hit PostgreSQL's IntegrityError (UniqueViolationError), mapped to clean 409.
    - Exactly 1 task row is persisted in the database.
    """
    await reset_session_engine()

    test_user_id = uuid.uuid4()
    headers = {
        "X-User-Id": str(test_user_id),
        "X-Gateway-Token": settings.GATEWAY_SERVICE_TOKEN,
    }

    mock_profile = {
        "user_id": str(test_user_id),
        "target_role": "Full Stack Engineer",
        "experience_level": "fresher",
        "learning_goal": "Learn modern scalable web development",
        "structured_skills": [
            {"name": "Python", "proficiency_level": "beginner", "verified": False},
        ],
    }

    from app.services.roadmap_service import RoadmapService

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Setup roadmap
            with patch.object(ProfileClient, "get_profile", new_callable=AsyncMock) as mock_get_profile:
                mock_get_profile.return_value = mock_profile
                roadmap_resp = await client.post("/roadmap/generate", headers=headers)
                assert roadmap_resp.status_code == 201

            # 2. Patch out application-level active task check so only DB index can stop duplicates
            with patch.object(RoadmapService, "get_active_task", new_callable=AsyncMock, return_value=None):
                tasks = [
                    client.post("/tasks/next", headers=headers)
                    for _ in range(10)
                ]
                responses = await asyncio.gather(*tasks)

        status_codes = [r.status_code for r in responses]
        count_200 = status_codes.count(200)
        count_409 = status_codes.count(409)

        for r in responses:
            assert "Traceback" not in r.text

        assert count_200 == 1, f"Expected 1 200 OK, got {count_200}. Statuses: {status_codes}"
        assert count_409 == 9, f"Expected 9 409 Conflict from DB index, got {count_409}. Statuses: {status_codes}"

        # Verify PostgreSQL actually has only 1 row
        engine = create_async_engine(REAL_DB_URL)
        try:
            async with engine.connect() as conn:
                res = await conn.execute(
                    text("SELECT count(*) FROM tasks WHERE user_id = :uid"),
                    {"uid": str(test_user_id)},
                )
                db_count = res.scalar()
        finally:
            await engine.dispose()

        assert db_count == 1, f"Database has {db_count} tasks, expected 1"

    finally:
        await cleanup_test_user(test_user_id)
        await reset_session_engine()


@pytest.mark.asyncio
async def test_repo_url_unique_index_bypassing_app_guard_proves_db_index():
    """
    PROVE DB PARTIAL UNIQUE INDEX (uix_task_user_github_repo):
    Bypasses the application-level SELECT query in submit_task.
    Directly attempts to commit a duplicate github_repo_url for the same user.
    PostgreSQL's uix_task_user_github_repo index raises IntegrityError,
    which is caught and mapped to a clean 409 Conflict.
    """
    from datetime import datetime, timezone
    from app.models.task import Task, TaskStatus
    from app.services.roadmap_service import RoadmapService, DuplicateRepoUrlError
    from sqlalchemy.exc import IntegrityError

    await reset_session_engine()

    test_user_id = uuid.uuid4()
    headers = {
        "X-User-Id": str(test_user_id),
        "X-Gateway-Token": settings.GATEWAY_SERVICE_TOKEN,
    }

    mock_profile = {
        "user_id": str(test_user_id),
        "target_role": "Full Stack Engineer",
        "experience_level": "fresher",
        "learning_goal": "Learn modern scalable web development",
        "structured_skills": [
            {"name": "Python", "proficiency_level": "beginner", "verified": False},
        ],
    }

    shared_repo = "https://github.com/test-user/my-reused-project"

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Setup roadmap
            with patch.object(ProfileClient, "get_profile", new_callable=AsyncMock) as mock_get_profile:
                mock_get_profile.return_value = mock_profile
                r_map = await client.post("/roadmap/generate", headers=headers)
                assert r_map.status_code == 201

            # 2. Generate task 1, start, submit with shared_repo, evaluate
            r_t1 = await client.post("/tasks/next", headers=headers)
            assert r_t1.status_code == 200
            t1_id = r_t1.json()["task"]["id"]

            await client.post(f"/tasks/{t1_id}/start", headers=headers)
            r_sub1 = await client.post(
                f"/tasks/{t1_id}/submit",
                json={"github_repo_url": shared_repo},
                headers=headers,
            )
            assert r_sub1.status_code == 200

            # Evaluate task 1 so it is no longer active
            internal_headers = {"X-Internal-Token": settings.INTERNAL_SERVICE_TOKEN}
            await client.post(f"/internal/tasks/{t1_id}/claim-evaluation", headers=internal_headers)
            await client.post(
                f"/internal/tasks/{t1_id}/evaluation",
                json={"score": 85.0, "feedback": "Good", "passed": True},
                headers=internal_headers,
            )

            # 3. Generate task 2 and start it
            r_t2 = await client.post("/tasks/next", headers=headers)
            assert r_t2.status_code == 200
            t2_id = r_t2.json()["task"]["id"]
            await client.post(f"/tasks/{t2_id}/start", headers=headers)

            # 4. Now submit task 2 with the SAME repo URL, bypassing the application-level SELECT check
            # Define a patched version of submit_task that skips the application-level dup query
            original_submit = RoadmapService.submit_task

            async def submit_without_app_check(self, db, task_id, user_id, github_repo_url):
                task = await self.get_task_by_id(db, task_id, user_id)
                self.state_machine.transition(task, TaskStatus.SUBMITTED)
                task.github_repo_url = github_repo_url
                task.submitted_at = datetime.now(timezone.utc)
                # Omit the application-level select query — rely strictly on PostgreSQL index!
                try:
                    await db.commit()
                    await db.refresh(task)
                    return task
                except IntegrityError as exc:
                    await db.rollback()
                    raise DuplicateRepoUrlError(
                        f"PostgreSQL uix_task_user_github_repo: Repository '{github_repo_url}' already exists."
                    ) from exc

            with patch.object(RoadmapService, "submit_task", submit_without_app_check):
                r_dup = await client.post(
                    f"/tasks/{t2_id}/submit",
                    json={"github_repo_url": shared_repo},
                    headers=headers,
                )

            assert r_dup.status_code == 409
            assert "already exists" in r_dup.json()["detail"] or "already been submitted" in r_dup.json()["detail"]

    finally:
        await cleanup_test_user(test_user_id)
        await reset_session_engine()
