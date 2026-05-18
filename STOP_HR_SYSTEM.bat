@echo off
title Stopping HR System...
echo Stopping Olympic HR Intelligence Platform...
taskkill /F /IM streamlit.exe /T > nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Olympic HR*" /T > nul 2>&1
echo Done. The HR Dashboard has been stopped.
echo PostgreSQL (Docker) is still running and data is preserved.
pause
