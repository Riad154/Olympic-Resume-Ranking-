# Resume Ranking System — Stop all app processes

Write-Host "=== Stopping HR Ranking System ===" -ForegroundColor Cyan

# Kill the watchdog PowerShell
Get-Process -Name "powershell" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*start_app.ps1*"
} | ForEach-Object {
    Write-Host "Stopping watchdog (PID $($_.Id))..."
    Stop-Process -Id $_.Id -Force
}

# Kill Streamlit
Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*streamlit*"
} | ForEach-Object {
    Write-Host "Stopping Streamlit (PID $($_.Id))..."
    Stop-Process -Id $_.Id -Force
}

Write-Host "Done. App stopped." -ForegroundColor Green
Start-Sleep -Seconds 1
