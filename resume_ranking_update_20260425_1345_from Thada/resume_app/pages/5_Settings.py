"""
pages/4_Settings.py — System health and configuration.
"""
import requests
import psycopg2
import streamlit as st
from db import get_conn, get_css, init_theme, render_sidebar, PG_CONN

st.set_page_config(page_title="Settings — HR Intelligence", page_icon="⚙️", layout="wide", initial_sidebar_state="expanded")
init_theme()
st.markdown(get_css(), unsafe_allow_html=True)
render_sidebar()

is_day   = st.session_state.get("day_mode", True)
txt_col  = "#1E293B" if is_day else "#E2E8F0"
sub_col  = "#64748B"
card_bg  = "#FFFFFF" if is_day else "#1E2435"
card_bdr = "#E2E8F0" if is_day else "#2D3748"

st.markdown(f'<div class="page-title" style="color:{txt_col} !important;">Settings</div>', unsafe_allow_html=True)
st.markdown('<div class="page-sub">System configuration and health monitoring</div>', unsafe_allow_html=True)
st.markdown('<hr class="divider" style="border-top:1px solid ' + card_bdr + '">', unsafe_allow_html=True)

# ── System health ──────────────────────────────────────────────────────────────
st.markdown(f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">System Health</div>', unsafe_allow_html=True)
col1, col2 = st.columns(2, gap="large")

with col1:
    try:
        c = psycopg2.connect(**PG_CONN); c.close(); pg_ok=True; pg_msg="Connected"
    except Exception as e:
        pg_ok=False; pg_msg=str(e)[:60]

    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        ol_ok = r.status_code==200
        models = [m["name"] for m in r.json().get("models",[])] if ol_ok else []
        ol_msg = f"{len(models)} model(s) loaded" if ol_ok else "Not reachable"
    except:
        ol_ok=False; ol_msg="Not reachable"; models=[]

    try:
        r2 = requests.get("http://localhost:5678/healthz", timeout=3)
        n8_ok = r2.status_code==200; n8_msg="Running"
    except:
        n8_ok=False; n8_msg="Not reachable"

    for label, ok, msg in [
        ("PostgreSQL", pg_ok, pg_msg),
        ("Ollama",     ol_ok, ol_msg),
        ("n8n",        n8_ok, n8_msg),
    ]:
        dot = "🟢" if ok else "🔴"
        st.markdown(f"""
            <div style="background:{card_bg};border:1px solid {card_bdr};border-radius:8px;
                        padding:0.9rem 1.1rem;margin-bottom:0.6rem;
                        display:flex;justify-content:space-between;align-items:center;">
                <div style="font-size:0.9rem;font-weight:500;color:{txt_col} !important;">{dot} &nbsp; {label}</div>
                <div style="font-size:0.82rem;color:{sub_col} !important;">{msg}</div>
            </div>
        """, unsafe_allow_html=True)

with col2:
    st.markdown(f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Loaded Models</div>', unsafe_allow_html=True)
    if models:
        for m in models:
            active = "qwen3:8b" in m
            st.markdown(f"""
                <div style="background:{card_bg};border:1px solid {'#FECACA' if active else card_bdr};
                            border-radius:8px;padding:0.7rem 1rem;margin-bottom:0.5rem;
                            display:flex;justify-content:space-between;align-items:center;">
                    <div style="font-size:0.86rem;font-weight:{'600' if active else '400'};color:{txt_col} !important;">
                        {'⭐ ' if active else ''}{m}
                    </div>
                    {'<div style="font-size:0.72rem;background:#FEE2E2;color:#991B1B !important;padding:2px 8px;border-radius:10px;font-weight:500;">ACTIVE</div>' if active else ''}
                </div>
            """, unsafe_allow_html=True)
    else:
        st.warning("No models loaded. Is Ollama running?")

    if ol_ok:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🧪  Send Test Prompt", type="secondary"):
            with st.spinner("Testing Ollama..."):
                try:
                    resp = requests.post(
                        "http://localhost:11434/api/chat",
                        json={"model":"qwen3:8b-q4_K_M","format":"json","stream":False,
                              "messages":[
                                  {"role":"system","content":"Return JSON only."},
                                  {"role":"user","content":'Return: {"status":"ok","message":"Pipeline working"}'},
                              ]},
                        timeout=30,
                    )
                    content = resp.json()["message"]["content"]
                    st.success(f"✓ Ollama OK: {content[:100]}")
                except Exception as e:
                    st.error(f"Test failed: {e}")

st.markdown('<hr class="divider" style="border-top:1px solid ' + card_bdr + '">', unsafe_allow_html=True)

# ── DB stats ───────────────────────────────────────────────────────────────────
st.markdown(f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Database</div>', unsafe_allow_html=True)
try:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(DISTINCT job_label),COUNT(*),SUM(CASE WHEN overall_score IS NOT NULL THEN 1 ELSE 0 END),SUM(CASE WHEN rank_error IS NOT NULL THEN 1 ELSE 0 END) FROM candidates")
        n_jobs,n_cands,n_ranked,n_errors = cur.fetchone()

    for col, val, lbl in zip(
        st.columns(4),
        [n_jobs or 0, n_cands or 0, n_ranked or 0, n_errors or 0],
        ["Job Postings","Total Candidates","Ranked","Errors"],
    ):
        with col:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-val" style="color:{txt_col} !important;font-size:1.8rem;">{val}</div>
                    <div class="metric-lbl" style="color:{sub_col} !important;">{lbl}</div>
                </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"""
        <div style="background:{card_bg};border:1px solid {card_bdr};border-radius:8px;padding:1rem;
                    font-family:monospace;font-size:0.82rem;color:{txt_col} !important;line-height:2;">
            Host: {PG_CONN['host']}:{PG_CONN['port']} &nbsp;·&nbsp;
            Database: {PG_CONN['dbname']} &nbsp;·&nbsp;
            User: {PG_CONN['user']}
        </div>
    """, unsafe_allow_html=True)
except Exception as e:
    st.error(f"Database error: {e}")

st.markdown('<hr class="divider" style="border-top:1px solid ' + card_bdr + '">', unsafe_allow_html=True)
st.markdown(f'<div class="section-hd" style="color:{sub_col} !important;border-bottom:1px solid {card_bdr};">Scoring Schema</div>', unsafe_allow_html=True)
st.markdown(f"""
    <div style="background:{card_bg};border:1px solid {card_bdr};border-radius:8px;padding:1rem 1.2rem;">
        <div style="font-size:0.88rem;color:{txt_col} !important;line-height:2.1;">
            <b>Model:</b> qwen3:8b-q4_K_M — local Ollama inference, no cloud exposure<br>
            <b>Dimensions:</b> AI/ML · ERP · Automation · Leadership · Education · Overall<br>
            <b>Verdicts:</b> Shortlist / Maybe / Reject — holistic LLM judgment, not score threshold<br>
            <b>BDJobs score:</b> Shown for reference only — not used in AI ranking<br>
            <b>All evaluations</b> stored with full reasoning for HR audit trail
        </div>
    </div>
""", unsafe_allow_html=True)
