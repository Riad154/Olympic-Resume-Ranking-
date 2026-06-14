# Resume Ranking System — Manual Start (with auto-restart)
# Just double-click this file, or run in PowerShell.

$ErrorActionPreference = "Continue"
$scriptPath = $PSScriptRoot
if (-not $scriptPath) { $scriptPath = (Get-Location).Path }

$watchdog = Join-Path $scriptPath "resume_app\start_app.ps1"

Write-Host "=== Starting HR Ranking System ===" -ForegroundColor Cyan
Write-Host "Watchdog script: $watchdog" -ForegroundColor Gray
Write-Host ""

if (-not (Test-Path $watchdog)) {
    Write-Host "ERROR: Watchdog script not found at $watchdog" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Start the watchdog in a new hidden window
Start-Process powershell.exe -ArgumentList "-ExecutionPolicy Bypass -File `"$watchdog`"" -WindowStyle Hidden

Write-Host "App started in background." -ForegroundColor Green
Write-Host "Access it at: http://$(hostname):8502  (or http://192.168.x.x:8502 from other devices)" -ForegroundColor White
Write-Host ""
Write-Host "To stop: Open Task Manager and end 'Python' processes, or run Stop-App.ps1" -ForegroundColor Yellow
Write-Host "Logs: F:\Projects\resume_ranking\_service_logs\streamlit_watchdog.log" -ForegroundColor Gray

Start-Sleep -Seconds 2
