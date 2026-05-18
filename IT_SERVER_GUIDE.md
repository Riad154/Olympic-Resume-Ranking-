# IT Server Management Guide — HR Intelligence Platform

## Daily Startup (if not set to auto-start)

1. Ensure Docker Desktop is running (check system tray)
2. Double-click `START_HR_SYSTEM.bat` in the project folder
3. A terminal window opens showing the server IP and port
4. Leave the terminal window open — closing it stops the server

## Stopping the Server

- Double-click `STOP_HR_SYSTEM.bat`, OR
- Click on the terminal window that START_HR_SYSTEM opened and press `Ctrl+C`

## Server Address for HR Team

Run `ipconfig` in cmd and look for **IPv4 Address** under your LAN adapter.
Tell HR to use: `http://<that-IP>:8501`

## Restarting PostgreSQL (if database errors appear)

```powershell
docker start postgres15
```

## Ranking Resumes (Run as Needed — Not Part of the HR UI)

```powershell
.\venv\Scripts\Activate.ps1
python ranker.py --job <JobFolderName> --jd downloaded_resumes\<JobFolderName>\_jd_prompt.txt --workers 3
deactivate
```

Replace `<JobFolderName>` with the folder name under `downloaded_resumes\`.

## Backup the Database

```powershell
docker exec postgres15 pg_dump -U postgres resume_ranking > backup_$(Get-Date -Format 'yyyyMMdd').sql
```

## Folder Structure

```
resume_ranking\
├── START_HR_SYSTEM.bat      ← Start the server
├── STOP_HR_SYSTEM.bat       ← Stop the server
├── HR_ACCESS_GUIDE.md       ← For HR team
├── IT_SERVER_GUIDE.md       ← This file
├── .env                     ← Config (do not share)
├── ranker.py                ← Ranking engine (CLI)
├── resume_app\              ← Streamlit web app
│   ├── Home.py
│   ├── db.py
│   └── pages\
├── downloaded_resumes\      ← Resume data per job
└── venv\                    ← Python environment
```

## Firewall Rule (Required for LAN Access)

Run this in an **Administrator PowerShell** on the server machine:

```powershell
New-NetFirewallRule `
  -DisplayName "Olympic HR System - Streamlit Port 8501" `
  -Direction Inbound `
  -Protocol TCP `
  -LocalPort 8501 `
  -Action Allow `
  -Profile Domain,Private `
  -Description "Allows LAN access to the Olympic HR Intelligence Platform on port 8501"
```

## Optional: Auto-Start on Boot

Run in Administrator PowerShell:

```powershell
$action = New-ScheduledTaskAction -Execute "F:\Projects\resume_ranking\START_HR_SYSTEM.bat"
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 0) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName "OlympicHRSystem" -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "Auto-starts Olympic HR Intelligence Platform on boot"
```
