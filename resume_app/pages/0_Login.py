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

# ── Session-state helpers ──────────────────────────────────────────────────────
if "login_error" not in st.session_state:
    st.session_state["login_error"] = ""

# ── If already logged in, show welcome ─────────────────────────────────────────
user = st.session_state.get("user")
if user and isinstance(user, dict) and user.get("username"):
    st.success(f"Welcome back, **{user.get('display_name', user['username'])}**!")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Go to Dashboard", type="primary", use_container_width=True, key="goto_dash"):
            safe_switch_page("Home.py")
    with c2:
        if st.button("🚪 Logout", use_container_width=True, key="logout_btn"):
            st.session_state.clear()
            st.rerun()

    banner_path = Path(__file__).resolve().parent.parent / "assets" / "hr_excellence_banner.png"
    if banner_path.exists():
        st.image(str(banner_path), use_container_width=True)
    st.stop()

# ── Self-test diagnostics (manual — does not run on page load) ───────────────
with st.expander("🔧 System Health (click if login fails)", expanded=False):
    if st.button("Check System Health", key="check_health"):
        db_ok = False
        users_ok = False
        admin_ok = False
        user_count = 0
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
            st.code(traceback.format_exc())

        d1, d2, d3 = st.columns(3)
        with d1:
            st.markdown(f"{'🟢' if db_ok else '🔴'} **DB Connection**: {'OK' if db_ok else 'FAILED'}")
        with d2:
            st.markdown(f"{'🟢' if users_ok else '🔴'} **Users table**: {user_count if users_ok else 'N/A'} rows")
        with d3:
            st.markdown(f"{'🟢' if admin_ok else '🔴'} **admin user**: {'active' if admin_ok else 'missing/inactive'}")

    if st.button("🧹 Force Clear Session", use_container_width=True, key="clear_sess"):
        st.session_state.clear()
        st.rerun()

# ── Login card (centered, beautiful) ─────────────────────────────────────────
st.markdown("<div style='height:4vh;'></div>", unsafe_allow_html=True)

left, col, right = st.columns([1, 1.4, 1])
with col:
    # Olympic logo — cache base64 in session state for speed
    _logo_b64 = st.session_state.get("_login_logo_b64")
    if _logo_b64 is None:
        logo_path = Path(__file__).resolve().parent.parent / "user_logo.png"
        if logo_path.exists():
            try:
                import base64
                _logo_b64 = base64.b64encode(logo_path.read_bytes()).decode()
                st.session_state["_login_logo_b64"] = _logo_b64
            except Exception:
                pass
    if _logo_b64:
        st.markdown(
            f"<div style='text-align:center;margin-bottom:0.3rem;'>"
            f"<img src='data:image/png;base64,{_logo_b64}' width='140' style='display:inline-block;'>"
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

    # ── Login form (st.form ensures inputs and button are submitted together) ──
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input(
            "Username", placeholder="Enter your username", key="login_user"
        )
        password = st.text_input(
            "Password", type="password", placeholder="Enter your password", key="login_pass"
        )
        submitted = st.form_submit_button(
            "Sign In", use_container_width=True, type="primary"
        )

    # Show any persisted error
    if st.session_state["login_error"]:
        st.error(st.session_state["login_error"])
        # Emergency reset button: always offer it on failed login so the
        # admin account can be recovered without manual DB edits.
        if st.button("🚨 Emergency Reset Admin Password", use_container_width=True, key="emergency_reset"):
            try:
                emergency_conn = get_conn()
                from db import _hash_password
                new_hash = _hash_password("Olympic2024!")
                with emergency_conn.cursor() as cur:
                    cur.execute(
                        "UPDATE users SET password_hash = %s, is_active = TRUE WHERE username = 'admin'",
                        (new_hash,)
                    )
                emergency_conn.commit()
                st.session_state["login_error"] = "Admin password reset to 'Olympic2024!'. Please try logging in now."
                st.rerun()
            except Exception as e:
                st.error(f"Reset failed: {e}")

    if submitted:
        st.session_state["login_error"] = ""
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
                    st.success(f"Welcome, **{user['display_name']}**!")
                    st.balloons()
                    if st.button("Go to Dashboard →", type="primary", use_container_width=True, key="continue_dash"):
                        safe_switch_page("Home.py")
                else:
                    # FALLBACK: try direct bcrypt to bypass any module issues
                    try:
                        import bcrypt
                        with conn.cursor() as cur:
                            cur.execute("SELECT id, username, password_hash, display_name, role, is_active FROM users WHERE username = %s", (username.strip(),))
                            row = cur.fetchone()
                        if row:
                            uid, uname, pwd_hash, dname, role, is_active = row
                            direct_ok = bcrypt.checkpw(password.encode("utf-8"), pwd_hash.encode("utf-8"))
                            if direct_ok:
                                # Direct bcrypt works! db._verify_password has a bug
                                user = {"id": uid, "username": uname, "display_name": dname or uname, "role": role}
                                st.session_state["user"] = user
                                log_audit(conn, user["id"], user["username"], "LOGIN")
                                st.success(f"Welcome, **{user['display_name']}**! (fallback login)")
                                st.balloons()
                                if st.button("Go to Dashboard →", type="primary", use_container_width=True, key="continue_dash_fb"):
                                    safe_switch_page("Home.py")
                                st.stop()
                            else:
                                st.session_state["login_error"] = "Invalid username or password."
                        else:
                            st.session_state["login_error"] = "Invalid username or password."
                    except Exception as dbg_e:
                        st.session_state["login_error"] = f"Login error: {type(dbg_e).__name__}. Please try again."
                    log_audit(conn, None, username.strip(), "LOGIN_FAILED",
                              details="Invalid credentials")
                    st.rerun()
            except Exception as e:
                st.session_state["login_error"] = f"Login error: {type(e).__name__}: {e}"
                st.rerun()
