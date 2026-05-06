parts = []

# Read the original detail panel
with open(r'F:\Projects\resume_ranking\_jr_detail_panel.py', 'r', encoding='utf-8') as f:
    detail_panel = f.read()

parts.append(r'''
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
            # Could show role details in a dialog; for now just open rankings
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
''')

with open(r'F:\Projects\resume_ranking\_new_2jr_part2.py', 'w', encoding='utf-8') as f:
    f.write(''.join(parts))

print("Part 2 written")
