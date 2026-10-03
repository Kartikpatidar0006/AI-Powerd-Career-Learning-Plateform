#!/bin/bash
# Start script: run Alembic migrations then start the server
set -e
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8005 --reload
