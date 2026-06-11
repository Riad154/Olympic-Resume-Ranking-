# Resume Ranking System — Local Windows Deployment Setup Script
# Run as Administrator in PowerShell

param(
    [string]$PgPassword = "resume_ranking_2024",
    [string]$DbName = "resume_ranking"
)

$ErrorActionPreference = "Stop"
Write-Host "=== Resume Ranking System — Local Setup ===" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Check Python ─────────────────────────────────────────────────────
Write-Host "[1/6] Checking Python..." -ForegroundColor Yellow
try {
    $pyVersion = python --version 2>$null
    if (-not $?) {
        Write-Host "ERROR: Python not found in PATH. Install Python 3.11+ first." -ForegroundColor Red
        exit 1
    }
    Write-Host "  Found: $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python not found. Install from https://python.org" -ForegroundColor Red
    exit 1
}

# ── Step 2: Check PostgreSQL ─────────────────────────────────────────────────
Write-Host "[2/6] Checking PostgreSQL..." -ForegroundColor Yellow
try {
    $pgVersion = psql --version 2>$null
    if (-not $?) {
        Write-Host "  PostgreSQL CLI not found." -ForegroundColor Red
        Write-Host ""
        Write-Host "  Please download and install PostgreSQL 16:" -ForegroundColor Cyan
        Write-Host "  https://www.enterprisedb.com/downloads/postgres-postgresql-downloads" -ForegroundColor White
        Write-Host ""
        Write-Host "  During installation:" -ForegroundColor Cyan
        Write-Host "  - Remember the password you set for 'postgres' user" -ForegroundColor White
        Write-Host "  - Keep port 5432" -ForegroundColor White
        Write-Host "  - Install pgAdmin4 (recommended)" -ForegroundColor White
        Write-Host ""
        Write-Host "  After installation, re-run this script." -ForegroundColor Yellow
        exit 1
    }
    Write-Host "  Found: $pgVersion" -ForegroundColor Green
} catch {
    Write-Host "  PostgreSQL not found. Please install it first (see instructions above)." -ForegroundColor Red
    exit 1
}

# ── Step 3: Create/update .env file ──────────────────────────────────────────
Write-Host "[3/6] Creating .env file..." -ForegroundColor Yellow
$envPath = "F:\Projects\resume_ranking\.env"
$envContent = @"
# ──────────────────────────────────────────────────────────────────────────────
# Resume Ranking System — LOCAL DEPLOYMENT
# For self-hosted HR system on Windows PC with GPU
# ──────────────────────────────────────────────────────────────────────────────

# PostgreSQL (local instance)
PG_HOST=localhost
PG_PORT=5432
PG_DBNAME=$DbName
PG_USER=postgres
PG_PASSWORD=$PgPassword

# Ollama LLM server (on this same Windows PC with RTX 3060 Ti)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen3:8b-q4_K_M

# Paths (absolute Windows paths for reliability)
RESUMES_BASE=F:/Projects/resume_ranking/downloaded_resumes
RANKER_PATH=F:/Projects/resume_ranking/ranker.py

# Use current Python interpreter
VENV_PYTHON=python

# Concurrency (adjust based on GPU VRAM)
RANKER_WORKERS=5

# Ollama performance tuning
OLLAMA_NUM_PARALLEL=5
OLLAMA_MAX_LOADED_MODELS=1
OLLAMA_NUM_CTX=8192
OLLAMA_NUM_PREDICT=2048
"@

Set-Content -Path $envPath -Value $envContent -Encoding UTF8
Write-Host "  Created: $envPath" -ForegroundColor Green
Write-Host "  DB Password: $PgPassword" -ForegroundColor Gray

# ── Step 4: Create database ──────────────────────────────────────────────────
Write-Host "[4/6] Creating database '$DbName'..." -ForegroundColor Yellow
try {
    $dbExists = psql -U postgres -c "SELECT 1 FROM pg_database WHERE datname='$DbName';" -t -A 2>$null
    if ($dbExists -eq "1") {
        Write-Host "  Database already exists. Skipping creation." -ForegroundColor Green
    } else {
        psql -U postgres -c "CREATE DATABASE $DbName;" 2>$null
        Write-Host "  Database created successfully." -ForegroundColor Green
    }
} catch {
    Write-Host "  Note: Could not auto-create database. You may need to:" -ForegroundColor Yellow
    Write-Host "  1. Open pgAdmin" -ForegroundColor White
    Write-Host "  2. Connect to localhost:5432 as postgres" -ForegroundColor White
    Write-Host "  3. Run: CREATE DATABASE $DbName;" -ForegroundColor White
}

# ── Step 5: Install dependencies ─────────────────────────────────────────────
Write-Host "[5/6] Installing Python dependencies..." -ForegroundColor Yellow
Set-Location "F:\Projects\resume_ranking"
try {
    python -m pip install -q -r requirements.txt 2>$null
    Write-Host "  Dependencies installed." -ForegroundColor Green
} catch {
    Write-Host "  Note: Some dependencies may need manual install." -ForegroundColor Yellow
}

# ── Step 6: Run schema migration ────────────────────────────────────────────
Write-Host "[6/6] Running database schema migration..." -ForegroundColor Yellow
Set-Location "F:\Projects\resume_ranking"
try {
    $env:PG_HOST = "localhost"
    $env:PG_PORT = "5432"
    $env:PG_DBNAME = $DbName
    $env:PG_USER = "postgres"
    $env:PG_PASSWORD = $PgPassword

    python -c "from resume_app.db import ensure_database; ensure_database()" 2>$null
    if ($?) {
        Write-Host "  Schema migration completed." -ForegroundColor Green
    } else {
        throw "Migration failed"
    }
} catch {
    Write-Host "  Schema migration may have failed. Common fixes:" -ForegroundColor Yellow
    Write-Host "  - Ensure PostgreSQL is running: services.msc -> PostgreSQL -> Start" -ForegroundColor White
    Write-Host "  - Verify password in .env matches what you set during install" -ForegroundColor White
    Write-Host "  - Check pgAdmin to see if tables were created" -ForegroundColor White
}

Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Ensure Ollama is running (check system tray)" -ForegroundColor White
Write-Host "  2. Start the app: cd F:\Projects\resume_ranking\resume_app; streamlit run Home.py --server.address 0.0.0.0 --server.port 8501" -ForegroundColor White
Write-Host "  3. On this PC:    http://localhost:8501" -ForegroundColor White
Write-Host "  4. On network:    http://YOUR_PC_IP:8501" -ForegroundColor White
Write-Host "  5. Via VPN:       http://YOUR_PC_IP:8501 (same, when connected to VPN)" -ForegroundColor White
Write-Host ""
Write-Host "To find your PC's IP: run 'ipconfig' and look for IPv4 Address" -ForegroundColor Gray
