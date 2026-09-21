# 🚀 AI Powered Career Learning Platform — Complete Project Documentation

> **Ye document AI ko (ya kisi bhi developer ko) poore project ka context dene ke liye banaya gaya hai.**
> Is file mein project ka har ek folder, service, feature, aur architecture detail mein explain ki gayi hai.

---

## 📌 Project Ka Ek-Line Summary

**"Ek AI-powered microservices platform jo students ko unke career roadmap ke according personalized learning paths, mock interviews aur real-time progress tracking deta hai."**

---

## 🏗️ Overall Architecture — Microservices

Ye platform **Microservices Architecture** follow karta hai. Iska matlab hai ki har ek feature ek alag independent service hai jo apne alag database ke saath kaam karta hai. Ye services ek dusre se **REST API calls** aur **RabbitMQ (message broker)** ke through communicate karte hain.

```
                        ┌────────────────────────────────────────────────────────────┐
                        │                       FRONTEND (React/Vite)                │
                        │                    http://localhost:5173                   │
                        └────────────────────────┬───────────────────────────────────┘
                                                 │ HTTP Requests
                                                 ▼
                        ┌────────────────────────────────────────────────────────────┐
                        │                  API GATEWAY (FastAPI)                     │
                        │                   http://localhost:8000                    │
                        │     (Saari requests pehle yahan aati hain, phir route      │
                        │      hoti hain sahi service tak)                           │
                        └──────┬──────┬──────┬──────┬──────┬──────┬────────┬────────┘
                               │      │      │      │      │      │        │
              ┌────────────────┘      │      │      │      │      │        └────────────────────┐
              ▼                       ▼      │      ▼      │      ▼                             ▼
   ┌──────────────────┐   ┌──────────────┐  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
   │  Auth Service    │   │Catalog Svc   │  │  │Learning Svc  │  │Interview Svc │  │Dashboard BFF     │
   │  :8001           │   │  :8002       │  │  │  :8003       │  │  :8004       │  │  :8007           │
   │  (JWT Auth)      │   │(Professions  │  │  │(Tasks,Courses│  │(Mock Inter-  │  │(Aggregates data  │
   │                  │   │ Skills,      │  │  │ LearningPath)│  │ views, AI    │  │ from all services│
   │  DB: :5433       │   │ Roadmaps)    │  │  │              │  │ Evaluation)  │  │ for dashboard)   │
   └──────────────────┘   │  DB: :5434   │  │  │  DB: :5435   │  │  DB: :5436   │  └──────────────────┘
                          └──────────────┘  │  └──────────────┘  └──────────────┘
                                            │
                               ┌────────────┴────────────┐
                               ▼                         ▼
                   ┌──────────────────┐   ┌──────────────────────┐
                   │  Progress Svc    │   │  Notification Svc     │
                   │  :8005           │   │  :8006                │
                   │(User Progress,   │   │(Notifications,        │
                   │ Roadmap Progress)│   │ Event Consumer)       │
                   │  DB: :5437       │   │  DB: :5438            │
                   └──────────────────┘   └──────────────────────┘
                              │                       │
                              └──────────┬────────────┘
                                         ▼
                            ┌─────────────────────────┐
                            │   RabbitMQ Message Broker│
                            │   :5672 (AMQP)          │
                            │   :15672 (Web UI)        │
                            └─────────────────────────┘
```

---

## 📁 Root-Level Folder Structure

```
AI Powered Career learning plateform/
│
├── frontend/                  → React (Vite) frontend application
├── gateway/                   → API Gateway (FastAPI) — single entry point
├── services/                  → Saari backend microservices
│   ├── auth-service/          → Authentication & User management
│   ├── catalog-service/       → Professions, Skills, Career Roadmaps
│   ├── learning-service/      → Learning Paths, Courses, Tasks
│   ├── interview-service/     → Mock Interviews + AI Evaluation
│   ├── progress-service/      → User Progress Tracking
│   ├── notification-service/  → In-app Notifications
│   ├── dashboard-bff/         → Dashboard Backend-For-Frontend (aggregator)
│   └── shared/                → Common utilities (JWT security, event publisher)
├── infra/
│   └── docker-compose.yml     → Poore platform ko Docker mein start karne ke liye
├── run-services.ps1           → Windows PowerShell script to run all services locally
├── run_services.py            → Python script to run all services locally
├── .gitignore
├── LICENCE
└── README.md
```

---

## 🌐 Tech Stack

### Backend (Har Service)
| Technology | Purpose |
|------------|---------|
| **Python 3.11+** | Programming language |
| **FastAPI** | Web framework (async, fast, auto-docs) |
| **SQLAlchemy 2.x** | ORM — database models |
| **PostgreSQL 16** | Relational database (har service ka alag DB) |
| **Alembic** | Database migrations |
| **RabbitMQ** | Async event/message broker |
| **Pydantic v2** | Data validation & schemas |
| **Uvicorn** | ASGI server |
| **Docker** | Containerization |

### Frontend
| Technology | Purpose |
|------------|---------|
| **React 18** | UI framework |
| **Vite** | Build tool (fast dev server) |
| **React Router v6** | Client-side routing |
| **Axios** | HTTP client (API calls) |
| **React Hot Toast** | Notifications/toasts |
| **Vanilla CSS** | Styling (custom variables, dark theme) |

### Infrastructure
| Technology | Purpose |
|------------|---------|
| **Docker Compose** | Local development orchestration |
| **pgAdmin** | Database management UI (optional) |

---

## 🔧 Services Detail

### 1️⃣ Auth Service (Port: 8001, DB Port: 5433)

**Purpose:** User registration, login, JWT token management, user profiles.

**Database:** `career_auth`

**Folder Structure:**
```
services/auth-service/
├── app/
│   ├── main.py              → FastAPI app entry point
│   ├── api/
│   │   └── v1/
│   │       ├── auth/        → /auth/login, /auth/register, /auth/refresh, /auth/me
│   │       └── users/       → /users/... (user management)
│   ├── models/
│   │   ├── user.py          → User table (id, email, full_name, hashed_password, role_id, ...)
│   │   ├── role.py          → Role table (admin, student, mentor)
│   │   └── user_activity.py → User activity log
│   ├── schemas/             → Pydantic request/response schemas
│   ├── repositories/        → DB query layer
│   ├── services/            → Business logic
│   ├── core/
│   │   └── config.py        → Environment variables & settings
│   └── db/
│       ├── init_db.py       → Database initialization
│       ├── seed.py          → Seed initial roles (admin, student, mentor)
│       └── session.py       → DB session factory
├── .env                     → Environment variables (DB URL, JWT secrets, etc.)
├── Dockerfile
└── requirements.txt
```

**Key Features:**
- JWT Access + Refresh Token system
- Role-based access (admin / student / mentor)
- Bcrypt password hashing
- Auto token refresh on expiry
- User activity tracking

**API Endpoints:**
- `POST /api/v1/auth/login` — Login karo
- `POST /api/v1/auth/register` — Register karo
- `POST /api/v1/auth/refresh` — Token refresh karo
- `GET  /api/v1/auth/me` — Apna profile dekho
- `POST /api/v1/auth/change-password` — Password change karo

---

### 2️⃣ Catalog Service (Port: 8002, DB Port: 5434)

**Purpose:** Career professions ka catalog manage karna — which skills are needed for which profession, what's the roadmap.

**Database:** `career_catalog`

**Folder Structure:**
```
services/catalog-service/
├── app/
│   ├── main.py
│   ├── api/v1/
│   │   ├── professions/     → CRUD for professions
│   │   ├── skills/          → CRUD for skills
│   │   └── career_roadmaps/ → CRUD for roadmaps and steps
│   ├── models/
│   │   ├── profession.py    → Profession table
│   │   ├── skill.py         → Skill table
│   │   └── career_roadmap.py→ CareerRoadmap + RoadmapStep tables
│   ├── schemas/
│   ├── repositories/
│   ├── services/
│   ├── events/              → Event publishing to RabbitMQ
│   ├── core/
│   └── db/
```

**Key Data Models:**
- **Profession** — `id`, `name`, `slug`, `description`, `category`, `average_salary`, `growth_rate`, `required_skills` (JSONB), `roadmap` (JSONB), `is_active`
- **Skill** — `id`, `name`, `slug`, `description`, `category`, `level`, `profession_id` (FK)
- **CareerRoadmap** — Structured learning roadmap for a profession
- **RoadmapStep** — Individual steps within a roadmap

**API Endpoints:**
- `GET/POST /api/v1/professions` — Professions list / create
- `GET/PUT/DELETE /api/v1/professions/{id}` — Single profession
- `GET/POST /api/v1/skills` — Skills
- `GET/POST /api/v1/career-roadmaps` — Roadmaps
- `GET/POST /api/v1/roadmap-steps` — Roadmap steps

---

### 3️⃣ Learning Service (Port: 8003, DB Port: 5435)

**Purpose:** Student ka learning journey manage karna — learning paths, courses, tasks, task submissions aur AI feedback.

**Database:** `career_learning`

**Folder Structure:**
```
services/learning-service/
├── app/
│   ├── main.py
│   ├── api/v1/
│   │   ├── learning_paths/      → Learning path CRUD
│   │   ├── courses/             → Course CRUD
│   │   ├── tasks/
│   │   │   ├── router.py        → Task routes
│   │   │   └── feedback_router.py → Task feedback routes
│   │   └── resume/              → Resume builder/generation
│   ├── models/
│   │   ├── learning_path.py     → LearningPath table
│   │   ├── course.py            → Course table
│   │   ├── task.py              → Task + TaskSubmission tables
│   │   └── task_feedback.py     → AI-generated feedback on tasks
│   ├── events/                  → Publishes task.graded events to RabbitMQ
│   ├── schemas/
│   ├── repositories/
│   └── services/
```

**Key Features:**
- Learning path ek profession ke liye structured hoti hai
- Courses learning path ke steps hote hain
- Tasks students ko complete karne hote hain
- Task submission ke baad AI evaluate karke feedback deta hai
- `task.graded` event publish hota hai RabbitMQ pe — Progress Service aur Notification Service ise consume karte hain
- Resume generation feature

---

### 4️⃣ Interview Service (Port: 8004, DB Port: 5436)

**Purpose:** AI-powered mock interview system — interview schedule karo, questions answer karo, AI feedback pao.

**Database:** `career_interview`

**Folder Structure:**
```
services/interview-service/
├── app/
│   ├── main.py
│   ├── ai/                       → AI Provider abstraction layer
│   │   ├── base_provider.py      → Abstract base class for AI providers
│   │   ├── dummy_provider.py     → Dev/testing ke liye dummy AI
│   │   └── factory.py            → get_ai_provider() — kaunsa provider use karna hai
│   ├── api/v1/
│   │   ├── interviews/           → Interview CRUD + lifecycle management
│   │   └── ai/                   → AI evaluation endpoints
│   ├── models/
│   │   ├── interview.py          → Interview table
│   │   ├── interview_question.py → Questions asked in interview
│   │   ├── interview_feedback.py → AI-generated feedback
│   │   ├── learning_path.py      → Local copy for context
│   │   ├── profession.py         → Local copy for context
│   │   ├── skill.py              → Local copy for context
│   │   ├── user.py               → Local copy for context
│   │   └── user_progress.py      → User progress data
│   ├── events/                   → Publishes interview.completed events
│   ├── schemas/
│   ├── repositories/
│   └── services/
```

**Interview Flow:**
```
1. Schedule Interview  → POST /api/v1/interviews/schedule/{taskId}
2. Start Interview     → POST /api/v1/interviews/{id}/start
3. Get Questions       → GET  /api/v1/interviews/{id}/questions
4. Answer Questions    → POST /api/v1/interviews/questions/{qId}/answer
5. Finish Interview    → POST /api/v1/interviews/{id}/finish
6. AI Evaluate         → POST /api/v1/interviews/{id}/evaluate
7. View Feedback       → GET  /api/v1/interviews/{id}/feedback
```

**AI Provider System:**
- Abstract `BaseAIProvider` class — real AI (Gemini/GPT) ya dummy provider switch kar sakte ho
- `DummyAIProvider` — development mein real API calls ki zarurat nahi, pre-defined responses deta hai
- `factory.py` — environment variable se decide hota hai kaunsa provider use karna hai

---

### 5️⃣ Progress Service (Port: 8005, DB Port: 5437)

**Purpose:** User ka overall learning progress track karna — kaunsa roadmap kitna complete hua, kaun se tasks done hain.

**Database:** `career_progress`

**Folder Structure:**
```
services/progress-service/
├── app/
│   ├── main.py
│   ├── api/v1/            → Progress endpoints
│   ├── models/            → UserProgress, RoadmapProgress tables
│   ├── events/            → Consumes task.graded & interview.completed events
│   ├── schemas/
│   ├── repositories/
│   └── services/
```

**Key Feature:** RabbitMQ events consume karta hai — jab koi task complete ho ya interview ho, Progress Service automatically user ka progress update karta hai. Direct API call ki zarurat nahi.

---

### 6️⃣ Notification Service (Port: 8006, DB Port: 5438)

**Purpose:** In-app notifications manage karna — task complete, interview done, achievements, etc.

**Database:** `career_notifications`

**Folder Structure:**
```
services/notification-service/
├── app/
│   ├── main.py
│   ├── api/v1/            → Notification endpoints
│   ├── models/            → Notification table
│   ├── events/            → Consumes events from RabbitMQ
│   ├── schemas/
│   ├── repositories/
│   └── services/
```

**Flow:** Other services events publish karte hain → Notification Service consume karta hai → User ko notification milti hai.

---

### 7️⃣ Dashboard BFF — Backend For Frontend (Port: 8007)

**Purpose:** Dashboard ke liye ek aggregator service. Frontend ko ek single API call mein saara dashboard data milta hai (multiple services se data combine karke).

**Folder Structure:**
```
services/dashboard-bff/
├── app/
│   ├── main.py
│   ├── api/v1/            → /dashboard/student, /dashboard/me
│   ├── models/
│   ├── events/
│   ├── schemas/
│   ├── repositories/
│   └── services/
```

**Pattern:** BFF (Backend For Frontend) pattern — har service ka alag-alag API call karne ki bajay, ek call mein saara data milta hai. Performance aur simplicity ke liye.

---

### 8️⃣ Shared Module

```
services/shared/
├── event_publisher.py   → RabbitMQ pe events publish karne ka common code
└── security.py          → JWT token verification (gateway ke liye)
```

---

### 9️⃣ API Gateway (Port: 8000)

**Purpose:** Single entry point for all requests. Frontend sirf `localhost:8000` se baat karta hai. Gateway appropriate service pe request forward karta hai.

```
gateway/
├── app/
├── .env
├── .env.example
├── Dockerfile
└── requirements.txt
```

**Service URL Routing:**
```
/api/v1/auth/*            → auth-service:8001
/api/v1/professions/*     → catalog-service:8002
/api/v1/skills/*          → catalog-service:8002
/api/v1/career-roadmaps/* → catalog-service:8002
/api/v1/learning-paths/*  → learning-service:8003
/api/v1/tasks/*           → learning-service:8003
/api/v1/interviews/*      → interview-service:8004
/api/v1/user-progress/*   → progress-service:8005
/api/v1/notifications/*   → notification-service:8006
/api/v1/dashboard/*       → dashboard-bff:8007
```

---

## 💻 Frontend Structure

**Tech:** React + Vite + React Router + Axios

```
frontend/src/
├── App.jsx              → Root component (BrowserRouter + AuthProvider + Routes)
├── main.jsx             → React app entry point
├── assets/              → Images, icons
├── components/          → Reusable UI components
│   ├── Breadcrumb/
│   ├── Button/
│   ├── Card/
│   ├── EmptyState/
│   ├── ErrorState/
│   ├── Input/
│   ├── Interview/       → Interview-specific components
│   ├── Loader/
│   ├── Modal/
│   ├── Navbar/
│   ├── PageHeader/
│   ├── Sidebar/
│   └── Textarea/
├── constants/
│   └── apiEndpoints.js  → Saari API endpoint URLs ek jagah
├── context/
│   └── AuthContext.jsx  → Global authentication state (user, token, login, logout)
├── hooks/               → Custom React hooks
├── layouts/             → Page layout wrappers
├── pages/               → Saare application pages (17 pages)
│   ├── LoginPage.jsx              → Login form
│   ├── RegisterPage.jsx           → Registration form
│   ├── OnboardingPage.jsx         → New user onboarding
│   ├── ProfessionSelectionPage.jsx→ Profession choose karo
│   ├── DashboardPage.jsx          → Main dashboard (saara overview)
│   ├── RoadmapPage.jsx            → Career roadmap visualization
│   ├── TaskListPage.jsx           → Learning tasks list
│   ├── TaskDetailsPage.jsx        → Task detail view
│   ├── TaskSubmissionPage.jsx     → Task submit karo
│   ├── TaskFeedbackPage.jsx       → Task ke baad AI feedback dekho
│   ├── InterviewListPage.jsx      → All interviews list
│   ├── InterviewPage.jsx          → Live interview session
│   ├── InterviewFeedbackPage.jsx  → Interview ke baad detailed AI feedback
│   ├── ProgressPage.jsx           → Overall progress analytics
│   ├── NotificationPage.jsx       → In-app notifications
│   ├── ProfilePage.jsx            → User profile management
│   └── NotFoundPage.jsx           → 404 page
├── routes/
│   └── AppRoutes.jsx    → All routes defined yahan
├── services/            → API call functions (axios wrappers)
│   ├── api.js           → Axios instance + interceptors (auto token + refresh)
│   ├── authService.js   → login(), register(), getMe(), logout()
│   ├── dashboardService.js
│   ├── interviewService.js
│   ├── notificationService.js
│   ├── onboardingService.js
│   ├── professionService.js
│   ├── progressService.js
│   ├── roadmapService.js
│   ├── taskService.js
│   └── userService.js
├── styles/
│   └── index.css        → Global CSS (dark theme, CSS variables)
├── types/               → Type definitions
└── utils/               → Utility functions
```

---

## 🔐 Authentication Flow

```
User opens app
      ↓
AuthContext checks localStorage for token
      ↓ (token found)
authService.getMe() → GET /api/v1/auth/me
      ↓ (success)
User logged in ✓
      ↓ (401 error — token expired)
Try refresh token → POST /api/v1/auth/refresh
      ↓ (success)
New token stored, user logged in ✓
      ↓ (refresh also fails)
Logout + Redirect to /login
```

**JWT System:**
- **Access Token** — Short-lived, stored in localStorage as `token` & `access_token`
- **Refresh Token** — Long-lived, stored as `refresh_token`
- Axios **request interceptor**: Har request mein automatically `Authorization: Bearer <token>` header add ho jaata hai
- Axios **response interceptor**: 401 mein automatically refresh try karta hai, saari pending requests queue ho jaati hain

---

## 🐇 Event-Driven Communication (RabbitMQ)

Services direct API calls ki bajay events ke through baat karte hain:

```
Learning Service                    RabbitMQ                    Progress Service
     │                                  │                              │
     │── task.graded event ────────────▶│── delivers ────────────────▶│
     │                                  │                              │ (progress update)
     │                                  │                              │
     │                                  │                    Notification Service
     │                                  │── delivers ────────────────▶│
     │                                  │                              │ (creates notification)
     │
Interview Service
     │── interview.completed event ────▶│── delivers ────────────────▶│ (both services)
```

**Benefits:**
- Services loosely coupled — ek service fail ho toh doosri pe asar nahi
- Async processing — user wait nahi karta
- Easy to add new consumers later

---

## 🗄️ Database Architecture

Har service ka **alag PostgreSQL database** hai (Database-per-Service pattern):

| Service | Database | Port |
|---------|----------|------|
| Auth Service | `career_auth` | 5433 |
| Catalog Service | `career_catalog` | 5434 |
| Learning Service | `career_learning` | 5435 |
| Interview Service | `career_interview` | 5436 |
| Progress Service | `career_progress` | 5437 |
| Notification Service | `career_notifications` | 5438 |

**Why separate databases?**
- Ek service doosre service ka data directly access nahi kar sakti
- Services independent scale ho sakti hain
- Schema change karna doosri service pe asar nahi karta
- True microservices independence

---

## 📱 Frontend Pages — User Journey Map

```
/login                    → LoginPage
/register                 → RegisterPage
/onboarding               → OnboardingPage (new users ke liye wizard)
/select-profession        → ProfessionSelectionPage

/dashboard                → DashboardPage (main hub)
/roadmap                  → RoadmapPage (career roadmap visualization)
/tasks                    → TaskListPage (all learning tasks)
/tasks/:id                → TaskDetailsPage
/tasks/:id/submit         → TaskSubmissionPage
/submissions/:id/feedback → TaskFeedbackPage (AI feedback)

/interviews               → InterviewListPage
/interviews/:id           → InterviewPage (live interview session)
/interviews/:id/feedback  → InterviewFeedbackPage (detailed AI feedback)

/progress                 → ProgressPage (analytics & charts)
/notifications            → NotificationPage
/profile                  → ProfilePage
*                         → NotFoundPage (404)
```

---

## 🛠️ Local Development Setup

### Option 1: Docker Compose (Recommended — Saab kuch ek saath start)
```bash
cd infra
docker compose up -d                       # Saari services start karo
docker compose --profile tools up -d      # pgAdmin bhi include karo
docker compose logs -f auth-service       # Kisi service ke logs dekho
docker compose down                        # Sab band karo
docker compose down -v                     # Sab band + data bhi wipe karo
```

### Option 2: Python Script (Docker ke bina)
```bash
python run_services.py
```

### Option 3: PowerShell Script (Windows)
```powershell
.\run-services.ps1
```

### Frontend Run Karo
```bash
cd frontend
npm install
npm run dev     # Opens http://localhost:5173
```

---

## 🌍 Complete Ports Reference

| Service | Local Port | Description |
|---------|-----------|-------------|
| Frontend | 5173 | React Vite dev server |
| **API Gateway** | **8000** | **Single entry point for frontend** |
| Auth Service | 8001 | JWT Auth & User Management |
| Catalog Service | 8002 | Professions, Skills, Roadmaps |
| Learning Service | 8003 | Tasks & Courses |
| Interview Service | 8004 | Mock Interviews + AI |
| Progress Service | 8005 | Progress Tracking |
| Notification Service | 8006 | In-app Notifications |
| Dashboard BFF | 8007 | Dashboard data aggregation |
| RabbitMQ AMQP | 5672 | Message broker |
| RabbitMQ UI | 15672 | Web management dashboard |
| Postgres Auth | 5433 | Auth DB |
| Postgres Catalog | 5434 | Catalog DB |
| Postgres Learning | 5435 | Learning DB |
| Postgres Interview | 5436 | Interview DB |
| Postgres Progress | 5437 | Progress DB |
| Postgres Notif | 5438 | Notifications DB |
| pgAdmin | 5050 | DB admin UI (optional, tools profile) |

---

## 🧩 Each Service Ka Internal Folder Pattern

Har backend service ek common pattern follow karta hai:

```
app/
├── main.py          → FastAPI app, middleware, routers register
├── api/
│   └── v1/          → API version 1
│       └── <feature>/
│           └── router.py  → Endpoints defined yahan
├── models/          → SQLAlchemy ORM models (database tables)
├── schemas/         → Pydantic models (request/response validation)
├── repositories/    → Database query functions (raw DB layer)
├── services/        → Business logic layer
├── core/
│   └── config.py    → Settings from .env file
├── db/
│   ├── base.py      → SQLAlchemy Base
│   ├── session.py   → DB session
│   └── init_db.py   → DB initialization on startup
└── events/          → RabbitMQ event publisher/consumer
```

**Layer Architecture (Request se DB tak):**
```
HTTP Request
    → Router (endpoint handle karo)
        → Service (business logic)
            → Repository (DB query)
                → Database (PostgreSQL)
            → Event Publisher (RabbitMQ pe event bhejo)
```

---

## 🤖 AI Integration (Interview Service)

```
services/interview-service/app/ai/
├── base_provider.py    → Abstract class: generate_questions(), evaluate_answer(), evaluate_interview()
├── dummy_provider.py   → Returns hardcoded responses (dev/testing ke liye, no real AI needed)
└── factory.py          → get_ai_provider() → returns correct provider based on env
```

**Design Pattern:** Strategy Pattern — Real AI provider (Gemini / GPT / Claude) add karna ho toh sirf `base_provider.py` implement karo aur `factory.py` update karo. Baaki koi code touch nahi karna.

**Current Status:** `DummyAIProvider` use ho raha hai development mein.
**Future:** Environment variable se real Gemini/GPT API connect hoga.

---

## 🔑 Environment Variables (.env files)

Har service ka alag `.env` file hai. Common variables:

```env
# Database
POSTGRES_SERVER=localhost
POSTGRES_PORT=5433
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=career_auth

# Security
SECRET_KEY=<jwt-secret-key>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=30

# App Config
PROJECT_NAME=Auth Service
PROJECT_VERSION=1.0.0
API_V1_STR=/api/v1
DEBUG=true
ENVIRONMENT=development

# CORS
BACKEND_CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]

# RabbitMQ (where applicable)
RABBITMQ_URL=amqp://career:career@localhost:5672/
```

---

## 📊 User Roles

| Role | Description | Access Level |
|------|-------------|--------------|
| `admin` | System administrator | Full access — manage professions, skills, all users |
| `student` | Learner (main user) | Browse roadmaps, complete tasks, take interviews |
| `mentor` | Industry mentor | Provide feedback on student work |

---

## 🔄 Complete Data Flow Example

**"Student ek task complete karta hai":**

```
1. Student → Frontend (TaskSubmissionPage)
      ↓
2. Frontend → POST /api/v1/tasks/{taskId}/submit → API Gateway (8000)
      ↓
3. API Gateway → Learning Service (8003)
      ↓
4. Learning Service → Saves submission in career_learning DB
      ↓
5. Learning Service → AI evaluates submission → Generates feedback
      ↓
6. Learning Service → Publishes "task.graded" event to RabbitMQ
      ↓
7a. Progress Service consumes event → Updates user progress in career_progress DB
7b. Notification Service consumes event → Creates notification in career_notifications DB
      ↓
8. Student refreshes → Dashboard shows updated progress + new notification
```

---

## 🚀 Current Development Status

| Service/Feature | Status |
|----------------|--------|
| Auth Service (login, register, JWT) | ✅ Complete |
| Catalog Service (professions, skills, roadmaps) | ✅ Complete |
| Learning Service (tasks, courses, learning paths) | ✅ Complete |
| Interview Service (mock interviews + AI evaluation) | ✅ Complete |
| Progress Service | ✅ Complete |
| Notification Service | ✅ Complete |
| Dashboard BFF | ✅ Complete |
| API Gateway | ✅ Complete |
| Frontend — All 17 Pages | ✅ Complete |
| Docker Compose Infrastructure | ✅ Complete |
| Real AI Integration (Gemini/GPT) | 🔄 Pending (dummy provider hai abhi) |
| Production Deployment | 🔄 Pending (abhi sirf local dev) |

---

## 📝 Important Files Quick Reference

| File | Purpose |
|------|---------|
| `infra/docker-compose.yml` | Full infrastructure definition |
| `frontend/src/constants/apiEndpoints.js` | All API URLs centralized |
| `frontend/src/context/AuthContext.jsx` | Global auth state management |
| `frontend/src/services/api.js` | Axios instance + auto token refresh |
| `services/shared/event_publisher.py` | RabbitMQ event publishing utility |
| `services/shared/security.py` | JWT verification for gateway |
| `services/interview-service/app/ai/` | AI provider abstraction layer |
| `services/auth-service/app/db/seed.py` | Initial roles seed data |
| `run_services.py` | Python script to start all services locally |
| `run-services.ps1` | PowerShell script for Windows |

---

*Document created: August 2026*
*Project: AI Powered Career Learning Platform*
*GitHub: https://github.com/Kartikpatidar0006/AI-Powerd-Career-Learning-Plateform*
