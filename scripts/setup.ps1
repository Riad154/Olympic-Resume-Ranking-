#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Setup script for HR AI Resume Ranking System (Windows)
.DESCRIPTION
    One-time setup: creates venv, installs deps, starts PostgreSQL via Docker,
    and verifies the environment.
.NOTES
    Run from project root: .\scripts\setup.ps1
#>

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  HR AI System — Windows Setup" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan

# ── 1. Check Python ───────────────────────────────────────────────────────────
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Error "Python not found. Install Python 3.10+ from https://python.org"
}
$ver = python --version 2>&1
Write-Host "[OK] $ver" -ForegroundColor Green

# ── 2. Create virtual environment ─────────────────────────────────────────────
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}
else {
    Write-Host "[OK] venv already exists" -ForegroundColor Green
}

# ── 3. Activate + install deps ────────────────────────────────────────────────
Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
& .\venv\Scripts\python.exe -m pip install --upgrade pip
& .\venv\Scripts\pip.exe install -r requirements.txt

# ── 4. Playwright (optional — for BDJobs downloader) ─────────────────────────
$installPlaywright = Read-Host "Install Playwright for BDJobs downloader? (y/n)"
if ($installPlaywright -eq 'y') {
    & .\venv\Scripts\playwright.exe install chromium
}

# ── 5. Create .env if missing ─────────────────────────────────────────────────
if (-not (Test-Path ".env")) {
    Write-Host "Creating .env from template..." -ForegroundColor Yellow
    Copy-Item .env.example .env
    Write-Host "[ACTION REQUIRED] Edit .env and set PG_PASSWORD and other secrets" -ForegroundColor Red
}
else {
    Write-Host "[OK] .env already exists" -ForegroundColor Green
}

# ── 6. Start PostgreSQL via Docker ────────────────────────────────────────────
$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker) {
    Write-Warning "Docker not found. Install Docker Desktop: https://docker.com/products/docker-desktop"
}
else {
    Write-Host "Starting PostgreSQL container..." -ForegroundColor Yellow
    docker compose up -d postgres
    Write-Host "Waiting for PostgreSQL to be ready..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
    docker exec hr_postgres pg_isready -U postgres 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] PostgreSQL is ready" -ForegroundColor Green
    }
    else {
        Write-Warning "PostgreSQL may still be starting. Wait a few more seconds."
    }
}

# ── 7. Check Ollama ────────────────────────────────────────────────────────────
$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    Write-Warning "Ollama not found. Install from https://ollama.com"
    Write-Warning "After install, run: ollama pull qwen3:8b-q4_K_M"
}
else {
    Write-Host "[OK] Ollama found" -ForegroundColor Green
    Write-Host "Pulling model (this may take several minutes)..." -ForegroundColor Yellow
    ollama pull qwen3:8b-q4_K_M
}

# ── 8. Set Ollama env vars for parallelism ─────────────────────────────────────
Write-Host "Setting Ollama parallelism environment variables..." -ForegroundColor Yellow
[Environment]::SetEnvironmentVariable("OLLAMA_NUM_PARALLEL", "3", "User")
[Environment]::SetEnvironmentVariable("OLLAMA_MAX_LOADED_MODELS", "1", "User")
Write-Host "[OK] Set OLLAMA_NUM_PARALLEL=3, OLLAMA_MAX_LOADED_MODELS=1" -ForegroundColor Green
Write-Host "[IMPORTANT] Quit and relaunch Ollama from the system tray for changes to take effect." -ForegroundColor Red

# ── 9. Verify ────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  Setup Complete!" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Edit .env with your database password" -ForegroundColor Yellow
Write-Host "  2. Restart Ollama (quit tray icon + relaunch)" -ForegroundColor Yellow
Write-Host "  3. Run: .\scripts\start.ps1" -ForegroundColor Yellow
Write-Host ""
