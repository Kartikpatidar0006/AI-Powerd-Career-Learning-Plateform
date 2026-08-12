# Environment Variables Reference

All services share the same base set of variables. Service-specific variables are noted.

## Common (all stateful services)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | ✅ | — | Shared JWT HMAC secret. Must match across ALL services. Generate with `openssl rand -hex 32`. |
| `ALGORITHM` | ✅ | `HS256` | JWT signing algorithm. |
| `ENVIRONMENT` | — | `development` | `development` \| `staging` \| `production` |
| `DEBUG` | — | `true` | Enables verbose logging. Set `false` in production. |
| `POSTGRES_SERVER` | ✅ | `localhost` | Postgres host (Docker: container name). |
| `POSTGRES_PORT` | ✅ | varies | Postgres port (see service table). |
| `POSTGRES_USER` | ✅ | `postgres` | Postgres username. |
| `POSTGRES_PASSWORD` | ✅ | — | Postgres password. |
| `POSTGRES_DB` | ✅ | varies | Database name (see service table). |
| `BACKEND_CORS_ORIGINS` | — | `http://localhost:5173` | Comma-separated list of allowed CORS origins. |
| `DB_POOL_SIZE` | — | `10` | SQLAlchemy connection pool size. |
| `DB_MAX_OVERFLOW` | — | `20` | SQLAlchemy max pool overflow. |
| `DB_POOL_TIMEOUT` | — | `30` | Pool checkout timeout (seconds). |
| `DB_POOL_RECYCLE` | — | `1800` | Recycle connections after N seconds. |
| `DB_ECHO` | — | `false` | Log all SQLAlchemy queries (debug only). |

## Service Port and DB Reference

| Service | Internal Port | DB Name | Postgres External Port |
|---------|-------------|---------|----------------------|
| API Gateway | 8000 | — | — |
| Auth Service | 8001 | `career_auth` | 5433 |
| Catalog Service | 8002 | `career_catalog` | 5434 |
| Learning Service | 8003 | `career_learning` | 5435 |
| Interview Service | 8004 | `career_interview` | 5436 |
| Progress Service | 8005 | `career_progress` | 5437 |
| Notification Service | 8006 | `career_notifications` | 5438 |
| Dashboard BFF | 8007 | — (no DB) | — |

## Service-Specific Variables

### API Gateway (gateway/.env)

| Variable | Description |
|----------|-------------|
| `AUTH_SERVICE_URL` | e.g. `http://auth-service:8001` |
| `CATALOG_SERVICE_URL` | e.g. `http://catalog-service:8002` |
| `LEARNING_SERVICE_URL` | e.g. `http://learning-service:8003` |
| `INTERVIEW_SERVICE_URL` | e.g. `http://interview-service:8004` |
| `PROGRESS_SERVICE_URL` | e.g. `http://progress-service:8005` |
| `NOTIFICATION_SERVICE_URL` | e.g. `http://notification-service:8006` |
| `DASHBOARD_SERVICE_URL` | e.g. `http://dashboard-bff:8007` |
| `HTTP_TIMEOUT` | Proxy request timeout in seconds (default `30.0`). |

### Auth Service

| Variable | Description |
|----------|-------------|
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT access token TTL (default `30`). |
| `REFRESH_TOKEN_EXPIRE_DAYS` | JWT refresh token TTL (default `7`). |

### Learning + Interview Services (Event Publishers)

| Variable | Description |
|----------|-------------|
| `RABBITMQ_URL` | AMQP URL, e.g. `amqp://career:career@rabbitmq:5672/` |

### Notification Service (Event Consumer + Publisher)

| Variable | Description |
|----------|-------------|
| `RABBITMQ_URL` | AMQP URL (same as above). |

### Dashboard BFF

| Variable | Description |
|----------|-------------|
| `AUTH_SERVICE_URL` | Downstream auth service URL. |
| `CATALOG_SERVICE_URL` | Downstream catalog service URL. |
| `LEARNING_SERVICE_URL` | Downstream learning service URL. |
| `INTERVIEW_SERVICE_URL` | Downstream interview service URL. |
| `PROGRESS_SERVICE_URL` | Downstream progress service URL. |
| `NOTIFICATION_SERVICE_URL` | Downstream notification service URL. |
| `HTTP_TIMEOUT` | Timeout for downstream HTTP calls (default `15.0`). |

## RabbitMQ (infra)

| Variable | Default |
|----------|---------|
| `RABBITMQ_DEFAULT_USER` | `career` |
| `RABBITMQ_DEFAULT_PASS` | `career` |

Management UI: http://localhost:15672  
AMQP Port: 5672

## Generating SECRET_KEY

```bash
# Linux / macOS
openssl rand -hex 32

# Windows (PowerShell)
[System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32) | ForEach-Object { '{0:x2}' -f $_ } | Join-String
```

> **Important**: Use the same `SECRET_KEY` value for ALL services. Any service with a
> different key will reject tokens issued by auth-service.
