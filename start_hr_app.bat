@echo off
REM Resume Ranking HR System — Startup Script
REM Starts Ollama (if not running) and Streamlit app

echo ==========================================
echo   Olympic Industries HR Ranking System
echo   Local Deployment
echo ==========================================
echo.

REM Check if Ollama is running
tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | find /I "ollama.exe" >nul
if errorlevel 1 (
    echo [INFO] Starting Ollama...
    start "" "C:\Users\%USERNAME%\AppData\Local\Programs\Ollama\ollama.exe"
    timeout /t 5 /nobreak >nul
) else (
    echo [INFO] Ollama already running
)

REM Start Streamlit
cd /d "F:\Projects\resume_ranking\resume_app"
echo [INFO] Starting Streamlit on port 8502...
echo.
echo Access URLs:
echo   This PC:     http://localhost:8502
echo   Network:     http://192.168.55.65:8502
echo   Via VPN:     http://192.168.55.65:8502
echo.

python -m streamlit run Home.py --server.address 0.0.0.0 --server.port 8502

pause
