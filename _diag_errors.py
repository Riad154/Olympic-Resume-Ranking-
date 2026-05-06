"""Throwaway diagnostic: categorise rank_error rows so we can design a real fix."""
import sys, re
from collections import Counter
sys.path.insert(0, "resume_app")
from db import _new_conn

conn = _new_conn()
with conn.cursor() as cur:
    cur.execute("""
        SELECT COUNT(*) FILTER (WHERE overall_score IS NOT NULL) AS ok,
               COUNT(*) FILTER (WHERE rank_error IS NOT NULL)    AS err,
               COUNT(*)                                          AS total
          FROM candidates
    """)
    ok, err, total = cur.fetchone()
    print(f"total={total}  ok={ok}  err={err}")

    cur.execute("""
        SELECT rank_error
          FROM candidates
         WHERE rank_error IS NOT NULL
    """)
    errs = [r[0] or "" for r in cur.fetchall()]

# Classify
def classify(msg: str) -> str:
    m = msg.lower()
    if "timeout" in m or "timed out" in m:                       return "timeout"
    if "json" in m or "expecting value" in m or "decode" in m:   return "json_parse"
    if "context" in m or "num_ctx" in m or "too long" in m:      return "context_overflow"
    if "pdf" in m or "extract" in m or "corrupt" in m or "empty" in m:
                                                                 return "parse_error"
    if "rate" in m or "429" in m or "503" in m or "502" in m:    return "rate_limit"
    if "connection" in m or "refused" in m or "reset" in m:      return "connection"
    if "unicode" in m or "utf-8" in m or "codec" in m:           return "encoding"
    if "validation" in m or "missing" in m or "keyerror" in m:   return "schema"
    return "unknown"

buckets = Counter(classify(e) for e in errs)
print("\n=== ERROR BREAKDOWN ===")
for k, n in buckets.most_common():
    print(f"  {k:20s} {n:4d}")

print("\n=== TOP 15 UNIQUE MESSAGES ===")
uniq = Counter(errs).most_common(15)
for msg, n in uniq:
    print(f"[{n:>3d}] {msg[:180]}")
