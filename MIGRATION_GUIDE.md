# Olympic Industries — HR AI System Migration Guide

**Old PC → New PC — Complete step-by-step checklist**

---

## What You Are Migrating

| Component | Description |
|-----------|-------------|
| **Application code** | Python scripts, Streamlit app, config files |
| **Database** | PostgreSQL with candidates, jobs, users, audit logs |
| **Resumes** | Downloaded PDFs and extracted text profiles |
| **Environment** | `.env` file with passwords and API endpoints |
| **Ollama model** | `qwen3:8b-q4_K_M` (re-downloadable) |

---

## Pre-Migration (Old PC)

### Step 1: Create a full backup

```powershell
# On old PC (PowerShell, run as Administrator)
cd f:\Projects\resume_ranking
.\scripts\backup.ps1
```

This creates: `backups\backup_<timestamp>.zip`

**Copy this ZIP to a USB drive, cloud storage, or network share.**

### Step 2: Note down these values from your `.env`

```powershell
cat .env
```

You will need them on the new PC. **Do not lose this file.**

### Step 3: Export database (if backup script fails)

```powershell
$env:PGPASSWORD = "your-password"
docker exec hr_postgres pg_dump -U postgres -d resume_ranking > resume_ranking_backup.sql
```

---

## New PC Setup

### Step 4: Install prerequisites

| Software | Download Link | Purpose |
|----------|--------------|---------|
| Python 3.10+ | https://python.org | Application runtime |
| Git | https://git-scm.com | Version control |
| Docker Desktop | https://docker.com/products/docker-desktop | PostgreSQL container |
| Ollama | https://ollama.com | LLM inference engine |
| NVIDIA Drivers | https://nvidia.com/drivers | GPU acceleration |

### Step 5: Copy the project

```powershell
# Option A: Clone from GitHub (if you pushed)
git clone https://github.com/your-org/resume_ranking.git f:\Projects\resume_ranking

# Option B: Extract from ZIP (if no GitHub)
# Extract your backup ZIP to f:\Projects\resume_ranking
```

### Step 6: Run setup

```powershell
cd f:\Projects\resume_ranking
.\scripts\setup.ps1
```

This will:
- Create a Python virtual environment
- Install all dependencies
- Start PostgreSQL in Docker
- Prompt you to pull the Ollama model

### Step 7: Restore your data

```powershell
# If you used the backup script:
.\scripts\restore.ps1 -BackupPath "backups\backup_<timestamp>.zip"

# Or manually restore just the database:
$env:PGPASSWORD = "your-password"
Get-Content resume_ranking_backup.sql | docker exec -i hr_postgres psql -U postgres -d resume_ranking
```

### Step 8: Copy `.env`

Paste your old `.env` values into the new `.env` file:

```powershell
notepad .env
```

Make sure these match the old PC:
- `PG_PASSWORD`
- `OLLAMA_MODEL`
- `RANKER_WORKERS`

### Step 9: Start the system

```powershell
.\scripts\start.ps1
```

Open browser: http://localhost:8501

---

## Verification Checklist

After starting, verify these work:

- [ ] Login page loads at `http://localhost:8501`
- [ ] You can log in with your admin credentials
- [ ] Dashboard shows correct job/candidate counts
- [ ] Job Rankings page shows previously ranked candidates
- [ ] Processing Status page connects to Ollama
- [ ] Settings page shows PostgreSQL as "Connected"

If counts are wrong, the database restore may have failed. Re-run `restore.ps1`.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Connection refused` on port 5432 | `docker start hr_postgres` |
| Dashboard shows 0 candidates | Database not restored — re-run restore script |
| Ollama not found | Install Ollama, then `ollama pull qwen3:8b-q4_K_M` |
| Streamlit won't start | Check `.venv\Scripts\streamlit.exe` exists; if not, re-run `setup.ps1` |
| Missing resumes | Copy `downloaded_resumes/` folder from old PC |
| Login fails | Check that database was restored (users table) |

---

## Rollback Plan

If migration fails:

1. Stop everything: `.\scripts\stop.ps1`
2. Keep the old PC running — do not wipe it until new PC is verified
3. The backup ZIP is your safety net — you can restore any time

---

## Post-Migration

- Update Git remote if the new PC has a different path
- Set up autostart: see `setup_autostart.ps1`
- Schedule regular backups: add `backup.ps1` to Windows Task Scheduler
