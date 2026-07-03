@echo off
echo ============================================================
echo  AI Placement Intelligence Agent — Windows Startup Script
echo ============================================================

REM 1. Verify watched directory exists
if not exist jd_files mkdir jd_files

REM 2. Verify Ollama
echo [1/3] Verifying Ollama local service...
curl -s http://localhost:11434/api/tags > nul
if %errorlevel% neq 0 (
    echo ⚠️  Ollama service is not running on http://localhost:11434.
    echo    Please open the Ollama application before running this script.
    pause
    exit /b 1
)
echo      Ollama is online.

REM 3. Start FastAPI Backend in new window
echo [2/3] Starting FastAPI backend on http://localhost:8000...
start "FastAPI Backend" cmd /k "venv\Scripts\python.exe main.py"

REM 4. Start Streamlit in new window
echo [3/3] Starting Streamlit UI on http://localhost:8501...
start "Streamlit UI" cmd /k "venv\Scripts\streamlit.exe run frontend.py --server.port 8501"

echo ============================================================
echo  🎓 Portal is ready!
echo     - Open URL: http://localhost:8501
echo     - Close terminal windows to stop services.
echo ============================================================
pause
