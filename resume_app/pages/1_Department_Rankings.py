"""
pages/1_Department_Rankings.py — Primary HR interface.

Top-level navigation by department, with per-department job sub-tabs and a
ranked-candidate table that numbers applicants #1..#N within the selected
scope.  A candidate detail panel sits below the table.
"""

from __future__ import annotations

import base64
import os
from datetime import datetime

import pandas as pd
import streamlit as st

from db import (
    get_conn,
    fetch_departments, fetch_jobs_by_department, fetch_candidates_by_department,
    to_excel, save_hr_override, delete_candidate,
    get_css, init_theme, render_sidebar,
    VERDICT_CFG, SCORE_DIMS,
    BDJOBS_JOB_REGISTRY,
    get_active_processing, render_processing_banner,
)

# ── Page chrome ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Department Rankings — HR Intelligence",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)
init_theme()
st.markdown(get_css(), unsafe_allow_html=True)

# Force dataframe text visibility regardless of Streamlit theme
st.markdown("""
<style>
[data-testid="stDataFrame"] [data-testid="glideDataEditor"] canvas {
    color-scheme: light !important;
}
div[data-testid="stDataFrame"] { border-radius: 8px !important; overflow: hidden; }
.score-ring-bg { fill:none; stroke:#E2E8F0; stroke-width:8; }
.score-ring-fill { fill:none; stroke-width:8; stroke-linecap:round; transform:rotate(-90deg); transform-origin:50% 50%; transition:stroke-dashoffset 0.6s ease; }
.dim-card { background:#ffffff; border:1px solid #E2E8F0; border-radius:8px; padding:0.7rem 0.9rem; text-align:center; }
.dim-label { font-size:0.65rem; font-weight:600; text-transform:uppercase; letter-spacing:0.08em; color:#64748B; margin-bottom:4px; }
.dim-score { font-size:1.4rem; font-weight:700; line-height:1.1; }
.dim-bar-track { height:4px; background:#E2E8F0; border-radius:2px; margin-top:6px; overflow:hidden; }
.dim-bar-fill { height:100%; border-radius:2px; transition:width 0.4s ease; }
.strength-item { display:flex; align-items:flex-start; gap:8px; padding:6px 8px; background:#F0FDF4; border-left:3px solid #16A34A; border-radius:0 6px 6px 0; margin-bottom:6px; font-size:0.82rem; color:#14532D; }
.gap-item { display:flex; align-items:flex-start; gap:8px; padding:6px 8px; background:#FFFBEB; border-left:3px solid #D97706; border-radius:0 6px 6px 0; margin-bottom:6px; font-size:0.82rem; color:#78350F; }
.timeline-item { position:relative; padding-left:16px; padding-bottom:12px; border-left:2px solid #E2E8F0; margin-left:6px; }
.timeline-item::before { content:''; position:absolute; left:-5px; top:2px; width:8px; height:8px; border-radius:50%; background:#C8102E; }
</style>
""", unsafe_allow_html=True)

render_sidebar()

# ── DB ─────────────────────────────────────────────────────────────────────────
try:
    conn = get_conn()
except Exception as e:
    st.error(f"Database connection failed: {e}")
    st.stop()

dept_rows = fetch_departments(conn)

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown('<div class="page-title">Department Rankings</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="page-sub">Navigate by department · Rankings computed with HR-configured weights</div>',
    unsafe_allow_html=True,
)
st.markdown('<hr class="divider">', unsafe_allow_html=True)

# ── Live processing banner + auto-refresh toggle ──────────────────────────────
_active_jobs = [r for r in get_active_processing() if r["is_running"]]
render_processing_banner()
if _active_jobs:
    with st.sidebar:
        _auto_refresh_dept = st.checkbox(
            "🔄 Auto-refresh (5s)", value=True,
            help="Live-refresh while ranking is in progress.",
            key="dept_auto_refresh",
        )
else:
    _auto_refresh_dept = False

if not dept_rows:
    if _active_jobs:
        st.info("⏳ Ranking is in progress — candidates will appear here as they are processed.")
    else:
        st.info(
            "No ranked candidates yet.  Use **New Job Posting** to register a job, "
            "then run `ranker.py --job <label> --department <dept>` to populate rankings."
        )
    if _auto_refresh_dept:
        import time as _time
        _time.sleep(5)
        st.rerun()
    st.stop()

# ── Sidebar filters (used by both the All-Depts overview and per-dept tabs) ───
with st.sidebar:
    st.markdown(
        '<hr style="border-color:rgba(255,255,255,0.2);margin:0.8rem 0;">',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="nav-label">Filters</div>', unsafe_allow_html=True)
    verdicts = st.multiselect(
        "Verdict",
        ["Shortlist", "Maybe", "Reject"],
        default=["Shortlist", "Maybe", "Reject"],
    )
    min_score = st.slider("Min Overall Score", 0, 100, 0, 5)
    min_exp   = st.slider("Min Experience (yrs)", 0, 20, 0, 1)
    search    = st.text_input("Search (name, ID, email, degree...)", placeholder="Type to filter...")

# ── Top tab strip: All Departments + one per active department ────────────────
tab_labels = ["All Departments"] + [
    f"{r['department']}  ({r['ranked_candidates']})" for r in dept_rows
]

# BUG-07 fix: when Home.py / Dashboard sets st.session_state["selected_dept"]
# via the OPEN -> button, surface a banner pointing the user to the matching
# tab. Streamlit's st.tabs has no native default-index API, so we cannot auto-
# focus the tab; this banner is the least-invasive way to direct attention.
_requested_dept = (st.session_state.get("selected_dept") or "").strip()
if _requested_dept:
    matched_idx = next(
        (i for i, r in enumerate(dept_rows, start=1)
         if r["department"] == _requested_dept),
        0,
    )
    if matched_idx > 0:
        st.info(
            f"🏢 Showing department: **{_requested_dept}** — "
            f"select its tab below ↓ (tab #{matched_idx})",
            icon="🏢",
        )
        # Clear after surfacing once so it doesn't keep flashing on every rerun.
        st.session_state.pop("selected_dept", None)

tabs = st.tabs(tab_labels)

# ── All Departments overview tab ───────────────────────────────────────────────
with tabs[0]:
    totals = {
        "depts":       len(dept_rows),
        "candidates":  sum(r["total_candidates"]   for r in dept_rows),
        "ranked":      sum(r["ranked_candidates"]  for r in dept_rows),
        "shortlist":   sum(r["shortlist"]          for r in dept_rows),
        "maybe":       sum(r["maybe"]              for r in dept_rows),
        "reject":      sum(r["reject"]             for r in dept_rows),
    }

    for col, val, lbl in zip(
        st.columns(5),
        [totals["depts"], totals["ranked"], totals["shortlist"], totals["maybe"], totals["reject"]],
        ["Active Departments", "Ranked", "🟢 Shortlist", "🟡 Maybe", "🔴 Reject"],
    ):
        with col:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-val">{val}</div>
                    <div class="metric-lbl">{lbl}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<div class="section-hd">Department Summary</div>',
        unsafe_allow_html=True,
    )

    for r in dept_rows:
        last = r.get("last_run") or "—"
        st.markdown(
            f"""
            <div class="dept-card">
                <div class="dept-name">{r['department']}
                    <span style="float:right;font-size:0.78rem;font-weight:500;color:#64748B;">
                        {r['job_count']} job posting{'s' if r['job_count'] != 1 else ''}
                    </span>
                </div>
                <div class="dept-stats">
                    <b>{r['ranked_candidates']}</b> ranked &nbsp;·&nbsp;
                    🟢 {r['shortlist']} Shortlist &nbsp;·&nbsp;
                    🟡 {r['maybe']} Maybe &nbsp;·&nbsp;
                    🔴 {r['reject']} Reject
                </div>
                <div class="dept-meta">Last run: {last}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ── Per-department tabs ────────────────────────────────────────────────────────


def _apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    if verdicts:
        out = out[out["recommendation"].isin(verdicts)]
    out = out[out["overall_score"] >= min_score]
    if min_exp > 0:
        out = out[out["experience_years"].fillna(0) >= min_exp]
    if search:
        search_lower = search.lower()
        mask = (
            out["candidate_name"].str.lower().str.contains(search_lower, na=False)
            | out["apply_id"].astype(str).str.lower().str.contains(search_lower, na=False)
            | out.get("email", pd.Series([""]*len(out), index=out.index)).str.lower().str.contains(search_lower, na=False)
            | out.get("mobile", pd.Series([""]*len(out), index=out.index)).astype(str).str.lower().str.contains(search_lower, na=False)
            | out.get("degree", pd.Series([""]*len(out), index=out.index)).str.lower().str.contains(search_lower, na=False)
            | out.get("university", pd.Series([""]*len(out), index=out.index)).str.lower().str.contains(search_lower, na=False)
            | out.get("experience_detail", pd.Series([""]*len(out), index=out.index)).str.lower().str.contains(search_lower, na=False)
        )
        out = out[mask]
    return out.reset_index(drop=True)


def _render_open_roles_for_dept(department: str, job_rows_for_dept: list, conn):
    """Shows BDJobs open role cards for this department.

    Each card shows: role title, experience, salary, location, key required skills.
    Clicking 'View Rankings' navigates to Job Rankings for that specific job.
    """
    dept_jobs = [
        (label, meta) for label, meta in BDJOBS_JOB_REGISTRY.items()
        if meta.get("department") == department
    ]

    if not dept_jobs:
        return

    is_day = st.session_state.get("day_mode", True)
    card_bg  = "#FFFFFF" if is_day else "#1E2435"
    card_bdr = "#E2E8F0" if is_day else "#2D3748"
    txt_col  = "#1E293B" if is_day else "#E2E8F0"
    sub_col  = "#64748B"

    st.markdown(
        f'<div class="section-hd" style="margin-top:1rem;">Open Roles ({len(dept_jobs)})</div>',
        unsafe_allow_html=True,
    )

    # Display in 2 columns
    for i in range(0, len(dept_jobs), 2):
        cols = st.columns(2)
        for j, (label, meta) in enumerate(dept_jobs[i:i+2]):
            with cols[j]:
                # Check if this job has ranked candidates
                job_row = next((r for r in job_rows_for_dept if r["job_label"] == label), None)
                ranked_count = job_row["ranked"] if job_row else 0
                shortlist    = job_row["shortlist"] if job_row else 0

                skills_preview = ", ".join((meta.get("required_skills") or [])[:4])
                salary_display = meta.get("salary_stated", "Negotiable")
                if salary_display == "Negotiable":
                    salary_display = meta.get("salary_estimate", "Negotiable")

                st.markdown(f"""
                <div style="background:{card_bg};border:1px solid {card_bdr};
                            border-radius:10px;padding:1rem;margin-bottom:0.8rem;">
                    <div style="font-size:0.9rem;font-weight:600;color:{txt_col};">
                        {meta.get('job_title', label)}
                    </div>
                    <div style="font-size:0.75rem;color:{sub_col};margin-top:4px;">
                        📍 {meta.get('location','-')} &nbsp;·&nbsp;
                        🕒 {meta.get('experience','-')} &nbsp;·&nbsp;
                        💸 {salary_display}
                    </div>
                    <div style="font-size:0.72rem;color:#94A3B8;margin-top:6px;">
                        <b>Key Skills:</b> {skills_preview}{"..." if len(meta.get('required_skills', [])) > 4 else ""}
                    </div>
                    <div style="font-size:0.72rem;color:#94A3B8;margin-top:6px;">
                        {ranked_count} ranked &nbsp;·&nbsp; 📈 {shortlist} shortlisted
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if st.button(
                    "View Rankings" if ranked_count > 0 else "No candidates yet",
                    key=f"role_btn_{label}",
                    type="primary" if ranked_count > 0 else "secondary",
                    use_container_width=True,
                    disabled=(ranked_count == 0),
                ):
                    st.session_state["selected_job"]     = label
                    st.session_state["jr_active_job"]    = label
                    st.session_state["jr_mode"]          = "detail"
                    st.session_state["jr_incoming_via"] = "dept"
                    st.switch_page("pages/2_Job_Rankings.py")

    st.markdown("<hr>", unsafe_allow_html=True)


def _render_ranked_table(df: pd.DataFrame, show_job_col: bool, unique_key: str):
    """Shared rendering for department-wide or single-job tables."""
    if df.empty:
        st.info("No candidates match the current filters.")
        return None

    disp = df.copy()
    # Re-number within the current view so ranks read 1..N after filtering.
    disp["#"] = range(1, len(disp) + 1)
    disp["verdict"] = disp["recommendation"].map(
        lambda v: f"{VERDICT_CFG.get(v, {}).get('icon', '')} {v}"
    )
    disp["cv"] = disp["has_uploaded_cv"].map(lambda x: "✅" if x else "")
    # Preview columns — first 2 items, mirrors Job Rankings exactly.
    disp["strengths_s"] = disp["strengths"].apply(
        lambda x: " · ".join(x[:2]) if isinstance(x, list) else ""
    )
    disp["gaps_s"] = disp["gaps"].apply(
        lambda x: " · ".join(x[:2]) if isinstance(x, list) else ""
    )
    disp["flags_s"] = disp["risk_flags"].apply(
        lambda x: " · ".join(x[:2]) if isinstance(x, list) else ""
    )

    cols = ["#", "candidate_name", "cv"]
    if show_job_col:
        cols.append("job_label")
    cols += [
        "overall_score", "skills_score", "experience_score",
        "leadership_score", "education_score", "culture_fit_score",
        "experience_years", "verdict",
        "strengths_s", "gaps_s", "flags_s", "reasoning",
        "bdjobs_score", "application_date", "age",
        "expected_salary", "current_salary",
    ]
    cols = [c for c in cols if c in disp.columns]

    rename = {
        "#": "#", "candidate_name": "Name", "cv": "CV",
        "job_label": "Job Posting",
        "overall_score": "Overall", "skills_score": "Skills",
        "experience_score": "Exp. Score",
        "leadership_score": "Lead.", "education_score": "Edu.",
        "culture_fit_score": "Culture",
        "experience_years": "Exp (yrs)", "verdict": "Verdict",
        "strengths_s": "Strengths", "gaps_s": "Weaknesses",
        "flags_s": "Risk Flags", "reasoning": "AI Summary",
        "bdjobs_score": "BDJobs (ref)", "application_date": "Applied",
        "age": "Age",
        "expected_salary": "Exp. Salary", "current_salary": "Cur. Salary",
    }
    table = disp[cols].rename(columns=rename)

    event = st.dataframe(
        table,
        use_container_width=True,
        height=460,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "#":          st.column_config.NumberColumn("#", width="small"),
            "Overall":    st.column_config.ProgressColumn("Overall",    min_value=0, max_value=100, format="%d"),
            "Skills":     st.column_config.ProgressColumn("Skills",     min_value=0, max_value=100, format="%d"),
            "Exp. Score": st.column_config.ProgressColumn("Exp. Score", min_value=0, max_value=100, format="%d"),
            "Lead.":      st.column_config.ProgressColumn("Lead.",      min_value=0, max_value=100, format="%d"),
            "Edu.":       st.column_config.ProgressColumn("Edu.",       min_value=0, max_value=100, format="%d"),
            "Culture":    st.column_config.ProgressColumn("Culture",    min_value=0, max_value=100, format="%d"),
            "Exp (yrs)":  st.column_config.NumberColumn("Exp (yrs)",    format="%.1f"),
            "AI Summary": st.column_config.TextColumn("AI Summary",     width="large"),
            "CV":         st.column_config.TextColumn("CV",             width="small"),
        },
        key=f"dept_rank_table_{unique_key}",
    )
    return event


def _render_candidate_detail(sel: pd.Series, key_suffix: str):
    """Full-feature candidate detail panel — mirrors 2_Job_Rankings.py exactly.

    Layout:
      - Header card (name/contact/edu on left, score+verdict on right)
      - Score pills (colored thresholds)
      - Salary row (current/expected/BDJobs/CV)
      - Two columns:
          left  [3] : AI Summary, Strengths, Weaknesses, Risk Flags, Experience
          right [2] : Score Breakdown chart, Resume download, HR Actions
      - Full-width below: PDF Viewer toggle + inline iframe
    """
    txt_col, sub_col, card_bg, card_bdr, body_col = (
        "#1E293B", "#64748B", "#FFFFFF", "#E2E8F0", "#374151",
    )

    name     = sel.get("candidate_name") or "—"
    email    = sel.get("email") or ""
    mobile   = sel.get("mobile") or ""
    location = sel.get("location") or ""
    degree   = sel.get("degree") or ""
    univ     = sel.get("university") or ""
    app_date = sel.get("application_date") or "—"
    age_val  = int(sel["age"]) if pd.notna(sel.get("age")) else "—"
    exp_yrs  = sel.get("experience_years") or "—"
    apply_id = str(sel.get("apply_id") or "")
    job_label = str(sel.get("job_label") or "")

    verdict  = str(sel.get("recommendation") or "")
    override = str(sel.get("hr_override") or "")
    display_verdict = override if override else verdict
    vcfg = VERDICT_CFG.get(
        display_verdict,
        {"color": "#64748B", "bg": "#F1F5F9", "icon": "◆"},
    )
    score       = int(sel.get("overall_score") or 0)
    score_color = "#16A34A" if score >= 70 else "#D97706" if score >= 50 else "#DC2626"

    contact_parts = [p for p in [email, mobile, location] if p]
    edu_parts     = [p for p in [degree, univ] if p]

    prof_fields = [name!="—", bool(email), bool(mobile), bool(degree), bool(univ), bool(sel.get("pdf_path"))]
    prof_pct    = int(sum(prof_fields)/len(prof_fields)*100)

    # PDF handling - moved to top so accessible throughout function
    pdf_path = str(sel.get("pdf_path") or "")
    pdf_exists = pdf_path and os.path.exists(pdf_path)
    pdf_bytes = None
    if pdf_exists:
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
    safe_name = str(name).replace(" ", "_").replace("/", "_")

    st.markdown(
        f'<div class="section-hd" style="color:{sub_col} !important;'
        f'border-bottom-color:{card_bdr};">Candidate Detail</div>',
        unsafe_allow_html=True,
    )

    # ── Header card ───────────────────────────────────────────────────────────
    st.markdown(f"""
        <div style="background:{card_bg};border:1px solid {card_bdr};
                    border-left:4px solid {vcfg['color']};
                    border-radius:10px;padding:1.4rem;margin-bottom:1rem;">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:1.2rem;">
                <div style="flex:1;min-width:0;">
                    <div style="display:flex;align-items:center;gap:12px;margin-bottom:4px;">
                        <div class="cand-name-lg" style="color:{txt_col} !important;">{name}</div>
                        <span class="verdict-badge verdict-{display_verdict.lower()}">{vcfg.get('icon','')} {display_verdict}</span>
                    </div>
                    <div class="cand-meta-sm" style="color:{sub_col} !important;">✉ {" · ".join(contact_parts)}</div>
                    <div class="cand-meta-sm" style="color:{sub_col} !important;">🎓 {" — ".join(edu_parts)}</div>
                    <div class="cand-meta-sm" style="color:{sub_col} !important;margin-top:6px;">
                        ID: <b>{apply_id}</b> &nbsp;·&nbsp; Job: <b>{job_label}</b> &nbsp;·&nbsp; Applied: <b>{app_date}</b> &nbsp;·&nbsp; Age: <b>{age_val}</b> &nbsp;·&nbsp; Exp: <b>{exp_yrs} yrs</b>
                        {f'&nbsp;·&nbsp;<span style="color:#64748B;font-weight:600;">HR Override Active</span>' if override else ''}
                    </div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # ── Salary & financial info ─────────────────────────────────────────────
    # Debug: show raw values to diagnose data issues
    debug_fields = ["expected_salary", "current_salary", "bdjobs_score", "has_uploaded_cv",
                    "application_date", "age", "email", "mobile"]
    debug_info = {f: sel.get(f) for f in debug_fields}

    exp_sal_raw = sel.get("expected_salary")
    cur_sal_raw = sel.get("current_salary")
    bd_score_raw = sel.get("bdjobs_score")
    has_cv_raw = sel.get("has_uploaded_cv")

    # Use raw value if present, otherwise show "—"
    exp_sal = str(exp_sal_raw).strip() if exp_sal_raw and str(exp_sal_raw).strip() else "—"
    cur_sal = str(cur_sal_raw).strip() if cur_sal_raw and str(cur_sal_raw).strip() else "—"
    bd_score = str(bd_score_raw).strip() if bd_score_raw and str(bd_score_raw).strip() else "—"
    has_cv = "✅" if has_cv_raw else "❌"
    cv_color = "#16A34A" if has_cv_raw else "#DC2626"

    # Format salary with BDT prefix only if value exists
    cur_sal_display = f"BDT {cur_sal}" if cur_sal != "—" else cur_sal
    exp_sal_display = f"BDT {exp_sal}" if exp_sal != "—" else exp_sal

    sal_html = f'''
        <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:1rem;">
            <div style="flex:1;min-width:130px;background:{card_bg};border:1px solid {card_bdr};border-radius:8px;padding:0.7rem 0.9rem;text-align:center;">
                <div style="font-size:0.62rem;font-weight:600;color:{sub_col};text-transform:uppercase;letter-spacing:0.06em;margin-bottom:4px;">Current Salary</div>
                <div style="font-size:0.92rem;font-weight:700;color:{txt_col} !important;">{cur_sal_display}</div>
            </div>
            <div style="flex:1;min-width:130px;background:{card_bg};border:1px solid {card_bdr};border-radius:8px;padding:0.7rem 0.9rem;text-align:center;">
                <div style="font-size:0.62rem;font-weight:600;color:{sub_col};text-transform:uppercase;letter-spacing:0.06em;margin-bottom:4px;">Expected Salary</div>
                <div style="font-size:0.92rem;font-weight:700;color:{txt_col} !important;">{exp_sal_display}</div>
            </div>
            <div style="flex:1;min-width:130px;background:{card_bg};border:1px solid {card_bdr};border-radius:8px;padding:0.7rem 0.9rem;text-align:center;">
                <div style="font-size:0.62rem;font-weight:600;color:{sub_col};text-transform:uppercase;letter-spacing:0.06em;margin-bottom:4px;">BDJobs Score</div>
                <div style="font-size:0.92rem;font-weight:700;color:{sub_col} !important;">{bd_score}</div>
            </div>
            <div style="flex:1;min-width:130px;background:{card_bg};border:1px solid {card_bdr};border-radius:8px;padding:0.7rem 0.9rem;text-align:center;">
                <div style="font-size:0.62rem;font-weight:600;color:{sub_col};text-transform:uppercase;letter-spacing:0.06em;margin-bottom:4px;">Uploaded CV</div>
                <div style="font-size:0.92rem;font-weight:700;color:{cv_color} !important;">{has_cv}</div>
            </div>
        </div>
    '''
    st.markdown(sal_html, unsafe_allow_html=True)

    # Debug expander to diagnose data issues
    with st.expander("🔍 Debug: Raw Data Values", expanded=True):
        st.json(debug_info)
        st.write("**All available columns:**")
        st.write(list(sel.index) if hasattr(sel, 'index') else "N/A")
        st.write("**Raw sel type:**", type(sel))
        # Check specific fields
        st.write("**Direct field access test:**")
        for field in ["expected_salary", "current_salary", "bdjobs_score", "has_uploaded_cv"]:
            val = sel[field] if field in sel.index else "FIELD_NOT_FOUND"
            st.write(f"  {field}: {repr(val)} (type: {type(val)})")

    # ── Two-column body ───────────────────────────────────────────────────────
    col_left, col_right = st.columns([3, 2], gap="large")

    with col_left:
        # AI Summary
        st.markdown(
            f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">AI Summary</div>',
            unsafe_allow_html=True,
        )
        reasoning = sel.get("reasoning") or "—"
        st.markdown(
            f'<div style="background:{card_bg};border:1px solid {card_bdr};border-radius:8px;'
            f'padding:0.9rem 1.1rem;font-size:0.9rem;color:{body_col} !important;line-height:1.7;margin-bottom:1rem;">'
            f'<span style="font-size:1.1rem;margin-right:6px;">💡</span> {reasoning}</div>',
            unsafe_allow_html=True,
        )

        # Strengths / Gaps
        col_s, col_w = st.columns(2)
        with col_s:
            st.markdown(
                f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Strengths</div>',
                unsafe_allow_html=True,
            )
            strengths_list = sel.get("strengths") or []
            if strengths_list:
                for s in strengths_list:
                    st.markdown(f'<div class="strength-item"><span style="font-size:1rem;flex-shrink:0;">✓</span><span>{s}</span></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div style="font-size:0.82rem;color:{sub_col};padding:6px 0;">No explicit strengths recorded.</div>', unsafe_allow_html=True)
        with col_w:
            st.markdown(
                f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Gaps & Weaknesses</div>',
                unsafe_allow_html=True,
            )
            gaps_list = sel.get("gaps") or []
            if gaps_list:
                for g in gaps_list:
                    st.markdown(f'<div class="gap-item"><span style="font-size:1rem;flex-shrink:0;">⚠</span><span>{g}</span></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div style="font-size:0.82rem;color:{sub_col};padding:6px 0;">No explicit gaps recorded.</div>', unsafe_allow_html=True)

        # Risk flags
        flags = sel.get("risk_flags") or []
        if len(flags):
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(
                f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Risk Flags</div>',
                unsafe_allow_html=True,
            )
            chips = "".join(f'<span class="flag-chip">⚑ {f}</span>' for f in flags)
            st.markdown(
                f'<div style="padding:0.3rem 0;">{chips}</div>',
                unsafe_allow_html=True,
            )

        # Experience detail (if present)
        exp_det = sel.get("experience_detail") or ""
        if exp_det:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(
                f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Experience</div>',
                unsafe_allow_html=True,
            )
            exp_entries = [e.strip().replace("*", "").replace("##", " — ") for e in str(exp_det).split("|") if e.strip()]
            for entry in exp_entries:
                st.markdown(
                    f'<div class="timeline-item" style="font-size:0.84rem;color:{body_col} !important;line-height:1.55;">'
                    f'<span style="font-weight:600;color:{txt_col} !important;">{entry}</span></div>',
                    unsafe_allow_html=True,
                )

    with col_right:
        # Score breakdown horizontal bars
        st.markdown(
            f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Score Breakdown</div>',
            unsafe_allow_html=True,
        )
        
        # Overall Score display at top of panel
        st.markdown(
            f'<div style="background:{card_bg};border:1px solid {card_bdr};border-left:4px solid {score_color};'
            f'border-radius:8px;padding:1rem 1.2rem;margin-bottom:1rem;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<div style="font-size:0.85rem;font-weight:600;color:{sub_col} !important;">Overall Score</div>'
            f'<div style="font-size:2rem;font-weight:700;color:{score_color} !important;line-height:1;">{score}</div>'
            f'</div>'
            f'<div style="margin-top:8px;height:8px;background:#E2E8F0;border-radius:4px;overflow:hidden;">'
            f'<div style="width:{score}%;height:100%;border-radius:4px;background:{score_color};transition:width 0.5s ease;"></div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        
        sb_dims = [
            ("Skills",      sel.get("skills_score") or 0,    "#8B5CF6", "30%"),
            ("Experience",  sel.get("experience_score") or 0, "#3B82F6", "25%"),
            ("Leadership",  sel.get("leadership_score") or 0, "#C8102E", "20%"),
            ("Education",   sel.get("education_score") or 0,  "#10B981", "15%"),
            ("Culture Fit", sel.get("culture_fit_score") or 0,"#F59E0B", "10%"),
        ]
        sb_html = '<div style="display:flex;flex-direction:column;gap:10px;margin-bottom:1rem;">'
        for d_label, d_score, d_col, d_w in sb_dims:
            d_pct = min(100, max(0, int(d_score)))
            sb_html += f'''<div>
                <div style="display:flex;justify-content:space-between;font-size:0.72rem;font-weight:600;color:{sub_col};margin-bottom:3px;">
                    <span>{d_label} <span style="font-weight:400;color:#94A3B8;">· {d_w}</span></span>
                    <span style="color:{d_col};font-weight:700;">{int(d_score)}</span>
                </div>
                <div style="height:10px;background:#E2E8F0;border-radius:5px;overflow:hidden;">
                    <div style="width:{d_pct}%;height:100%;border-radius:5px;background:{d_col};transition:width 0.5s ease;"></div>
                </div>
            </div>'''
        sb_html += '</div>'
        st.markdown(sb_html, unsafe_allow_html=True)

        # Resume card
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Resume</div>',
            unsafe_allow_html=True,
        )
        if pdf_exists and pdf_bytes:
            file_size = len(pdf_bytes)
            size_kb = round(file_size / 1024, 1)
            st.markdown(
                f'<div style="background:{card_bg};border:1px solid {card_bdr};border-radius:8px;'
                f'padding:0.7rem 0.9rem;display:flex;justify-content:space-between;align-items:center;margin-bottom:0.6rem;">'
                f'<div><div style="font-size:0.78rem;font-weight:600;color:{txt_col} !important;">{safe_name}_cv.pdf</div>'
                f'<div style="font-size:0.68rem;color:{sub_col} !important;margin-top:2px;">{size_kb} KB · PDF</div></div>'
                f'<div style="background:#DCFCE7;color:#166534;border-radius:6px;padding:3px 10px;font-size:0.65rem;font-weight:600;">✓ Available</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.download_button(
                "⬇ Download Resume PDF",
                pdf_bytes,
                file_name=f"{safe_name}_cv.pdf",
                mime="application/pdf",
                key=f"dl_cv_{apply_id}_{key_suffix}",
                use_container_width=True,
            )
        else:
            st.markdown(
                f'<div style="background:{card_bg};border:1px solid {card_bdr};border-radius:8px;'
                f'padding:0.7rem 0.9rem;display:flex;justify-content:space-between;align-items:center;margin-bottom:0.6rem;">'
                f'<div style="font-size:0.78rem;font-weight:600;color:{sub_col} !important;">No uploaded CV</div>'
                f'<div style="background:#FEE2E2;color:#991B1B;border-radius:6px;padding:3px 10px;font-size:0.65rem;font-weight:600;">✗ Missing</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # HR Actions
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">HR Actions</div>',
            unsafe_allow_html=True,
        )
        override_options = ["", "Shortlist", "Maybe", "Reject"]
        cur_idx = override_options.index(override) if override in override_options else 0
        new_override = st.selectbox(
            "Override AI Recommendation",
            override_options,
            index=cur_idx,
            key=f"override_dept_{apply_id}_{key_suffix}",
            format_func=lambda x: "— No override —" if x == "" else x,
        )
        hr_note = st.text_area(
            "Internal Note",
            value=str(sel.get("hr_note") or ""),
            placeholder="Add internal note about this candidate...",
            height=80,
            key=f"note_dept_{apply_id}_{key_suffix}",
        )
        if st.button(
            "💾  Save HR Decision",
            type="primary",
            key=f"save_dept_{apply_id}_{key_suffix}",
            use_container_width=True,
        ):
            save_hr_override(job_label, apply_id, new_override, hr_note)
            st.success("Saved successfully.")
            st.rerun()

        # Delete candidate
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Danger Zone</div>',
            unsafe_allow_html=True,
        )
        del_key = f"del_confirm_dept_{apply_id}_{key_suffix}"
        if del_key not in st.session_state:
            st.session_state[del_key] = False

        if not st.session_state[del_key]:
            if st.button("🗑️  Delete This Candidate", type="secondary",
                         key=f"del_dept_{apply_id}_{key_suffix}", use_container_width=True):
                st.session_state[del_key] = True
                st.rerun()
        else:
            st.error(f"⚠️ **Permanently delete {name}** (ID: {apply_id})? This cannot be undone.")
            dc1, dc2 = st.columns(2)
            with dc1:
                if st.button("✅ Confirm Delete", type="primary",
                             key=f"del_yes_dept_{apply_id}_{key_suffix}", use_container_width=True):
                    ok = delete_candidate(job_label, apply_id)
                    st.session_state[del_key] = False
                    if ok:
                        st.success(f"Deleted {name} successfully.")
                    else:
                        st.error("Candidate not found or already deleted.")
                    st.rerun()
            with dc2:
                if st.button("Cancel", key=f"del_no_dept_{apply_id}_{key_suffix}", use_container_width=True):
                    st.session_state[del_key] = False
                    st.rerun()

    # ── Full-width PDF viewer (toggle) ────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Resume Viewer</div>',
        unsafe_allow_html=True,
    )
    if not pdf_exists:
        st.error("📄 No resume uploaded for this candidate.")
    else:
        view_key = f"view_pdf_dept_{apply_id}_{key_suffix}"
        if view_key not in st.session_state:
            st.session_state[view_key] = False
        is_open = st.session_state[view_key]
        
        col_view, col_download = st.columns([1, 1])
        with col_view:
            if st.button(
                "✕  Close PDF Viewer" if is_open else "🔍  View PDF in Browser",
                key=f"btn_pdf_dept_{apply_id}_{key_suffix}",
                type="secondary",
                use_container_width=True,
            ):
                st.session_state[view_key] = not is_open
                st.rerun()
        
        with col_download:
            st.download_button(
                "⬇ Download PDF",
                pdf_bytes,
                file_name=f"{safe_name}_resume.pdf",
                mime="application/pdf",
                key=f"dl_pdf_dept_{apply_id}_{key_suffix}",
                use_container_width=True,
            )
        
        if st.session_state[view_key]:
            try:
                # Validate PDF magic bytes
                is_valid_pdf = pdf_bytes[:4] == b"%PDF"
                
                if not is_valid_pdf:
                    st.error("⚠️ The file exists but appears to be an invalid PDF format.")
                elif len(pdf_bytes) > 10 * 1024 * 1024:  # 10MB limit
                    st.warning("📄 PDF is large (>10MB). Please download to view locally.")
                else:
                    b64 = base64.b64encode(pdf_bytes).decode("utf-8")
                    st.markdown(
                        f'<iframe src="data:application/pdf;base64,{b64}" '
                        f'width="100%" height="820px" '
                        f'style="border:1px solid {card_bdr};border-radius:8px;margin-top:0.5rem;"></iframe>',
                        unsafe_allow_html=True,
                    )
            except Exception as e:
                st.error(f"❌ Failed to load PDF: {str(e)}")
                st.info("💡 Try downloading the PDF instead using the button above.")


for idx, dept in enumerate(dept_rows, start=1):
    dept_name = dept["department"]
    with tabs[idx]:
        # Metrics strip for this dept
        for col, val, lbl in zip(
            st.columns(4),
            [
                dept["ranked_candidates"],
                dept["shortlist"],
                dept["maybe"],
                dept["job_count"],
            ],
            ["Ranked", "🟢 Shortlist", "🟡 Maybe", "Job Postings"],
        ):
            with col:
                st.markdown(
                    f"""
                    <div class="metric-card">
                        <div class="metric-val">{val}</div>
                        <div class="metric-lbl">{lbl}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown("<br>", unsafe_allow_html=True)

        # Load all candidates for this dept once (cached per interaction).
        all_df = fetch_candidates_by_department(conn, dept_name)
        jobs_in_dept = fetch_jobs_by_department(conn, dept_name)

        # BDJobs open role cards for this department
        _render_open_roles_for_dept(dept_name, jobs_in_dept, conn)

        # Job sub-tabs: "All Jobs" + one per job_label
        job_tab_labels = [f"All Jobs in Dept ({len(all_df)})"] + [
            f"{r['job_label']}  ({r['ranked']})" for r in jobs_in_dept
        ]
        job_tabs = st.tabs(job_tab_labels)

        def _export_button(scope_df: pd.DataFrame, scope_label: str, key: str):
            if scope_df.empty:
                return
            stamp = datetime.now().strftime("%Y%m%d_%H%M")
            fname = f"{scope_label}_{stamp}.xlsx"
            st.download_button(
                f"📥  Export — {scope_label}.xlsx",
                data=to_excel(scope_df, scope_label),
                file_name=fname,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"export_{key}",
            )

        # -- All Jobs sub-tab ------------------------------------------------
        with job_tabs[0]:
            filtered = _apply_filters(all_df)
            _export_button(filtered, f"{dept_name}_rankings", f"dept_{idx}_all")
            st.markdown(
                f'<div class="hint-text" style="padding:0.4rem 0;">'
                f'Showing {len(filtered)} of {len(all_df)} ranked in {dept_name}'
                f'</div>',
                unsafe_allow_html=True,
            )
            event = _render_ranked_table(filtered, show_job_col=True, unique_key=f"d{idx}_all")
            if event and event.selection and event.selection.rows:
                sel = filtered.iloc[event.selection.rows[0]]
                st.markdown('<hr class="divider">', unsafe_allow_html=True)
                _render_candidate_detail(sel, key_suffix=f"d{idx}_all")

        # -- One sub-tab per job_label ---------------------------------------
        for j, job in enumerate(jobs_in_dept, start=1):
            with job_tabs[j]:
                if all_df.empty or "job_label" not in all_df.columns:
                    job_df = pd.DataFrame()
                else:
                    job_df = all_df[all_df["job_label"] == job["job_label"]].copy()
                if not job_df.empty:
                    job_df = job_df.reset_index(drop=True)
                    job_df["rank"] = range(1, len(job_df) + 1)
                filtered = _apply_filters(job_df)
                _export_button(filtered, job["job_label"], f"dept_{idx}_job_{j}")
                title = job.get("job_title") or job["job_label"]
                st.markdown(
                    f'<div class="hint-text" style="padding:0.4rem 0;">'
                    f'{title} — {len(filtered)} of {len(job_df)} ranked</div>',
                    unsafe_allow_html=True,
                )
                event = _render_ranked_table(filtered, show_job_col=False, unique_key=f"d{idx}_j{j}")
                if event and event.selection and event.selection.rows:
                    sel = filtered.iloc[event.selection.rows[0]]
                    st.markdown('<hr class="divider">', unsafe_allow_html=True)
                    _render_candidate_detail(sel, key_suffix=f"d{idx}_j{j}")

# ── Auto-refresh while live processing is happening ───────────────────────────
if _auto_refresh_dept and _active_jobs:
    import time as _time
    _time.sleep(5)
    st.rerun()
