"""
Home.py — Dashboard. Department-grouped job postings, live metrics,
department activity, recent jobs, active processing alerts, and quick actions.

Run: streamlit run resume_app/Home.py
"""
import streamlit as st

from db import (
    get_conn,
    fetch_all_jobs, fetch_departments, fetch_global_stats, set_job_department,
    get_active_processing,
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

if not st.session_state.get("user"):
    st.warning("🔒 Please log in to access this page.")
    safe_switch_page("pages/0_Login.py")
    st.stop()

# Deferred navigation from Quick Actions — st.switch_page must run at top level
_nav = st.session_state.pop("_navigate_to", None)
if _nav:
    safe_switch_page(_nav)

try:
    conn = get_conn()
except Exception as e:
    st.error(f"Database connection failed: {e}")
    st.stop()

stats     = fetch_global_stats(conn)
jobs_df   = fetch_all_jobs(conn)
dept_rows = fetch_departments(conn)
active_runs = get_active_processing()

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
    f'''<div class="page-title" style="color:{txt_col} !important;">Dashboard</div>''',
    unsafe_allow_html=True,
)
st.markdown(
    '''<div class="page-sub">AI-powered resume ranking pipeline — Olympic Industries PLC</div>''',
    unsafe_allow_html=True,
)
st.markdown(
    f'''<hr class="divider" style="border-top:1px solid {card_bdr}">''',
    unsafe_allow_html=True,
)

# ── Animations CSS ─────────────────────────────────────────────────────────────
ANIMATION_CSS = """
<style>
@keyframes bannerSlideUp {
    from { opacity: 0; transform: translateY(30px); }
    to   { opacity: 1; transform: translateY(0); }
}
@keyframes shimmer {
    0%   { background-position: -200% center; }
    100% { background-position: 200% center; }
}
@keyframes trophyFloat {
    0%, 100% { transform: translateY(0) rotate(0deg); }
    25%      { transform: translateY(-6px) rotate(3deg); }
    75%      { transform: translateY(-3px) rotate(-2deg); }
}
@keyframes metricFadeIn {
    from { opacity: 0; transform: translateY(20px) scale(0.95); }
    to   { opacity: 1; transform: translateY(0) scale(1); }
}
@keyframes countPop {
    0%   { transform: scale(0.5); opacity: 0; }
    60%  { transform: scale(1.15); opacity: 1; }
    100% { transform: scale(1); opacity: 1; }
}
@keyframes textReveal {
    from { opacity: 0; transform: translateX(-15px); }
    to   { opacity: 1; transform: translateX(0); }
}

.banner-animated {
    animation: bannerSlideUp 0.7s ease-out both;
}
.banner-animated .banner-shimmer {
    background-size: 200% 200%;
    animation: shimmer 4s linear infinite;
}
.banner-animated .trophy-icon {
    animation: trophyFloat 3s ease-in-out infinite;
    display: inline-block;
}
.banner-animated .banner-title {
    animation: textReveal 0.6s ease-out 0.25s both;
}
.banner-animated .banner-sub {
    animation: textReveal 0.6s ease-out 0.45s both;
}

.metric-card-animated {
    animation: metricFadeIn 0.5s ease-out both;
    transition: transform 0.25s ease, box-shadow 0.25s ease;
}
.metric-card-animated:hover {
    transform: translateY(-4px);
    box-shadow: 0 6px 16px rgba(0,0,0,0.08);
}
.metric-card-animated .metric-val {
    animation: countPop 0.5s ease-out both;
}
</style>
"""
st.markdown(ANIMATION_CSS, unsafe_allow_html=True)

# ── Olympic × FIFA World Cup 2026 banner ───────────────────────────────────────
wc_bg    = "#0B3D2E" if is_day else "#0A2E23"
wc_accent = "#C8102E"
wc_text   = "#FFFFFF"
st.markdown(
    f"""
    <div style="
        background: linear-gradient(135deg, {wc_bg} 0%, #145A3E 50%, {wc_bg} 100%);
        border-radius: 12px;
        padding: 1.2rem 1.6rem;
        margin-bottom: 1.2rem;
        border-left: 5px solid {wc_accent};
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    ">
        <div style="display:flex;align-items:center;gap:1rem;">
            <div style="font-size:2.4rem;line-height:1;">⚽</div>
            <div>
                <div style="color:{wc_text};font-size:1.05rem;font-weight:700;letter-spacing:0.3px;">
                    Building the Winning Team — Olympic Industries PLC
                </div>
                <div style="color:rgba(255,255,255,0.75);font-size:0.82rem;margin-top:0.3rem;">
                    Just like the FIFA World Cup 2026 unites the best talent from 48 nations,
                    our AI-powered HR pipeline scouts, ranks, and assembles the perfect squad for every role.
                </div>
            </div>
        </div>
        <div style="text-align:center;min-width:80px;">
            <div style="font-size:1.8rem;line-height:1;">🏆</div>
            <div style="color:rgba(255,255,255,0.7);font-size:0.65rem;margin-top:0.2rem;">
                WE ARE 26
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Metrics strip (6 live cards) ───────────────────────────────────────────────
active_depts = len(dept_rows)
total_short  = sum(r.get("shortlist", 0) for r in dept_rows)
ranked_count = stats["total_candidates"] - stats["pending"]
rank_pct     = round((ranked_count / stats["total_candidates"] * 100), 1) if stats["total_candidates"] else 0

metrics = [
    (active_depts,              "Active Departments"),
    (stats["total_jobs"],       "Job Postings"),
    (stats["total_candidates"], "Total Candidates"),
    (stats["pending"],          "⏳ Pending"),
    (ranked_count,              f"⭐ Ranked  ({rank_pct}%)"),
    (total_short,               "🟢 Shortlists"),
]
for idx, (col, (val, lbl)) in enumerate(zip(st.columns(6), metrics)):
    delay = 0.08 * idx
    with col:
        st.markdown(
            f'''
            <div class="metric-card metric-card-animated" style="animation-delay:{delay:.2f}s;">
                <div class="metric-val" style="color:{txt_col} !important;animation-delay:{delay + 0.15:.2f}s;">{val}</div>
                <div class="metric-lbl" style="color:{sub_col} !important;">{lbl}</div>
            </div>
            ''',
            unsafe_allow_html=True,
        )

st.markdown("<br>", unsafe_allow_html=True)

# ── Two-column: Department Activity + Quick Actions / Active Runs ────────────
col_left, col_right = st.columns([2, 1])

with col_left:
    st.markdown(
        f'''<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">'
        'Department Activity</div>''',
        unsafe_allow_html=True,
    )
    if dept_rows:
        for d in dept_rows:
            dept_name = d["department"]
            total_c   = d["total_candidates"]
            ranked_c  = d["ranked_candidates"]
            short_c   = d["shortlist"]
            maybe_c   = d["maybe"]
            reject_c  = d["reject"]
            progress  = (ranked_c / total_c) if total_c else 0
            progress_color = "#16A34A" if progress >= 1 else ("#EAB308" if progress >= 0.5 else "#C8102E")

            st.markdown(
                f'''
                <div style="background:{card_bg};border:1px solid {card_bdr};border-radius:10px;padding:0.9rem 1.1rem;margin-bottom:0.6rem;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.4rem;">
                        <div style="font-weight:700;font-size:0.95rem;color:{txt_col} !important;">{dept_name}</div>
                        <div style="font-size:0.78rem;color:{sub_col} !important;">{d["job_count"]} job(s) · {total_c} candidate(s)</div>
                    </div>
                    <div style="background:{bar_bg};border-radius:6px;height:8px;overflow:hidden;margin-bottom:0.5rem;">
                        <div style="width:{progress*100:.1f}%;background:{progress_color};height:100%;border-radius:6px;transition:width 0.3s;"></div>
                    </div>
                    <div style="display:flex;gap:0.5rem;flex-wrap:wrap;">
                        <span class="verdict-badge verdict-shortlist">🟢 {short_c} Shortlist</span>
                        <span class="verdict-badge verdict-maybe">🟡 {maybe_c} Maybe</span>
                        <span class="verdict-badge verdict-reject">🔴 {reject_c} Reject</span>
                    </div>
                </div>
                ''',
                unsafe_allow_html=True,
            )
    else:
        st.info("No department data yet. Create job postings and upload CVs to get started.")

with col_right:
    # Quick Actions
    st.markdown(
        f'''<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">'
        'Quick Actions</div>''',
        unsafe_allow_html=True,
    )
    qa_col1, qa_col2 = st.columns(2)
    with qa_col1:
        if st.button("➕ New Job", use_container_width=True, type="secondary"):
            st.session_state["_navigate_to"] = "pages/3_New_Job.py"
            st.rerun()
        if st.button("📊 Job Rankings", use_container_width=True, type="secondary"):
            st.session_state["_navigate_to"] = "pages/2_Job_Rankings.py"
            st.rerun()
    with qa_col2:
        if st.button("⬆️ Upload CVs", use_container_width=True, type="secondary"):
            st.session_state["_navigate_to"] = "pages/0_Download_CVs.py"
            st.rerun()
        if st.button("⚙️ Processing", use_container_width=True, type="secondary"):
            st.session_state["_navigate_to"] = "pages/4_Processing_Status.py"
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # Active Processing
    st.markdown(
        f'''<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">'
        'Live Processing</div>''',
        unsafe_allow_html=True,
    )
    running = [r for r in active_runs if r["is_running"]]
    if running:
        for run in running:
            job = run["job"]
            proc = run["processed"]
            tot  = run["total"]
            errs = run["errors"]
            pct  = (proc / tot * 100) if tot else 0
            st.markdown(
                f'''
                <div style="background:{card_bg};border:1px solid {card_bdr};border-left:4px solid #3B82F6;border-radius:10px;padding:0.8rem 1rem;margin-bottom:0.5rem;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                    <div style="font-weight:600;font-size:0.9rem;color:{txt_col} !important;margin-bottom:0.3rem;">{job}</div>
                    <div style="background:{bar_bg};border-radius:6px;height:6px;overflow:hidden;margin-bottom:0.4rem;">
                        <div style="width:{pct:.0f}%;background:#3B82F6;height:100%;border-radius:6px;"></div>
                    </div>
                    <div style="font-size:0.75rem;color:{sub_col} !important;">{proc}/{tot} processed · {errs} error(s)</div>
                </div>
                ''',
                unsafe_allow_html=True,
            )
    else:
        done_recent = [r for r in active_runs if r["done"]]
        if done_recent:
            st.markdown(
                f'''<div style="font-size:0.85rem;color:{sub_col} !important;">✅ {len(done_recent)} recent run(s) completed. All quiet now.</div>''',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'''<div style="font-size:0.85rem;color:{sub_col} !important;">🟢 No active ranking runs. Start one from <b>Processing Status</b>.</div>''',
                unsafe_allow_html=True,
            )

st.markdown("<br>", unsafe_allow_html=True)

# ── Recent Jobs table ──────────────────────────────────────────────────────────
st.markdown(
    f'''<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">'
    'Recent Jobs</div>''',
    unsafe_allow_html=True,
)
if not jobs_df.empty:
    display_df = jobs_df[["job_label", "department", "total", "ranked", "shortlisted", "avg_score", "status", "last_ranked_at"]].copy()
    display_df.columns = ["Job", "Department", "Candidates", "Ranked", "Shortlist", "Avg Score", "Status", "Last Ranked"]
    # Add completion %
    display_df["Progress"] = display_df.apply(
        lambda r: f"{(r['Ranked'] / r['Candidates'] * 100):.0f}%" if r["Candidates"] > 0 else "—", axis=1
    )
    # Status badge helper
    def _status_badge(s):
        if s == "active":
            return "🟢 Active"
        elif s == "completed":
            return "✅ Done"
        elif s == "paused":
            return "⏸️ Paused"
        return f"⚪ {s.title()}"
    display_df["Status"] = display_df["Status"].apply(_status_badge)
    display_df = display_df[["Job", "Department", "Candidates", "Ranked", "Progress", "Shortlist", "Avg Score", "Status", "Last Ranked"]]
    st.dataframe(display_df.head(12), use_container_width=True, hide_index=True)
else:
    st.info("No jobs yet. Click **New Job** in Quick Actions to create your first posting.")

st.markdown("<br>", unsafe_allow_html=True)

# ── Quick-jump: Department + Job selector ─────────────────────────────────────
st.markdown(
    f'''<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">'
    'Open Rankings</div>''',
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
            safe_switch_page("pages/1_Department_Rankings.py")

st.markdown("<br>", unsafe_allow_html=True)

# ── Assign Departments UI (only shows if there are Uncategorized jobs) ────────
if not jobs_df.empty:
    uncategorised = jobs_df[jobs_df["department"] == "Uncategorized"]
    if not uncategorised.empty:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f'''<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">'
            f'Assign Departments  ·  {len(uncategorised)} pending</div>''',
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
                    f'''<div style="padding-top:0.6rem;font-size:0.9rem;'
                    f'color:{txt_col} !important;">{label}</div>''',
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
