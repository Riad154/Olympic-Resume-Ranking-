# Olympic Industries — HR AI Resume Ranking System

**AI-powered resume screening and ranking pipeline** for Olympic Industries PLC.

Built with: Python · Streamlit · PostgreSQL · Ollama (LLM) · Docker

---

## System Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Streamlit     │────▶│   PostgreSQL     │◀────│   Ranker CLI    │
│   Dashboard     │     │   (candidates,   │     │   (async LLM    │
│   (resume_app/) │     │    jobs, users)  │     │    workers)     │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                                            │
         │         ┌──────────────────┐              │
         └────────▶│   Ollama Server  │◀─────────────┘
                   │   (qwen3:8b)     │
                   └──────────────────┘
                            │
                   ┌──────────────────┐
                   │   BDJobs API     │
                   │   (downloader)   │
                   └──────────────────┘
```

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | Streamlit 1.32+ | Interactive dashboard |
| **Backend** | Python 3.10+ | Ranking engine, data processing |
| **Database** | PostgreSQL 15 | Persistent storage |
| **LLM** | Ollama + qwen3:8b-q4_K_M | Resume scoring & analysis |
| **Scraper** | Playwright | BDJobs resume downloading |
| **Container** | Docker + Docker Compose | Portable deployment |

---

## Quick Start

### Prerequisites

- Windows 10/11 or Linux/macOS
- Python 3.10+
- Docker Desktop
- Ollama (with NVIDIA GPU recommended, 8 GB+ VRAM)

### One-time setup

```powershell
# Windows (PowerShell as Administrator)
cd f:\Projects\resume_ranking
.\scripts\setup.ps1
```

```bash
# Linux / macOS
bash scripts/setup.sh
```

### Daily operation

```powershell
# Start everything
.\scripts\start.ps1

# Stop everything
.\scripts\stop.ps1

# Create backup
.\scripts\backup.ps1

# Restore from backup
.\scripts\restore.ps1 -BackupPath "backups\backup_20260115_143022.zip"
```

Access the dashboard at: **http://localhost:8501**

---

## Folder Structure

```
resume_ranking/
├── resume_app/                 # Streamlit multi-page app
│   ├── Home.py                 # Dashboard (entry point)
│   ├── db.py                   # Database layer + utilities
│   ├── _bdjobs_registry.py   # 43 live BDJobs listings
│   ├── pages/
│   │   ├── 0_Login.py          # Authentication
│   │   ├── 1_Department_Rankings.py
│   │   ├── 2_Job_Rankings.py
│   │   ├── 3_New_Job.py
│   │   ├── 4_Processing_Status.py
│   │   └── 5_Settings.py
│   └── assets/                 # Logos, favicons
│
├── ranker.py                   # Async parallel ranking CLI
├── check_ollama.py             # Pre-flight health checks
├── bdjobs_downloader.py        # BDJobs resume scraper
├── bdjobs_login.py             # One-time login helper
├── dashboard.py                # Single-page dashboard (legacy)
│
├── docker/
│   └── init-scripts/           # PostgreSQL init scripts
├── scripts/                    # Automation scripts
│   ├── setup.ps1 / setup.sh
│   ├── start.ps1 / start.sh
│   ├── stop.ps1 / stop.sh
│   ├── backup.ps1 / backup.sh
│   └── restore.ps1 / restore.sh
│
├── Dockerfile                  # Application container
├── docker-compose.yml          # Full stack orchestration
├── requirements.txt            # Python dependencies
├── .env.example                # Configuration template
├── RUN.md                      # Detailed run guide
├── MIGRATION_GUIDE.md          # PC migration instructions
└── downloaded_resumes/         # Job folders with CVs
```

---

## Environment Variables

Create `.env` from `.env.example`:

```env
# PostgreSQL
PG_HOST=localhost
PG_PORT=5432
PG_DBNAME=resume_ranking
PG_USER=postgres
PG_PASSWORD=your-secure-password

# Ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen3:8b-q4_K_M

# Paths
RESUMES_BASE=./downloaded_resumes
RANKER_PATH=./ranker.py

# Concurrency
RANKER_WORKERS=2
```

---

## Docker Deployment

### Option A: Docker Compose (recommended)

```bash
docker compose up -d
```

Services:
- `postgres` — PostgreSQL 15 on port 5432
- `app` — Streamlit on port 8501

### Option B: Manual Docker

```bash
# Build image
docker build -t hr-ai-app .

# Run
docker run -d -p 8501:8501 \
  --env-file .env \
  -v $(pwd)/downloaded_resumes:/app/downloaded_resumes \
  hr-ai-app
```

---

## Database Schema

Auto-created on first connection by `db.py`:

| Table | Purpose |
|-------|---------|
| `candidates` | Resume data, scores, strengths, gaps |
| `jobs` | Job postings and JD text |
| `users` | Authentication (bcrypt hashed) |
| `audit_logs` | Login and action tracking |
| `bdjobs_applicants` | Raw BDJobs applicant registry |

---

## Backup Strategy

### Automated (recommended)

```powershell
# Add to Windows Task Scheduler daily at 6 PM
.\scripts\backup.ps1
```

### Manual

```powershell
# Full system backup (DB + files + config)
.\scripts\backup.ps1

# Database-only backup
docker exec hr_postgres pg_dump -U postgres -d resume_ranking > db_backup.sql
```

### Storage

Keep backups in:
- `backups/` folder (local)
- External drive / USB
- Cloud storage (OneDrive, Google Drive)

---

## Migration (New PC)

See **[MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)** for complete step-by-step instructions.

Quick summary:
1. Run `backup.ps1` on old PC → get ZIP
2. Copy ZIP to new PC
3. Install prerequisites (Python, Docker, Ollama)
4. Run `setup.ps1` then `restore.ps1`
5. Verify at http://localhost:8501

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `Connection refused` 5432 | PostgreSQL not running | `docker start hr_postgres` |
| Cannot reach Ollama | Ollama not started | Launch from system tray |
| Login page slow | DB schema creation on first run | Wait 30–60s, then refresh |
| Ranker slow (60s/candidate) | `OLLAMA_NUM_PARALLEL` not set | `setx OLLAMA_NUM_PARALLEL 3`, restart Ollama |
| GPU memory warning | Too many workers | Reduce `--workers` to 1–2 |
| Scores all 0 | Schema mismatch | Ensure using latest `ranker.py` |

---

## Security Notes

- **Never commit `.env`** — it contains passwords
- **Rotate `PG_PASSWORD`** periodically
- **Use bcrypt passwords** — default admin is set via `create_admin.py`
- **Backup encryption** — ZIP backups may contain sensitive candidate data; store securely
- **Streamlit secrets** — for cloud deployment, use `.streamlit/secrets.toml` (not in Git)

---

## Performance Benchmarks

Hardware: RTX 3060 Ti (8 GB), qwen3:8b-q4_K_M

| Workers | Sec/candidate | 197 candidates |
|---------|--------------|----------------|
| 1 | ~60 s | ~197 min |
| 2 | ~13 s | ~43 min |
| 3 | ~9 s | ~30 min |

To go faster: use `qwen3:8b-q3_K_S` (smaller quant) or more VRAM.

---

## Support

- **Run guide**: [RUN.md](RUN.md)
- **Migration**: [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)
- **BDJobs access**: [HR_ACCESS_GUIDE.md](HR_ACCESS_GUIDE.md)
- **IT server guide**: [IT_SERVER_GUIDE.md](IT_SERVER_GUIDE.md)

---

## License

Internal use only — Olympic Industries PLC
