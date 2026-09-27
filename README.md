# 🚀 AI Powered Career Learning Platform

> A production-grade, microservices-based platform that leverages AI to deliver personalized career learning paths, skill tracking, and intelligent recommendations.

**Current Phase:** Week 1 — Foundation & Auth Infrastructure

---

## 🏗 Architecture

```
career-platform/
├── services/
│   ├── api-gateway/            # FastAPI reverse proxy — single entry point
│   │   ├── app/
│   │   │   ├── main.py         # Gateway app with proxy routes
│   │   │   └── config.py       # Service URLs and CORS config
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   └── auth-service/           # Authentication microservice
│       ├── app/
│       │   ├── core/           # Config, security, dependencies
│       │   ├── db/             # SQLAlchemy session & base
│       │   ├── models/         # ORM models (User)
│       │   ├── schemas/        # Pydantic v2 request/response schemas
│       │   ├── routers/        # API route handlers
│       │   ├── services/       # Business logic layer
│       │   └── main.py         # FastAPI application entry point
│       ├── alembic/            # Database migrations
│       ├── alembic.ini
│       ├── Dockerfile
│       └── requirements.txt
│
├── frontend/                   # React + TypeScript + Vite
│   └── src/
│       ├── components/         # Reusable UI components
│       ├── context/            # React context providers (Auth)
│       ├── pages/              # Page components
│       ├── routes/             # Router configuration
│       ├── services/           # API client and service modules
│       └── types/              # TypeScript type definitions
│
├── docker-compose.yml          # Orchestrates all services
├── .env                        # Environment variables
└── README.md
```

## 🛠 Tech Stack

| Layer        | Technology                                          |
| ------------ | --------------------------------------------------- |
| Backend      | Python 3.12, FastAPI (async), SQLAlchemy 2.0 (async) |
| Frontend     | React 19, TypeScript, Vite, Tailwind CSS v4          |
| Database     | PostgreSQL 16 (separate DB per service)              |
| Auth         | JWT (access + refresh tokens), bcrypt                |
| Migrations   | Alembic (async)                                      |
| Container    | Docker + Docker Compose                              |

## 🚀 Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/install/)
- That's it! Everything runs in containers.

### Run the entire platform

```bash
# Clone the repository
git clone <repo-url>
cd career-platform

# Copy environment template and configure
cp .env.example .env
# Edit .env with your preferred settings (defaults work for development)

# Start all services
docker-compose up --build
```

### Access the services

| Service        | URL                          | Description                     |
| -------------- | ---------------------------- | ------------------------------- |
| **Frontend**   | http://localhost:5173         | React application               |
| **API Gateway**| http://localhost:8000         | Single API entry point          |
| **Auth Service** (direct) | http://localhost:8001 | Auth microservice (internal)   |
| **Gateway Docs** | http://localhost:8000/docs  | API Gateway Swagger UI          |
| **Auth Docs**  | http://localhost:8001/docs    | Auth Service Swagger UI         |

### Test the auth flow

1. Open **http://localhost:5173** in your browser
2. Click **Create one** to go to the signup page
3. Register with an email and password (min. 8 characters)
4. You'll be automatically logged in and redirected to the Dashboard
5. The Dashboard shows your profile info and placeholder stats
6. Click **Sign out** to log out

### Test with cURL

```bash
# 1. Sign up
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "secureP@ss123"}'

# 2. Log in (returns access + refresh tokens)
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "secureP@ss123"}'

# 3. Get current user (replace <TOKEN> with access_token from step 2)
curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer <TOKEN>"

# 4. Refresh token (replace <REFRESH_TOKEN> from step 2)
curl -X POST http://localhost:8000/auth/refresh-token \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "<REFRESH_TOKEN>"}'

# 5. Health checks
curl http://localhost:8000/health
curl http://localhost:8001/health
```

## 📁 Service Details

### Auth Service (port 8001)

| Endpoint               | Method | Auth | Description                    |
| ---------------------- | ------ | ---- | ------------------------------ |
| `/auth/signup`         | POST   | ❌   | Register a new user            |
| `/auth/login`          | POST   | ❌   | Authenticate, get JWT tokens   |
| `/auth/refresh-token`  | POST   | ❌   | Refresh expired access token   |
| `/auth/me`             | GET    | ✅   | Get current user profile       |
| `/health`              | GET    | ❌   | Service health check           |

### API Gateway (port 8000)

- Proxies all `/auth/*` requests to the auth-service
- CORS configured for frontend origins
- Request logging middleware (method, path, response time)
- Health check at `/health`

## 🗄 Database

- **PostgreSQL 16 Alpine** running on port `5433` (mapped from container's `5432`)
- Dedicated database `auth_db` for the auth service
- Migrations managed by **Alembic** (async-compatible)
- Named volume `career-platform-postgres-auth-data` for data persistence

### Running migrations manually

```bash
# Inside the auth-service container
docker-compose exec auth-service alembic upgrade head

# Generate a new migration after model changes
docker-compose exec auth-service alembic revision --autogenerate -m "description"
```

## 🔒 Security

- Passwords hashed with **bcrypt** (passlib)
- **JWT access tokens** expire in 30 minutes (configurable)
- **JWT refresh tokens** expire in 7 days (configurable)
- Token type validation (access vs refresh) prevents token misuse
- All secrets configurable via environment variables
- CORS restricted to configured frontend origins

## 📋 Week 1 Checklist

- [x] Auth service with signup, login, refresh, and profile endpoints
- [x] Async SQLAlchemy with PostgreSQL (asyncpg driver)
- [x] Alembic migrations (no `create_all` in production code)
- [x] JWT access + refresh token flow with bcrypt password hashing
- [x] API Gateway with reverse proxy, CORS, and request logging
- [x] Docker Compose with healthchecks, named volumes, and env vars
- [x] React + TypeScript frontend with auth pages and protected routes
- [x] Axios interceptors for automatic token management
- [x] Production-grade code: typing, docstrings, error handling, separation of concerns

## 📄 License

Private — All rights reserved.
