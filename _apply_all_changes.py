"""
Master script to apply all spec changes from the Windsurf prompt.
"""
import re

# =============================================================================
# 1. db.py: Add fetch_departments_with_roles + ALTER TABLE migration
# =============================================================================
DB_PATH = r"F:\Projects\resume_ranking\resume_app\db.py"
with open(DB_PATH, "r", encoding="utf-8") as f:
    db_content = f.read()

# Check if already applied
if "fetch_departments_with_roles" not in db_content:
    # Insert after fetch_all_jobs (before fetch_job_labels)
    marker = "\n\ndef fetch_job_labels(conn) -> list:"
    if marker in db_content:
        new_func = '''

def fetch_departments_with_roles(conn) -> list[dict]:
    """
    Returns all departments that have at least one job posting,
    grouped with their roles and live applicant/ranked/error counts.

    Called by the Job Rankings landing accordion.
    """
    sql = """
        SELECT
            COALESCE(j.department, 'Uncategorized')          AS department,
            j.job_label,
            j.job_title,
            j.status,
            j.salary_range,
            j.location,
            j.min_experience,
            j.education_req,
            j.required_skills,
            COUNT(c.id)                                       AS total,
            SUM(CASE WHEN c.overall_score IS NOT NULL
                     THEN 1 ELSE 0 END)                       AS ranked,
            SUM(CASE WHEN c.recommendation = 'Shortlist'
                     THEN 1 ELSE 0 END)                       AS shortlisted,
            SUM(CASE WHEN c.recommendation = 'Maybe'
                     THEN 1 ELSE 0 END)                       AS maybe,
            SUM(CASE WHEN c.recommendation = 'Reject'
                     THEN 1 ELSE 0 END)                       AS rejected,
            SUM(CASE WHEN c.rank_error IS NOT NULL
                          AND c.overall_score IS NULL
                     THEN 1 ELSE 0 END)                       AS errors,
            ROUND(AVG(c.overall_score))                       AS avg_score
        FROM jobs j
        LEFT JOIN candidates c ON c.job_label = j.job_label
        GROUP BY
            j.department, j.job_label, j.job_title, j.status,
            j.salary_range, j.location, j.min_experience,
            j.education_req, j.required_skills
        ORDER BY j.department ASC, j.created_at DESC NULLS LAST
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    from collections import defaultdict
    dept_map = defaultdict(lambda: {
        "department":        "",
        "roles":             [],
        "total_roles":       0,
        "total_applicants":  0,
        "total_ranked":      0,
        "total_shortlisted": 0,
        "total_errors":      0,
    })

    for r in rows:
        dept = r.get("department") or "Uncategorized"
        role = {
            "job_label":       r["job_label"],
            "job_title":       r.get("job_title") or r["job_label"],
            "status":          r.get("status")          or "Pending",
            "salary_range":    r.get("salary_range")    or "Negotiable",
            "location":        r.get("location")        or "Bangladesh",
            "min_experience":  r.get("min_experience")  or "Any",
            "education_req":   r.get("education_req")   or "Any",
            "required_skills": r.get("required_skills") or [],
            "total":           int(r.get("total")       or 0),
            "ranked":          int(r.get("ranked")      or 0),
            "shortlisted":     int(r.get("shortlisted") or 0),
            "maybe":           int(r.get("maybe")       or 0),
            "rejected":        int(r.get("rejected")    or 0),
            "errors":          int(r.get("errors")      or 0),
            "avg_score":       int(r["avg_score"]) if r.get("avg_score") is not None else None,
        }
        d = dept_map[dept]
        d["department"]        = dept
        d["roles"].append(role)
        d["total_roles"]       += 1
        d["total_applicants"]  += role["total"]
        d["total_ranked"]      += role["ranked"]
        d["total_shortlisted"] += role["shortlisted"]
        d["total_errors"]      += role["errors"]

    return sorted(dept_map.values(), key=lambda x: x["department"])


def fetch_job_labels'''
        db_content = db_content.replace(marker, new_func)
        print("[OK] Added fetch_departments_with_roles to db.py")
    else:
        print("[ERROR] Could not find fetch_job_labels marker in db.py")
else:
    print("[SKIP] fetch_departments_with_roles already in db.py")

# Add ALTER TABLE migration
if "rank_error TYPE TEXT" not in db_content:
    marker = "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS bdjobs_experience TEXT;"
    if marker in db_content:
        db_content = db_content.replace(
            marker,
            marker + "\nALTER TABLE candidates ALTER COLUMN rank_error TYPE TEXT;   -- remove any length limit"
        )
        print("[OK] Added rank_error TYPE TEXT migration")
    else:
        print("[WARNING] Could not find bdjobs_experience migration marker")
else:
    print("[SKIP] rank_error TYPE TEXT migration already present")

with open(DB_PATH, "w", encoding="utf-8") as f:
    f.write(db_content)

# =============================================================================
# 2. ranker.py: Fix call_ollama_async + process_one guard + upsert_error cap
# =============================================================================
RANKER_PATH = r"F:\Projects\resume_ranking\ranker.py"
with open(RANKER_PATH, "r", encoding="utf-8") as f:
    rcontent = f.read()

# 2a. Fix call_ollama_async: add ValueError + json.JSONDecodeError to except clause
old_except = "except (aiohttp.ClientError, asyncio.TimeoutError) as e:"
new_except = "except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError, ValueError) as e:"
if old_except in rcontent and new_except not in rcontent:
    rcontent = rcontent.replace(old_except, new_except)
    print("[OK] Fixed except clause in call_ollama_async")
else:
    print("[SKIP] except clause already fixed or not found")

# 2b. Fix upsert_error: increase cap from 500 to 1000
old_upsert = "(job_label, apply_id, name, txt_path, error_msg[:500])"
new_upsert = "(job_label, apply_id, name, txt_path, error_msg[:1000])"
if old_upsert in rcontent:
    rcontent = rcontent.replace(old_upsert, new_upsert)
    print("[OK] Increased upsert_error cap to 1000")
else:
    print("[SKIP] upsert_error cap already fixed or not found")

# 2c. Add profile_text length guard in process_one
# Find: profile_text = await asyncio.to_thread(_read_txt)
# Add guard after it
old_profile = "            profile_text = await asyncio.to_thread(_read_txt)"
if old_profile in rcontent and "_profile_stripped = profile_text.strip()" not in rcontent:
    guard = '''            profile_text = await asyncio.to_thread(_read_txt)

            # Guard: minimum profile length
            _profile_stripped = profile_text.strip() if profile_text else ""
            if len(_profile_stripped) < 150:
                raise ValueError(
                    f"EMPTY_PROFILE: Profile text is only {len(_profile_stripped)} chars "
                    f"(minimum 150 required). "
                    f"The resume text file may be empty, corrupted, or from a scanned PDF. "
                    f"File: {txt_path}"
                )
            profile_text = _profile_stripped   # use stripped version'''
    rcontent = rcontent.replace(old_profile, guard)
    print("[OK] Added profile_text length guard in process_one")
else:
    print("[SKIP] profile_text guard already present or not found")

with open(RANKER_PATH, "w", encoding="utf-8") as f:
    f.write(rcontent)

# =============================================================================
# 3. Create rerank_failed.py
# =============================================================================
RERANK_PATH = r"F:\Projects\resume_ranking\rerank_failed.py"
rerank_content = '''"""
rerank_failed.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Clears rank_error for all candidates that failed ranking
so they are re-processed on the next ranker run.

Usage:
    python rerank_failed.py                     # clear all failed
    python rerank_failed.py --job <job_label>   # clear for one job only
    python rerank_failed.py --dry-run           # show what would be cleared
    python rerank_failed.py --error-type empty  # only clear empty-response failures
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from __future__ import annotations
import argparse
import os
import psycopg2

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

PG = {
    "host":     os.environ.get("PG_HOST",     "localhost"),
    "port":     int(os.environ.get("PG_PORT", "5432")),
    "dbname":   os.environ.get("PG_DBNAME",   "resume_ranking"),
    "user":     os.environ.get("PG_USER",     "postgres"),
    "password": os.environ.get("PG_PASSWORD", "ai&dt@OIPLC"),
}

ERROR_FILTERS = {
    "empty":    "%Expecting value: line 1 column 1%",
    "timeout":  "%timeout%",
    "pdf":      "%PDF_EXTRACT%",
    "encoding": "%encoding%",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job",        type=str, default=None,
                        help="Filter to one job_label only")
    parser.add_argument("--error-type", type=str, default=None,
                        choices=list(ERROR_FILTERS.keys()),
                        help="Only clear a specific error type")
    parser.add_argument("--dry-run",    action="store_true",
                        help="Show what would be cleared without modifying DB")
    args = parser.parse_args()

    conn = psycopg2.connect(**PG)
    conn.autocommit = True

    where = ["rank_error IS NOT NULL", "overall_score IS NULL"]
    params: list = []

    if args.job:
        where.append("job_label = %s")
        params.append(args.job)

    if args.error_type:
        pattern = ERROR_FILTERS[args.error_type]
        where.append("rank_error ILIKE %s")
        params.append(pattern)

    where_sql = " AND ".join(where)

    with conn.cursor() as cur:
        cur.execute(
            f"SELECT apply_id, job_label, LEFT(rank_error, 80) AS err "
            f"FROM candidates WHERE {where_sql} ORDER BY ranked_at DESC",
            params,
        )
        rows = cur.fetchall()

    print(f"\\n{'[DRY RUN] ' if args.dry_run else ''}Found {len(rows)} failed candidates to clear.\\n")

    if args.dry_run:
        for apply_id, job_label, err in rows[:30]:
            print(f"  [{job_label}] {apply_id} — {err}")
        if len(rows) > 30:
            print(f"  ... and {len(rows) - 30} more")
        print("\\nRe-run without --dry-run to apply.")
        return

    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE candidates SET rank_error = NULL, ranked_at = NULL "
            f"WHERE {where_sql}",
            params,
        )
        cleared = cur.rowcount

    conn.close()
    print(f"✅ Cleared rank_error for {cleared} candidates.")
    print(f"\\nNext step — re-rank them:")
    if args.job:
        print(f"  python ranker.py --job {args.job}")
    else:
        print(f"  python ranker.py --job <job_label>   (run for each job)")
    print()


if __name__ == "__main__":
    main()
'''
with open(RERANK_PATH, "w", encoding="utf-8") as f:
    f.write(rerank_content)
print("[OK] Created rerank_failed.py")

print("\\nPhase 1 & 2 complete.")
