"""
migrate_apply_ids.py — One-time fix: merge legacy filename-keyed candidate
rows (e.g. 'Abdulla_Al_Noman_390578420') into numeric-keyed rows ('390578420')
so BDJobs metadata (salary, email, mobile, etc.) and ranker scores share a row.

Safe to re-run.  Dry-run first:
    python migrate_apply_ids.py
Apply:
    python migrate_apply_ids.py --apply
"""

from __future__ import annotations

import argparse
import os
import re
import sys

import psycopg2
import psycopg2.extras

PG_CONN = {
    "host":     os.environ.get("PG_HOST",     "localhost"),
    "port":     int(os.environ.get("PG_PORT", "5432")),
    "dbname":   os.environ.get("PG_DBNAME",   "resume_ranking"),
    "user":     os.environ.get("PG_USER",     "postgres"),
    "password": os.environ.get("PG_PASSWORD", "ai&dt@OIPLC"),
}

# Columns written by the ranker — copy these from the legacy row to the
# numeric row during merge.  Metadata columns (email, salary, etc.) stay on
# the numeric row untouched.
RANKER_COLS = [
    "candidate_name", "profile_txt_path", "pdf_path", "pdf_text_chars",
    "jd_used",
    "overall_score", "skills_score", "experience_score",
    "leadership_score", "education_score", "culture_fit_score",
    "experience_years",
    "strengths", "gaps", "risk_flags",
    "recommendation", "reasoning",
    "ranked_at", "rank_error",
]

LEGACY_KEY_RE = re.compile(r"_(\d+)$")


def find_pairs(cur) -> list[tuple[str, str, str]]:
    """Return list of (job_label, legacy_id, numeric_id) to merge."""
    cur.execute("""
        SELECT job_label, apply_id
        FROM candidates
        WHERE apply_id ~ '[A-Za-z]'
    """)
    pairs = []
    for job_label, legacy_id in cur.fetchall():
        m = LEGACY_KEY_RE.search(legacy_id)
        if not m:
            continue
        numeric_id = m.group(1)
        cur.execute(
            "SELECT 1 FROM candidates WHERE job_label=%s AND apply_id=%s",
            (job_label, numeric_id),
        )
        if cur.fetchone():
            pairs.append((job_label, legacy_id, numeric_id))
    return pairs


def merge_pair(cur, job_label: str, legacy_id: str, numeric_id: str) -> None:
    set_clause = ", ".join(f"{c} = src.{c}" for c in RANKER_COLS)
    cur.execute(
        f"""
        UPDATE candidates AS dst
           SET {set_clause}
          FROM candidates AS src
         WHERE dst.job_label = %s AND dst.apply_id = %s
           AND src.job_label = %s AND src.apply_id = %s
        """,
        (job_label, numeric_id, job_label, legacy_id),
    )
    cur.execute(
        "DELETE FROM candidates WHERE job_label=%s AND apply_id=%s",
        (job_label, legacy_id),
    )


def orphans_without_metadata(cur) -> list[tuple[str, str]]:
    """Legacy rows whose numeric counterpart does NOT exist — these just need
    to have their apply_id rewritten to the numeric form."""
    cur.execute("""
        SELECT job_label, apply_id
        FROM candidates
        WHERE apply_id ~ '[A-Za-z]'
    """)
    result = []
    for job_label, legacy_id in cur.fetchall():
        m = LEGACY_KEY_RE.search(legacy_id)
        if not m:
            continue
        numeric_id = m.group(1)
        cur.execute(
            "SELECT 1 FROM candidates WHERE job_label=%s AND apply_id=%s",
            (job_label, numeric_id),
        )
        if not cur.fetchone():
            result.append((job_label, legacy_id, numeric_id))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="Apply the migration (default: dry-run).")
    args = parser.parse_args()

    conn = psycopg2.connect(**PG_CONN)
    conn.autocommit = False

    with conn.cursor() as cur:
        mergeable = find_pairs(cur)
        rewritable = orphans_without_metadata(cur)

    total_legacy = len(mergeable) + len(rewritable)
    print(f"Found {total_legacy} legacy row(s):")
    print(f"  - {len(mergeable):>4}  will MERGE into existing numeric rows")
    print(f"  - {len(rewritable):>4}  will be RENAMED to numeric apply_id")

    if total_legacy == 0:
        print("Nothing to do.")
        conn.close()
        return 0

    # Summary per job.
    jobs: dict[str, dict[str, int]] = {}
    for job, _, _ in mergeable:
        jobs.setdefault(job, {"merge": 0, "rename": 0})["merge"] += 1
    for job, _, _ in rewritable:
        jobs.setdefault(job, {"merge": 0, "rename": 0})["rename"] += 1
    print("\nBreakdown per job:")
    for job, counts in sorted(jobs.items()):
        print(f"  {job:<50} merge={counts['merge']:>4}  rename={counts['rename']:>4}")

    if not args.apply:
        print("\n(dry-run — re-run with --apply to execute)")
        conn.close()
        return 0

    print("\nApplying migration...")
    with conn.cursor() as cur:
        for job, legacy_id, numeric_id in mergeable:
            merge_pair(cur, job, legacy_id, numeric_id)
        for job, legacy_id, numeric_id in rewritable:
            cur.execute(
                "UPDATE candidates SET apply_id=%s WHERE job_label=%s AND apply_id=%s",
                (numeric_id, job, legacy_id),
            )
    conn.commit()
    print(f"Migration complete. Merged {len(mergeable)}, renamed {len(rewritable)}.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
