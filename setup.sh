#!/bin/bash
# ============================================================
#  AI Placement Intelligence Agent — Mac / Linux Setup
#  Run ONCE from inside the jd_agent/ folder:
#    cd jd_agent
#    bash setup.sh
# ============================================================
set -e

echo ""
echo "============================================================"
echo " AI Placement Intelligence Agent — First-Time Setup"
echo "============================================================"
echo ""

# ── 0. Check prerequisites ────────────────────────────────────
echo "[0/5] Checking prerequisites..."

if ! command -v python3 &>/dev/null; then
    echo "  ERROR: python3 not found. Install Python 3.10+ from https://python.org"
    exit 1
fi
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  Python $PY_VER found."

if ! command -v node &>/dev/null; then
    echo "  ERROR: node not found. Install Node.js 18+ from https://nodejs.org"
    exit 1
fi
echo "  Node.js $(node --version) found."

if ! command -v npm &>/dev/null; then
    echo "  ERROR: npm not found. Install Node.js from https://nodejs.org"
    exit 1
fi
echo "  npm $(npm --version) found."

if ! command -v ollama &>/dev/null; then
    echo "  ERROR: Ollama not found."
    echo "         Install from https://ollama.com then re-run setup.sh"
    exit 1
fi
echo "  Ollama found."

# ── 1. Python virtual environment ────────────────────────────
echo ""
echo "[1/5] Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip --quiet
echo "  Done."

# ── 2. Python dependencies ────────────────────────────────────
echo ""
echo "[2/5] Installing Python dependencies (3-5 minutes)..."
pip install -r requirements.txt --quiet
echo "  Done."

# ── 3. React UI dependencies ──────────────────────────────────
echo ""
echo "[3/5] Installing React UI dependencies..."
cd ui
npm install --silent
npm install react-markdown --silent
cd ..
echo "  Done."

# ── 4. Pull Ollama model ──────────────────────────────────────
echo ""
echo "[4/5] Pulling LLM model (llama3.2 ~2GB — may take a few minutes)..."
if curl -s http://localhost:11434/api/tags 2>/dev/null | grep -q "llama3.2"; then
    echo "  llama3.2:latest already downloaded."
else
    if curl -s http://localhost:11434/api/tags &>/dev/null; then
        ollama pull llama3.2:latest
        echo "  Model downloaded."
    else
        echo "  Ollama is not running. Start Ollama first, then run:"
        echo "    ollama pull llama3.2:latest"
    fi
fi

# ── 5. Create jd_files folder ────────────────────────────────
echo ""
echo "[5/5] Creating jd_files/ folder..."
mkdir -p jd_files data
echo "  Done."

echo ""
echo "============================================================"
echo " Setup complete!"
echo ""
echo " Next steps:"
echo "   1. Start Ollama (if not running)"
echo "   2. Drop your JD PDF / DOCX files into:  jd_files/"
echo "   3. Run:  bash start.sh"
echo "   4. Open: http://localhost:5173"
echo ""
echo " Requirements:"
echo "   RAM: 8 GB minimum (LLM uses ~2 GB on first query)"
echo "   Disk: ~5 GB (model + embeddings + app)"
echo "============================================================"
