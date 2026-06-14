# Resume Ranking System — Auto-Start Setup (Task Scheduler)
# Run as Administrator in PowerShell

$ErrorActionPreference = "Stop"
Write-Host "=== Setting up Auto-Start for HR Ranking System ===" -ForegroundColor Cyan
Write-Host ""

# Check admin rights
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: Must run as Administrator. Right-click PowerShell -> Run as Administrator." -ForegroundColor Red
    exit 1
}

$TaskName = "ResumeRankingHRApp"
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument '-ExecutionPolicy Bypass -WindowStyle Hidden -File "F:\Projects\resume_ranking\resume_app\start_app.ps1"'
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1)
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -LogonType Interactive -RunLevel Highest

try {
    # Remove existing task if present
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    
    # Register new task
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Force
    
    Write-Host "Auto-start task created successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Task Name : $TaskName" -ForegroundColor White
    Write-Host "Trigger   : When user logs on" -ForegroundColor White
    Write-Host "Behavior  : Watchdog auto-restarts Streamlit if it crashes" -ForegroundColor White
    Write-Host "Port      : 8502" -ForegroundColor White
    Write-Host ""
    Write-Host "Manual start : Double-click start_now.ps1" -ForegroundColor Yellow
    Write-Host "Manual stop  : Double-click stop_app.ps1" -ForegroundColor Yellow
    Write-Host "Logs         : F:\Projects\resume_ranking\_service_logs\" -ForegroundColor Gray
    Write-Host ""
    Write-Host "To test auto-start: Restart your PC." -ForegroundColor Yellow
    Write-Host "To manage task     : Open Task Scheduler -> '$TaskName'" -ForegroundColor Gray
} catch {
    Write-Host "ERROR creating task: $_" -ForegroundColor Red
    exit 1
}
