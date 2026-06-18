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

# ── Session-state helpers ──────────────────────────────────────────────────────
if "login_error" not in st.session_state:
    st.session_state["login_error"] = ""
if "login_success" not in st.session_state:
    st.session_state["login_success"] = False


def _clear_login_flags():
    st.session_state["login_error"] = ""
    st.session_state["login_success"] = False


# ── If already logged in, show welcome ─────────────────────────────────────────
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

    banner_path = Path(__file__).resolve().parent.parent / "assets" / "hr_excellence_banner.png"
    if banner_path.exists():
        st.image(str(banner_path), use_container_width=True)
    st.stop()
elif user is not None:
    # Corrupted session state — force clear
    st.warning("Session state appears corrupted. Clearing and reloading...")
    st.session_state.clear()
    st.rerun()

# ── Self-test diagnostics (visible, collapsible) ───────────────────────────────
with st.expander("🔧 System Health (click if login fails)", expanded=False):
    diag_cols = st.columns(3)
    db_ok = False
    users_ok = False
    admin_ok = False
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM users")
            user_count = cur.fetchone()[0]
            cur.execute("SELECT username, is_active FROM users WHERE username = 'admin'")
            admin_row = cur.fetchone()
        db_ok = True
        users_ok = user_count > 0
        admin_ok = admin_row is not None and admin_row[1] is True
    except Exception as e:
        st.error(f"DB connection error: {e}")

    with diag_cols[0]:
        st.markdown(f"{'🟢' if db_ok else '🔴'} **DB Connection**: {'OK' if db_ok else 'FAILED'}")
    with diag_cols[1]:
        st.markdown(f"{'🟢' if users_ok else '🔴'} **Users table**: {user_count if users_ok else 'N/A'} rows")
    with diag_cols[2]:
        st.markdown(f"{'🟢' if admin_ok else '🔴'} **admin user**: {'active' if admin_ok else 'missing/inactive'}")

    if st.button("🧹 Force Clear Session", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# ── Login form ─────────────────────────────────────────────────────────────────
st.markdown("<div style='height:4vh;'></div>", unsafe_allow_html=True)

left, col, right = st.columns([1, 1.4, 1])
with col:
    logo_path = Path(__file__).resolve().parent.parent / "user_logo.png"
    if logo_path.exists():
        try:
            import base64
            b64 = base64.b64encode(logo_path.read_bytes()).decode()
            st.markdown(
                f"<div style='text-align:center;margin-bottom:0.3rem;'>"
                f"<img src='data:image/png;base64,{b64}' width='140' style='display:inline-block;'>"
                f"</div>",
                unsafe_allow_html=True,
            )
        except Exception:
            pass
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

    # Use regular widgets (not a form) — simpler and more reliable
    username = st.text_input(
        "Username", placeholder="Enter your username",
        key="login_user", on_change=_clear_login_flags,
    )
    password = st.text_input(
        "Password", type="password", placeholder="Enter your password",
        key="login_pass", on_change=_clear_login_flags,
    )
    login_clicked = st.button(
        "Sign In", use_container_width=True, type="primary", key="login_btn",
    )

    # Show any persisted error
    if st.session_state["login_error"]:
        st.error(st.session_state["login_error"])

    if login_clicked:
        _clear_login_flags()
        if not username or not password:
            st.session_state["login_error"] = "Please enter both username and password."
            st.rerun()
        else:
            try:
                conn = get_conn()
                user = authenticate_user(conn, username.strip(), password)
                if user:
                    st.session_state["user"] = user
                    log_audit(conn, user["id"], user["username"], "LOGIN")
                    st.session_state["login_success"] = True
                    st.rerun()
                else:
                    log_audit(conn, None, username.strip(), "LOGIN_FAILED",
                              details="Invalid credentials")
                    st.session_state["login_error"] = (
                        "Invalid username or password. Please try again."
                    )
                    st.rerun()
            except Exception as e:
                st.session_state["login_error"] = f"Login error: {type(e).__name__}: {e}"
                st.rerun()

    # Success state renders as a separate block so rerun shows it cleanly
    if st.session_state["login_success"]:
        user = st.session_state.get("user")
        if user:
            st.success(f"Welcome, **{user.get('display_name', user['username'])}**!")
            st.balloons()
            if st.button("Go to Dashboard →", type="primary", use_container_width=True):
                safe_switch_page("Home.py")
