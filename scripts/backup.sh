#!/usr/bin/env bash
# Olympic Industries — Backup HR AI System (Linux/macOS)
# Run from project root: bash scripts/backup.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="backups/backup_$TIMESTAMP"
mkdir -p "$BACKUP_DIR"

echo "==============================================="
echo "  HR AI System Backup — $TIMESTAMP"
echo "==============================================="

# ── 1. Backup PostgreSQL ───────────────────────────────────────────────────────
echo "[1/5] Backing up PostgreSQL database..."
PG_USER=$(grep "^PG_USER=" .env | cut -d'=' -f2 | tr -d '"')
PG_DBNAME=$(grep "^PG_DBNAME=" .env | cut -d'=' -f2 | tr -d '"')
PG_PASSWORD=$(grep "^PG_PASSWORD=" .env | cut -d'=' -f2)

[ -z "$PG_USER" ] && PG_USER="postgres"
[ -z "$PG_DBNAME" ] && PG_DBNAME="resume_ranking"

export PGPASSWORD="$PG_PASSWORD"
docker exec hr_postgres pg_dump -U "$PG_USER" -d "$PG_DBNAME" --no-owner --no-acl > "$BACKUP_DIR/database.sql"
unset PGPASSWORD

echo "[OK] Database dumped"

# ── 2. Backup downloaded resumes ────────────────────────────────────────────────
echo "[2/5] Backing up downloaded resumes..."
if [ -d "downloaded_resumes" ]; then
    cp -r downloaded_resumes "$BACKUP_DIR/"
    echo "[OK] Resumes copied"
fi

# ── 3. Backup profiles_txt ─────────────────────────────────────────────────────
echo "[3/5] Backing up profiles_txt..."
if [ -d "profiles_txt" ]; then
    cp -r profiles_txt "$BACKUP_DIR/"
    echo "[OK] Profiles copied"
fi

# ── 4. Backup config ───────────────────────────────────────────────────────────
echo "[4/5] Backing up configuration..."
cp .env "$BACKUP_DIR/" 2>/dev/null || true
cp .env.example "$BACKUP_DIR/" 2>/dev/null || true
echo "[OK] Config copied"

# ── 5. Create manifest ─────────────────────────────────────────────────────────
echo "[5/5] Creating manifest..."
cat > "$BACKUP_DIR/MANIFEST.txt" <<EOF
Backup Manifest
================
Created: $(date "+%Y-%m-%d %H:%M:%S")
Source: $PROJECT_ROOT
Contents:
  - database.sql        PostgreSQL dump
  - downloaded_resumes/ Candidate resumes and metadata
  - profiles_txt/       Extracted text profiles
  - .env                Environment configuration
Restore: See MIGRATION_GUIDE.md
EOF

# ── 6. Create tar.gz ───────────────────────────────────────────────────────────
ARCHIVE="backups/backup_$TIMESTAMP.tar.gz"
tar -czf "$ARCHIVE" -C "backups" "backup_$TIMESTAMP"
rm -rf "$BACKUP_DIR"

SIZE=$(du -h "$ARCHIVE" | cut -f1)
echo ""
echo "==============================================="
echo "  Backup Complete!"
echo "==============================================="
echo "Location: $ARCHIVE"
echo "Size:     $SIZE"
echo ""
