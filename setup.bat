@echo off
REM ============================================================
REM  AI Placement Intelligence Agent — Windows Setup Script
REM  Run this ONCE from inside the jd_agent\ folder:
REM    cd jd_agent
REM    setup.bat
REM ============================================================

echo.
echo === AI Placement Intelligence Agent — Setup ===
echo.

REM ── 1. Create virtual environment ────────────────────────────
echo [1/4] Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.10+ from python.org
    pause & exit /b 1
)
echo      Done.

REM ── 2. Activate venv ─────────────────────────────────────────
call venv\Scripts\activate.bat

REM ── 3. Upgrade pip ───────────────────────────────────────────
echo [2/4] Upgrading pip...
python -m pip install --upgrade pip --quiet

REM ── 4. Install dependencies ──────────────────────────────────
echo [3/4] Installing dependencies (this takes 3-5 minutes)...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo ERROR: Some packages failed to install. See output above.
    pause & exit /b 1
)
echo      Done.

REM ── 5. Run setup check ───────────────────────────────────────
echo [4/4] Running setup verification...
python test_setup.py

echo.
echo ============================================================
echo  Setup complete! Next steps:
echo    1. Install Ollama from https://ollama.com
echo    2. Run:  ollama pull qwen3:8b
echo    3. Drop some JD files into the jd_files\ folder
echo    4. Run:  python test_setup.py   (should show all PASS)
echo ============================================================
pause
