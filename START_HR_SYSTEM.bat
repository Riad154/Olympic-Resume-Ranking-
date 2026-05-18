@echo off
title Olympic HR Intelligence System — Starting...
color 0A

echo ============================================================
echo   Olympic Industries — HR Intelligence Platform
echo   Starting server... please wait.
echo ============================================================
echo.

REM -- Step 1: Check Docker is running
docker info > nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Desktop is not running.
    echo Please start Docker Desktop and try again.
    pause
    exit /b 1
)
echo [OK] Docker Desktop is running.

REM -- Step 2: Start PostgreSQL container
docker start postgres15 > nul 2>&1
if errorlevel 1 (
    echo [WARN] postgres15 container not found. Creating it now...
    docker run -d --name postgres15 ^
      -e POSTGRES_PASSWORD="ai&dt@OIPLC" ^
      -p 5432:5432 ^
      --restart unless-stopped ^
      -v pgdata:/var/lib/postgresql/data ^
      postgres:15
    timeout /t 5 /nobreak > nul
)
echo [OK] PostgreSQL is running.

REM -- Step 3: Load .env (so Python can read it)
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
        if not "%%A"=="" if not "%%A:~0,1%"=="#" set "%%A=%%B"
    )
)

REM -- Step 4: Launch Streamlit
echo [OK] Launching HR Dashboard on port 8501...
echo.
echo ============================================================
echo   Access from this machine:   http://localhost:8501
echo   Access from other computers: http://%COMPUTERNAME%:8501
echo              OR use the server IP address:
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /C:"IPv4 Address" ^| findstr /v "127.0.0.1"') do (
    for /f "tokens=1" %%b in ("%%a") do echo              http://%%b:8501
)
echo ============================================================
echo.
echo   Press Ctrl+C to stop the server.
echo.

cd /d "%~dp0"
.\venv\Scripts\python.exe -m streamlit run resume_app\Home.py --server.address=0.0.0.0 --server.port=8501

pause
