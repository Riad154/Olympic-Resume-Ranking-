"""
pages/0_Login.py — Authentication gate.
"""
from __future__ import annotations
import traceback
from pathlib import Path
import streamlit as st
from db import (
    get_conn, authenticate_user, log_audit,
    render_sidebar, init_theme, get_css,
    safe_switch_page, FAVICON,
)

st.set_page_config(
    page_title="Login — HR Intelligence",
    page_icon=FAVICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

init_theme()
st.markdown(f"<style>{get_css()}</style>", unsafe_allow_html=True)
render_sidebar()

# ── Guard against corrupted session ────────────────────────────────────────────
user = st.session_state.get("user")
if user and isinstance(user, dict) and user.get("username"):
    st.success(f"Welcome back, **{user.get('display_name', user['username'])}**!")
    if st.button("Go to Dashboard", type="primary", use_container_width=True, key="goto_dash"):
        safe_switch_page("Home.py")
    if st.button("🚪 Logout", use_container_width=True, key="logout_btn"):
        st.session_state.clear()
        st.rerun()
    st.stop()

# ── Diagnostics (always visible) ─────────────────────────────────────────────
st.subheader("🔧 System Health")
try:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM users")
        user_count = cur.fetchone()[0]
        cur.execute("SELECT username, is_active FROM users WHERE username = 'admin'")
        admin_row = cur.fetchone()
    c1, c2, c3 = st.columns(3)
    c1.success("DB: Connected")
    c2.info(f"Users: {user_count}")
    c3.info(f"admin: {'active' if admin_row and admin_row[1] else 'missing'}")
except Exception as e:
    st.error(f"DB Error: {e}")
    st.code(traceback.format_exc())

if st.button("🧹 Force Clear Session", key="clear_sess"):
    st.session_state.clear()
    st.rerun()

st.divider()

# ── Login form (absolutely minimal) ───────────────────────────────────────────
st.header("Sign In")

username = st.text_input("Username", key="login_user")
password = st.text_input("Password", type="password", key="login_pass")

if st.button("Sign In", type="primary", key="login_btn"):
    if not username or not password:
        st.error("Please enter both username and password.")
    else:
        try:
            conn = get_conn()
            user = authenticate_user(conn, username.strip(), password)
            if user:
                st.session_state["user"] = user
                log_audit(conn, user["id"], user["username"], "LOGIN")
                st.success(f"Welcome, **{user['display_name']}**!")
                st.balloons()
                if st.button("Continue to Dashboard →", key="continue_dash"):
                    safe_switch_page("Home.py")
            else:
                log_audit(conn, None, username.strip(), "LOGIN_FAILED",
                          details="Invalid credentials")
                st.error("Invalid username or password.")
        except Exception as e:
            st.error(f"Login failed: {type(e).__name__}: {e}")
            st.code(traceback.format_exc())
