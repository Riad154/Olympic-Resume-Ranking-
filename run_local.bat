@echo off
REM Resume Ranking System — Quick Start (Local Mode)
REM Double-click this file to start the HR app

cd /d "F:\Projects\resume_ranking\resume_app"

REM Load environment variables from .env file
for /f "tokens=1,2 delims==" %%a in (..\.env) do (
    if not "%%a"=="" if not "%%b"=="" (
        if not "%%a:~0,1%"=="#" (
            set "%%a=%%b"
        )
    )
)

echo ==========================================
echo   Resume Ranking HR System
echo   Local Mode — Using GPU + Local DB
echo ==========================================
echo.
echo Starting Streamlit on port 8502...
echo.
echo Access URLs:
echo   This PC:     http://localhost:8502
echo   Network:     http://%COMPUTERNAME%:8502
echo   (Find IP with: ipconfig)
echo.
echo Press Ctrl+C to stop
echo.

python -m streamlit run Home.py --server.address 0.0.0.0 --server.port 8502

pause
