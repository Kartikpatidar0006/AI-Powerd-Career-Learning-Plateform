# 🚀 AI-Powered Career Learning Platform (Microservices Architecture)

An end-to-end, production-ready **AI-Powered Career Learning Platform** built with **FastAPI**, **React + Vite**, **PostgreSQL**, **RabbitMQ**, and an **API Gateway**.

---

## 🏗️ Architecture Overview

The platform uses a decoupled microservices architecture with a single API Gateway entry point:

```
[ React + Vite Frontend ]
           │
           ▼ (HTTP / REST)
  [ API Gateway ] (Port 8000)
           │
 ┌─────────┼───────────────┬────────────────┬─────────────────┬──────────────────┬─────────────────┐
 │         │               │                │                 │                  │                 │
 ▼         ▼               ▼                ▼                 ▼                  ▼                 ▼
Auth     Catalog        Learning        Interview         Progress          Notification     Dashboard BFF
(8001)   (8002)          (8003)          (8004)            (8005)              (8006)           (8007)
```

---

## 🧩 Microservices Suite

| # | Service | Port | Description | Database |
|---|---------|------|-------------|----------|
| 1 | **API Gateway** | `8000` | Single entry point, JWT middleware, reverse proxy | *Stateless* |
| 2 | **Auth Service** | `8001` | User registration, login, JWT token issuance | `career_auth` |
| 3 | **Catalog Service** | `8002` | Professions, Skills, Roadmaps & Milestone steps | `career_catalog` |
| 4 | **Learning Service** | `8003` | Learning paths, courses, tasks & submissions | `career_learning` |
| 5 | **Interview Service** | `8004` | AI-powered mock interviews & evaluation engine | `career_interview` |
| 6 | **Progress Service** | `8005` | Skill progress tracking & completion analytics | `career_progress` |
| 7 | **Notification Service** | `8006` | Multi-channel notifications & RabbitMQ event consumer | `career_notifications` |
| 8 | **Dashboard BFF** | `8007` | Aggregator service providing unified learner dashboard data | *Stateless* |

---

## ⚡ Quick Start (Local Setup)

### Prerequisites
- **Python 3.12+**
- **Node.js 18+**
- **PostgreSQL 14+** (running on port `5432`)

### 1. Launch Microservices & Gateway
Run the provided PowerShell launcher script from the root directory:

```powershell
# Start all 8 microservices
.\run-services.ps1

# To stop all running services:
.\run-services.ps1 -Action stop
```

### 2. Launch React Frontend
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000` in your web browser.

---

## 🔑 Default Test Credentials

Pre-seeded test account ready for instant testing:
- **Email**: `testlearner@aicareer.com`
- **Password**: `SecretPassword123!`

---

## 🐳 Docker Deployment (Optional)

To launch the full microservices stack using Docker Compose:

```bash
docker-compose -f infra/docker-compose.yml up --build -d
```
