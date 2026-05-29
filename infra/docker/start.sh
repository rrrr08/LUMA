#!/bin/sh

# Source the virtual environment to ensure all python binaries are on the PATH
if [ -f /opt/venv/bin/activate ]; then
    . /opt/venv/bin/activate
fi

# Print PATH and python version for debugging purposes in Render logs
echo "Current PATH: $PATH"
echo "Using Python: $(which python)"

echo "Running Database Migrations..."
alembic upgrade head

echo "Starting Celery worker in background..."
celery -A app.workers.celery_app.celery_app worker --loglevel=info &

echo "Starting APScheduler in background..."
python -m app.workers.scheduler &

echo "Starting Uvicorn FastAPI server in foreground..."
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT
