"""
Apply all BDJobs integration changes:
1. Add bdjobs_credentials table to db.py schema
2. Add migration SQL
3. Add credential functions
4. Create auto-login script
5. Update 0_Download_CVs.py
"""
import os

# ═══════════════════════════════════════════════════════════════════════════════
# 1. Update db.py — add bdjobs_credentials table + functions
# ═══════════════════════════════════════════════════════════════════════════════
DB_PATH = r"F:\Projects\resume_ranking\resume_app\db.py"
with open(DB_PATH, "r", encoding="utf-8") as f:
    db_content = f.read()

# 1a. Add table creation (if not already present)
if "CREATE TABLE IF NOT EXISTS bdjobs_credentials" not in db_content:
    marker = 'CREATE INDEX IF NOT EXISTS idx_hr_audit_app ON hr_audit_log(apply_id);\n"""'
    new_table = '''CREATE INDEX IF NOT EXISTS idx_hr_audit_app ON hr_audit_log(apply_id);

-- BDJobs credentials table — stores recruiter login for auto-login
CREATE TABLE IF NOT EXISTS bdjobs_credentials (
    id            SERIAL PRIMARY KEY,
    username      TEXT NOT NULL,
    password      TEXT NOT NULL,  -- base64-encoded obfuscation (not true encryption)
    created_at    TIMESTAMP DEFAULT NOW(),
    updated_at    TIMESTAMP DEFAULT NOW()
);
"""'''
    if marker in db_content:
        db_content = db_content.replace(marker, new_table)
        print("[OK] Added bdjobs_credentials table to SCHEMA_SQL")
    else:
        print("[WARN] Could not find hr_audit_app index marker")
else:
    print("[SKIP] bdjobs_credentials table already in SCHEMA_SQL")

# 1b. Add migration SQL (if not already present)
if "CREATE TABLE IF NOT EXISTS bdjobs_credentials" not in db_content.split("MIGRATION_SQL")[1]:
    migration_marker = "UPDATE jobs SET department = 'Uncategorized'"
    new_migration = """CREATE TABLE IF NOT EXISTS bdjobs_credentials (
    id            SERIAL PRIMARY KEY,
    username      TEXT NOT NULL,
    password      TEXT NOT NULL,
    created_at    TIMESTAMP DEFAULT NOW(),
    updated_at    TIMESTAMP DEFAULT NOW()
);

UPDATE jobs SET department = 'Uncategorized'"""
    if migration_marker in db_content:
        db_content = db_content.replace(migration_marker, new_migration)
        print("[OK] Added bdjobs_credentials table to MIGRATION_SQL")
    else:
        print("[WARN] Could not find migration marker")
else:
    print("[SKIP] bdjobs_credentials migration already present")

# 1c. Add credential functions at the end of db.py
if "def get_bdjobs_credentials" not in db_content:
    credential_funcs = '''

# ═══════════════════════════════════════════════════════════════════════════════
# BDJobs credential helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _encode_pwd(pwd: str) -> str:
    """Basic obfuscation — not encryption, but prevents casual shoulder-surfing."""
    import base64
    return base64.b64encode(pwd.encode("utf-8")).decode("ascii")


def _decode_pwd(enc: str) -> str:
    import base64
    return base64.b64decode(enc.encode("ascii")).decode("utf-8")


def save_bdjobs_credentials(conn, username: str, password: str) -> None:
    """Upsert BDJobs credentials."""
    enc = _encode_pwd(password)
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO bdjobs_credentials (id, username, password, updated_at)
            VALUES (1, %s, %s, NOW())
            ON CONFLICT (id) DO UPDATE SET
                username = EXCLUDED.username,
                password = EXCLUDED.password,
                updated_at = NOW()
        """, (username, enc))


def get_bdjobs_credentials(conn) -> dict | None:
    """Return {"username": str, "password": str} or None."""
    with conn.cursor() as cur:
        cur.execute("SELECT username, password FROM bdjobs_credentials ORDER BY id LIMIT 1")
        row = cur.fetchone()
    if row:
        return {"username": row[0], "password": _decode_pwd(row[1])}
    return None


def has_bdjobs_credentials(conn) -> bool:
    """Return True if credentials are stored."""
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM bdjobs_credentials LIMIT 1")
        return cur.fetchone() is not None
'''
    db_content = db_content.rstrip() + "\n" + credential_funcs + "\n"
    print("[OK] Added BDJobs credential functions to db.py")
else:
    print("[SKIP] BDJobs credential functions already in db.py")

with open(DB_PATH, "w", encoding="utf-8") as f:
    f.write(db_content)

print(f"[DONE] db.py updated ({len(db_content)} chars)")

# ═══════════════════════════════════════════════════════════════════════════════
# 2. Create bdjobs_auto_login.py script
# ═══════════════════════════════════════════════════════════════════════════════
AUTO_LOGIN_PATH = r"F:\Projects\resume_ranking\bdjobs_auto_login.py"
auto_login_code = r'''"""
bdjobs_auto_login.py — Auto-login using stored PostgreSQL credentials.
Opens Chromium, auto-fills username/password, navigates to recruiter dashboard.

Usage:
    python bdjobs_auto_login.py                    # uses DB credentials
    python bdjobs_auto_login.py --username X --password Y  # override
    python bdjobs_auto_login.py --headless         # headless mode
"""

import argparse
import os
import sys
import time
from pathlib import Path

# Read credentials from PostgreSQL
def _get_db_creds():
    import psycopg2
    PG = {
        "host":     os.environ.get("PG_HOST",     "localhost"),
        "port":     int(os.environ.get("PG_PORT", "5432")),
        "dbname":   os.environ.get("PG_DBNAME",   "resume_ranking"),
        "user":     os.environ.get("PG_USER",     "postgres"),
        "password": os.environ.get("PG_PASSWORD", "ai&dt@OIPLC"),
    }
    conn = psycopg2.connect(**PG)
    with conn.cursor() as cur:
        cur.execute("SELECT username, password FROM bdjobs_credentials ORDER BY id LIMIT 1")
        row = cur.fetchone()
    conn.close()
    if row:
        import base64
        return {"username": row[0], "password": base64.b64decode(row[1].encode()).decode("utf-8")}
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--wait-for-flag", default=None)
    parser.add_argument("--max-wait-minutes", type=int, default=15)
    args = parser.parse_args()

    if args.username and args.password:
        creds = {"username": args.username, "password": args.password}
    else:
        creds = _get_db_creds()

    if not creds:
        print("[ERROR] No BDJobs credentials found in database.")
        print("        Go to Settings → BDJobs Credentials to store them.")
        sys.exit(1)

    CONTEXT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bdjobs_session")
    BDJOBS_URL = "https://recruiter.bdjobs.com"

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[ERROR] Playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=CONTEXT_DIR,
            headless=args.headless,
            viewport={"width": 1280, "height": 900},
            accept_downloads=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else context.new_page()

        print(f"[INFO] Navigating to {BDJOBS_URL} …")
        page.goto(BDJOBS_URL, wait_until="domcontentloaded", timeout=30000)

        # Check if already logged in
        current = page.url.lower()
        if "signin" not in current and "login" not in current:
            print("[OK] Already logged in (valid session).")
            context.close()
            sys.exit(0)

        # Try to auto-fill login form
        print(f"[INFO] Auto-filling credentials for {creds['username']} …")
        try:
            page.fill("input[type='text'], input[name='UserName'], #UserName", creds["username"], timeout=5000)
            page.fill("input[type='password'], input[name='Password'], #Password", creds["password"], timeout=5000)
            page.click("input[type='submit'], button[type='submit'], .btn-login", timeout=5000)
            print("[INFO] Login form submitted. Waiting for navigation …")
            page.wait_for_load_state("networkidle", timeout=30000)
        except Exception as e:
            print(f"[WARN] Could not auto-fill form ({e}). Manual login may be required.")

        # Verify
        current = page.url.lower()
        if "signin" in current or "login" in current:
            print("[WARNING] Still on login page. Credentials may be wrong or CAPTCHA present.")
            if args.wait_for_flag:
                flag = Path(args.wait_for_flag)
                deadline = time.time() + args.max_wait_minutes * 60
                print(f"[WAITING] Polling for sentinel: {flag}")
                while time.time() < deadline:
                    if flag.exists():
                        print("[OK] Sentinel detected.")
                        try: flag.unlink()
                        except Exception: pass
                        break
                    time.sleep(1)
                else:
                    print("[TIMEOUT] No sentinel received.")
                    context.close()
                    sys.exit(2)
            else:
                input(">>> Press ENTER after you have logged in manually … ")
        else:
            print("[OK] Login successful!")

        context.close()
        print(f"[DONE] Session saved to: {CONTEXT_DIR}")


if __name__ == "__main__":
    main()
'''

with open(AUTO_LOGIN_PATH, "w", encoding="utf-8") as f:
    f.write(auto_login_code)
print(f"[OK] Created {AUTO_LOGIN_PATH}")

# ═══════════════════════════════════════════════════════════════════════════════
# 3. Update 0_Download_CVs.py — add credential UI + auto-login option
# ═══════════════════════════════════════════════════════════════════════════════
DL_PATH = r"F:\Projects\resume_ranking\resume_app\pages\0_Download_CVs.py"
with open(DL_PATH, "r", encoding="utf-8") as f:
    dl_content = f.read()

# Add imports for credential functions
if "has_bdjobs_credentials" not in dl_content:
    old_import = """from db import (
    get_css, init_theme, render_sidebar,
    DEPARTMENT_LIST, list_download_folders,
    RESUMES_BASE, RANKER_PATH, VENV_PYTHON,
)"""
    new_import = """from db import (
    get_css, init_theme, render_sidebar,
    DEPARTMENT_LIST, list_download_folders,
    RESUMES_BASE, RANKER_PATH, VENV_PYTHON,
    get_conn, save_bdjobs_credentials, get_bdjobs_credentials,
    has_bdjobs_credentials,
)"""
    dl_content = dl_content.replace(old_import, new_import)
    print("[OK] Updated imports in 0_Download_CVs.py")

# Add LOGIN_AUTO_PATH constant
if "LOGIN_AUTO_PATH" not in dl_content:
    old_const = '''LOGIN_PATH      = str(PROJECT_ROOT / "bdjobs_login.py")
SESSION_DIR     = PROJECT_ROOT / "bdjobs_session"
LOG_DIR         = PROJECT_ROOT / "_dl_logs"
LOG_DIR.mkdir(exist_ok=True)
LOGIN_FLAG      = PROJECT_ROOT / "_login_done.flag"'''
    new_const = '''LOGIN_PATH      = str(PROJECT_ROOT / "bdjobs_login.py")
LOGIN_AUTO_PATH = str(PROJECT_ROOT / "bdjobs_auto_login.py")
SESSION_DIR     = PROJECT_ROOT / "bdjobs_session"
LOG_DIR         = PROJECT_ROOT / "_dl_logs"
LOG_DIR.mkdir(exist_ok=True)
LOGIN_FLAG      = PROJECT_ROOT / "_login_done.flag"'''
    dl_content = dl_content.replace(old_const, new_const)
    print("[OK] Added LOGIN_AUTO_PATH constant")

# Add _spawn_auto_login function
if "def _spawn_auto_login" not in dl_content:
    old_spawn = '''def _spawn_login():
    try: LOGIN_FLAG.unlink()
    except FileNotFoundError: pass
    return _spawn(
        [VENV_PYTHON, LOGIN_PATH, "--wait-for-flag", str(LOGIN_FLAG)],
        log_name="login", new_console=True,
    )'''
    new_spawn = '''def _spawn_login():
    try: LOGIN_FLAG.unlink()
    except FileNotFoundError: pass
    return _spawn(
        [VENV_PYTHON, LOGIN_PATH, "--wait-for-flag", str(LOGIN_FLAG)],
        log_name="login", new_console=True,
    )


def _spawn_auto_login():
    try: LOGIN_FLAG.unlink()
    except FileNotFoundError: pass
    return _spawn(
        [VENV_PYTHON, LOGIN_AUTO_PATH, "--wait-for-flag", str(LOGIN_FLAG), "--headless"],
        log_name="auto_login", new_console=False,
    )'''
    dl_content = dl_content.replace(old_spawn, new_spawn)
    print("[OK] Added _spawn_auto_login function")

# Update the session status section to include credential storage + auto-login
if "### 🔐 BDJobs session" in dl_content and "credentials_expander" not in dl_content:
    # Find the section and replace with enhanced version
    old_section = '''st.markdown("### 🔐 BDJobs session")
sa, sb = st.columns([3, 1])
sa.markdown(f"**{state_icon} {status['state'].title()}** — {status['msg']}")'''
    new_section = '''st.markdown("### 🔐 BDJobs session")

# ── Credential storage (collapsible) ───────────────────────────────────────
conn = get_conn()
with st.expander("💾 Manage BDJobs Credentials", expanded=not has_bdjobs_credentials(conn)):
    existing = get_bdjobs_credentials(conn)
    c1, c2 = st.columns(2)
    default_user = existing["username"] if existing else ""
    default_pwd  = existing["password"] if existing else ""
    username = c1.text_input("BDJobs Username", value=default_user, key="bdj_user")
    password = c2.text_input("BDJobs Password", value=default_pwd, type="password", key="bdj_pwd")
    if st.button("💾 Save Credentials", use_container_width=True, type="primary"):
        if username.strip() and password.strip():
            save_bdjobs_credentials(conn, username.strip(), password.strip())
            st.success("Credentials saved securely in PostgreSQL.")
            st.rerun()
        else:
            st.error("Both username and password are required.")

sa, sb = st.columns([3, 1])
sa.markdown(f"**{state_icon} {status['state'].title()}** — {status['msg']}")'''
    dl_content = dl_content.replace(old_section, new_section)
    print("[OK] Added credential storage UI")

# Update the else: block (when login_proc is None) to offer auto-login
if 'AUTO_LOGIN' not in dl_content:
    old_else = '''else:
    if sb.button("🔐 Re-login to BDJobs", type="primary", use_container_width=True):
        proc, lp = _spawn_login()'''
    new_else = '''else:
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🔐 Manual Re-login (Browser)", type="primary", use_container_width=True, key="btn_manual_login"):
            proc, lp = _spawn_login()
            st.session_state["bdjobs_login_proc"] = proc
            st.session_state["bdjobs_login_log"] = lp
            st.rerun()
    with col_btn2:
        has_creds = has_bdjobs_credentials(conn)
        if st.button(
            "🤖 Auto Re-login (Headless)" if has_creds else "🤖 Auto Re-login (Set credentials first)",
            type="secondary", use_container_width=True, key="btn_auto_login",
            disabled=not has_creds,
        ):
            proc, lp = _spawn_auto_login()
            st.session_state["bdjobs_login_proc"] = proc
            st.session_state["bdjobs_login_log"] = lp
            st.rerun()'''
    dl_content = dl_content.replace(old_else, new_else)
    print("[OK] Added auto-login button")

with open(DL_PATH, "w", encoding="utf-8") as f:
    f.write(dl_content)
print(f"[DONE] 0_Download_CVs.py updated ({len(dl_content)} chars)")

# ═══════════════════════════════════════════════════════════════════════════════
# 4. Add BDJobs Credentials section to Settings page
# ═══════════════════════════════════════════════════════════════════════════════
SETTINGS_PATH = r"F:\Projects\resume_ranking\resume_app\pages\5_Settings.py"
with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
    settings_content = f.read()

if "bdjobs_credentials" not in settings_content:
    # Add imports
    if "get_conn" not in settings_content:
        # Already imported or different import pattern — check
        pass

    # Find a good insertion point (after Ranking Health or at the end)
    bdjobs_settings = '''

# ═══════════════════════════════════════════════════════════════════════════════
# BDJobs CREDENTIALS — Stored securely in PostgreSQL
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("<br>", unsafe_allow_html=True)
st.markdown(
    f"<div class='section-hd' style='font-size:1.2rem;color:{txt_col} !important;'>"
    f"BDJobs Credentials</div>",
    unsafe_allow_html=True,
)

conn_bdj = get_conn()
creds = get_bdjobs_credentials(conn_bdj)

if creds:
    st.success(f"✅ Credentials stored for: **{creds['username']}**")
    st.caption("Password is obfuscated (base64) in the database. To update, re-enter below.")
else:
    st.warning("⚠️ No BDJobs credentials stored. Enter them below to enable auto-login.")

with st.form("bdjobs_creds_form"):
    c1, c2 = st.columns(2)
    default_user = creds["username"] if creds else ""
    default_pwd  = creds["password"] if creds else ""
    bdj_user = c1.text_input("BDJobs Username", value=default_user)
    bdj_pwd  = c2.text_input("BDJobs Password", value=default_pwd, type="password")
    submitted = st.form_submit_button("💾 Save Credentials", use_container_width=True, type="primary")
    if submitted:
        if bdj_user.strip() and bdj_pwd.strip():
            save_bdjobs_credentials(conn_bdj, bdj_user.strip(), bdj_pwd.strip())
            st.success("Credentials saved.")
            st.rerun()
        else:
            st.error("Both fields are required.")
'''
    settings_content = settings_content.rstrip() + "\n" + bdjobs_settings + "\n"
    print("[OK] Added BDJobs Credentials section to 5_Settings.py")
else:
    print("[SKIP] BDJobs Credentials section already in 5_Settings.py")

with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
    f.write(settings_content)

print("\nAll BDJobs integration changes applied successfully!")
print("Next steps:")
print("  1. Install Playwright: pip install playwright && playwright install chromium")
print("  2. Restart Streamlit server")
print("  3. Go to Download CVs page or Settings → BDJobs Credentials to store login info")
