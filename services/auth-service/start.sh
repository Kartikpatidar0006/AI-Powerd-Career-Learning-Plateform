#!/bin/bash
# Startup script for auth-service container.
# Runs Alembic migrations then starts the uvicorn server.

set -e

echo "⏳ Running database migrations..."
alembic upgrade head

echo "🚀 Starting auth service..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
