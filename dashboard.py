"""
dashboard.py — Resume Ranking Dashboard
Run: streamlit run dashboard.py

Reads ranked candidates from PostgreSQL resume_ranking database.
Features: job selector, score filters, sortable table, candidate detail, Excel export.
"""

import streamlit as st
import psycopg2
import psycopg2.extras
import pandas as pd
import io
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────

PG_CONN = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "resume_ranking",
    "user":     "postgres",
    "password": "ai&dt@OIPLC",  # match your docker run password
}

SCORE_COLS = [
    "overall_score", "skills_score", "experience_score",
    "leadership_score", "education_score", "culture_fit_score",
]

VERDICT_COLOR = {
    "Shortlist": "🟢",
    "Maybe":     "🟡",
    "Reject":    "🔴",
}

# ── DB ────────────────────────────────────────────────────────────────────────

def get_conn():
    """Return a live psycopg2 connection, reconnecting if stale/closed."""
    try:
        conn = st.session_state.get("pg_conn")
        if conn is None or getattr(conn, "closed", 1):
            conn = psycopg2.connect(**PG_CONN)
            st.session_state["pg_conn"] = conn
        else:
            # Ping to detect broken connections.
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return conn
    except Exception:
        conn = psycopg2.connect(**PG_CONN)
        st.session_state["pg_conn"] = conn
        return conn


def fetch_job_labels(conn) -> list:
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT job_label FROM candidates ORDER BY job_label DESC")
        return [r[0] for r in cur.fetchall()]


def fetch_candidates(conn, job_label: str) -> pd.DataFrame:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT
                apply_id,
                candidate_name,
                overall_score,
                skills_score,
                experience_score,
                leadership_score,
                education_score,
                culture_fit_score,
                experience_years,
                recommendation,
                reasoning,
                strengths,
                gaps,
                pdf_text_chars,
                jd_used,
                ranked_at,
                rank_error
            FROM candidates
            WHERE job_label = %s
            ORDER BY overall_score DESC NULLS LAST
        """, (job_label,))
        rows = cur.fetchall()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["ranked_at"] = pd.to_datetime(df["ranked_at"]).dt.strftime("%Y-%m-%d %H:%M")
    df["experience_years"] = pd.to_numeric(df["experience_years"], errors="coerce")
    return df


# ── Excel Export ──────────────────────────────────────────────────────────────

def to_excel(df: pd.DataFrame) -> bytes:
    export = df.copy()
    for col in ["strengths", "gaps"]:
        if col in export.columns:
            export[col] = export[col].apply(
                lambda x: "; ".join(x) if isinstance(x, list) else str(x or "")
            )
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        export.to_excel(writer, index=False, sheet_name="Rankings")
        ws = writer.sheets["Rankings"]
        for col_cells in ws.columns:
            max_len = max(len(str(c.value or "")) for c in col_cells)
            ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 2, 50)
    return buf.getvalue()


# ── Main App ──────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="Resume Ranking — Olympic Industries",
        page_icon="🏭",
        layout="wide",
    )

    st.title("🏭 Resume Ranking System")
    st.caption("Olympic Industries PLC — HR Department  |  Local AI  |  Zero Cloud Exposure")

    try:
        conn = get_conn()
    except Exception as e:
        st.error(f"Cannot connect to PostgreSQL: {e}")
        st.stop()

    job_labels = fetch_job_labels(conn)
    if not job_labels:
        st.warning("No ranked candidates in database yet. Run ranker.py first.")
        st.stop()

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("Job Posting")
        job_label = st.selectbox("Select", job_labels, label_visibility="collapsed")

        st.markdown("---")
        st.header("Filters")
        min_overall = st.slider("Min Overall Score", 0, 100, 0, 5)
        verdicts = st.multiselect(
            "Verdict",
            ["Shortlist", "Maybe", "Reject"],
            default=["Shortlist", "Maybe", "Reject"],
        )
        sort_by = st.selectbox("Sort By", SCORE_COLS, index=0)

        st.markdown("---")
        show_errors = st.checkbox("Show failed rankings", False)

    # ── Load data ─────────────────────────────────────────────────────────────
    df = fetch_candidates(conn, job_label)
    if df.empty:
        st.warning(f"No candidates found for: {job_label}")
        st.stop()

    errors_df = df[df["rank_error"].notna() & df["overall_score"].isna()]
    ranked_df = df[df["overall_score"].notna()].copy()

    ranked_df = ranked_df[
        (ranked_df["overall_score"] >= min_overall) &
        (ranked_df["recommendation"].isin(verdicts))
    ].sort_values(sort_by, ascending=False)

    # ── Summary metrics ───────────────────────────────────────────────────────
    total   = len(df)
    ranked  = len(df[df["overall_score"].notna()])
    n_short = len(df[df["recommendation"] == "Shortlist"])
    n_maybe = len(df[df["recommendation"] == "Maybe"])
    n_rej   = len(df[df["recommendation"] == "Reject"])
    n_pdf   = int((df["pdf_text_chars"].fillna(0) > 0).sum())

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Applicants", total)
    c2.metric("Ranked",           ranked)
    c3.metric("🟢 Shortlist",     n_short)
    c4.metric("🟡 Maybe",         n_maybe)
    c5.metric("🔴 Reject",        n_rej)
    c6.metric("📄 With PDF",      n_pdf)

    jd_values = [j for j in df["jd_used"].dropna().unique() if j]
    if jd_values:
        st.info(f"Scored against JD: **{jd_values[0]}**")
    else:
        st.warning("⚠️ No JD used — scores based on role label only. Re-rank with `--jd` for better accuracy.")

    st.markdown("---")

    # ── Export row ────────────────────────────────────────────────────────────
    col_exp, col_info = st.columns([1, 4])
    with col_exp:
        if not ranked_df.empty:
            st.download_button(
                label="📥 Export to Excel",
                data=to_excel(ranked_df),
                file_name=f"{job_label}_rankings_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
    with col_info:
        st.caption(f"Showing {len(ranked_df)} of {ranked} ranked candidates")

    # ── Main table ────────────────────────────────────────────────────────────
    if ranked_df.empty:
        st.info("No candidates match current filters.")
    else:
        display_df = ranked_df.copy()

        display_df["recommendation"] = display_df["recommendation"].map(
            lambda v: f"{VERDICT_COLOR.get(v, '')} {v}"
        )
        display_df["strengths"] = display_df["strengths"].apply(
            lambda x: " · ".join(x[:3]) if isinstance(x, list) else ""
        )
        display_df["gaps"] = display_df["gaps"].apply(
            lambda x: " · ".join(x[:2]) if isinstance(x, list) else ""
        )
        display_df["pdf"] = display_df["pdf_text_chars"].apply(
            lambda x: "✅" if (x or 0) > 0 else "—"
        )

        cols_show = [
            "candidate_name", "apply_id", "pdf",
            "overall_score", "skills_score", "experience_score",
            "leadership_score", "education_score", "culture_fit_score",
            "experience_years", "recommendation",
            "reasoning", "strengths", "gaps", "ranked_at",
        ]
        cols_show = [c for c in cols_show if c in display_df.columns]

        rename_map = {
            "candidate_name":    "Name",
            "apply_id":          "Apply ID",
            "pdf":               "PDF",
            "overall_score":     "Overall",
            "skills_score":      "Skills",
            "experience_score":  "Experience",
            "leadership_score":  "Leadership",
            "education_score":   "Education",
            "culture_fit_score": "Culture Fit",
            "experience_years":  "Exp (yrs)",
            "recommendation":    "Verdict",
            "reasoning":         "Summary",
            "strengths":         "Strengths",
            "gaps":              "Gaps",
            "ranked_at":         "Ranked At",
        }

        display_df = display_df[cols_show].rename(columns=rename_map)

        st.dataframe(
            display_df,
            use_container_width=True,
            height=550,
            column_config={
                "Overall":     st.column_config.ProgressColumn("Overall",     min_value=0, max_value=100, format="%d"),
                "Skills":      st.column_config.ProgressColumn("Skills",      min_value=0, max_value=100, format="%d"),
                "Experience":  st.column_config.ProgressColumn("Experience",  min_value=0, max_value=100, format="%d"),
                "Leadership":  st.column_config.ProgressColumn("Leadership",  min_value=0, max_value=100, format="%d"),
                "Education":   st.column_config.ProgressColumn("Education",   min_value=0, max_value=100, format="%d"),
                "Culture Fit": st.column_config.ProgressColumn("Culture Fit", min_value=0, max_value=100, format="%d"),
                "Exp (yrs)":   st.column_config.NumberColumn("Exp (yrs)", format="%.1f"),
                "Summary":     st.column_config.TextColumn("Summary", width="large"),
            },
        )

    # ── Candidate Detail ──────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Candidate Detail")

    if not ranked_df.empty:
        ranked_df["_label"] = ranked_df.apply(
            lambda r: f"{r['candidate_name'] or 'Unknown'} — {r['apply_id']}", axis=1
        )
        selected_label = st.selectbox("Select candidate", ranked_df["_label"].tolist())
        sel = ranked_df[ranked_df["_label"] == selected_label].iloc[0]

        col_a, col_b = st.columns(2)

        with col_a:
            verdict_icon = VERDICT_COLOR.get(sel["recommendation"], "")
            st.markdown(f"**Name:** {sel['candidate_name'] or '—'}")
            st.markdown(f"**Apply ID:** {sel['apply_id']}")
            st.markdown(f"**Verdict:** {verdict_icon} {sel['recommendation']}")
            st.markdown(f"**Overall Score:** {sel['overall_score']} / 100")
            st.markdown(f"**Experience:** {sel['experience_years']:.1f} years")
            pdf_chars = sel.get("pdf_text_chars") or 0
            pdf_status = f"✅ {int(pdf_chars)} chars extracted" if pdf_chars > 0 else "— Not available"
            st.markdown(f"**Uploaded CV:** {pdf_status}")
            st.markdown(f"**Summary:** {sel['reasoning']}")

        with col_b:
            score_data = pd.DataFrame({
                "Dimension": ["Skills", "Experience", "Leadership", "Education", "Culture Fit"],
                "Score": [
                    sel["skills_score"], sel["experience_score"],
                    sel["leadership_score"], sel["education_score"],
                    sel["culture_fit_score"],
                ],
            })
            st.bar_chart(score_data.set_index("Dimension"), height=250)

        col_s, col_g = st.columns(2)
        with col_s:
            st.markdown("**Strengths**")
            if isinstance(sel["strengths"], list):
                for s in sel["strengths"]:
                    st.markdown(f"- {s}")
        with col_g:
            st.markdown("**Gaps**")
            if isinstance(sel["gaps"], list):
                for g in sel["gaps"]:
                    st.markdown(f"- {g}")

    # ── Failed rankings ───────────────────────────────────────────────────────
    if show_errors and not errors_df.empty:
        st.markdown("---")
        st.subheader(f"⚠️ Failed Rankings ({len(errors_df)})")
        st.dataframe(
            errors_df[["apply_id", "candidate_name", "rank_error", "ranked_at"]],
            use_container_width=True,
        )


if __name__ == "__main__":
    main()
