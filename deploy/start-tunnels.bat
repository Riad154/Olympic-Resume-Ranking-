@echo off
echo ============================================
echo  Olympic HR - Starting Services and Tunnels
echo ============================================

echo [1/3] Starting n8n...
start "n8n Server" cmd /k "n8n start"
timeout /t 5 /nobreak >nul

echo [2/3] Starting ngrok tunnels (Ollama + n8n)...
start "ngrok Tunnels" cmd /k "ngrok start --all --config %USERPROFILE%\.config\ngrok\ngrok.yml"
timeout /t 5 /nobreak >nul

echo [3/3] All services started!
echo.
echo Visit ngrok dashboard at: http://127.0.0.1:4040
echo to see your public tunnel URLs.
echo.
echo Copy the HTTPS URLs and update Streamlit Cloud secrets:
echo   OLLAMA_HOST = https://xxxx.ngrok-free.app  (from ollama tunnel)
echo   N8N_HOST    = https://yyyy.ngrok-free.app  (from n8n tunnel)
echo.
pause
