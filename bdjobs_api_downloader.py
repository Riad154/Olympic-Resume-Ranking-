"""
bdjobs_api_downloader.py — BDJobs API-based Resume Downloader

Replaces Playwright-based login with direct HTTP API calls to avoid
browser-automation detection.  Keeps optional Playwright only for CV
downloads (the one remaining click-based action).

Usage (CI):
    python bdjobs_api_downloader.py \
        --username  "$BDJOBS_USER" \
        --password  "$BDJOBS_PASS" \
        --jobno     1344660 \
        --label     "Data Analyst" \
        --max-candidates 0

Environment:
    BDJOBS_USER / BDJOBS_PASS   – credentials (or --username/--password)
    PYTHONUNBUFFERED=1          – recommended in CI
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse, quote

import requests

# ── Constants ──────────────────────────────────────────────────────────────
LOGIN_URL       = "https://api.bdjobs.com/auth/api/Login/Login"
SUPPORT_URL     = "https://corporate3.bdjobs.com/SupportingData-test.asp"
API_BASE        = "https://testmongo.bdjobs.com/api/api"
V1_API_BASE     = "https://testmongo.bdjobs.com/v1/api"
REC_BASE        = "https://recruiter.bdjobs.com"
CORP_BASE       = "https://corporate3.bdjobs.com"
PDF_GENERATOR   = "https://recruiter.bdjobs.com/profilepdfgenerator/api/PdfGenerator/generate-pdf-zip"

SESSION_FILE = "bdjobs_api_session.json"
UI_PAGE_SIZE = 50


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _now() -> str:
    return datetime.now().isoformat()


def _load_session(path: str = SESSION_FILE) -> dict | None:
    """Load cached JWT + company info."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # simple validity: token exists
        if data.get("token"):
            return data
    except Exception:
        pass
    return None


def _save_session(data: dict, path: str = SESSION_FILE) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def sanitize_filename(name: str) -> str:
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s]+", "_", name.strip())
    return name[:80]


# ══════════════════════════════════════════════════════════════════════════════
# BDJobs API Client
# ══════════════════════════════════════════════════════════════════════════════

class BDJobsAPIClient:
    def __init__(self, token: str, company_id: str | None = None, encrypt_id: str | None = None):
        self.token = token
        self.company_id = company_id
        self.encrypt_id = encrypt_id
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.9,bn;q=0.8",
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Origin": REC_BASE,
            "Referer": f"{REC_BASE}/",
        })

    @classmethod
    def login(cls, username: str, password: str) -> "BDJobsAPIClient":
        print(f"[INFO] Logging in as {username} …", flush=True)
        resp = requests.post(
            LOGIN_URL,
            json={"userName": username, "password": password, "systemId": 2},
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "en-US,en;q=0.9,bn;q=0.8",
                "Cache-Control": "no-cache",
                "Origin": REC_BASE,
                "Pragma": "no-cache",
                "Referer": f"{REC_BASE}/",
                "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
            },
            timeout=30,
        )
        print(f"[DEBUG] Login HTTP {resp.status_code}", flush=True)
        resp.raise_for_status()
        data = resp.json()

        # Debug: dump first 2000 chars of response
        raw_preview = json.dumps(data)[:2000]
        print(f"[DEBUG] Login response preview: {raw_preview}", flush=True)

        # Robust token extraction — try multiple known response shapes
        token = refresh = encrypt_id = msg = None

        # Shape A: data.event.eventData[0].value = {token, refreshToken, encryptId, message}
        event = data.get("event", {})
        event_data = event.get("eventData", [])
        if event_data and isinstance(event_data, list):
            for item in event_data:
                if isinstance(item, dict):
                    val = item.get("value", {})
                    if isinstance(val, dict):
                        if val.get("token"):
                            token = val.get("token")
                            refresh = val.get("refreshToken")
                            encrypt_id = val.get("encryptId")
                            msg = val.get("message", "")
                            break

        # Shape B: data.token directly (some APIs return flat structure)
        if not token:
            token = data.get("token")
            refresh = data.get("refreshToken")
            encrypt_id = data.get("encryptId")
            msg = data.get("message", "")

        # Shape C: nested in data.result or data.data
        for key in ("result", "data", "response", "body"):
            if not token and key in data:
                nested = data[key]
                if isinstance(nested, dict):
                    token = nested.get("token") or nested.get("accessToken")
                    refresh = nested.get("refreshToken")
                    encrypt_id = nested.get("encryptId")
                    msg = nested.get("message", "")
                elif isinstance(nested, list) and nested:
                    first = nested[0]
                    if isinstance(first, dict):
                        token = first.get("token") or first.get("accessToken")
                        refresh = first.get("refreshToken")
                        encrypt_id = first.get("encryptId")
                        msg = first.get("message", "")

        # Shape D: search recursively for token key anywhere in JSON
        def _find_key(obj, key_name):
            if isinstance(obj, dict):
                if key_name in obj:
                    return obj[key_name]
                for v in obj.values():
                    result = _find_key(v, key_name)
                    if result is not None:
                        return result
            elif isinstance(obj, list):
                for item in obj:
                    result = _find_key(item, key_name)
                    if result is not None:
                        return result
            return None

        if not token:
            token = _find_key(data, "token")
            if not token:
                token = _find_key(data, "accessToken")
        if not refresh:
            refresh = _find_key(data, "refreshToken")
        if not encrypt_id:
            encrypt_id = _find_key(data, "encryptId")
        if not msg:
            msg = _find_key(data, "message") or ""
            if not msg:
                msg = _find_key(data, "Message") or ""

        print(f"[INFO] Login message: {msg}", flush=True)
        if not token:
            raise RuntimeError(f"Login failed: no token found. Response preview: {raw_preview[:500]}")
        print(f"[OK] JWT obtained (len={len(token)})", flush=True)
        # fetch company info
        client = cls(token=token, encrypt_id=encrypt_id)
        client._fetch_company_info()
        return client

    def _fetch_company_info(self) -> None:
        """Call SupportingData to get ComID (company cookie value)."""
        if not self.encrypt_id:
            print("[WARN] No encryptId, cannot fetch company info", flush=True)
            return
        url = f"{SUPPORT_URL}?ComUsrAcc={quote(self.encrypt_id)}"
        print(f"[INFO] Fetching company info …", flush=True)
        try:
            r = self.session.get(url, timeout=30)
            print(f"[DEBUG] SupportingData HTTP {r.status_code}", flush=True)
            # Response is HTML with inline script setting cookies
            html = r.text
            # Extract ComNo from the HTML
            m = re.search(r"ComNo=([^&;'\"\s]+)", html)
            if m:
                self.company_id = m.group(1)
                print(f"[OK] CompanyId = {self.company_id}", flush=True)
            else:
                print("[WARN] Could not extract ComNo from SupportingData", flush=True)
        except Exception as e:
            print(f"[WARN] Failed to fetch company info: {e}", flush=True)

    def fetch_applicants(self, jobno: str, page_size: int = UI_PAGE_SIZE, max_pages: int = 200) -> list[dict]:
        """Paginate through AllApplicantSearchResult and return flat list."""
        if not self.company_id:
            raise RuntimeError("CompanyId not available. Cannot fetch applicants.")
        all_applicants = []
        total_reported = None
        for pg in range(1, max_pages + 1):
            url = (
                f"{API_BASE}/AllApplicantSearchResult"
                f"?CompanyId={self.company_id}"
                f"&jobno={jobno}"
                f"&ordTyp=OMP&pgtype=al&sIdentity=0&stype=al"
                f"&age=/&exp=/&qOrg=&qInst=&qJobLevel=&qs=&qloc=0&valLocType=0&sal=/&qWork="
                f"&pg_size={page_size}&pg_no={pg}"
                f"&AppliedFromLinkedIn=1&JobPaid=0&qInvited=0&qLocName="
                f"&sortby=&sorttype=&NT=&qarmy=0&module="
                f"&assmntResult=&assmntOperator=&qmlloc=&qmlskill="
                f"&newCount=0&pwd=0&FairID=0&FromLeftFilterSearch=0"
            )
            print(f"[INFO] Fetching page {pg} …", flush=True)
            r = self.session.get(url, timeout=30)
            print(f"[DEBUG] Page {pg} HTTP {r.status_code}", flush=True)
            r.raise_for_status()
            data = r.json()
            error = data.get("Error")
            if error not in (0, "0", None, ""):
                print(f"[ERROR] API error on page {pg}: {error}", flush=True)
                break
            if pg == 1:
                total_reported = data.get("TotalCVFound", 0)
                print(f"[INFO] Total candidates reported: {total_reported}", flush=True)
            batch = data.get("Applicants", [])
            if not batch:
                print(f"[INFO] Empty page {pg}, stopping.", flush=True)
                break
            all_applicants.extend(batch)
            print(f"  Page {pg}: +{len(batch)} | running total: {len(all_applicants)}", flush=True)
            if len(all_applicants) >= total_reported:
                break
            time.sleep(0.3)
        # deduplicate
        seen, uniq = set(), []
        for a in all_applicants:
            aid = str(a.get("ApplyID", ""))
            if aid and aid not in seen:
                seen.add(aid)
                uniq.append(a)
            elif not aid:
                uniq.append(a)
        if len(uniq) < len(all_applicants):
            print(f"[INFO] Deduplicated: {len(all_applicants)} → {len(uniq)}", flush=True)
        return uniq

    def _get_applicant_id(self, job_no: str, apply_id: str) -> int | None:
        """Call CheckValidity to get the numeric ApplicantId from ApplyID."""
        url = f"{V1_API_BASE}/JobInformation/CheckValidity"
        payload = {
            "Data": {
                "JobId": job_no,
                "ApplyId": apply_id,
                "JobType": ""
            }
        }
        try:
            r = self.session.post(url, json=payload, timeout=30)
            if r.status_code == 200:
                data = r.json()
                if data.get("statusCode") == 0:
                    applicant_id = data.get("data", {}).get("ApplicantId")
                    if applicant_id:
                        return int(applicant_id)
            print(f"[DEBUG] CheckValidity HTTP {r.status_code} resp={r.text[:200]}", flush=True)
        except Exception as e:
            print(f"[DEBUG] CheckValidity failed: {e}", flush=True)
        return None

    def download_cv(self, applicant: dict, out_path: str, jobno: str, job_title: str = "") -> str:
        """
        Download candidate CV via BDJobs PDF generator.
        Flow: CheckValidity -> get ApplicantId -> POST generate-pdf-zip.
        Returns status string.
        """
        apply_id = str(applicant.get("ApplyID", ""))
        job_no = str(jobno)
        name = str(applicant.get("Name", "unnamed"))
        if not apply_id or not job_no:
            return "failed_no_applyid"

        # Step 1: Get numeric ApplicantId via CheckValidity
        applicant_id = self._get_applicant_id(job_no, apply_id)
        if not applicant_id:
            print(f"[WARN] Could not resolve ApplicantId for {name} (ApplyID={apply_id})", flush=True)
            return "failed_no_applicant_id"

        # Step 2: Call PDF generator
        salary_raw = str(applicant.get("Salary", "0")).replace(",", "").replace("/", "")
        try:
            expected_salary = int(float(salary_raw)) if salary_raw else 0
        except ValueError:
            expected_salary = 0

        payload = {
            "jobTitle": job_title or applicant.get("JobTitle", ""),
            "applicantIds": [applicant_id],
            "jobId": int(job_no) if job_no.isdigit() else 0,
            "expectedSalary": expected_salary,
        }

        try:
            print(f"[DEBUG] PDF gen for {name}: applicantId={applicant_id}, jobId={job_no}", flush=True)
            r = self.session.post(PDF_GENERATOR, json=payload, timeout=60)
            print(f"[DEBUG] PDF gen HTTP {r.status_code} len={len(r.content)}", flush=True)
            if r.status_code == 200 and r.content[:4] == b"%PDF":
                with open(out_path, "wb") as f:
                    f.write(r.content)
                return "success"
            elif r.status_code == 200:
                # Might be JSON error or redirect
                print(f"[DEBUG] PDF gen response: {r.text[:300]}", flush=True)
            else:
                print(f"[DEBUG] PDF gen failed: HTTP {r.status_code}", flush=True)
        except Exception as e:
            print(f"[DEBUG] PDF gen exception: {e}", flush=True)

        return "failed_pdf_generation"


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", default=os.environ.get("BDJOBS_USER", "").strip())
    parser.add_argument("--password", default=os.environ.get("BDJOBS_PASS", "").strip())
    parser.add_argument("--jwt", default=os.environ.get("BDJOBS_JWT", "").strip(),
                        help="Pre-authenticated JWT token (skips login, avoids IP blocking)")
    parser.add_argument("--company-id", default=os.environ.get("BDJOBS_COMPANY_ID", "").strip(),
                        help="Company ID (required when using --jwt)")
    parser.add_argument("--encrypt-id", default=os.environ.get("BDJOBS_ENCRYPT_ID", "").strip(),
                        help="EncryptId (optional, used for some endpoints)")
    parser.add_argument("--jobno", required=True)
    parser.add_argument("--label", default="")
    parser.add_argument("--job-title", default="",
                        help="Job posting title (used for PDF generation)")
    parser.add_argument("--max-candidates", type=int, default=0)
    parser.add_argument("--min-score", type=float, default=0)
    parser.add_argument("--cv-only", action="store_true")
    parser.add_argument("--location", default="")
    parser.add_argument("--exp-keyword", default="")
    parser.add_argument("--output-dir", default="downloaded_resumes")
    parser.add_argument("--force-login", action="store_true", help="Ignore cached session and re-login")
    args = parser.parse_args()

    # ── Auth: prefer JWT token (skip login), else fall back to username/password ──
    session = None
    client = None

    if args.jwt and args.company_id:
        print("[INFO] Using pre-authenticated JWT token (skipping login)", flush=True)
        client = BDJobsAPIClient(
            token=args.jwt,
            company_id=args.company_id,
            encrypt_id=args.encrypt_id or None,
        )
    else:
        # Try cached session first
        if not args.force_login:
            session = _load_session()
            if session:
                print(f"[INFO] Reusing cached session", flush=True)

        if session is None:
            if not args.username or not args.password:
                print("[ERROR] Either --jwt + --company-id OR --username + --password required", flush=True)
                sys.exit(1)
            client = BDJobsAPIClient.login(args.username, args.password)
            session = {
                "token": client.token,
                "company_id": client.company_id,
                "encrypt_id": client.encrypt_id,
                "saved_at": _now(),
            }
            _save_session(session)
        else:
            client = BDJobsAPIClient(
                token=session["token"],
                company_id=session.get("company_id"),
                encrypt_id=session.get("encrypt_id"),
            )

    if not client.company_id:
        print("[ERROR] Could not determine CompanyId. Aborting.", flush=True)
        sys.exit(1)

    # ── Prepare output dirs ───────────────────────────────────────────
    # Folder name: "JobLabel_123456" or just "123456" if no label provided
    safe_label = sanitize_filename(args.label).strip("_") if args.label else ""
    folder_name = f"{safe_label}_{args.jobno}" if safe_label else args.jobno
    job_dir = os.path.join(args.output_dir, folder_name)
    txt_dir = os.path.join(job_dir, "profiles_txt")
    cv_dir  = os.path.join(job_dir, "uploaded_cvs")
    os.makedirs(txt_dir, exist_ok=True)
    os.makedirs(cv_dir, exist_ok=True)
    print(f"[INFO] Output folder: {job_dir}", flush=True)

    # ── Fetch applicants ──────────────────────────────────────────────
    print(f"[INFO] Fetching applicants for job {args.jobno} …", flush=True)
    applicants = client.fetch_applicants(args.jobno)
    print(f"[OK] Fetched {len(applicants)} unique applicants", flush=True)

    if not applicants:
        print("[WARN] No applicants found.", flush=True)
        sys.exit(0)

    # ── Apply filters ─────────────────────────────────────────────────
    original_count = len(applicants)
    filtered = []
    for a in applicants:
        score_str = str(a.get("MatchingScore", "0")).replace("%", "")
        try:
            score = float(score_str) if score_str else 0
        except ValueError:
            score = 0
        if score < args.min_score:
            continue
        if args.cv_only and a.get("AttachedCV") != 1:
            continue
        if args.location:
            loc = str(a.get("ApplicantLocation", "")).lower()
            if args.location.lower() not in loc:
                continue
        if args.exp_keyword:
            exp = str(a.get("Exps", a.get("Exp", ""))).lower()
            if args.exp_keyword.lower() not in exp:
                continue
        filtered.append(a)
    applicants = filtered

    if args.max_candidates and len(applicants) > args.max_candidates:
        applicants = applicants[:args.max_candidates]

    if len(applicants) < original_count:
        print(f"[INFO] Filtered: {original_count} → {len(applicants)}", flush=True)

    # ── Save raw metadata ─────────────────────────────────────────────
    meta_path = os.path.join(job_dir, f"{folder_name}_metadata.csv")
    json_path = os.path.join(job_dir, "candidates.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(applicants, f, indent=2)

    # ── Write metadata CSV ────────────────────────────────────────────
    fieldnames = [
        "ApplyID", "Name", "Email", "Mobile", "Degree", "University",
        "Exps", "ApplicantLocation", "ApplicantCurrentSalary", "Salary",
        "MatchingScore", "AppliedDate", "AttachedCV",
    ]
    with open(meta_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for a in applicants:
            row = {k: a.get(k, "") for k in fieldnames}
            writer.writerow(row)

    # ── Download / extract ────────────────────────────────────────────
    print(f"[INFO] Processing {len(applicants)} candidates …", flush=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    cv_ok = txt_ok = fail = 0
    failed_downloads = []

    for i, applicant in enumerate(applicants, 1):
        name = applicant.get("Name", "Unknown")
        safe_name = sanitize_filename(name)
        apply_id = str(applicant.get("ApplyID", ""))

        # Save profile text (minimal — just structured metadata)
        # In full implementation we'd scrape iframe text; here we write what the API gave us
        txt_fname = f"{safe_name}_{apply_id}.txt"
        txt_path = os.path.join(txt_dir, txt_fname)
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
            f"ScrapedAt:     {_now()}\n"
            f"{'=' * 44}\n\n"
        )
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(header)
        txt_ok += 1

        # Try CV download
        cv_fname = f"{args.jobno}_{safe_name}_{ts}_uploaded.pdf"
        cv_path = os.path.join(cv_dir, cv_fname)
        status = client.download_cv(applicant, cv_path, jobno=args.jobno, job_title=(args.job_title or args.label))
        if status == "success":
            cv_ok += 1
            print(f"  [{i}/{len(applicants)}] CV OK   – {name}", flush=True)
        else:
            fail += 1
            failed_downloads.append({
                "ApplyID": apply_id,
                "Name": name,
                "Status": status,
            })
            print(f"  [{i}/{len(applicants)}] CV FAIL – {name} ({status})", flush=True)

    # ── Summary ───────────────────────────────────────────────────────
    print(f"\n[DONE] Results for job {args.jobno}:", flush=True)
    print(f"  Profile texts saved: {txt_ok}", flush=True)
    print(f"  CVs downloaded:      {cv_ok}", flush=True)
    print(f"  CV download fails:   {fail}", flush=True)

    if failed_downloads:
        fail_path = os.path.join(job_dir, "failed_downloads.json")
        with open(fail_path, "w", encoding="utf-8") as f:
            json.dump(failed_downloads, f, indent=2)
        print(f"  Failed list saved: {fail_path}", flush=True)

    print(f"\nOutput directory: {job_dir}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print(f"[FATAL] {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)
