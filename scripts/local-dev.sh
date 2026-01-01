#!/bin/bash
set -e

cd "$(dirname "$0")/.."

# Start DB
docker compose up -d db
echo "Waiting for PostgreSQL..."
sleep 3

# Backend
cd backend
pip install -e ".[dev]" -q
alembic upgrade head
uvicorn src.main:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

# Frontend
cd frontend
npm ci --silent
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo ""

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; docker compose stop db" EXIT
wait
