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
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument '-WindowStyle Hidden -Command "cd F:\Projects\resume_ranking; python -m streamlit run resume_app/Home.py --server.address 0.0.0.0 --server.port 8502"'
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -LogonType Interactive -RunLevel Highest

try {
    # Remove existing task if present
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    
    # Register new task
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Force
    
    Write-Host "Auto-start task created successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Task Name: $TaskName" -ForegroundColor White
    Write-Host "Trigger: When user logs on" -ForegroundColor White
    Write-Host "Command: Streamlit on port 8502" -ForegroundColor White
    Write-Host ""
    Write-Host "To test: Restart your PC and the app will auto-start." -ForegroundColor Yellow
    Write-Host "To manage: Open Task Scheduler and look for '$TaskName'" -ForegroundColor Gray
} catch {
    Write-Host "ERROR creating task: $_" -ForegroundColor Red
    exit 1
}
