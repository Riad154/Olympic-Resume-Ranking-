<#
.SYNOPSIS
    Start the HR AI Resume Ranking System (Windows)
.DESCRIPTION
    Starts PostgreSQL (if Docker), verifies Ollama, then launches Streamlit.
.NOTES
    Run from project root: .\scripts\start.ps1
#>

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  Starting HR AI System" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan

# ── 1. Start PostgreSQL ────────────────────────────────────────────────────────
$docker = Get-Command docker -ErrorAction SilentlyContinue
if ($docker) {
    $pgRunning = docker ps --format "{{.Names}}" | Select-String "hr_postgres"
    if (-not $pgRunning) {
        Write-Host "Starting PostgreSQL container..." -ForegroundColor Yellow
        docker compose up -d postgres
        Start-Sleep -Seconds 3
    }
    else {
        Write-Host "[OK] PostgreSQL already running" -ForegroundColor Green
    }
}
else {
    Write-Warning "Docker not found — assuming PostgreSQL is running elsewhere"
}

# ── 2. Verify Ollama ───────────────────────────────────────────────────────────
try {
    Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 3 | Out-Null
    Write-Host "[OK] Ollama is running" -ForegroundColor Green
}
catch {
    Write-Warning "Ollama not responding on localhost:11434"
    Write-Warning "Start Ollama from the system tray and try again."
}

# ── 3. Start Streamlit ────────────────────────────────────────────────────────
Write-Host "Starting Streamlit app..." -ForegroundColor Green
& .\venv\Scripts\streamlit.exe run resume_app\Home.py
