"""
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
        # Try env vars next (used by GitHub Actions)
        env_user = os.environ.get("BDJOBS_USER")
        env_pass = os.environ.get("BDJOBS_PASS")
        if env_user and env_pass:
            creds = {"username": env_user, "password": env_pass}
        else:
            creds = _get_db_creds()

    if not creds:
        print("[ERROR] No BDJobs credentials found.")
        print("        Provide --username/--password, set BDJOBS_USER/BDJOBS_PASS env vars,")
        print("        or store them in the PostgreSQL database.")
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
