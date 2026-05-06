"""
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

    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Found {len(rows)} failed candidates to clear.\n")

    if args.dry_run:
        for apply_id, job_label, err in rows[:30]:
            print(f"  [{job_label}] {apply_id} — {err}")
        if len(rows) > 30:
            print(f"  ... and {len(rows) - 30} more")
        print("\nRe-run without --dry-run to apply.")
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
    print(f"\nNext step — re-rank them:")
    if args.job:
        print(f"  python ranker.py --job {args.job}")
    else:
        print(f"  python ranker.py --job <job_label>   (run for each job)")
    print()


if __name__ == "__main__":
    main()
