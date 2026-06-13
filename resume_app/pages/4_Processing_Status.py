"""
3_Processing_Status.py — Live progress monitor for ranker.py runs.

Reads _ranker_progress.jsonl from each job folder under downloaded_resumes/
and surfaces progress, ETA, errors, and GPU/Ollama status in real time.
"""

from __future__ import annotations

import os
import sys
import json
import time
import datetime
from pathlib import Path

import requests
import streamlit as st

from db import get_css, init_theme, render_sidebar, _is_streamlit_cloud


# ── Config / paths ────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RESUMES_BASE = Path(os.environ.get(
    "RESUMES_BASE",
    str(BASE_DIR / "downloaded_resumes"),
))
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

# ── Cloud detection ─────────────────────────────────────────────────────────────
ON_CLOUD = _is_streamlit_cloud()

# ── Cloud: rich status view matching local UI design ──────────────────────────
if ON_CLOUD:
    st.markdown(get_css(), unsafe_allow_html=True)
    render_sidebar()

    st.markdown('<div class="page-title">Processing Status</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-sub">Ranker &amp; scraper status on Streamlit Cloud</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # ── Sidebar: job selector + refresh controls ───────────────────────────────
    job_labels = []
    try:
        from db import get_conn
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT job_label FROM jobs ORDER BY updated_at DESC")
            job_labels = [r[0] for r in cur.fetchall() if r[0]]
    except Exception:
        pass

    if not job_labels:
        try:
            job_labels = list_job_folders()
        except Exception:
            pass

    if not job_labels:
        st.warning("No jobs found. Create a job on the New Job Posting page first.")
        st.stop()

    with st.sidebar:
        st.header("Job")
        selected_job = st.selectbox("Select job", job_labels, index=0)
        auto_refresh = st.checkbox("Auto-refresh (3s)", value=True)
        refresh_now = st.button("Refresh now")

    # ── Fetch per-job DB stats ────────────────────────────────────────────────
    db_stats = {
        "total": 0, "ranked": 0, "errors": 0,
        "recent": [], "err_rows": [],
    }
    try:
        from db import get_conn
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM candidates WHERE job_label = %s",
                (selected_job,)
            )
            db_stats["total"] = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM candidates WHERE job_label = %s AND overall_score IS NOT NULL",
                (selected_job,)
            )
            db_stats["ranked"] = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM candidates WHERE job_label = %s AND rank_error IS NOT NULL AND rank_error != ''",
                (selected_job,)
            )
            db_stats["errors"] = cur.fetchone()[0]
            cur.execute("""
                SELECT apply_id, candidate_name, overall_score, recommendation, ranked_at, rank_error
                FROM candidates
                WHERE job_label = %s AND overall_score IS NOT NULL
                ORDER BY ranked_at DESC NULLS LAST
                LIMIT 10
            """, (selected_job,))
            db_stats["recent"] = cur.fetchall()
            cur.execute("""
                SELECT apply_id, candidate_name, rank_error, ranked_at
                FROM candidates
                WHERE job_label = %s AND rank_error IS NOT NULL AND rank_error != ''
                ORDER BY ranked_at DESC NULLS LAST
            """, (selected_job,))
            db_stats["err_rows"] = cur.fetchall()
    except Exception as e:
        st.error(f"Database error: {e}")

    total   = db_stats["total"]
    ranked  = db_stats["ranked"]
    errors  = db_stats["errors"]
    recent  = db_stats["recent"]
    err_rows = db_stats["err_rows"]

    # ── GitHub Actions status (compact) ────────────────────────────────────────
    with st.expander("🚀 GitHub Actions — BDJobs Scraper", expanded=False):
        try:
            sys.path.insert(0, str(BASE_DIR / "scripts"))
            from github_actions import _get_token, _get_repo, get_latest_run_status
            token = _get_token()
            repo = _get_repo()
            if token:
                run = get_latest_run_status(repo, token)
                if run.get("status") == "error":
                    st.error(f"Could not fetch run status: {run.get('msg', 'Unknown error')}")
                else:
                    status = run.get("status", "unknown")
                    conclusion = run.get("conclusion", "—")
                    created = run.get("created_at", "—")
                    url = run.get("html_url", f"https://github.com/{repo}/actions")
                    status_icon = {
                        "completed": "✅", "in_progress": "🔄",
                        "queued": "⏳", "waiting": "⏳", "requested": "⏳",
                    }.get(status, "❓")
                    st.markdown(f"**Latest run:** {status_icon} `{status}` — conclusion: `{conclusion}`")
                    st.markdown(f"**Created:** {created}")
                    st.link_button("View on GitHub →", url, type="secondary")
            else:
                st.warning("No GH_TOKEN configured.")
        except Exception as e:
            st.error(f"Failed to fetch GitHub Actions status: {e}")

    # ── Top metrics bar (matches local layout) ─────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total", total)
    c2.metric("Processed", ranked)
    c3.metric("✅ OK", max(0, ranked - errors))
    c4.metric("⚠ Errors", errors)
    remaining = max(0, total - ranked)
    c5.metric("⏳ Remaining", remaining)

    pct = (ranked / total) if total else 0.0
    st.progress(min(1.0, pct), text=f"Ranked {ranked} of {total or '?'} candidates")

    # ── Database activity (matches local "Last 10 processed") ──────────────────
    st.subheader("Last 10 processed")
    if recent:
        rows = []
        for r in recent:
            apply_id, name, score, rec, ts, err = r
            ts_str = str(ts)[-8:] if ts else "—"
            rows.append({
                "When": ts_str,
                "Apply ID": apply_id or "",
                "Name": name or "",
                "Score": score if score is not None else "—",
                "Verdict": rec or "",
                "Note": "" if not err else err[:80],
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.caption("No candidates processed yet for this job.")

    # ── Errors expander (matches local) ────────────────────────────────────────
    with st.expander(f"Errored candidates ({len(err_rows)})", expanded=False):
        if err_rows:
            st.dataframe(
                [{
                    "Apply ID": r[0] or "",
                    "Name":     r[1] or "",
                    "Error":    r[2] or "",
                    "When":     str(r[3]) if r[3] else "",
                } for r in err_rows],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("No errors so far.")

    # ── Auto refresh ───────────────────────────────────────────────────────────
    if auto_refresh:
        time.sleep(3)
        st.rerun()
    elif refresh_now:
        st.rerun()

    st.stop()

st.set_page_config(
    page_title="Processing Status — HR Intelligence",
    page_icon="../plc_logo_w_text.png",
    layout="wide",
    initial_sidebar_state="expanded",
)
init_theme()
st.markdown(get_css(), unsafe_allow_html=True)
render_sidebar()

st.markdown('<div class="page-title">Processing Status</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="page-sub">Live ranker progress · GPU &amp; Ollama health</div>',
    unsafe_allow_html=True,
)
st.markdown('<hr class="divider">', unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def list_job_folders() -> list[str]:
    """Return all job folders that have candidate data (profiles_txt or uploaded_cvs).
    Previously only showed folders with _ranker_progress.jsonl, which meant
    newly-created jobs didn't appear until ranker started."""
    if not RESUMES_BASE.exists():
        return []
    folders = []
    for p in RESUMES_BASE.iterdir():
        if not p.is_dir():
            continue
        has_profiles = (p / "profiles_txt").is_dir()
        has_cvs = (p / "uploaded_cvs").is_dir()
        if has_profiles or has_cvs:
            folders.append(p.name)
    return sorted(folders, reverse=True)


def read_progress(job_folder: str) -> list[dict]:
    path = RESUMES_BASE / job_folder / "_ranker_progress.jsonl"
    if not path.exists():
        return []
    events: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except Exception:
                continue
    return events


def gpu_stats() -> dict:
    """Return GPU stats dict. Keys always present: ok (bool), error (str|None)."""
    out: dict = {"ok": False, "error": None}
    try:
        import pynvml
    except ImportError:
        out["error"] = "pynvml not installed  →  `pip install nvidia-ml-py`"
        return out

    try:
        pynvml.nvmlInit()
    except Exception as e:
        out["error"] = f"nvmlInit failed: {e}"
        return out

    try:
        count = pynvml.nvmlDeviceGetCount()
        if count == 0:
            out["error"] = "No NVIDIA GPUs found on this host"
            pynvml.nvmlShutdown()
            return out

        h = pynvml.nvmlDeviceGetHandleByIndex(0)
        name = pynvml.nvmlDeviceGetName(h)
        if isinstance(name, bytes):
            name = name.decode("utf-8", errors="ignore")
        mem = pynvml.nvmlDeviceGetMemoryInfo(h)
        util = pynvml.nvmlDeviceGetUtilizationRates(h)

        # Optional extra sensors (temp, power, clocks)
        try:
            temp = pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)
        except Exception:
            temp = None
        try:
            power = pynvml.nvmlDeviceGetPowerUsage(h) / 1000.0
        except Exception:
            power = None
        try:
            clk_graphics = pynvml.nvmlDeviceGetClockInfo(h, pynvml.NVML_CLOCK_GRAPHICS)
        except Exception:
            clk_graphics = None
        try:
            clk_mem = pynvml.nvmlDeviceGetClockInfo(h, pynvml.NVML_CLOCK_MEM)
        except Exception:
            clk_mem = None

        pynvml.nvmlShutdown()

        out.update({
            "ok": True,
            "error": None,
            "name": name,
            "vram_used_gb":  mem.used / (1024 ** 3),
            "vram_total_gb": mem.total / (1024 ** 3),
            "util_pct":      int(util.gpu),
            "temp_c":        temp,
            "power_w":       power,
            "clk_graphics_mhz": clk_graphics,
            "clk_mem_mhz":   clk_mem,
        })
        return out
    except Exception as e:
        out["error"] = f"Unexpected NVML error: {e}"
        try:
            pynvml.nvmlShutdown()
        except Exception:
            pass
        return out


def ollama_ps() -> list[dict] | None:
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/ps", timeout=3)
        r.raise_for_status()
        return r.json().get("models", []) or []
    except Exception:
        return None


# ── Sidebar (local only) ────────────────────────────────────────────────────

jobs = list_job_folders()
if not jobs:
    st.warning(f"No job folders found under `{RESUMES_BASE}`. Download or upload CVs first.")
    st.stop()

with st.sidebar:
    st.header("Job")
    selected = st.selectbox("Progress log", jobs, index=0)
    # Show a note if no progress file yet
    _progress_path = RESUMES_BASE / selected / "_ranker_progress.jsonl"
    if not _progress_path.exists():
        st.info("⏳ Ranking not started yet. Use the **New Job Posting** page to start ranking.")
    # NAV-02: peek at events first so we can disable auto-refresh once the
    # run is complete. Otherwise the page keeps spinning on a finished run.
    _peek_events = read_progress(selected)
    _peek_done = any(e.get("event") == "done" for e in _peek_events)
    if _peek_done:
        auto_refresh = st.checkbox(
            "Auto-refresh (3s)", value=False, disabled=True,
            help="Run is complete — auto-refresh disabled.",
        )
    else:
        auto_refresh = st.checkbox("Auto-refresh (3s)", value=True)
    refresh_now = st.button("Refresh now")

events = _peek_events

# ── Parse events ──────────────────────────────────────────────────────────────

start_ev = next((e for e in events if e.get("event") == "start"), None)
done_ev  = next((e for e in reversed(events) if e.get("event") == "done"), None)
oks      = [e for e in events if e.get("event") == "ok"]
errs     = [e for e in events if e.get("event") == "error"]

total   = (start_ev or {}).get("total", len(oks) + len(errs))
workers = (start_ev or {}).get("workers", "?")
processed = len(oks) + len(errs)

# ETA + speed calc from first ok/error timestamp to last, / processed -> avg; times remaining.
eta_str = "—"
speed_str = "—"        # candidates per second
avg_sec = None
if processed >= 2 and total and processed < total:
    try:
        ts = [datetime.datetime.fromisoformat(e["ts"])
              for e in events if e.get("event") in ("ok", "error") and "ts" in e]
        if len(ts) >= 2:
            elapsed = (ts[-1] - ts[0]).total_seconds()
            avg_sec = elapsed / max(1, len(ts) - 1)
            remaining = avg_sec * (total - processed)
            mins = remaining / 60.0
            eta_str = f"~{mins:.1f} min"
            speed_str = f"{1.0 / avg_sec:.2f} cand/s"
    except Exception:
        pass

if avg_sec is None and start_ev:
    # Fallback: use wall-clock time since start event
    try:
        start_ts = datetime.datetime.fromisoformat(start_ev.get("ts", ""))
        elapsed = (datetime.datetime.now() - start_ts).total_seconds()
        if elapsed > 0 and processed > 0:
            avg_sec = elapsed / processed
            remaining = avg_sec * (total - processed)
            eta_str = f"~{remaining/60.0:.1f} min (wall)"
            speed_str = f"{1.0 / avg_sec:.2f} cand/s"
    except Exception:
        pass

# ── Top metrics ───────────────────────────────────────────────────────────────

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Total", total or 0)
c2.metric("Processed", processed)
c3.metric("✅ OK", len(oks))
c4.metric("⚠ Errors", len(errs))
c5.metric("Workers", workers)
c6.metric("⚡ Speed", speed_str, delta=eta_str)

pct = (processed / total) if total else 0.0
st.progress(min(1.0, pct), text=f"Ranked {processed} of {total or '?'} — ETA {eta_str}")

if done_ev:
    st.success(f"Run finished at {done_ev.get('ts', '?')} with {done_ev.get('errors', 0)} errors.")

# ── GPU + Ollama status ───────────────────────────────────────────────────────

col_gpu, col_ol = st.columns(2)

with col_gpu:
    st.subheader("GPU")
    g = gpu_stats()
    if not g.get("ok"):
        # Distinguish missing driver vs no GPUs vs init error
        err = g.get("error", "Unknown error")
        if "not installed" in err.lower():
            st.warning(f"⚠️ {err}")
            st.caption("GPU metrics unavailable. Install pynvml to monitor VRAM & utilization.")
        elif "no nvidia" in err.lower() or "count == 0" in err.lower():
            st.info(f"ℹ️ {err}")
        else:
            st.error(f"🔴 {err}")
    else:
        util = g["util_pct"]
        vram_used = g["vram_used_gb"]
        vram_total = g["vram_total_gb"]
        vram_pct = (vram_used / vram_total * 100.0) if vram_total else 0

        # Health / speed status
        if util > 70 and vram_pct > 80:
            health_icon = "🟢 Healthy & Busy"
            health_color = "green"
        elif util > 50:
            health_icon = "🟢 Active"
            health_color = "green"
        elif util < 10 and vram_pct < 20:
            health_icon = "🟡 Idle / Under-utilized"
            health_color = "orange"
        elif vram_pct > 90:
            health_icon = "🔴 VRAM Critical"
            health_color = "red"
        else:
            health_icon = "🟠 Ramping"
            health_color = "orange"

        st.markdown(f"**{g['name']}** — <span style='color:{health_color}'>{health_icon}</span>", unsafe_allow_html=True)

        # Metrics row inside GPU column
        mg1, mg2, mg3 = st.columns(3)
        mg1.metric("Utilization", f"{util}%")
        mg2.metric("VRAM", f"{vram_used:.1f}/{vram_total:.1f} GB")
        mg3.metric("VRAM %", f"{vram_pct:.0f}%")

        st.progress(min(1.0, util / 100.0), text=f"GPU compute {util}%")
        st.progress(min(1.0, vram_pct / 100.0), text=f"VRAM {vram_pct:.0f}%")

        # Extra sensors
        extras = []
        if g.get("temp_c") is not None:
            extras.append(f"Temp: **{g['temp_c']}°C**")
        if g.get("power_w") is not None:
            extras.append(f"Power: **{g['power_w']:.1f} W**")
        if g.get("clk_graphics_mhz") is not None:
            extras.append(f"Clock: **{g['clk_graphics_mhz']} MHz**")
        if extras:
            st.caption("  ·  ".join(extras))

        # Processing speed context
        if speed_str != "—":
            st.caption(f"Current throughput: **{speed_str}**  ·  avg {avg_sec:.1f}s per candidate" if avg_sec else f"Current throughput: **{speed_str}**")

with col_ol:
    st.subheader("Ollama")
    ps = ollama_ps()
    if ps is None:
        st.error(f"🔴 Cannot reach Ollama at {OLLAMA_HOST}")
    elif not ps:
        st.info("No models currently loaded (will load on first request).")
    else:
        for m in ps:
            name = m.get("name", "?")
            vram = (m.get("size_vram") or 0) / 1e9
            total_sz = (m.get("size") or 0) / 1e9
            on_gpu_pct = (100.0 * (m.get("size_vram") or 0) / (m.get("size") or 1))
            st.markdown(
                f"**{name}** — {vram:.1f}/{total_sz:.1f} GB "
                f"({on_gpu_pct:.0f}% on GPU)"
            )

# ── Recent candidates ─────────────────────────────────────────────────────────

st.subheader("Last 10 processed")
recent = [e for e in events if e.get("event") in ("ok", "error")][-10:][::-1]
if recent:
    rows = []
    for e in recent:
        rows.append({
            "When": e.get("ts", "")[-8:],
            "Apply ID": e.get("apply_id", ""),
            "Name": e.get("name", ""),
            "Score": e.get("score", "—") if e.get("event") == "ok" else "—",
            "Verdict": e.get("recommendation", "") if e.get("event") == "ok" else "ERROR",
            "Note": "" if e.get("event") == "ok" else (e.get("error", "")[:80]),
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)
else:
    st.caption("No candidates processed yet.")

# ── Errors ────────────────────────────────────────────────────────────────────

with st.expander(f"Errored candidates ({len(errs)})", expanded=False):
    if errs:
        st.dataframe(
            [{
                "Apply ID": e.get("apply_id", ""),
                "Name":     e.get("name", ""),
                "Error":    e.get("error", ""),
                "When":     e.get("ts", ""),
            } for e in errs],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("No errors so far.")

# ── Auto refresh ──────────────────────────────────────────────────────────────

if auto_refresh and not done_ev:
    time.sleep(3)
    st.rerun()
elif refresh_now:
    st.rerun()
