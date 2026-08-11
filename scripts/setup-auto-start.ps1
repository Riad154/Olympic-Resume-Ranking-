<#
.SYNOPSIS
    One-time setup: register the HR AI System to auto-start on Windows logon.
.DESCRIPTION
    Creates a Windows Scheduled Task that runs auto-start.ps1 every time
    the user logs in. Also opens Windows Firewall port 8501.
    Run as Administrator.
.NOTES
    Right-click PowerShell → "Run as Administrator", then run:
        .\scripts\setup-auto-start.ps1
#>

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  HR AI System — Auto-Start Setup" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

# ── Check elevation ──────────────────────────────────────────────────────────────
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
if (-not $isAdmin) {
    Write-Warning "This script must be run as Administrator to create Scheduled Tasks and Firewall rules."
    Write-Host "Right-click PowerShell → 'Run as Administrator' and try again." -ForegroundColor Yellow
    exit 1
}

# ── Create Scheduled Task ──────────────────────────────────────────────────────
$TaskName = "HR-AI-AutoStart"
$TaskPath = "\Olympic Industries\"
$PsExe = "${env:SystemRoot}\System32\WindowsPowerShell\v1.0\powershell.exe"
$ScriptPath = Join-Path $ProjectRoot "scripts\auto-start.ps1"
$Argument = "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ScriptPath`""

Write-Host "Creating Scheduled Task: $TaskName ..." -ForegroundColor Yellow

# Remove old task if exists
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# Create task action
$action = New-ScheduledTaskAction -Execute $PsExe -Argument $Argument -WorkingDirectory $ProjectRoot

# Create trigger (at logon of current user)
$trigger = New-ScheduledTaskTrigger -AtLogon

# Create settings
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable:$false `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

# Create principal (current user)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest

# Register the task
Register-ScheduledTask `
    -TaskName $TaskName `
    -TaskPath $TaskPath `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Force | Out-Null

Write-Host "[OK] Scheduled Task created successfully." -ForegroundColor Green

# ── Open Windows Firewall ──────────────────────────────────────────────────────
Write-Host "Opening Windows Firewall port 8501 ..." -ForegroundColor Yellow

$ruleName = "HR-AI-Streamlit-8501"
# Remove existing rule if present
Remove-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue

New-NetFirewallRule `
    -DisplayName $ruleName `
    -Direction Inbound `
    -LocalPort 8501 `
    -Protocol TCP `
    -Action Allow `
    -Profile Domain,Private,Public `
    -Description "Allow inbound connections to HR AI Resume Ranking System (Streamlit)" | Out-Null

Write-Host "[OK] Firewall rule added for port 8501." -ForegroundColor Green

# ── Also open PostgreSQL port if needed ────────────────────────────────────────
$pgRuleName = "HR-AI-PostgreSQL-5432"
Remove-NetFirewallRule -DisplayName $pgRuleName -ErrorAction SilentlyContinue
New-NetFirewallRule `
    -DisplayName $pgRuleName `
    -Direction Inbound `
    -LocalPort 5432 `
    -Protocol TCP `
    -Action Allow `
    -Profile Domain,Private `
    -Description "Allow inbound connections to HR AI PostgreSQL" | Out-Null

Write-Host "[OK] Firewall rule added for port 5432 (PostgreSQL)." -ForegroundColor Green

# ── Summary ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "===============================================" -ForegroundColor Green
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Green
Write-Host ""
Write-Host "The system will now auto-start every time you log in."
Write-Host "You can verify the task in: Task Scheduler → Task Scheduler Library → Olympic Industries"
Write-Host ""
Write-Host "Access the app from this PC:    http://localhost:8501"
Write-Host "Access from other PCs/devices:  http://$(hostname):8501"
Write-Host ""
Write-Host "To test now, run: .\scripts\auto-start.ps1"
Write-Host ""
