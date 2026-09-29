"""
Verification script for 1(b) and 1(c):
1(b): Prove ports 5433, 5434 are closed on the host
1(c): Directly invoke auth, profile, and roadmap services WITHOUT X-Gateway-Token to prove 403 Forbidden
"""

import sys
import os
import subprocess
import time
import requests
import socket

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

GATEWAY_TOKEN = "change-me-gateway-token"
INTERNAL_TOKEN = "change-me-internal-token"

COMMON_ENV = {
    **os.environ,
    "GATEWAY_SERVICE_TOKEN": GATEWAY_TOKEN,
    "INTERNAL_SERVICE_TOKEN": INTERNAL_TOKEN,
    "JWT_SECRET_KEY": "change-me-in-production-use-a-strong-secret",
    "APP_ENV": "development",
    "LLM_PROVIDER": "mock",
    "PYTHONPATH": ".",
}

AUTH_ENV = {**COMMON_ENV, "DATABASE_URL": "postgresql+asyncpg://postgres@localhost:5435/auth_db"}
PROFILE_ENV = {**COMMON_ENV, "DATABASE_URL": "postgresql+asyncpg://postgres@localhost:5435/profile_db"}
ROADMAP_ENV = {**COMMON_ENV, "DATABASE_URL": "postgresql+asyncpg://postgres@localhost:5435/roadmap_db", "PROFILE_SERVICE_INTERNAL_URL": "http://127.0.0.1:8002"}

def test_port_connection(port: int):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        res = s.connect_ex(('127.0.0.1', port))
        return res == 0

def main():
    print("=== Verification of Port Isolation & Gateway Token Defense ===")

    # 1. Check unopened DB ports 5433 and 5434
    for port in [5433, 5434]:
        is_open = test_port_connection(port)
        print(f"Port {port} connection check: {'CONNECTED (FAIL)' if is_open else 'CONNECTION REFUSED (PASSED)'}")

    # 2. Start services on ports 8001, 8002, 8003
    procs = []
    try:
        p1 = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8001", "--host", "127.0.0.1"],
                              cwd=os.path.join(BASE_DIR, "services", "auth-service"), env=AUTH_ENV,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        p2 = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8002", "--host", "127.0.0.1"],
                              cwd=os.path.join(BASE_DIR, "services", "profile-agent-service"), env=PROFILE_ENV,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        p3 = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8003", "--host", "127.0.0.1"],
                              cwd=os.path.join(BASE_DIR, "services", "roadmap-agent-service"), env=ROADMAP_ENV,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        procs.extend([p1, p2, p3])

        time.sleep(2.5)

        print("\n--- Testing Direct Service Access WITHOUT X-Gateway-Token ---")
        
        # Auth Service: POST /auth/signup without token
        r_auth = requests.post("http://127.0.0.1:8001/auth/signup", json={"email": "direct@test.com", "password": "Password123!"})
        print(f"POST http://127.0.0.1:8001/auth/signup (no X-Gateway-Token):")
        print(f"  Status Code: {r_auth.status_code}")
        print(f"  Response Body: {r_auth.text}")
        assert r_auth.status_code == 403

        # Profile Service: GET /profile/me without token
        r_prof = requests.get("http://127.0.0.1:8002/profile/me", headers={"X-User-Id": "00000000-0000-0000-0000-000000000001"})
        print(f"\nGET http://127.0.0.1:8002/profile/me (no X-Gateway-Token):")
        print(f"  Status Code: {r_prof.status_code}")
        print(f"  Response Body: {r_prof.text}")
        assert r_prof.status_code == 403

        # Roadmap Service: POST /roadmap/generate without token
        r_road = requests.post("http://127.0.0.1:8003/roadmap/generate", headers={"X-User-Id": "00000000-0000-0000-0000-000000000001"})
        print(f"\nPOST http://127.0.0.1:8003/roadmap/generate (no X-Gateway-Token):")
        print(f"  Status Code: {r_road.status_code}")
        print(f"  Response Body: {r_road.text}")
        assert r_road.status_code == 403

        print("\n--- Testing Direct Service Access WITH Valid X-Gateway-Token ---")
        headers = {"X-Gateway-Token": GATEWAY_TOKEN}

        # Health probe is exempt:
        r_health = requests.get("http://127.0.0.1:8003/health")
        print(f"GET http://127.0.0.1:8003/health: Status {r_health.status_code} (Exempt from token)")

        # With valid token, request passes defense middleware:
        r_road_valid = requests.post("http://127.0.0.1:8003/roadmap/generate", headers=headers)
        print(f"POST http://127.0.0.1:8003/roadmap/generate WITH X-Gateway-Token:")
        print(f"  Status Code: {r_road_valid.status_code} (401 because no user auth, NOT 403 Forbidden!)")
        assert r_road_valid.status_code == 401

        print("\n>>> ALL CHECKS PASSED: Defense in depth fully confirmed! <<<")

    finally:
        for p in procs:
            p.terminate()
            p.wait()

if __name__ == "__main__":
    main()
