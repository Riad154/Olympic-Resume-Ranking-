<#
.SYNOPSIS
    Restore the HR AI Resume Ranking System from backup (Windows)
.DESCRIPTION
    Restores database, resumes, and config from a backup ZIP.
    WARNING: This OVERWRITES existing database data.
.PARAMETER BackupPath
    Path to the backup ZIP file
.NOTES
    Run from project root: .\scripts\restore.ps1 -BackupPath "backups\backup_20260115_143022.zip"
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$BackupPath
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Test-Path $BackupPath)) {
    Write-Error "Backup file not found: $BackupPath"
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$restoreDir = "backups\restore_$timestamp"
New-Item -ItemType Directory -Path $restoreDir -Force | Out-Null

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  HR AI System Restore" -ForegroundColor Cyan
Write-Host "  Source: $BackupPath" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan

# ── 1. Extract ZIP ───────────────────────────────────────────────────────────────
Write-Host "[1/4] Extracting backup..." -ForegroundColor Yellow
Expand-Archive -Path $BackupPath -DestinationPath $restoreDir -Force
Write-Host "[OK] Extracted" -ForegroundColor Green

# ── 2. Restore database ────────────────────────────────────────────────────────
Write-Host "[2/4] Restoring PostgreSQL database..." -ForegroundColor Yellow
$pgPassword = (Get-Content .env | Select-String "^PG_PASSWORD=").ToString().Split("=")[1]
$pgUser = (Get-Content .env | Select-String "^PG_USER=").ToString().Split("=")[1] -replace "`"", ''
$pgDb = (Get-Content .env | Select-String "^PG_DBNAME=").ToString().Split("=")[1] -replace "`"", ''
if (-not $pgDb) { $pgDb = "resume_ranking" }
if (-not $pgUser) { $pgUser = "postgres" }

$env:PGPASSWORD = $pgPassword

# Drop and recreate database
docker exec hr_postgres psql -U $pgUser -d postgres -c "DROP DATABASE IF EXISTS $pgDb;" 2>$null
docker exec hr_postgres psql -U $pgUser -d postgres -c "CREATE DATABASE $pgDb;" 2>$null

# Restore from dump
Get-Content "$restoreDir\database.sql" | docker exec -i hr_postgres psql -U $pgUser -d $pgDb
Remove-Item Env:\PGPASSWORD

Write-Host "[OK] Database restored" -ForegroundColor Green

# ── 3. Restore files ────────────────────────────────────────────────────────────
Write-Host "[3/4] Restoring files..." -ForegroundColor Yellow
if (Test-Path "$restoreDir\downloaded_resumes") {
    if (Test-Path "downloaded_resumes") {
        Remove-Item -Recurse -Force "downloaded_resumes"
    }
    Move-Item "$restoreDir\downloaded_resumes" "downloaded_resumes"
    Write-Host "[OK] Resumes restored" -ForegroundColor Green
}
if (Test-Path "$restoreDir\profiles_txt") {
    if (Test-Path "profiles_txt") {
        Remove-Item -Recurse -Force "profiles_txt"
    }
    Move-Item "$restoreDir\profiles_txt" "profiles_txt"
    Write-Host "[OK] Profiles restored" -ForegroundColor Green
}

# ── 4. Restore config (ask first) ─────────────────────────────────────────────
Write-Host "[4/4] Restoring configuration..." -ForegroundColor Yellow
if (Test-Path "$restoreDir\.env") {
    $confirm = Read-Host "Overwrite existing .env with backup version? (y/n)"
    if ($confirm -eq 'y') {
        Copy-Item "$restoreDir\.env" ".env" -Force
        Write-Host "[OK] Config restored" -ForegroundColor Green
    }
    else {
        Write-Host "[SKIP] Keeping current .env" -ForegroundColor Yellow
    }
}

# ── Cleanup ─────────────────────────────────────────────────────────────────────
Remove-Item -Recurse -Force $restoreDir

Write-Host ""
Write-Host "===============================================" -ForegroundColor Green
Write-Host "  Restore Complete!" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Green
Write-Host "Run .\scripts\start.ps1 to verify" -ForegroundColor Yellow
Write-Host ""
