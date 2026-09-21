# 🚀 AI-Powered Career Learning Platform

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19.0-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-6.0-646CFF?style=flat&logo=vite&logoColor=white)](https://vitejs.dev/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An enterprise-grade, microservices-driven **AI-Powered Career Learning Platform**. It delivers personalized learning paths, dynamic roadmaps, automated AI mock interviews with instant evaluation, and real-time progress tracking.

---

## 📂 Project Structure

```
AI Powered Career learning plateform/
├── docs/                             # 📖 Architecture, API specs & in-depth documentation
│   └── PROJECT_DOCUMENTATION.md      # Comprehensive end-to-end platform guide
├── frontend/                         # 💻 React 19 + Vite Single Page Application
├── gateway/                          # 🌐 FastAPI Reverse Proxy & Auth Gateway (Port 8000)
├── infra/                            # 🐳 Infrastructure as Code & Docker Compose
│   └── docker-compose.yml
├── scripts/                          # ⚡ Orchestration & Local Dev Automation
│   ├── run_services.py               # Cross-platform Python service launcher
│   └── run-services.ps1              # Minimized PowerShell runner for Windows
├── services/                         # 🧩 Domain-Driven Microservices
│   ├── auth-service/                 # Port 8001: JWT Authentication & User Management
│   ├── catalog-service/              # Port 8002: Professions, Skills, Roadmaps & Milestones
│   ├── dashboard-bff/                # Port 8007: Aggregator Backend-for-Frontend
│   ├── interview-service/            # Port 8004: AI Mock Interview Engine & Feedback
│   ├── learning-service/             # Port 8003: Courses, Modules & Practical Tasks
│   ├── notification-service/         # Port 8006: Event Consumer & Multi-channel Alerts
│   ├── progress-service/             # Port 8005: Real-time Skill & Career Analytics
│   └── shared/                       # Shared models, security & event helpers
├── .gitignore                        # 🛡️ Hardened Git ignore rules
├── LICENSE                           # 📜 MIT Open Source License
└── README.md                         # 📌 Project Overview & Quickstart Guide
```

---

## 🏗️ Architecture Overview

The system follows a distributed microservices pattern orchestrated through a unified **API Gateway**:

```
                  ┌───────────────────────────────┐
                  │    React 19 Frontend SPA      │
                  │     http://localhost:3000     │
                  └───────────────┬───────────────┘
                                  │ HTTP / REST
                                  ▼
                  ┌───────────────────────────────┐
                  │      FastAPI API Gateway      │
                  │     http://localhost:8000     │
                  └───────────────┬───────────────┘
                                  │
    ┌──────────┬──────────┬───────┴───┬──────────┬──────────┬──────────┐
    ▼          ▼          ▼           ▼          ▼          ▼          ▼
  Auth      Catalog    Learning   Interview   Progress  Notification Dashboard
 (8001)     (8002)     (8003)      (8004)      (8005)      (8006)     (8007)
```

> 📖 **Want the deep dive?** Read the complete system design, database schemas, and event flows in **[docs/PROJECT_DOCUMENTATION.md](docs/PROJECT_DOCUMENTATION.md)**.

---

## 🧩 Microservices Directory

| Service | Port | Primary Responsibility | Storage |
|---------|------|------------------------|---------|
| **API Gateway** | `8000` | Single entry point, JWT authentication middleware, routing | Stateless |
| **Auth Service** | `8001` | Registration, login, password hashing, JWT issuance | `career_auth` |
| **Catalog Service** | `8002` | Career domains, skills, roadmaps, step progressions | `career_catalog` |
| **Learning Service** | `8003` | Learning paths, modules, assignments, project submissions | `career_learning` |
| **Interview Service** | `8004` | AI-driven mock interviews, question banks, candidate grading | `career_interview` |
| **Progress Service** | `8005` | Skill mastery scoring, timeline completion metrics | `career_progress` |
| **Notification Service**| `8006`| User alerts, background email/in-app messaging | `career_notifications`|
| **Dashboard BFF** | `8007` | High-performance aggregated data for student dashboards | Stateless |

---

## ⚡ Quick Start (Local Setup)

### Prerequisites
- **Python 3.12+**
- **Node.js 18+** & **npm**
- **PostgreSQL 14+** *(or SQLite automatic local fallback)*

---

### 1. Launch Microservices (Backend + Gateway)

You can launch all 8 services using either the **cross-platform Python launcher** or the **Windows PowerShell script**:

#### Option A: Python Orchestrator (Cross-Platform — Recommended)
```bash
# Start all 8 microservices
python scripts/run_services.py

# Check status of running services
python scripts/run_services.py status

# Interactive dev mode with live reload
python scripts/run_services.py dev

# Stop all running services
python scripts/run_services.py stop
```

#### Option B: Windows PowerShell Launcher
```powershell
# Start all services (minimized windows)
.\scripts\run-services.ps1

# Check status
.\scripts\run-services.ps1 -Action status

# Stop all services
.\scripts\run-services.ps1 -Action stop
```

---

### 2. Launch the React Frontend

```bash
cd frontend
npm install
npm run dev
```

Visit **`http://localhost:3000`** in your browser.

---

## 🔑 Default Test Credentials

Pre-seeded student account for immediate testing:
- **Email**: `testlearner@aicareer.com`
- **Password**: `SecretPassword123!`

---

## 🐳 Docker Deployment (Optional)

To spin up the entire platform including PostgreSQL databases, RabbitMQ, and microservices in isolated containers:

```bash
docker compose -f infra/docker-compose.yml up --build -d
```

To view logs or tear down:
```bash
docker compose -f infra/docker-compose.yml logs -f
docker compose -f infra/docker-compose.yml down
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
