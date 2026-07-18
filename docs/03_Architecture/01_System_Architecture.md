# AI Career Hub

# System Architecture

Version: 1.0

Author: Kartik Patidar

---

# 1. Architecture Overview

AI Career Hub follows a modern three-tier architecture with AI services integrated as independent components.

The architecture is designed to be scalable, modular, secure, and cloud-ready.

---

# 2. High Level Architecture

Frontend

↓

API Gateway (FastAPI)

↓

Business Logic

↓

AI Services

↓

Database

↓

Cloud Storage

---

# 3. Technology Stack

## Frontend

- React.js
- Tailwind CSS
- React Router
- React Query
- Axios
- Framer Motion

---

## Backend

- FastAPI
- SQLAlchemy
- Alembic

---

## Authentication

- JWT
- OAuth (Future)

---

## Database

- PostgreSQL

---

## Vector Database

- ChromaDB

---

## Storage

- AWS S3

---

## AI

- Gemini
- LangChain
- Sentence Transformers

---

## Deployment

- Docker
- Nginx
- Vercel
- Railway
- AWS


# 4. Core Components

## Frontend

Responsible for

- Authentication UI
- Dashboard
- Task Pages
- Resume Analyzer
- Interview Portal

---

## Backend

Responsible for

- Business Logic
- Authentication
- APIs
- AI Integration
- Database Operations

---

## PostgreSQL

Stores

- Users
- Tasks
- Skills
- Interviews
- Reports

---

## ChromaDB

Stores

- Embeddings
- AI Memory
- Context

---

## AWS S3

Stores

- Resume
- Images
- Certificates
- Reports

---

## Gemini API

Responsible for

- AI Feedback
- Resume Review
- Mock Interview
- Chat Assistant
