import re

with open(r'F:\Projects\resume_ranking\resume_app\pages\5_Settings.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find where to insert (after the last closing """ or at the end)
ranking_health = '''

# ═══════════════════════════════════════════════════════════════════════════════
# RANKING HEALTH — live error dashboard
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("<br>", unsafe_allow_html=True)
st.markdown(
    f"<div class='section-hd' style='font-size:1.2rem;color:{txt_col} !important;'>"
    f"Ranking Health</div>",
    unsafe_allow_html=True,
)

conn_health = get_conn()
with conn_health.cursor() as cur:
    cur.execute("""
        SELECT
            COUNT(*) AS total_failed,
            COUNT(*) FILTER (WHERE rank_error ILIKE '%Expecting value: line 1 column 1%') AS empty_failures,
            COUNT(*) FILTER (WHERE rank_error ILIKE '%timeout%') AS timeout_failures,
            COUNT(*) FILTER (WHERE rank_error ILIKE '%PDF extraction%') AS pdf_failures,
            COUNT(*) FILTER (WHERE rank_error ILIKE '%encoding%') AS encoding_failures,
            COUNT(DISTINCT job_label) AS affected_jobs,
            MIN(ranked_at) AS oldest_failure,
            MAX(ranked_at) AS newest_failure
        FROM candidates
        WHERE rank_error IS NOT NULL
          AND overall_score IS NULL
    """)
    row = cur.fetchone()

total_failed, empty, timeout, pdf_err, enc, jobs, oldest, newest = row
total_failed = total_failed or 0
empty = empty or 0
timeout = timeout or 0
pdf_err = pdf_err or 0
enc = enc or 0
jobs = jobs or 0

if total_failed == 0:
    st.success("✅ All candidates ranked successfully. No failures detected.")
else:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Failed Candidates", total_failed)
    c2.metric("Empty Responses", empty)
    c3.metric("Affected Jobs", jobs)
    c4.metric("PDF Failures", pdf_err)

    st.markdown("<br>", unsafe_allow_html=True)

    # Action buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Re-rank All Failed", use_container_width=True, type="primary"):
            with conn_health.cursor() as cur:
                cur.execute("""
                    UPDATE candidates
                    SET rank_error = NULL, ranked_at = NULL
                    WHERE rank_error IS NOT NULL AND overall_score IS NULL
                """)
                conn_health.commit()
            st.success(f"Cleared {total_failed} failed candidates. Re-run ranker.py for each job.")

    with col2:
        if st.button("📋 View Error Log", use_container_width=True, type="secondary"):
            with conn_health.cursor() as cur:
                cur.execute("""
                    SELECT apply_id, job_label, LEFT(rank_error, 120) AS err, ranked_at
                    FROM candidates
                    WHERE rank_error IS NOT NULL AND overall_score IS NULL
                    ORDER BY ranked_at DESC
                    LIMIT 50
                """)
                rows = cur.fetchall()
                if rows:
                    df_err = pd.DataFrame(rows, columns=["Apply ID", "Job", "Error", "Time"])
                    st.dataframe(df_err, use_container_width=True, hide_index=True)
                else:
                    st.info("No errors to display.")

    if total_failed > 0:
        st.caption(
            f"Oldest failure: {oldest.strftime('%Y-%m-%d %H:%M') if oldest else 'N/A'}  ·  "
            f"Newest failure: {newest.strftime('%Y-%m-%d %H:%M') if newest else 'N/A'}"
        )

conn_health.close()
'''

if "Ranking Health" not in content:
    content = content.rstrip() + "\n" + ranking_health + "\n"
    print("[OK] Added Ranking Health section to 5_Settings.py")
else:
    print("[SKIP] Ranking Health already present")

with open(r'F:\Projects\resume_ranking\resume_app\pages\5_Settings.py', 'w', encoding='utf-8') as f:
    f.write(content)
