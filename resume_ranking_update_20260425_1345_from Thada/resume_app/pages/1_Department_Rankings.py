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
    to_excel, save_hr_override,
    get_css, init_theme, render_sidebar,
    VERDICT_CFG, SCORE_DIMS,
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

if not dept_rows:
    st.info(
        "No ranked candidates yet.  Use **New Job Posting** to register a job, "
        "then run `ranker.py --job <label> --department <dept>` to populate rankings."
    )
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
    search    = st.text_input("Search by Name", placeholder="Type to filter...")

# ── Top tab strip: All Departments + one per active department ────────────────
tab_labels = ["All Departments"] + [
    f"{r['department']}  ({r['ranked_candidates']})" for r in dept_rows
]
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
        out = out[out["candidate_name"].str.contains(search, case=False, na=False)]
    return out.reset_index(drop=True)


def _render_ranked_table(df: pd.DataFrame, show_job_col: bool):
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
    disp["cv"] = disp["has_uploaded_cv"].map(lambda x: "✓" if x else "")
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
        key=f"dept_rank_table_{id(df)}",
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

    st.markdown(
        f'<div class="section-hd" style="color:{sub_col} !important;'
        f'border-bottom-color:{card_bdr};">Candidate Detail</div>',
        unsafe_allow_html=True,
    )

    # ── Header card ────────────────────────────────────────────────────────────
    st.markdown(f"""
        <div style="background:{card_bg};border:1px solid {card_bdr};
                    border-left:4px solid {vcfg['color']};
                    border-radius:10px;padding:1.4rem;margin-bottom:1rem;">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;">
                <div style="flex:1;min-width:0;">
                    <div class="cand-name-lg" style="color:{txt_col} !important;">{name}</div>
                    <div class="cand-meta-sm" style="color:{sub_col} !important;">{" · ".join(contact_parts)}</div>
                    <div class="cand-meta-sm" style="color:{sub_col} !important;">{" — ".join(edu_parts)}</div>
                    <div class="cand-meta-sm" style="color:{sub_col} !important;margin-top:4px;">
                        Apply ID: {apply_id} &nbsp;·&nbsp;
                        Job: {job_label} &nbsp;·&nbsp;
                        Applied: {app_date} &nbsp;·&nbsp;
                        Age: {age_val} &nbsp;·&nbsp;
                        Exp: {exp_yrs} yrs
                    </div>
                </div>
                <div style="text-align:right;flex-shrink:0;">
                    <div style="font-size:3rem;font-weight:700;color:{score_color} !important;line-height:1;">{score}</div>
                    <div style="font-size:0.72rem;font-weight:500;color:{sub_col} !important;text-transform:uppercase;letter-spacing:0.1em;">Overall Score</div>
                    <div style="margin-top:6px;">
                        <span class="verdict-badge verdict-{display_verdict.lower()}">{vcfg.get('icon','')} {display_verdict}</span>
                    </div>
                    {f'<div style="font-size:0.7rem;color:{sub_col} !important;margin-top:3px;">HR Override</div>' if override else ''}
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # ── Score pills ───────────────────────────────────────────────────────────
    dims_vals = [
        ("Skills",      sel.get("skills_score")),
        ("Experience",  sel.get("experience_score")),
        ("Leadership",  sel.get("leadership_score")),
        ("Education",   sel.get("education_score")),
        ("Culture Fit", sel.get("culture_fit_score")),
    ]
    pills = ""
    for dim, sc in dims_vals:
        if sc is not None:
            sc  = int(sc)
            cls = "score-green" if sc >= 70 else "score-yellow" if sc >= 50 else "score-red"
            pills += f'<span class="score-pill {cls}">{dim} &nbsp; {sc}</span>'
    st.markdown(
        f'<div style="margin-bottom:1rem;">{pills}</div>',
        unsafe_allow_html=True,
    )

    # ── Salary / CV row ───────────────────────────────────────────────────────
    exp_sal  = sel.get("expected_salary") or "—"
    cur_sal  = sel.get("current_salary") or "—"
    bd_score = sel.get("bdjobs_score") or "—"
    has_cv   = "✓ Yes" if sel.get("has_uploaded_cv") else "—"
    st.markdown(f"""
        <div style="background:{card_bg};border:1px solid {card_bdr};border-radius:8px;
                    padding:0.8rem 1rem;margin-bottom:1rem;display:flex;gap:2rem;flex-wrap:wrap;">
            <div>
                <div style="font-size:0.72rem;font-weight:500;color:{sub_col} !important;text-transform:uppercase;letter-spacing:0.06em;">Current Salary</div>
                <div style="font-size:0.92rem;font-weight:600;color:{txt_col} !important;">BDT {cur_sal}</div>
            </div>
            <div>
                <div style="font-size:0.72rem;font-weight:500;color:{sub_col} !important;text-transform:uppercase;letter-spacing:0.06em;">Expected Salary</div>
                <div style="font-size:0.92rem;font-weight:600;color:{txt_col} !important;">BDT {exp_sal}</div>
            </div>
            <div>
                <div style="font-size:0.72rem;font-weight:500;color:{sub_col} !important;text-transform:uppercase;letter-spacing:0.06em;">BDJobs Score (ref)</div>
                <div style="font-size:0.92rem;color:{sub_col} !important;">{bd_score}</div>
            </div>
            <div>
                <div style="font-size:0.72rem;font-weight:500;color:{sub_col} !important;text-transform:uppercase;letter-spacing:0.06em;">Uploaded CV</div>
                <div style="font-size:0.92rem;color:{txt_col} !important;">{has_cv}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # ── Two-column body ───────────────────────────────────────────────────────
    col_left, col_right = st.columns([3, 2], gap="large")

    with col_left:
        # AI Summary
        st.markdown(
            f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">AI Summary</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="font-size:0.92rem;color:{body_col} !important;line-height:1.75;padding:0.5rem 0 1rem;">'
            f'{sel.get("reasoning") or "—"}</div>',
            unsafe_allow_html=True,
        )

        # Strengths / Weaknesses
        col_s, col_w = st.columns(2)
        with col_s:
            st.markdown(
                f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Strengths</div>',
                unsafe_allow_html=True,
            )
            for s in (sel.get("strengths") or []):
                st.markdown(
                    f'<div style="font-size:0.88rem;color:#16A34A !important;margin-bottom:5px;">✓ &nbsp;{s}</div>',
                    unsafe_allow_html=True,
                )
        with col_w:
            st.markdown(
                f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Weaknesses</div>',
                unsafe_allow_html=True,
            )
            for g in (sel.get("gaps") or []):
                st.markdown(
                    f'<div style="font-size:0.88rem;color:#D97706 !important;margin-bottom:5px;">⚠ &nbsp;{g}</div>',
                    unsafe_allow_html=True,
                )

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
            for entry in str(exp_det).split("|"):
                entry = entry.strip().replace("*", "").replace("##", " — ")
                if entry:
                    st.markdown(
                        f'<div style="font-size:0.86rem;color:{body_col} !important;margin-bottom:5px;'
                        f'padding-left:0.6rem;border-left:2px solid {card_bdr};">• {entry}</div>',
                        unsafe_allow_html=True,
                    )

    with col_right:
        # Score chart
        st.markdown(
            f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Score Breakdown</div>',
            unsafe_allow_html=True,
        )
        chart_data = pd.DataFrame({
            "Dimension": ["Skills", "Experience", "Leadership", "Education", "Culture Fit"],
            "Score": [
                sel.get("skills_score") or 0,
                sel.get("experience_score") or 0,
                sel.get("leadership_score") or 0,
                sel.get("education_score") or 0,
                sel.get("culture_fit_score") or 0,
            ],
        })
        st.bar_chart(chart_data.set_index("Dimension"), height=240, color="#C8102E")

        # Resume download
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Resume</div>',
            unsafe_allow_html=True,
        )
        pdf_path = str(sel.get("pdf_path") or "")
        pdf_exists = pdf_path and os.path.exists(pdf_path)
        pdf_bytes = None
        if pdf_exists:
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            safe_name = str(name).replace(" ", "_").replace("/", "_")
            st.download_button(
                "📄  Download Resume PDF",
                pdf_bytes,
                file_name=f"{safe_name}_cv.pdf",
                mime="application/pdf",
                key=f"dl_cv_{apply_id}_{key_suffix}",
                use_container_width=True,
            )
        else:
            st.markdown(
                f'<div style="font-size:0.86rem;color:{sub_col} !important;padding:0.5rem 0;">'
                f'No uploaded CV available.</div>',
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

    # ── Full-width PDF viewer (toggle) ────────────────────────────────────────
    if pdf_exists and pdf_bytes:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Resume Viewer</div>',
            unsafe_allow_html=True,
        )
        view_key = f"view_pdf_dept_{apply_id}_{key_suffix}"
        if view_key not in st.session_state:
            st.session_state[view_key] = False
        is_open = st.session_state[view_key]
        if st.button(
            "✕  Close PDF Viewer" if is_open else "🔍  View PDF in Browser",
            key=f"btn_pdf_dept_{apply_id}_{key_suffix}",
            type="secondary",
        ):
            st.session_state[view_key] = not is_open
            st.rerun()
        if st.session_state[view_key]:
            b64 = base64.b64encode(pdf_bytes).decode("utf-8")
            st.markdown(
                f'<iframe src="data:application/pdf;base64,{b64}" '
                f'width="100%" height="820px" '
                f'style="border:1px solid {card_bdr};border-radius:8px;margin-top:0.5rem;"></iframe>',
                unsafe_allow_html=True,
            )


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
            event = _render_ranked_table(filtered, show_job_col=True)
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
                event = _render_ranked_table(filtered, show_job_col=False)
                if event and event.selection and event.selection.rows:
                    sel = filtered.iloc[event.selection.rows[0]]
                    st.markdown('<hr class="divider">', unsafe_allow_html=True)
                    _render_candidate_detail(sel, key_suffix=f"d{idx}_j{j}")
