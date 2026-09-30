
# 🚀 AI Powered Career Learning Platform

> A production-grade, microservices-based platform leveraging specialized AI Agents to deliver personalized career learning paths, deterministic skill evaluation, daily coding tasks, and real-time readiness tracking.

**Current Phase:** Week 4 Complete — Agent 3: GitHub Repository Evaluator (Static Analysis, Prompt Injection Defense, Evaluation Lifecycle)

---

## 🏗 System Architecture

```
career-platform/
├── services/
│   ├── api-gateway/            # FastAPI reverse proxy — single external entry point (port 8000)
│   │   ├── app/
│   │   │   ├── main.py         # Proxies auth, profile, roadmap, tasks, evaluations with JWT validation
│   │   │   └── config.py       # Gateway config, rate limits, timeouts, defense tokens
│   │   ├── tests/              # Gateway proxy and security tests (16 tests)
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── auth-service/           # Authentication microservice (internal port 8001)
│   │   ├── app/                # User accounts, bcrypt security, access + refresh tokens
│   │   ├── alembic/            # DB migrations for auth_db (001_initial, 002_refresh_tokens)
│   │   ├── tests/              # 21 tests covering auth features & gateway defense
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── profile-agent-service/  # Agent 1: Profile & Dashboard Agent (internal port 8002)
│   │   ├── app/
│   │   │   ├── routers/        # POST /profile/onboarding, GET /profile/me
│   │   │   ├── services/       # Profile extraction, readiness scoring, profile locking
│   │   │   └── core/llm/       # LLM provider abstraction (OpenAI, Anthropic, Mock)
│   │   ├── alembic/            # DB migrations for profile_db (001_create_student_profiles)
│   │   ├── tests/              # Agent 1 schema validation and domain tests (20 tests)
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── roadmap-agent-service/  # Agent 2: Roadmap & Daily Task Generator (internal port 8003)
│   │   ├── app/
│   │   │   ├── routers/        # /roadmap/generate, /roadmap/me, /tasks/next, /tasks/{id}/*
│   │   │   ├── services/       # State machine, difficulty calculation, LLM task generation, evaluator trigger
│   │   │   ├── models/         # Roadmap & Task models with partial unique indexes
│   │   │   └── core/llm/       # LLM provider abstraction with duplicate title detection
│   │   ├── alembic/            # DB migrations for roadmap_db (001_initial, 002_week4_prep)
│   │   ├── tests/              # 81 unit & real-DB concurrency integration tests
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   └── evaluator-agent-service/# Agent 3: GitHub Repository Evaluator (internal port 8004)
│       ├── app/
│       │   ├── routers/        # POST /internal/evaluate, GET /evaluations/{task_id}, POST /dev/evaluations/trigger/{task_id}
│       │   ├── services/       # 7 deterministic checks, GitHub REST client, LLM code reviewer, score composition
│       │   ├── models/         # Evaluation ORM model with JSONB snapshots and check results
│       │   └── core/llm/       # LLM provider abstraction with strict prompt injection defense
│       ├── alembic/            # DB migrations for evaluator_db (0001_initial)
│       ├── tests/              # 40 comprehensive unit & injection defense tests
│       ├── Dockerfile
│       └── requirements.txt
│
├── frontend/                   # React 19 + TypeScript + Vite + Tailwind CSS
│   └── src/
│       ├── pages/              # LoginPage, SignupPage, OnboardingPage, DashboardPage, RoadmapPage, DailyTaskPage, EvaluationResultPage
│       ├── components/         # ProtectedRoute, AppNavbar, TaskCard, MilestoneTimeline, ScoreRing
│       └── services/           # Axios API clients for auth, profile, roadmap, and evaluator
│
├── docker-compose.yml          # Production compose: host ports restricted to gateway & frontend
├── docker-compose.dev.yml      # Local debugging compose: publishes internal microservice & DB ports
├── .env.example                # Environment variables template
├── .env                        # Local active configuration
└── README.md
```

---

## 🔒 Network Isolation & Security (Defense in Depth)

### 1. Host Port Isolation
- **Production (`docker-compose.yml`)**: Only `api-gateway` (port `8000:8000`) and `frontend` (port `5173:5173`) publish ports to the host machine.
- All internal microservices (`auth-service`, `profile-agent-service`, `roadmap-agent-service`) and dedicated PostgreSQL instances (`postgres-auth`, `postgres-profile`, `postgres-roadmap`) use Docker `expose:` only.
- **Local Debugging (`docker-compose.dev.yml`)**: Can be combined via `docker compose -f docker-compose.yml -f docker-compose.dev.yml up` to expose internal ports for development:
  - `postgres-auth`: `5433:5432`
  - `postgres-profile`: `5434:5432`
  - `postgres-roadmap`: `5435:5432`
  - `auth-service`: `8001:8001`
  - `profile-agent-service`: `8002:8002`
  - `roadmap-agent-service`: `8003:8003`

### 2. Defense in Depth (`X-Gateway-Token`)
- To protect downstream services in case of container network bridging, the API Gateway automatically injects a cryptographically verified `X-Gateway-Token` header.
- Every downstream service verifies this token using constant-time comparison (`hmac.compare_digest`). Requests omitting or providing an invalid gateway token are immediately rejected with `403 Forbidden`.
- Health check probes (`/health`) and OpenAPI doc endpoints (`/docs`, `/openapi.json`) are exempt from this requirement.

### 3. Route Blocking at the Gateway
- All `/internal/*` routes (e.g. Agent 3 evaluation endpoints) and `/dev/*` routes (simulation endpoints) are strictly intercepted and blocked by the API Gateway with `404 Not Found`.

---

## 📋 Verified Onboarding Specification & Enums

### Endpoint
`POST /profile/onboarding` (proxied via `http://localhost:8000/profile/onboarding` with Bearer token)

### `experience_level` Enum
The experience level bracket is strictly validated against the following enum values:
- `"student"`: Currently enrolled in high school or university.
- `"fresher"`: Recent graduate seeking first full-time role (0 years experience).
- `"1-2yrs"`: Early career professional (1 to 2 years experience).
- `"2+yrs"`: Experienced professional transitioning or upskilling (2+ years experience).

### Immutability & Profile Locking
- Immediately upon processing, Agent 1 structures the skills, calculates a deterministic readiness score, and locks the profile (`is_locked = True`).
- Any subsequent call to `POST /profile/onboarding` returns `403 Forbidden` (`{"detail": "Profile already exists and is locked"}`). No `PUT` or `PATCH` endpoints are exposed for onboarding fields.

---

## ⚙️ Task State Machine & Migration 002

### Lifecycle Transitions
```
                ┌───────────────────────────────────────────────┐
                │                                               │
                ▼                                               │
[ASSIGNED] ──► [IN_PROGRESS] ──► [SUBMITTED] ──► [EVALUATING] ──► [EVALUATED] (Terminal)
                                      ▲               │
                                      │  (on failure) │
                                      └───────────────┘
```

1. **`ASSIGNED` -> `IN_PROGRESS`**: Triggered via `POST /tasks/{id}/start`. Sets `tasks.started_at = NOW()`.
2. **`IN_PROGRESS` -> `SUBMITTED`**: Triggered via `POST /tasks/{id}/submit` with a valid GitHub repo URL. Sets `tasks.submitted_at = NOW()`.
3. **`SUBMITTED` -> `SUBMITTED`**: Re-submission permitted only while in `SUBMITTED` state (e.g. updating the GitHub URL).
4. **`SUBMITTED` -> `EVALUATING`**: Triggered via internal worker endpoint `POST /internal/tasks/{id}/claim-evaluation`.
5. **`EVALUATING` -> `SUBMITTED`**: Evaluation failure rollback via `POST /internal/tasks/{id}/fail-evaluation`.
6. **`EVALUATING` -> `EVALUATED`**: Evaluation complete via `POST /internal/tasks/{id}/evaluation`.
7. **Re-submission Blocked**: Re-submitting GitHub URL while a task is in `EVALUATING` or `EVALUATED` status returns `409 Conflict`.

### Database Constraints (Alembic 002)
- **Active Task Isolation**: Partial unique index `uix_one_active_task_per_user` on `tasks(user_id)` where `status IN ('ASSIGNED', 'IN_PROGRESS', 'SUBMITTED', 'EVALUATING')`. Enforces that a user can never have more than one active task at any time.
- **GitHub Repository Uniqueness**: Partial unique index `uix_task_user_github_repo` on `(user_id, github_repo_url) WHERE github_repo_url IS NOT NULL`. Prevents a user from reusing the same repository for multiple tasks, returning a clean `409 Conflict`.

---

## 🎯 Pass/Fail Semantics & Adaptive Remediation

1. **Score & Pass Threshold**:
   - `evaluation_summary` contains `score` (0-100) and `passed` (boolean).
   - Passing threshold defaults to `PASS_SCORE=60` (configurable via environment).
2. **Milestone Completion Criteria**:
   - Milestone progress counts **ONLY passed tasks** (`task.evaluation_summary.get("passed") is True`).
   - Failed tasks do not increment completed task count for milestone progression.
3. **Adaptive Remediation Tasks**:
   - If a student's last evaluated task failed (`passed=False`), the next call to `POST /tasks/next` automatically generates a **REMEDIATION task** targeting the exact same milestone and skills.
   - The evaluator's previous feedback is injected directly into the LLM prompt to address the student's specific gaps.

---

## 🚦 Verified Step-by-Step API Walkthrough (Real Terminal Outputs)

Below is the verified end-to-end flow executed through the API Gateway on `http://localhost:8000`.

### Step 1: User Signup
```bash
curl -s -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alex.engineer@example.com",
    "password": "Password123!Safe",
    "full_name": "Alex Engineer"
  }'
```
**Output (HTTP 201 Created):**
```json
{
  "id": "dcc369e1-880e-4f37-90f6-062c983a488d",
  "email": "alex.engineer@example.com",
  "full_name": "Alex Engineer",
  "is_active": true,
  "created_at": "2026-09-28T08:32:00.124510Z"
}
```

---

### Step 2: User Login
```bash
curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alex.engineer@example.com",
    "password": "Password123!Safe"
  }'
```
**Output (HTTP 200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800,
  "refresh_token": "b78a9c3d-2495-4672-9b2f-1fa4b7324c52"
}
```
*(Store the token in `TOKEN="eyJhbGciOi..."` for subsequent requests)*

---

### Step 3: Complete Onboarding (Agent 1 Profile Lock)
```bash
curl -s -X POST http://localhost:8000/profile/onboarding \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "education": {
      "degree": "B.Tech",
      "branch": "Computer Science",
      "year": 2025,
      "institution": "National Institute of Technology"
    },
    "skills_description": "I have experience with Python, basic FastAPI REST APIs, and simple React components.",
    "target_role": "Full Stack Engineer",
    "experience_level": "fresher"
  }'
```
**Output (HTTP 201 Created):**
```json
{
  "id": "5f9e2b10-6218-4ad0-bb23-e18e47c1b504",
  "user_id": "dcc369e1-880e-4f37-90f6-062c983a488d",
  "target_role": "Full Stack Engineer",
  "experience_level": "fresher",
  "is_locked": true,
  "readiness_score": 42,
  "structured_skills": [
    {
      "skill_name": "Python",
      "category": "Backend",
      "proficiency_level": "intermediate",
      "confidence_score": 0.85
    },
    {
      "skill_name": "FastAPI",
      "category": "Backend",
      "proficiency_level": "beginner",
      "confidence_score": 0.70
    },
    {
      "skill_name": "React",
      "category": "Frontend",
      "proficiency_level": "beginner",
      "confidence_score": 0.65
    }
  ]
}
```

---

### Step 4: Generate Learning Roadmap (Agent 2)
```bash
curl -s -X POST http://localhost:8000/roadmap/generate \
  -H "Authorization: Bearer $TOKEN"
```
**Output (HTTP 201 Created):**
```json
{
  "id": "a22276d9-45b7-418c-986c-21c972a20384",
  "user_id": "dcc369e1-880e-4f37-90f6-062c983a488d",
  "status": "active",
  "milestones": [
    {
      "order": 1,
      "title": "Foundations & Environment Setup",
      "description": "Establish a solid foundation for Full Stack Engineer by setting up development tooling and reviewing core CS fundamentals.",
      "target_skills": ["Git & GitHub", "Linux CLI", "VS Code"],
      "estimated_days": 10,
      "difficulty_band": 1,
      "tasks_completed": 0,
      "tasks_planned": 1,
      "state": "current",
      "success_criteria": [
        "Create and manage a Git repository with branches and pull requests",
        "Configure a professional local dev environment"
      ]
    },
    {
      "order": 2,
      "title": "Core Language Proficiency",
      "description": "Master the primary programming language required for the target role with idiomatic patterns.",
      "target_skills": ["Python", "Data Structures & Algorithms"],
      "estimated_days": 15,
      "difficulty_band": 2,
      "tasks_completed": 0,
      "tasks_planned": 1,
      "state": "upcoming"
    }
  ]
}
```

---

### Step 5: Request Next Daily Task
```bash
curl -s -X POST http://localhost:8000/tasks/next \
  -H "Authorization: Bearer $TOKEN"
```
**Output (HTTP 200 OK):**
```json
{
  "status": "task_assigned",
  "task": {
    "id": "87615136-ad9a-47ca-9fb1-9b3ade063f45",
    "user_id": "dcc369e1-880e-4f37-90f6-062c983a488d",
    "roadmap_id": "a22276d9-45b7-418c-986c-21c972a20384",
    "milestone_order": 1,
    "sequence_number": 1,
    "title": "Git Repository Management & Branching Workflow",
    "description": "Practice professional Git workflows by creating a repository, implementing a feature with proper branching, and submitting a pull request.",
    "requirements": [
      "1. Initialize a new Git repository for a sample Python project",
      "2. Create a 'develop' branch from main",
      "3. Add a Python script that computes the Fibonacci sequence iteratively",
      "4. Commit with conventional commit messages (feat:, fix:, docs:)",
      "5. Create a pull request and document the changes in a CHANGELOG.md"
    ],
    "acceptance_criteria": [
      "Repository is public on GitHub with at least 5 meaningful commits",
      "Branching strategy is documented in README.md",
      "CHANGELOG.md follows Keep a Changelog format",
      "Python script is PEP8 compliant and includes docstrings"
    ],
    "skills_targeted": ["Git & GitHub", "Linux CLI", "Technical Documentation"],
    "difficulty": 1,
    "estimated_hours": 6.0,
    "starter_hint": "Start by reviewing the milestone objectives for 'Foundations & Environment Setup'. Structure your code in clear modules before writing tests.",
    "status": "ASSIGNED",
    "started_at": null,
    "submitted_at": null,
    "evaluated_at": null
  }
}
```

---

### Step 6: Start Task (`ASSIGNED` -> `IN_PROGRESS`)
```bash
TASK_ID="87615136-ad9a-47ca-9fb1-9b3ade063f45"

curl -s -X POST http://localhost:8000/tasks/$TASK_ID/start \
  -H "Authorization: Bearer $TOKEN"
```
**Output (HTTP 200 OK):**
```json
{
  "id": "87615136-ad9a-47ca-9fb1-9b3ade063f45",
  "status": "IN_PROGRESS",
  "started_at": "2026-09-28T08:32:04.282737Z",
  "submitted_at": null,
  "evaluated_at": null
}
```

---

### Step 7: Submit Task (`IN_PROGRESS` -> `SUBMITTED`)
```bash
curl -s -X POST http://localhost:8000/tasks/$TASK_ID/submit \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "github_repo_url": "https://github.com/alex-student/fullstack-task-9146a4"
  }'
```
**Output (HTTP 200 OK):**
```json
{
  "id": "87615136-ad9a-47ca-9fb1-9b3ade063f45",
  "status": "SUBMITTED",
  "github_repo_url": "https://github.com/alex-student/fullstack-task-9146a4",
  "started_at": "2026-09-28T08:32:04.282737Z",
  "submitted_at": "2026-09-28T08:32:06.346507Z"
}
```

---

### Step 8: Claim Task for Evaluation (`SUBMITTED` -> `EVALUATING`)
*(Direct internal call made by Agent 3 evaluator worker)*
```bash
curl -s -X POST http://localhost:8003/internal/tasks/$TASK_ID/claim-evaluation \
  -H "X-Internal-Token: change-me-internal-token"
```
**Output (HTTP 200 OK):**
```json
{
  "id": "87615136-ad9a-47ca-9fb1-9b3ade063f45",
  "status": "EVALUATING",
  "github_repo_url": "https://github.com/alex-student/fullstack-task-9146a4"
}
```

---

### Step 9: Apply Evaluation Result (`EVALUATING` -> `EVALUATED`)
*(Direct internal call from Agent 3 evaluator worker after review)*
```bash
curl -s -X POST http://localhost:8003/internal/tasks/$TASK_ID/evaluation \
  -H "X-Internal-Token: change-me-internal-token" \
  -H "Content-Type: application/json" \
  -d '{
    "score": 88.0,
    "feedback": "Outstanding implementation. Code is clean, modular, and adheres to all criteria.",
    "criteria_results": [
      {"criterion": "Git branch workflow", "passed": true},
      {"criterion": "Python PEP8 standards", "passed": true}
    ],
    "passed": true
  }'
```
**Output (HTTP 200 OK):**
```json
{
  "id": "87615136-ad9a-47ca-9fb1-9b3ade063f45",
  "status": "EVALUATED",
  "evaluated_at": "2026-09-28T08:32:12.504256Z",
  "evaluation_summary": {
    "score": 88.0,
    "passed": true,
    "feedback": "Outstanding implementation. Code is clean, modular, and adheres to all criteria.",
    "evaluated_by": "agent-3",
    "criteria_results": [
      {"criterion": "Git branch workflow", "passed": true},
      {"criterion": "Python PEP8 standards", "passed": true}
    ]
  }
}
```

---

### Step 10: Request Next Daily Task (Progression Unlocked)
```bash
curl -s -X POST http://localhost:8000/tasks/next \
  -H "Authorization: Bearer $TOKEN"
```
**Output (HTTP 200 OK — Sequence 2 Assigned):**
```json
{
  "status": "task_assigned",
  "task": {
    "id": "95792467-656c-44ff-9d55-ac5e63393264",
    "user_id": "dcc369e1-880e-4f37-90f6-062c983a488d",
    "roadmap_id": "a22276d9-45b7-418c-986c-21c972a20384",
    "milestone_order": 1,
    "sequence_number": 2,
    "title": "Linux CLI Automation & Environment Tooling",
    "description": "Develop an automated command-line workflow script in Python to streamline project initialization and testing.",
    "requirements": [
      "1. Write a CLI automation script for project scaffolding and checks",
      "2. Parse arguments and handle environment flags with argparse",
      "3. Ensure clean exit codes and error messages",
      "4. Add unit tests covering argument parsing and script execution"
    ],
    "acceptance_criteria": [
      "Script executes without error on standard environments",
      "Arguments are validated with descriptive help messages",
      "Tests pass with 100% success rate"
    ],
    "skills_targeted": ["Linux CLI", "Python", "Automation"],
    "difficulty": 1,
    "estimated_hours": 6.0,
    "status": "ASSIGNED"
  }
}
```

---

## 🧪 Automated Testing Suite

All tests across all 5 microservices pass with 100% success rate (178 tests total):

```bash
# 1. API Gateway tests (16 passed)
pytest services/api-gateway/tests

# 2. Auth Service tests (21 passed)
pytest services/auth-service/tests

# 3. Profile Agent Service tests (20 passed)
pytest services/profile-agent-service/tests

# 4. Roadmap Agent Service unit & real-DB concurrency tests (81 passed)
pytest services/roadmap-agent-service/tests

# 5. Evaluator Agent Service (Agent 3) unit & injection defense tests (40 passed)
pytest services/evaluator-agent-service/tests
```

**Evaluator Agent Service (Agent 3) Test Coverage:**
- 18 isolated tests for all 7 deterministic checks with crafted fixtures and language heuristics
- 5 prompt injection defense tests proving delimiter protection, char limits, and cap rule enforcement
- 5 score composition tests verifying 65%/35% formula, cap boundaries, and mentor feedback synthesis
- 5 GitHub REST API error mapping tests (404, private, 429 rate limit, 500 server error)
- 7 API integration & defense tests verifying idempotency (409), gateway security tokens, and user isolation
- Zero response leakage of internal red_flags or python "Traceback" stack traces
