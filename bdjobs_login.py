"""
bdjobs_login.py — One-time BDJobs login session saver
Olympic Industries PLC — AI Resume Ranking System (Phase 0, Step 1)

Usage:
    python bdjobs_login.py

Opens a Chromium browser. HR logs into BDJobs manually.
Once logged in, press Enter in the terminal to save the session.
All subsequent scripts reuse the saved session — no re-login needed.
"""

import argparse
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

# ── Configuration ──────────────────────────────────────────────────────────────
CONTEXT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bdjobs_session")
BDJOBS_LOGIN_URL = "https://recruiter.bdjobs.com"
# ───────────────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="BDJobs One-time Login Session Saver")
    parser.add_argument("--wait-for-flag", default=None,
                        help="Path to a sentinel file. If set, the script polls every "
                             "second for this file to exist instead of waiting for the user "
                             "to press Enter. Used by the Streamlit dashboard to drive login "
                             "non-interactively.")
    parser.add_argument("--poll-seconds", type=int, default=1,
                        help="How often to check for --wait-for-flag (default: 1).")
    parser.add_argument("--max-wait-minutes", type=int, default=15,
                        help="Hard cap on the wait. Defaults to 15 minutes.")
    args, _ = parser.parse_known_args()

    context_path = Path(CONTEXT_DIR)

    if context_path.exists():
        print(f"[INFO] Existing session found at: {context_path}")
        print("       This will be overwritten with the new login session.")
    else:
        print(f"[INFO] No existing session. A new one will be created at: {context_path}")

    print()
    print("=" * 60)
    print("  BDJobs Login — Session Saver")
    print("=" * 60)
    print()
    print("  1. A browser window will open to the BDJobs login page.")
    print("  2. Log in with your BDJobs employer account.")
    print("  3. Once you see your dashboard, come back here")
    print("     and press ENTER to save the session.")
    print()

    with sync_playwright() as p:
        # Launch persistent context — this is what stores cookies/localStorage
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(context_path),
            headless=False,
            viewport={"width": 1280, "height": 900},
            accept_downloads=True,
            args=[
                "--disable-blink-features=AutomationControlled",
            ],
        )

        page = context.pages[0] if context.pages else context.new_page()

        try:
            page.goto(BDJOBS_LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"[ERROR] Could not load BDJobs login page: {e}")
            print("        Check your internet connection and try again.")
            context.close()
            sys.exit(1)

        print("[WAITING] Browser is open. Log in to BDJobs now.")
        print()

        if args.wait_for_flag:
            flag = Path(args.wait_for_flag)
            try: flag.unlink()
            except FileNotFoundError: pass
            except Exception: pass
            deadline = time.time() + args.max_wait_minutes * 60
            print(f"[WAITING] Polling for sentinel file: {flag}")
            print(f"          (Streamlit will create this file when you click 'I'm done logging in'.)")
            try:
                while time.time() < deadline:
                    if flag.exists():
                        print(f"[OK] Sentinel file detected at {flag}; saving session.")
                        try: flag.unlink()
                        except Exception: pass
                        break
                    time.sleep(args.poll_seconds)
                else:
                    print(f"[TIMEOUT] No sentinel after {args.max_wait_minutes} min. Session NOT saved.")
                    context.close()
                    sys.exit(2)
            except KeyboardInterrupt:
                print("\n[ABORT] Cancelled by user. Session NOT saved.")
                context.close()
                sys.exit(1)
        else:
            try:
                input(">>> Press ENTER here after you have logged in successfully... ")
            except KeyboardInterrupt:
                print("\n[ABORT] Cancelled by user. Session NOT saved.")
                context.close()
                sys.exit(1)

        # Verify we're no longer on the login page
        current_url = page.url.lower()
        if "signin" in current_url or "login" in current_url:
            print("[WARNING] You still appear to be on the login page.")
            print("          The session will be saved anyway, but it may not")
            print("          contain valid credentials. Re-run if needed.")
        else:
            print("[OK] Login detected. Saving session...")

        context.close()

    print()
    print(f"[DONE] Session saved to: {context_path}")
    print("       You can now run bdjobs_downloader.py — it will reuse this session.")
    print("       Re-run this script any time the session expires.")


if __name__ == "__main__":
    main()
