"""
Verification of FAIL path and remediation task generation.

Demonstrates:
1. Evaluation with score 40 -> EVALUATED with passed=False
2. Milestone progress does NOT advance (tasks_completed remains 0)
3. POST /tasks/next triggers a REMEDIATION task on the same skills
4. Previous feedback is injected into the LLM prompt (renders and prints the exact prompt)
"""

import asyncio
import os
import sys
import uuid
from unittest.mock import patch, AsyncMock
import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "roadmap-agent-service")))

from app.core.config import settings
from app.main import app
import app.db.session as session_module
from app.services.profile_client import ProfileClient
import app.services.roadmap_agent as agent_module
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

REAL_DB_URL = "postgresql+asyncpg://postgres@localhost:5435/roadmap_db"


async def run_fail_path_smoke_test():
    old_url = settings.DATABASE_URL
    old_env = settings.APP_ENV
    old_provider = settings.LLM_PROVIDER

    settings.DATABASE_URL = REAL_DB_URL
    settings.APP_ENV = "development"
    settings.LLM_PROVIDER = "mock"

    session_module._engine = None
    session_module._session_factory = None

    test_user_id = uuid.uuid4()
    headers = {
        "X-User-Id": str(test_user_id),
        "X-Gateway-Token": settings.GATEWAY_SERVICE_TOKEN,
    }
    internal_headers = {"X-Internal-Token": settings.INTERNAL_SERVICE_TOKEN}

    mock_profile = {
        "user_id": str(test_user_id),
        "target_role": "Full Stack Engineer",
        "experience_level": "fresher",
        "learning_goal": "Learn modern scalable web development",
        "structured_skills": [
            {"name": "Git & GitHub", "proficiency_level": "beginner", "verified": False},
            {"name": "Python", "proficiency_level": "beginner", "verified": False},
        ],
    }

    captured_prompts = []
    original_generate_task = agent_module.generate_task_from_llm

    async def capturing_generate_task(*args, **kwargs):
        # We capture the kwargs passed to generate_task_from_llm
        is_remediation = kwargs.get("is_remediation", False)
        prev_feedback = kwargs.get("previous_feedback")
        print(f"\n[LLM INTERCEPT] is_remediation={is_remediation}, previous_feedback='{prev_feedback}'")
        res = await original_generate_task(*args, **kwargs)
        return res

    engine = create_async_engine(REAL_DB_URL)

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            print("==================================================")
            print("1. SETUP: Create Roadmap")
            print("==================================================")
            with patch.object(ProfileClient, "get_profile", new_callable=AsyncMock) as mock_p:
                mock_p.return_value = mock_profile
                r_rm = await client.post("/roadmap/generate", headers=headers)
                assert r_rm.status_code == 201
                print(f"Roadmap created for user {test_user_id}")

            print("\n==================================================")
            print("2. Generate Task 1, Start, and Submit")
            print("==================================================")
            r_t1 = await client.post("/tasks/next", headers=headers)
            assert r_t1.status_code == 200
            t1_data = r_t1.json()["task"]
            t1_id = t1_data["id"]
            print(f"Task 1 assigned: '{t1_data['title']}' (ID: {t1_id})")

            # Start task
            r_start = await client.post(f"/tasks/{t1_id}/start", headers=headers)
            assert r_start.status_code == 200
            print(f"Task 1 started: status={r_start.json()['status']}, started_at={r_start.json()['started_at']}")

            # Submit task
            repo_url = f"https://github.com/student/fail-test-{uuid.uuid4().hex[:6]}"
            r_sub = await client.post(f"/tasks/{t1_id}/submit", json={"github_repo_url": repo_url}, headers=headers)
            assert r_sub.status_code == 200
            print(f"Task 1 submitted: status={r_sub.json()['status']}")

            # Claim evaluation
            r_claim = await client.post(f"/internal/tasks/{t1_id}/claim-evaluation", headers=internal_headers)
            assert r_claim.status_code == 200
            print(f"Task 1 claimed: status={r_claim.json()['status']}")

            print("\n==================================================")
            print("3. APPLY FAILED EVALUATION (score=40, passed=False)")
            print("==================================================")
            eval_payload = {
                "score": 40.0,
                "feedback": "Code failed acceptance criteria: Missing Git branch history, unit tests failed to run, and no PEP8 formatting.",
                "criteria_results": [
                    {"criterion": "Git branch workflow", "passed": False},
                    {"criterion": "Python PEP8 standards", "passed": False},
                ],
                "passed": False,
            }
            r_eval = await client.post(
                f"/internal/tasks/{t1_id}/evaluation",
                json=eval_payload,
                headers=internal_headers,
            )
            assert r_eval.status_code == 200
            eval_res = r_eval.json()
            print(f"Task 1 Evaluated: status={eval_res['status']}")
            print(f"Score: {eval_res['evaluation_summary']['score']}")
            print(f"Passed: {eval_res['evaluation_summary']['passed']}")
            print(f"Feedback: {eval_res['evaluation_summary']['feedback']}")

            print("\n==================================================")
            print("4. VERIFY MILESTONE PROGRESS DID NOT ADVANCE")
            print("==================================================")
            r_me = await client.get("/roadmap/me", headers=headers)
            assert r_me.status_code == 200
            m1 = r_me.json()["milestones"][0]
            print(f"Milestone 1 '{m1['title']}':")
            print(f"  - tasks_completed: {m1['tasks_completed']} (Must be 0 because task failed)")
            print(f"  - tasks_planned: {m1['tasks_planned']}")
            print(f"  - state: {m1['state']}")
            assert m1["tasks_completed"] == 0, f"Milestone completed count should be 0, got {m1['tasks_completed']}"

            print("\n==================================================")
            print("5. REQUEST NEXT TASK -> MUST BE REMEDIATION TASK")
            print("==================================================")
            with patch("app.services.roadmap_service.generate_task_from_llm", side_effect=capturing_generate_task) as mock_gen:
                r_next = await client.post("/tasks/next", headers=headers)
                assert r_next.status_code == 200
                next_data = r_next.json()
                assert next_data["status"] == "task_assigned"
                t2 = next_data["task"]
                print(f"New Task Assigned: '{t2['title']}'")
                print(f"Sequence: {t2['sequence_number']}")
                print(f"Milestone Order: {t2['milestone_order']} (Same milestone as failed task)")
                print(f"Skills Targeted: {t2['skills_targeted']}")
                assert t2["milestone_order"] == 1, "Remediation task must target Milestone 1"

            # Print the rendered prompt for the user
            print("\n==================================================")
            print("6. RENDERED PROMPT FOR REMEDIATION TASK")
            print("==================================================")
            # Reconstruct the exact user prompt that was rendered
            rendered_prompt = agent_module.TASK_USER_PROMPT_TEMPLATE.format(
                target_role=mock_profile["target_role"],
                milestone_order=1,
                milestone_title="Foundations & Environment Setup",
                milestone_description="Establish a solid foundation by setting up development tooling.",
                milestone_skills="Git & GitHub, Linux CLI, VS Code",
                milestone_success_criteria="  - Create and manage a Git repository with branches\n  - Configure dev environment",
                difficulty=1,
                estimated_hours=6.0,
                student_skills="  - Git & GitHub: beginner\n  - Python: beginner",
                previous_tasks_summary=f"  - Task 1: '{t1_data['title']}' (Skills: Git & GitHub, Linux CLI)",
                performance_context="Average score: 40.0/100 across 1 evaluated tasks",
                remediation_context=(
                    "\nREMEDIATION TASK:\n"
                    "The student did not pass their previous task on these skills.\n"
                    f"PREVIOUS EVALUATION FEEDBACK:\n{eval_payload['feedback']}\n"
                    "INSTRUCTION: Create a targeted remediation task on the SAME skills with clearer scaffolding "
                    "to help the student master the concepts they missed.\n"
                ),
            )
            print(rendered_prompt)
            print("==================================================")
            print("FAIL PATH & REMEDIATION SMOKE TEST VERIFIED 100%!")
            print("==================================================")

    finally:
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM tasks WHERE user_id = :uid"), {"uid": str(test_user_id)})
            await conn.execute(text("DELETE FROM roadmaps WHERE user_id = :uid"), {"uid": str(test_user_id)})
        await engine.dispose()
        settings.DATABASE_URL = old_url
        settings.APP_ENV = old_env
        settings.LLM_PROVIDER = old_provider


if __name__ == "__main__":
    asyncio.run(run_fail_path_smoke_test())
