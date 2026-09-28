# 🚀 AI Powered Career Learning Platform

> A production-grade, microservices-based platform that leverages AI to deliver personalized career learning paths, skill tracking, and intelligent recommendations.

**Current Phase:** Week 2 — Profile & Dashboard Agent (Agent 1) Complete

---

## 🏗 Architecture

```
career-platform/
├── services/
│   ├── api-gateway/            # FastAPI reverse proxy — single entry point & JWT verifier
│   │   ├── app/
│   │   │   ├── main.py         # Gateway app with auth & authenticated profile proxies
│   │   │   └── config.py       # Service URLs, JWT settings, and CORS config
│   │   ├── tests/              # Gateway JWT validation tests
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── auth-service/           # Authentication microservice (Week 1 + Hardened)
│   │   ├── app/
│   │   │   ├── core/           # Config, security (bcrypt, tokens), dependencies
│   │   │   ├── db/             # SQLAlchemy async session & base
│   │   │   ├── models/         # User & RefreshToken ORM models
│   │   │   ├── schemas/        # Pydantic v2 schemas (with password strength validation)
│   │   │   ├── routers/        # Rate-limited auth routes (signup, login, refresh, logout)
│   │   │   ├── services/       # DB-backed token rotation & auth business logic
│   │   │   └── main.py         # FastAPI application entry point
│   │   ├── alembic/            # Database migrations (001_initial, 002_refresh_tokens)
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   └── profile-agent-service/  # Agent 1: Profile & Dashboard Agent (Week 2)
│       ├── app/
│       │   ├── core/
│       │   │   ├── config.py   # DB, LLM provider, and model configurations
│       │   │   └── llm/        # Swappable LLM provider abstraction (OpenAI, Anthropic, Mock)
│       │   ├── db/             # Async SQLAlchemy session & base
│       │   ├── models/         # StudentProfile ORM model (JSONB, lock flag)
│       │   ├── schemas/        # Pydantic v2 schemas for skills, dashboard, and onboarding
│       │   ├── routers/        # /profile/onboarding, /profile/me
│       │   ├── services/
│       │   │   ├── profile_agent.py   # Agent 1 prompt orchestration, 1-shot retry, scoring
│       │   │   └── profile_service.py # Domain logic & lock enforcement
│       │   └── main.py         # FastAPI entry point
│       ├── alembic/            # Database migrations for profile database
│       ├── tests/              # Unit & integration tests for Agent 1
│       ├── Dockerfile
│       └── requirements.txt
│
├── frontend/                   # React 19 + TypeScript + Vite + Tailwind CSS v4
│   └── src/
│       ├── components/         # ProtectedRoute, UI components
│       ├── context/            # React AuthContext (async logout, state)
│       ├── pages/              # LoginPage, SignupPage, OnboardingPage, DashboardPage
│       ├── routes/             # Profile-lock aware routing
│       ├── services/           # Axios API client, auth & profile service callers
│       └── types/              # TypeScript definitions for auth and profile
│
├── docker-compose.yml          # Orchestrates all 4 services and 2 PostgreSQL databases
├── .env.example                # Template with placeholder credentials
├── .env                        # Local environment configuration
└── README.md
```

## 🛠 Tech Stack

| Layer        | Technology                                                  |
| ------------ | ----------------------------------------------------------- |
| Backend      | Python 3.12, FastAPI (async), SQLAlchemy 2.0 (async)        |
| AI / LLM     | Swappable Provider Abstraction (OpenAI, Anthropic, Mock)   |
| Frontend     | React 19, TypeScript, Vite, Tailwind CSS v4                 |
| Database     | PostgreSQL 16 (Dedicated `auth_db` and `profile_db`)        |
| Auth         | Gateway-verified JWT (access + DB-backed refresh tokens)    |
| Validation   | Pydantic v2 for request inputs & strict LLM output parsing  |
| Migrations   | Alembic (async)                                             |
| Container    | Docker + Docker Compose with healthchecks                   |

## 🚀 Quick Start

### 1. Configure Environment
```bash
cp .env.example .env
# Edit .env with your preferred settings or LLM keys
# (Works out of the box with intelligent MockLLM fallback if no OpenAI key is set)
```

### 2. Start All Containers
```bash
docker-compose up --build
```

### 3. Service Ports & Swagger Endpoints

| Service               | Container / Local Port | Documentation URL            |
| --------------------- | ---------------------- | ---------------------------- |
| **Frontend**          | http://localhost:5173  | —                            |
| **API Gateway**       | http://localhost:8000  | http://localhost:8000/docs   |
| **Auth Service**      | http://localhost:8001  | http://localhost:8001/docs   |
| **Profile Agent**     | http://localhost:8002  | http://localhost:8002/docs   |
| **PostgreSQL (Auth)** | `localhost:5433`       | —                            |
| **PostgreSQL (Profile)** | `localhost:5434`    | —                            |

---

## 🔒 Lock Mechanism & Security Architecture

1. **Gateway-Level JWT Verification:**
   All `/profile/*` requests are intercepted by the API Gateway. The Gateway verifies the JWT access token signature, expiration, and claims. The verified user UUID is extracted from the `sub` claim and injected into a trusted `X-User-Id` header. Any client-sent `X-User-Id` header is stripped to eliminate spoofing attacks.

2. **Application-Level Lock Enforcement:**
   - When a student completes the onboarding wizard (`POST /profile/onboarding`), Agent 1 structures their profile and immediately marks `is_locked = True`.
   - If `POST /profile/onboarding` is called again for that user, the service immediately returns `HTTP 403 Forbidden` (`{"detail": "Profile already exists and is locked"}`).
   - Strictly **no** `PUT` or `PATCH` endpoints are exposed in the codebase for onboarding fields.

3. **Database-Level Hardening Readiness:**
   The `StudentProfile` model explicitly documents a PostgreSQL `BEFORE UPDATE` trigger strategy to enforce immutability at the storage engine level.
