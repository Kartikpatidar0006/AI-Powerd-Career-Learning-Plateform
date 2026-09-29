"""
End-to-End Smoke Test for AI Powered Career Learning Platform.

Executes:
1. Signup (POST /auth/signup)
2. Login (POST /auth/login)
3. Onboarding (POST /profile/onboarding)
4. Roadmap generation (POST /roadmap/generate)
5. Generate first task (POST /tasks/next)
6. Start task (POST /tasks/{id}/start -> checks started_at)
7. Submit task (POST /tasks/{id}/submit -> checks github_repo_url)
8. Claim evaluation (POST /internal/tasks/{id}/claim-evaluation -> checks EVALUATING)
9. Simulate/apply evaluation (POST /internal/tasks/{id}/evaluation -> checks EVALUATED & score/passed)
10. Generate next task (POST /tasks/next -> checks sequence 2)
"""

import os
import sys
import time
import json
import uuid
import subprocess
import requests

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

GATEWAY_TOKEN = "change-me-gateway-token"
INTERNAL_TOKEN = "change-me-internal-token"
JWT_SECRET = "change-me-in-production-use-a-strong-secret"

COMMON_ENV = {
    **os.environ,
    "GATEWAY_SERVICE_TOKEN": GATEWAY_TOKEN,
    "INTERNAL_SERVICE_TOKEN": INTERNAL_TOKEN,
    "JWT_SECRET_KEY": JWT_SECRET,
    "APP_ENV": "development",
    "LLM_PROVIDER": "mock",
    "PYTHONPATH": ".",
}

AUTH_ENV = {
    **COMMON_ENV,
    "DATABASE_URL": "postgresql+asyncpg://postgres@localhost:5435/auth_db",
}

PROFILE_ENV = {
    **COMMON_ENV,
    "DATABASE_URL": "postgresql+asyncpg://postgres@localhost:5435/profile_db",
}

ROADMAP_ENV = {
    **COMMON_ENV,
    "DATABASE_URL": "postgresql+asyncpg://postgres@localhost:5435/roadmap_db",
    "PROFILE_SERVICE_INTERNAL_URL": "http://127.0.0.1:8002",
}

GATEWAY_ENV = {
    **COMMON_ENV,
    "AUTH_SERVICE_URL": "http://127.0.0.1:8001",
    "PROFILE_SERVICE_URL": "http://127.0.0.1:8002",
    "ROADMAP_SERVICE_URL": "http://127.0.0.1:8003",
}


def wait_for_health(url: str, name: str, timeout: int = 15):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(url, timeout=1.0)
            if r.status_code == 200:
                print(f"[{name}] Healthy at {url}")
                return True
        except Exception:
            pass
        time.sleep(0.5)
    raise TimeoutError(f"[{name}] Failed to become healthy at {url} within {timeout}s")


def main():
    procs = []
    try:
        print("=== 1. Starting Services Locally ===")
        # Start Auth Service (8001)
        auth_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8001", "--host", "127.0.0.1"],
            cwd=os.path.join(BASE_DIR, "services", "auth-service"),
            env=AUTH_ENV,
        )
        procs.append(("auth-service", auth_proc))

        # Start Profile Service (8002)
        profile_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8002", "--host", "127.0.0.1"],
            cwd=os.path.join(BASE_DIR, "services", "profile-agent-service"),
            env=PROFILE_ENV,
        )
        procs.append(("profile-agent-service", profile_proc))

        # Start Roadmap Service (8003)
        roadmap_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8003", "--host", "127.0.0.1"],
            cwd=os.path.join(BASE_DIR, "services", "roadmap-agent-service"),
            env=ROADMAP_ENV,
        )
        procs.append(("roadmap-agent-service", roadmap_proc))

        # Start API Gateway (8000)
        gateway_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8000", "--host", "127.0.0.1"],
            cwd=os.path.join(BASE_DIR, "services", "api-gateway"),
            env=GATEWAY_ENV,
        )
        procs.append(("api-gateway", gateway_proc))

        # Wait for all health checks
        wait_for_health("http://127.0.0.1:8001/health", "Auth Service")
        wait_for_health("http://127.0.0.1:8002/health", "Profile Service")
        wait_for_health("http://127.0.0.1:8003/health", "Roadmap Service")
        wait_for_health("http://127.0.0.1:8000/health", "API Gateway")

        print("\nAll 4 services healthy! Running End-to-End Smoke Test Flow...\n")

        random_suffix = uuid.uuid4().hex[:6]
        user_email = f"student_{random_suffix}@example.com"
        user_password = "Password123!Safe"

        # ----------------------------------------------------
        # Step 1: Signup
        # ----------------------------------------------------
        print("--- Step 1: User Signup via Gateway ---")
        signup_payload = {
            "email": user_email,
            "password": user_password,
            "full_name": f"Alex Student {random_suffix}",
        }
        r = requests.post("http://localhost:8000/auth/signup", json=signup_payload)
        print(f"POST /auth/signup -> {r.status_code}")
        print(json.dumps(r.json(), indent=2))
        assert r.status_code == 201, f"Signup failed: {r.text}"

        # ----------------------------------------------------
        # Step 2: Login
        # ----------------------------------------------------
        print("\n--- Step 2: User Login via Gateway ---")
        login_payload = {
            "email": user_email,
            "password": user_password,
        }
        r = requests.post("http://localhost:8000/auth/login", json=login_payload)
        print(f"POST /auth/login -> {r.status_code}")
        login_data = r.json()
        print(json.dumps(login_data, indent=2))
        assert r.status_code == 200, f"Login failed: {r.text}"
        access_token = login_data["access_token"]
        auth_headers = {"Authorization": f"Bearer {access_token}"}

        # ----------------------------------------------------
        # Step 3: Onboarding
        # ----------------------------------------------------
        print("\n--- Step 3: Student Onboarding via Gateway (Agent 1) ---")
        onboarding_payload = {
            "education": {
                "degree": "B.Tech",
                "branch": "Computer Science",
                "year": 2025,
                "institution": "National Institute of Technology",
            },
            "skills_description": "I have experience with Python, basic FastAPI REST APIs, and simple React components.",
            "target_role": "Full Stack Engineer",
            "experience_level": "fresher",
        }
        r = requests.post("http://localhost:8000/profile/onboarding", json=onboarding_payload, headers=auth_headers)
        print(f"POST /profile/onboarding -> {r.status_code}")
        profile_data = r.json()
        print(json.dumps(profile_data, indent=2))
        assert r.status_code == 201, f"Onboarding failed: {r.text}"
        assert profile_data["is_locked"] is True, "Profile should be locked"

        # ----------------------------------------------------
        # Step 4: Roadmap Generation
        # ----------------------------------------------------
        print("\n--- Step 4: Generate Roadmap via Gateway (Agent 2) ---")
        r = requests.post("http://localhost:8000/roadmap/generate", headers=auth_headers)
        print(f"POST /roadmap/generate -> {r.status_code}")
        roadmap_data = r.json()
        print(f"Roadmap ID: {roadmap_data.get('id')}")
        print(f"Milestones generated: {len(roadmap_data.get('milestones', []))}")
        print(f"Milestone 1 title: {roadmap_data['milestones'][0]['title']}")
        print(f"Milestone 1 state: {roadmap_data['milestones'][0]['state']}")
        assert r.status_code == 201, f"Roadmap generation failed: {r.text}"

        # ----------------------------------------------------
        # Step 5: Get First Task
        # ----------------------------------------------------
        print("\n--- Step 5: Request Next Task via Gateway ---")
        r = requests.post("http://localhost:8000/tasks/next", headers=auth_headers)
        print(f"POST /tasks/next -> {r.status_code}")
        task_data = r.json()
        print(json.dumps(task_data, indent=2))
        assert r.status_code == 200, f"Task generation failed: {r.text}"
        assert task_data["status"] == "task_assigned"
        task1 = task_data["task"]
        task1_id = task1["id"]
        print(f"Assigned Task 1 ID: {task1_id}, Title: {task1['title']}, Status: {task1['status']}")
        assert task1["status"] == "ASSIGNED"

        # ----------------------------------------------------
        # Step 6: Start Task (ASSIGNED -> IN_PROGRESS)
        # ----------------------------------------------------
        print("\n--- Step 6: Start Task (ASSIGNED -> IN_PROGRESS) ---")
        r = requests.post(f"http://localhost:8000/tasks/{task1_id}/start", headers=auth_headers)
        print(f"POST /tasks/{task1_id}/start -> {r.status_code}")
        started_data = r.json()
        print(json.dumps(started_data, indent=2))
        assert r.status_code == 200, f"Start task failed: {r.text}"
        assert started_data["status"] == "IN_PROGRESS"
        assert started_data["started_at"] is not None, "started_at must be populated on start"
        print(f"Started at: {started_data['started_at']}")

        # ----------------------------------------------------
        # Step 7: Submit Task (IN_PROGRESS -> SUBMITTED)
        # ----------------------------------------------------
        print("\n--- Step 7: Submit Task with GitHub Repo URL ---")
        github_repo = f"https://github.com/alex-student/fullstack-task-{random_suffix}"
        r = requests.post(
            f"http://localhost:8000/tasks/{task1_id}/submit",
            json={"github_repo_url": github_repo},
            headers=auth_headers,
        )
        print(f"POST /tasks/{task1_id}/submit -> {r.status_code}")
        submitted_data = r.json()
        print(json.dumps(submitted_data, indent=2))
        assert r.status_code == 200, f"Submit task failed: {r.text}"
        assert submitted_data["status"] == "SUBMITTED"
        assert submitted_data["github_repo_url"] == github_repo

        # ----------------------------------------------------
        # Step 8: Claim Evaluation (SUBMITTED -> EVALUATING)
        # ----------------------------------------------------
        print("\n--- Step 8: Claim Evaluation via Internal Route (SUBMITTED -> EVALUATING) ---")
        internal_headers = {"X-Internal-Token": INTERNAL_TOKEN}
        r = requests.post(
            f"http://localhost:8003/internal/tasks/{task1_id}/claim-evaluation",
            headers=internal_headers,
        )
        print(f"POST /internal/tasks/{task1_id}/claim-evaluation -> {r.status_code}")
        evaluating_data = r.json()
        print(json.dumps(evaluating_data, indent=2))
        assert r.status_code == 200, f"Claim evaluation failed: {r.text}"
        assert evaluating_data["status"] == "EVALUATING"

        # Verify re-submission in EVALUATING is rejected
        print("\n--- Step 8b: Verify re-submission in EVALUATING is rejected ---")
        r_re_sub = requests.post(
            f"http://localhost:8000/tasks/{task1_id}/submit",
            json={"github_repo_url": github_repo},
            headers=auth_headers,
        )
        print(f"POST /tasks/{task1_id}/submit while EVALUATING -> {r_re_sub.status_code} (Expected 409)")
        assert r_re_sub.status_code == 409

        # ----------------------------------------------------
        # Step 9: Simulate / Apply Evaluation (EVALUATING -> EVALUATED)
        # ----------------------------------------------------
        print("\n--- Step 9: Apply Evaluation Result (EVALUATING -> EVALUATED) ---")
        eval_payload = {
            "score": 88.0,
            "feedback": "Outstanding implementation. Code is clean, modular, and adheres to all criteria.",
            "criteria_results": [
                {"criterion": "Git branch workflow", "passed": True},
                {"criterion": "Python PEP8 standards", "passed": True},
            ],
            "passed": True,
        }
        r = requests.post(
            f"http://localhost:8003/internal/tasks/{task1_id}/evaluation",
            json=eval_payload,
            headers=internal_headers,
        )
        print(f"POST /internal/tasks/{task1_id}/evaluation -> {r.status_code}")
        evaluated_data = r.json()
        print(json.dumps(evaluated_data, indent=2))
        assert r.status_code == 200, f"Evaluation failed: {r.text}"
        assert evaluated_data["status"] == "EVALUATED"
        assert evaluated_data["evaluation_summary"]["score"] == 88.0
        assert evaluated_data["evaluation_summary"]["passed"] is True

        # ----------------------------------------------------
        # Step 10: Request Next Task (Sequence 2)
        # ----------------------------------------------------
        print("\n--- Step 10: Request Next Task (Sequence 2) ---")
        r = requests.post("http://localhost:8000/tasks/next", headers=auth_headers)
        print(f"POST /tasks/next -> {r.status_code}")
        task2_data = r.json()
        print(json.dumps(task2_data, indent=2))
        assert r.status_code == 200, f"Next task request failed: {r.text}"
        assert task2_data["status"] == "task_assigned"
        task2 = task2_data["task"]
        print(f"Assigned Task 2 ID: {task2['id']}, Seq: {task2['sequence_number']}, Title: {task2['title']}")
        assert task2["sequence_number"] == 2

        print("\n==================================================")
        print("SMOKE TEST COMPLETED SUCCESSFULLY! ALL 10 STEPS PASSED!")
        print("==================================================")

    finally:
        print("\nTerminating background services...")
        for name, proc in procs:
            proc.terminate()
            proc.wait()
            print(f"Terminated {name}")


if __name__ == "__main__":
    main()
