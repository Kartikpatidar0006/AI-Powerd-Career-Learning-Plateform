"""
End-to-End Smoke Test for AI Powered Career Learning Platform.

TESTED WITH LOCAL PROCESSES ONLY — Docker is NOT installed on this machine.
No Docker / port-isolation / Dockerfile / container-migration items are verified here.

Architecture note:
  Steps 1-7 and Step 10 call the API GATEWAY (port 8000).
  Steps 8-9 call the ROADMAP SERVICE DIRECTLY (port 8003 / internal endpoints).
  The distinction is labelled clearly in each step header.

UNVERIFIED - requires Docker:
  - docker-compose.yml / docker-compose.dev.yml port bindings
  - Dockerfile multi-stage builds for all services
  - Container-to-container networking (service DNS names)
  - Database migrations run inside Docker containers
  - Health check timeouts configured in docker-compose
  - Port isolation between services in production Docker network

Steps:
  1.  Signup              → API Gateway  POST /auth/signup
  2.  Login               → API Gateway  POST /auth/login
  3.  Onboarding          → API Gateway  POST /profile/onboarding
  4.  Roadmap generation  → API Gateway  POST /roadmap/generate
  5.  Get first task      → API Gateway  POST /tasks/next
  6.  Start task          → API Gateway  POST /tasks/{id}/start
  7.  Submit task         → API Gateway  POST /tasks/{id}/submit  (uses lowercase-normalized URL)
  8.  Claim evaluation    → Roadmap Service DIRECTLY  POST http://127.0.0.1:8003/internal/tasks/{id}/claim-evaluation
  8b. Re-submission check → API Gateway  POST /tasks/{id}/submit  (expects 409)
  9.  Apply evaluation    → Roadmap Service DIRECTLY  POST http://127.0.0.1:8003/internal/tasks/{id}/evaluation
  10. Next task           → API Gateway  POST /tasks/next
"""

import json
import os
import subprocess
import sys
import time
import uuid

import requests

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

GATEWAY_TOKEN   = "change-me-gateway-token"
INTERNAL_TOKEN  = "change-me-internal-token"
JWT_SECRET      = "change-me-in-production-use-a-strong-secret"

# ---------------------------------------------------------------------------
# URLs — keep these as named constants so the test code is readable
# ---------------------------------------------------------------------------
GATEWAY_BASE  = "http://127.0.0.1:8000"
ROADMAP_BASE  = "http://127.0.0.1:8003"   # direct, not via gateway

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
    "AUTH_SERVICE_URL":     "http://127.0.0.1:8001",
    "PROFILE_SERVICE_URL":  "http://127.0.0.1:8002",
    "ROADMAP_SERVICE_URL":  "http://127.0.0.1:8003",
}


def wait_for_health(url: str, name: str, timeout: int = 15) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(url, timeout=1.0)
            if r.status_code == 200:
                print(f"  [{name}] Healthy at {url}")
                return True
        except Exception:
            pass
        time.sleep(0.5)
    raise TimeoutError(f"[{name}] Failed to become healthy at {url} within {timeout}s")


def _print_raw(label: str, resp: requests.Response) -> None:
    """Print a labelled raw curl-style output block for this response."""
    print(f"\n  RAW RESPONSE [{label}] HTTP {resp.status_code}:")
    try:
        body = json.dumps(resp.json(), indent=4)
    except Exception:
        body = resp.text
    for line in body.splitlines():
        print(f"    {line}")


def main() -> None:
    procs = []
    try:
        print("=" * 62)
        print("  AI Career Platform — End-to-End Smoke Test")
        print("  Tested with LOCAL PROCESSES only. Docker NOT used.")
        print("=" * 62)

        print("\n=== Phase 1: Starting Services Locally ===")
        # Auth Service (8001)
        procs.append(("auth-service", subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8001", "--host", "127.0.0.1"],
            cwd=os.path.join(BASE_DIR, "services", "auth-service"),
            env=AUTH_ENV,
        )))

        # Profile Service (8002)
        procs.append(("profile-agent-service", subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8002", "--host", "127.0.0.1"],
            cwd=os.path.join(BASE_DIR, "services", "profile-agent-service"),
            env=PROFILE_ENV,
        )))

        # Roadmap Service (8003)
        procs.append(("roadmap-agent-service", subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8003", "--host", "127.0.0.1"],
            cwd=os.path.join(BASE_DIR, "services", "roadmap-agent-service"),
            env=ROADMAP_ENV,
        )))

        # API Gateway (8000)
        procs.append(("api-gateway", subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8000", "--host", "127.0.0.1"],
            cwd=os.path.join(BASE_DIR, "services", "api-gateway"),
            env=GATEWAY_ENV,
        )))

        print("\n  Waiting for health checks...")
        wait_for_health("http://127.0.0.1:8001/health", "Auth Service")
        wait_for_health("http://127.0.0.1:8002/health", "Profile Service")
        wait_for_health("http://127.0.0.1:8003/health", "Roadmap Service")
        wait_for_health("http://127.0.0.1:8000/health", "API Gateway")

        print("\n  All 4 services healthy — running E2E smoke test.\n")

        random_suffix = uuid.uuid4().hex[:6]
        user_email    = f"student_{random_suffix}@example.com"
        user_password = "Password123!Safe"

        # ----------------------------------------------------------------
        # Step 1: Signup
        #   Endpoint: API Gateway (port 8000) — user-facing
        # ----------------------------------------------------------------
        print("─" * 62)
        print(f"  Step 1  [API Gateway {GATEWAY_BASE}]  POST /auth/signup")
        print("─" * 62)
        r = requests.post(f"{GATEWAY_BASE}/auth/signup", json={
            "email":     user_email,
            "password":  user_password,
            "full_name": f"Alex Student {random_suffix}",
        })
        _print_raw("POST /auth/signup", r)
        assert r.status_code == 201, f"Signup failed: {r.text}"

        # ----------------------------------------------------------------
        # Step 2: Login
        #   Endpoint: API Gateway (port 8000) — user-facing
        # ----------------------------------------------------------------
        print("\n" + "─" * 62)
        print(f"  Step 2  [API Gateway {GATEWAY_BASE}]  POST /auth/login")
        print("─" * 62)
        r = requests.post(f"{GATEWAY_BASE}/auth/login", json={
            "email":    user_email,
            "password": user_password,
        })
        _print_raw("POST /auth/login", r)
        assert r.status_code == 200, f"Login failed: {r.text}"

        login_data    = r.json()
        access_token  = login_data["access_token"]
        auth_headers  = {"Authorization": f"Bearer {access_token}"}

        # ----------------------------------------------------------------
        # Step 3: Onboarding
        #   Endpoint: API Gateway (port 8000) — user-facing
        # ----------------------------------------------------------------
        print("\n" + "─" * 62)
        print(f"  Step 3  [API Gateway {GATEWAY_BASE}]  POST /profile/onboarding")
        print("─" * 62)
        r = requests.post(f"{GATEWAY_BASE}/profile/onboarding", headers=auth_headers, json={
            "education": {
                "degree":      "B.Tech",
                "branch":      "Computer Science",
                "year":        2025,
                "institution": "National Institute of Technology",
            },
            "skills_description": (
                "I have experience with Python, basic FastAPI REST APIs, "
                "and simple React components."
            ),
            "target_role":      "Full Stack Engineer",
            "experience_level": "fresher",
        })
        _print_raw("POST /profile/onboarding", r)
        assert r.status_code == 201, f"Onboarding failed: {r.text}"
        assert r.json()["is_locked"] is True, "Profile should be locked"

        # ----------------------------------------------------------------
        # Step 4: Generate Roadmap
        #   Endpoint: API Gateway (port 8000) — user-facing
        # ----------------------------------------------------------------
        print("\n" + "─" * 62)
        print(f"  Step 4  [API Gateway {GATEWAY_BASE}]  POST /roadmap/generate")
        print("─" * 62)
        r = requests.post(f"{GATEWAY_BASE}/roadmap/generate", headers=auth_headers)
        roadmap_data = r.json()
        _print_raw("POST /roadmap/generate", r)
        assert r.status_code == 201, f"Roadmap generation failed: {r.text}"
        print(f"  Milestones: {len(roadmap_data.get('milestones', []))}")
        print(f"  M1 title: {roadmap_data['milestones'][0]['title']}")
        print(f"  M1 state: {roadmap_data['milestones'][0]['state']}")

        # ----------------------------------------------------------------
        # Step 5: Get First Task
        #   Endpoint: API Gateway (port 8000) — user-facing
        # ----------------------------------------------------------------
        print("\n" + "─" * 62)
        print(f"  Step 5  [API Gateway {GATEWAY_BASE}]  POST /tasks/next")
        print("─" * 62)
        r = requests.post(f"{GATEWAY_BASE}/tasks/next", headers=auth_headers)
        _print_raw("POST /tasks/next", r)
        assert r.status_code == 200, f"Task generation failed: {r.text}"

        task_data = r.json()
        assert task_data["status"] == "task_assigned"
        task1    = task_data["task"]
        task1_id = task1["id"]
        print(f"  Task 1 ID: {task1_id} | Title: {task1['title']} | Status: {task1['status']}")
        assert task1["status"] == "ASSIGNED"

        # ----------------------------------------------------------------
        # Step 6: Start Task (ASSIGNED -> IN_PROGRESS)
        #   Endpoint: API Gateway (port 8000) — user-facing
        # ----------------------------------------------------------------
        print("\n" + "─" * 62)
        print(f"  Step 6  [API Gateway {GATEWAY_BASE}]  POST /tasks/{task1_id}/start")
        print("─" * 62)
        r = requests.post(f"{GATEWAY_BASE}/tasks/{task1_id}/start", headers=auth_headers)
        _print_raw(f"POST /tasks/{task1_id}/start", r)
        assert r.status_code == 200, f"Start task failed: {r.text}"

        started_data = r.json()
        assert started_data["status"] == "IN_PROGRESS"
        assert started_data["started_at"] is not None, "started_at must be populated"
        print(f"  started_at: {started_data['started_at']}")

        # ----------------------------------------------------------------
        # Step 7: Submit Task (IN_PROGRESS -> SUBMITTED)
        #   Endpoint: API Gateway (port 8000) — user-facing
        #   Note: URL uses MIXED CASE owner to verify lowercase normalization.
        # ----------------------------------------------------------------
        print("\n" + "─" * 62)
        print(f"  Step 7  [API Gateway {GATEWAY_BASE}]  POST /tasks/{task1_id}/submit")
        print("  (mixed-case GitHub URL → service must store lowercase-normalized form)")
        print("─" * 62)
        # Mixed-case URL: uppercase owner + repo to exercise the normalizer
        github_repo_mixed = f"https://github.com/Alex-Student/FullStack-Task-{random_suffix}"
        github_repo_expected = github_repo_mixed.lower().replace(
            "https://github.com/", "https://github.com/", 1
        )
        # Manually build expected: lowercase only the path after the scheme+host
        github_repo_expected = (
            "https://github.com/"
            + github_repo_mixed[len("https://github.com/"):].lower()
        )

        r = requests.post(
            f"{GATEWAY_BASE}/tasks/{task1_id}/submit",
            json={"github_repo_url": github_repo_mixed},
            headers=auth_headers,
        )
        _print_raw(f"POST /tasks/{task1_id}/submit", r)
        assert r.status_code == 200, f"Submit task failed: {r.text}"

        submitted_data = r.json()
        assert submitted_data["status"] == "SUBMITTED"
        stored_url = submitted_data["github_repo_url"]
        assert stored_url == github_repo_expected, (
            f"github_repo_url must be stored lowercase.\n"
            f"  Expected: {github_repo_expected}\n"
            f"  Got:      {stored_url}"
        )
        print(f"  Stored URL (lowercase): {stored_url}  ✓")

        # ----------------------------------------------------------------
        # Step 8: Claim Evaluation (SUBMITTED -> EVALUATING)
        #   Endpoint: ROADMAP SERVICE DIRECTLY (port 8003, not via gateway)
        #   Internal endpoint — requires X-Internal-Token header.
        # ----------------------------------------------------------------
        print("\n" + "─" * 62)
        print(f"  Step 8  [Roadmap Service DIRECTLY {ROADMAP_BASE}]")
        print(f"          POST /internal/tasks/{task1_id}/claim-evaluation")
        print("          (bypasses API Gateway — internal service-to-service call)")
        print("─" * 62)
        internal_headers = {"X-Internal-Token": INTERNAL_TOKEN}
        r = requests.post(
            f"{ROADMAP_BASE}/internal/tasks/{task1_id}/claim-evaluation",
            headers=internal_headers,
        )
        _print_raw(f"POST {ROADMAP_BASE}/internal/tasks/{task1_id}/claim-evaluation", r)
        assert r.status_code == 200, f"Claim evaluation failed: {r.text}"

        evaluating_data = r.json()
        assert evaluating_data["status"] == "EVALUATING"
        print(f"  Task status: {evaluating_data['status']}  ✓")

        # ----------------------------------------------------------------
        # Step 8b: Verify re-submission in EVALUATING is rejected (409)
        #   Endpoint: API Gateway (port 8000) — user-facing
        # ----------------------------------------------------------------
        print("\n" + "─" * 62)
        print(f"  Step 8b [API Gateway {GATEWAY_BASE}]  POST /tasks/{task1_id}/submit")
        print("          (must be rejected with 409 — task is EVALUATING)")
        print("─" * 62)
        r_re_sub = requests.post(
            f"{GATEWAY_BASE}/tasks/{task1_id}/submit",
            json={"github_repo_url": github_repo_mixed},
            headers=auth_headers,
        )
        _print_raw(f"POST /tasks/{task1_id}/submit (re-submit while EVALUATING)", r_re_sub)
        assert r_re_sub.status_code == 409, (
            f"Expected 409 when re-submitting in EVALUATING state, got {r_re_sub.status_code}"
        )
        print(f"  Correctly rejected with 409  ✓")

        # ----------------------------------------------------------------
        # Step 9: Apply Evaluation (EVALUATING -> EVALUATED)
        #   Endpoint: ROADMAP SERVICE DIRECTLY (port 8003, not via gateway)
        #   Internal endpoint — requires X-Internal-Token header.
        # ----------------------------------------------------------------
        print("\n" + "─" * 62)
        print(f"  Step 9  [Roadmap Service DIRECTLY {ROADMAP_BASE}]")
        print(f"          POST /internal/tasks/{task1_id}/evaluation")
        print("          (bypasses API Gateway — internal Agent 3 callback)")
        print("─" * 62)
        eval_payload = {
            "score": 88.0,
            "feedback": "Outstanding implementation. Code is clean and adheres to all criteria.",
            "criteria_results": [
                {"criterion": "Git branch workflow",   "passed": True},
                {"criterion": "Python PEP8 standards", "passed": True},
            ],
            "passed": True,
        }
        r = requests.post(
            f"{ROADMAP_BASE}/internal/tasks/{task1_id}/evaluation",
            json=eval_payload,
            headers=internal_headers,
        )
        _print_raw(f"POST {ROADMAP_BASE}/internal/tasks/{task1_id}/evaluation", r)
        assert r.status_code == 200, f"Evaluation failed: {r.text}"

        evaluated_data = r.json()
        assert evaluated_data["status"] == "EVALUATED"
        assert evaluated_data["evaluation_summary"]["score"]  == 88.0
        assert evaluated_data["evaluation_summary"]["passed"] is True
        print(f"  Score: {evaluated_data['evaluation_summary']['score']}  ✓")
        print(f"  Passed: {evaluated_data['evaluation_summary']['passed']}  ✓")

        # ----------------------------------------------------------------
        # Step 10: Request Next Task (Sequence 2)
        #   Endpoint: API Gateway (port 8000) — user-facing
        # ----------------------------------------------------------------
        print("\n" + "─" * 62)
        print(f"  Step 10 [API Gateway {GATEWAY_BASE}]  POST /tasks/next")
        print("─" * 62)
        r = requests.post(f"{GATEWAY_BASE}/tasks/next", headers=auth_headers)
        _print_raw("POST /tasks/next (sequence 2)", r)
        assert r.status_code == 200, f"Next task request failed: {r.text}"

        task2_data = r.json()
        assert task2_data["status"] == "task_assigned"
        task2 = task2_data["task"]
        print(f"  Task 2 ID: {task2['id']} | Seq: {task2['sequence_number']} | Title: {task2['title']}")
        assert task2["sequence_number"] == 2, (
            f"Expected sequence_number=2, got {task2['sequence_number']}"
        )
        print(f"  sequence_number: {task2['sequence_number']}  ✓")

        # ----------------------------------------------------------------
        # Summary
        # ----------------------------------------------------------------
        print("\n" + "=" * 62)
        print("  SMOKE TEST COMPLETED SUCCESSFULLY! ALL 10 STEPS PASSED!")
        print("=" * 62)
        print()
        print("  ENDPOINT ROUTING SUMMARY:")
        print("  Steps 1-7, 8b, 10 → API Gateway  (http://127.0.0.1:8000)")
        print("  Steps 8, 9         → Roadmap Service directly  (http://127.0.0.1:8003/internal/...)")
        print()
        print("  UNVERIFIED - requires Docker:")
        print("    - docker-compose.yml / docker-compose.dev.yml port bindings")
        print("    - Dockerfile multi-stage builds for all services")
        print("    - Container-to-container networking (service DNS names)")
        print("    - Database migrations inside containers")
        print("    - Health check timeouts in docker-compose")
        print("    - Port isolation in production Docker network")

    finally:
        print("\n  Terminating background services...")
        for name, proc in procs:
            proc.terminate()
            proc.wait()
            print(f"    Terminated {name}")


if __name__ == "__main__":
    main()
