"""
Home.py — Dashboard.  Department-grouped job postings, live metrics, and
a quick UI to assign departments to Uncategorized jobs.

Run: streamlit run resume_app/Home.py
"""
import streamlit as st

from db import (
    get_conn,
    fetch_all_jobs, fetch_departments, fetch_global_stats, set_job_department,
    get_css, init_theme, render_sidebar,
    DEPARTMENT_LIST,
    BDJOBS_JOB_REGISTRY,
)

st.set_page_config(
    page_title="HR Intelligence — Olympic Industries",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)
init_theme()
st.markdown(get_css(), unsafe_allow_html=True)
render_sidebar()

try:
    conn = get_conn()
except Exception as e:
    st.error(f"Database connection failed: {e}")
    st.stop()

stats     = fetch_global_stats(conn)
jobs_df   = fetch_all_jobs(conn)
dept_rows = fetch_departments(conn)

# ── Colour tokens ──────────────────────────────────────────────────────────────
is_day   = st.session_state.get("day_mode", True)
txt_col  = "#1E293B" if is_day else "#E2E8F0"
sub_col  = "#64748B"
card_bg  = "#FFFFFF" if is_day else "#1E2435"
card_bdr = "#E2E8F0" if is_day else "#2D3748"
bar_bg   = "#E2E8F0" if is_day else "#2D3748"
bar_fill = "#C8102E"

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown(
    f'<div class="page-title" style="color:{txt_col} !important;">Dashboard</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="page-sub">AI-powered resume ranking pipeline — Olympic Industries PLC</div>',
    unsafe_allow_html=True,
)
st.markdown(
    f'<hr class="divider" style="border-top:1px solid {card_bdr}">',
    unsafe_allow_html=True,
)

# ── Metrics strip (now 5 live cards) ───────────────────────────────────────────
active_depts = len(dept_rows)
total_short  = sum(r.get("shortlist", 0) for r in dept_rows)

metrics = [
    (active_depts,                     "Active Departments"),
    (stats["total_jobs"],              "Job Postings"),
    (stats["total_candidates"],        "Total Candidates"),
    (stats["total_candidates"] - stats["pending"], "Ranked"),
    (total_short,                      "🟢 Shortlists"),
]
for col, (val, lbl) in zip(st.columns(5), metrics):
    with col:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-val" style="color:{txt_col} !important;">{val}</div>
                <div class="metric-lbl" style="color:{sub_col} !important;">{lbl}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("<br>", unsafe_allow_html=True)

# ── Quick-jump: Department + Job selector ─────────────────────────────────────
st.markdown(
    f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">'
    'Open Rankings</div>',
    unsafe_allow_html=True,
)

col_dept, col_job, col_btn = st.columns([2, 3, 1])
with col_dept:
    all_depts_with_data = [r["department"] for r in dept_rows] or ["Uncategorized"]
    sel_dept = st.selectbox(
        "Department",
        all_depts_with_data,
        key="quickjump_dept",
        label_visibility="visible",
    )
with col_job:
    dept_jobs = []
    if not jobs_df.empty:
        dept_jobs = jobs_df[jobs_df["department"].fillna("Uncategorized") == sel_dept]["job_label"].tolist()
    dept_jobs = dept_jobs or ["— no postings —"]
    sel_job = st.selectbox(
        "Job Posting",
        dept_jobs,
        key="quickjump_job",
        label_visibility="visible",
    )
with col_btn:
    st.markdown("<div style='height:1.6rem'></div>", unsafe_allow_html=True)
    if st.button("OPEN  →", type="primary", use_container_width=True):
        if sel_job and sel_job != "— no postings —":
            st.session_state["selected_dept"] = sel_dept
            st.session_state["selected_job"]  = sel_job
            st.switch_page("pages/1_Department_Rankings.py")

st.markdown("<br>", unsafe_allow_html=True)

# ── Department-grouped job postings ────────────────────────────────────────────
st.markdown(
    f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">'
    'Active Job Postings</div>',
    unsafe_allow_html=True,
)

if jobs_df.empty:
    st.info("No job postings yet. Use **New Job Posting** to register one.")
else:
    # Group by department
    jobs_df = jobs_df.copy()
    jobs_df["department"] = jobs_df["department"].fillna("Uncategorized")
    # Sort groups: non-Uncategorized first by name, Uncategorized last
    dept_names = sorted(
        jobs_df["department"].unique(),
        key=lambda d: (d == "Uncategorized", d),
    )

    status_cls = {
        "Complete":   "status-complete",
        "Processing": "status-processing",
        "Pending":    "status-pending",
        "Error":      "status-error",
    }

    def _open_roles_count(dept_name: str) -> int:
        return sum(1 for m in BDJOBS_JOB_REGISTRY.values() if m.get("department") == dept_name)

    for dept in dept_names:
        group = jobs_df[jobs_df["department"] == dept]
        open_roles = _open_roles_count(dept)
        with st.expander(
            f"{dept}  ({len(group)} posting{'s' if len(group) != 1 else ''}) · {open_roles} open role{'s' if open_roles != 1 else ''}",
            expanded=True,
        ):
            for _, row in group.iterrows():
                total  = int(row.get("total") or 0)
                ranked = int(row.get("ranked") or 0)
                short  = int(row.get("shortlisted") or 0)
                avg    = row.get("avg_score") or "—"
                status = str(row.get("status") or "Pending")
                title  = str(row.get("job_title") or row["job_label"])
                label  = str(row["job_label"])
                posted = str(row.get("created_at") or "")
                last   = str(row.get("last_ranked_at") or "—")
                prog   = int(ranked / total * 100) if total > 0 else 0
                scls   = status_cls.get(status, "status-pending")

                col_main, col_action = st.columns([6, 1])
                with col_main:
                    st.markdown(
                        f"""
                        <div style="background:{card_bg};border:1px solid {card_bdr};border-radius:8px;
                                    padding:1rem 1.2rem;margin-bottom:0.6rem;">
                            <div style="display:flex;align-items:center;gap:0.6rem;flex-wrap:wrap;margin-bottom:4px;">
                                <span style="font-size:0.95rem;font-weight:600;color:{txt_col} !important;">{title}</span>
                                <span class="status-badge {scls}">{status}</span>
                                <span style="font-size:0.72rem;color:{sub_col} !important;">· {label}</span>
                            </div>
                            <div style="font-size:0.8rem;color:{sub_col} !important;margin-bottom:8px;">
                                Posted {posted} &nbsp;·&nbsp; {ranked}/{total} ranked &nbsp;·&nbsp;
                                🟢 {short} shortlisted &nbsp;·&nbsp; Avg score: {avg} &nbsp;·&nbsp; Last run: {last}
                            </div>
                            <div style="background:{bar_bg};border-radius:4px;height:5px;">
                                <div style="background:{bar_fill};width:{prog}%;height:5px;border-radius:4px;"></div>
                            </div>
                            <div style="font-size:0.72rem;color:#94A3B8 !important;margin-top:3px;">{prog}% processed</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with col_action:
                    st.markdown("<div style='height:0.4rem'></div>", unsafe_allow_html=True)
                    if st.button(
                        "View Results",
                        key=f"view_{label}",
                        type="primary",
                        use_container_width=True,
                    ):
                        st.session_state["selected_job"]     = label
                        st.session_state["jr_active_job"]    = label
                        st.session_state["jr_mode"]          = "detail"
                        st.session_state["jr_incoming_via"]  = "dashboard"
                        st.session_state["selected_dept"]    = dept
                        st.switch_page("pages/2_Job_Rankings.py")

# ── Assign Departments UI (only shows if there are Uncategorized jobs) ────────
if not jobs_df.empty:
    uncategorised = jobs_df[jobs_df["department"] == "Uncategorized"]
    if not uncategorised.empty:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">'
            f'Assign Departments  ·  {len(uncategorised)} pending</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "Legacy jobs created before department support — assign the correct "
            "department to unlock department-level rankings."
        )
        for _, row in uncategorised.iterrows():
            label = str(row["job_label"])
            col_lbl, col_sel, col_btn = st.columns([4, 3, 1])
            with col_lbl:
                st.markdown(
                    f'<div style="padding-top:0.6rem;font-size:0.9rem;'
                    f'color:{txt_col} !important;">{label}</div>',
                    unsafe_allow_html=True,
                )
            with col_sel:
                dept_choice = st.selectbox(
                    "Department",
                    DEPARTMENT_LIST,
                    key=f"assign_dept_{label}",
                    label_visibility="collapsed",
                )
            with col_btn:
                if st.button("SAVE", key=f"save_dept_{label}", type="primary", use_container_width=True):
                    set_job_department(conn, label, dept_choice)
                    st.success(f"{label} → {dept_choice}")
                    st.rerun()
