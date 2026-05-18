"""
bdjobs_downloader.py — BDJobs Bulk Resume Downloader
Olympic Industries PLC — AI Resume Ranking System (Phase 0, Step 2)

Usage:
    python bdjobs_downloader.py                                  # interactive
    python bdjobs_downloader.py --label X --url "https://..."   # non-interactive

Prerequisites:
    - Run bdjobs_login.py first to save a valid session.

Output folder structure per run:
    downloaded_resumes/
    └── {job_id}/
        ├── profiles_txt/          ← profile text scraped from popup iframe
        │   └── {Name}_{ApplyID}.txt
        ├── uploaded_cvs/          ← uploaded CV PDFs from card icon
        │   └── {job_id}_{Name}_{ts}_uploaded.pdf
        ├── {job_id}_metadata.csv  ← full candidate metadata + status per row
        ├── candidates.json        ← raw API response, all candidates
        └── failed_downloads.json  ← failed entries for retry (if any)

Profile text: scraped from popup iframe (app-cv-details selector).
              Replaces the broken profile PDF download approach.
Uploaded CV:  downloaded via card icon click (expect_download), same as before.
"""

import argparse
import csv
import json
import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout
from tqdm import tqdm

# When stdout is a pipe (e.g. Streamlit subprocess), tqdm spams one line per
# update which makes parsing brittle. Detect that and emit structured progress
# lines instead.
_NON_TTY = not sys.stdout.isatty()


def _emit_progress(i: int, total: int, txt_ok: int, cv_ok: int, fail: int,
                   ui_page: int = 0, last_name: str = "") -> None:
    """Print a single-line, machine-parseable progress beacon.

    Streamlit's Download CVs page tails the log, picks the LAST [PROGRESS]
    line, and renders st.progress() + 4 metrics from it. Always flush so the
    pipe sees it immediately.
    """
    payload = json.dumps({
        "i":         i,
        "total":     total,
        "txt":       txt_ok,
        "cv":        cv_ok,
        "fail":      fail,
        "ui_page":   ui_page,
        "last_name": last_name[:60],
    }, ensure_ascii=False)
    print(f"[PROGRESS] {payload}", flush=True)


# Force UTF-8 on stdout/stderr so non-ASCII chars (e.g. arrows in our log lines)
# don't crash with UnicodeEncodeError on Windows when this script is launched
# with redirected stdout by Streamlit. Best-effort; safe on Python 3.7+.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ── Configuration ──────────────────────────────────────────────────────────────
CONTEXT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bdjobs_session")
OUTPUT_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloaded_resumes")

DELAY_MIN            = 0.5    # seconds between candidates
DELAY_MAX            = 1.5    # — still randomized for anti-bot
PAGE_LOAD_TIMEOUT    = 30000  # ms
POPUP_TIMEOUT        = 15000  # ms
DOWNLOAD_TIMEOUT     = 30000  # ms
IFRAME_POLL_TIMEOUT  = 20     # seconds to wait for iframe text content
MIN_PROFILE_CHARS    = 300    # minimum chars to accept as a valid profile scrape
UI_PAGE_SIZE         = 50     # candidates per UI page
# ───────────────────────────────────────────────────────────────────────────────

CSV_COLUMNS = [
    "index",
    "candidate_name",
    "apply_id",
    "application_date",
    "age",
    "expected_salary",
    "current_salary",
    "bdjobs_match_score",
    "email",
    "mobile",
    "location",
    "degree",
    "university",
    "experience",
    "profile_txt_file",
    "profile_txt_chars",
    "profile_txt_status",
    "uploaded_cv_file",
    "uploaded_cv_status",
    "has_uploaded_cv",
    "timestamp",
]


# ══════════════════════════════════════════════════════════════════════════════
# Utilities
# ══════════════════════════════════════════════════════════════════════════════

def sanitize_filename(name: str) -> str:
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s]+", "_", name.strip())
    return name[:80]  # cap length


def build_list_api_url(company_id: str, job_number: str, pg_no: int) -> str:
    return (
        f"https://testmongo.bdjobs.com/api/api/AllApplicantSearchResult"
        f"?CompanyId={company_id}"
        f"&jobno={job_number}"
        f"&ordTyp=OMP&pgtype=al&sIdentity=0&stype=al"
        f"&age=/&exp=/&qOrg=&qInst=&qJobLevel=&qs=&qloc=0&valLocType=0&sal=/&qWork="
        f"&pg_size={UI_PAGE_SIZE}&pg_no={pg_no}"
        f"&AppliedFromLinkedIn=1&JobPaid=0&qInvited=0&qLocName="
        f"&sortby=&sorttype=&NT=&qarmy=0&module="
        f"&assmntResult=&assmntOperator=&qmlloc=&qmlskill="
        f"&newCount=0&pwd=0&FairID=0&FromLeftFilterSearch=0"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Profile text scrape
# ══════════════════════════════════════════════════════════════════════════════

def wait_for_iframe_content(page, min_chars: int = MIN_PROFILE_CHARS,
                             timeout: int = IFRAME_POLL_TIMEOUT) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            length = page.evaluate("""
                () => {
                    const iframe = document.querySelector('iframe');
                    if (!iframe) return 0;
                    const doc = iframe.contentDocument || iframe.contentWindow.document;
                    if (!doc || !doc.body) return 0;
                    const el = doc.querySelector('app-cv-details') || doc.body;
                    return (el.innerText || '').length;
                }
            """)
            if length >= min_chars:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def extract_iframe_text(page) -> str:
    JS = """
    () => {
        const iframe = document.querySelector('iframe');
        if (!iframe) return '';
        const doc = iframe.contentDocument || iframe.contentWindow.document;
        if (!doc || !doc.body) return '';
        const el = doc.querySelector('app-cv-details') || doc.body;
        const raw = el.innerText || el.textContent || '';
        const lines = raw.split('\\n').map(l => l.trim());
        const cleaned = [];
        let prevBlank = false;
        for (const line of lines) {
            if (line === '') {
                if (!prevBlank) cleaned.push('');
                prevBlank = true;
            } else {
                cleaned.push(line);
                prevBlank = false;
            }
        }
        return cleaned.join('\\n').trim();
    }
    """
    try:
        return page.evaluate(JS)
    except Exception:
        return ""


def close_popup(page):
    try:
        btn = page.query_selector("span.icon-cross-close")
        if btn:
            btn.click()
            time.sleep(0.4)
            return
    except Exception:
        pass
    try:
        page.keyboard.press("Escape")
        time.sleep(0.4)
    except Exception:
        pass


def scrape_profile_text(page, card, applicant: dict,
                        txt_dir: str) -> tuple[str, int, str]:
    """
    Click candidate name → popup → iframe → extract text → save .txt
    Returns (filename, char_count, status)
    """
    apply_id  = str(applicant.get("ApplyID", ""))
    name      = applicant.get("Name", "Unknown")
    safe_name = sanitize_filename(name)

    # Click name button
    try:
        name_btn = card.query_selector("button.text-base.text-left")
        if not name_btn:
            # Fallback: button with candidate's first name text
            first = name.split()[0] if name else ""
            name_btn = card.query_selector(f'button:has-text("{first}")')
        if not name_btn:
            return "", 0, "failed_no_name_button"
        name_btn.click()
    except Exception as e:
        return "", 0, f"failed_click: {e}"

    # Wait for iframe
    try:
        page.wait_for_selector("iframe", timeout=POPUP_TIMEOUT)
    except PwTimeout:
        close_popup(page)
        return "", 0, "failed_iframe_timeout"

    # Poll for rendered content
    got_content = wait_for_iframe_content(page)
    if not got_content:
        # Extract anyway — partial content is still useful
        pass

    text = extract_iframe_text(page)
    close_popup(page)

    if not text or len(text) < MIN_PROFILE_CHARS:
        return "", len(text) if text else 0, f"failed_insufficient_content"

    # Build file header with metadata from API
    header = (
        f"=== BDJobs Candidate Profile ===\n"
        f"Name:          {name}\n"
        f"ApplyID:       {apply_id}\n"
        f"CrpApplID:     {applicant.get('CrpApplID', '')}\n"
        f"Email:         {applicant.get('Email', '')}\n"
        f"Mobile:        {applicant.get('Mobile', '')}\n"
        f"Degree:        {applicant.get('Degree', '')}\n"
        f"University:    {applicant.get('University', '')}\n"
        f"Experience:    {applicant.get('Exps', applicant.get('Exp', ''))}\n"
        f"Location:      {applicant.get('ApplicantLocation', '')}\n"
        f"CurrentSalary: {applicant.get('ApplicantCurrentSalary', '')}\n"
        f"ExpSalary:     {applicant.get('Salary', '')}\n"
        f"MatchScore:    {applicant.get('MatchingScore', '')}%\n"
        f"AppliedDate:   {applicant.get('AppliedDate', '')}\n"
        f"AttachedCV:    {'Yes' if applicant.get('AttachedCV') == 1 else 'No'}\n"
        f"ScrapedAt:     {datetime.now().isoformat()}\n"
        f"{'=' * 44}\n\n"
    )

    fname = f"{safe_name}_{apply_id}.txt"
    fpath = os.path.join(txt_dir, fname)
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(header + text)

    return fname, len(text), "success"


# ══════════════════════════════════════════════════════════════════════════════
# Uploaded CV download
# ══════════════════════════════════════════════════════════════════════════════

def download_uploaded_cv(page, card, job_id: str, safe_name: str,
                          ts: str, cv_dir: str) -> tuple[str, str]:
    """
    Click the red PDF icon on the card → expect_download → save.
    Returns (filename, status).

    BDJobs CV button is highly variable across candidate cards.
    We use a cascading strategy:
      1. Scroll card into view + hover to reveal lazy buttons.
      2. Deep DOM search inside the card for any clickable PDF/download element.
      3. Try direct click → JS click → keyboard Enter → parent row click.
      4. If all button-based approaches fail, try page-level keydown(Ctrl+J)
         which many Angular apps bind to "download" actions.
    """
    # ── 1. Scroll into view + hover to reveal lazy elements ───────
    try:
        card.evaluate("el => { el.scrollIntoView({block:'center'}); el.dispatchEvent(new MouseEvent('mouseover',{bubbles:true})); }")
        time.sleep(0.4)
    except Exception:
        pass

    # ── 2. Deep DOM search for PDF / download trigger ─────────────
    cv_btn = None

    # Phase A: exact known selectors
    selectors = [
        "span.icon-pdf-file",
        "button:has(span.icon-pdf-file)",
        "span[class*='pdf']",
        "button[title*='PDF']",
        "button[title*='Download']",
        "a[title*='PDF']",
        "a[title*='Download']",
        "button:has-text('PDF')",
        "button:has-text('Download')",
        "a:has-text('PDF')",
        "a:has-text('Download')",
        "i[class*='pdf']",
        "img[src*='pdf']",
        "[class*='download']",
        "[class*='cv-download']",
        "[class*='attachment']",
    ]
    for sel in selectors:
        try:
            cv_btn = card.query_selector(sel)
            if cv_btn:
                break
        except Exception:
            pass

    # Phase B: XPath text search (broader than just "PDF")
    if not cv_btn:
        try:
            cv_btn = card.query_selector("xpath=.//*[contains(translate(text(),'PDFpdf','PDFPDF'),'PDF')]")
        except Exception:
            pass
    if not cv_btn:
        try:
            cv_btn = card.query_selector("xpath=.//*[contains(translate(text(),'DOWNLOAdownload','DOWNLOAdownload'),'DOWNLOAD')]")
        except Exception:
            pass

    # Phase C: look for ANY <button> or <a> inside the card that is small
    # (download icons are typically small inline elements)
    if not cv_btn:
        try:
            btns = card.query_selector_all("button, a")
            for b in btns:
                try:
                    box = b.bounding_box()
                    if box and box["width"] < 80 and box["height"] < 50:
                        # likely an icon button
                        cv_btn = b
                        break
                except Exception:
                    continue
        except Exception:
            pass

    # Phase D: last resort — use JS to find the element with the CV icon
    if not cv_btn:
        try:
            js_result = card.evaluate("""el => {
                const all = el.querySelectorAll('*');
                for (const c of all) {
                    const cls = (c.className || '').toLowerCase();
                    const txt = (c.innerText || c.textContent || '').toLowerCase();
                    const tag = c.tagName.toLowerCase();
                    if (cls.includes('pdf') || cls.includes('download') || cls.includes('cv')
                        || txt.includes('pdf') || txt.includes('download')
                        || c.getAttribute('title')?.toLowerCase().includes('pdf')) {
                        if (tag === 'button' || tag === 'a' || tag === 'span' || tag === 'i') {
                            return c;
                        }
                    }
                }
                return null;
            }""")
            if js_result:
                cv_btn = js_result
        except Exception:
            pass

    if not cv_btn:
        return "", "no_button"

    # ── 3. Click / trigger download with cascading fallbacks ────────
    download_triggered = False
    dl_info = None

    # Strategy A: standard Playwright click with expect_download
    try:
        with page.expect_download(timeout=DOWNLOAD_TIMEOUT) as _dl:
            cv_btn.click()
        dl_info = _dl.value
        download_triggered = True
    except PwTimeout:
        pass  # will try next strategy
    except Exception:
        pass

    # Strategy B: JS click + synthetic events on the element
    if not download_triggered:
        try:
            with page.expect_download(timeout=DOWNLOAD_TIMEOUT) as _dl:
                cv_btn.evaluate("""el => {
                    el.click();
                    el.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,button:0}));
                    el.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,button:0}));
                    el.dispatchEvent(new MouseEvent('click',{bubbles:true,button:0}));
                    // If it's an <a> with href, force navigation
                    if (el.tagName === 'A' && el.href) { window.open(el.href,'_blank'); }
                }""")
            dl_info = _dl.value
            download_triggered = True
        except PwTimeout:
            pass
        except Exception:
            pass

    # Strategy C: hover + keyboard Enter on the card (Angular lazy-load)
    if not download_triggered:
        try:
            with page.expect_download(timeout=DOWNLOAD_TIMEOUT) as _dl:
                card.evaluate("el => { el.focus(); el.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true})); }")
                time.sleep(0.5)
            dl_info = _dl.value
            download_triggered = True
        except PwTimeout:
            pass
        except Exception:
            pass

    # Strategy D: page-level Ctrl+J or Ctrl+S (last resort)
    if not download_triggered:
        try:
            with page.expect_download(timeout=DOWNLOAD_TIMEOUT) as _dl:
                page.keyboard.press("Control+j")
                time.sleep(0.5)
            dl_info = _dl.value
            download_triggered = True
        except PwTimeout:
            pass
        except Exception:
            pass

    if not download_triggered:
        return "", "failed_download_timeout"

    # Save the downloaded file
    filename  = f"{job_id}_{safe_name}_{ts}_uploaded.pdf"
    save_path = os.path.join(cv_dir, filename)
    dl_info.save_as(save_path)

    if os.path.exists(save_path) and os.path.getsize(save_path) > 100:
        with open(save_path, "rb") as f:
            header = f.read(5)
        status = "success" if header == b"%PDF-" else "success_unverified"
    else:
        status = "failed_empty"
    return filename, status


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def _advance_to_page(page, target_page: int, job_dir: str) -> bool:
    """Try to advance to the target page.

    Returns True if successful, False on failure (pagination DOM + screenshot
    dumped to job_dir).
    """
    import random

    # ── Strategy 1: Next-button click ────────────────────────────────────
    try:
        next_btn = page.query_selector("button[aria-label='Next']")
        if next_btn:
            # Check if disabled
            disabled = next_btn.evaluate("el => el.disabled || el.getAttribute('disabled')")
            if not disabled:
                next_btn.click()
                # Wait for cards AND verify we have some cards on the new page
                for wait_attempt in range(5):
                    time.sleep(1.5 + random.uniform(0.5, 1.5))
                    cards = page.query_selector_all("app-applicant-card")
                    if len(cards) >= 1:
                        return True
                # Cards still not visible — maybe slow network
                time.sleep(3)
                cards = page.query_selector_all("app-applicant-card")
                if len(cards) >= 1:
                    return True
    except Exception as e:
        pass

    # ── Strategy 2: page-number-N button click ────────────────────────────
    try:
        page_num_btn = page.query_selector(f"button:has-text('{target_page}')")
        if page_num_btn:
            page_num_btn.click()
            for wait_attempt in range(5):
                time.sleep(1.5 + random.uniform(0.5, 1.5))
                cards = page.query_selector_all("app-applicant-card")
                if len(cards) >= 1:
                    return True
            time.sleep(3)
            cards = page.query_selector_all("app-applicant-card")
            if len(cards) >= 1:
                return True
    except Exception:
        pass

    # ── Strategy 3: arrow-button pagination (BDJobs uses right-arrow) ─────
    try:
        arrow = page.query_selector("button.pagination-next, a.pagination-next, .next-page, [aria-label='Next page']")
        if arrow:
            arrow.click()
            for wait_attempt in range(5):
                time.sleep(1.5 + random.uniform(0.5, 1.5))
                cards = page.query_selector_all("app-applicant-card")
                if len(cards) >= 1:
                    return True
    except Exception:
        pass

    # ── Strategy 4: JS window.scrollTo bottom + wait for Angular ──────────
    try:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)
        cards = page.query_selector_all("app-applicant-card")
        if len(cards) >= 1:
            return True
    except Exception:
        pass

    # Dump pagination DOM + screenshot on failure
    try:
        page_content = page.content()
        with open(os.path.join(job_dir, "_pagination_dom.html"), "w", encoding="utf-8") as f:
            f.write(page_content)
    except Exception:
        pass
    try:
        page.screenshot(path=os.path.join(job_dir, "_pagination_failure.png"), full_page=True)
    except Exception:
        pass

    return False


def _is_ci():
    """Detect if running in a CI environment (GitHub Actions, etc.)."""
    return os.environ.get("GITHUB_ACTIONS", "").lower() == "true" or \
           os.environ.get("CI", "").lower() == "true"


def main():
    # Session dir check is deferred until after arg parsing.
    # In CI/headless mode, auto-login creates the dir; if missing, create
    # an empty one so Playwright can start (session cookies come from login step).
    ci_mode = _is_ci()
    if not Path(CONTEXT_DIR).exists():
        if "--headless" in sys.argv or ci_mode:
            os.makedirs(CONTEXT_DIR, exist_ok=True)
            print(f"[INFO] Created empty session dir: {CONTEXT_DIR}")
        else:
            print("[ERROR] No saved session found. Run bdjobs_login.py first.")
            sys.exit(1)

    print()
    print("=" * 60)
    print("  BDJobs Bulk Resume Downloader")
    print("=" * 60)
    print()

    # ── Inputs (CLI args take precedence; fall back to interactive) ──────────
    parser = argparse.ArgumentParser(
        description="BDJobs Bulk Resume Downloader",
        add_help=True,
    )
    parser.add_argument("--label", "-l", default=None,
                        help="Job label / folder name (e.g. AI_Executive_Mar2026)")
    parser.add_argument("--url",   "-u", default=None,
                        help="BDJobs applicant list URL containing ?jobno=...")
    # Filter options for large job postings
    parser.add_argument("--max-candidates", "-m", type=int, default=None,
                        help="Limit download to first N candidates (default: all)")
    parser.add_argument("--min-score", type=int, default=0,
                        help="Minimum BDJobs match score %% to include (default: 0)")
    parser.add_argument("--cv-only", action="store_true",
                        help="Only download candidates with uploaded CV")
    parser.add_argument("--location", type=str, default="",
                        help="Filter by location substring (case-insensitive)")
    parser.add_argument("--exp-keyword", type=str, default="",
                        help="Filter by experience substring (case-insensitive)")
    parser.add_argument("--headless", action="store_true",
                        help="Run browser in headless mode (required for CI/GitHub Actions)")
    args, _unknown = parser.parse_known_args()

    if args.headless or ci_mode:
        # In headless/CI mode, all args must come from CLI — no interactive prompts
        job_id = (args.label or "").strip()
        if not job_id:
            print("[ERROR] --label is required in headless/CI mode.")
            sys.exit(1)
        applicant_url = (args.url or "").strip()
        if not applicant_url:
            print("[ERROR] --url is required in headless/CI mode.")
            sys.exit(1)
    else:
        job_id = (args.label or "").strip() or input("Enter job label (e.g. AI_Executive_Mar2026): ").strip()
        applicant_url = (args.url or "").strip() or input("Paste applicant list URL: ").strip()

    if not job_id:
        print("[ERROR] Job label cannot be empty.")
        sys.exit(1)
    job_id_safe = sanitize_filename(job_id)
    if not applicant_url:
        print("[ERROR] URL cannot be empty.")
        sys.exit(1)

    parsed     = urlparse(applicant_url)
    qs         = parse_qs(parsed.query)
    job_number = qs.get("jobno", [None])[0]
    if not job_number:
        print("[ERROR] Could not extract jobno from URL.")
        sys.exit(1)

    # ── Folder structure ──────────────────────────────────────────────────────
    job_dir  = os.path.join(OUTPUT_DIR, job_id_safe)
    txt_dir  = os.path.join(job_dir, "profiles_txt")
    cv_dir   = os.path.join(job_dir, "uploaded_cvs")
    csv_path    = os.path.join(job_dir, f"{job_id_safe}_metadata.csv")
    json_path   = os.path.join(job_dir, "candidates.json")
    failed_path = os.path.join(job_dir, "failed_downloads.json")

    for d in [job_dir, txt_dir, cv_dir]:
        os.makedirs(d, exist_ok=True)

    print()
    print(f"  Job label    : {job_id_safe}")
    print(f"  Job number   : {job_number}")
    print(f"  Output root  : {job_dir}")
    print(f"  Profiles txt : {txt_dir}")
    print(f"  Uploaded CVs : {cv_dir}")
    print(f"  Metadata CSV : {csv_path}")
    print()

    with sync_playwright() as p:
        # In CI with xvfb, run headless=False (xvfb provides the display)
        # In local mode, respect the --headless flag if passed
        browser_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
        ]
        if ci_mode:
            browser_args.extend([
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ])
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=CONTEXT_DIR,
            headless=args.headless and not ci_mode,
            viewport={"width": 1400, "height": 900},
            accept_downloads=True,
            args=browser_args,
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # ── Load page + validate session ──────────────────────────────────
        print("[INFO] Loading applicant list page...")
        try:
            page.goto(applicant_url, wait_until="domcontentloaded",
                      timeout=PAGE_LOAD_TIMEOUT)
        except Exception as e:
            print(f"[ERROR] Could not load URL: {e}")
            ctx.close()
            sys.exit(1)

        # Wait for the SPA to settle before the auth-redirect check — the
        # Angular router can switch from the deep-link URL to the login route
        # AFTER the initial domcontentloaded fires.
        try:
            page.wait_for_load_state("networkidle", timeout=PAGE_LOAD_TIMEOUT)
        except PwTimeout:
            pass  # not fatal; continue with detection below

        def _on_login_page() -> bool:
            u = page.url.lower()
            if "signin" in u or "login" in u:
                return True
            # Sometimes the URL stays on /applicants but the SPA renders the
            # login component instead (app-login element present, no app-root
            # children for the dashboard).
            try:
                if page.query_selector("app-login"):
                    return True
            except Exception:
                pass
            return False

        if _on_login_page():
            print("[ERROR] Session is not authenticated for this URL.")
            print(f"        Final URL: {page.url}")
            print("        Open the dashboard in Streamlit, click 'Re-login to BDJobs',")
            print("        log in, then navigate Dashboard → your job → View Applicants")
            print("        BEFORE clicking 'I've finished logging in'.")
            ctx.close()
            sys.exit(1)

        # Wait for applicant cards. If they never appear it usually means one
        # of three things: zero applicants (BDJobs renders skeleton loaders
        # forever), the Angular app's DOM tag was renamed, or the API stalled.
        # We don't fail here -- the API fetch below is the source of truth.
        cards_visible = False
        try:
            page.wait_for_selector("app-applicant-card", timeout=PAGE_LOAD_TIMEOUT)
            cards_visible = True
            print("[OK] Session valid, cards loaded.")
        except PwTimeout:
            print("[WARN] No <app-applicant-card> elements after "
                  f"{PAGE_LOAD_TIMEOUT // 1000}s -- continuing via API "
                  "(the job may have zero applicants).")

            # Best-effort diagnostic dump to help debug DOM changes.
            try:
                diag = page.evaluate("""() => {
                    const cnt = sel => document.querySelectorAll(sel).length;
                    const txt = (document.body.innerText || '').split('\\n')
                        .map(s => s.trim()).filter(Boolean).slice(0, 30).join(' | ');
                    return {
                        url:   location.href,
                        appLogin:        cnt('app-login'),
                        appApplicantCard:cnt('app-applicant-card'),
                        appApplicantList:cnt('app-applicant-list'),
                        anyAppTag:       Array.from(document.querySelectorAll('*'))
                            .map(e => e.tagName.toLowerCase())
                            .filter(t => t.startsWith('app-'))
                            .reduce((a,t) => (a[t]=(a[t]||0)+1, a), {}),
                        topText: txt.slice(0, 1500),
                    };
                }""")
                print(f"        Final URL  : {page.url}")
                try:
                    print(f"        Page title : {page.title()}")
                except Exception:
                    pass
                print(f"        <app-login>          : {diag.get('appLogin')}")
                print(f"        <app-applicant-card> : {diag.get('appApplicantCard')}")
                print(f"        <app-applicant-list> : {diag.get('appApplicantList')}")
                tags = diag.get("anyAppTag") or {}
                if tags:
                    print("        Any <app-*> tags     : "
                          + ", ".join(f"{k}={v}" for k, v in sorted(tags.items())))
                print("        Top body text :")
                print(f"        {diag.get('topText','')}")
            except Exception as e:
                print(f"        (diagnostics evaluation failed: {e})")

            # Save a screenshot so the Streamlit page can surface it.
            try:
                shot_path = os.path.join(job_dir, "_failure_screenshot.png")
                page.screenshot(path=shot_path, full_page=True)
                print(f"        Screenshot : {shot_path}")
            except Exception as e:
                print(f"        (screenshot failed: {e})")

        # ── Extract CompanyId ─────────────────────────────────────────────
        company_id = page.evaluate("""() => {
            try {
                const cookies = document.cookie.split(';');
                for (const c of cookies) {
                    const [name, val] = c.trim().split('=');
                    if (name === 'Company') {
                        const match = val.match(/ComNo=([^&]+)/);
                        if (match) return decodeURIComponent(match[1]);
                    }
                }
                const li = localStorage.getItem('CompanyId');
                if (li) return li;
            } catch(e) {}
            return null;
        }""")

        if not company_id:
            if args.headless:
                print("[ERROR] CompanyId not found automatically and cannot prompt in headless mode.")
                print("        The login session may not be valid for this job URL.")
                ctx.close()
                sys.exit(1)
            company_id = input("CompanyId not found automatically. Enter it (e.g. ZiC6PiY=): ").strip()
        if not company_id:
            print("[ERROR] CompanyId is required.")
            ctx.close()
            sys.exit(1)

        print(f"[INFO] CompanyId: {company_id}")

        # ── Fetch all candidates via in-browser fetch() ───────────────────
        print("[INFO] Fetching candidate list from API...")

        all_applicants   = []
        total_candidates = 0
        api_page         = 1

        while True:
            api_url = build_list_api_url(company_id, job_number, api_page)
            batch = page.evaluate("""async (url) => {
                try {
                    const resp = await fetch(url, { credentials: 'include' });
                    const data = await resp.json();
                    return {
                        error:      data.Error,
                        total:      data.TotalCVFound,
                        applicants: data.Applicants || []
                    };
                } catch(e) {
                    return { error: e.message, total: 0, applicants: [] };
                }
            }""", api_url)

            err = batch.get("error")
            if err not in (0, "0", None, ""):
                if api_page == 1:
                    print(f"[ERROR] API error: {err}")
                    ctx.close()
                    sys.exit(1)
                break

            if api_page == 1:
                total_candidates = batch.get("total", 0)
                print(f"[INFO] Total candidates reported: {total_candidates}")

            fetched = batch.get("applicants", [])
            if not fetched:
                break

            all_applicants.extend(fetched)
            print(f"  Page {api_page}: +{len(fetched)} | running total: {len(all_applicants)}")

            if len(all_applicants) >= total_candidates:
                break
            api_page += 1
            time.sleep(0.4)

        # Deduplicate by ApplyID
        seen, unique = set(), []
        for a in all_applicants:
            aid = str(a.get("ApplyID", ""))
            if aid and aid not in seen:
                seen.add(aid)
                unique.append(a)
            elif not aid:
                unique.append(a)
        if len(unique) < len(all_applicants):
            print(f"[INFO] Deduplicated: {len(all_applicants)} → {len(unique)}")
        all_applicants = unique

        # ── Apply Filters (if specified) ──────────────────────────────────────
        original_count = len(all_applicants)
        filtered = []
        for a in all_applicants:
            # Min BDJobs score filter
            score_str = str(a.get("MatchingScore", "0")).replace("%", "")
            try:
                score = float(score_str) if score_str else 0
            except ValueError:
                score = 0
            if score < args.min_score:
                continue

            # CV-only filter
            if args.cv_only and a.get("AttachedCV") != 1:
                continue

            # Location filter
            if args.location:
                loc = str(a.get("ApplicantLocation", "")).lower()
                if args.location.lower() not in loc:
                    continue

            # Experience keyword filter
            if args.exp_keyword:
                exp = str(a.get("Exps", a.get("Exp", ""))).lower()
                if args.exp_keyword.lower() not in exp:
                    continue

            filtered.append(a)

        all_applicants = filtered

        # Max candidates limit
        if args.max_candidates and len(all_applicants) > args.max_candidates:
            print(f"[INFO] Limiting to first {args.max_candidates} candidates (from {len(all_applicants)} filtered)")
            all_applicants = all_applicants[:args.max_candidates]

        if len(all_applicants) < original_count:
            print(f"[INFO] Filtered: {original_count} → {len(all_applicants)} candidates")
            if args.min_score > 0:
                print(f"       - Min score >= {args.min_score}%")
            if args.cv_only:
                print(f"       - Has uploaded CV only")
            if args.location:
                print(f"       - Location contains: {args.location}")
            if args.exp_keyword:
                print(f"       - Experience contains: {args.exp_keyword}")
            if args.max_candidates:
                print(f"       - Max limit: {args.max_candidates}")

        if not all_applicants:
            if total_candidates == 0:
                print("[INFO] This job has zero applicants -- nothing to download.")
                print("       (Job posting is live but no one has applied yet.)")
                ctx.close()
                sys.exit(3)  # exit code 3 == empty (treated specially in Streamlit)
            print("[ERROR] API reported applicants but none were fetched.")
            ctx.close()
            sys.exit(1)

        has_cv_count = sum(1 for a in all_applicants if a.get("AttachedCV") == 1)
        print(f"[INFO] Unique candidates : {len(all_applicants)}")
        print(f"[INFO] With uploaded CV  : {has_cv_count}")
        print()

        # Save raw candidate JSON
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(all_applicants, f, ensure_ascii=False, indent=2)
        print(f"[INFO] candidates.json saved → {json_path}")

        # ── Check already-done (resume support) ───────────────────────────
        def txt_already_done(apply_id: str) -> bool:
            for f in Path(txt_dir).iterdir():
                if f.suffix == ".txt" and f.stem.endswith(f"_{apply_id}"):
                    return True
            return False

        def cv_already_done(apply_id: str) -> bool:
            for f in Path(cv_dir).iterdir():
                if f"_{apply_id}_" in f.name or f.stem.endswith(f"_{apply_id}"):
                    return True
            return False

        # ── Init CSV ──────────────────────────────────────────────────────
        csv_file   = open(csv_path, "w", newline="", encoding="utf-8")
        csv_writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
        csv_writer.writeheader()

        # ── Main download loop ─────────────────────────────────────────────
        print("[START] Processing candidates...\n")

        failed_list   = []
        total_txt_ok  = 0
        total_cv_ok   = 0
        total_failed  = 0
        current_ui_pg = 1

        # Suppress tqdm under Streamlit (non-TTY); we emit [PROGRESS] beacons.
        pbar = tqdm(
            total=len(all_applicants),
            desc="Processing",
            unit="candidate",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}] {postfix}",
            disable=_NON_TTY,
        )
        pbar.set_postfix_str("txt:0 cv:0 fail:0")
        _emit_progress(0, len(all_applicants), 0, 0, 0, 1, "")

        for i, applicant in enumerate(all_applicants):
            apply_id       = str(applicant.get("ApplyID", ""))
            name           = applicant.get("Name", f"unknown_{i+1}")
            safe_name      = sanitize_filename(name)
            has_attached   = applicant.get("AttachedCV") == 1
            ts             = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Navigate to correct UI page when needed (50 per page)
            expected_ui_pg = (i // UI_PAGE_SIZE) + 1
            if expected_ui_pg > current_ui_pg:
                advanced = _advance_to_page(page, expected_ui_pg, job_dir)
                if advanced:
                    current_ui_pg = expected_ui_pg
                    # After page advance, ensure cards are actually visible
                    # before trying to find the specific card
                    time.sleep(1.0)
                    cards = page.query_selector_all("app-applicant-card")
                    if len(cards) == 0:
                        # Angular may still be loading; give it more time
                        for settle_attempt in range(3):
                            time.sleep(2.0)
                            cards = page.query_selector_all("app-applicant-card")
                            if len(cards) > 0:
                                break
                else:
                    msg = (f"[FATAL] Could not advance UI from page {current_ui_pg} "
                           f"to {expected_ui_pg}. Pagination DOM was dumped to "
                           f"{job_dir}\\_pagination_dom.html and a screenshot to "
                           f"{job_dir}\\_pagination_failure.png. Stopping at "
                           f"i={i} of {len(all_applicants)} "
                           f"(saved={total_txt_ok} so far). Re-run after fix to "
                           f"resume from already-done items.")
                    if _NON_TTY:
                        print(msg, flush=True)
                    else:
                        tqdm.write(msg)
                    break

            # Find card
            card = page.query_selector(f'app-applicant-card[id="{apply_id}"]') if apply_id else None

            # ── Profile text ──────────────────────────────────────────────
            if txt_already_done(apply_id):
                # Find existing file to get char count for CSV
                existing = next((f for f in Path(txt_dir).iterdir()
                                 if f.stem.endswith(f"_{apply_id}")), None)
                txt_fname  = existing.name if existing else ""
                txt_chars  = existing.stat().st_size if existing else 0
                txt_status = "skipped_already_done"
                total_txt_ok += 1
            elif card:
                # Retry up to 3 times for profile scrape
                for attempt in range(3):
                    txt_fname, txt_chars, txt_status = scrape_profile_text(
                        page, card, applicant, txt_dir
                    )
                    if txt_status == "success":
                        break
                    if attempt < 2:
                        tqdm.write(f"  RETRY {attempt+1} profile: {name[:30]} ({txt_status})")
                        time.sleep(2)
                        card = page.query_selector(f'app-applicant-card[id="{apply_id}"]') if apply_id else None
                        if card:
                            time.sleep(0.5)
                        else:
                            break
                if txt_status == "success":
                    total_txt_ok += 1
                card = page.query_selector(f'app-applicant-card[id="{apply_id}"]') if apply_id else None
                if card:
                    # Ensure card is settled after popup close / profile scrape
                    time.sleep(0.3)
            else:
                txt_fname, txt_chars, txt_status = "", 0, "failed_card_not_found"

            # ── Uploaded CV ───────────────────────────────────────────────
            if not has_attached:
                cv_fname, cv_status = "", "no_cv"
            elif cv_already_done(apply_id):
                existing  = next((f for f in Path(cv_dir).iterdir()
                                  if apply_id in f.name), None)
                cv_fname  = existing.name if existing else ""
                cv_status = "skipped_already_done"
                total_cv_ok += 1
            elif card:
                # Retry up to 3 times for CV download
                for attempt in range(3):
                    cv_fname, cv_status = download_uploaded_cv(
                        page, card, job_id_safe, safe_name, ts, cv_dir
                    )
                    if "success" in cv_status:
                        break
                    if attempt < 2:
                        tqdm.write(f"  RETRY {attempt+1} CV: {name[:30]} ({cv_status})")
                        time.sleep(3)
                        card = page.query_selector(f'app-applicant-card[id="{apply_id}"]') if apply_id else None
                        if card:
                            # Small settle wait so Angular renders the lazy buttons
                            time.sleep(0.8)
                            try:
                                card.evaluate("el => { el.scrollIntoView({block:'center'}); el.dispatchEvent(new MouseEvent('mouseover',{bubbles:true})); }")
                                time.sleep(0.4)
                            except Exception:
                                pass
                        else:
                            break
                if "success" in cv_status:
                    total_cv_ok += 1
            else:
                cv_fname, cv_status = "", "failed_card_not_found"

            # ── Track failures ────────────────────────────────────────────
            txt_ok = txt_status in ("success", "skipped_already_done")
            cv_ok  = cv_status in ("success", "success_unverified",
                                   "skipped_already_done", "no_cv")
            if not txt_ok or not cv_ok:
                total_failed += 1
                failed_list.append({
                    "index":          i + 1,
                    "candidate_name": name,
                    "apply_id":       apply_id,
                    "txt_status":     txt_status,
                    "cv_status":      cv_status,
                    "timestamp":      datetime.now().isoformat(),
                })

            # ── CSV row ───────────────────────────────────────────────────
            csv_writer.writerow({
                "index":             i + 1,
                "candidate_name":    applicant.get("Name", ""),
                "apply_id":          apply_id,
                "application_date":  applicant.get("AppliedDate", ""),
                "age":               applicant.get("Age", ""),
                "expected_salary":   applicant.get("Salary", ""),
                "current_salary":    applicant.get("ApplicantCurrentSalary", ""),
                "bdjobs_match_score":f"{applicant.get('MatchingScore', '')}%",
                "email":             applicant.get("Email", ""),
                "mobile":            applicant.get("Mobile", ""),
                "location":          applicant.get("ApplicantLocation", ""),
                "degree":            applicant.get("Degree", ""),
                "university":        applicant.get("University", ""),
                "experience":        applicant.get("Exps", applicant.get("Exp", "")),
                "profile_txt_file":  txt_fname,
                "profile_txt_chars": txt_chars,
                "profile_txt_status":txt_status,
                "uploaded_cv_file":  cv_fname,
                "uploaded_cv_status":cv_status,
                "has_uploaded_cv":   "Yes" if has_attached else "No",
                "timestamp":         datetime.now().isoformat(),
            })
            csv_file.flush()

            pbar.update(1)
            pbar.set_postfix_str(f"txt:{total_txt_ok} cv:{total_cv_ok} fail:{total_failed}")
            _emit_progress(
                i + 1, len(all_applicants),
                total_txt_ok, total_cv_ok, total_failed,
                current_ui_pg, name,
            )

            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

        pbar.close()
        ctx.close()

    csv_file.close()

    # Save failed list
    if failed_list:
        with open(failed_path, "w", encoding="utf-8") as f:
            json.dump(failed_list, f, indent=2, ensure_ascii=False)

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  Download Complete")
    print("=" * 60)
    print(f"  Profile texts scraped : {total_txt_ok}")
    print(f"  Uploaded CVs saved    : {total_cv_ok}")
    print(f"  Failed / partial      : {total_failed}")
    print(f"  Output folder         : {job_dir}")
    print(f"  Metadata CSV          : {csv_path}")
    print(f"  Candidates JSON       : {json_path}")
    if failed_list:
        print(f"  Failed log            : {failed_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()