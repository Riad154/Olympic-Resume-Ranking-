"""
pages/0_Login.py — Authentication gate.

All other pages require a valid session.  This is the only page that works
without an active user session.
"""

from __future__ import annotations

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
    st.stop()

# ── Login form ─────────────────────────────────────────────────────────────────
left, col, right = st.columns([1, 2, 1])
with col:
    st.markdown(
        """
        <div style="text-align:center;margin-bottom:1.5rem;">
            <div style="font-size:1.4rem;font-weight:700;color:#1E293B;">
                HR Intelligence Platform
            </div>
            <div style="font-size:0.85rem;color:#64748B;margin-top:4px;">
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
