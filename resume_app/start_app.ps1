# Resume Ranking System — Streamlit Watchdog & Auto-Restarter
# This script keeps Streamlit alive permanently. Run once; it loops forever.

$ErrorActionPreference = "Continue"
$Port        = 8502
$AppPath     = "F:\Projects\resume_ranking\resume_app\Home.py"
$LogDir      = "F:\Projects\resume_ranking\_service_logs"
$LogFile     = "$LogDir\streamlit_watchdog.log"
$Python      = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $Python) { $Python = (Get-Command python3 -ErrorAction SilentlyContinue).Source }
if (-not $Python) { $Python = "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe" }

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

function Write-Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts  $msg" | Tee-Object -FilePath $LogFile -Append | Write-Host
}

function Test-PortOpen($port) {
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient("127.0.0.1", $port)
        $tcp.Close()
        return $true
    } catch { return $false }
}

Write-Log "=== Streamlit Watchdog started ==="
Write-Log "Port: $Port | App: $AppPath | Python: $Python"

while ($true) {
    if (Test-PortOpen $Port) {
        Write-Log "Streamlit already running on port $Port. Waiting..."
        Start-Sleep -Seconds 30
        continue
    }

    Write-Log "Streamlit not detected. Starting..."

    $proc = $null
    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName        = $Python
        $psi.Arguments       = "-m streamlit run `"$AppPath`" --server.address 0.0.0.0 --server.port $Port --server.headless true --browser.gatherUsageStats false"
        $psi.WorkingDirectory = "F:\Projects\resume_ranking"
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError  = $true
        $psi.UseShellExecute       = $false
        $psi.CreateNoWindow        = $true

        $proc = [System.Diagnostics.Process]::Start($psi)
        Write-Log "Streamlit started (PID $($proc.Id))"

        # Capture output asynchronously
        $stdout = $proc.StandardOutput.ReadToEndAsync()
        $stderr = $proc.StandardError.ReadToEndAsync()

        # Wait for port to open (up to 60 sec)
        $ready = $false
        for ($i = 0; $i -lt 30; $i++) {
            Start-Sleep -Seconds 2
            if (Test-PortOpen $Port) {
                Write-Log "Streamlit ready on port $Port"
                $ready = $true
                break
            }
        }
        if (-not $ready) {
            Write-Log "WARNING: Streamlit did not open port within 60 seconds."
        }

        # Wait for process to exit
        $proc.WaitForExit()
        $exitCode = $proc.ExitCode
        Write-Log "Streamlit exited with code $exitCode"

        # Log any output
        try {
            $out = $stdout.Result
            $err = $stderr.Result
            if ($out) { Write-Log "STDOUT: $($out.Substring([Math]::Max(0, $out.Length - 500)))" }
            if ($err) { Write-Log "STDERR: $($err.Substring([Math]::Max(0, $err.Length - 500)))" }
        } catch {}

    } catch {
        Write-Log "ERROR starting Streamlit: $_"
    } finally {
        if ($proc -and -not $proc.HasExited) {
            Write-Log "Terminating orphaned Streamlit process..."
            $proc.Kill()
        }
    }

    Write-Log "Restarting in 5 seconds..."
    Start-Sleep -Seconds 5
}
