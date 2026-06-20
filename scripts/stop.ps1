<#
.SYNOPSIS
    Stop the HR AI Resume Ranking System (Windows)
.DESCRIPTION
    Gracefully stops Streamlit, then stops PostgreSQL container.
.NOTES
    Run from project root: .\scripts\stop.ps1
#>

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "===============================================" -ForegroundColor Yellow
Write-Host "  Stopping HR AI System" -ForegroundColor Yellow
Write-Host "===============================================" -ForegroundColor Yellow

# ── 1. Stop Streamlit ──────────────────────────────────────────────────────────
$streamlitProc = Get-Process -Name "streamlit" -ErrorAction SilentlyContinue
if ($streamlitProc) {
    Write-Host "Stopping Streamlit..." -ForegroundColor Yellow
    $streamlitProc | Stop-Process -Force
    Start-Sleep -Seconds 2
}
else {
    Write-Host "[OK] Streamlit not running" -ForegroundColor Green
}

# ── 2. Stop PostgreSQL ─────────────────────────────────────────────────────────
$docker = Get-Command docker -ErrorAction SilentlyContinue
if ($docker) {
    $pgRunning = docker ps --format "{{.Names}}" | Select-String "hr_postgres"
    if ($pgRunning) {
        Write-Host "Stopping PostgreSQL container..." -ForegroundColor Yellow
        docker stop hr_postgres
    }
    else {
        Write-Host "[OK] PostgreSQL not running" -ForegroundColor Green
    }
}

Write-Host "===============================================" -ForegroundColor Green
Write-Host "  System stopped" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Green
