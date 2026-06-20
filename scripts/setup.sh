#!/usr/bin/env bash
# Olympic Industries — HR AI Resume Ranking System Setup (Linux/macOS)
# Run from project root: bash scripts/setup.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "==============================================="
echo "  HR AI System — Linux/macOS Setup"
echo "==============================================="

# ── 1. Check Python ───────────────────────────────────────────────────────────
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found. Install Python 3.10+"
    exit 1
fi
PYTHON_VER=$(python3 --version)
echo "[OK] $PYTHON_VER"

# ── 2. Create virtual environment ─────────────────────────────────────────────
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
else
    echo "[OK] venv already exists"
fi

# ── 3. Install deps ───────────────────────────────────────────────────────────
echo "Installing Python dependencies..."
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# ── 4. Playwright (optional) ──────────────────────────────────────────────────
read -p "Install Playwright for BDJobs downloader? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    ./venv/bin/playwright install chromium
fi

# ── 5. Create .env ────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    echo "Creating .env from template..."
    cp .env.example .env
    echo "[ACTION REQUIRED] Edit .env and set PG_PASSWORD"
else
    echo "[OK] .env already exists"
fi

# ── 6. Start PostgreSQL ────────────────────────────────────────────────────────
if command -v docker &> /dev/null; then
    echo "Starting PostgreSQL container..."
    docker compose up -d postgres
    echo "Waiting for PostgreSQL..."
    sleep 5
    if docker exec hr_postgres pg_isready -U postgres &> /dev/null; then
        echo "[OK] PostgreSQL is ready"
    else
        echo "WARNING: PostgreSQL may still be starting"
    fi
else
    echo "WARNING: Docker not found. Install Docker: https://docker.com"
fi

# ── 7. Check Ollama ────────────────────────────────────────────────────────────
if command -v ollama &> /dev/null; then
    echo "[OK] Ollama found"
    echo "Pulling model (may take several minutes)..."
    ollama pull qwen3:8b-q4_K_M
else
    echo "WARNING: Ollama not found. Install from https://ollama.com"
fi

# ── 8. Ollama env vars ─────────────────────────────────────────────────────────
echo "Setting Ollama parallelism env vars..."
export OLLAMA_NUM_PARALLEL=3
export OLLAMA_MAX_LOADED_MODELS=1
# Add to shell rc for persistence
for rc in ~/.bashrc ~/.zshrc; do
    if [ -f "$rc" ]; then
        if ! grep -q "OLLAMA_NUM_PARALLEL" "$rc" 2>/dev/null; then
            echo "export OLLAMA_NUM_PARALLEL=3" >> "$rc"
            echo "export OLLAMA_MAX_LOADED_MODELS=1" >> "$rc"
        fi
    fi
done
echo "[OK] Env vars set (restart Ollama for changes to take effect)"

# ── 9. Done ───────────────────────────────────────────────────────────────────
echo ""
echo "==============================================="
echo "  Setup Complete!"
echo "==============================================="
echo "Next steps:"
echo "  1. Edit .env with your database password"
echo "  2. Restart Ollama (quit tray icon + relaunch)"
echo "  3. Run: bash scripts/start.sh"
echo ""
