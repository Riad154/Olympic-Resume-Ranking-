"""
pages/7_Admin.py — Admin Panel.

User management and audit log viewer.  Only accessible to users with role='admin'.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd

from db import (
    get_conn,
    create_user,
    reset_user_password,
    list_users,
    toggle_user_active,
    get_audit_logs,
    log_audit,
    render_sidebar,
    init_theme,
    get_css,
    safe_switch_page,
    FAVICON,
)

# ── Page chrome ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Admin — HR Intelligence",
    page_icon=FAVICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

init_theme()
st.markdown(f"<style>{get_css()}</style>", unsafe_allow_html=True)
render_sidebar()

# ── Auth guard ─────────────────────────────────────────────────────────────────
user = st.session_state.get("user")
if not user:
    st.warning("🔒 Please log in to access this page.")
    if st.button("Go to Login", type="primary"):
        safe_switch_page("pages/0_Login.py")
    st.stop()

if user.get("role") != "admin":
    st.error("🚫 Admin access required.")
    st.stop()

conn = get_conn()

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown("<div class='page-title'>🔐 Admin Panel</div>", unsafe_allow_html=True)
st.markdown("<div class='page-sub'>User management & audit logs</div>", unsafe_allow_html=True)
st.markdown("<hr class='divider'>", unsafe_allow_html=True)

# ── Create User ────────────────────────────────────────────────────────────────
st.markdown("<div class='section-hd'>Create New User</div>", unsafe_allow_html=True)
st.caption("Only admins can create accounts. Fill in all required fields below.")

r1 = st.columns(2)
with r1[0]:
    new_username = st.text_input("Username *", key="new_username")
    new_password = st.text_input("Password *", type="password", key="new_password")
    new_department = st.text_input("Department", placeholder="e.g. HR, IT, Finance", key="new_dept")
with r1[1]:
    new_display = st.text_input("Full Name *", key="new_display")
    new_role = st.selectbox("Role *", ["user", "admin"], key="new_role")
    new_employee_id = st.text_input("Employee ID", key="new_emp_id")

r2 = st.columns(2)
with r2[0]:
    new_email = st.text_input("Email", placeholder="user@company.com", key="new_email")
with r2[1]:
    new_phone = st.text_input("Phone Number", placeholder="+880 1XXX XXXXXX", key="new_phone")

if st.button("Create User", type="primary"):
    if not new_username or not new_password or not new_display:
        st.error("Username, Full Name, and Password are required.")
    elif len(new_password) < 6:
        st.error("Password must be at least 6 characters.")
    else:
        ok, msg = create_user(
            conn,
            username=new_username,
            password=new_password,
            display_name=new_display,
            role=new_role,
            created_by=user["username"],
            department=new_department or None,
            email=new_email or None,
            phone=new_phone or None,
            employee_id=new_employee_id or None,
        )
        if ok:
            st.success(msg)
            log_audit(conn, user["id"], user["username"], "CREATE_USER",
                      target_type="user", target_id=new_username,
                      details=f"Created {new_role} account | Dept: {new_department or 'N/A'}")
        else:
            st.error(msg)

st.markdown("<br>", unsafe_allow_html=True)

# ── User List ─────────────────────────────────────────────────────────────────
st.markdown("<div class='section-hd'>Users</div>", unsafe_allow_html=True)

users = list_users(conn)
if users:
    df = pd.DataFrame(users)
    df["status"] = df["is_active"].apply(lambda x: "🟢 Active" if x else "🔴 Disabled")
    df["last_login"] = df["last_login"].fillna("—")
    df["department"] = df["department"].fillna("—")
    df["email"] = df["email"].fillna("—")
    df["phone"] = df["phone"].fillna("—")
    df["employee_id"] = df["employee_id"].fillna("—")
    display_cols = ["username", "display_name", "role", "department", "email", "phone", "employee_id", "status", "created_at", "last_login"]
    st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

    st.markdown("<div class='section-hd' style='margin-top:1rem;'>Manage Users</div>", unsafe_allow_html=True)
    manage_cols = st.columns(3)
    with manage_cols[0]:
        target_user = st.selectbox("Select user", [u["username"] for u in users if u["username"] != user["username"]], key="manage_user")
    with manage_cols[1]:
        action = st.selectbox("Action", ["Disable", "Enable", "Reset Password"], key="user_action")
    with manage_cols[2]:
        st.markdown("<div style='height:1.6rem;'></div>", unsafe_allow_html=True)
        if st.button("Apply", use_container_width=True):
            target = next((u for u in users if u["username"] == target_user), None)
            if not target:
                st.error("User not found.")
            elif action == "Reset Password":
                st.session_state["reset_target_user"] = target_user
                st.rerun()
            else:
                is_active = (action == "Enable")
                toggle_user_active(conn, target["id"], is_active)
                st.success(f"User '{target_user}' is now {'enabled' if is_active else 'disabled'}.")
                log_audit(conn, user["id"], user["username"], f"{action.upper()}_USER",
                          target_type="user", target_id=target_user)
                st.rerun()

    if st.session_state.get("reset_target_user"):
        st.markdown("<div class='section-hd' style='margin-top:1rem;'>Reset Password</div>", unsafe_allow_html=True)
        st.info(f"Resetting password for **{st.session_state['reset_target_user']}**")
        pw1 = st.text_input("New password", type="password", key="reset_pw1")
        pw2 = st.text_input("Confirm password", type="password", key="reset_pw2")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Confirm Reset", type="primary", use_container_width=True):
                if not pw1 or len(pw1) < 6:
                    st.error("Password must be at least 6 characters.")
                elif pw1 != pw2:
                    st.error("Passwords do not match.")
                else:
                    ok, msg = reset_user_password(conn, st.session_state["reset_target_user"], pw1)
                    if ok:
                        st.success(msg)
                        log_audit(conn, user["id"], user["username"], "PASSWORD_RESET",
                                  target_type="user", target_id=st.session_state["reset_target_user"])
                        del st.session_state["reset_target_user"]
                        st.rerun()
                    else:
                        st.error(msg)
        with c2:
            if st.button("Cancel", use_container_width=True):
                del st.session_state["reset_target_user"]
                st.rerun()
else:
    st.info("No users found. Create the first user above.")

st.markdown("<br>", unsafe_allow_html=True)

# ── Audit Logs ─────────────────────────────────────────────────────────────────
st.markdown("<div class='section-hd'>Audit Logs</div>", unsafe_allow_html=True)

logs = get_audit_logs(conn, limit=500)
if logs:
    log_df = pd.DataFrame(logs)
    log_df["created_at"] = pd.to_datetime(log_df["created_at"])
    st.dataframe(
        log_df[["created_at", "username", "action", "target_type", "target_id", "details"]],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No audit logs yet.")
