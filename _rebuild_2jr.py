"""
Rebuild 2_Job_Rankings.py from scratch with correct indentation.
"""
import textwrap

# Read original file to extract candidate detail panel
with open(r'F:\Projects\resume_ranking\resume_app\pages\2_Job_Rankings.py', 'r', encoding='utf-8') as f:
    original = f.read()

# Find the detail panel in the original (from row_idx to just before Errors)
start_marker = "        row_idx  = selected_rows[0]"
end_marker = "# ── Errors"

start_idx = original.find(start_marker)
end_idx = original.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print(f"ERROR: Could not find markers. start={start_idx}, end={end_idx}")
    exit(1)

# Extract the detail panel (including the else: block)
# We need from "    else:" to just before "# ── Errors"
else_start = original.rfind("    else:", 0, start_idx)
detail_panel_raw = original[else_start:end_idx]

# The detail panel in the original is indented at 4 spaces for the else block
# In the new file, it needs to be at 4 spaces (inside the if/else that checks selected_rows)
# So we can use it almost as-is, but we need to make sure the indentation is correct

# Actually, the original detail panel is:
#     else:
#         row_idx = ...
#         ...
# This is 4 spaces for else, 8 for body. In the new file, it's inside:
#     if not selected_rows:
#         ...
#     else:
#         row_idx = ...
# Which is the same indentation! So we can use it as-is.

# But wait - in the new file, the context is:
#     if not selected_rows:
#         st.markdown(...)
#     else:
#         [detail panel]
# This is exactly the same as the original! So the indentation should match.

# Let me verify by checking the original context
orig_else = original[original.rfind("\n    else:", 0, start_idx):start_idx]
print(f"Original else context: {repr(orig_else[-50:])}")

# The detail panel should work as-is since the nesting is identical
# But let me check if there are any issues with the extraction
print(f"Detail panel length: {len(detail_panel_raw)} chars, {detail_panel_raw.count(chr(10))} lines")

# Build the new file
new_file = r'''"""
2_Job_Rankings.py — Job Rankings page (Landing-first navigation flow)
Olympic Industries PLC — HR Intelligence Platform
"""

import os
import io
import base64
import pandas as pd
import streamlit as st
from pathlib import Path
from datetime import datetime

# ── Shared data layer ─────────────────────────────────────────────────────────
from resume_app.db import (
    get_conn,
    t,
    fetch_candidates,
    fetch_departments_with_roles,
    fetch_all_jobs,
    export_candidates,
    save_hr_override,
    fetch_audit_log,
    to_excel,
    update_candidate_details,
    find_duplicate_applications,
    BDJOBS_JOB_REGISTRY,
)

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Job Rankings",
    page_icon="🏆",
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
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

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

conn = get_conn()
'''

# Sidebar
new_file += r'''
# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.image(str(Path(__file__).resolve().parent.parent / "plc_logo_w_text.png"), width=180)
    st.markdown("<hr class='divider'>", unsafe_allow_html=True)

    # ── Navigation links (always shown) ───────────────────────────────────────
    st.page_link("Home.py",                    label="📊  Dashboard")
    st.page_link("pages/2_Job_Rankings.py",    label="🏆  Job Rankings")
    st.page_link("pages/1_Department_Rankings.py", label="🏢  Department Rankings")
    st.page_link("pages/5_Settings.py",        label="⚙️  Settings")

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
'''

# Landing mode
new_file += r'''
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

    depts = fetch_departments_with_roles(conn)
    if not depts:
        st.info("No open roles found. Add a job posting from the Dashboard or Settings page.")
        return

    # Search box (landing only)
    search_term = st.text_input(
        "🔎  Search roles or departments", "",
        placeholder="e.g. SAP, Finance, Manager...",
        key="landing_search",
    )

    last_dept = st.session_state.get("jr_last_dept")

    for dept in depts:
        dept_name = dept.get("department") or "Uncategorized"
        roles = dept.get("roles", [])

        if search_term:
            search_lower = search_term.lower()
            roles = [
                r for r in roles
                if search_lower in (r.get("job_title") or "").lower()
                or search_lower in (r.get("job_label") or "").lower()
                or search_lower in dept_name.lower()
            ]
            if not roles:
                continue

        expand = (dept_name == last_dept)
        label = (
            f"{dept_name}  ·  "
            f"{dept.get('total_roles', 0)} role(s)  ·  "
            f"{dept.get('total_applicants', 0)} applicant(s)  ·  "
            f"{dept.get('total_ranked', 0)} ranked"
        )

        with st.expander(label, expanded=expand):
            for role in roles:
                _render_role_card(role)


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

    col1, col2 = st.columns([1, 1])
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
'''

# Detail mode header
new_file += r'''
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

    # Summary metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Candidates", len(all_df))
    c2.metric("Ranked", len(ranked_df))
    c3.metric("Filtered", len(filtered))
    c4.metric("Errors", len(errors_df))

    # Export button
    if not filtered.empty:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        excel_bytes = to_excel(filtered, job_label)
        c4.download_button(
            "⬇  Export to Excel",
            excel_bytes,
            file_name=f"{job_label}_rankings_{ts}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"export_{job_label}",
            use_container_width=True,
        )

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
        selection_mode="single-row",
        key=f"table_{job_label}",
    )

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
'''

# Now add the detail panel (it should be indented correctly from the original)
# Since original is 4-space based, and our "else:" is at 4 spaces,
# the detail panel body should be at 8 spaces.
# In the original, the detail panel after "else:" is at 8 spaces.
# So we can just add it directly with no extra indentation.
# But we need to verify the original detail panel starts at the right level.

# Strip the leading "    else:" from the extracted panel and just use the body
# Actually, let's just use the raw panel directly since the indentation matches
new_file += detail_panel_raw

# Add error expander and mode dispatch
new_file += r'''
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
'''

# Write the file
with open(r'F:\Projects\resume_ranking\resume_app\pages\2_Job_Rankings.py', 'w', encoding='utf-8') as f:
    f.write(new_file)

print(f"[OK] Written {len(new_file)} chars, {new_file.count(chr(10))} lines")

# Verify syntax
import py_compile
try:
    py_compile.compile(r'F:\Projects\resume_ranking\resume_app\pages\2_Job_Rankings.py', doraise=True)
    print("[OK] Syntax check passed")
except py_compile.PyCompileError as e:
    print(f"[ERROR] Syntax error: {e}")
