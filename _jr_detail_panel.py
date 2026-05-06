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