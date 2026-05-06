# Olympic Industries — Resume Ranking System

Local AI resume ranking pipeline with parallel Ollama workers, PostgreSQL
storage, and a Streamlit dashboard.

---

## 1. Prerequisites

| Component | Version / Notes |
|---|---|
| Windows 10/11 | 64-bit |
| Python | 3.10+ (tested on 3.10) |
| NVIDIA GPU | ≥ 8 GB VRAM recommended for `qwen3:8b-q4_K_M` |
| Docker Desktop | For PostgreSQL container |
| Ollama | Installed + running in system tray |

---

## 2. One-time setup

### 2.1 Clone / extract the project

Extract this zip anywhere. Examples below assume `f:\Projects\resume_ranking`.

### 2.2 Create venv + install deps

```powershell
cd f:\Projects\resume_ranking
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium         # only if you use bdjobs_downloader.py
```

### 2.3 Start PostgreSQL (Docker)

```powershell
# First time (creates container):
docker run -d --name postgres15 `
  -e POSTGRES_PASSWORD="ai&dt@OIPLC" `
  -p 5432:5432 `
  -v pgdata:/var/lib/postgresql/data `
  postgres:15

# Subsequent starts:
docker start postgres15
```

`ranker.py` auto-creates the `resume_ranking` database and `candidates` table
on first run.

### 2.4 Pull the LLM

```powershell
ollama pull qwen3:8b-q4_K_M
```

### 2.5 Ollama env vars (CRITICAL for parallelism)

Without these the Ollama server serializes all requests and the parallel
ranker gives **no speedup**.

```powershell
setx OLLAMA_NUM_PARALLEL 3
setx OLLAMA_MAX_LOADED_MODELS 1
setx OLLAMA_KV_CACHE_TYPE q8_0
```

Then **fully quit the Ollama tray icon and relaunch it** — `setx` only
affects new processes.

---

## 3. Daily workflow

### 3.1 Download resumes from BDJobs

```powershell
.\venv\Scripts\Activate.ps1
python bdjobs_login.py                   # one-time browser login (saves session)
python bdjobs_downloader.py              # downloads into downloaded_resumes/<job>/
```

### 3.2 Pre-flight: check GPU + Ollama

```powershell
python check_ollama.py
```

Verifies: Ollama reachable, model installed, latency, GPU residency, env var
hints.

### 3.3 Rank candidates

```powershell
# Default (skips already-ranked):
python ranker.py --job AIDigital_Transformation-SrExecutive `
                 --jd downloaded_resumes\AIDigital_Transformation-SrExecutive\_jd_prompt.txt `
                 --workers 2

# Re-score everyone (overwrites existing scores):
python ranker.py --job AIDigital_Transformation-SrExecutive `
                 --jd downloaded_resumes\AIDigital_Transformation-SrExecutive\_jd_prompt.txt `
                 --workers 2 --rerank

# Fix "Unknown" candidate names without re-ranking:
python ranker.py --job AIDigital_Transformation-SrExecutive --backfill-names
```

**Worker count guidance (by free VRAM after model load):**

| Free VRAM | Safe `--workers` |
|---|---|
| < 2 GB | 1 |
| 2 – 4 GB | 2 |
| 4 – 8 GB | 3 – 4 |
| > 8 GB | 5 – 6 |

### 3.4 View rankings + live progress

```powershell
# Multi-page app (New Job / Rankings / Processing Status / Settings):
streamlit run resume_app\Home.py

# Or the simple single-page dashboard:
streamlit run dashboard.py
```

The **Processing Status** page (`resume_app/pages/3_Processing_Status.py`)
auto-refreshes every 3 s while `ranker.py` is running and shows:

- Progress bar + ETA
- Last 10 candidates with scores
- GPU utilization / VRAM
- Ollama model residency (`/api/ps`)
- Collapsible error list

---

## 4. Environment overrides (.env or shell)

The following variables are read at startup. Create a `.env` in the project
root (loaded by `python-dotenv`) or export them in PowerShell.

| Variable | Default | Purpose |
|---|---|---|
| `RESUMES_BASE` | `<script_dir>/downloaded_resumes` | Root folder of job directories |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama endpoint |
| `OLLAMA_MODEL` | `qwen3:8b-q4_K_M` | Model tag |
| `PG_HOST` | `localhost` | Postgres host |
| `PG_PORT` | `5432` | Postgres port |
| `PG_DBNAME` | `resume_ranking` | Database name |
| `PG_USER` | `postgres` | Database user |
| `PG_PASSWORD` | `ai&dt@OIPLC` | Database password |
| `RANKER_WORKERS` | `5` | Default `--workers` if not supplied |

---

## 5. Troubleshooting

| Symptom | Fix |
|---|---|
| `Connection refused` on 5432 | `docker start postgres15` |
| `Cannot reach Ollama` | Start Ollama from tray icon / Start menu |
| All scores show 0 in dashboard | Schema mismatch — ensure you're running the patched `ranker.py` + `dashboard.py` from this bundle |
| Ranker slow (~60 s/candidate even with `--workers 3`) | `OLLAMA_NUM_PARALLEL` not active: set via `setx`, **quit + relaunch Ollama tray** |
| GPU0 WARNING `< 6 GB free VRAM` | Close other GPU apps, or reduce `--workers`, or use a smaller quant |
| `qwen3` emits `<think>` blocks | Already handled — `/no_think` prepended + regex strip |

---

## 6. Performance benchmarks

Hardware: RTX 3060 Ti (8 GB), qwen3:8b-q4_K_M, `OLLAMA_NUM_PARALLEL=3`.

| Workers | Sec/candidate | 197 candidates total |
|---|---|---|
| 1 (pre-async) | ~60 s | ~197 min |
| 2 (this build) | ~13 s | ~43 min |
| 3 (VRAM permitting) | ~9 s | ~30 min |

To reach the < 20 min target on this GPU: switch to `qwen3:8b-q3_K_S`
(frees ~2 GB VRAM → 4 workers viable) or reduce context length via
`OLLAMA_CONTEXT_LENGTH=4096`.

---

## 7. File map

```
resume_ranking/
├── ranker.py                  # Async parallel ranking engine (main CLI)
├── check_ollama.py            # Ollama + GPU pre-flight utility
├── dashboard.py               # Standalone single-page dashboard
├── bdjobs_downloader.py       # Playwright scraper
├── bdjobs_login.py            # One-time login helper
├── requirements.txt
├── RUN.md                     # This file
├── resume_app/                # Multi-page Streamlit app
│   ├── Home.py
│   ├── db.py
│   ├── ingest_metadata.py
│   └── pages/
│       ├── 1_New_Job.py
│       ├── 2_Rankings.py
│       ├── 3_Processing_Status.py   # Live monitor (new)
│       └── 4_Settings.py
└── downloaded_resumes/        # Created per job by bdjobs_downloader
    └── <JobLabel>/
        ├── profiles_txt/
        ├── uploaded_cvs/
        ├── <JobLabel>_metadata.csv
        ├── _jd_prompt.txt
        └── _ranker_progress.jsonl   # Written by ranker, read by Status page
```
