<#
.SYNOPSIS
    Auto-start HR AI System on Windows boot / user logon.
.DESCRIPTION
    Starts Docker, PostgreSQL, Ollama, and Streamlit so the system is
    accessible on the network immediately after the PC powers on.
    Run once via Task Scheduler (setup-auto-start.ps1) or manually.
.NOTES
    This script writes logs to logs/auto-start.log
#>

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

# ── Logging ────────────────────────────────────────────────────────────────────
$LogDir = Join-Path $ProjectRoot "logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
$LogFile = Join-Path $LogDir "auto-start.log"
function Write-Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts  $msg" | Tee-Object -FilePath $LogFile -Append | Write-Host
}

Write-Log "=================================="
Write-Log "HR AI System Auto-Start Initiated"
Write-Log "=================================="

# ── 1. Start Docker Desktop ────────────────────────────────────────────────────
Write-Log "[Step 1/4] Checking Docker..."
$dockerDesktop = Get-Process "Docker Desktop" -ErrorAction SilentlyContinue
if (-not $dockerDesktop) {
    $dockerExe = "${env:ProgramFiles}\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dockerExe) {
        Write-Log "Starting Docker Desktop..."
        Start-Process $dockerExe
        # Wait for Docker to be ready (up to 60 seconds)
        $maxWait = 60
        $elapsed = 0
        while ($elapsed -lt $maxWait) {
            Start-Sleep -Seconds 5
            $elapsed += 5
            try {
                docker ps >$null 2>&1
                if ($LASTEXITCODE -eq 0) {
                    Write-Log "Docker is ready."
                    break
                }
            } catch {}
        }
        if ($elapsed -ge $maxWait) {
            Write-Log "WARNING: Docker did not become ready within 60s. Continuing anyway..."
        }
    } else {
        Write-Log "WARNING: Docker Desktop not found at expected path."
    }
} else {
    Write-Log "Docker Desktop already running."
}

# ── 2. Start PostgreSQL Container ──────────────────────────────────────────────
Write-Log "[Step 2/4] Checking PostgreSQL container..."
try {
    $pgRunning = docker ps --format "{{.Names}}" | Select-String "hr_postgres"
    if (-not $pgRunning) {
        Write-Log "Starting PostgreSQL container..."
        docker compose up -d postgres
        Start-Sleep -Seconds 5
        Write-Log "PostgreSQL started."
    } else {
        Write-Log "PostgreSQL already running."
    }
} catch {
    Write-Log "ERROR starting PostgreSQL: $_"
}

# ── 3. Verify Ollama ───────────────────────────────────────────────────────────
Write-Log "[Step 3/4] Checking Ollama..."
try {
    Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 5 | Out-Null
    Write-Log "Ollama is running."
} catch {
    Write-Log "WARNING: Ollama not responding on localhost:11434."
    Write-Log "Please ensure Ollama is set to start on boot (system tray > Settings > Start Ollama on boot)."
}

# ── 4. Start Streamlit ─────────────────────────────────────────────────────────
Write-Log "[Step 4/4] Checking Streamlit..."
$streamlitProc = Get-Process "streamlit" -ErrorAction SilentlyContinue
if (-not $streamlitProc) {
    Write-Log "Starting Streamlit..."
    $streamlitScript = Join-Path $ProjectRoot "venv\Scripts\streamlit.exe"

    if (Test-Path $streamlitScript) {
        # Start Streamlit in a hidden window so it runs in background
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $streamlitScript
        $psi.Arguments = "run resume_app\Home.py"
        $psi.WorkingDirectory = $ProjectRoot
        $psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
        $psi.UseShellExecute = $false
        [System.Diagnostics.Process]::Start($psi) | Out-Null

        Start-Sleep -Seconds 3
        Write-Log "Streamlit started on http://0.0.0.0:8501"
    } else {
        Write-Log "ERROR: streamlit.exe not found in venv."
    }
} else {
    Write-Log "Streamlit already running."
}

# ── 5. Summary ─────────────────────────────────────────────────────────────────
Write-Log "----------------------------------"
Write-Log "Auto-start complete."
Write-Log "Access the app at: http://$(hostname):8501"
Write-Log "Log file: $LogFile"
Write-Log "----------------------------------"

# Keep window open briefly so user can see results
Start-Sleep -Seconds 5
