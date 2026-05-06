# Read the detail panel from original
with open(r'F:\Projects\resume_ranking\_jr_detail_panel.py', 'r', encoding='utf-8') as f:
    detail_panel = f.read()

# Read the error expander from original
with open(r'F:\Projects\resume_ranking\resume_app\pages\2_Job_Rankings.py', 'r', encoding='utf-8') as f:
    original = f.read()
error_start = original.find("# ── Errors ─────────────────────────────────────────────────────────────────────")
error_section = ""
if error_start != -1:
    error_section = original[error_start:]

parts = []

parts.append(r'''
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
        f'<a href="javascript:void(0)" onclick="window.parent.postMessage({{type: \'streamlit:setComponentValue\', value: \'landing\'}}, \'*\')" '
        f'style="color:{sub_col};text-decoration:none;">{via_label}</a>'
        f' &nbsp;›&nbsp; <span style="color:{txt_col};font-weight:500;">{job_label}</span>'
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
''')

# Insert the detail panel (indent it properly)
indented_panel = ""
for line in detail_panel.split('\n'):
    if line.strip():
        indented_panel += "        " + line + "\n"
    else:
        indented_panel += "\n"

parts.append(indented_panel)

# Add the error expander at the end
parts.append(r'''

    # ── Errors ─────────────────────────────────────────────────────────────────────
    if not errors_df.empty:
        with st.expander(f"⚠️ Failed rankings ({len(errors_df)})", expanded=False):
            st.dataframe(
                errors_df[["apply_id","candidate_name","rank_error","ranked_at"]],
                use_container_width=True,
                hide_index=True,
            )
''')

with open(r'F:\Projects\resume_ranking\_new_2jr_part3.py', 'w', encoding='utf-8') as f:
    f.write(''.join(parts))

print("Part 3 written")
