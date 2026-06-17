"""
pages/0_Login.py — Authentication gate.

All other pages require a valid session.  This is the only page that works
without an active user session.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from db import (
    get_conn,
    authenticate_user,
    log_audit,
    render_sidebar,
    init_theme,
    get_css,
    safe_switch_page,
    FAVICON,
)

# ── Page chrome ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Login — HR Intelligence",
    page_icon=FAVICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

init_theme()
st.markdown(f"<style>{get_css()}</style>", unsafe_allow_html=True)
render_sidebar()

# ── If already logged in, redirect to Dashboard ──────────────────────────────────
if st.session_state.get("user"):
    st.success(f"Welcome back, **{st.session_state['user']['display_name']}**!")
    if st.button("Go to Dashboard", type="primary", use_container_width=True):
        safe_switch_page("Home.py")

    # ── Olympic Industries PLC × HR branded banner ─────────────────────────────
    st.markdown("<div style='height:2.5rem'></div>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style="
            background: linear-gradient(135deg, #C8102E 0%, #9B0B23 50%, #C8102E 100%);
            border-radius: 14px;
            padding: 2.2rem 2rem;
            margin-top: 0.5rem;
            text-align: center;
            box-shadow: 0 6px 20px rgba(200,16,46,0.25);
            color: #FFFFFF;
        ">
            <div style="font-size: 2.2rem; margin-bottom: 0.6rem;">🏭 ⚽ 🏆</div>
            <div style="font-size: 1.15rem; font-weight: 700; letter-spacing: 0.4px; margin-bottom: 0.4rem;">
                Olympic Industries PLC — Human Resources
            </div>
            <div style="font-size: 0.88rem; color: rgba(255,255,255,0.85); line-height: 1.5; max-width: 520px; margin: 0 auto;">
                Empowering talent across Bangladesh &amp; beyond.<br>
                Where world-class manufacturing meets world-class people.
            </div>
            <div style="margin-top: 1.2rem; display: flex; justify-content: center; gap: 2rem; flex-wrap: wrap;">
                <div style="text-align: center;">
                    <div style="font-size: 1.3rem; font-weight: 700;">1979</div>
                    <div style="font-size: 0.7rem; color: rgba(255,255,255,0.65);">ESTABLISHED</div>
                </div>
                <div style="text-align: center;">
                    <div style="font-size: 1.3rem; font-weight: 700;">2,500+</div>
                    <div style="font-size: 0.7rem; color: rgba(255,255,255,0.65);">EMPLOYEES</div>
                </div>
                <div style="text-align: center;">
                    <div style="font-size: 1.3rem; font-weight: 700;">48+</div>
                    <div style="font-size: 0.7rem; color: rgba(255,255,255,0.65);">EXPORT MARKETS</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

# ── Login form (compact, no-scroll) ────────────────────────────────────────────
st.markdown("<div style='height:4vh;'></div>", unsafe_allow_html=True)

left, col, right = st.columns([1, 1.4, 1])
with col:
    # Olympic logo — perfectly centered, tight spacing
    logo_path = Path(__file__).resolve().parent.parent / "user_logo.png"
    if logo_path.exists():
        b64 = ""
        try:
            import base64
            b64 = base64.b64encode(logo_path.read_bytes()).decode()
        except Exception:
            pass
        if b64:
            st.markdown(
                f"<div style='text-align:center;margin-bottom:0.3rem;'>"
                f"<img src='data:image/png;base64,{b64}' width='140' style='display:inline-block;'>"
                f"</div>",
                unsafe_allow_html=True,
            )
    else:
        st.markdown("<div style='height:0.3rem;'></div>", unsafe_allow_html=True)

    st.markdown(
        """
        <div style="text-align:center;margin-bottom:0.8rem;">
            <div style="font-size:1.25rem;font-weight:700;color:#1E293B;">
                HR Intelligence Platform
            </div>
            <div style="font-size:0.8rem;color:#64748B;margin-top:2px;">
                Please sign in to continue
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        submitted = st.form_submit_button("Sign In", use_container_width=True, type="primary")

    if submitted:
        if not username or not password:
            st.error("Please enter both username and password.")
        else:
            conn = get_conn()
            user = authenticate_user(conn, username.strip(), password)
            if user:
                st.session_state["user"] = user
                log_audit(conn, user["id"], user["username"], "LOGIN")
                st.success(f"Welcome, **{user['display_name']}**!")
                st.balloons()
                st.rerun()
            else:
                log_audit(conn, None, username.strip(), "LOGIN_FAILED",
                          details="Invalid credentials")
                st.error("Invalid username or password. Please try again.")
