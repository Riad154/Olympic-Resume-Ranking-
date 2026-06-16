"""
Home.py — Dashboard.  Department-grouped job postings, live metrics, and
a quick UI to assign departments to Uncategorized jobs.

Run: streamlit run resume_app/Home.py
"""
import streamlit as st

from db import (
    get_conn,
    fetch_all_jobs, fetch_departments, fetch_global_stats, set_job_department,
    get_css, init_theme, render_sidebar, safe_switch_page,
    DEPARTMENT_LIST, FAVICON,
)

st.set_page_config(
    page_title="HR Intelligence — Olympic Industries",
    page_icon=FAVICON,
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
    (stats["total_candidates"],        "Total Candidates"),
    (stats["total_candidates"] - stats["pending"], "Ranked"),
    (total_short,                      "🟢 Shortlists"),
]
for col, (val, lbl) in zip(st.columns(4), metrics):
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
