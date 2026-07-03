#!/bin/bash
# ============================================================
#  AI Placement Intelligence Agent — Startup Script
#  Usage:  bash start.sh
#  Stop:   bash stop.sh
# ============================================================
set -e

mkdir -p jd_files

echo "============================================================"
echo " Booting Placement Intelligence Agent..."
echo "============================================================"

# ── 1. Ollama health check ────────────────────────────────────
echo "[1/3] Verifying Ollama service..."
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "  Ollama is not running. Please start Ollama first, then re-run."
    exit 1
fi
echo "  Ollama is online."

echo "[2/3] Verifying LLM model (llama3.2:latest)..."
if ! curl -s http://localhost:11434/api/tags | grep -q "llama3.2"; then
    echo "  Pulling llama3.2:latest (this takes a few minutes)..."
    curl -s -d '{"name":"llama3.2:latest"}' http://localhost:11434/api/pull | tail -1
    echo "  Model ready."
else
    echo "  llama3.2:latest found."
fi

# ── 2. FastAPI backend ────────────────────────────────────────
echo "[3/3] Starting FastAPI backend on http://localhost:8000..."

# Kill any stale backend
if [ -f backend.pid ]; then
    OLD=$(cat backend.pid)
    if ps -p "$OLD" > /dev/null 2>&1; then
        echo "  Stopping stale backend (PID $OLD)..."
        kill "$OLD" 2>/dev/null || true
        sleep 1
    fi
    rm -f backend.pid
fi

# Also kill any other python processes on port 8000
lsof -ti :8000 | xargs kill -9 2>/dev/null || true

nohup venv/bin/python main.py > backend.log 2>&1 &
echo $! > backend.pid
echo "  Backend PID: $(cat backend.pid). Waiting for health check..."

# Wait up to 45s for the embedding model to load
READY=0
for i in $(seq 1 45); do
    if curl -s http://localhost:8000/api/index/health > /dev/null 2>&1; then
        READY=1
        break
    fi
    printf "."
    sleep 1
done
echo ""

if [ $READY -eq 0 ]; then
    echo "  Backend did not start in time. Check backend.log:"
    tail -20 backend.log
    exit 1
fi
echo "  FastAPI backend is healthy."

# ── 3. React UI ───────────────────────────────────────────────
UI_PORT=5173
if lsof -ti :$UI_PORT > /dev/null 2>&1; then
    echo ""
    echo "  React UI already running on http://localhost:$UI_PORT"
else
    echo ""
    echo "  Starting React UI..."
    cd ui && nohup npm run dev > ../ui.log 2>&1 &
    echo $! > ../ui.pid
    cd ..
    sleep 3
    echo "  React UI started. Log: ui.log"
fi

echo ""
echo "============================================================"
echo " Ready!"
echo "   React UI  →  http://localhost:5173"
echo "   API docs  →  http://localhost:8000/docs"
echo "   Logs      →  tail -f backend.log"
echo "   Stop      →  bash stop.sh"
echo ""
echo " RAM tip: llama3.2 (~2 GB) loads on your FIRST chat query."
echo " Keep Brave/other heavy apps minimised before querying."
echo "============================================================"
