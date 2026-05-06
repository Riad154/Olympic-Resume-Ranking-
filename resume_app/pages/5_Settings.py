"""
pages/4_Settings.py — System health and configuration.
"""
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

import requests
import psycopg2
import streamlit as st
from db import (
    get_conn, get_css, init_theme, render_sidebar, PG_CONN,
    fetch_all_jobs, get_job_department, update_job_status,
    fix_inconsistent_verdicts, associate_candidates_with_job,
    get_bdjobs_credentials, save_bdjobs_credentials,
    BDJOBS_JOB_REGISTRY,
    RANKER_PATH, VENV_PYTHON,
)

# FEAT-04: re-rank job spawner. Mirrors _spawn_ranker in pages/3_New_Job.py.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_LOG_DIR      = _PROJECT_ROOT / "_rank_logs"
_LOG_DIR.mkdir(exist_ok=True)


def _spawn_rerank(label: str, department: str, normalise: bool):
    cmd = [VENV_PYTHON, RANKER_PATH, "--job", label, "--rerank"]
    if department:
        cmd += ["--department", department]
    if normalise:
        cmd += ["--normalise"]
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = _LOG_DIR / f"rerank_{label}_{ts}.log"
    log_fp   = open(log_path, "w", encoding="utf-8")
    flags    = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
    proc     = subprocess.Popen(
        cmd, cwd=str(_PROJECT_ROOT),
        stdout=log_fp, stderr=subprocess.STDOUT,
        creationflags=flags,
    )
    return proc, str(log_path)

st.set_page_config(page_title="Settings — HR Intelligence", page_icon="⚙️", layout="wide", initial_sidebar_state="expanded")
init_theme()
st.markdown(get_css(), unsafe_allow_html=True)
render_sidebar()

is_day   = st.session_state.get("day_mode", True)
txt_col  = "#1E293B" if is_day else "#E2E8F0"
sub_col  = "#64748B"
card_bg  = "#FFFFFF" if is_day else "#1E2435"
card_bdr = "#E2E8F0" if is_day else "#2D3748"

st.markdown(f'<div class="page-title" style="color:{txt_col} !important;">Settings</div>', unsafe_allow_html=True)
st.markdown('<div class="page-sub">System configuration and health monitoring</div>', unsafe_allow_html=True)
st.markdown('<hr class="divider" style="border-top:1px solid ' + card_bdr + '">', unsafe_allow_html=True)

# ── System health ──────────────────────────────────────────────────────────────
st.markdown(f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">System Health</div>', unsafe_allow_html=True)
col1, col2 = st.columns(2, gap="large")

with col1:
    try:
        c = psycopg2.connect(**PG_CONN); c.close(); pg_ok=True; pg_msg="Connected"
    except Exception as e:
        pg_ok=False; pg_msg=str(e)[:60]

    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        ol_ok = r.status_code==200
        models = [m["name"] for m in r.json().get("models",[])] if ol_ok else []
        ol_msg = f"{len(models)} model(s) loaded" if ol_ok else "Not reachable"
    except:
        ol_ok=False; ol_msg="Not reachable"; models=[]

    try:
        r2 = requests.get("http://localhost:5678/healthz", timeout=3)
        n8_ok = r2.status_code==200; n8_msg="Running"
    except:
        n8_ok=False; n8_msg="Not reachable"

    for label, ok, msg in [
        ("PostgreSQL", pg_ok, pg_msg),
        ("Ollama",     ol_ok, ol_msg),
        ("n8n",        n8_ok, n8_msg),
    ]:
        dot = "🟢" if ok else "🔴"
        st.markdown(f"""
            <div style="background:{card_bg};border:1px solid {card_bdr};border-radius:8px;
                        padding:0.9rem 1.1rem;margin-bottom:0.6rem;
                        display:flex;justify-content:space-between;align-items:center;">
                <div style="font-size:0.9rem;font-weight:500;color:{txt_col} !important;">{dot} &nbsp; {label}</div>
                <div style="font-size:0.82rem;color:{sub_col} !important;">{msg}</div>
            </div>
        """, unsafe_allow_html=True)

with col2:
    st.markdown(f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Loaded Models</div>', unsafe_allow_html=True)
    if models:
        for m in models:
            active = "qwen3:8b" in m
            st.markdown(f"""
                <div style="background:{card_bg};border:1px solid {'#FECACA' if active else card_bdr};
                            border-radius:8px;padding:0.7rem 1rem;margin-bottom:0.5rem;
                            display:flex;justify-content:space-between;align-items:center;">
                    <div style="font-size:0.86rem;font-weight:{'600' if active else '400'};color:{txt_col} !important;">
                        {'⭐ ' if active else ''}{m}
                    </div>
                    {'<div style="font-size:0.72rem;background:#FEE2E2;color:#991B1B !important;padding:2px 8px;border-radius:10px;font-weight:500;">ACTIVE</div>' if active else ''}
                </div>
            """, unsafe_allow_html=True)
    else:
        st.warning("No models loaded. Is Ollama running?")

    if ol_ok:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🧪  Send Test Prompt", type="secondary"):
            with st.spinner("Testing Ollama..."):
                try:
                    resp = requests.post(
                        "http://localhost:11434/api/chat",
                        json={"model":"qwen3:8b-q4_K_M","format":"json","stream":False,
                              "messages":[
                                  {"role":"system","content":"Return JSON only."},
                                  {"role":"user","content":'Return: {"status":"ok","message":"Pipeline working"}'},
                              ]},
                        timeout=30,
                    )
                    content = resp.json()["message"]["content"]
                    st.success(f"✓ Ollama OK: {content[:100]}")
                except Exception as e:
                    st.error(f"Test failed: {e}")

st.markdown('<hr class="divider" style="border-top:1px solid ' + card_bdr + '">', unsafe_allow_html=True)

# ── DB stats ───────────────────────────────────────────────────────────────────
st.markdown(f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Database</div>', unsafe_allow_html=True)
try:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(DISTINCT job_label),COUNT(*),SUM(CASE WHEN overall_score IS NOT NULL THEN 1 ELSE 0 END),SUM(CASE WHEN rank_error IS NOT NULL THEN 1 ELSE 0 END) FROM candidates")
        n_jobs,n_cands,n_ranked,n_errors = cur.fetchone()

    for col, val, lbl in zip(
        st.columns(4),
        [n_jobs or 0, n_cands or 0, n_ranked or 0, n_errors or 0],
        ["Job Postings","Total Candidates","Ranked","Errors"],
    ):
        with col:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-val" style="color:{txt_col} !important;font-size:1.8rem;">{val}</div>
                    <div class="metric-lbl" style="color:{sub_col} !important;">{lbl}</div>
                </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"""
        <div style="background:{card_bg};border:1px solid {card_bdr};border-radius:8px;padding:1rem;
                    font-family:monospace;font-size:0.82rem;color:{txt_col} !important;line-height:2;">
            Host: {PG_CONN['host']}:{PG_CONN['port']} &nbsp;·&nbsp;
            Database: {PG_CONN['dbname']} &nbsp;·&nbsp;
            User: {PG_CONN['user']}
        </div>
    """, unsafe_allow_html=True)
except Exception as e:
    st.error(f"Database error: {e}")

st.markdown('<hr class="divider" style="border-top:1px solid ' + card_bdr + '">', unsafe_allow_html=True)

# ── Database Maintenance ─────────────────────────────────────────────────────
st.markdown(
    f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Database Maintenance</div>',
    unsafe_allow_html=True,
)
st.caption("One-shot operations to clean up legacy data inconsistencies.")

col1, col2 = st.columns([1, 2])
with col1:
    if st.button("🔧 Normalise Verdicts", type="primary", help="Collapse free-text LLM verdicts into canonical Shortlist/Maybe/Reject"):
        with st.spinner("Running normalisation …"):
            try:
                conn = get_conn()
                n = fix_inconsistent_verdicts(conn)
                st.success(f"✓ Normalised {n} rows.")
            except Exception as e:
                st.error(f"Migration failed: {e}")

with col2:
    st.info(
        "**What this does:**\n"
        "- Converts legacy free-text verdicts ('Yes', 'Strong Fit', 'Decline', etc.) into the canonical ternary\n"
        "- Leaves already-canonical values unchanged\n"
        "- Safe to re-run — only touches rows where recommendation ∉ {Shortlist, Maybe, Reject}"
    )

st.markdown('<hr class="divider" style="border-top:1px solid ' + card_bdr + '">', unsafe_allow_html=True)

# ── Salary Benchmarks ────────────────────────────────────────────────────────
st.markdown(
    f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Salary Benchmarks — All Open Roles</div>',
    unsafe_allow_html=True,
)
st.caption("Source: BDJobs listings. 'Stated' = explicit in job posting. 'Estimate' = market-based estimate.")

try:
    from db import BDJOBS_JOB_REGISTRY
    rows = []
    for label, meta in BDJOBS_JOB_REGISTRY.items():
        rows.append({
            "Department":      meta.get("department", "-"),
            "Role":            meta.get("job_title", label),
            "Location":        meta.get("location", "-"),
            "Experience":      meta.get("experience", "-"),
            "Salary (Stated)": meta.get("salary_stated", "Negotiable"),
            "Salary (Est.)":   meta.get("salary_estimate", "-"),
            "Deadline":        meta.get("deadline", "-"),
        })
    salary_df = pd.DataFrame(rows).sort_values(["Department", "Role"])
    st.dataframe(salary_df, use_container_width=True, hide_index=True)
except Exception as e:
    st.error(f"Failed to load salary benchmarks: {e}")

st.markdown('<hr class="divider" style="border-top:1px solid ' + card_bdr + '">', unsafe_allow_html=True)

# ── FEAT-04: Re-rank Job ───────────────────────────────────────────────────────
st.markdown(
    f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Re-rank a Job</div>',
    unsafe_allow_html=True,
)
st.caption("Re-sends every candidate for the selected job through the AI scorer. "
           "Useful after changing scoring weights, switching the LLM model, or updating department profiles.")

try:
    _conn_rr   = get_conn()
    _job_rows  = fetch_all_jobs(_conn_rr)
    _labels_rr = _job_rows["job_label"].tolist() if not _job_rows.empty else []
except Exception as _err:
    _labels_rr = []
    st.warning(f"Could not load job list: {_err}")

if not _labels_rr:
    st.info("No jobs are currently registered.")
else:
    rr_col1, rr_col2 = st.columns([3, 1])
    with rr_col1:
        rerank_job = st.selectbox(
            "Job to Re-rank", _labels_rr, key="rerank_job_select",
        )
    with rr_col2:
        normalise = st.checkbox(
            "Normalise after",
            value=True,
            help="Run percentile rescaling pass after ranking completes.",
        )

    if st.button("🔄  Start Re-rank", type="primary"):
        try:
            dept = get_job_department(_conn_rr, rerank_job) or ""
            proc, log_path = _spawn_rerank(rerank_job, dept, normalise)
            try:
                update_job_status(rerank_job, "Processing")
            except Exception:
                pass
            st.session_state["rerank_pid"] = proc.pid
            st.success(
                f"✓ Re-rank started for **{rerank_job}** (PID {proc.pid}). "
                f"Log: `{log_path}`"
            )
            st.markdown(
                "Open the **Processing Status** page to monitor live progress."
            )
            st.page_link("pages/4_Processing_Status.py",
                         label="⏳  Open Processing Status →")
        except Exception as e:
            st.error(f"Failed to start re-rank: {e}")

st.markdown('<hr class="divider" style="border-top:1px solid ' + card_bdr + '">', unsafe_allow_html=True)
st.markdown(f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Scoring Schema</div>', unsafe_allow_html=True)
st.markdown(f"""
    <div style="background:{card_bg};border:1px solid {card_bdr};border-radius:8px;padding:1rem 1.2rem;">
        <div style="font-size:0.88rem;color:{txt_col} !important;line-height:2.1;">
            <b>Model:</b> qwen3:8b-q4_K_M — local Ollama inference, no cloud exposure<br>
            <b>Dimensions:</b> AI/ML · ERP · Automation · Leadership · Education · Overall<br>
            <b>Verdicts:</b> Shortlist / Maybe / Reject — holistic LLM judgment, not score threshold<br>
            <b>BDJobs score:</b> Shown for reference only — not used in AI ranking<br>
            <b>All evaluations</b> stored with full reasoning for HR audit trail
        </div>
    </div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# RANKING HEALTH — live error dashboard
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("<br>", unsafe_allow_html=True)
st.markdown(
    f"<div class='section-hd' style='font-size:1.2rem;color:{txt_col} !important;'>"
    f"Ranking Health</div>",
    unsafe_allow_html=True,
)

conn_health = get_conn()
with conn_health.cursor() as cur:
    cur.execute("""
        SELECT
            COUNT(*) AS total_failed,
            COUNT(*) FILTER (WHERE rank_error ILIKE '%Expecting value: line 1 column 1%') AS empty_failures,
            COUNT(*) FILTER (WHERE rank_error ILIKE '%timeout%') AS timeout_failures,
            COUNT(*) FILTER (WHERE rank_error ILIKE '%PDF extraction%') AS pdf_failures,
            COUNT(*) FILTER (WHERE rank_error ILIKE '%encoding%') AS encoding_failures,
            COUNT(DISTINCT job_label) AS affected_jobs,
            MIN(ranked_at) AS oldest_failure,
            MAX(ranked_at) AS newest_failure
        FROM candidates
        WHERE rank_error IS NOT NULL
          AND overall_score IS NULL
    """)
    row = cur.fetchone()

total_failed, empty, timeout, pdf_err, enc, jobs, oldest, newest = row
total_failed = total_failed or 0
empty = empty or 0
timeout = timeout or 0
pdf_err = pdf_err or 0
enc = enc or 0
jobs = jobs or 0

if total_failed == 0:
    st.success("✅ All candidates ranked successfully. No failures detected.")
else:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Failed Candidates", total_failed)
    c2.metric("Empty Responses", empty)
    c3.metric("Affected Jobs", jobs)
    c4.metric("PDF Failures", pdf_err)

    st.markdown("<br>", unsafe_allow_html=True)

    # Action buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Re-rank All Failed", use_container_width=True, type="primary"):
            with conn_health.cursor() as cur:
                cur.execute("""
                    UPDATE candidates
                    SET rank_error = NULL, ranked_at = NULL
                    WHERE rank_error IS NOT NULL AND overall_score IS NULL
                """)
                conn_health.commit()
            st.success(f"Cleared {total_failed} failed candidates. Re-run ranker.py for each job.")

    with col2:
        if st.button("📋 View Error Log", use_container_width=True, type="secondary"):
            with conn_health.cursor() as cur:
                cur.execute("""
                    SELECT apply_id, job_label, LEFT(rank_error, 120) AS err, ranked_at
                    FROM candidates
                    WHERE rank_error IS NOT NULL AND overall_score IS NULL
                    ORDER BY ranked_at DESC
                    LIMIT 50
                """)
                rows = cur.fetchall()
                if rows:
                    df_err = pd.DataFrame(rows, columns=["Apply ID", "Job", "Error", "Time"])
                    st.dataframe(df_err, use_container_width=True, hide_index=True)
                else:
                    st.info("No errors to display.")

    if total_failed > 0:
        st.caption(
            f"Oldest failure: {oldest.strftime('%Y-%m-%d %H:%M') if oldest else 'N/A'}  ·  "
            f"Newest failure: {newest.strftime('%Y-%m-%d %H:%M') if newest else 'N/A'}"
        )

conn_health.close()


# ═══════════════════════════════════════════════════════════════════════════════
# ASSOCIATE CANDIDATES WITH JOB — Fix job_label mapping for department candidates
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("<br>", unsafe_allow_html=True)
st.markdown(
    f"<div class='section-hd' style='font-size:1.2rem;color:{txt_col} !important;'>"
    f"Associate Candidates with Job</div>",
    unsafe_allow_html=True,
)
st.caption(
    "Use this to reassign all candidates in a department to a specific job from BDJobs Registry. "
    "This fixes cases where candidates were imported with generic job_labels (e.g., 'bdjobs_1463602') "
    "but should be associated with a proper job role (e.g., 'Delivery-Manager')."
)

# Get list of departments from job registry
dept_options = sorted(set(meta.get("department", "") for meta in BDJOBS_JOB_REGISTRY.values() if meta.get("department")))

assoc_col1, assoc_col2 = st.columns(2)
with assoc_col1:
    selected_dept = st.selectbox("Department", dept_options, key="assoc_dept")
with assoc_col2:
    # Filter jobs for selected department
    dept_jobs = [(label, meta.get("job_title", label)) for label, meta in BDJOBS_JOB_REGISTRY.items() if meta.get("department") == selected_dept]
    job_options = [f"{label} :: {title}" for label, title in dept_jobs]
    selected_job_opt = st.selectbox("Target Job", job_options, key="assoc_job")
    selected_job_label = selected_job_opt.split(" :: ")[0] if selected_job_opt else None

if st.button("🔗 Associate Candidates", type="primary", use_container_width=True):
    if selected_dept and selected_job_label:
        try:
            updated_count = associate_candidates_with_job(selected_dept, selected_job_label)
            st.success(
                f"✅ Successfully associated **{updated_count}** candidates from **{selected_dept}** "
                f"with job **{selected_job_label}**."
            )
            st.info("Refresh the Department Rankings page to see the updated job associations.")
        except Exception as e:
            st.error(f"Failed to associate candidates: {e}")
    else:
        st.error("Please select both a department and a target job.")

st.markdown('<hr class="divider" style="border-top:1px solid ' + card_bdr + '">', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# BDJobs CREDENTIALS — Stored securely in PostgreSQL
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("<br>", unsafe_allow_html=True)
st.markdown(
    f"<div class='section-hd' style='font-size:1.2rem;color:{txt_col} !important;'>"
    f"BDJobs Credentials</div>",
    unsafe_allow_html=True,
)

conn_bdj = get_conn()
creds = get_bdjobs_credentials(conn_bdj)

if creds:
    st.success(f"✅ Credentials stored for: **{creds['username']}**")
    st.caption("Password is obfuscated (base64) in the database. To update, re-enter below.")
else:
    st.warning("⚠️ No BDJobs credentials stored. Enter them below to enable auto-login.")

with st.form("bdjobs_creds_form"):
    c1, c2 = st.columns(2)
    default_user = creds["username"] if creds else ""
    default_pwd  = creds["password"] if creds else ""
    bdj_user = c1.text_input("BDJobs Username", value=default_user)
    bdj_pwd  = c2.text_input("BDJobs Password", value=default_pwd, type="password")
    submitted = st.form_submit_button("💾 Save Credentials", use_container_width=True, type="primary")
    if submitted:
        if bdj_user.strip() and bdj_pwd.strip():
            save_bdjobs_credentials(conn_bdj, bdj_user.strip(), bdj_pwd.strip())
            st.success("Credentials saved.")
            st.rerun()
        else:
            st.error("Both fields are required.")

