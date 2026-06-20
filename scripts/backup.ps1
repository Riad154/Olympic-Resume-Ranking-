<#
.SYNOPSIS
    Backup the HR AI Resume Ranking System (Windows)
.DESCRIPTION
    Backs up database, downloaded resumes, profiles, and creates a timestamped ZIP.
.NOTES
    Run from project root: .\scripts\backup.ps1
#>

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = "backups\backup_$timestamp"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  HR AI System Backup — $timestamp" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan

# ── 1. Backup PostgreSQL ────────────────────────────────────────────────────────
Write-Host "[1/5] Backing up PostgreSQL database..." -ForegroundColor Yellow
$pgPassword = (Get-Content .env | Select-String "^PG_PASSWORD=").ToString().Split("=")[1]
$pgUser = (Get-Content .env | Select-String "^PG_USER=").ToString().Split("=")[1] -replace "`"", ''
$pgDb = (Get-Content .env | Select-String "^PG_DBNAME=").ToString().Split("=")[1] -replace "`"", ''

if (-not $pgDb) { $pgDb = "resume_ranking" }
if (-not $pgUser) { $pgUser = "postgres" }

$env:PGPASSWORD = $pgPassword
docker exec hr_postgres pg_dump -U $pgUser -d $pgDb --no-owner --no-acl > "$backupDir\database.sql"
Remove-Item Env:\PGPASSWORD

if (Test-Path "$backupDir\database.sql") {
    Write-Host "[OK] Database dumped" -ForegroundColor Green
}
else {
    Write-Warning "Database backup may have failed"
}

# ── 2. Backup downloaded resumes ────────────────────────────────────────────────
Write-Host "[2/5] Backing up downloaded resumes..." -ForegroundColor Yellow
if (Test-Path "downloaded_resumes") {
    Copy-Item -Recurse -Force "downloaded_resumes" "$backupDir\downloaded_resumes"
    Write-Host "[OK] Resumes copied" -ForegroundColor Green
}

# ── 3. Backup profiles_txt ────────────────────────────────────────────────────
Write-Host "[3/5] Backing up profiles_txt..." -ForegroundColor Yellow
if (Test-Path "profiles_txt") {
    Copy-Item -Recurse -Force "profiles_txt" "$backupDir\profiles_txt"
    Write-Host "[OK] Profiles copied" -ForegroundColor Green
}

# ── 4. Backup config ────────────────────────────────────────────────────────────
Write-Host "[4/5] Backing up configuration..." -ForegroundColor Yellow
Copy-Item ".env" "$backupDir\.env" -ErrorAction SilentlyContinue
Copy-Item ".env.example" "$backupDir\.env.example" -ErrorAction SilentlyContinue
Write-Host "[OK] Config copied" -ForegroundColor Green

# ── 5. Create manifest ──────────────────────────────────────────────────────────
Write-Host "[5/5] Creating manifest..." -ForegroundColor Yellow
$manifest = @"
Backup Manifest
================
Created: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Source: $ProjectRoot
Contents:
  - database.sql        PostgreSQL dump
  - downloaded_resumes/ Candidate resumes and metadata
  - profiles_txt/       Extracted text profiles
  - .env                Environment configuration
Restore: See MIGRATION_GUIDE.md
"@
$manifest | Out-File -FilePath "$backupDir\MANIFEST.txt" -Encoding UTF8

# ── 6. Create ZIP ───────────────────────────────────────────────────────────────
$zipPath = "backups\backup_$timestamp.zip"
Compress-Archive -Path "$backupDir\*" -DestinationPath $zipPath -Force
Remove-Item -Recurse -Force $backupDir

Write-Host ""
Write-Host "===============================================" -ForegroundColor Green
Write-Host "  Backup Complete!" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Green
Write-Host "Location: $zipPath" -ForegroundColor White
Write-Host "Size:     $([math]::Round((Get-Item $zipPath).Length / 1MB, 2)) MB" -ForegroundColor White
Write-Host ""
