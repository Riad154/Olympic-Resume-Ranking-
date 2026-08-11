<#
.SYNOPSIS
    Check the status of all HR AI System services.
.NOTES
    Run from project root: .\scripts\status.ps1
#>

$ErrorActionPreference = "SilentlyContinue"

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  HR AI System — Status Check" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

# PostgreSQL
$pgRunning = docker ps --format "{{.Names}}" | Select-String "hr_postgres"
if ($pgRunning) {
    Write-Host "[PostgreSQL]   " -NoNewline; Write-Host "RUNNING" -ForegroundColor Green
} else {
    Write-Host "[PostgreSQL]   " -NoNewline; Write-Host "STOPPED" -ForegroundColor Red
}

# Streamlit
$streamlitProc = Get-Process "streamlit" -ErrorAction SilentlyContinue
if ($streamlitProc) {
    Write-Host "[Streamlit]    " -NoNewline; Write-Host "RUNNING (PID $($streamlitProc.Id))" -ForegroundColor Green
} else {
    Write-Host "[Streamlit]    " -NoNewline; Write-Host "STOPPED" -ForegroundColor Red
}

# Ollama
try {
    Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 3 | Out-Null
    Write-Host "[Ollama]       " -NoNewline; Write-Host "RUNNING" -ForegroundColor Green
} catch {
    Write-Host "[Ollama]       " -NoNewline; Write-Host "STOPPED / Not responding" -ForegroundColor Red
}

# Docker
$dockerProc = Get-Process "Docker Desktop" -ErrorAction SilentlyContinue
if ($dockerProc) {
    Write-Host "[Docker]       " -NoNewline; Write-Host "RUNNING" -ForegroundColor Green
} else {
    Write-Host "[Docker]       " -NoNewline; Write-Host "STOPPED" -ForegroundColor Red
}

# Network access
$hostname = hostname
Write-Host ""
Write-Host "Access URLs:" -ForegroundColor Cyan
Write-Host "  This PC:       http://localhost:8501"
Write-Host "  Other devices: http://$hostname`:8501"
Write-Host ""
