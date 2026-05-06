#!/usr/bin/env python3
import sys
sys.path.insert(0, 'F:\\Projects\\resume_ranking\\resume_app')
from db import get_conn

conn = get_conn()
with conn.cursor() as cur:
    # Check CV storage
    cur.execute("SELECT COUNT(*) FROM candidates WHERE pdf_path IS NOT NULL AND pdf_path != %s", ('',))
    print(f"Candidates with pdf_path: {cur.fetchone()[0]}")
    
    cur.execute("SELECT COUNT(*) FROM candidates WHERE has_uploaded_cv = TRUE")
    print(f"Candidates with has_uploaded_cv=TRUE: {cur.fetchone()[0]}")
    
    # Check Delivery department candidates
    cur.execute("""SELECT COUNT(*) FROM candidates c 
                  JOIN jobs j ON c.job_label = j.job_label 
                  WHERE j.department = 'Delivery'""")
    print(f"Delivery dept candidates: {cur.fetchone()[0]}")
    
    # Check specific job
    cur.execute("""SELECT j.job_label, j.job_title, COUNT(c.apply_id) as cand_count
                  FROM jobs j 
                  LEFT JOIN candidates c ON j.job_label = c.job_label 
                  WHERE j.department = 'Delivery'
                  GROUP BY j.job_label, j.job_title""")
    print("\nDelivery Jobs:")
    for row in cur.fetchall():
        print(f"  Job: {row[0]} | {row[1]} | Candidates: {row[2]}")
    
    # Check a specific candidate
    cur.execute("""SELECT apply_id, candidate_name, pdf_path, has_uploaded_cv, job_label 
                  FROM candidates 
                  WHERE candidate_name LIKE '%Khandaker%' LIMIT 1""")
    row = cur.fetchone()
    if row:
        print(f"\nSample candidate (Khandaker):")
        print(f"  apply_id: {row[0]}")
        print(f"  name: {row[1]}")
        print(f"  pdf_path: {row[2]}")
        print(f"  has_uploaded_cv: {row[3]}")
        print(f"  job_label: {row[4]}")
