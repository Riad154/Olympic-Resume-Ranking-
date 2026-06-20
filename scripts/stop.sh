#!/usr/bin/env bash
# Olympic Industries — Stop HR AI System (Linux/macOS)
# Run from project root: bash scripts/stop.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "==============================================="
echo "  Stopping HR AI System"
echo "==============================================="

# ── 1. Stop Streamlit ──────────────────────────────────────────────────────────
if pgrep -f "streamlit" > /dev/null; then
    echo "Stopping Streamlit..."
    pkill -f "streamlit"
    sleep 2
else
    echo "[OK] Streamlit not running"
fi

# ── 2. Stop PostgreSQL ───────────────────────────────────────────────────────
if command -v docker &> /dev/null; then
    if docker ps --format "{{.Names}}" | grep -q "hr_postgres"; then
        echo "Stopping PostgreSQL container..."
        docker stop hr_postgres
    else
        echo "[OK] PostgreSQL not running"
    fi
fi

echo "==============================================="
echo "  System stopped"
echo "==============================================="
