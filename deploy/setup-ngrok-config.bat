@echo off
echo ============================================
echo  Setting up ngrok config for Olympic HR
echo ============================================
echo.
echo Step 1: Creating ngrok config directory...
if not exist "%USERPROFILE%\.config\ngrok" mkdir "%USERPROFILE%\.config\ngrok"

echo Step 2: Writing ngrok.yml config...
(
echo version: "3"
echo.
echo agent:
echo   authtoken: YOUR_NGROK_AUTH_TOKEN_HERE
echo.
echo tunnels:
echo   ollama:
echo     proto: http
echo     addr: 11434
echo     schemes:
echo       - https
echo     inspect: false
echo.
echo   n8n:
echo     proto: http
echo     addr: 5678
echo     schemes:
echo       - https
echo     inspect: false
) > "%USERPROFILE%\.config\ngrok\ngrok.yml"

echo.
echo Step 3: Done! Now edit the config file to add your authtoken:
echo   %USERPROFILE%\.config\ngrok\ngrok.yml
echo.
echo Get your authtoken from: https://dashboard.ngrok.com/get-started/your-authtoken
echo.
echo Then run:
echo   ngrok start --all
echo.
pause
