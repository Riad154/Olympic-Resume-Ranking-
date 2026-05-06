"""
pages/1_New_Job.py — JD intake form. Creates job record and triggers ranker.
"""

import os
import re
import subprocess
import time
import json
import streamlit as st
from datetime import datetime
from pathlib import Path
from db import (
    render_sidebar,
    get_conn, create_job, ingest_metadata, update_job_status,
    get_css, init_theme, build_prompt_preview,
    DEPARTMENTS, EXPERIENCE_OPTIONS, EDUCATION_OPTIONS,
    COMMON_SKILLS, SKILL_DOMAINS, RED_FLAG_PRESETS, RESUMES_BASE, RANKER_PATH, VENV_PYTHON,
)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_LOG_DIR      = _PROJECT_ROOT / "_dl_logs"
_LOG_DIR.mkdir(exist_ok=True)


def _spawn_ranker(label: str, jd_file: str, department: str):
    """Launch ranker.py as a background subprocess; return (proc, log_path)."""
    cmd = [VENV_PYTHON, RANKER_PATH, "--job", label]
    if jd_file:
        cmd += ["--jd", jd_file]
    if department:
        cmd += ["--department", department]
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = _LOG_DIR / f"rank_{label}_{ts}.log"
    log_fp   = open(log_path, "w", encoding="utf-8")
    flags    = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
    proc     = subprocess.Popen(
        cmd, cwd=str(_PROJECT_ROOT),
        stdout=log_fp, stderr=subprocess.STDOUT,
        creationflags=flags,
    )
    return proc, str(log_path)


def _is_process_running(pid: int) -> bool:
    """Check if a process with given PID is still running."""
    try:
        import psutil
        return psutil.Process(pid).is_running()
    except Exception:
        return False


def _read_log_tail(log_path: str, lines: int = 20) -> str:
    """Read the last N lines from a log file."""
    try:
        if not os.path.exists(log_path):
            return ""
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()
            return "".join(all_lines[-lines:])
    except Exception:
        return ""


def _read_ranker_progress(log_path: str) -> dict:
    """Parse ranker log to extract progress statistics."""
    try:
        if not os.path.exists(log_path):
            return {"processed": 0, "failed": 0}
        
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        
        # Count OK and FAIL indicators
        processed = content.count("  OK  ") + content.count("RTRY")
        failed = content.count(" FAIL ") + content.count("[ERROR]")
        
        # Also check for JSON progress lines if they exist
        for line in content.split("\n"):
            if "processed" in line and "failed" in line:
                try:
                    # Try to extract from JSON-like format
                    if "{" in line and "}" in line:
                        json_part = line[line.find("{"):line.rfind("}")+1]
                        data = json.loads(json_part)
                        if "processed" in data:
                            processed = max(processed, data.get("processed", 0))
                        if "failed" in data:
                            failed = max(failed, data.get("failed", 0))
                except Exception:
                    pass
        
        return {"processed": processed, "failed": failed}
    except Exception:
        return {"processed": 0, "failed": 0}

st.set_page_config(
    page_title="New Job Posting — HR Intelligence",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_theme()
st.markdown(get_css(), unsafe_allow_html=True)

if "skill_domain_picker" not in st.session_state:
    st.session_state["skill_domain_picker"] = "— Select a domain —"

# ── Sidebar
render_sidebar()

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown('<div class="page-title">New Job Posting</div>', unsafe_allow_html=True)
st.markdown('<div class="page-sub">Submit a job description for AI-powered candidate ranking</div>', unsafe_allow_html=True)
st.markdown('<hr class="divider">', unsafe_allow_html=True)

# ── Available job folders ──────────────────────────────────────────────────────
available_folders = []
if os.path.isdir(RESUMES_BASE):
    available_folders = sorted([
        d for d in os.listdir(RESUMES_BASE)
        if os.path.isdir(os.path.join(RESUMES_BASE, d))
    ], reverse=True)

# ── Form ───────────────────────────────────────────────────────────────────────
col_form, col_help = st.columns([3, 1], gap="large")

with col_form:
    # ── Section 1: Job basics
    st.markdown('<div class="section-hd">Job Information</div>', unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        job_title = st.text_input(
            "Job Title *",
            placeholder="e.g. Sr. Executive — AI & Digital Transformation",
        )
    with col_b:
        department = st.selectbox("Department", [""] + DEPARTMENTS)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 2: JD text
    st.markdown('<div class="section-hd">Job Description</div>', unsafe_allow_html=True)
    jd_text = st.text_area(
        "Full Job Description",
        placeholder="Paste the complete job description here. The AI will extract requirements automatically.",
        height=200,
        label_visibility="collapsed",
    )

    st.markdown("<br>", unsafe_allow_html=True)

# ── Section 3: Requirements
    st.markdown('<div class="section-hd">Candidate Requirements</div>', unsafe_allow_html=True)
    col_c, col_d = st.columns(2)
    with col_c:
        min_experience = st.selectbox("Minimum Experience", EXPERIENCE_OPTIONS)
    with col_d:
        education_req = st.selectbox("Education Requirement", EDUCATION_OPTIONS)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Skill picker
    st.markdown('<div class="section-hd">Required Skills</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hint-text" style="margin-bottom:0.8rem;">Choose a domain, click skills to add them, then switch domains to add more.</div>',
        unsafe_allow_html=True,
    )

    # Session state for accumulated skills
    if "picked_skills" not in st.session_state:
        st.session_state["picked_skills"] = []

    # Domain selector
    domain_options = ["— Select a domain —"] + list(SKILL_DOMAINS.keys())
    selected_domain = st.selectbox(
        "Skill Domain",
        domain_options,
        key="skill_domain_picker",
        label_visibility="collapsed",
    )

    # Skill buttons for chosen domain
    if selected_domain and selected_domain != "— Select a domain —":
        domain_skills = SKILL_DOMAINS[selected_domain]
        st.markdown(
            f'<div style="font-size:0.78rem;color:#64748B;margin-bottom:0.5rem;">'
            f'Click to add · {selected_domain}</div>',
            unsafe_allow_html=True,
        )
        # Render skills as a flowing set of buttons
        cols = st.columns(4)
        for i, skill in enumerate(domain_skills):
            already = skill in st.session_state["picked_skills"]
            with cols[i % 4]:
                label = f"✓ {skill}" if already else skill
                btn_style = "primary" if already else "secondary"
                if st.button(label, key=f"skill_btn_{skill}", type=btn_style, use_container_width=True):
                    if already:
                        st.session_state["picked_skills"].remove(skill)
                    else:
                        st.session_state["picked_skills"].append(skill)
                    st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # Also allow free-text custom skills
    custom_skills_raw = st.text_input(
        "Additional Skills (comma-separated)",
        placeholder="e.g. BGMEA Compliance, Halal Certification, HACCP",
        key="custom_skills_input",
    )
    custom_skills = [s.strip() for s in custom_skills_raw.split(",") if s.strip()] if custom_skills_raw else []

    # Merge picked + custom, deduplicated
    required_skills = list(dict.fromkeys(st.session_state["picked_skills"] + custom_skills))

    # Show current selection summary
    if required_skills:
        pills = "".join(
            f'<span style="display:inline-block;background:#FEE2E2;color:#991B1B;'
            f'border-radius:5px;padding:3px 10px;font-size:0.78rem;font-weight:500;'
            f'margin:2px 3px;">{s}</span>'
            for s in required_skills
        )
        st.markdown(
            f'<div style="margin-bottom:0.5rem;"><span style="font-size:0.75rem;'
            f'color:#64748B;font-weight:600;text-transform:uppercase;letter-spacing:0.1em;">'
            f'{len(required_skills)} skills selected</span></div>'
            f'<div style="padding:0.6rem;background:#FFF8F8;border:1px solid #FEE2E2;'
            f'border-radius:8px;margin-bottom:0.5rem;">{pills}</div>',
            unsafe_allow_html=True,
        )
        if st.button("✕  Clear all skills", type="secondary", key="clear_skills"):
            st.session_state["picked_skills"] = []
            st.rerun()
    else:
        st.markdown(
            '<div class="hint-text">No skills selected yet.</div>',
            unsafe_allow_html=True,
        )

    # ── Section 4: Scoring weights
    st.markdown('<div class="section-hd">Scoring Weights</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hint-text" style="margin-bottom:0.8rem;">Adjust how much each of the five dimensions influences the overall AI score. All five must total 100%.</div>',
        unsafe_allow_html=True,
    )

    if "w_skills"     not in st.session_state: st.session_state["w_skills"]     = 50
    if "w_exp"        not in st.session_state: st.session_state["w_exp"]        = 30
    if "w_edu"        not in st.session_state: st.session_state["w_edu"]        = 10
    if "w_leadership" not in st.session_state: st.session_state["w_leadership"] = 5
    if "w_culture"    not in st.session_state: st.session_state["w_culture"]    = 5

    # FEAT-03: per-department weight presets. The user can apply optimal
    # defaults for the selected department with one click, then fine-tune.
    DEPT_WEIGHT_PRESETS = {
        "AI & Digital Transformation":           {"skills": 55, "exp": 25, "edu": 10, "leadership": 5,  "culture": 5},
        "Brand & Marketing":                     {"skills": 50, "exp": 25, "edu": 10, "leadership": 10, "culture": 5},
        "Marketing Designer":                    {"skills": 60, "exp": 25, "edu": 5,  "leadership": 5,  "culture": 5},
        "Software Designer":                     {"skills": 60, "exp": 25, "edu": 5,  "leadership": 5,  "culture": 5},
        "Finance and Accounts":                  {"skills": 35, "exp": 30, "edu": 25, "leadership": 5,  "culture": 5},
        "Sales":                                 {"skills": 40, "exp": 35, "edu": 5,  "leadership": 15, "culture": 5},
        "Field Force":                           {"skills": 35, "exp": 40, "edu": 5,  "leadership": 10, "culture": 10},
        "Institutional Sales":                   {"skills": 40, "exp": 35, "edu": 10, "leadership": 10, "culture": 5},
        "Human Resource (HR)":                   {"skills": 35, "exp": 30, "edu": 20, "leadership": 10, "culture": 5},
        "Engineering":                           {"skills": 50, "exp": 30, "edu": 15, "leadership": 5,  "culture": 0},
        "Production":                            {"skills": 40, "exp": 35, "edu": 10, "leadership": 10, "culture": 5},
        "Supply Chain":                          {"skills": 40, "exp": 35, "edu": 10, "leadership": 10, "culture": 5},
        "Quality Assurance Department (QAD)":    {"skills": 45, "exp": 30, "edu": 20, "leadership": 5,  "culture": 0},
        "Internal Audit":                        {"skills": 35, "exp": 30, "edu": 25, "leadership": 5,  "culture": 5},
        "External Audit":                        {"skills": 35, "exp": 30, "edu": 25, "leadership": 5,  "culture": 5},
        "VAT / VAT & Delivery":                  {"skills": 40, "exp": 30, "edu": 20, "leadership": 5,  "culture": 5},
        "ERP - SAP":                             {"skills": 55, "exp": 30, "edu": 10, "leadership": 5,  "culture": 0},
        "Information & Communication Technology (ICT)": {"skills": 50, "exp": 30, "edu": 10, "leadership": 5, "culture": 5},
        "Management Information System (MIS)":   {"skills": 50, "exp": 30, "edu": 10, "leadership": 5,  "culture": 5},
        "Operations":                            {"skills": 40, "exp": 35, "edu": 10, "leadership": 10, "culture": 5},
        "Corporate Affairs":                     {"skills": 35, "exp": 30, "edu": 25, "leadership": 5,  "culture": 5},
        "_default":                              {"skills": 50, "exp": 30, "edu": 10, "leadership": 5,  "culture": 5},
    }
    if department:
        preset = DEPT_WEIGHT_PRESETS.get(department, DEPT_WEIGHT_PRESETS["_default"])
        if st.button(
            f"💡  Apply Recommended Weights for {department}",
            type="secondary",
            use_container_width=True,
            help=(
                f"Skills {preset['skills']} · Exp {preset['exp']} · Edu {preset['edu']} · "
                f"Leadership {preset['leadership']} · Culture {preset['culture']}"
            ),
        ):
            st.session_state["w_skills"]     = preset["skills"]
            st.session_state["w_exp"]        = preset["exp"]
            st.session_state["w_edu"]        = preset["edu"]
            st.session_state["w_leadership"] = preset["leadership"]
            st.session_state["w_culture"]    = preset["culture"]
            st.rerun()

    col_w1, col_w2, col_w3 = st.columns(3)
    with col_w1:
        w_skills = st.slider("Skills",      0, 100, st.session_state["w_skills"], 5, key="sl_skills")
    with col_w2:
        w_exp    = st.slider("Experience",  0, 100, st.session_state["w_exp"],    5, key="sl_exp")
    with col_w3:
        w_edu    = st.slider("Education",   0, 100, st.session_state["w_edu"],    5, key="sl_edu")

    col_w4, col_w5 = st.columns(2)
    with col_w4:
        w_leadership = st.slider("Leadership",  0, 100, st.session_state["w_leadership"], 5, key="sl_leadership")
    with col_w5:
        w_culture    = st.slider("Culture Fit", 0, 100, st.session_state["w_culture"],    5, key="sl_culture")

    total_w = w_skills + w_exp + w_edu + w_leadership + w_culture
    if total_w != 100:
        st.warning(f"Weights total {total_w}% — must equal 100%. Adjust the sliders.")
    else:
        st.success("✓ Weights sum to 100%")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 5: Red flags
    st.markdown('<div class="section-hd">Red Flags</div>', unsafe_allow_html=True)
    red_flags = st.multiselect(
        "Flag these patterns in candidates",
        RED_FLAG_PRESETS,
        label_visibility="collapsed",
    )
    custom_flags_raw = st.text_input(
        "Additional red flags (comma-separated)",
        placeholder="e.g. No pharmaceutical background",
    )
    if custom_flags_raw:
        custom_flags = [f.strip() for f in custom_flags_raw.split(",") if f.strip()]
        red_flags = red_flags + custom_flags

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 6: Interviewer notes
    st.markdown('<div class="section-hd">Interviewer Notes</div>', unsafe_allow_html=True)
    interviewer_notes = st.text_area(
        "Additional context for the AI",
        placeholder="Any specific context, priorities, or preferences for this hire...",
        height=100,
        label_visibility="collapsed",
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 7: Resume source
    st.markdown('<div class="section-hd">Resume Source</div>', unsafe_allow_html=True)

    if available_folders:
        source_folder = st.selectbox(
            "Select downloaded resume folder",
            available_folders,
            help="These are folders found in your downloaded_resumes directory.",
        )
    else:
        source_folder = st.text_input(
            "Resume folder name",
            placeholder="e.g. AIDigital_Transformation-SrExecutive",
        )
        st.caption(f"Folder will be looked up in: {RESUMES_BASE}")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Buttons
    col_prev, col_submit = st.columns([1, 2])

    with col_prev:
        preview_clicked = st.button("👁  Preview Prompt", type="secondary", use_container_width=True)

    with col_submit:
        submit_clicked = st.button("🚀  Start Ranking Job", type="primary", use_container_width=True,
                                   disabled=(not job_title or not source_folder or total_w != 100))

# ── Help panel ─────────────────────────────────────────────────────────────────
with col_help:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-hd">How it works</div>', unsafe_allow_html=True)

    is_day = st.session_state.get("day_mode", True)
    card_bg = "#FFFFFF" if is_day else "#242736"
    card_border = "#E2E8F0" if is_day else "#2D3148"
    text_col = "#1E293B" if is_day else "#E2E8F0"
    sub_col  = "#64748B" if is_day else "#64748B"

    steps = [
        ("1", "Fill in job details", "Title and JD text help the AI understand exactly what you're hiring for."),
        ("2", "Set weights", "Prioritise skills, experience, or education based on role requirements."),
        ("3", "Choose flags", "Red flags help the AI surface risk patterns."),
        ("4", "Submit", "The AI processes each candidate and ranks them. Takes ~14 seconds per candidate."),
        ("5", "Review results", "Go to Ranking Results to view shortlist, filter, and export to Excel."),
    ]
    for num, title, desc in steps:
        st.markdown(f"""
            <div style="background:{card_bg};border:1px solid {card_border};border-radius:8px;padding:0.9rem 1rem;margin-bottom:0.6rem;">
                <div style="display:flex;gap:0.6rem;align-items:flex-start;">
                    <div style="background:#1E3A5F;color:#FFFFFF !important;border-radius:50%;width:22px;height:22px;
                                display:flex;align-items:center;justify-content:center;
                                font-size:0.7rem;font-weight:700;flex-shrink:0;margin-top:1px;">{num}</div>
                    <div>
                        <div style="font-size:0.84rem;font-weight:600;color:{text_col} !important;">{title}</div>
                        <div style="font-size:0.78rem;color:{sub_col} !important;margin-top:2px;line-height:1.4;">{desc}</div>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-hd">Scoring dimensions</div>', unsafe_allow_html=True)
    dims = [
        ("AI/ML Score",      "Hands-on AI/ML tools and deployments"),
        ("ERP Score",        "SAP, Oracle, Odoo experience"),
        ("Automation Score", "RPA, scripting, workflow tools"),
        ("Leadership Score", "Team and project ownership"),
        ("Education Score",  "Degree relevance and quality"),
    ]
    for dim, desc in dims:
        st.markdown(f"""
            <div style="margin-bottom:0.4rem;">
                <span style="font-size:0.8rem;font-weight:600;color:{'#1E3A5F' if is_day else '#93C5FD'} !important;">{dim}</span>
                <span style="font-size:0.78rem;color:{sub_col} !important;"> — {desc}</span>
            </div>
        """, unsafe_allow_html=True)

# ── Preview prompt modal ───────────────────────────────────────────────────────
if preview_clicked:
    job_data = {
        "job_title": job_title, "department": department, "jd_text": jd_text,
        "required_skills": required_skills, "red_flags": red_flags,
        "min_experience": min_experience, "education_req": education_req,
        "weight_skills": w_skills, "weight_exp": w_exp, "weight_edu": w_edu,
        "weight_leadership": w_leadership, "weight_culture": w_culture,
        "interviewer_notes": interviewer_notes,
    }
    with st.expander("📄 AI Prompt Preview", expanded=True):
        st.code(build_prompt_preview(job_data), language="text")

# ── Submit ─────────────────────────────────────────────────────────────────────
if submit_clicked:
    if not job_title:
        st.error("Job title is required.")
    elif not source_folder:
        st.error("Please select a resume source folder.")
    elif total_w != 100:
        st.error("Scoring weights must sum to 100%.")
    else:
        # Build job label from folder name
        job_label = source_folder

        # Check metadata CSV
        meta_csv = os.path.join(RESUMES_BASE, job_label, f"{job_label}_metadata.csv")

        job_data = {
            "job_label": job_label, "job_title": job_title,
            "department": department, "jd_text": jd_text,
            "required_skills": required_skills, "red_flags": red_flags,
            "min_experience": min_experience, "education_req": education_req,
            "weight_skills": w_skills, "weight_exp": w_exp, "weight_edu": w_edu,
            "weight_leadership": w_leadership, "weight_culture": w_culture,
            "interviewer_notes": interviewer_notes,
        }

        with st.spinner("Creating job record..."):
            create_job(job_data)

        # Ingest metadata
        with st.spinner("Ingesting candidate metadata from CSV..."):
            updated, skipped = ingest_metadata(job_label, meta_csv)

        if updated > 0:
            st.success(f"✓ Metadata loaded: {updated} candidates imported.")
        else:
            st.warning("No metadata CSV found — names and contact info will be unavailable until ranker runs.")

        # Build JD file for ranker
        jd_file = os.path.join(RESUMES_BASE, job_label, "_jd_prompt.txt")
        if jd_text or required_skills or interviewer_notes:
            with open(jd_file, "w", encoding="utf-8") as f:
                if jd_text:
                    f.write(jd_text + "\n\n")
                if required_skills:
                    f.write("Required Skills: " + ", ".join(required_skills) + "\n")
                if red_flags:
                    f.write("Watch for: " + ", ".join(red_flags) + "\n")
                if interviewer_notes:
                    f.write("\nAdditional Notes:\n" + interviewer_notes + "\n")
            jd_arg = ["--jd", jd_file]
        else:
            jd_arg = []

        # Estimate time
        txt_dir   = os.path.join(RESUMES_BASE, job_label, "profiles_txt")
        n_resumes = len([f for f in os.listdir(txt_dir) if f.endswith(".txt")]) if os.path.isdir(txt_dir) else 0
        est_mins  = round(n_resumes * 14 / 60)

        st.markdown("---")
        st.success(f"""
            ✅ **Job created successfully!**
            - Job ID: `{job_label}`
            - Candidates to process: **{n_resumes}**
            - Estimated time: **~{est_mins} minutes**
        """)

        # Launch the ranker in the background -- no terminal needed.
        ranker_started = False
        proc = None
        log_path = None
        try:
            proc, log_path = _spawn_ranker(
                job_label,
                jd_file if jd_arg else "",
                department or "",
            )
            ranker_started = True
            # Store in session state for status tracking
            st.session_state[f"ranker_{job_label}_pid"] = proc.pid
            st.session_state[f"ranker_{job_label}_log"] = log_path
            st.session_state[f"ranker_{job_label}_start"] = datetime.now().isoformat()
            st.session_state[f"ranker_{job_label}_status"] = "running"
            st.session_state[f"ranker_{job_label}_total"] = n_resumes
            st.session_state[f"ranker_{job_label}_processed"] = 0
        except Exception as e:
            st.error(f"❌ Failed to start ranker: {e}")
            st.caption("You can still launch it manually:")
            cmd = f'python ranker.py --job "{job_label}"'
            if jd_arg:
                cmd += f' --jd "{jd_file}"'
            if department:
                cmd += f' --department "{department}"'
            st.code(cmd, language="bash")

        # ═══════════════════════════════════════════════════════════════════════
        # PROCESSING STATUS & RANKER MONITORING
        # ═══════════════════════════════════════════════════════════════════════
        if ranker_started and proc:
            st.markdown("---")
            st.markdown("### 📊 Processing Status")
            
            # Status container for live updates
            status_container = st.container()
            
            with status_container:
                # Get current progress from log file
                progress_data = _read_ranker_progress(log_path)
                processed = progress_data.get("processed", 0)
                failed = progress_data.get("failed", 0)
                total = n_resumes
                
                # Calculate percentages
                if total > 0:
                    success_pct = (processed / total) * 100
                    failed_pct = (failed / total) * 100
                    remaining = total - processed - failed
                else:
                    success_pct = 0
                    failed_pct = 0
                    remaining = 0
                
                # Progress metrics
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("✅ Processed", f"{processed}/{total}")
                col2.metric("❌ Failed", failed)
                col3.metric("⏳ Remaining", remaining)
                
                # ETA calculation
                if processed > 0 and total > 0:
                    elapsed = (datetime.now() - datetime.fromisoformat(st.session_state.get(f"ranker_{job_label}_start", datetime.now().isoformat()))).total_seconds()
                    avg_time = elapsed / processed
                    eta_seconds = avg_time * remaining
                    eta_mins = int(eta_seconds / 60)
                    eta_secs = int(eta_seconds % 60)
                    col4.metric("⏱️ ETA", f"{eta_mins}m {eta_secs}s")
                else:
                    col4.metric("⏱️ ETA", "Calculating...")
                
                # Progress bar
                if total > 0:
                    progress = (processed + failed) / total
                    st.progress(min(progress, 0.99), text=f"Processing... {int(progress*100)}% complete")
                
                # Status indicators
                status_cols = st.columns(3)
                with status_cols[0]:
                    st.info(f"🖥️ **Ranker PID:** `{proc.pid}`")
                with status_cols[1]:
                    if _is_process_running(proc.pid):
                        st.success("🟢 **Status:** Running")
                    else:
                        st.warning("🟡 **Status:** Completed or Stopped")
                with status_cols[2]:
                    st.caption(f"📄 **Log:** `{Path(log_path).name}`")
                
                # Live log viewer (last 20 lines)
                with st.expander("📋 Live Ranker Log (Last 20 lines)", expanded=False):
                    log_content = _read_log_tail(log_path, lines=20)
                    st.code(log_content or "(Log is empty - ranker just started)", language="text")
                
                # Background processing controls
                st.markdown("#### 🎛️ Background Processing Controls")
                ctrl_col1, ctrl_col2, ctrl_col3 = st.columns(3)
                
                with ctrl_col1:
                    if st.button("🛑 Stop Ranker", type="secondary", key=f"stop_{job_label}", use_container_width=True):
                        try:
                            import psutil
                            parent = psutil.Process(proc.pid)
                            for child in parent.children(recursive=True):
                                child.terminate()
                            parent.terminate()
                            st.session_state[f"ranker_{job_label}_status"] = "stopped"
                            st.warning("Ranker stopped by user.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to stop: {e}")
                
                with ctrl_col2:
                    if st.button("🔄 Refresh Status", type="secondary", key=f"refresh_{job_label}", use_container_width=True):
                        st.rerun()
                
                with ctrl_col3:
                    if st.button("📊 View Full Log", type="secondary", key=f"viewlog_{job_label}", use_container_width=True):
                        st.session_state["view_full_log"] = log_path
                        st.rerun()
                
                # Show full log if requested
                if st.session_state.get("view_full_log") == log_path:
                    with st.expander("📄 Full Ranker Log", expanded=True):
                        full_log = _read_log_tail(log_path, lines=200)
                        st.code(full_log or "(No log content yet)", language="text")
                        if st.button("Close Full Log", key=f"close_log_{job_label}"):
                            st.session_state.pop("view_full_log", None)
                            st.rerun()
            
            # Auto-refresh if still running
            if _is_process_running(proc.pid):
                st.caption("⏱️ Status auto-refreshes every 5 seconds...")
                time.sleep(5)
                st.rerun()
        
        # Navigate to rankings
        st.markdown("---")
        if st.button("Go to Ranking Results →", type="primary", use_container_width=True):
            st.session_state["selected_job"] = job_label
            st.switch_page("pages/2_Job_Rankings.py")
