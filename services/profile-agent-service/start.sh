#!/bin/bash
set -e

echo "Waiting for PostgreSQL (profile database) to be ready..."
alembic upgrade head

echo "Starting Profile Agent Service..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
