"""
2_Job_Rankings.py — Job Rankings page (Landing-first navigation flow)
Olympic Industries PLC — HR Intelligence Platform
"""

import os
import io
import base64
import requests
import pandas as pd
import streamlit as st
from pathlib import Path
from datetime import datetime

# ── Shared data layer ─────────────────────────────────────────────────────────
from db import (
    get_conn, log_audit,
    t,
    fetch_candidates,
    fetch_departments_with_roles,
    fetch_all_jobs,
    save_hr_override,
    fetch_audit_log,
    to_excel,
    find_duplicate_applications,
    delete_candidate,
    delete_candidates_bulk,
    delete_job,
    get_active_processing,
    render_processing_banner,
    init_theme,
    render_sidebar,
    safe_switch_page,
    _is_streamlit_cloud, FAVICON,
)

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Job Rankings",
    page_icon=FAVICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Theme / CSS ───────────────────────────────────────────────────────────────
CSS = """
<style>
:root {
  --brand: #C8102E;
  --brand-dark: #8A0B1F;
  --accent: #2D6A4F;
  --card-bg: #ffffff;
  --card-bdr: #e2e8f0;
  --page-bg: #F8FAFC;
  --txt: #0F172A;
  --sub: #475569;
  --divider: #E2E8F0;
}
[data-testid="stAppViewContainer"] {
  background-color: var(--page-bg);
}
.section-hd {
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--txt);
  border-bottom: 2px solid var(--divider);
  padding-bottom: 0.4rem;
  margin-bottom: 1rem;
}
.hint-text {
  font-size: 0.85rem;
  color: var(--sub);
  font-weight: 500;
}
.cand-name-lg {
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--txt);
  line-height: 1.2;
}
.cand-meta-sm {
  font-size: 0.78rem;
  color: var(--sub);
  margin-top: 2px;
}
.verdict-badge {
  display: inline-block;
  padding: 4px 14px;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  color: #fff;
  margin-top: 4px;
}
.verdict-shortlist { background: #16A34A; }
.verdict-maybe      { background: #D97706; }
.verdict-reject     { background: #DC2626; }
.score-pill {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 0.72rem;
  font-weight: 600;
  margin-right: 5px;
  margin-bottom: 5px;
}
.score-green  { background: #DCFCE7; color: #166534; }
.score-yellow { background: #FEF3C7; color: #92400E; }
.score-red    { background: #FEE2E2; color: #991B1B; }
.flag-chip {
  display: inline-block;
  background: #FFF1F2;
  color: #9B1C31;
  border: 1px solid #FECDD3;
  border-radius: 6px;
  padding: 2px 8px;
  font-size: 0.7rem;
  margin: 2px 4px 2px 0;
}
.score-ring-container {
  position: relative;
  width: 120px;
  height: 120px;
}
.score-ring-bg {
  fill: none;
  stroke: #E2E8F0;
  stroke-width: 8;
}
.score-ring-fill {
  fill: none;
  stroke-width: 8;
  stroke-linecap: round;
  transform: rotate(-90deg);
  transform-origin: 50% 50%;
  transition: stroke-dashoffset 0.6s ease;
}
.dim-card {
  background: #ffffff;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  padding: 0.7rem 0.9rem;
  text-align: center;
}
.dim-label {
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #64748B;
  margin-bottom: 4px;
}
.dim-score {
  font-size: 1.4rem;
  font-weight: 700;
  line-height: 1.1;
}
.dim-bar-track {
  height: 4px;
  background: #E2E8F0;
  border-radius: 2px;
  margin-top: 6px;
  overflow: hidden;
}
.dim-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.4s ease;
}
.strength-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 8px;
  background: #F0FDF4;
  border-left: 3px solid #16A34A;
  border-radius: 0 6px 6px 0;
  margin-bottom: 6px;
  font-size: 0.82rem;
  color: #14532D;
}
.gap-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 8px;
  background: #FFFBEB;
  border-left: 3px solid #D97706;
  border-radius: 0 6px 6px 0;
  margin-bottom: 6px;
  font-size: 0.82rem;
  color: #78350F;
}
.timeline-item {
  position: relative;
  padding-left: 16px;
  padding-bottom: 12px;
  border-left: 2px solid #E2E8F0;
  margin-left: 6px;
}
.timeline-item::before {
  content: '';
  position: absolute;
  left: -5px;
  top: 2px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #C8102E;
}
.salary-badge {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 0.82rem;
  font-weight: 600;
}
.profile-card {
  background: #ffffff;
  border: 1px solid #E2E8F0;
  border-radius: 10px;
  padding: 1.2rem;
  margin-bottom: 1rem;
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ── Initialize theme (matches Department Rankings) ────────────────────────────
init_theme()

# ── Colour helpers ──────────────────────────────────────────────────────────
day_mode = st.session_state.get("day_mode", True)
card_bg   = "#ffffff" if day_mode else "#1E293B"
card_bdr  = "#E2E8F0" if day_mode else "#334155"
txt_col   = "#0F172A" if day_mode else "#F1F5F9"
sub_col   = "#475569" if day_mode else "#94A3B8"
body_col  = "#334155" if day_mode else "#CBD5E1"
VERDICT_CFG = {
    "Shortlist": {"color":"#16A34A","bg":"#DCFCE7","icon":"✓","dark_bg":"#14532D","dark_color":"#BBF7D0"},
    "Maybe":     {"color":"#D97706","bg":"#FEF3C7","icon":"◆","dark_bg":"#78350F","dark_color":"#FDE68A"},
    "Reject":    {"color":"#DC2626","bg":"#FEE2E2","icon":"✗","dark_bg":"#7F1D1D","dark_color":"#FECACA"},
}

# ── Session-state guard (safe defaults) ─────────────────────────────────────
for key, default in [
    ("jr_mode",         "landing"),
    ("jr_active_job",   None),
    ("jr_last_dept",    None),
    ("selected_job",    None),
    ("jr_incoming_via", None),
    ("jr_verdicts",     None),
    ("jr_min_score",    0),
    ("jr_search",       ""),
    ("jr_sort",         "overall_score DESC"),
]:
    if key not in st.session_state:
        st.session_state[key] = default

try:
    conn = get_conn()
except Exception as e:
    conn = None
    st.error(f"Database connection failed: {e}")
    st.info("Check your PostgreSQL secrets in Streamlit Cloud settings.")
    st.stop()

# ── Live processing banner (visible while ranker subprocess is active) ────────
_active_jobs_jr = [r for r in get_active_processing() if r["is_running"]]
render_processing_banner()

# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR (using shared render_sidebar for consistency)
# ═══════════════════════════════════════════════════════════════════════════════
render_sidebar()

if not st.session_state.get("user"):
    st.warning("🔒 Please log in to access this page.")
    safe_switch_page("pages/0_Login.py")
    st.stop()


# ── Extra sidebar controls for Job Rankings ────────────────────────────────
with st.sidebar:
    # ── Back button (only in detail mode) ─────────────────────────────────────
    if st.session_state["jr_mode"] == "detail":
        st.markdown("<hr class='divider'>", unsafe_allow_html=True)
        if st.button("⬅  Back to All Roles", use_container_width=True, type="secondary"):
            st.session_state["jr_mode"]       = "landing"
            st.session_state["jr_active_job"] = None
            st.session_state["selected_job"]  = None
            st.session_state["jr_incoming_via"] = None
            st.rerun()

    # ── Detail-mode filters ────────────────────────────────────────────────────
    if st.session_state["jr_mode"] == "detail":
        st.markdown("<hr class='divider'>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='hint-text'>Filters — {st.session_state['jr_active_job']}</div>",
            unsafe_allow_html=True,
        )

        _verdicts = ["Shortlist", "Maybe", "Reject"]
        current_verdicts = st.session_state.get("jr_verdicts") or _verdicts
        verdicts = st.multiselect(
            "Verdict", _verdicts, default=current_verdicts,
            key="sb_verdicts",
        )
        st.session_state["jr_verdicts"] = verdicts

        min_score = st.slider(
            "Min Overall Score", 0, 100,
            st.session_state.get("jr_min_score", 0),
            key="sb_min_score",
        )
        st.session_state["jr_min_score"] = min_score

        sort_opts = {
            "overall_score DESC":  "Overall Score (High → Low)",
            "overall_score ASC":   "Overall Score (Low → High)",
            "ranked_at DESC":      "Recently Ranked",
            "candidate_name ASC":  "Name (A → Z)",
            "recommendation":      "Verdict (Shortlist first)",
        }
        sort_key = st.selectbox(
            "Sort by", list(sort_opts.keys()),
            index=list(sort_opts.keys()).index(st.session_state.get("jr_sort", "overall_score DESC")),
            format_func=lambda k: sort_opts[k],
            key="sb_sort",
        )
        st.session_state["jr_sort"] = sort_key

        search = st.text_input(
            "🔎  Search name or apply ID", value=st.session_state.get("jr_search", ""),
            key="sb_search",
        )
        st.session_state["jr_search"] = search

    # ── Theme toggle ─────────────────────────────────────────────────────────
    st.markdown("<hr class='divider'>", unsafe_allow_html=True)
    dm = st.toggle("🌞 / 🌙", value=st.session_state.get("day_mode", True), key="day_toggle")
    st.session_state["day_mode"] = dm

    # ── Live auto-refresh while ranker is running ────────────────────────────
    if _active_jobs_jr:
        st.markdown("<hr class='divider'>", unsafe_allow_html=True)
        _auto_refresh_jr = st.checkbox(
            "🔄 Auto-refresh (5s)", value=True,
            help="Live-refresh while ranking is in progress.",
            key="jr_auto_refresh",
        )
    else:
        _auto_refresh_jr = False

# ═══════════════════════════════════════════════════════════════════════════════
# LANDING MODE — All Open Roles (accordion by department)
# ═══════════════════════════════════════════════════════════════════════════════

def render_landing():
    st.markdown(
        f"<div class='section-hd' style='font-size:1.4rem;margin-bottom:0.2rem;color:{txt_col} !important;'>"
        f"All Open Roles</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div class='hint-text' style='margin-bottom:1.5rem;'>"
        f"Select a department below, then click <b>View Rankings →</b> on any role to see ranked candidates."
        f"</div>",
        unsafe_allow_html=True,
    )

    # Search box (landing only)
    search_term = st.text_input(
        "🔎  Search roles or departments", "",
        placeholder="e.g. SAP, Finance, Manager...",
        key="landing_search",
    )

    # Fetch departments and keep only roles that have ranked candidates
    depts = fetch_departments_with_roles(conn)
    clean_depts = []
    for dept in depts:
        roles = [r for r in dept.get("roles", []) if r.get("ranked", 0) > 0]
        if roles:
            dept = dict(dept)
            dept["roles"] = roles
            dept["total_roles"] = len(roles)
            dept["total_applicants"] = sum(r.get("total", 0) for r in roles)
            dept["total_ranked"] = sum(r.get("ranked", 0) for r in roles)
            clean_depts.append(dept)

    # Apply search filter if user typed something
    search_lower = search_term.lower()
    display_depts = []
    for dept in clean_depts:
        dept_name = dept.get("department") or "Uncategorized"
        if search_term:
            roles = [
                r for r in dept.get("roles", [])
                if search_lower in (r.get("job_title") or "").lower()
                or search_lower in (r.get("job_label") or "").lower()
                or search_lower in dept_name.lower()
            ]
        else:
            roles = dept.get("roles", [])
        if roles:
            d = dict(dept)
            d["roles"] = roles
            d["total_roles"] = len(roles)
            d["total_applicants"] = sum(r.get("total", 0) for r in roles)
            d["total_ranked"] = sum(r.get("ranked", 0) for r in roles)
            display_depts.append(d)

    if display_depts:
        for dept in display_depts:
            dept_name = dept.get("department") or "Uncategorized"
            label = (
                f"{dept_name}  ·  "
                f"{dept.get('total_roles', 0)} role(s)  ·  "
                f"{dept.get('total_applicants', 0)} applicant(s)  ·  "
                f"{dept.get('total_ranked', 0)} ranked"
            )
            with st.expander(label, expanded=True):
                for role in dept.get("roles", []):
                    _render_role_card(role)
    else:
        st.info(
            "🎉 Welcome to the HR Ranking Platform.\n\n"
            "Use the search box above to find roles, or go to "
            "**Download/Upload CVs** to fetch applicants and start ranking."
        )


def _render_role_card(role: dict):
    label = role.get("job_label", "")
    title = role.get("job_title") or label
    status = role.get("status") or "Pending"
    salary = role.get("salary_range") or "Negotiable"
    location = role.get("location") or "Bangladesh"
    min_exp = role.get("min_experience") or "Any"
    edu_req = role.get("education_req") or "Any"
    total = int(role.get("total") or 0)
    ranked = int(role.get("ranked") or 0)
    errors = int(role.get("errors") or 0)
    avg_score = role.get("avg_score")

    skills = role.get("required_skills") or []
    skill_chips = ""
    if skills:
        skill_chips = "".join(
            f'<span style="display:inline-block;background:#F1F5F9;color:#334155 !important;'
            f'border:1px solid #E2E8F0;border-radius:10px;padding:2px 10px;font-size:0.72rem;'
            f'margin:2px 4px 2px 0;">{s}</span>'
            for s in skills[:6]
        )
        if len(skills) > 6:
            skill_chips += f'<span style="font-size:0.72rem;color:{sub_col} !important;">+{len(skills)-6} more</span>'

    meta_html = (
        f'<span style="font-size:0.8rem;color:{sub_col} !important;">'
        f'📍 {location}  ·  💰 {salary}  ·  🎓 {edu_req}  ·  ⏳ {min_exp}'
        f'</span>'
    )

    status_color = "#16A34A" if status.lower() == "open" else "#D97706"
    status_badge = (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:999px;font-size:0.7rem;'
        f'font-weight:600;color:#fff;background:{status_color};">{status.upper()}</span>'
    )

    score_badge = ""
    if avg_score is not None:
        score_color = "#16A34A" if avg_score >= 70 else "#D97706" if avg_score >= 50 else "#DC2626"
        score_badge = (
            f' <span style="display:inline-block;padding:2px 10px;border-radius:999px;font-size:0.7rem;'
            f'font-weight:600;color:#fff;background:{score_color};">Avg {avg_score}</span>'
        )

    error_badge = ""
    if errors:
        error_badge = (
            f' <span style="display:inline-block;padding:2px 10px;border-radius:999px;font-size:0.7rem;'
            f'font-weight:600;color:#fff;background:#DC2626;">{errors} errors</span>'
        )

    st.markdown(f"""
        <div style="background:{card_bg};border:1px solid {card_bdr};border-radius:10px;
                    padding:1rem 1.2rem;margin-bottom:0.8rem;">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;">
                <div style="flex:1;min-width:0;">
                    <div style="font-size:1.05rem;font-weight:600;color:{txt_col} !important;line-height:1.2;">
                        {title}
                    </div>
                    <div style="margin-top:4px;">{meta_html}</div>
                    <div style="margin-top:8px;">{skill_chips}</div>
                </div>
                <div style="text-align:right;flex-shrink:0;">
                    <div>{status_badge}{score_badge}{error_badge}</div>
                    <div style="font-size:0.78rem;color:{sub_col} !important;margin-top:6px;">
                        {ranked} / {total} ranked
                    </div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("View Rankings →", key=f"open_{label}", use_container_width=True, type="primary"):
            st.session_state["jr_last_dept"] = _dept_for_label(label)
            st.session_state["selected_job"]   = label
            st.session_state["jr_active_job"]  = label
            st.session_state["jr_mode"]        = "detail"
            st.session_state["jr_incoming_via"] = "landing"
            st.rerun()
    with col2:
        if st.button("View Role Details", key=f"details_{label}", use_container_width=True, type="secondary"):
            st.session_state["jr_last_dept"] = _dept_for_label(label)
            st.session_state["selected_job"]   = label
            st.session_state["jr_active_job"]  = label
            st.session_state["jr_mode"]        = "detail"
            st.session_state["jr_incoming_via"] = "landing"
            st.rerun()
    with col3:
        confirm_key = f"jr_confirm_del_{label}"
        if st.session_state.get(confirm_key):
            st.warning("Delete this job?")
            c_y, c_n = st.columns(2)
            with c_y:
                if st.button("Yes", key=f"jr_yes_del_{label}", type="primary", use_container_width=True):
                    res = delete_job(label)
                    st.success(
                        f"Deleted `{label}` — {res['candidates_deleted']} candidate(s), "
                        f"{res['audit_deleted']} audit row(s). "
                        + ("Folder removed." if res["folder_removed"] else "Folder kept.")
                    )
                    st.session_state[confirm_key] = False
                    st.rerun()
            with c_n:
                if st.button("No", key=f"jr_no_del_{label}", use_container_width=True):
                    st.session_state[confirm_key] = False
                    st.rerun()
        else:
            if st.button("🗑️ Delete", key=f"jr_del_{label}", use_container_width=True):
                st.session_state[confirm_key] = True
                st.rerun()


def _dept_for_label(job_label: str) -> str | None:
    """Look up department for a given job_label from the registry or DB."""
    try:
        for entry in fetch_departments_with_roles(conn):
            for r in entry.get("roles", []):
                if r.get("job_label") == job_label:
                    return entry.get("department")
    except Exception:
        pass
    return None

def _fetch_pdf_from_vm(pdf_path: str, job_label: str, apply_id: str = "") -> tuple[bytes | None, str | None]:
    """Fetch PDF bytes from the remote VM via Tailscale URL when on Streamlit Cloud.
    Returns (pdf_bytes, working_url) tuple."""
    try:
        # Try multiple secret key paths
        vm_url = ""
        if "services" in st.secrets:
            vm_url = st.secrets["services"].get("OLLAMA_HOST", "")
        if not vm_url and "OLLAMA_HOST" in st.secrets:
            vm_url = st.secrets["OLLAMA_HOST"]
        if not vm_url:
            return None, None

        # Normalize Windows backslashes so basename works on Linux
        normalized_path = pdf_path.replace("\\", "/")
        filename = os.path.basename(normalized_path)
        if not filename:
            return None, None

        # Build a list of candidate folder names to try
        folders_to_try = [job_label]

        # Extract folder name from the pdf_path itself (parent of uploaded_cvs)
        path_parts = normalized_path.split("/")
        for i, part in enumerate(path_parts):
            if part == "uploaded_cvs" and i > 0:
                parent_folder = path_parts[i - 1]
                if parent_folder and parent_folder not in folders_to_try:
                    folders_to_try.append(parent_folder)
                break

        # Try to extract numeric job_id from apply_id (e.g. "1344660_Arif_...")
        if apply_id:
            parts = apply_id.split("_")
            if parts and parts[0].isdigit():
                if parts[0] not in folders_to_try:
                    folders_to_try.append(parts[0])

        # Also try extracting job_id from filename prefix (e.g. "1344660_Arif_...pdf")
        fname_parts = filename.split("_")
        if fname_parts and fname_parts[0].isdigit():
            if fname_parts[0] not in folders_to_try:
                folders_to_try.append(fname_parts[0])

        for folder in folders_to_try:
            remote_url = f"{vm_url.rstrip('/')}/resumes/{folder}/uploaded_cvs/{filename}"
            resp = requests.get(remote_url, timeout=15)
            if resp.status_code == 200:
                return resp.content, remote_url
    except Exception:
        pass
    return None, None

# ═══════════════════════════════════════════════════════════════════════════════
# DETAIL MODE — Ranked candidates for a single job
# ═══════════════════════════════════════════════════════════════════════════════

def render_detail():
    job_label = st.session_state.get("jr_active_job")
    if not job_label:
        st.warning("No job selected. Use the sidebar or go back to choose a role.")
        return

    # Breadcrumb
    incoming = st.session_state.get("jr_incoming_via") or "manual"
    via_label = {
        "dashboard": "Dashboard",
        "dept":      "Department Rankings",
        "landing":   "All Open Roles",
        "manual":    "Navigation",
    }.get(incoming, "Navigation")

    st.markdown(
        f'<div style="font-size:0.78rem;color:{sub_col} !important;margin-bottom:0.4rem;">'
        f'{via_label} &nbsp;&rsaquo;&nbsp; <span style="color:{txt_col};font-weight:500;">{job_label}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Title + action bar
    st.markdown(
        f"<div class='section-hd' style='font-size:1.3rem;color:{txt_col} !important;'>"
        f"🏆  {job_label}</div>",
        unsafe_allow_html=True,
    )

    # ── Load data ─────────────────────────────────────────────────────────
    all_df = fetch_candidates(conn, job_label=job_label)
    if all_df.empty or "overall_score" not in all_df.columns:
        st.info("No candidates have been loaded or ranked for this job yet.")
        if st.button("← Back to all roles"):
            st.session_state.pop("selected_job", None)
            st.rerun()
        st.stop()
    ranked_df = all_df[all_df["overall_score"].notna()].copy()
    errors_df = all_df[all_df["rank_error"].notna() & all_df["overall_score"].isna()].copy()

    if not ranked_df.empty:
        ranked_df = ranked_df.reset_index(drop=True)
        ranked_df["rank"] = range(1, len(ranked_df) + 1)

    # ── Filters ───────────────────────────────────────────────────────────
    verdicts = st.session_state.get("jr_verdicts") or ["Shortlist", "Maybe", "Reject"]
    min_score = st.session_state.get("jr_min_score", 0)
    search = st.session_state.get("jr_search", "").strip().lower()
    sort_key = st.session_state.get("jr_sort", "overall_score DESC")

    def _apply_filters(df):
        if df.empty:
            return df
        mask = df["recommendation"].isin(verdicts)
        mask &= (df["overall_score"].fillna(0) >= min_score)
        if search:
            mask &= (
                df["candidate_name"].fillna("").str.lower().str.contains(search, na=False)
                | df["apply_id"].fillna("").str.lower().str.contains(search, na=False)
            )
        return df[mask].copy()

    filtered = _apply_filters(ranked_df)

    # Unranked candidates (for export sheet 2)
    _unranked_all = all_df[all_df["overall_score"].isna() & all_df["rank_error"].isna()].copy()

    # Summary metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Candidates", len(all_df))
    c2.metric("Ranked", len(ranked_df))
    c3.metric("Filtered", len(filtered))
    c4.metric("Errors", len(errors_df))

    # ── Verdict health warning ────────────────────────────────────────────
    if not ranked_df.empty:
        canonical = {"Shortlist", "Maybe", "Reject"}
        bad = ranked_df[~ranked_df["recommendation"].isin(canonical)]
        if not bad.empty:
            st.warning(
                f"⚠️ **{len(bad)} candidate(s)** have non-standard verdicts "
                f"({', '.join(bad['recommendation'].unique())}). "
                "Go to **Settings → Database Maintenance → Normalise Verdicts** to fix."
            )

    # ── Export button (visible even if filters hide all ranked candidates) ───────
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    excel_bytes = to_excel(ranked_df, job_label, unranked_df=_unranked_all if not _unranked_all.empty else None)
    st.download_button(
        "⬇  Export to Excel",
        excel_bytes,
        file_name=f"{job_label}_rankings_{ts}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"export_{job_label}",
        use_container_width=True,
    )

    # ── Compare candidates section ───────────────────────────────────────────
    if not filtered.empty:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f'<div class="section-hd" style="color:{sub_col} !important;'
            f'border-bottom:1px solid {card_bdr};">Compare Candidates</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="hint-text" style="margin-bottom:0.8rem;">'
            f'Select 2–3 candidates to compare side-by-side</div>',
            unsafe_allow_html=True,
        )
        compare_options = {
            str(r["apply_id"]): f"{r['candidate_name']} ({r['apply_id']}) — Score: {int(r['overall_score'] or 0)}"
            for _, r in filtered.iterrows()
        }
        selected_compare = st.multiselect(
            "Pick candidates",
            options=list(compare_options.keys()),
            default=st.session_state.get("jr_compare_ids", []),
            format_func=lambda k: compare_options.get(k, k),
            key="jr_compare_select",
        )
        st.session_state["jr_compare_ids"] = selected_compare

        c1, c2 = st.columns([1, 4])
        with c1:
            if st.button(
                "⚖️  Open Comparison",
                use_container_width=True,
                type="primary",
                disabled=len(selected_compare) < 2 or len(selected_compare) > 3,
            ):
                st.session_state["compare_ids"] = selected_compare
                st.session_state["compare_job"] = job_label
                safe_switch_page("pages/6_Compare_Candidates.py")
        with c2:
            if len(selected_compare) < 2:
                st.caption("Select at least 2 candidates to compare.")
            elif len(selected_compare) > 3:
                st.caption("Maximum 3 candidates allowed. Please remove some.")
            else:
                st.caption(f"Ready: {len(selected_compare)} candidates selected.")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Sorting ────────────────────────────────────────────────────────────
    if not filtered.empty:
        if sort_key == "overall_score DESC":
            filtered = filtered.sort_values("overall_score", ascending=False)
        elif sort_key == "overall_score ASC":
            filtered = filtered.sort_values("overall_score", ascending=True)
        elif sort_key == "ranked_at DESC":
            filtered = filtered.sort_values("ranked_at", ascending=False, na_position="last")
        elif sort_key == "candidate_name ASC":
            filtered = filtered.sort_values("candidate_name", ascending=True)
        elif sort_key == "recommendation":
            order = {"Shortlist": 0, "Maybe": 1, "Reject": 2}
            filtered["_rec_order"] = filtered["recommendation"].map(order).fillna(99)
            filtered = filtered.sort_values(["_rec_order", "overall_score"], ascending=[True, False])
            filtered = filtered.drop(columns=["_rec_order"])

    # ── Candidate table ──────────────────────────────────────────────────
    display_cols = [
        "rank", "apply_id", "candidate_name", "overall_score",
        "skills_score", "experience_score", "leadership_score",
        "education_score", "culture_fit_score",
        "recommendation", "experience_years",
    ]
    available = [c for c in display_cols if c in filtered.columns]

    # Selection mode toggle (single for detail view, multi for bulk actions)
    sel_mode = st.session_state.get("jr_sel_mode", "single-row")

    event = st.dataframe(
        filtered[available] if not filtered.empty else pd.DataFrame(),
        use_container_width=True,
        hide_index=True,
        column_config={
            "rank":            st.column_config.NumberColumn("Rank", width="small"),
            "apply_id":        st.column_config.TextColumn("Apply ID", width="medium"),
            "candidate_name":  st.column_config.TextColumn("Name", width="medium"),
            "overall_score":   st.column_config.NumberColumn("Overall", width="small"),
            "skills_score":    st.column_config.NumberColumn("Skills", width="small"),
            "experience_score": st.column_config.NumberColumn("Experience", width="small"),
            "leadership_score": st.column_config.NumberColumn("Leadership", width="small"),
            "education_score":  st.column_config.NumberColumn("Education", width="small"),
            "culture_fit_score": st.column_config.NumberColumn("Culture", width="small"),
            "recommendation":  st.column_config.TextColumn("Verdict", width="small"),
            "experience_years": st.column_config.NumberColumn("Exp (yrs)", width="small"),
        },
        on_select="rerun",
        selection_mode=sel_mode,
        key=f"table_{job_label}",
    )

    # ── Bulk delete bar (shown when multiple rows selected) ────────────
    selected_rows_all = event.selection.rows if event and event.selection else []
    if sel_mode == "multi-row" and selected_rows_all:
        sel_ids = [str(filtered.iloc[i]["apply_id"]) for i in selected_rows_all if i < len(filtered)]
        sel_names = [str(filtered.iloc[i]["candidate_name"]) for i in selected_rows_all if i < len(filtered)]
        st.warning(f"**{len(sel_ids)} candidate(s) selected:** {', '.join(sel_names[:5])}{'...' if len(sel_names) > 5 else ''}")
        bc1, bc2 = st.columns([1, 4])
        with bc1:
            if st.button(f"🗑️  Delete {len(sel_ids)} Selected", type="primary", key="bulk_del"):
                st.session_state["jr_confirm_bulk_del"] = sel_ids
        with bc2:
            if st.button("Cancel", key="bulk_del_cancel"):
                st.session_state.pop("jr_confirm_bulk_del", None)
                st.session_state["jr_sel_mode"] = "single-row"
                st.rerun()
        if st.session_state.get("jr_confirm_bulk_del"):
            st.error(f"⚠️ **Confirm deletion** of {len(sel_ids)} candidate(s)? This cannot be undone.")
            if st.button("✅ Yes, permanently delete them", key="bulk_del_confirm"):
                count = delete_candidates_bulk(job_label, sel_ids)
                st.session_state.pop("jr_confirm_bulk_del", None)
                st.session_state["jr_sel_mode"] = "single-row"
                st.success(f"Deleted {count} candidate(s).")
                st.rerun()

    # Toggle button for selection mode
    mode_col1, mode_col2 = st.columns([1, 5])
    with mode_col1:
        if sel_mode == "single-row":
            if st.button("☑ Multi-select mode", key="toggle_multi"):
                st.session_state["jr_sel_mode"] = "multi-row"
                st.rerun()
        else:
            if st.button("☐ Single-select mode", key="toggle_single"):
                st.session_state["jr_sel_mode"] = "single-row"
                st.rerun()

    # ── Candidate detail panel ───────────────────────────────────────────
    st.markdown("<hr class='divider'>", unsafe_allow_html=True)
    selected_rows = event.selection.rows if event and event.selection else []

    if not selected_rows:
        st.markdown(
            f'<div style="text-align:center;padding:2.5rem;font-size:0.9rem;'
            f'color:{sub_col} !important;">'
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
        name     = sel.get("candidate_name") or "—"
        
        # PDF handling - moved to top so accessible throughout
        pdf_path = str(sel.get("pdf_path") or "")
        pdf_exists = pdf_path and os.path.exists(pdf_path)
        pdf_bytes = None
        pdf_url = None
        if pdf_exists:
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
        elif pdf_path and _is_streamlit_cloud():
            # Fallback: fetch from remote VM when on Streamlit Cloud
            pdf_bytes, pdf_url = _fetch_pdf_from_vm(pdf_path, job_label, apply_id)
            pdf_exists = bool(pdf_bytes)
        
        safe_name = str(name).replace(" ", "_").replace("/", "_")
        
        st.markdown(
            f'<div class="section-hd" style="color:{sub_col} !important;border-bottom-color:{card_bdr};">Candidate Detail</div>',
            unsafe_allow_html=True,
        )
        
        col_left, col_right = st.columns([3, 2], gap="large")
        
        with col_left:
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

            # Profile completeness check (use pdf_exists instead of re-checking)
            prof_fields = [name!="—", bool(email), bool(mobile), bool(degree), bool(univ), bool(pdf_exists)]
            prof_pct    = int(sum(prof_fields)/len(prof_fields)*100)
        
            # Profile card
            override_badge = f'&nbsp;·&nbsp;<span style="color:#64748B;font-weight:600;">HR Override Active</span>' if override else ''
            profile_card = (
                f'<div style="background:{card_bg};border:1px solid {card_bdr};'
                f'border-left:4px solid {vcfg["color"]};'
                f'border-radius:10px;padding:1.4rem;margin-bottom:1rem;">'
                f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:1.2rem;">'
                f'<div style="flex:1;min-width:0;">'
                f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:4px;">'
                f'<div class="cand-name-lg" style="color:{txt_col} !important;">{name}</div>'
                f'<span class="verdict-badge verdict-{display_verdict.lower()}">{vcfg["icon"]} {display_verdict}</span>'
                f'</div>'
                f'<div class="cand-meta-sm" style="color:{sub_col} !important;">✉ {" · ".join(contact_parts)}</div>'
                f'<div class="cand-meta-sm" style="color:{sub_col} !important;">🎓 {" — ".join(edu_parts)}</div>'
                f'<div class="cand-meta-sm" style="color:{sub_col} !important;margin-top:6px;">'
                f'ID: <b>{apply_id}</b> &nbsp;·&nbsp; Job: <b>{job_label}</b> &nbsp;·&nbsp; Applied: <b>{app_date}</b> &nbsp;·&nbsp; Age: <b>{age_val}</b> &nbsp;·&nbsp; Exp: <b>{exp_yrs} yrs</b>'
                f'{override_badge}'
                f'</div>'
                f'</div>'
                f'</div>'
                f'</div>'
            )
            st.markdown(profile_card, unsafe_allow_html=True)
        
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
        
                # Salary & financial info
            exp_sal_raw = sel.get("expected_salary")
            cur_sal_raw = sel.get("current_salary")
            bd_score_raw = sel.get("bdjobs_score")
            has_cv_raw = sel.get("has_uploaded_cv")

            exp_sal = str(exp_sal_raw).strip() if exp_sal_raw and str(exp_sal_raw).strip() else "—"
            cur_sal = str(cur_sal_raw).strip() if cur_sal_raw and str(cur_sal_raw).strip() else "—"
            bd_score = str(bd_score_raw).strip() if bd_score_raw and str(bd_score_raw).strip() else "—"
            has_cv = "✅" if has_cv_raw else "❌"
            cv_color = "#16A34A" if has_cv_raw else "#DC2626"

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
        
                # AI Summary
            st.markdown(f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">AI Summary</div>', unsafe_allow_html=True)
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
                st.markdown(f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">🌟 Strengths</div>', unsafe_allow_html=True)
                strengths_list = sel.get("strengths") or []
                if strengths_list:
                    for s in strengths_list:
                        st.markdown(f'<div class="strength-item"><span style="font-size:1rem;flex-shrink:0;">✓</span><span>{s}</span></div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div style="font-size:0.82rem;color:{sub_col};padding:6px 0;">No explicit strengths recorded.</div>', unsafe_allow_html=True)
            with col_w:
                st.markdown(f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">🚧 Gaps & Weaknesses</div>', unsafe_allow_html=True)
                gaps_list = sel.get("gaps") or []
                if gaps_list:
                    for g in gaps_list:
                        st.markdown(f'<div class="gap-item"><span style="font-size:1rem;flex-shrink:0;">⚠</span><span>{g}</span></div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div style="font-size:0.82rem;color:{sub_col};padding:6px 0;">No explicit gaps recorded.</div>', unsafe_allow_html=True)
        
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
                st.markdown(f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">💼 Experience</div>', unsafe_allow_html=True)
                exp_entries = [e.strip().replace("*","").replace("##"," — ") for e in exp_det.split("|") if e.strip()]
                for entry in exp_entries:
                    st.markdown(
                        f'<div class="timeline-item" style="font-size:0.84rem;color:{body_col} !important;line-height:1.55;">'
                        f'<span style="font-weight:600;color:{txt_col} !important;">{entry}</span></div>',
                        unsafe_allow_html=True,
                    )
        
        with col_right:
                # Score breakdown panel with Overall Score at top
            st.markdown(f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Score Breakdown</div>', unsafe_allow_html=True)
            
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
            
            # Dimension score bars with weights
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
            st.markdown(f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">📄 Resume</div>', unsafe_allow_html=True)

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
                user = st.session_state.get("user", {})
                log_audit(conn, user.get("id"), user.get("username"), "SAVE_HR_OVERRIDE",
                          target_type="candidate", target_id=apply_id,
                          details=f"Job: {job_label} | Override: {new_override}")
                st.success("Saved successfully.")
                st.rerun()

            # Delete candidate button
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(
                f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Danger Zone</div>',
                unsafe_allow_html=True,
            )
            del_key = f"del_confirm_{apply_id}"
            if del_key not in st.session_state:
                st.session_state[del_key] = False

            if not st.session_state[del_key]:
                if st.button("🗑️  Delete This Candidate", type="secondary", key=f"del_{apply_id}", use_container_width=True):
                    st.session_state[del_key] = True
                    st.rerun()
            else:
                st.error(f"⚠️ **Permanently delete {name}** (ID: {apply_id}) from this job? This cannot be undone.")
                dc1, dc2 = st.columns(2)
                with dc1:
                    if st.button("✅ Confirm Delete", type="primary", key=f"del_yes_{apply_id}", use_container_width=True):
                        ok = delete_candidate(job_label, apply_id)
                        st.session_state[del_key] = False
                        if ok:
                            st.success(f"Deleted {name} successfully.")
                        else:
                            st.error("Candidate not found or already deleted.")
                        st.rerun()
                with dc2:
                    if st.button("Cancel", key=f"del_no_{apply_id}", use_container_width=True):
                        st.session_state[del_key] = False
                        st.rerun()

            # Re-rank button for candidates with suspect scores
            all_dim_scores = [int(sel.get(k) or 0) for k in ["skills_score","experience_score","leadership_score","education_score","culture_fit_score"]]
            is_suspect = (len(set(all_dim_scores)) == 1 and all_dim_scores[0] > 0) or all(s == 0 for s in all_dim_scores)
            if is_suspect:
                st.warning("⚠️ This candidate may have been scored incorrectly (all dimensions are identical). Consider re-ranking.")
            if st.button("🔄  Re-rank This Candidate", type="secondary", key=f"rerank_{apply_id}", use_container_width=True):
                if _is_streamlit_cloud():
                    _ollama_url = ""
                    try:
                        if "services" in st.secrets and "OLLAMA_HOST" in st.secrets["services"]:
                            _ollama_url = str(st.secrets["services"]["OLLAMA_HOST"]).strip()
                        elif "OLLAMA_HOST" in st.secrets:
                            _ollama_url = str(st.secrets["OLLAMA_HOST"]).strip()
                    except Exception:
                        pass
                    if not _ollama_url or _ollama_url.startswith("http://localhost"):
                        st.error(
                            "❌ Re-ranking requires a remote Ollama server. "
                            "Configure OLLAMA_HOST in Streamlit secrets."
                        )
                        st.stop()
                try:
                    import subprocess as _sp
                    from pathlib import Path as _Path
                    from db import RANKER_PATH, VENV_PYTHON, RESUMES_BASE
                    _env = os.environ.copy()
                    try:
                        if "services" in st.secrets:
                            svc = st.secrets["services"]
                            if "OLLAMA_HOST" in svc: _env["OLLAMA_HOST"] = str(svc["OLLAMA_HOST"]).strip()
                            if "OLLAMA_MODEL" in svc: _env["OLLAMA_MODEL"] = str(svc["OLLAMA_MODEL"]).strip()
                        if "postgresql" in st.secrets:
                            pg = st.secrets["postgresql"]
                            _env.setdefault("PG_HOST", str(pg.get("host", "")).strip())
                            _env.setdefault("PG_PORT", str(pg.get("port", "5432")).strip())
                            _env.setdefault("PG_DBNAME", str(pg.get("dbname", "")).strip())
                            _env.setdefault("PG_USER", str(pg.get("user", "")).strip())
                            _env.setdefault("PG_PASSWORD", str(pg.get("password", "")).strip())
                    except Exception:
                        pass
                    cmd = [VENV_PYTHON, RANKER_PATH, "--job", job_label, "--rerank-id", apply_id]
                    with st.spinner(f"Re-ranking {name}..."):
                        result = _sp.run(cmd, capture_output=True, text=True, timeout=180,
                                         cwd=str(_Path(RESUMES_BASE).parent), env=_env)
                    if result.returncode == 0:
                        st.success(f"✅ Re-ranked {name} successfully. Refreshing...")
                        st.rerun()
                    else:
                        st.error(f"Re-rank failed: {result.stderr[:300]}")
                        if result.stdout:
                            with st.expander("Ranker output"):
                                st.code(result.stdout[-500:])
                except Exception as e:
                    st.error(f"Re-rank error: {e}")
        
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
        # Use pdf_exists and pdf_bytes from top-level (already defined when row selected)
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Resume Viewer</div>',
            unsafe_allow_html=True,
        )
        
        if not pdf_exists:
            st.error("📄 No resume uploaded for this candidate.")
        else:
            # Buttons row: Open / Download
            col_link, col_download = st.columns([1, 1])
            with col_link:
                if pdf_url:
                    # Streamlit Cloud: open in new tab (iframes blocked by CSP)
                    st.link_button(
                        "🔍 Open in New Tab",
                        url=pdf_url,
                        type="primary",
                        use_container_width=True,
                    )
                else:
                    st.markdown(
                        '<div style="text-align:center;padding:0.5rem 0;color:#64748B;font-size:0.85rem;">'
                        'PDF viewer below ⬇️</div>',
                        unsafe_allow_html=True,
                    )
            with col_download:
                st.download_button(
                    "⬇ Download PDF",
                    pdf_bytes,
                    file_name=f"{safe_name}_resume.pdf",
                    mime="application/pdf",
                    key=f"dl_pdf_{apply_id}",
                    use_container_width=True,
                )

            # Full-width PDF viewer — rendered outside columns so it spans the whole page
            if not pdf_url and pdf_bytes and pdf_bytes[:4] == b"%PDF":
                try:
                    b64 = base64.b64encode(pdf_bytes).decode("utf-8")
                    st.markdown(
                        f'<iframe src="data:application/pdf;base64,{b64}" '
                        f'width="100%" height="920px" style="border:1px solid {card_bdr};border-radius:8px;margin-top:0.8rem;"></iframe>',
                        unsafe_allow_html=True,
                    )
                except Exception as e:
                    st.error(f"❌ Failed to load PDF: {str(e)}")

    # ── Errors ─────────────────────────────────────────────────────────────────────
    if not errors_df.empty:
        with st.expander(f"⚠️ Failed rankings ({len(errors_df)})", expanded=False):
            st.dataframe(
                errors_df[["apply_id","candidate_name","rank_error","ranked_at"]],
                use_container_width=True,
                hide_index=True,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# MODE DISPATCH
# ═══════════════════════════════════════════════════════════════════════════════

if st.session_state["jr_mode"] == "landing":
    render_landing()
else:
    render_detail()

# ── Auto-refresh while live processing is happening ───────────────────────────
if _auto_refresh_jr and _active_jobs_jr:
    import time as _time
    _time.sleep(5)
    st.rerun()
