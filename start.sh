#!/usr/bin/env bash
# Dimensions - Unified Startup Script
# Starts both backend and frontend services

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

# Parse arguments
SEED=false
for arg in "$@"; do
    case $arg in
        --seed)
            SEED=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--seed] [--help]"
            echo ""
            echo "Options:"
            echo "  --seed    Run seed.py before starting services"
            echo "  --help    Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown argument: $arg"
            exit 1
            ;;
    esac
done

echo "=== Dimensions Startup ==="
echo "Backend:  $BACKEND_DIR"
echo "Frontend: $FRONTEND_DIR"
echo ""

# Check virtual environment
if [ ! -d "$BACKEND_DIR/.venv" ]; then
    echo "[WARN] No .venv found in $BACKEND_DIR, creating one..."
    python3 -m venv "$BACKEND_DIR/.venv"
    source "$BACKEND_DIR/.venv/bin/activate"
    pip install -r "$BACKEND_DIR/requirements.txt"
else
    echo "[OK] Virtual environment found"
fi

# Check environment variables
echo ""
echo "Checking environment configuration..."
if [ ! -f "$BACKEND_DIR/.env" ]; then
    echo "[ERROR] .env file not found at $BACKEND_DIR/.env"
    exit 1
fi

# Source .env for checks
set -a
source "$BACKEND_DIR/.env"
set +a

# Check required variables
MISSING_VARS=()
[ -z "$MONGO_URL" ] && MISSING_VARS+=("MONGO_URL")
[ -z "$DB_NAME" ] && MISSING_VARS+=("DB_NAME")
[ -z "$MODEL_API_KEY" ] && MISSING_VARS+=("MODEL_API_KEY")
[ -z "$JWT_SECRET" ] && MISSING_VARS+=("JWT_SECRET")
[ -z "$ADMIN_EMAIL" ] && MISSING_VARS+=("ADMIN_EMAIL")
[ -z "$ADMIN_PASSWORD" ] && MISSING_VARS+=("ADMIN_PASSWORD")

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    echo "[WARN] Missing environment variables: ${MISSING_VARS[*]}"
    echo "       Please check $BACKEND_DIR/.env"
fi
echo "[OK] Environment configuration loaded"

# Check MongoDB connectivity
echo ""
echo "Checking MongoDB connectivity..."
echo "Configured: $MONGO_URL"

# Seed database if requested
if [ "$SEED" = true ]; then
    echo ""
    echo "Running seed script..."
    cd "$BACKEND_DIR"
    source .venv/bin/activate
    python seed.py
    echo "[OK] Database seeded"
fi

# Start backend in background
echo ""
echo "Starting backend..."
cd "$BACKEND_DIR"
source .venv/bin/activate
uvicorn server:app --host 0.0.0.0 --port 8001 --reload &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID (port 8001)"

# Wait for backend to be ready
echo "Waiting for backend..."
for i in {1..15}; do
    if curl -sf http://localhost:8001/api/ > /dev/null 2>&1; then
        echo "[OK] Backend is ready"
        break
    fi
    sleep 1
done

# Start frontend in background
echo ""
echo "Starting frontend..."
cd "$FRONTEND_DIR"
pnpm dev &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID (port 3000)"

# Wait for frontend to be ready
echo "Waiting for frontend..."
for i in {1..10}; do
    if curl -sf http://localhost:3000 > /dev/null 2>&1; then
        echo "[OK] Frontend is ready"
        break
    fi
    sleep 1
done

echo ""
echo "=== All services started ==="
echo "Backend:  http://localhost:8001"
echo "Frontend: http://localhost:3000"
echo "API:      http://localhost:8001/api/"
echo ""
echo "PIDs: backend=$BACKEND_PID, frontend=$FRONTEND_PID"
echo "Press Ctrl+C to stop all services"

# Trap to kill both processes on exit
trap 'echo ""; echo "Stopping services..."; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true; exit' INT TERM EXIT

# Wait forever
wait
