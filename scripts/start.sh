#!/usr/bin/env bash
# Olympic Industries — Start HR AI System (Linux/macOS)
# Run from project root: bash scripts/start.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "==============================================="
echo "  Starting HR AI System"
echo "==============================================="

# ── 1. Start PostgreSQL ───────────────────────────────────────────────────────
if command -v docker &> /dev/null; then
    if ! docker ps --format "{{.Names}}" | grep -q "hr_postgres"; then
        echo "Starting PostgreSQL container..."
        docker compose up -d postgres
        sleep 3
    else
        echo "[OK] PostgreSQL already running"
    fi
else
    echo "WARNING: Docker not found — assuming PostgreSQL is running elsewhere"
fi

# ── 2. Verify Ollama ───────────────────────────────────────────────────────────
if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "[OK] Ollama is running"
else
    echo "WARNING: Ollama not responding on localhost:11434"
fi

# ── 3. Start Streamlit ─────────────────────────────────────────────────────────
echo "Starting Streamlit app..."
./venv/bin/streamlit run resume_app/Home.py
