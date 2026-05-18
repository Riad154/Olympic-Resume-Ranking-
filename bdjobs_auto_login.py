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
    pg_port_str = os.environ.get("PG_PORT", "5432") or "5432"  # handle empty string
    PG = {
        "host":     os.environ.get("PG_HOST",     "localhost") or "localhost",
        "port":     int(pg_port_str),
        "dbname":   os.environ.get("PG_DBNAME",   "resume_ranking") or "resume_ranking",
        "user":     os.environ.get("PG_USER",     "postgres") or "postgres",
        "password": os.environ.get("PG_PASSWORD", ""),
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
    parser.add_argument("--force", action="store_true",
                        help="Clear existing session and force a fresh login.")
    args = parser.parse_args()

    if args.username and args.password:
        creds = {"username": args.username, "password": args.password}
    else:
        # Try env vars next (used by GitHub Actions)
        env_user = os.environ.get("BDJOBS_USER", "").strip()
        env_pass = os.environ.get("BDJOBS_PASS", "").strip()
        if env_user and env_pass:
            creds = {"username": env_user, "password": env_pass}
        elif args.headless:
            # In CI/headless mode, don't try DB — fail fast with clear message
            print("[ERROR] No BDJobs credentials available in headless mode.")
            print("        --username/--password args were empty or not provided.")
            print("        BDJOBS_USER/BDJOBS_PASS env vars are also empty.")
            print("")
            print("        FIX: Add these secrets to your GitHub repo:")
            print("          - BDJOBS_USER: your BDJobs recruiter username/email")
            print("          - BDJOBS_PASS: your BDJobs recruiter password")
            print("")
            print("        Go to: GitHub repo → Settings → Secrets and variables → Actions")
            sys.exit(1)
        else:
            creds = _get_db_creds()

    if not creds:
        print("[ERROR] No BDJobs credentials found.")
        print("        Provide --username/--password, set BDJOBS_USER/BDJOBS_PASS env vars,")
        print("        or store them in the PostgreSQL database.")
        sys.exit(1)

    CONTEXT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bdjobs_session")
    BDJOBS_URL = "https://recruiter.bdjobs.com"
    SCREENSHOT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_login_failure.png")

    if args.force:
        import shutil
        if os.path.exists(CONTEXT_DIR):
            shutil.rmtree(CONTEXT_DIR)
            print(f"[INFO] Cleared session dir for fresh login: {CONTEXT_DIR}")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[ERROR] Playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    def _is_logged_in(page) -> bool:
        """Verify actual authenticated state by checking DOM, not just URL."""
        url = page.url.lower()
        # If URL explicitly has login/signin, we're definitely not logged in
        if "signin" in url or "login" in url:
            return False

        # Check for authenticated UI elements
        try:
            # Look for logout link/button, dashboard menu, or recruiter-specific elements
            indicators = [
                "a[href*='logout']",
                "a[href*='signout']",
                "button:has-text('Logout')",
                "button:has-text('Sign out')",
                ".logout",
                "#logout",
                "app-dashboard",
                "app-recruitment-center",
                "app-header",
                ".user-profile",
                ".recruiter-menu",
            ]
            for sel in indicators:
                try:
                    if page.query_selector(sel):
                        return True
                except Exception:
                    pass
        except Exception:
            pass

        # Also check page text for logged-in markers
        try:
            body_text = (page.evaluate("() => document.body.innerText") or "").lower()
            logged_in_markers = ["logout", "sign out", "dashboard", "my jobs", "post a job", "applicant tracking"]
            logged_out_markers = ["sign in", "login", "register", "create account", "employer login"]
            logged_in_score = sum(1 for m in logged_in_markers if m in body_text)
            logged_out_score = sum(1 for m in logged_out_markers if m in body_text)
            if logged_in_score > 0 and logged_in_score >= logged_out_score:
                return True
            if logged_out_score > 0:
                return False
        except Exception:
            pass

        # Default: if we're on the bare root domain with no clear auth markers, assume NOT logged in
        parsed = urlparse(url)
        if parsed.path in ("", "/") and not (parsed.query or parsed.fragment):
            return False

        # Ambiguous — assume not logged in to be safe
        return False

    from urllib.parse import urlparse

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
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        # ── Check if already logged in ──────────────────────────────────────
        if _is_logged_in(page):
            print("[OK] Already logged in (valid session).")
            context.close()
            sys.exit(0)

        print("[INFO] Not authenticated. Proceeding with login form …")

        # ── Try to auto-fill login form ───────────────────────────────────
        print(f"[INFO] Auto-filling credentials for {creds['username']} …")
        login_ok = False
        try:
            # Try multiple possible selectors for BDJobs login form
            user_sel = None
            for sel in ["input#UserName", "input[name='UserName']", "input[type='text']", "#userName", "#username"]:
                if page.query_selector(sel):
                    user_sel = sel
                    break
            pass_sel = None
            for sel in ["input#Password", "input[name='Password']", "input[type='password']"]:
                if page.query_selector(sel):
                    pass_sel = sel
                    break
            submit_sel = None
            for sel in ["input[type='submit']", "button[type='submit']", ".btn-login", "#btnLogin", "button:has-text('Sign In')", "button:has-text('Login')"]:
                if page.query_selector(sel):
                    submit_sel = sel
                    break

            if user_sel and pass_sel and submit_sel:
                page.fill(user_sel, creds["username"], timeout=5000)
                page.fill(pass_sel, creds["password"], timeout=5000)
                page.click(submit_sel, timeout=5000)
                print(f"[INFO] Form submitted via {submit_sel}. Waiting for navigation …")
                page.wait_for_load_state("networkidle", timeout=30000)
                login_ok = True
            else:
                print(f"[WARN] Could not find all login form fields.")
                print(f"        user_field={user_sel}, pass_field={pass_sel}, submit={submit_sel}")
        except Exception as e:
            print(f"[WARN] Could not auto-fill form ({e}).")

        # ── Wait a moment for SPA routing ─────────────────────────────────
        time.sleep(3)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        # ── Verify login succeeded ────────────────────────────────────────
        if _is_logged_in(page):
            print("[OK] Login successful!")
            context.close()
            print(f"[DONE] Session saved to: {CONTEXT_DIR}")
            sys.exit(0)

        # ── Login failed — capture diagnostics ──────────────────────────
        print("[ERROR] Login failed. Session is NOT authenticated.")
        print(f"        Final URL: {page.url}")
        try:
            body_text = (page.evaluate("() => document.body.innerText") or "")
            print(f"        Page text preview: {body_text[:500]}...")
        except Exception:
            pass

        # Take screenshot for debugging
        try:
            page.screenshot(path=SCREENSHOT_PATH, full_page=True)
            print(f"        Screenshot saved: {SCREENSHOT_PATH}")
        except Exception as e:
            print(f"        (screenshot failed: {e})")

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
        elif args.headless:
            print("[ERROR] Login failed in headless mode. Cannot prompt for manual login.")
            print("        Possible causes:")
            print("          1. Wrong BDJOBS_USER / BDJOBS_PASS credentials")
            print("          2. BDJobs is showing a CAPTCHA challenge")
            print("          3. The login page structure has changed")
            print("          4. BDJobs is blocking headless browser access")
            print("")
            print("        FIX: Use --force to clear session and retry with correct credentials.")
            context.close()
            sys.exit(1)
        else:
            input(">>> Press ENTER after you have logged in manually … ")

        context.close()
        print(f"[DONE] Session saved to: {CONTEXT_DIR}")


if __name__ == "__main__":
    main()
