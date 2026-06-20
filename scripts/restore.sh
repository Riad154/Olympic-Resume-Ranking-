#!/usr/bin/env bash
# Olympic Industries — Restore HR AI System from backup (Linux/macOS)
# Run from project root: bash scripts/restore.sh backups/backup_20260115_143022.tar.gz

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

BACKUP_PATH="${1:-}"
if [ -z "$BACKUP_PATH" ] || [ ! -f "$BACKUP_PATH" ]; then
    echo "Usage: bash scripts/restore.sh <backup-file.tar.gz>"
    exit 1
fi

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESTORE_DIR="backups/restore_$TIMESTAMP"
mkdir -p "$RESTORE_DIR"

echo "==============================================="
echo "  HR AI System Restore"
echo "  Source: $BACKUP_PATH"
echo "==============================================="

# ── 1. Extract ──────────────────────────────────────────────────────────────────
echo "[1/4] Extracting backup..."
tar -xzf "$BACKUP_PATH" -C "backups/"
EXTRACTED=$(tar -tzf "$BACKUP_PATH" | head -1 | cut -d'/' -f1)
mv "backups/$EXTRACTED" "$RESTORE_DIR/"
echo "[OK] Extracted"

# ── 2. Restore database ─────────────────────────────────────────────────────────
echo "[2/4] Restoring PostgreSQL database..."
PG_USER=$(grep "^PG_USER=" .env | cut -d'=' -f2 | tr -d '"')
PG_DBNAME=$(grep "^PG_DBNAME=" .env | cut -d'=' -f2 | tr -d '"')
PG_PASSWORD=$(grep "^PG_PASSWORD=" .env | cut -d'=' -f2)
[ -z "$PG_DBNAME" ] && PG_DBNAME="resume_ranking"
[ -z "$PG_USER" ] && PG_USER="postgres"

export PGPASSWORD="$PG_PASSWORD"
docker exec hr_postgres psql -U "$PG_USER" -d postgres -c "DROP DATABASE IF EXISTS $PG_DBNAME;" > /dev/null 2>&1 || true
docker exec hr_postgres psql -U "$PG_USER" -d postgres -c "CREATE DATABASE $PG_DBNAME;" > /dev/null 2>&1 || true
cat "$RESTORE_DIR/database.sql" | docker exec -i hr_postgres psql -U "$PG_USER" -d "$PG_DBNAME"
unset PGPASSWORD

echo "[OK] Database restored"

# ── 3. Restore files ────────────────────────────────────────────────────────────
echo "[3/4] Restoring files..."
if [ -d "$RESTORE_DIR/downloaded_resumes" ]; then
    rm -rf downloaded_resumes 2>/dev/null || true
    mv "$RESTORE_DIR/downloaded_resumes" .
    echo "[OK] Resumes restored"
fi
if [ -d "$RESTORE_DIR/profiles_txt" ]; then
    rm -rf profiles_txt 2>/dev/null || true
    mv "$RESTORE_DIR/profiles_txt" .
    echo "[OK] Profiles restored"
fi

# ── 4. Restore config ─────────────────────────────────────────────────────────
echo "[4/4] Restoring configuration..."
if [ -f "$RESTORE_DIR/.env" ]; then
    read -p "Overwrite existing .env with backup version? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cp "$RESTORE_DIR/.env" .env
        echo "[OK] Config restored"
    else
        echo "[SKIP] Keeping current .env"
    fi
fi

# ── Cleanup ─────────────────────────────────────────────────────────────────────
rm -rf "$RESTORE_DIR"

echo ""
echo "==============================================="
echo "  Restore Complete!"
echo "==============================================="
echo "Run: bash scripts/start.sh"
echo ""
