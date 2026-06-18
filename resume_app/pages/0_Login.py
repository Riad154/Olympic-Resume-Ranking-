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
user = st.session_state.get("user")
if user and isinstance(user, dict) and user.get("username"):
    st.success(f"Welcome back, **{user.get('display_name', user['username'])}**!")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Go to Dashboard", type="primary", use_container_width=True):
            safe_switch_page("Home.py")
    with c2:
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    # ── Olympic Industries PLC × HR Excellence banner image ────────────────────
    st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)
    banner_path = Path(__file__).resolve().parent.parent / "assets" / "hr_excellence_banner.png"
    if banner_path.exists():
        st.image(str(banner_path), use_container_width=True)
    else:
        st.info(
            "📁 Place the HR Excellence banner image at:\n\n"
            f"`{banner_path}`\n\n"
            "It will appear here automatically once saved."
        )
    st.stop()
elif user is not None:
    # Corrupted session state — force clear
    st.warning("Session state appears corrupted. Clearing and reloading...")
    st.session_state.clear()
    st.rerun()

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
        username = st.text_input("Username", placeholder="Enter your username", key="login_user")
        password = st.text_input("Password", type="password", placeholder="Enter your password", key="login_pass")
        submitted = st.form_submit_button("Sign In", use_container_width=True, type="primary")

    if submitted:
        if not username or not password:
            st.error("Please enter both username and password.")
        else:
            try:
                conn = get_conn()
            except Exception as e:
                st.error(f"Database connection failed: {e}")
                st.info("Check that PostgreSQL is running and credentials are correct.")
                raise  # re-raise so the traceback appears in the console

            try:
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
            except Exception as e:
                st.error(f"Login error: {e}")
                st.caption(f"Debug: username='{username.strip()}' | error_type={type(e).__name__}")
                raise  # Show full traceback in the console for debugging
