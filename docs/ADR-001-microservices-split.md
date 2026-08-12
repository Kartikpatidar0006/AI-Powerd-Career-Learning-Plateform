# ADR 001 — Microservices Split

**Status**: Accepted  
**Date**: 2025-08  
**Authors**: Platform Engineering Team

---

## Context

The AI Career Hub originally shipped as a FastAPI **deployment monolith** — a single
Python process sharing one PostgreSQL database and one deployment unit. This was
appropriate early in the project lifecycle (single team, low traffic, fast iteration).

As the platform grows, the monolith has begun causing:

1. **Scaling constraints** — Interview AI evaluation (heavy CPU) scales with everything
   else, wasting resources on lightweight services.
2. **Deployment risk** — A broken migration on the `notifications` table can take down
   the auth flow.
3. **Ownership friction** — Teams cannot independently deploy their domain without a
   full regression cycle on all others.

---

## Decision

Split the monolith into **8 independently deployable services** using a
**lift-and-split** approach (move well-layered domain code, not rewrite).

### Service Boundaries

| # | Service | Port | DB | Event Role |
|---|---------|------|----|------------|
| 0 | API Gateway | 8000 | — | Routes, validates JWT |
| 1 | Auth Service | 8001 | career_auth | — |
| 2 | Catalog Service | 8002 | career_catalog | — |
| 3 | Learning Service | 8003 | career_learning | Publishes `task.graded` |
| 4 | Interview Service | 8004 | career_interview | Publishes `interview.completed` |
| 5 | Progress Service | 8005 | career_progress | — |
| 6 | Notification Service | 8006 | career_notifications | Consumes events |
| 7 | Dashboard BFF | 8007 | — | Aggregates from all |

---

## Architectural Decisions

### JWT: shared SECRET_KEY (stateless validation)

Each service validates the JWT signature locally using the same `SECRET_KEY`.
No inter-service call is needed to authenticate a request.

**Tradeoffs:**
- ✅ Zero auth latency (no network hop)
- ✅ No single auth bottleneck
- ⚠️  Token revocation requires a blocklist (Redis) — not implemented in Phase 1

### Database-per-Service

Each stateful service gets its own PostgreSQL database. The six databases
share one Postgres instance in development (separated by database names).
In production, each could run on its own Postgres cluster.

**Cross-service FK references** (e.g., `users.id` referenced in `notifications.user_id`)
are stored as plain UUIDs in the dependent service — no DB-level FK constraint
across service boundaries. Referential integrity is enforced at the application layer.

### Async Events: RabbitMQ topic exchange

Events are published to the `career_platform_events` topic exchange.

| Routing Key | Publisher | Consumer |
|------------|-----------|----------|
| `task.graded` | Learning Service | Notification Service |
| `interview.completed` | Interview Service | Notification Service |

### API Gateway

The gateway (`httpx`-based reverse proxy) is stateless and horizontally scalable.
It performs:
1. JWT signature and expiry validation
2. Route resolution (prefix → upstream URL)
3. Request forwarding with hop-by-hop header stripping
4. CORS header injection for the frontend

---

## Consequences

- **Positive**: Each service can be scaled, deployed, and tested independently.
- **Positive**: AI evaluation in Interview Service can be given GPU resources
  without scaling the auth service.
- **Negative**: Distributed tracing, service-mesh tooling, and per-service
  Alembic migrations add operational complexity.
- **Negative**: Local development now requires Docker Compose or `just` commands
  to start all services.

---

## Superseded Decisions

- The original single `docker-compose.yml` at the repo root is superseded by
  `infra/docker-compose.yml`.
- The original `backend/` directory is preserved as a reference and for gradual migration.

---

*Updated as implementation decisions evolve.*
