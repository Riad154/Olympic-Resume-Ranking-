import os

# Read the original file to extract the candidate detail panel
with open(r'F:\Projects\resume_ranking\_jr_detail_panel.py', 'r', encoding='utf-8') as f:
    detail_panel = f.read()

# Also read the error expander section from original
with open(r'F:\Projects\resume_ranking\resume_app\pages\2_Job_Rankings.py', 'r', encoding='utf-8') as f:
    original = f.read()

# Find the error expander section in original
error_start = original.find("# ── Errors ─────────────────────────────────────────────────────────────────────")
error_section = ""
if error_start != -1:
    error_section = original[error_start:]

# Build the new file
parts = []

parts.append(r'''"""
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

# ── Theme / CSS (exact same stylesheet as Department Rankings) ───────────────
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
''')

parts.append(r'''
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
            # Return to landing; keep the previously expanded department
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
''')

with open(r'F:\Projects\resume_ranking\_new_2jr_part1.py', 'w', encoding='utf-8') as f:
    f.write(''.join(parts))

print("Part 1 written")
