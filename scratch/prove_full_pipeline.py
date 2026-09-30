"""
Live Automated End-to-End Pipeline Proof for Agent 3 (Evaluator Agent Service).

Strict Requirements:
1. Full automatic pipeline on the REAL Docker stack (via API Gateway port 8000):
   signup -> onboarding -> roadmap -> task -> start -> submit (github_repo_url)
2. NO manual / dev trigger called anywhere.
3. Poll GET /evaluations/{task_id} via API Gateway until status == COMPLETED.
4. Verify task automatically reached EVALUATED in roadmap-agent-service via its own internal call chain.
5. Print real HTTP curl/request and response outputs for every single step.
"""

import json
import sys
import time
import uuid
import requests

# Ensure UTF-8 output on Windows terminal
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

GATEWAY_BASE = "http://localhost:8000"
REPO_URL = "https://github.com/navdeep-G/samplemod"


def print_step(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def safe_json(resp: requests.Response) -> dict | str:
    try:
        return resp.json()
    except Exception:
        return resp.text


def print_req_resp(method: str, path: str, status_code: int, req_body: dict | None, resp: requests.Response) -> None:
    print(f"\n>> {method} {GATEWAY_BASE}{path}")
    if req_body:
        print(f">> Request Body:\n{json.dumps(req_body, indent=2)}")
    print(f"<< HTTP {status_code}")
    print(f"<< Response Body:")
    data = safe_json(resp)
    if isinstance(data, dict):
        print(json.dumps(data, indent=2))
    else:
        print(data)


def main() -> None:
    print("=" * 70)
    print("AGENT 3 FULL AUTOMATIC PIPELINE PROOF (DOCKER STACK)")
    print("=" * 70)

    # Pre-flight check: Gateway & Services health
    print("\nChecking API Gateway health at http://localhost:8000/health ...")
    r_health = requests.get(f"{GATEWAY_BASE}/health", timeout=5)
    assert r_health.status_code == 200, f"Gateway unhealthy: {r_health.text}"
    print(f"[OK] API Gateway healthy: {r_health.json()}")

    unique_id = uuid.uuid4().hex[:6]
    email = f"eval_student_{unique_id}@example.com"
    password = "SafePassword123!"

    # ──────────────────────────────────────────────────────────────────
    # Step 1: Signup
    # ──────────────────────────────────────────────────────────────────
    print_step("STEP 1: Student Signup (POST /auth/signup)")
    signup_payload = {
        "email": email,
        "password": password,
        "full_name": f"Eval Student {unique_id}",
    }
    r = requests.post(f"{GATEWAY_BASE}/auth/signup", json=signup_payload, timeout=10)
    print_req_resp("POST", "/auth/signup", r.status_code, signup_payload, r)
    assert r.status_code == 201, f"Signup failed: {r.text}"

    # ──────────────────────────────────────────────────────────────────
    # Step 2: Login
    # ──────────────────────────────────────────────────────────────────
    print_step("STEP 2: Student Login (POST /auth/login)")
    login_payload = {
        "email": email,
        "password": password,
    }
    r = requests.post(f"{GATEWAY_BASE}/auth/login", json=login_payload, timeout=10)
    print_req_resp("POST", "/auth/login", r.status_code, login_payload, r)
    assert r.status_code == 200, f"Login failed: {r.text}"

    login_res = r.json()
    token = login_res["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # ──────────────────────────────────────────────────────────────────
    # Step 3: Onboarding
    # ──────────────────────────────────────────────────────────────────
    print_step("STEP 3: Profile Onboarding (POST /profile/onboarding)")
    onboarding_payload = {
        "education": {
            "degree": "B.Tech",
            "branch": "Computer Science",
            "year": 2025,
            "institution": "Tech Institute",
        },
        "skills_description": "I know Python and building REST APIs.",
        "target_role": "Python Backend Engineer",
        "experience_level": "fresher",
    }
    r = requests.post(f"{GATEWAY_BASE}/profile/onboarding", headers=headers, json=onboarding_payload, timeout=30)
    print_req_resp("POST", "/profile/onboarding", r.status_code, onboarding_payload, r)
    assert r.status_code == 201, f"Onboarding failed: {r.text}"

    # ──────────────────────────────────────────────────────────────────
    # Step 4: Generate Roadmap
    # ──────────────────────────────────────────────────────────────────
    print_step("STEP 4: Generate Roadmap (POST /roadmap/generate)")
    r = requests.post(f"{GATEWAY_BASE}/roadmap/generate", headers=headers, timeout=45)
    print_req_resp("POST", "/roadmap/generate", r.status_code, None, r)
    assert r.status_code == 201, f"Roadmap generation failed: {r.text}"

    # ──────────────────────────────────────────────────────────────────
    # Step 5: Get First Task
    # ──────────────────────────────────────────────────────────────────
    print_step("STEP 5: Get Next Task (POST /tasks/next)")
    r = requests.post(f"{GATEWAY_BASE}/tasks/next", headers=headers, timeout=30)
    print_req_resp("POST", "/tasks/next", r.status_code, None, r)
    assert r.status_code == 200, f"Task fetch failed: {r.text}"

    task_res = r.json()
    task = task_res["task"]
    task_id = task["id"]
    print(f"\n[OK] Assigned Task ID: {task_id}")
    print(f"[OK] Task Title: {task['title']}")
    print(f"[OK] Task State: {task['status']}")

    # ──────────────────────────────────────────────────────────────────
    # Step 6: Start Task
    # ──────────────────────────────────────────────────────────────────
    print_step(f"STEP 6: Start Task (POST /tasks/{task_id}/start)")
    r = requests.post(f"{GATEWAY_BASE}/tasks/{task_id}/start", headers=headers, timeout=10)
    print_req_resp("POST", f"/tasks/{task_id}/start", r.status_code, None, r)
    assert r.status_code == 200, f"Task start failed: {r.text}"
    start_res = r.json()
    assert start_res["status"] == "IN_PROGRESS"

    # ──────────────────────────────────────────────────────────────────
    # Step 7: Submit Task (with real public repo URL)
    # ──────────────────────────────────────────────────────────────────
    print_step(f"STEP 7: Submit Task with GitHub Repo (POST /tasks/{task_id}/submit)")
    submit_payload = {"github_repo_url": REPO_URL}
    r = requests.post(f"{GATEWAY_BASE}/tasks/{task_id}/submit", headers=headers, json=submit_payload, timeout=15)
    print_req_resp("POST", f"/tasks/{task_id}/submit", r.status_code, submit_payload, r)
    assert r.status_code == 200, f"Task submit failed: {r.text}"
    submit_res = r.json()
    assert submit_res["status"] == "SUBMITTED"
    print("\n>>> Task SUBMITTED successfully.")
    print(">>> NOTE: No manual/dev triggers called. Evaluation pipeline runs automatically via internal service call chain.")

    # ──────────────────────────────────────────────────────────────────
    # Step 8: Poll GET /evaluations/{task_id} until COMPLETED
    # ──────────────────────────────────────────────────────────────────
    print_step(f"STEP 8: Poll Student-Facing Endpoint (GET /evaluations/{task_id})")
    print(f"Polling {GATEWAY_BASE}/evaluations/{task_id} via API Gateway...")

    eval_data = None
    max_wait_seconds = 60
    poll_interval = 2.0
    start_time = time.time()

    while time.time() - start_time < max_wait_seconds:
        elapsed = int(time.time() - start_time)
        r = requests.get(f"{GATEWAY_BASE}/evaluations/{task_id}", headers=headers, timeout=10)
        
        if r.status_code == 200:
            data = r.json()
            status_val = data.get("status")
            print(f"  [{elapsed:2d}s] HTTP 200 - Evaluation Status: {status_val}")
            if status_val == "COMPLETED":
                eval_data = data
                print("\n[SUCCESS] Evaluation reached COMPLETED!")
                print_req_resp("GET", f"/evaluations/{task_id}", r.status_code, None, r)
                break
            elif status_val == "FAILED":
                eval_data = data
                print(f"\n[FAIL] Evaluation status is FAILED: {data}")
                break
        elif r.status_code == 404:
            print(f"  [{elapsed:2d}s] HTTP 404 - Evaluation record not yet created, waiting...")
        else:
            print(f"  [{elapsed:2d}s] HTTP {r.status_code} - {r.text}")

        time.sleep(poll_interval)

    assert eval_data is not None, f"Evaluation did not complete within {max_wait_seconds}s"
    assert eval_data["status"] == "COMPLETED", f"Expected COMPLETED, got {eval_data['status']}"
    assert eval_data["final_score"] <= 35.0, f"Expected capped score <= 35.0, got {eval_data['final_score']}"
    assert eval_data["passed"] is False, f"Expected passed == False, got {eval_data['passed']}"
    assert eval_data["reuse_suspected"] is True, f"Expected reuse_suspected == True, got {eval_data.get('reuse_suspected')}"
    assert "No commits were found after you started this task." in eval_data["feedback_summary"]

    # ──────────────────────────────────────────────────────────────────
    # Step 9: Verify Task Automatically Reached EVALUATED in Roadmap Agent Service
    # ──────────────────────────────────────────────────────────────────
    print_step(f"STEP 9: Verify Task State in Roadmap Service (GET /tasks/{task_id})")
    r_task = requests.get(f"{GATEWAY_BASE}/tasks/{task_id}", headers=headers, timeout=10)
    print_req_resp("GET", f"/tasks/{task_id}", r_task.status_code, None, r_task)
    assert r_task.status_code == 200
    task_final = r_task.json()
    assert task_final["status"] == "EVALUATED", (
        f"Task did not automatically reach EVALUATED! Current status: {task_final.get('status')}"
    )
    assert task_final["evaluation_summary"]["passed"] is False, "Task evaluation_summary should be passed=False"
    assert task_final["evaluation_summary"]["score"] <= 35.0, "Task evaluation_summary score should be <= 35.0"

    print("\n" + "=" * 70)
    print("PROVED: Full Automatic Pipeline Completed with Scoring Integrity Gate!")
    print(f"  - Final Score:     {eval_data.get('final_score')} (CAPPED <= 35.0)")
    print(f"  - Passed:          {eval_data.get('passed')} (FORCED False)")
    print(f"  - Reuse Suspected: {eval_data.get('reuse_suspected')} (Correctly flagged)")
    print(f"  - Task Status:     {task_final.get('status')} (Automatically transitioned to EVALUATED)")
    print(f"  - Summary:         \"{eval_data.get('feedback_summary')}\"")
    print("=" * 70)


if __name__ == "__main__":
    main()
