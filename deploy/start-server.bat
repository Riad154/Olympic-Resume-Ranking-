@echo off
echo ============================================
echo  Olympic HR AI - Server Startup
echo ============================================
echo.

echo [1/4] Stopping old Ollama instances...
taskkill /f /im ollama.exe >nul 2>&1
taskkill /f /im ollama_runners.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo [2/4] Starting Ollama...
set OLLAMA_ORIGINS=*
set OLLAMA_HOST=0.0.0.0:11434
start "Ollama Server" cmd /k "set OLLAMA_ORIGINS=* && set OLLAMA_HOST=0.0.0.0:11434 && ollama serve"
timeout /t 5 /nobreak >nul

echo [3/4] Starting Ollama Proxy (port 8080)...
start "Ollama Proxy" cmd /k "python %~dp0ollama_proxy.py"
timeout /t 3 /nobreak >nul

echo [4/4] Starting n8n...
start "n8n Server" cmd /k "n8n start"
timeout /t 3 /nobreak >nul

echo.
echo ============================================
echo  All services started!
echo ============================================
echo.
echo  Ollama:       http://localhost:11434
echo  Ollama Proxy: http://localhost:8080
echo  n8n:          http://localhost:5678
echo.
echo  Now run Tailscale Funnel:
echo    tailscale funnel reset
echo    tailscale funnel 8080
echo.
echo  Then test:
echo    curl https://ai.tail01167f.ts.net/api/tags
echo.
pause
