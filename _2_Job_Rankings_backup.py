"""
pages/2_Rankings.py — Ranked candidates table + click-to-detail with PDF viewer.
"""

import os
import base64
import streamlit as st
import pandas as pd
from datetime import datetime
from db import (
    get_conn, fetch_candidates, fetch_all_jobs, to_excel, save_hr_override,
    get_css, init_theme, theme_toggle,
    SCORE_DIMS, VERDICT_CFG, LOGO_PATH,
    get_job_department, fetch_audit_log, find_duplicate_applications,
    render_sidebar,
    BDJOBS_JOB_REGISTRY,
)

st.set_page_config(
    page_title="Ranking Results — HR Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_theme()
st.markdown(get_css(), unsafe_allow_html=True)

# ── Force dataframe text visibility regardless of Streamlit theme ──────────────
st.markdown("""
<style>
[data-testid="stDataFrame"] [data-testid="glideDataEditor"] canvas {
    color-scheme: light !important;
}
div[data-testid="stDataFrame"] { border-radius: 8px !important; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

# ── DB ─────────────────────────────────────────────────────────────────────────
try:
    conn = get_conn()
except Exception as e:
    st.error(f"Database connection failed: {e}")
    st.stop()

job_rows = fetch_all_jobs(conn)
labels   = job_rows["job_label"].tolist() if not job_rows.empty else []

if not labels:
    st.warning("No ranked data yet. Go to **New Job Posting** to start.")
    st.stop()

# ── Sidebar ───────────────────────────────────────────────────────────────────────────────────
# NAV-01: render_sidebar() in db.py is the single source of truth for the
# logo + navigation links. The previous manual duplication of page_link calls
# was removed; the job selector + filters below are page-specific and remain.
render_sidebar()

with st.sidebar:
    st.markdown('<hr style="border-color:rgba(255,255,255,0.2);margin:0.8rem 0;">', unsafe_allow_html=True)
    st.markdown('<div class="nav-label">Job Posting</div>', unsafe_allow_html=True)

    default_idx = 0
    if "selected_job" in st.session_state and st.session_state["selected_job"] in labels:
        default_idx = labels.index(st.session_state["selected_job"])
    job_label = st.selectbox("Job", labels, index=default_idx, label_visibility="collapsed")
    st.session_state["selected_job"] = job_label

    st.markdown('<div class="nav-label" style="margin-top:0.8rem;">Filters</div>', unsafe_allow_html=True)
    verdicts  = st.multiselect("Verdict", ["Shortlist","Maybe","Reject"], default=["Shortlist","Maybe","Reject"])
    min_score = st.slider("Min Overall Score", 0, 100, 0, 5)
    search    = st.text_input("Search (name, ID, email, degree...)", placeholder="Type to filter...")

    score_labels = [lbl for _, lbl in SCORE_DIMS]
    score_keys   = [key for key, _ in SCORE_DIMS]
    sort_lbl = st.selectbox("Sort By", score_labels, index=0)
    sort_key = score_keys[score_labels.index(sort_lbl)]

# ── Load & filter ──────────────────────────────────────────────────────────────
df = fetch_candidates(conn, job_label)
if df.empty:
    st.warning(f"No candidates found for **{job_label}**.")
    st.stop()

# FEAT-02: surface duplicate applications (same candidate applied to multiple
# jobs) as a top-level banner. The detail panel already shows per-candidate
# duplicates; this banner alerts HR before they start reviewing.
try:
    _dupe_df = find_duplicate_applications(job_label=job_label, conn=conn)
    if _dupe_df is not None and not _dupe_df.empty:
        st.warning(
            f"⚠️ {len(_dupe_df)} potential duplicate application(s) detected for "
            f"**{job_label}** — the same candidate has applied to other open jobs. "
            f"Review the per-candidate detail panel for the matching apply IDs.",
            icon="⚠️",
        )
except Exception:
    # Non-fatal: duplicate detection should never block the rankings page.
    pass

ranked_df = df[df["overall_score"].notna()].copy()
ranked_df = ranked_df.sort_values("overall_score", ascending=False).drop_duplicates(subset=["apply_id"], keep="first")
errors_df = df[df["rank_error"].notna() & df["overall_score"].isna()]

filtered = ranked_df.copy()
if verdicts:
    filtered = filtered[filtered["recommendation"].isin(verdicts)]
filtered = filtered[filtered["overall_score"] >= min_score]
if search:
    s = search.lower()
    mask = (
        filtered["candidate_name"].str.lower().str.contains(s, na=False)
        | filtered["apply_id"].astype(str).str.lower().str.contains(s, na=False)
        | filtered.get("email", pd.Series([""]*len(filtered), index=filtered.index)).str.lower().str.contains(s, na=False)
        | filtered.get("mobile", pd.Series([""]*len(filtered), index=filtered.index)).astype(str).str.lower().str.contains(s, na=False)
        | filtered.get("degree", pd.Series([""]*len(filtered), index=filtered.index)).str.lower().str.contains(s, na=False)
        | filtered.get("university", pd.Series([""]*len(filtered), index=filtered.index)).str.lower().str.contains(s, na=False)
        | filtered.get("experience_detail", pd.Series([""]*len(filtered), index=filtered.index)).str.lower().str.contains(s, na=False)
    )
    filtered = filtered[mask]
filtered = filtered.sort_values(sort_key, ascending=False).reset_index(drop=True)

# ── Header ───────────────────────────────────────────────────────────────────
job_info      = job_rows[job_rows["job_label"] == job_label].iloc[0] if not job_rows.empty else {}
title_display = str(job_info.get("job_title") or job_label) if hasattr(job_info, "get") else job_label
dept_label    = get_job_department(conn, job_label)

is_day   = st.session_state.get("day_mode", True)
txt_col  = "#1E293B" if is_day else "#E2E8F0"
sub_col  = "#64748B"
card_bg  = "#FFFFFF" if is_day else "#1E2435"
card_bdr = "#E2E8F0" if is_day else "#2D3748"
body_col = "#374151" if is_day else "#CBD5E1"

st.markdown(f'<div class="page-title" style="color:{txt_col} !important;">Job Rankings</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="page-sub">{title_display} · {job_label} '
    f'&nbsp;<span style="display:inline-block;padding:2px 10px;border-radius:10px;'
    f'background:#FFF1F2;color:#C8102E !important;font-size:0.75rem;font-weight:600;'
    f'letter-spacing:0.04em;margin-left:4px;">{dept_label}</span></div>',
    unsafe_allow_html=True,
)

# ── Open Roles Header ───────────────────────────────────────────────────────────
st.markdown(
    f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};margin-top:1rem;">All Open Roles</div>',
    unsafe_allow_html=True,
)

# Get candidate counts for all BDJobs roles
role_counts = {}
for label in BDJOBS_JOB_REGISTRY.keys():
    try:
        role_df = fetch_candidates(conn, label)
        ranked_count = len(role_df[role_df["overall_score"].notna()])
        role_counts[label] = ranked_count
    except Exception:
        role_counts[label] = 0

# Group by department for better organization
dept_roles = {}
for label, meta in BDJOBS_JOB_REGISTRY.items():
    dept = meta.get("department", "Uncategorized")
    if dept not in dept_roles:
        dept_roles[dept] = []
    dept_roles[dept].append((label, meta, role_counts.get(label, 0)))

# Display roles by department
for dept in sorted(dept_roles.keys()):
    roles = dept_roles[dept]
    with st.expander(f"{dept} ({len(roles)} roles)", expanded=False):
        for label, meta, count in roles:
            has_candidates = count > 0
            status_color = "#16A34A" if has_candidates else "#94A3B8"
            status_text = f"{count} CV{'s' if count != 1 else ''}" if has_candidates else "0 CVs"
            status_bg = "#DCFCE7" if has_candidates else "#F1F5F9"
            
            st.markdown(f"""
            <div style="display:flex;align-items:center;justify-content:space-between;
                        background:{card_bg};border:1px solid {card_bdr};
                        border-radius:8px;padding:0.8rem;margin-bottom:0.5rem;">
                <div style="flex:1;">
                    <div style="font-weight:600;color:{txt_col};font-size:0.9rem;">
                        {meta.get('job_title', label)}
                    </div>
                    <div style="font-size:0.75rem;color:{sub_col};margin-top:2px;">
                        {meta.get('location', '-')} · {meta.get('experience', '-')}
                    </div>
                </div>
                <div style="text-align:right;">
                    <div style="font-weight:600;color:{status_color};font-size:0.85rem;">
                        {status_text}
                    </div>
                    <div style="font-size:0.7rem;color:{sub_col};margin-top:2px;">
                        {'Ranked' if has_candidates else 'No applications'}
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            # Navigation button
            if st.button("View →", key=f"role_nav_{label}", use_container_width=True):
                st.session_state["selected_job"] = label
                st.rerun()

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# BDJobs salary / location / experience strip
registry_meta = BDJOBS_JOB_REGISTRY.get(job_label, {})
salary_stated   = registry_meta.get("salary_stated", "Negotiable")
salary_estimate = registry_meta.get("salary_estimate", "")
location_label  = registry_meta.get("location", "")
experience_req  = registry_meta.get("experience", "")
if salary_stated or location_label:
    info_parts = []
    if location_label:
        info_parts.append(f"&#128205; {location_label}")
    if experience_req:
        info_parts.append(f"&#9200; {experience_req}")
    if salary_stated and salary_stated != "Negotiable":
        info_parts.append(f"&#128176; {salary_stated}")
    elif salary_estimate:
        info_parts.append(f"&#128176; Est. {salary_estimate}")

    st.markdown(
        f'<div style="font-size:0.8rem;color:#64748B;margin-bottom:0.5rem;">'
        + "  &nbsp;&middot;&nbsp;  ".join(info_parts)
        + '</div>',
        unsafe_allow_html=True,
    )
st.markdown('<hr class="divider">', unsafe_allow_html=True)

# ── Metrics ────────────────────────────────────────────────────────────────────
total   = len(df)
ranked  = len(ranked_df)
n_short = len(ranked_df[ranked_df["recommendation"] == "Shortlist"])
n_maybe = len(ranked_df[ranked_df["recommendation"] == "Maybe"])
n_rej   = len(ranked_df[ranked_df["recommendation"] == "Reject"])
showing = len(filtered)

for col, val, lbl in zip(
    st.columns(6),
    [total, ranked, n_short, n_maybe, n_rej, showing],
    ["Total Applicants","Processed","🟢 Shortlisted","🟡 Maybe","🔴 Rejected","Showing"],
):
    with col:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-val" style="font-size:1.8rem;">{val}</div>
                <div class="metric-lbl">{lbl}</div>
            </div>
        """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Export ─────────────────────────────────────────────────────────────────────
col_dl, col_info = st.columns([1,4])
with col_dl:
    if not filtered.empty:
        v_str = "+".join(verdicts) if verdicts else "all"
        st.download_button(
            "📥  Download Excel Report",
            data=to_excel(filtered, job_label),
            file_name=f"{job_label}_{v_str}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
with col_info:
    st.markdown(
        f'<div class="hint-text" style="padding-top:0.6rem;">'
        f'Showing {showing} of {ranked} ranked · Filter: {", ".join(verdicts) if verdicts else "none"}'
        f' · Score ≥ {min_score} · Sort: {sort_lbl}</div>',
        unsafe_allow_html=True,
    )

st.markdown(
    '<div class="hint-text" style="margin-bottom:0.5rem;">← Click any row to view candidate details below</div>',
    unsafe_allow_html=True,
)

# ── Table ──────────────────────────────────────────────────────────────────────
if filtered.empty:
    st.info("No candidates match current filters.")
    st.stop()

disp = filtered.copy()
disp["#"]           = range(1, len(disp) + 1)
disp["verdict"]     = disp["recommendation"].map(
    lambda v: f"{VERDICT_CFG.get(v,{}).get('icon','')} {v}"
)
disp["strengths_s"] = disp["strengths"].apply(lambda x: " · ".join(x[:2]) if isinstance(x,list) else "")
disp["gaps_s"]      = disp["gaps"].apply(lambda x: " · ".join(x[:2]) if isinstance(x,list) else "")
disp["flags_s"]     = disp["risk_flags"].apply(lambda x: " · ".join(x[:2]) if isinstance(x,list) else "")
disp["cv"]          = disp["has_uploaded_cv"].map(lambda x: "✓" if x else "")

cols_show = [
    "#","candidate_name","cv",
    "overall_score","skills_score","experience_score",
    "leadership_score","education_score","culture_fit_score",
    "experience_years","verdict",
    "strengths_s","gaps_s","flags_s","reasoning",
    "bdjobs_score","application_date","age","expected_salary","current_salary",
]
cols_show = [c for c in cols_show if c in disp.columns]

rename = {
    "#":"#","candidate_name":"Name","cv":"CV",
    "overall_score":"Overall","skills_score":"Skills","experience_score":"Exp. Score",
    "leadership_score":"Lead.","education_score":"Edu.","culture_fit_score":"Culture",
    "experience_years":"Exp (yrs)","verdict":"Verdict",
    "strengths_s":"Strengths","gaps_s":"Weaknesses","flags_s":"Risk Flags",
    "reasoning":"AI Summary",
    "bdjobs_score":"BDJobs (ref)","application_date":"Applied",
    "age":"Age","expected_salary":"Exp. Salary","current_salary":"Cur. Salary",
}

table = disp[cols_show].rename(columns=rename)

event = st.dataframe(
    table,
    use_container_width=True,
    height=460,
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    column_config={
        "#":          st.column_config.NumberColumn("#",          width="small"),
        "Overall":    st.column_config.ProgressColumn("Overall",    min_value=0, max_value=100, format="%d"),
        "Skills":     st.column_config.ProgressColumn("Skills",     min_value=0, max_value=100, format="%d"),
        "Exp. Score": st.column_config.ProgressColumn("Exp. Score", min_value=0, max_value=100, format="%d"),
        "Lead.":      st.column_config.ProgressColumn("Lead.",      min_value=0, max_value=100, format="%d"),
        "Edu.":       st.column_config.ProgressColumn("Edu.",       min_value=0, max_value=100, format="%d"),
        "Culture":    st.column_config.ProgressColumn("Culture",    min_value=0, max_value=100, format="%d"),
        "Exp (yrs)":  st.column_config.NumberColumn("Exp (yrs)",    format="%.1f"),
        "AI Summary": st.column_config.TextColumn("AI Summary",    width="large"),
        "CV":         st.column_config.TextColumn("CV",             width="small"),
    },
    key="rankings_table",
)

# ── FEAT-01: Compare candidates side-by-side ───────────────────────────────────
if not filtered.empty:
    with st.expander("⚖️  Compare candidates side-by-side", expanded=False):
        _name_by_id = filtered.set_index("apply_id")["candidate_name"].to_dict()
        compare_ids = st.multiselect(
            "Select 2–3 candidates to compare",
            options=filtered["apply_id"].tolist(),
            format_func=lambda aid: f"{_name_by_id.get(aid, aid)}  ({aid})",
            max_selections=3,
            key=f"compare_selection_{job_label}",
        )
        if len(compare_ids) >= 2:
            if st.button("Open Comparison →", type="secondary"):
                st.session_state["compare_ids"] = compare_ids
                st.session_state["compare_job"] = job_label
                st.switch_page("pages/6_Compare_Candidates.py")
        elif compare_ids:
            st.caption("Pick at least 2 candidates to compare.")

# ── Candidate detail panel ─────────────────────────────────────────────────────
st.markdown('<hr class="divider">', unsafe_allow_html=True)

selected_rows = event.selection.rows if event and event.selection else []

if not selected_rows:
    st.markdown(
        f'<div style="text-align:center;padding:2.5rem;font-size:0.9rem;color:{sub_col} !important;">'
        f'↑ Click a row in the table above to view candidate details</div>',
        unsafe_allow_html=True,
    )
else:
    row_idx  = selected_rows[0]
    sel      = filtered.iloc[row_idx]
    verdict  = str(sel.get("recommendation") or "")
    override = str(sel.get("hr_override") or "")
    display_verdict = override if override else verdict
    vcfg     = VERDICT_CFG.get(display_verdict, {"color":"#64748B","bg":"#F1F5F9","icon":"◆","dark_bg":"#1E293B","dark_color":"#94A3B8"})
    score    = int(sel.get("overall_score") or 0)
    score_color = "#16A34A" if score >= 70 else "#D97706" if score >= 50 else "#DC2626"
    apply_id = str(sel.get("apply_id") or "")

    st.markdown(
        f'<div class="section-hd" style="color:{sub_col} !important;border-bottom-color:{card_bdr};">Candidate Detail</div>',
        unsafe_allow_html=True,
    )

    col_left, col_right = st.columns([3, 2], gap="large")

    with col_left:
        name     = sel.get("candidate_name") or "—"
        email    = sel.get("email") or ""
        mobile   = sel.get("mobile") or ""
        location = sel.get("location") or ""
        degree   = sel.get("degree") or ""
        univ     = sel.get("university") or ""
        app_date = sel.get("application_date") or "—"
        age_val  = int(sel["age"]) if pd.notna(sel.get("age")) else "—"
        exp_yrs  = sel.get("experience_years") or "—"

        contact_parts = [p for p in [email, mobile, location] if p]
        edu_parts     = [p for p in [degree, univ] if p]

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
                            Applied: {app_date} &nbsp;·&nbsp;
                            Age: {age_val} &nbsp;·&nbsp;
                            Exp: {exp_yrs} yrs
                        </div>
                    </div>
                    <div style="text-align:right;flex-shrink:0;">
                        <div style="font-size:3rem;font-weight:700;color:{score_color} !important;line-height:1;">{score}</div>
                        <div style="font-size:0.72rem;font-weight:500;color:{sub_col} !important;text-transform:uppercase;letter-spacing:0.1em;">Overall Score</div>
                        <div style="margin-top:6px;">
                            <span class="verdict-badge verdict-{display_verdict.lower()}">{vcfg['icon']} {display_verdict}</span>
                        </div>
                        {f'<div style="font-size:0.7rem;color:{sub_col} !important;margin-top:3px;">HR Override</div>' if override else ''}
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # Score pills
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
        st.markdown(f'<div style="margin-bottom:1rem;">{pills}</div>', unsafe_allow_html=True)

        # Education sub-score breakdown (Part 7.1) — only if any sub-score is set
        edu_tier   = sel.get("edu_tier_score")
        edu_degree = sel.get("edu_degree_score")
        edu_gpa    = sel.get("edu_gpa_score")
        if any(v is not None and int(v) > 0 for v in [edu_tier, edu_degree, edu_gpa]):
            with st.expander("📚  Education breakdown (Tier · Degree · GPA)", expanded=False):
                edu_cols = st.columns(3)
                for col_, label_, sc_, weight_ in zip(
                    edu_cols,
                    ["University Tier", "Degree Level", "GPA / Result"],
                    [edu_tier, edu_degree, edu_gpa],
                    ["50%", "30%", "20%"],
                ):
                    with col_:
                        sc_val = int(sc_) if sc_ is not None else 0
                        color  = "#16A34A" if sc_val >= 70 else "#D97706" if sc_val >= 50 else "#DC2626"
                        st.markdown(
                            f'<div style="background:{card_bg};border:1px solid {card_bdr};'
                            f'border-radius:8px;padding:0.8rem;text-align:center;">'
                            f'<div style="font-size:0.7rem;color:{sub_col} !important;'
                            f'text-transform:uppercase;letter-spacing:0.08em;font-weight:500;">'
                            f'{label_} &nbsp;·&nbsp; {weight_}</div>'
                            f'<div style="font-size:1.8rem;font-weight:700;color:{color} !important;'
                            f'line-height:1.1;margin-top:3px;">{sc_val}</div></div>',
                            unsafe_allow_html=True,
                        )
                st.caption("education_score = tier × 0.50 + degree × 0.30 + gpa × 0.20 (capped at 50 when role requirement not met).")

        # Cross-job application badge (Part 7.7)
        dup_matches = find_duplicate_applications(
            apply_id    = apply_id,
            email       = str(sel.get("email") or "").strip() or None,
            mobile      = str(sel.get("mobile") or "").strip() or None,
            exclude_job = job_label,
        )
        if dup_matches:
            chips = "".join(
                f'<span style="display:inline-block;background:#EFF6FF;color:#1E3A5F !important;'
                f'border:1px solid #BFDBFE;border-radius:10px;padding:2px 10px;font-size:0.76rem;'
                f'font-weight:500;margin:2px 4px 2px 0;">'
                f'{m.get("job_title") or m.get("job_label")} — {m.get("recommendation") or "?"}'
                f' ({m.get("overall_score") if m.get("overall_score") is not None else "—"})'
                f'</span>'
                for m in dup_matches
            )
            st.markdown(
                f'<div style="margin-bottom:1rem;">'
                f'<span style="font-size:0.72rem;font-weight:600;color:{sub_col} !important;'
                f'text-transform:uppercase;letter-spacing:0.08em;">Also applied for</span><br>'
                f'<div style="margin-top:4px;">{chips}</div></div>',
                unsafe_allow_html=True,
            )

        # Salary row
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

        # AI Summary
        st.markdown(f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">AI Summary</div>', unsafe_allow_html=True)
        reasoning = sel.get("reasoning") or "—"
        st.markdown(
            f'<div style="font-size:0.92rem;color:{body_col} !important;line-height:1.75;padding:0.5rem 0 1rem;">{reasoning}</div>',
            unsafe_allow_html=True,
        )

        # Strengths / Weaknesses
        col_s, col_w = st.columns(2)
        with col_s:
            st.markdown(f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Strengths</div>', unsafe_allow_html=True)
            for s in (sel.get("strengths") or []):
                st.markdown(f'<div style="font-size:0.88rem;color:#16A34A !important;margin-bottom:5px;">✓ &nbsp;{s}</div>', unsafe_allow_html=True)
        with col_w:
            st.markdown(f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Weaknesses</div>', unsafe_allow_html=True)
            for g in (sel.get("gaps") or []):
                st.markdown(f'<div style="font-size:0.88rem;color:#D97706 !important;margin-bottom:5px;">⚠ &nbsp;{g}</div>', unsafe_allow_html=True)

        # Risk flags
        flags = sel.get("risk_flags") or []
        if flags:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Risk Flags</div>', unsafe_allow_html=True)
            chips = "".join(f'<span class="flag-chip">⚑ {f}</span>' for f in flags)
            st.markdown(f'<div style="padding:0.3rem 0;">{chips}</div>', unsafe_allow_html=True)

        # Experience
        exp_det = sel.get("experience_detail") or ""
        if exp_det:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Experience</div>', unsafe_allow_html=True)
            for entry in exp_det.split("|"):
                entry = entry.strip().replace("*","").replace("##"," — ")
                if entry:
                    st.markdown(
                        f'<div style="font-size:0.86rem;color:{body_col} !important;margin-bottom:5px;'
                        f'padding-left:0.6rem;border-left:2px solid {card_bdr};">• {entry}</div>',
                        unsafe_allow_html=True,
                    )

    with col_right:
        # Score chart
        st.markdown(f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Score Breakdown</div>', unsafe_allow_html=True)
        chart_data = pd.DataFrame({
            "Dimension": ["Skills","Experience","Leadership","Education","Culture Fit"],
            "Score": [
                sel.get("skills_score") or 0,
                sel.get("experience_score") or 0,
                sel.get("leadership_score") or 0,
                sel.get("education_score") or 0,
                sel.get("culture_fit_score") or 0,
            ],
        })
        st.bar_chart(chart_data.set_index("Dimension"), height=240, color="#C8102E")

        # PDF download only in right column
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Resume</div>', unsafe_allow_html=True)

        pdf_path = str(sel.get("pdf_path") or "")
        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            safe_name = str(name).replace(" ","_").replace("/","_")
            st.download_button(
                "📄  Download Resume PDF",
                pdf_bytes,
                file_name=f"{safe_name}_cv.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        else:
            st.markdown(
                f'<div style="font-size:0.86rem;color:{sub_col} !important;padding:0.5rem 0;">No uploaded CV available.</div>',
                unsafe_allow_html=True,
            )
            
        
        # HR Actions
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">HR Actions</div>', unsafe_allow_html=True)

        override_options = ["", "Shortlist", "Maybe", "Reject"]
        current_override_idx = override_options.index(override) if override in override_options else 0

        new_override = st.selectbox(
            "Override AI Recommendation",
            override_options,
            index=current_override_idx,
            key=f"override_{apply_id}",
            format_func=lambda x: "— No override —" if x == "" else x,
        )
        hr_note = st.text_area(
            "Internal Note",
            value=str(sel.get("hr_note") or ""),
            placeholder="Add internal note about this candidate...",
            height=80,
            key=f"note_{apply_id}",
        )
        if st.button("💾  Save HR Decision", type="primary", key=f"save_{apply_id}", use_container_width=True):
            save_hr_override(job_label, apply_id, new_override, hr_note)
            st.success("Saved successfully.")
            st.rerun()

        # HR override audit trail (Part 7.5)
        audit_df = fetch_audit_log(job_label=job_label, apply_id=apply_id)
        if not audit_df.empty:
            with st.expander(f"🕒  HR override history ({len(audit_df)})", expanded=False):
                show = audit_df[["changed_at", "hr_user", "old_value", "new_value", "note"]].copy()
                show.columns = ["When", "HR User", "From", "To", "Note"]
                show["When"] = pd.to_datetime(show["When"]).dt.strftime("%Y-%m-%d %H:%M")
                show["From"] = show["From"].fillna("").replace("", "—")
                show["To"]   = show["To"].fillna("").replace("", "—")
                st.dataframe(show, use_container_width=True, hide_index=True)

# ── Full width PDF viewer (only when a row is selected) ──────────────────────
if selected_rows:
    pdf_path = str(sel.get("pdf_path") or "")
    if pdf_path and os.path.exists(pdf_path):
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Resume Viewer</div>',
            unsafe_allow_html=True,
        )

        view_key = f"view_pdf_{apply_id}"
        if view_key not in st.session_state:
            st.session_state[view_key] = False

        # Read state BEFORE the button so label reflects current state correctly
        is_open = st.session_state[view_key]

        if st.button(
            "✕  Close PDF Viewer" if is_open else "🔍  View PDF in Browser",
            key=f"btn_pdf_{apply_id}",
            type="secondary",
        ):
            st.session_state[view_key] = not is_open
            st.rerun()

        if st.session_state[view_key]:
            with open(pdf_path, "rb") as f:
                pdf_bytes_view = f.read()
            b64 = base64.b64encode(pdf_bytes_view).decode("utf-8")
            st.markdown(
                f'<iframe src="data:application/pdf;base64,{b64}" '
                f'width="100%" height="820px" style="border:1px solid {card_bdr};border-radius:8px;margin-top:0.5rem;"></iframe>',
                unsafe_allow_html=True,
            )

# ── Errors ─────────────────────────────────────────────────────────────────────
if not errors_df.empty:
    with st.expander(f"⚠️ Failed rankings ({len(errors_df)})", expanded=False):
        st.dataframe(
            errors_df[["apply_id","candidate_name","rank_error","ranked_at"]],
            use_container_width=True,
            hide_index=True,
        )