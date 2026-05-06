"""
ingest_metadata.py — Standalone script to ingest candidate metadata from CSV into PostgreSQL.
Run once per job label after bdjobs_downloader.py completes.

Usage:
    python ingest_metadata.py --job AIDigital_Transformation-SrExecutive
    python ingest_metadata.py --all   (ingests all job folders found in downloaded_resumes)
"""

import os
import argparse
import sys

# Add app dir to path so db.py is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "resume_app"))

from db import ingest_metadata, RESUMES_BASE


def run_job(job_label: str):
    meta_csv = os.path.join(RESUMES_BASE, job_label, f"{job_label}_metadata.csv")
    if not os.path.exists(meta_csv):
        print(f"  [SKIP] No metadata CSV found for: {job_label}")
        print(f"         Expected: {meta_csv}")
        return

    print(f"  [INGEST] {job_label} ...")
    updated, skipped = ingest_metadata(job_label, meta_csv)
    print(f"  [DONE]   {updated} candidates imported, {skipped} skipped.")


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--job", help="Specific job folder name")
    group.add_argument("--all", action="store_true", help="Ingest all job folders")
    args = parser.parse_args()

    if args.all:
        if not os.path.isdir(RESUMES_BASE):
            print(f"ERROR: RESUMES_BASE not found: {RESUMES_BASE}")
            return
        folders = [
            d for d in os.listdir(RESUMES_BASE)
            if os.path.isdir(os.path.join(RESUMES_BASE, d))
        ]
        print(f"Found {len(folders)} job folders.")
        for folder in sorted(folders):
            run_job(folder)
    else:
        run_job(args.job)


if __name__ == "__main__":
    main()
