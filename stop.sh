#!/bin/bash
# ============================================================
#  AI Placement Intelligence Agent — Shutdown Script
#  Usage:  bash stop.sh
# ============================================================

echo "============================================================"
echo " Stopping services..."
echo "============================================================"

# 1. FastAPI backend
if [ -f backend.pid ]; then
    PID=$(cat backend.pid)
    echo "[1/2] Stopping FastAPI backend (PID: $PID)..."
    if ps -p "$PID" > /dev/null 2>&1; then
        kill "$PID"
        for i in $(seq 1 6); do
            ps -p "$PID" > /dev/null 2>&1 || break
            sleep 1
        done
        ps -p "$PID" > /dev/null 2>&1 && kill -9 "$PID" 2>/dev/null || true
        echo "  Stopped."
    else
        echo "  Already stopped."
    fi
    rm -f backend.pid
else
    # Fallback: kill by port
    lsof -ti :8000 | xargs kill -9 2>/dev/null && echo "[1/2] Killed process on :8000." || echo "[1/2] Nothing on :8000."
fi

# 2. React Vite dev server
if [ -f ui.pid ]; then
    PID=$(cat ui.pid)
    echo "[2/2] Stopping React UI (PID: $PID)..."
    kill "$PID" 2>/dev/null || true
    rm -f ui.pid
    echo "  Stopped."
else
    lsof -ti :5173 | xargs kill -9 2>/dev/null && echo "[2/2] Killed process on :5173." || echo "[2/2] Nothing on :5173."
fi

echo "============================================================"
echo " Done. Ollama is left running (manage separately)."
echo "============================================================"
