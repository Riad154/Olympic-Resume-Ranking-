"""
3_Processing_Status.py — Live progress monitor for ranker.py runs.

Reads _ranker_progress.jsonl from each job folder under downloaded_resumes/
and surfaces progress, ETA, errors, and GPU/Ollama status in real time.
"""

from __future__ import annotations

import os
import json
import time
import datetime
from pathlib import Path

import requests
import streamlit as st

from db import get_css, init_theme, render_sidebar


# ── Config / paths ────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RESUMES_BASE = Path(os.environ.get(
    "RESUMES_BASE",
    str(BASE_DIR / "downloaded_resumes"),
))
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

st.set_page_config(
    page_title="Processing Status — HR Intelligence",
    page_icon="⏳",
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
    if not RESUMES_BASE.exists():
        return []
    return sorted(
        [p.name for p in RESUMES_BASE.iterdir()
         if p.is_dir() and (p / "_ranker_progress.jsonl").exists()],
        reverse=True,
    )


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


def gpu_stats() -> dict | None:
    try:
        import pynvml
        pynvml.nvmlInit()
        if pynvml.nvmlDeviceGetCount() == 0:
            return None
        h = pynvml.nvmlDeviceGetHandleByIndex(0)
        name = pynvml.nvmlDeviceGetName(h)
        if isinstance(name, bytes):
            name = name.decode("utf-8", errors="ignore")
        mem = pynvml.nvmlDeviceGetMemoryInfo(h)
        util = pynvml.nvmlDeviceGetUtilizationRates(h)
        out = {
            "name": name,
            "vram_used_gb":  mem.used / (1024 ** 3),
            "vram_total_gb": mem.total / (1024 ** 3),
            "util_pct":      int(util.gpu),
        }
        pynvml.nvmlShutdown()
        return out
    except Exception:
        return None


def ollama_ps() -> list[dict] | None:
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/ps", timeout=3)
        r.raise_for_status()
        return r.json().get("models", []) or []
    except Exception:
        return None


# ── Sidebar ───────────────────────────────────────────────────────────────────

jobs = list_job_folders()
if not jobs:
    st.warning(f"No progress logs found under `{RESUMES_BASE}`.")
    st.stop()

with st.sidebar:
    st.header("Job")
    selected = st.selectbox("Progress log", jobs, index=0)
    auto_refresh = st.checkbox("Auto-refresh (3s)", value=True)
    refresh_now = st.button("Refresh now")

events = read_progress(selected)

# ── Parse events ──────────────────────────────────────────────────────────────

start_ev = next((e for e in events if e.get("event") == "start"), None)
done_ev  = next((e for e in reversed(events) if e.get("event") == "done"), None)
oks      = [e for e in events if e.get("event") == "ok"]
errs     = [e for e in events if e.get("event") == "error"]

total   = (start_ev or {}).get("total", len(oks) + len(errs))
workers = (start_ev or {}).get("workers", "?")
processed = len(oks) + len(errs)

# ETA calc: from first ok/error timestamp to last, / processed -> avg; times remaining.
eta_str = "—"
if processed >= 2 and total and processed < total:
    try:
        ts = [datetime.datetime.fromisoformat(e["ts"])
              for e in events if e.get("event") in ("ok", "error") and "ts" in e]
        if len(ts) >= 2:
            elapsed = (ts[-1] - ts[0]).total_seconds()
            avg = elapsed / max(1, len(ts) - 1)
            remaining = avg * (total - processed)
            mins = remaining / 60.0
            eta_str = f"~{mins:.1f} min ({avg:.1f}s/candidate)"
    except Exception:
        pass

# ── Top metrics ───────────────────────────────────────────────────────────────

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total", total or 0)
c2.metric("Processed", processed)
c3.metric("✅ OK", len(oks))
c4.metric("⚠ Errors", len(errs))
c5.metric("Workers", workers)

pct = (processed / total) if total else 0.0
st.progress(min(1.0, pct), text=f"Ranked {processed} of {total or '?'} — ETA {eta_str}")

if done_ev:
    st.success(f"Run finished at {done_ev.get('ts', '?')} with {done_ev.get('errors', 0)} errors.")

# ── GPU + Ollama status ───────────────────────────────────────────────────────

col_gpu, col_ol = st.columns(2)

with col_gpu:
    st.subheader("GPU")
    g = gpu_stats()
    if g is None:
        st.error("🔴 No NVIDIA GPU detected (or pynvml unavailable).")
    else:
        util = g["util_pct"]
        if util > 50:
            icon = "🟢 Active"
        elif util < 20:
            icon = "🟡 Idle"
        else:
            icon = "🟠 Ramping"
        st.markdown(f"**{g['name']}** — {icon}")
        st.markdown(
            f"- VRAM: {g['vram_used_gb']:.1f} / {g['vram_total_gb']:.1f} GB\n"
            f"- Utilization: **{util}%**"
        )
        st.progress(min(1.0, util / 100.0))

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
