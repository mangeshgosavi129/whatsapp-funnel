#!/bin/bash

# Function to kill processes
kill_processes() {
    echo "Killing existing processes..."

    # Kill anything bound to port 8000 (gunicorn/uvicorn)
    sudo fuser -k 8000/tcp || true

    # Kill background workers cleanly
    pkill -f "whatsapp_worker" || true
    pkill -f "celery" || true
    pkill -f "gunicorn" || true
    pkill -f "uvicorn" || true

    echo "Processes killed."
}

# Check for --kill flag
if [ "$1" == "--kill" ]; then
    kill_processes
    exit 0
fi

if [ "$1" == "--restart" ]; then
    echo "There is no restart option, use --kill and then run the script again."
    exit 0
fi

if [ "$1" = "--reset-db-remotely" ]; then
    echo "Resetting database remotely..."

    ssh -i wabot.pem ubuntu@13.203.213.109 << 'EOF'
        set -e

        cd whatsapp-funnel

        ./prod.sh --kill

        psql "postgresql://wabot_user:aidukviuociwn@localhost:5432/wabot" << 'SQL'
        BEGIN;
        DELETE FROM messages;
        DELETE FROM conversation_events;
        DELETE FROM conversations;
        DELETE FROM leads;
        COMMIT;
SQL

        ./prod.sh
EOF

    exit 0
fi

# Activate virtual environment
if [ -f "./.venv/bin/activate" ]; then
    source ./.venv/bin/activate
fi

# Create logs directory if it doesn't exist
mkdir -p logs

echo "------------------------------------------"
# Start Redis if not running
if ! pgrep -x "redis-server" > /dev/null; then
    echo "Starting Redis Server (logs in logs/redis.log)..."
    # Check if redis-server is in path
    if command -v redis-server >/dev/null 2>&1; then
        nohup redis-server > logs/redis.log 2>&1 &
        # Give it a moment to start
        sleep 2
    else
        echo "WARNING: redis-server not found in PATH. Please install Redis."
    fi
else
    echo "Redis Server is already running."
fi

echo "Starting FastAPI server on 0.0.0.0:8000 (logs in logs/server.log)..."
nohup gunicorn server.main:app \
  --workers 1 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  >> logs/server.log 2>&1 &
SERVER_PID=$!

echo "Starting WhatsApp Worker (logs in logs/worker.log)..."
nohup python3 -m whatsapp_worker.main >> logs/worker.log 2>&1 &
WORKER_PID=$!

# Start Celery Worker and Beat using Python module
echo "Starting Celery Worker (logs in logs/celery_worker.log)..."
nohup python3 -m celery -A whatsapp_worker.tasks.celery_app worker --loglevel=info >> logs/celery_worker.log 2>&1 &
CELERY_WORKER_PID=$!

echo "Starting Celery Beat (logs in logs/celery_beat.log)..."
nohup python3 -m celery -A whatsapp_worker.tasks.celery_app beat --loglevel=info >> logs/celery_beat.log 2>&1 &
CELERY_BEAT_PID=$!

echo "------------------------------------------"
echo "Processes started in background."
echo "FastAPI Server PID: $SERVER_PID"
echo "WhatsApp Worker PID: $WORKER_PID"
echo "Celery Worker PID:  $CELERY_WORKER_PID"
echo "Celery Beat PID:    $CELERY_BEAT_PID"
echo "------------------------------------------"
echo "To stop them, run: ./prod.sh --kill"
