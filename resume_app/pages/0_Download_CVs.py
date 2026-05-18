"""
pages/0_Download_CVs.py — In-app BDJobs CV download and manual CV upload.

Replaces the manual `python bdjobs_login.py` + `python bdjobs_downloader.py`
terminal workflow with a one-click HR experience.

Sections:
    A. Session status + Re-login button
    B. Start a new download (URL + label + department + optional auto-rank)
    C. Browse existing download folders
"""

from __future__ import annotations

import io
import os
import re
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd
import streamlit as st

from db import (
    get_css, init_theme, render_sidebar, safe_switch_page,
    DEPARTMENT_LIST, list_download_folders,
    RESUMES_BASE, RANKER_PATH, VENV_PYTHON,
    get_conn, save_bdjobs_credentials, get_bdjobs_credentials,
    has_bdjobs_credentials, _is_streamlit_cloud,
)

# ── Page chrome ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Download/Upload CVs — HR Intelligence",
    page_icon="⬇️⬆️",
    layout="wide",
    initial_sidebar_state="expanded",
)
init_theme()
st.markdown(get_css(), unsafe_allow_html=True)
render_sidebar()

# ── Constants ──────────────────────────────────────────────────────────────────
PROJECT_ROOT    = Path(__file__).resolve().parent.parent.parent
DOWNLOADER_PATH = str(PROJECT_ROOT / "bdjobs_downloader.py")
LOGIN_PATH      = str(PROJECT_ROOT / "bdjobs_login.py")
LOGIN_AUTO_PATH = str(PROJECT_ROOT / "bdjobs_auto_login.py")
SESSION_DIR     = PROJECT_ROOT / "bdjobs_session"
LOG_DIR         = PROJECT_ROOT / "_dl_logs"
LOG_DIR.mkdir(exist_ok=True)
LOGIN_FLAG      = PROJECT_ROOT / "_login_done.flag"

# ── Helpers ────────────────────────────────────────────────────────────────────

def _session_status() -> dict:
    """Heuristic check on the saved Playwright session."""
    if not SESSION_DIR.is_dir():
        return {"state": "missing", "msg": "No session saved yet — click Re-login below."}
    cookies = SESSION_DIR / "Default" / "Network" / "Cookies"
    if not cookies.is_file():
        cookies = SESSION_DIR / "Default" / "Cookies"
    if cookies.is_file():
        age_h = (time.time() - cookies.stat().st_mtime) / 3600
        if age_h < 24:
            return {"state": "fresh", "msg": f"Last activity {age_h:.1f}h ago.", "age_h": age_h}
        return {"state": "stale",
                "msg": f"Last activity {age_h:.1f}h ago — refresh recommended.",
                "age_h": age_h}
    return {"state": "unknown", "msg": "Session folder exists but no cookies file detected."}


def _is_alive(p) -> bool:
    return bool(p and p.poll() is None)


def _read_log(log_path, last_n: int = 300) -> str:
    if not log_path:
        return ""
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return "".join(lines[-last_n:])
    except Exception:
        return ""


def _read_log_split(log_path) -> tuple:
    """Return (last_progress_dict, filtered_log_text).

    Strips noisy [PROGRESS] beacons + tqdm carriage-return updates from the
    visible log; returns the most recent progress dict for the live bar.
    """
    import json as _json
    if not log_path:
        return None, ""
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()
    except Exception:
        return None, ""

    # Split on both \n and \r so tqdm \r-updates become separate lines.
    lines = re.split(r"[\r\n]+", raw)
    last_progress = None
    keep = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith("[PROGRESS]"):
            try:
                last_progress = _json.loads(s[len("[PROGRESS]"):].strip())
            except Exception:
                pass
            continue
        # Drop tqdm progress-bar lines (they look like "Processing:  X%|...").
        if re.match(r"^Processing:\s*\d+%\|", s):
            continue
        keep.append(line)
    # Show only the tail so very long runs don't blow up the page.
    return last_progress, "\n".join(keep[-200:])


def _open_in_explorer(path: str) -> None:
    """Open a folder in the OS file manager. Best-effort, swallow failures."""
    try:
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as e:
        st.warning(f"Could not open `{path}`: {e}")


def _sanitize_label(name: str) -> str:
    name = re.sub(r"[^\w\s-]", "", (name or "").strip())
    name = re.sub(r"[\s]+", "_", name)
    return name[:80]


def _extract_jobno(url: str):
    try:
        return parse_qs(urlparse(url).query).get("jobno", [None])[0]
    except Exception:
        return None


def _spawn(cmd: list, log_name: str, new_console: bool = False):
    """Spawn a subprocess, redirecting stdout+stderr to a logfile in LOG_DIR.
    Optionally open it in a NEW visible console on Windows."""
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"{log_name}_{ts}.log"
    flags    = 0
    if new_console and os.name == "nt":
        flags = subprocess.CREATE_NEW_CONSOLE
    log_fp = open(log_path, "w", encoding="utf-8")
    p = subprocess.Popen(
        cmd, cwd=str(PROJECT_ROOT),
        stdout=log_fp, stderr=subprocess.STDOUT,
        creationflags=flags,
    )
    return p, str(log_path)


def _spawn_login():
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
    )


def _spawn_downloader(
    label: str,
    url: str,
    max_candidates: int = 500,
    min_bdjobs_score: int = 0,
    cv_only: bool = False,
    location_filter: str = "",
    exp_keyword: str = "",
):
    cmd = [
        VENV_PYTHON, DOWNLOADER_PATH,
        "--label", label,
        "--url", url,
        "--max-candidates", str(max_candidates),
        "--min-score", str(min_bdjobs_score),
    ]
    if cv_only:
        cmd.append("--cv-only")
    if location_filter.strip():
        cmd.extend(["--location", location_filter.strip()])
    if exp_keyword.strip():
        cmd.extend(["--exp-keyword", exp_keyword.strip()])
    return _spawn(
        cmd,
        log_name=f"dl_{label}", new_console=False,
    )


def _spawn_ranker(label: str, department: str):
    return _spawn(
        [VENV_PYTHON, RANKER_PATH, "--job", label, "--department", department],
        log_name=f"rank_{label}", new_console=False,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Upload CV Processing Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _ensure_upload_folders(job_label: str) -> dict:
    """Create folder structure for uploaded CVs (mirrors BDJobs downloader layout)."""
    safe_label = _sanitize_label(job_label)
    base_path = Path(RESUMES_BASE) / safe_label
    txt_dir = base_path / "profiles_txt"
    cv_dir = base_path / "uploaded_cvs"

    for d in [base_path, txt_dir, cv_dir]:
        d.mkdir(parents=True, exist_ok=True)

    return {
        "base": str(base_path),
        "txt": str(txt_dir),
        "cv": str(cv_dir),
        "label": safe_label,
    }


def _save_uploaded_cv(uploaded_file, dest_folder: str, prefix: str = "") -> str:
    """Save an uploaded file to the destination folder."""
    from pathlib import Path

    safe_name = _sanitize_label(uploaded_file.name)
    if prefix:
        safe_name = f"{prefix}_{safe_name}"

    dest_path = Path(dest_folder) / safe_name

    # Handle duplicate names
    counter = 1
    original_dest = dest_path
    while dest_path.exists():
        stem = original_dest.stem
        suffix = original_dest.suffix
        dest_path = original_dest.parent / f"{stem}_{counter:02d}{suffix}"
        counter += 1

    with open(dest_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return str(dest_path)


def _extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF using pdfplumber or PyPDF2."""
    try:
        import pdfplumber
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text.strip()
    except ImportError:
        # Fallback to PyPDF2
        try:
            import PyPDF2
            text = ""
            with open(pdf_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text += page.extract_text() + "\n"
            return text.strip()
        except Exception as e:
            return f"[ERROR extracting PDF: {e}]"
    except Exception as e:
        return f"[ERROR extracting PDF: {e}]"


def _save_profile_text(text: str, dest_folder: str, base_name: str, candidate_name: str = "") -> str:
    """Save extracted text as a .txt profile file with Name: header for ranker compatibility."""
    txt_path = Path(dest_folder) / f"{base_name}.txt"
    header = f"Name: {candidate_name}\n\n" if candidate_name else ""
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(header + text)
    return str(txt_path)


def _write_metadata_csv(base_folder: str, job_label: str, entries: list) -> str:
    """Write {job_label}_metadata.csv for ranker compatibility.
    entries: list of dicts with keys apply_id, candidate_name, uploaded_cv_file
    """
    import csv
    csv_path = Path(base_folder) / f"{job_label}_metadata.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["apply_id", "candidate_name", "uploaded_cv_file"])
        writer.writeheader()
        for e in entries:
            writer.writerow(e)
    return str(csv_path)


def _register_job_in_db(job_label: str, department: str):
    """Register the uploaded job in the jobs table so ranker can find it."""
    from db import get_conn
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO jobs (job_label, department)
                VALUES (%s, %s)
                ON CONFLICT (job_label) DO UPDATE SET
                    department = EXCLUDED.department,
                    updated_at = NOW()
            """, (job_label, department))
        conn.commit()
        return True
    except Exception as e:
        return False


def _write_default_jd(base_folder: str, job_label: str, department: str) -> str:
    """Write a default JD file if none exists so ranker has context."""
    jd_path = Path(base_folder) / "jd_default.txt"
    if not jd_path.exists():
        jd_text = f"""Job Title: {job_label.replace('_', ' ')}
Department: {department}
Company: Olympic Industries PLC

Evaluate candidates based on general professional competency and relevance to an FMCG manufacturing company.
Consider skills, experience, education, leadership potential, and cultural fit.
"""
        with open(jd_path, "w", encoding="utf-8") as f:
            f.write(jd_text)
    return str(jd_path)


def _process_single_cv(uploaded_file, job_label: str, department: str, is_bulk: bool = False) -> dict:
    """Process a single uploaded CV: save PDF, extract text, create metadata.
    Compatible with ranker pipeline."""
    import hashlib

    folders = _ensure_upload_folders(job_label)
    _register_job_in_db(job_label, department)

    # Generate apply_id BEFORE saving so we can use it in the filename
    file_hash = hashlib.md5(uploaded_file.name.encode()).hexdigest()[:8].upper()
    apply_id = f"UP_{file_hash}"

    # Save the CV PDF with apply_id in the filename for ranker matching
    safe_name = _sanitize_label(Path(uploaded_file.name).stem)[:40]
    cv_filename = f"{safe_name}_{apply_id}.pdf"
    cv_path = str(Path(folders["cv"]) / cv_filename)
    with open(cv_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # Extract text
    text = _extract_text_from_pdf(cv_path)

    # Candidate name from filename (remove prefix/suffix)
    candidate_name = safe_name.replace("uploaded_", "").replace("_", " ").strip()
    if not candidate_name:
        candidate_name = "Unknown"

    # Save profile text with Name: header for ranker parse_name_from_txt
    txt_filename = f"{safe_name}_{apply_id}.txt"
    txt_path = _save_profile_text(text, folders["txt"], f"{safe_name}_{apply_id}", candidate_name)

    # Write/update metadata CSV
    meta_path = _write_metadata_csv(
        folders["base"], folders["label"],
        [{"apply_id": apply_id, "candidate_name": candidate_name, "uploaded_cv_file": cv_filename}]
    )

    # Write default JD if missing
    jd_path = _write_default_jd(folders["base"], job_label, department)

    return {
        "apply_id": apply_id,
        "candidate_name": candidate_name,
        "cv_path": cv_path,
        "txt_path": txt_path,
        "text_length": len(text),
        "folder": folders["base"],
        "label": folders["label"],
        "department": department,
    }


def _extract_zip_and_process(zip_file, job_label: str, department: str) -> list:
    """Extract ZIP and process all PDFs inside — ranker-compatible."""
    import hashlib, shutil

    folders = _ensure_upload_folders(job_label)
    _register_job_in_db(job_label, department)
    results = []
    meta_entries = []

    # Extract ZIP to temp location
    temp_dir = Path(folders["base"]) / "_temp_zip"
    temp_dir.mkdir(exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(zip_file.getbuffer()), 'r') as zf:
        zf.extractall(temp_dir)

    # Find all PDFs
    pdf_files = list(temp_dir.rglob("*.pdf")) + list(temp_dir.rglob("*.PDF"))

    for pdf_path in pdf_files:
        with open(pdf_path, "rb") as f:
            content = f.read()

        file_hash = hashlib.md5(pdf_path.name.encode()).hexdigest()[:8].upper()
        apply_id = f"UP_{file_hash}"
        safe_name = _sanitize_label(pdf_path.stem)[:40]
        cv_filename = f"{safe_name}_{apply_id}.pdf"
        cv_path = str(Path(folders["cv"]) / cv_filename)
        with open(cv_path, "wb") as f:
            f.write(content)

        text = _extract_text_from_pdf(cv_path)
        candidate_name = safe_name.replace("_", " ").strip() or "Unknown"
        txt_path = _save_profile_text(text, folders["txt"], f"{safe_name}_{apply_id}", candidate_name)

        results.append({
            "apply_id": apply_id,
            "candidate_name": candidate_name,
            "cv_path": cv_path,
            "txt_path": txt_path,
            "text_length": len(text),
            "folder": folders["base"],
            "label": folders["label"],
            "department": department,
        })
        meta_entries.append({
            "apply_id": apply_id,
            "candidate_name": candidate_name,
            "uploaded_cv_file": cv_filename,
        })

    # Cleanup temp
    shutil.rmtree(temp_dir, ignore_errors=True)

    # Write combined metadata CSV
    if meta_entries:
        _write_metadata_csv(folders["base"], folders["label"], meta_entries)
        _write_default_jd(folders["base"], job_label, department)

    return results


def _process_ocr_cv(uploaded_file, job_label: str, department: str, dpi: int = 200) -> dict:
    """Process a scanned CV using OCR — ranker-compatible."""
    import hashlib

    folders = _ensure_upload_folders(job_label)
    _register_job_in_db(job_label, department)

    # Generate apply_id
    file_hash = hashlib.md5(uploaded_file.name.encode()).hexdigest()[:8].upper()
    apply_id = f"OCR_{file_hash}"

    # Save the original file with apply_id in filename
    original_name = uploaded_file.name
    file_ext = Path(original_name).suffix.lower()
    safe_name = _sanitize_label(Path(original_name).stem)[:40]
    cv_filename = f"{safe_name}_{apply_id}{file_ext}"
    cv_path = str(Path(folders["cv"]) / cv_filename)
    with open(cv_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # Try OCR extraction
    text = ""
    try:
        if file_ext in ['.png', '.jpg', '.jpeg']:
            from PIL import Image
            import pytesseract
            image = Image.open(io.BytesIO(uploaded_file.getbuffer()))
            text = pytesseract.image_to_string(image, lang='eng')
        else:
            try:
                from pdf2image import convert_from_path
                import pytesseract
                images = convert_from_path(cv_path, dpi=dpi)
                for img in images:
                    page_text = pytesseract.image_to_string(img, lang='eng')
                    text += page_text + "\n"
            except ImportError:
                text = "[OCR requires pytesseract and pdf2image packages]"
    except Exception as e:
        text = f"[OCR ERROR: {e}]"

    # Candidate name
    candidate_name = safe_name.replace("ocr_uploaded_", "").replace("_", " ").strip() or "Unknown"

    # Save profile text with Name: header
    txt_path = _save_profile_text(text, folders["txt"], f"{safe_name}_{apply_id}", candidate_name)

    # Write metadata CSV
    _write_metadata_csv(
        folders["base"], folders["label"],
        [{"apply_id": apply_id, "candidate_name": candidate_name, "uploaded_cv_file": cv_filename}]
    )
    _write_default_jd(folders["base"], job_label, department)

    return {
        "apply_id": apply_id,
        "candidate_name": candidate_name,
        "cv_path": cv_path,
        "txt_path": txt_path,
        "text_length": len(text),
        "folder": folders["base"],
        "label": folders["label"],
        "department": department,
    }


# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("# ⬇️⬆️ Download/Upload CVs from BDJobs")
st.caption("Pull applicant profiles + uploaded CVs straight from BDJobs Recruiter and feed them into the ranker.")

# ══════════════════════════════════════════════════════════════════════════════
# A. Session status + login
# ══════════════════════════════════════════════════════════════════════════════
try:
    conn = get_conn()
except Exception as e:
    conn = None
    st.error(f"Database connection failed: {e}")
    st.info("Check your PostgreSQL secrets in Streamlit Cloud settings.")

on_cloud = _is_streamlit_cloud()
status = _session_status()  # always define — used in Section B idle phase too

# ══════════════════════════════════════════════════════════════════════════════
# A. BDJobs Session (Login + Credentials) — shown FIRST on both cloud & local
# ══════════════════════════════════════════════════════════════════════════════
state_icon = {"missing": "🔴", "stale": "🟡", "fresh": "🟢", "unknown": "🟡"}.get(status["state"], "⚪")

st.markdown("### 🔐 BDJobs Session")

# Credential storage (collapsible) — shown on both cloud & local
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
sa.markdown(f"**{state_icon} {status['state'].title()}** — {status['msg']}")

login_proc = st.session_state.get("bdjobs_login_proc")
login_log  = st.session_state.get("bdjobs_login_log")

if _is_alive(login_proc):
    sb.warning("⏳ Login in progress")
    st.markdown(
        """
        > **Action needed in the Chromium window that just opened:**
        > 1. Sign in to BDJobs with your Recruiter account.
        > 2. **Important:** click into **Job Dashboard → your job → View Applicants** so the SPA issues all auth tokens.
        >    *(Skipping this step causes the downloader to fail with "Applicant cards did not load".)*
        > 3. Once you can SEE applicant cards, come back here and click the green button below.
        """
    )
    c1, c2 = st.columns([1, 1])
    if c1.button("✅ I've finished logging in (save session)", type="primary", use_container_width=True):
        Path(LOGIN_FLAG).touch()
        st.toast("Saving session… give it a moment.")
        time.sleep(2)
        st.rerun()
    if c2.button("✖ Cancel login", use_container_width=True):
        try: login_proc.terminate()
        except Exception: pass
        for k in ("bdjobs_login_proc", "bdjobs_login_log"):
            st.session_state.pop(k, None)
        st.rerun()
    with st.expander("Login script log", expanded=False):
        st.code(_read_log(login_log) or "(no output yet)", language="text")
    # Auto-poll while alive
    time.sleep(3); st.rerun()
elif login_proc is not None:
    # Just exited
    rc = login_proc.returncode
    if rc == 0:
        sb.success("✅ Saved")
        st.success("Session saved. You can start a download below.")
    else:
        sb.error(f"❌ rc={rc}")
        st.error(f"Login script exited with code {rc}. See log below.")
        with st.expander("Login script log", expanded=True):
            st.code(_read_log(login_log) or "(no output)", language="text")
    for k in ("bdjobs_login_proc", "bdjobs_login_log"):
        st.session_state.pop(k, None)
else:
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button(
            "🔐 Manual Re-login (Browser)",
            type="primary", use_container_width=True, key="btn_manual_login",
        ):
            if on_cloud:
                st.info(
                    "☁️ Local browser login is not available on Streamlit Cloud. "
                    "Use the **BDJobs CV Sync** form below to trigger a remote login + download via GitHub Actions."
                )
            else:
                proc, lp = _spawn_login()
                st.session_state["bdjobs_login_proc"] = proc
                st.session_state["bdjobs_login_log"] = lp
                st.toast("A new console + Chromium will open. Sign in there.")
                time.sleep(1)
                st.rerun()
    with col_btn2:
        has_creds = has_bdjobs_credentials(conn)
        if st.button(
            "🤖 Auto Re-login (Headless)" if has_creds else "🤖 Auto Re-login (Set credentials first)",
            type="secondary", use_container_width=True, key="btn_auto_login",
            disabled=not has_creds,
        ):
            if on_cloud:
                st.info(
                    "☁️ Headless login runs on GitHub Actions. "
                    "Use the **BDJobs CV Sync** form below and check '🔄 Force fresh login' to trigger it."
                )
            else:
                proc, lp = _spawn_auto_login()
                st.session_state["bdjobs_login_proc"] = proc
                st.session_state["bdjobs_login_log"] = lp
                st.rerun()

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# B. BDJobs CV Sync (GitHub Actions) — shown on Cloud, and as remote option on Local
# ══════════════════════════════════════════════════════════════════════════════
if on_cloud:
    st.markdown("### ☁️ BDJobs CV Sync (GitHub Actions)")
    st.info(
        "Playwright browsers cannot run on Streamlit Community Cloud. "
        "CV downloading is handled by a **GitHub Actions** workflow that runs on Ubuntu runners. "
        "Fill in the job details and click **Trigger Sync** below.",
        icon="☁️",
    )
else:
    st.markdown("### ☁️ BDJobs CV Sync (GitHub Actions)")
    st.info(
        "Alternatively, trigger a **GitHub Actions** workflow remotely to download CVs. "
        "This is useful if you don't have a local browser or want to run the scraper on GitHub's servers.",
    )

with st.form("gha_sync_form", clear_on_submit=False):
    gha_label = st.text_input(
        "Job Label",
        placeholder="e.g., CostControl-SrExecutive",
        help="Must match the job label used in the app.",
    )
    gha_url = st.text_input(
        "BDJobs Job URL",
        placeholder="https://employer.bdjobs.com/...",
        help="The full BDJobs employer portal URL for this job posting.",
    )
    gha_max = st.number_input(
        "Max candidates", min_value=0, value=0,
        help="0 = download all applicants. Set a limit for testing.",
    )
    gha_dept = st.selectbox("Department", DEPARTMENT_LIST, index=0)
    gha_force_login = st.checkbox(
        "🔄 Force fresh login (clear old BDJobs session)",
        value=False,
        help="Check this if the scraper fails with 'Session is not authenticated'. "
             "It will clear the saved browser session and do a fresh login.",
    )
    submitted_gha = st.form_submit_button(
        "🚀 Trigger GitHub Actions Sync", type="primary", use_container_width=True,
    )

# ── Test token button for diagnostics ──────────────────────────────────
st.markdown("---")
with st.expander("🔧 Diagnostics: Test GitHub Token", expanded=False):
    if st.button("🧪 Test GitHub Token", key="test_gha_token"):
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        from github_actions import test_github_token
        ok, msg = test_github_token()
        if ok:
            st.success(msg)
        else:
            st.error(msg)

if submitted_gha:
    if not gha_label.strip() or not gha_url.strip():
        st.error("Job label and URL are required.")
    elif "jobno=" not in gha_url:
        st.error("URL must contain a `jobno=` parameter.")
    else:
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        from github_actions import trigger_bdjobs_scrape
        ok, msg = trigger_bdjobs_scrape(
            job_label=gha_label.strip(),
            job_url=gha_url.strip(),
            max_candidates=int(gha_max),
            department=gha_dept,
            force_relogin=gha_force_login,
        )
        if ok:
            st.success(msg)
        else:
            st.error(msg)

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# B. Start a new download (and optional auto-rank)
# ══════════════════════════════════════════════════════════════════════════════
phase     = st.session_state.get("bdjobs_phase", "idle")  # idle|downloading|ranking|done
dl_proc   = st.session_state.get("bdjobs_dl_proc")
dl_log    = st.session_state.get("bdjobs_dl_log")
dl_label  = st.session_state.get("bdjobs_dl_label")
dl_dept   = st.session_state.get("bdjobs_dl_dept")
auto_rank = st.session_state.get("bdjobs_auto_rank", True)
rank_proc = st.session_state.get("bdjobs_rank_proc")
rank_log  = st.session_state.get("bdjobs_rank_log")

st.markdown("### 🚀 Start a new download")

if phase == "downloading":
    # Header row: message left, ETA right
    hdr_l, hdr_r = st.columns([3, 1])
    hdr_l.info(f"⏳ **Downloading CVs for `{dl_label}`** — a Chromium window is doing the work.")

    # Quick ETA for header
    eta_hdr = "—"
    start_iso = st.session_state.get("bdjobs_dl_start")
    progress_hdr, _ = _read_log_split(dl_log)
    if start_iso and progress_hdr and progress_hdr.get("i"):
        try:
            start_dt = datetime.fromisoformat(start_iso)
            elapsed  = (datetime.now() - start_dt).total_seconds()
            rate     = elapsed / max(int(progress_hdr["i"]), 1)
            remain   = rate * (max(int(progress_hdr.get("total", 1)), 1) - int(progress_hdr["i"]))
            if remain < 60:
                eta_hdr = f"{int(remain)}s"
            elif remain < 3600:
                eta_hdr = f"{int(remain // 60)}m {int(remain % 60)}s"
            else:
                eta_hdr = f"{int(remain // 3600)}h {int((remain % 3600) // 60)}m"
        except Exception:
            pass
    hdr_r.metric("⏱️ ETA", eta_hdr, delta=f"{progress_hdr.get('i',0)}/{progress_hdr.get('total','?')}" if progress_hdr else "starting")

    # Live progress bar from [PROGRESS] beacons emitted by bdjobs_downloader.py.
    progress, clean_log = _read_log_split(dl_log)
    if progress and progress.get("total"):
        i_done   = int(progress.get("i", 0))
        total_n  = int(progress.get("total", 1))
        pct      = min(max(i_done / max(total_n, 1), 0.0), 1.0)
        ui_pg    = progress.get("ui_page", 0)
        last_nm  = progress.get("last_name", "")
        st.progress(pct, text=f"Candidate {i_done} / {total_n}"
                              f"{f'  ·  UI page {ui_pg}' if ui_pg else ''}"
                              f"{f'  ·  last: {last_nm}' if last_nm else ''}")

        # ── ETA calculation ────────────────────────────────────────────────
        eta_text = "—"
        start_iso = st.session_state.get("bdjobs_dl_start")
        if start_iso and i_done > 0:
            try:
                start_dt = datetime.fromisoformat(start_iso)
                elapsed  = (datetime.now() - start_dt).total_seconds()
                rate     = elapsed / i_done  # seconds per candidate
                remain   = rate * (total_n - i_done)
                if remain < 60:
                    eta_text = f"{int(remain)}s"
                elif remain < 3600:
                    eta_text = f"{int(remain // 60)}m {int(remain % 60)}s"
                else:
                    eta_text = f"{int(remain // 3600)}h {int((remain % 3600) // 60)}m"
            except Exception:
                pass

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Processed",      f"{i_done} / {total_n}")
        m2.metric("Profile texts",  progress.get("txt", 0))
        m3.metric("Uploaded CVs",   progress.get("cv", 0))
        m4.metric("Failed",         progress.get("fail", 0))
        m5.metric("ETA remaining",  eta_text, delta=f"{int(pct*100)}% done")

    if not _is_alive(dl_proc):
        rc = dl_proc.returncode if dl_proc else None
        st.session_state.pop("bdjobs_dl_start", None)  # clear start timestamp
        if rc == 0:
            st.success(f"✅ Download finished (exit code {rc}).")
            if auto_rank and dl_label and dl_dept:
                st.info(f"⏳ Auto-launching ranker for `{dl_label}` (department: `{dl_dept}`)…")
                p, lp = _spawn_ranker(dl_label, dl_dept)
                st.session_state["bdjobs_rank_proc"] = p
                st.session_state["bdjobs_rank_log"]  = lp
                st.session_state["bdjobs_phase"]     = "ranking"
            else:
                st.session_state["bdjobs_phase"]     = "done"
            time.sleep(1); st.rerun()
        elif rc == 3:
            # Empty job — clean exit, no error.
            st.info(f"ℹ️ **`{dl_label}` has zero applicants on BDJobs** — nothing to download. "
                    "The job posting is live but no one has applied yet. "
                    "Skipping the ranker.")
            st.session_state["bdjobs_phase"] = "done"
        else:
            st.error(f"❌ Downloader exited with code {rc}. Inspect the log below.")
            # Surface the failure screenshot if the downloader saved one.
            shot = Path(RESUMES_BASE) / dl_label / "_failure_screenshot.png"
            if shot.is_file():
                with st.expander("📸 Page state when the wait failed", expanded=True):
                    st.image(str(shot), caption=str(shot), use_container_width=True)
            st.session_state["bdjobs_phase"] = "done"
    # Clean log (no [PROGRESS] beacons, no tqdm \r-spam) inside an expander.
    with st.expander("Downloader log", expanded=False):
        st.code(clean_log or "(no output yet)", language="text")
    if st.button("✖ Stop download", key="stop_dl"):
        try: dl_proc.terminate()
        except Exception: pass
        st.session_state["bdjobs_phase"] = "done"
        st.rerun()
    if _is_alive(dl_proc):
        time.sleep(3); st.rerun()

elif phase == "ranking":
    st.info(f"🤖 **Ranking `{dl_label}`** (department: `{dl_dept}`) — running locally with Ollama.")
    if not _is_alive(rank_proc):
        rc = rank_proc.returncode if rank_proc else None
        if rc == 0:
            st.success("✅ Ranking finished.")
        else:
            st.error(f"❌ Ranker exited with code {rc}.")
        st.session_state["bdjobs_phase"] = "done"
    st.code(_read_log(rank_log) or "(no output yet)", language="text")
    if st.button("✖ Stop ranker", key="stop_rank"):
        try: rank_proc.terminate()
        except Exception: pass
        st.session_state["bdjobs_phase"] = "done"
        st.rerun()
    if _is_alive(rank_proc):
        time.sleep(3); st.rerun()

elif phase == "done":
    st.success(f"🎉 Workflow complete for `{dl_label}`.")
    cA, cB, cC, cD = st.columns(4)
    if cA.button("📊 Open Job Rankings", type="primary", use_container_width=True):
        st.session_state["selected_job"] = dl_label
        safe_switch_page("pages/2_Job_Rankings.py")
    dl_folder = str(Path(RESUMES_BASE) / dl_label) if dl_label else ""
    if cB.button("📂 Open folder", use_container_width=True,
                 disabled=not (dl_folder and os.path.isdir(dl_folder))):
        _open_in_explorer(dl_folder)
        st.toast(f"Opened {dl_folder} in Explorer")
    if cC.button("🏢 Department Rankings", use_container_width=True):
        safe_switch_page("pages/1_Department_Rankings.py")
    if cD.button("⟳ Start another", use_container_width=True):
        for k in ("bdjobs_phase", "bdjobs_dl_proc", "bdjobs_dl_log",
                  "bdjobs_dl_label", "bdjobs_dl_dept", "bdjobs_dl_url",
                  "bdjobs_rank_proc", "bdjobs_rank_log", "bdjobs_auto_rank",
                  "dl_job_label_input"):
            st.session_state.pop(k, None)
        st.rerun()
    _, clean_log_done = _read_log_split(dl_log)
    with st.expander("Last download log", expanded=False):
        st.code(clean_log_done or "(no output)", language="text")
    if rank_log:
        with st.expander("Last ranker log", expanded=False):
            st.code(_read_log(rank_log) or "(no output)", language="text")

else:
    if not on_cloud and status["state"] in ("missing", "stale", "unknown"):
        st.warning("⚠️ Your BDJobs session may not be valid. Refresh the login above before starting.")

    with st.form("bdjobs_dl_form", clear_on_submit=False):
        url = st.text_input(
            "Applicant list URL",
            placeholder="https://recruiter.bdjobs.com/recruitment-center/applicants?jobno=1476429",
            help="Paste the URL of the applicant-list page from BDJobs Recruiter.",
        )
        jobno = _extract_jobno(url) if url else None

        c_l, c_r = st.columns(2)

        # Auto-suggest label only if user hasn't entered one manually
        suggested_label = f"bdjobs_{jobno}" if jobno else ""
        current_label = st.session_state.get("dl_job_label_input", "")
        # If URL changed and no manual entry, use suggested; otherwise keep user's entry
        if suggested_label and not current_label:
            st.session_state["dl_job_label_input"] = suggested_label

        label = c_l.text_input(
            "Job label (folder name)",
            value=st.session_state.get("dl_job_label_input", suggested_label),
            key="dl_job_label_input",
            help="Folder name under downloaded_resumes/ AND --job key for the ranker. You can customize this.",
        )
        dept = c_r.selectbox(
            "Department",
            DEPARTMENT_LIST,
            help="Used by the ranker to file candidates and weight scoring.",
        )

        existing = (Path(RESUMES_BASE) / _sanitize_label(label)).is_dir() if label else False
        if existing:
            st.info(f"📂 Folder `{_sanitize_label(label)}` already exists. New downloads will append; existing files are skipped.")

        # ── Filter Options (for large job postings) ────────────────────────────
        with st.expander("🔍 Filter Options (Optional — useful for 2000+ candidate jobs)", expanded=False):
            f1, f2, f3 = st.columns(3)
            with f1:
                max_candidates = st.number_input(
                    "Max candidates to download",
                    min_value=1, max_value=5000, value=500,
                    help="Limit download to first N candidates. Useful for testing or partial downloads."
                )
            with f2:
                min_bdjobs_score = st.number_input(
                    "Min BDJobs score (%)",
                    min_value=0, max_value=100, value=0,
                    help="Only download candidates with BDJobs match score >= this value."
                )
            with f3:
                cv_only = st.checkbox(
                    "Only candidates with uploaded CV",
                    value=False,
                    help="Skip candidates who haven't uploaded a CV."
                )

            f4, f5 = st.columns(2)
            with f4:
                location_filter = st.text_input(
                    "Location contains (optional)",
                    placeholder="e.g., Dhaka, Narayanganj",
                    help="Only download candidates whose location contains this text (case-insensitive)."
                )
            with f5:
                exp_keyword = st.text_input(
                    "Experience contains (optional)",
                    placeholder="e.g., FMCG, Manager",
                    help="Only download candidates whose experience field contains this text."
                )

            st.caption("💡 Filters are applied after fetching candidate list from BDJobs. The downloader will skip candidates that don't match your criteria.")

        c1, c2, _ = st.columns([1, 1, 2])
        auto_rank_cb = c1.checkbox("Run ranker after download", value=True,
                                    help=f"After download finishes, automatically run "
                                         f"`ranker.py --job {{label}} --department {{dept}}`.")
        submitted = c2.form_submit_button("🚀 Start download", type="primary")

    if submitted:
        if _is_streamlit_cloud():
            st.error(
                "❌ BDJobs download is not available on Streamlit Cloud.\n\n"
                "Please run the downloader on your local Windows workstation, "
                "then upload the downloaded CVs via the Upload tab below."
            )
        elif not url or not jobno:
            st.error("❌ URL is invalid — could not find a `jobno=` parameter.")
        elif not label.strip():
            st.error("❌ Job label is required.")
        elif status["state"] == "missing":
            st.error("❌ No BDJobs session saved. Click 'Re-login to BDJobs' above first.")
        else:
            label_safe = _sanitize_label(label)
            p, lp = _spawn_downloader(
                label_safe, url.strip(),
                max_candidates=max_candidates,
                min_bdjobs_score=min_bdjobs_score,
                cv_only=cv_only,
                location_filter=location_filter,
                exp_keyword=exp_keyword,
            )
            st.session_state["bdjobs_dl_proc"]   = p
            st.session_state["bdjobs_dl_log"]    = lp
            st.session_state["bdjobs_dl_label"]  = label_safe
            st.session_state["bdjobs_dl_dept"]   = dept
            st.session_state["bdjobs_dl_url"]    = url.strip()
            st.session_state["bdjobs_auto_rank"] = auto_rank_cb
            st.session_state["bdjobs_phase"]     = "downloading"
            st.session_state["bdjobs_dl_start"]  = datetime.now().isoformat()
            st.toast("Downloader started. A Chromium window will appear.")
            time.sleep(1); st.rerun()

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# C. Upload CVs (Single, Multiple, Bulk, OCR)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("### ⬆️ Upload CVs")
st.caption("Upload CVs manually — supports single PDF, multiple PDFs, bulk ZIP files, and scanned/OCR documents.")

upload_tab1, upload_tab2 = st.tabs([
    "📄 Single & Multiple CVs + OCR", "🗜️ Bulk ZIP + OCR"
])

with upload_tab1:
    st.markdown("**Upload one or more CV PDFs or scanned images**")
    st.info("📄 Supports single PDF, multiple PDFs, and scanned image files (PNG/JPG). Choose text extraction or OCR below.")
    u1_col1, u1_col2 = st.columns(2)
    with u1_col1:
        cv_job = st.text_input(
            "Job label (folder name)",
            key="upload_cv_job",
            placeholder="e.g., Manager_Delivery_Jan2026",
            help="Creates folder under downloaded_resumes/ for this upload batch."
        )
    with u1_col2:
        cv_dept = st.selectbox(
            "Department",
            DEPARTMENT_LIST,
            key="upload_cv_dept",
            help="Used for scoring and organizing candidates."
        )
    cv_files = st.file_uploader(
        "Upload CV PDFs or scanned images",
        type=["pdf", "png", "jpg", "jpeg"],
        key="cv_uploader",
        accept_multiple_files=True,
    )
    ocr_quality = st.radio(
        "OCR Quality/Speed tradeoff",
        ["Fast", "Balanced", "High Quality (slower)"],
        horizontal=True,
        key="ocr_quality_tab1",
        help="Used only when OCR mode is selected. Fast = lower accuracy but quick. High Quality = best text extraction but slower."
    )
    if cv_files and cv_job:
        st.caption(f"Selected {len(cv_files)} file(s)")
        btn_col1, btn_col2, btn_col3 = st.columns(3)
        with btn_col1:
            if st.button("🚀 Extract Text", type="primary", key="btn_cv_extract", use_container_width=True):
                progress_bar = st.progress(0)
                results = []
                errors = []
                for i, cv in enumerate(cv_files):
                    progress_bar.progress((i) / len(cv_files), text=f"Processing {cv.name}...")
                    result = _process_single_cv(cv, cv_job, cv_dept)
                    if result["text_length"] > 0:
                        results.append(result)
                    else:
                        errors.append(cv.name)
                progress_bar.progress(1.0, text="Complete!")
                if results:
                    st.success(f"✅ **{len(results)}** CVs processed successfully")
                    st.caption(f"📁 Saved to: `{results[0]['folder']}`")
                    # Store for ranking
                    st.session_state["last_upload_job"] = cv_job
                    st.session_state["last_upload_dept"] = cv_dept
                    st.session_state["last_upload_count"] = len(results)
                if errors:
                    st.warning(f"⚠️ {len(errors)} file(s) may need OCR: {', '.join(errors[:3])}{'...' if len(errors) > 3 else ''}")
                    st.info("💡 Use the 'OCR Process' button for scanned documents.")
        with btn_col2:
            if st.button("🔍 OCR Process", type="secondary", key="btn_cv_ocr", use_container_width=True):
                progress_bar = st.progress(0)
                ocr_results = []
                ocr_errors = []
                dpi_map = {"Fast": 150, "Balanced": 200, "High Quality (slower)": 300}
                ocr_dpi = dpi_map.get(ocr_quality, 200)
                for i, cv in enumerate(cv_files):
                    progress_bar.progress((i) / len(cv_files), text=f"OCR processing {cv.name}...")
                    try:
                        result = _process_ocr_cv(cv, cv_job, cv_dept, ocr_dpi)
                        if result["text_length"] > 0:
                            ocr_results.append(result)
                        else:
                            ocr_errors.append(cv.name)
                    except Exception as e:
                        ocr_errors.append(f"{cv.name}: {str(e)[:50]}")
                progress_bar.progress(1.0, text="OCR Complete!")
                if ocr_results:
                    st.success(f"✅ **{len(ocr_results)}** CVs OCR-processed successfully")
                    st.caption(f"📁 Saved to: `{ocr_results[0]['folder']}`")
                    st.caption(f"🔍 OCR Quality: {ocr_quality} ({ocr_dpi} DPI)")
                    # Store for ranking
                    st.session_state["last_upload_job"] = cv_job
                    st.session_state["last_upload_dept"] = cv_dept
                    st.session_state["last_upload_count"] = len(ocr_results)
                if ocr_errors:
                    st.warning(f"⚠️ {len(ocr_errors)} file(s) failed OCR: {', '.join(ocr_errors[:3])}{'...' if len(ocr_errors) > 3 else ''}")
        with btn_col3:
            if st.button("⚡ Start Ranking Job", type="primary", key="btn_cv_rank", use_container_width=True):
                if _is_streamlit_cloud():
                    st.error(
                        "❌ AI ranking is not available on Streamlit Cloud.\n\n"
                        "The ranker requires a local Ollama LLM server. "
                        "Please run ranking on your local Windows workstation."
                    )
                    st.stop()
                # First ensure files are processed
                if "last_upload_job" not in st.session_state or st.session_state["last_upload_job"] != cv_job:
                    # Auto-process files first
                    progress_bar = st.progress(0)
                    results = []
                    for i, cv in enumerate(cv_files):
                        progress_bar.progress((i) / len(cv_files), text=f"Processing {cv.name}...")
                        result = _process_single_cv(cv, cv_job, cv_dept)
                        if result["text_length"] > 0:
                            results.append(result)
                    progress_bar.progress(1.0, text="Complete!")
                    if results:
                        st.success(f"✅ **{len(results)}** CVs processed successfully")
                
                # Now start the ranker
                try:
                    from datetime import datetime
                    from pathlib import Path
                    
                    # Ensure JD exists
                    folders = _ensure_upload_folders(cv_job)
                    jd_path = Path(folders["base"]) / "jd_default.txt"
                    if not jd_path.exists():
                        _write_default_jd(folders["base"], cv_job, cv_dept)
                    
                    # Spawn ranker
                    safe_label = _sanitize_label(cv_job)
                    log_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    log_path = Path(RESUMES_BASE) / "_dl_logs" / f"rank_{safe_label}_{log_ts}.log"
                    log_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    cmd = [
                        sys.executable,
                        str(Path(RANKER_PATH)),
                        "--job", safe_label,
                        "--department", cv_dept
                    ]
                    if jd_path.exists():
                        cmd.extend(["--jd", str(jd_path)])
                    
                    flags = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
                    log_fp = open(log_path, "w", encoding="utf-8")
                    proc = subprocess.Popen(
                        cmd, cwd=str(Path(RESUMES_BASE).parent),
                        stdout=log_fp, stderr=subprocess.STDOUT,
                        creationflags=flags,
                    )
                    
                    st.success(f"🚀 **Ranker started** for `{cv_job}` (PID {proc.pid})")
                    st.caption(f"📄 Log: `{log_path}`")
                    st.session_state[f"ranker_{safe_label}_pid"] = proc.pid
                    st.session_state[f"ranker_{safe_label}_log"] = str(log_path)
                    st.session_state[f"ranker_{safe_label}_start"] = datetime.now().isoformat()
                    st.session_state[f"ranker_{safe_label}_status"] = "running"
                    
                    # Navigate to job rankings
                    st.session_state["selected_job"] = safe_label
                    safe_switch_page("pages/2_Job_Rankings.py")
                    
                except Exception as e:
                    st.error(f"❌ Failed to start ranker: {e}")
                    st.info("💡 Try processing files first with 'Extract Text' button")

with upload_tab2:
    st.markdown("**Bulk upload via ZIP archive + OCR**")
    st.info("📦 ZIP should contain PDF CVs or scanned images. Each file will be treated as a separate candidate. Choose text extraction or OCR below.")
    u2_col1, u2_col2 = st.columns(2)
    with u2_col1:
        zip_job = st.text_input(
            "Job label (folder name)",
            key="upload_zip_job",
            placeholder="e.g., Campus_Recruitment_2026",
            help="All CVs from the ZIP will be grouped under this job label."
        )
    with u2_col2:
        zip_dept = st.selectbox(
            "Department",
            DEPARTMENT_LIST,
            key="upload_zip_dept",
            help="Used for scoring all uploaded candidates."
        )
    zip_file = st.file_uploader(
        "Upload ZIP file",
        type=["zip"],
        key="zip_uploader",
        accept_multiple_files=False,
    )
    zip_ocr_quality = st.radio(
        "OCR Quality/Speed tradeoff",
        ["Fast", "Balanced", "High Quality (slower)"],
        horizontal=True,
        key="ocr_quality_tab2",
        help="Used only when OCR mode is selected for ZIP contents."
    )
    if zip_file and zip_job:
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button("🚀 Extract Text", type="primary", key="btn_zip_extract", use_container_width=True):
                with st.spinner(f"Extracting and processing {zip_file.name}..."):
                    results = _extract_zip_and_process(zip_file, zip_job, zip_dept)
                if results:
                    success_count = sum(1 for r in results if r["text_length"] > 0)
                    st.success(f"✅ **{success_count}/{len(results)}** CVs extracted and processed")
                    st.caption(f"📁 Saved to: `{results[0]['folder']}`")
                    if success_count < len(results):
                        st.warning(f"⚠️ {len(results) - success_count} file(s) may need OCR processing")
                        st.info("💡 Use the '🔍 OCR Process' button for scanned documents in the ZIP.")
        with btn_col2:
            if st.button("🔍 OCR Process", type="secondary", key="btn_zip_ocr", use_container_width=True):
                with st.spinner(f"Extracting {zip_file.name} and running OCR..."):
                    folders = _ensure_upload_folders(zip_job)
                    _register_job_in_db(zip_job, zip_dept)
                    temp_dir = Path(folders["base"]) / "_temp_zip"
                    temp_dir.mkdir(exist_ok=True)
                    import shutil
                    with zipfile.ZipFile(io.BytesIO(zip_file.getbuffer()), 'r') as zf:
                        zf.extractall(temp_dir)
                    pdf_files = list(temp_dir.rglob("*.pdf")) + list(temp_dir.rglob("*.PDF")) + list(temp_dir.rglob("*.png")) + list(temp_dir.rglob("*.jpg")) + list(temp_dir.rglob("*.jpeg"))

                    progress_bar = st.progress(0)
                    ocr_results = []
                    ocr_errors = []
                    ocr_meta_entries = []
                    dpi_map = {"Fast": 150, "Balanced": 200, "High Quality (slower)": 300}
                    ocr_dpi = dpi_map.get(zip_ocr_quality, 200)

                    for i, pdf_path in enumerate(pdf_files):
                        progress_bar.progress((i) / len(pdf_files), text=f"OCR processing {pdf_path.name}...")
                        with open(pdf_path, "rb") as f:
                            content = f.read()

                        file_hash = hashlib.md5(pdf_path.name.encode()).hexdigest()[:8].upper()
                        apply_id = f"OCR_{file_hash}"
                        safe_name = _sanitize_label(pdf_path.stem)[:40]
                        file_ext = pdf_path.suffix.lower()
                        cv_filename = f"{safe_name}_{apply_id}{file_ext}"
                        cv_path = str(Path(folders["cv"]) / cv_filename)
                        with open(cv_path, "wb") as f:
                            f.write(content)

                        # OCR extract text
                        text = ""
                        try:
                            if file_ext in ['.png', '.jpg', '.jpeg']:
                                from PIL import Image
                                import pytesseract
                                image = Image.open(io.BytesIO(content))
                                text = pytesseract.image_to_string(image, lang='eng')
                            else:
                                from pdf2image import convert_from_path
                                import pytesseract
                                images = convert_from_path(cv_path, dpi=ocr_dpi)
                                for img in images:
                                    page_text = pytesseract.image_to_string(img, lang='eng')
                                    text += page_text + "\n"
                        except Exception as e:
                            text = f"[OCR ERROR: {e}]"

                        candidate_name = safe_name.replace("_", " ").strip() or "Unknown"
                        txt_path = _save_profile_text(text, folders["txt"], f"{safe_name}_{apply_id}", candidate_name)

                        if len(text) > 0 and not text.startswith("[OCR ERROR"):
                            ocr_results.append({
                                "apply_id": apply_id,
                                "candidate_name": candidate_name,
                                "text_length": len(text),
                            })
                            ocr_meta_entries.append({
                                "apply_id": apply_id,
                                "candidate_name": candidate_name,
                                "uploaded_cv_file": cv_filename,
                            })
                        else:
                            ocr_errors.append(pdf_path.name)

                    shutil.rmtree(temp_dir, ignore_errors=True)
                    if ocr_meta_entries:
                        _write_metadata_csv(folders["base"], folders["label"], ocr_meta_entries)
                        _write_default_jd(folders["base"], zip_job, zip_dept)
                    progress_bar.progress(1.0, text="OCR Complete!")

                    if ocr_results:
                        st.success(f"✅ **{len(ocr_results)}** CVs OCR-processed from ZIP")
                        st.caption(f"📁 Saved to: `{folders['base']}`")
                        st.caption(f"🔍 OCR Quality: {zip_ocr_quality} ({ocr_dpi} DPI)")
                    if ocr_errors:
                        st.warning(f"⚠️ {len(ocr_errors)} file(s) failed OCR: {', '.join(ocr_errors[:3])}{'...' if len(ocr_errors) > 3 else ''}")

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# D. Browse existing downloads
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("### 📂 Existing downloads")

folders = list_download_folders()
if not folders:
    st.info(f"No download folders yet under `{RESUMES_BASE}`.")
else:
    rows = [{
        "Folder":        f["name"],
        "Profiles":      f["n_profiles"],
        "Uploaded CVs":  f["n_cvs"],
        "Size (MB)":     f["size_mb"],
        "Last modified": f["modified"].strftime("%d %b %Y %H:%M") if f["modified"] else "—",
        "Metadata CSV":  "✅" if f["has_metadata_csv"] else "—",
    } for f in folders]
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    sel = st.selectbox("Inspect a folder", [""] + [f["name"] for f in folders])
    if sel:
        chosen = next(f for f in folders if f["name"] == sel)
        st.code(chosen["path"])
        c1, c2, c3 = st.columns(3)
        c1.metric("Profiles (.txt)",      chosen["n_profiles"])
        c2.metric("Uploaded CVs (.pdf)",  chosen["n_cvs"])
        c3.metric("Size (MB)",            chosen["size_mb"])
        bA, bB, bC, bD = st.columns(4)
        if bA.button("📂 Open folder", key=f"explore_{sel}", use_container_width=True,
                     help="Open the download folder in Windows Explorer."):
            _open_in_explorer(chosen["path"])
            st.toast(f"Opened {chosen['path']} in Explorer")
        cv_dir = os.path.join(chosen["path"], "uploaded_cvs")
        if bB.button("📂 Open CVs subfolder", key=f"cvs_{sel}", use_container_width=True,
                     disabled=not os.path.isdir(cv_dir),
                     help="Jump straight to the uploaded_cvs/ subfolder of PDFs."):
            _open_in_explorer(cv_dir)
            st.toast(f"Opened {cv_dir} in Explorer")
        if bC.button("📊 Job Rankings", key=f"open_{sel}", use_container_width=True):
            st.session_state["selected_job"] = sel
            safe_switch_page("pages/2_Job_Rankings.py")
        if bD.button("📝 Job Posting", key=f"new_{sel}", use_container_width=True):
            st.session_state["preset_job_label"] = sel
            safe_switch_page("pages/3_New_Job.py")
