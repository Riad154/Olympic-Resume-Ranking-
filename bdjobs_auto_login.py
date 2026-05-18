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


def _is_ci():
    """Detect if running in a CI environment (GitHub Actions, etc.)."""
    return os.environ.get("GITHUB_ACTIONS", "").lower() == "true" or \
           os.environ.get("CI", "").lower() == "true"


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

    ci_mode = _is_ci()

    if args.username and args.password:
        creds = {"username": args.username.strip(), "password": args.password.strip()}
    else:
        # Try env vars next (used by GitHub Actions)
        env_user = os.environ.get("BDJOBS_USER", "").strip()
        env_pass = os.environ.get("BDJOBS_PASS", "").strip()
        if env_user and env_pass:
            creds = {"username": env_user, "password": env_pass}
        elif args.headless or ci_mode:
            # In CI/headless mode, don't try DB — fail fast with clear message
            print("[ERROR] No BDJobs credentials available in headless mode.", flush=True)
            print("        --username/--password args were empty or not provided.", flush=True)
            print("        BDJOBS_USER/BDJOBS_PASS env vars are also empty.", flush=True)
            print("", flush=True)
            print("        FIX: Add these secrets to your GitHub repo:", flush=True)
            print("          - BDJOBS_USER: your BDJobs recruiter username/email", flush=True)
            print("          - BDJOBS_PASS: your BDJobs recruiter password", flush=True)
            print("", flush=True)
            print("        Go to: GitHub repo → Settings → Secrets and variables → Actions", flush=True)
            sys.exit(1)
        else:
            creds = _get_db_creds()

    if not creds:
        print("[ERROR] No BDJobs credentials found.", flush=True)
        print("        Provide --username/--password, set BDJOBS_USER/BDJOBS_PASS env vars,", flush=True)
        print("        or store them in the PostgreSQL database.", flush=True)
        sys.exit(1)

    CONTEXT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bdjobs_session")
    BDJOBS_URL = "https://recruiter.bdjobs.com"
    SCREENSHOT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_login_failure.png")

    if args.force:
        import shutil
        if os.path.exists(CONTEXT_DIR):
            shutil.rmtree(CONTEXT_DIR)
            print(f"[INFO] Cleared session dir for fresh login: {CONTEXT_DIR}", flush=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        print(f"[ERROR] Playwright not installed ({e}). Run: pip install playwright && playwright install chromium", flush=True)
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

    # Extra args to avoid automation detection in headless mode
    browser_args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
        "--no-sandbox",
    ]
    if args.headless or ci_mode:
        browser_args.extend([
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
        ])

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=CONTEXT_DIR,
            headless=args.headless and not ci_mode,  # CI uses xvfb, not headless
            viewport={"width": 1366, "height": 768},
            accept_downloads=True,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            args=browser_args,
        )
        page = context.pages[0] if context.pages else context.new_page()

        # Override navigator.webdriver to avoid detection
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        print(f"[INFO] Navigating to {BDJOBS_URL} …", flush=True)
        page.goto(BDJOBS_URL, wait_until="domcontentloaded", timeout=30000)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        # ── Check if already logged in ──────────────────────────────────────
        if _is_logged_in(page):
            print("[OK] Already logged in (valid session).", flush=True)
            context.close()
            sys.exit(0)

        print("[INFO] Not authenticated. Proceeding with login form …", flush=True)

        # Pre-login screenshot for debugging
        try:
            page.screenshot(path=SCREENSHOT_PATH.replace("_login_failure", "_login_before"), full_page=True)
        except Exception:
            pass

        # ── Landing page detection ────────────────────────────────────────
        body_text = (page.evaluate("() => document.body.innerText") or "").lower()
        landing_markers = ["create or sign in to your account", "create account", "don't have an account", "post a job", "service packages"]
        is_landing = any(m in body_text for m in landing_markers)

        if is_landing:
            print("[INFO] Detected landing page. Looking for 'Sign in' link/button …", flush=True)
            signin_clicked = False
            for sel in ["a:has-text('Sign in')", "button:has-text('Sign in')", "a:has-text('Sign In')", "button:has-text('Sign In')",
                        "a[href*='signin']", "a[href*='login']", ".login-link", "#loginLink", "a:has-text('Login')", "button:has-text('Login')"]:
                try:
                    el = page.query_selector(sel)
                    if el:
                        print(f"[INFO] Clicking sign-in element: {sel}", flush=True)
                        el.click()
                        signin_clicked = True
                        time.sleep(4)
                        try:
                            page.wait_for_load_state("networkidle", timeout=15000)
                        except Exception:
                            pass
                        break
                except Exception as e:
                    print(f"[DEBUG] Selector {sel} failed: {e}", flush=True)
                    continue
            if not signin_clicked:
                print("[WARN] Could not find 'Sign in' link on landing page. Will try direct /signin URL.", flush=True)

        # ── Try to auto-fill login form ───────────────────────────────────
        print(f"[INFO] Auto-filling credentials for {creds['username']} …", flush=True)
        login_ok = False

        # Strategy: navigate directly to signin page if still on landing
        if is_landing and not _is_logged_in(page):
            signin_url = "https://recruiter.bdjobs.com/signin"
            try:
                print(f"[INFO] Navigating directly to {signin_url} …", flush=True)
                page.goto(signin_url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(3)
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
            except Exception as e:
                print(f"[WARN] Could not navigate to signin page ({e}), staying on current page.", flush=True)

        try:
            # Dump page HTML before attempting login (for debugging)
            try:
                html_path = SCREENSHOT_PATH.replace("_login_failure", "_login_page_dump")
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(page.content())
                print(f"[DEBUG] Page HTML dumped to: {html_path}", flush=True)
            except Exception:
                pass

            # Wait for login form to be fully rendered
            page.wait_for_selector("input[type='text'], input[type='email'], input#UserName, input[name='UserName'], input#username", timeout=15000)

            # Try multiple possible selectors for BDJobs login form
            user_sel = None
            for sel in ["input#UserName", "input[name='UserName']", "input#username", "input[type='text']", "input[type='email']"]:
                if page.query_selector(sel):
                    user_sel = sel
                    break
            pass_sel = None
            for sel in ["input#Password", "input[name='Password']", "input[type='password']"]:
                if page.query_selector(sel):
                    pass_sel = sel
                    break
            submit_sel = None
            for sel in ["button[type='submit']", "input[type='submit']", ".btn-login", "#btnLogin", "button:has-text('Sign In')", "button:has-text('Login')"]:
                if page.query_selector(sel):
                    submit_sel = sel
                    break

            if user_sel and pass_sel and submit_sel:
                print(f"[INFO] Found form fields: user={user_sel}, pass={pass_sel}, submit={submit_sel}", flush=True)

                # Method 1: Use JavaScript to set values (more reliable with Angular/SPA)
                page.evaluate(
                    """([userSel, passSel, userVal, passVal]) => {
                        const u = document.querySelector(userSel);
                        const p = document.querySelector(passSel);
                        if (u) {
                            u.value = userVal;
                            u.dispatchEvent(new Event('input', {bubbles:true}));
                            u.dispatchEvent(new Event('change', {bubbles:true}));
                            u.dispatchEvent(new Event('keyup', {bubbles:true}));
                        }
                        if (p) {
                            p.value = passVal;
                            p.dispatchEvent(new Event('input', {bubbles:true}));
                            p.dispatchEvent(new Event('change', {bubbles:true}));
                            p.dispatchEvent(new Event('keyup', {bubbles:true}));
                        }
                    }""",
                    [user_sel, pass_sel, creds["username"], creds["password"]]
                )
                print("[INFO] Credentials set via JS with input/change/keyup events.", flush=True)
                time.sleep(2)  # Wait for Angular to process

                # Method A: Click submit button
                print(f"[INFO] Clicking submit: {submit_sel}", flush=True)
                page.click(submit_sel, timeout=5000)

                # Wait and poll for result (Angular SPA may not navigate)
                print("[INFO] Polling for login result (up to 30s) …", flush=True)
                result = None
                for _ in range(30):
                    time.sleep(1)
                    try:
                        page.wait_for_load_state("networkidle", timeout=5000)
                    except Exception:
                        pass
                    body_text = (page.evaluate("() => document.body.innerText") or "").lower()
                    url = page.url.lower()

                    # Success: not on signin/login URL and has logged-in markers
                    if "signin" not in url and "login" not in url:
                        if any(m in body_text for m in ["dashboard", "logout", "my jobs", "job dashboard", "post a job"]):
                            result = "success"
                            break

                    # Error indicators
                    if "invalid credentials" in body_text:
                        result = "invalid_creds"
                        break
                    if "captcha" in body_text or "i'm not a robot" in body_text:
                        result = "captcha"
                        break
                    if "too many" in body_text or "temporarily blocked" in body_text:
                        result = "blocked"
                        break

                if result == "success":
                    print("[INFO] Login appears successful (detected logged-in UI).", flush=True)
                    login_ok = True
                elif result == "invalid_creds":
                    print("[ERROR] BDJobs returned 'Invalid Credentials'. The username or password is wrong.", flush=True)
                    print("        Username used: " + creds["username"], flush=True)
                    login_ok = False
                elif result == "captcha":
                    print("[ERROR] BDJobs is showing a CAPTCHA challenge.", flush=True)
                    login_ok = False
                elif result == "blocked":
                    print("[ERROR] Account temporarily blocked due to too many failed attempts.", flush=True)
                    login_ok = False
                else:
                    print("[WARN] Could not determine login result from polling. Checking auth state …", flush=True)
                    login_ok = True  # Let _is_logged_in() decide below
            else:
                print(f"[WARN] Could not find all login form fields.", flush=True)
                print(f"        user_field={user_sel}, pass_field={pass_sel}, submit={submit_sel}", flush=True)
                # Save HTML for debugging
                try:
                    html_path = SCREENSHOT_PATH.replace(".png", "_page.html")
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(page.content())
                    print(f"        Page HTML saved: {html_path}", flush=True)
                except Exception:
                    pass
        except Exception as e:
            print(f"[WARN] Could not auto-fill form ({e}).", flush=True)

        # ── Wait for SPA routing and any redirects ──────────────────────
        time.sleep(3)
        try:
            page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass

        # Dump page HTML for debugging if login failed
        if not login_ok:
            try:
                html_path = SCREENSHOT_PATH.replace(".png", "_page.html")
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(page.content())
                print(f"[DEBUG] Page HTML saved: {html_path}", flush=True)
            except Exception:
                pass

        # ── Verify login succeeded ────────────────────────────────────────
        if _is_logged_in(page):
            print("[OK] Login successful!", flush=True)
            context.close()
            print(f"[DONE] Session saved to: {CONTEXT_DIR}", flush=True)
            sys.exit(0)

        # ── Login failed — capture diagnostics ──────────────────────────
        print("[ERROR] Login failed. Session is NOT authenticated.", flush=True)
        print(f"        Final URL: {page.url}", flush=True)
        try:
            body_text = (page.evaluate("() => document.body.innerText") or "")
            print(f"        Page text preview: {body_text[:500]}...", flush=True)
            # Detect specific error patterns
            body_lower = body_text.lower()
            if "invalid credentials" in body_lower:
                print("[DIAGNOSIS] BDJobs explicitly rejected the password.", flush=True)
                print("            The BDJOBS_USER / BDJOBS_PASS secrets are incorrect.", flush=True)
                print("            ACTION: Log in manually at https://recruiter.bdjobs.com", flush=True)
                print("                    with the SAME credentials to verify them.", flush=True)
            elif "captcha" in body_lower or "i'm not a robot" in body_lower:
                print("[DIAGNOSIS] BDJobs is showing a CAPTCHA challenge.", flush=True)
                print("            ACTION: Wait 10-15 minutes and retry, or use manual login.", flush=True)
            elif "too many" in body_lower or "temporarily blocked" in body_lower:
                print("[DIAGNOSIS] Account temporarily blocked due to too many failed attempts.", flush=True)
                print("            ACTION: Wait 30 minutes before retrying.", flush=True)
        except Exception:
            pass

        # Take screenshot for debugging
        try:
            page.screenshot(path=SCREENSHOT_PATH, full_page=True)
            print(f"        Screenshot saved: {SCREENSHOT_PATH}", flush=True)
        except Exception as e:
            print(f"        (screenshot failed: {e})", flush=True)

        if args.wait_for_flag:
            flag = Path(args.wait_for_flag)
            deadline = time.time() + args.max_wait_minutes * 60
            print(f"[WAITING] Polling for sentinel: {flag}", flush=True)
            while time.time() < deadline:
                if flag.exists():
                    print("[OK] Sentinel detected.", flush=True)
                    try: flag.unlink()
                    except Exception: pass
                    break
                time.sleep(1)
            else:
                print("[TIMEOUT] No sentinel received.", flush=True)
                context.close()
                sys.exit(2)
        elif args.headless or ci_mode:
            print("[ERROR] Login failed in headless/CI mode. Cannot prompt for manual login.", flush=True)
            print("        Possible causes:", flush=True)
            print("          1. Wrong BDJOBS_USER / BDJOBS_PASS credentials", flush=True)
            print("          2. BDJobs is showing a CAPTCHA challenge", flush=True)
            print("          3. The login page structure has changed", flush=True)
            print("          4. BDJobs is blocking headless browser access", flush=True)
            print("", flush=True)
            print("        FIX: Use --force to clear session and retry with correct credentials.", flush=True)
            context.close()
            sys.exit(1)
        else:
            input(">>> Press ENTER after you have logged in manually … ")

        context.close()
        print(f"[DONE] Session saved to: {CONTEXT_DIR}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print(f"[FATAL] Unexpected error: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)
