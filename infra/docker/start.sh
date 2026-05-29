#!/bin/sh

echo "Running Database Migrations..."
alembic upgrade head

echo "Starting Celery worker in background..."
celery -A app.workers.celery_app.celery_app worker --loglevel=info &

echo "Starting APScheduler in background..."
python -m app.workers.scheduler &

echo "Starting Uvicorn FastAPI server in foreground..."
# Use exec so that Uvicorn receives OS signals directly (e.g. SIGTERM for graceful shutdown)
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT
