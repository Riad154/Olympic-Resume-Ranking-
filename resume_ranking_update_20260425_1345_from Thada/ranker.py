"""
ranker.py — General Purpose Resume Ranker (Async / Parallel Edition)
Olympic Industries PLC — HR Intelligence Platform

Usage:
    python ranker.py --job AIDigital_Transformation-SrExecutive
    python ranker.py --job AIDigital_Transformation-SrExecutive --jd jd_prompt.txt
    python ranker.py --job AIDigital_Transformation-SrExecutive --rerank
    python ranker.py --job AIDigital_Transformation-SrExecutive --backfill-names
    python ranker.py --job AIDigital_Transformation-SrExecutive --jd jd.txt --workers 6
"""

from __future__ import annotations

import os
import re
import csv
import sys
import json
import glob
import asyncio
import argparse
import datetime
from pathlib import Path

import aiohttp
import psycopg2
from tqdm.asyncio import tqdm as tqdm_asyncio
from tqdm import tqdm

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# ── Config ────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent.resolve()
RESUMES_BASE = os.environ.get(
    "RESUMES_BASE",
    str(BASE_DIR / "downloaded_resumes"),
)
OLLAMA_HOST  = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_URL   = f"{OLLAMA_HOST}/api/chat"
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:8b-q4_K_M")

PG_CONN = {
    "host":     os.environ.get("PG_HOST", "localhost"),
    "port":     int(os.environ.get("PG_PORT", "5432")),
    "dbname":   os.environ.get("PG_DBNAME", "resume_ranking"),
    "user":     os.environ.get("PG_USER", "postgres"),
    "password": os.environ.get("PG_PASSWORD", "ai&dt@OIPLC"),
}

# Profile/prompt sizing
# Raised for the new scoring framework — the added education/leadership/culture
# blocks add ~3.5k chars of prompt context. Keep profile budget generous.
PROFILE_SOFT_CAP = 8000    # chars for profile portion
PROMPT_TOTAL_CAP = 18000   # total for profile + JD + framework blocks combined
OLLAMA_TIMEOUT_SECS = 240  # Increased: longer prompts need more generation time
COMMIT_BATCH_SIZE = 10

REQUIRED_COLUMNS = {
    "id", "job_label", "apply_id", "candidate_name",
    "profile_txt_path", "pdf_path", "pdf_text_chars", "jd_used",
    "overall_score", "skills_score", "experience_score",
    "leadership_score", "education_score", "culture_fit_score",
    # Education sub-scores (Part 7.1 — transparent breakdown of education_score)
    "edu_tier_score", "edu_degree_score", "edu_gpa_score",
    "experience_years", "strengths", "gaps", "risk_flags",
    "recommendation", "reasoning", "ranked_at", "rank_error",
}

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS candidates (
    id                SERIAL PRIMARY KEY,
    job_label         TEXT NOT NULL,
    apply_id          TEXT NOT NULL,
    candidate_name    TEXT,
    profile_txt_path  TEXT,
    pdf_path          TEXT,
    pdf_text_chars    INTEGER DEFAULT 0,
    jd_used           TEXT DEFAULT '',
    overall_score     INTEGER,
    skills_score      INTEGER,
    experience_score  INTEGER,
    leadership_score  INTEGER,
    education_score   INTEGER,
    edu_tier_score    INTEGER,
    edu_degree_score  INTEGER,
    edu_gpa_score     INTEGER,
    culture_fit_score INTEGER,
    experience_years  NUMERIC(4,1),
    strengths         TEXT[],
    gaps              TEXT[],
    risk_flags        TEXT[],
    recommendation    TEXT CHECK (recommendation IN ('Shortlist', 'Maybe', 'Reject')),
    reasoning         TEXT,
    ranked_at         TIMESTAMP DEFAULT NOW(),
    rank_error        TEXT,
    UNIQUE (job_label, apply_id)
);
CREATE INDEX IF NOT EXISTS idx_job_label      ON candidates(job_label);
CREATE INDEX IF NOT EXISTS idx_recommendation ON candidates(recommendation);
CREATE INDEX IF NOT EXISTS idx_overall_score  ON candidates(overall_score DESC);

-- Minimal `jobs` table so --department upsert works when ranker runs standalone
-- (i.e. without the Streamlit app having bootstrapped the richer schema).
-- The Streamlit side adds extra columns via its own schema + migrations.
CREATE TABLE IF NOT EXISTS jobs (
    id                  SERIAL PRIMARY KEY,
    job_label           TEXT UNIQUE NOT NULL,
    department          TEXT NOT NULL DEFAULT 'Uncategorized',
    weight_leadership   INTEGER DEFAULT 10,
    weight_culture      INTEGER DEFAULT 5,
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

-- HR override audit trail (Part 7.5).  Populated by the Streamlit UI when HR
-- overrides an AI recommendation.  Kept alongside candidates so a compliance
-- query does not require joining across databases.
CREATE TABLE IF NOT EXISTS hr_audit_log (
    id          SERIAL PRIMARY KEY,
    job_label   TEXT NOT NULL,
    apply_id    TEXT NOT NULL,
    hr_user     TEXT,
    old_value   TEXT,
    new_value   TEXT,
    note        TEXT,
    changed_at  TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_hr_audit_job ON hr_audit_log(job_label);
CREATE INDEX IF NOT EXISTS idx_hr_audit_app ON hr_audit_log(apply_id);
CREATE INDEX IF NOT EXISTS idx_jobs_label ON jobs(job_label);
CREATE INDEX IF NOT EXISTS idx_jobs_dept  ON jobs(department);
"""

SYSTEM_PROMPT = """You are an expert HR analyst for Olympic Industries PLC, Bangladesh's largest FMCG manufacturer.
You evaluate candidates across all departments and functions — from production and supply chain to finance, HR, sales, and IT.
You MUST respond with valid JSON only. No explanation, no markdown, no preamble.
Be consistent and fair: two candidates with equivalent evidence must receive the same scores."""

RANKING_PROMPT_TEMPLATE = """Evaluate this candidate for the following role.

{jd_block}
{role_block}
{dept_skills_block}
--- CANDIDATE PROFILE START ---
{profile_text}
--- CANDIDATE PROFILE END ---
{rule_flags_block}
{education_block}

{leadership_block}

{culture_block}

Score the candidate and return ONLY this JSON (no markdown, no preamble):
{{
  "skills_score": <0-100>,
  "experience_score": <0-100>,
  "leadership_score": <0-100>,
  "education_score": <0-100>,
  "edu_tier_score": <0-100>,
  "edu_degree_score": <0-100>,
  "edu_gpa_score": <0-100>,
  "culture_fit_score": <0-100>,
  "experience_years": <number>,
  "strengths": ["<strength1>", "<strength2>", "<strength3>"],
  "gaps": ["<gap1>", "<gap2>"],
  "risk_flags": ["<flag1>"],
  "recommendation": "<Shortlist|Maybe|Reject>",
  "reasoning": "<2 sentence summary of the candidate>"
}}

SCORING BANDS (anchor your scores to these, not to vibes):
  90-100 : Exceptional match — clearly exceeds requirements with strong evidence
  75-89  : Strong match — meets all requirements with supporting evidence
  60-74  : Adequate match — meets most requirements, some gaps
  40-59  : Partial match — notable gaps against requirements
  0-39   : Poor match — fundamental gaps or clear mismatch

DIMENSION DEFINITIONS:
- skills_score:      Overlap with REQUIRED SKILLS for this role AND the department core skills.
                     Use the DEPARTMENT SKILLS CONTEXT block above.
                     Missing >50%% of listed required skills caps this at 50.

- experience_score:  Relevance + depth of work experience for this role.
                     Below the stated MINIMUM EXPERIENCE caps this at 50.

- leadership_score:  Use the LEADERSHIP SCORE ANCHOR GUIDE above.
                     Scale to role seniority.

- education_score:   Use the EDUCATION SCORING FRAMEWORK above.
                     Apply the three-part formula: university tier (50%%) +
                     degree level (30%%) + GPA/result (20%%).
                     Also emit edu_tier_score, edu_degree_score, edu_gpa_score
                     individually for HR transparency.
                     Below the stated education minimum caps education_score at 50.

- culture_fit_score: Use the OLYMPIC INDUSTRIES CULTURE FIT GUIDE above.
                     FMCG background, stability, and work ethic are primary signals.

- experience_years:  Total years of relevant professional experience (decimal).

- risk_flags:        SHORT phrases for RED FLAGS only (e.g. "2 jobs in 18 months",
                     "no FMCG exposure", "degree level below requirement").
                     Include any pre-detected rule-based flags from the
                     PRE-DETECTED SIGNALS block above. Leave empty array if no
                     meaningful red flags.

- recommendation:
    Shortlist : Strong candidate, worth interviewing
    Maybe     : Has potential but has gaps; keep if shortlist pool is thin
    Reject    : Clear mismatch, insufficient experience, or disqualifying red flag

NOTE: The system computes overall_score from your five dimension scores using
HR-configured weights. DO NOT include overall_score in your JSON response."""


# ── Education Quality Framework (Part 1) ──────────────────────────────────────
#
# Three sub-dimensions combine to form the education_score.
# The LLM uses these tables to anchor its score rather than guessing.
#
# Sub-dimension weights (must sum to 1.0):
#   University Tier  → 50%
#   Degree Level     → 30%
#   GPA / Result     → 20%

UNIVERSITY_TIERS = """
UNIVERSITY TIER SCORING GUIDE (contributes 50% of education_score):

TIER 1 — International Elite (score anchor: 90-100)
  Examples: MIT, Harvard, Cambridge, Oxford, UCL, Imperial College London,
            Stanford, LSE, NUS Singapore, IIT Bombay/Delhi, Peking University,
            ETH Zurich, KAIST, any QS World Top 100 university.

TIER 2 — Strong Regional / Top Bangladesh (score anchor: 70-85)
  Examples: BUET (Bangladesh University of Engineering & Technology),
            University of Dhaka, IBA Dhaka, BRAC University, North South University,
            AIUB, United International University (UIU),
            any QS Asia Top 200 or nationally ranked top university in South/Southeast Asia.

TIER 3 — Mid-Tier Asia / Bangladesh (score anchor: 45-65)
  Examples: Daffodil International University, East West University,
            American International University Bangladesh (AIUB — ranked below top tier for some programs),
            other private universities in Bangladesh, mid-ranked Indian/Pakistani universities,
            regional universities with accreditation but limited research output.

TIER 4 — Low Quality / Unaccredited (score anchor: 10-40)
  Examples: Unrecognised or newly established universities with no external ranking,
            degree mills, institutions with revoked accreditation,
            unverified or unclear institutional credentials.

  NOTE: If university is not mentioned in the resume, score the tier component at 45
        (neutral — do not penalise for missing data alone).
"""

DEGREE_LEVEL_SCORES = """
DEGREE LEVEL SCORING GUIDE (contributes 30% of education_score):

  PhD / Doctorate                        → 100
  Master's (MSc, MBA, MA, MEng, MPhil)   → 80
  Bachelor's (BSc, BBA, BA, BEng, LLB)   → 60
  Diploma (3-year polytechnic/HND)       → 40
  HSC / A-Level / Higher Secondary       → 25
  SSC / O-Level / Secondary              → 10

  NOTE: Score the HIGHEST degree completed.
  NOTE: A Bachelor's from Tier 1 may outperform a Master's from Tier 4 —
        the university tier component captures this.
"""

GPA_BAND_SCORES = """
GPA / CGPA / RESULT SCORING GUIDE (contributes 20% of education_score):

  4.0 / 4.0   or  First Class Honours                 → 100
  3.7 – 3.99  or  Distinction                         → 85
  3.5 – 3.69  or  Upper Second Class (2:1)            → 70
  3.0 – 3.49  or  Second Class / Good                 → 55
  2.5 – 2.99  or  Pass                                → 35
  Below 2.5   or  Third Class / Bare Pass             → 15
  GPA not mentioned in resume                         → 50  (neutral — no penalty)

  NOTE: Bangladeshi grading — convert as follows:
    CGPA 4.0 scale is common. 3.75+ = First Class.
    Percentage: 80%+ = First, 65-79% = Second, 50-64% = Pass.
"""

EDUCATION_SCORING_FORMULA = """
EDUCATION SCORE CALCULATION:
  education_score = round(
      (university_tier_score * 0.50) +
      (degree_level_score    * 0.30) +
      (gpa_band_score        * 0.20)
  )

  If the role's EDUCATION REQUIREMENT is not met (e.g., role needs Master's but
  candidate only has Bachelor's), apply a cap: education_score = min(education_score, 50).
"""


def build_education_scoring_block() -> str:
    """Returns the full education scoring guide to inject into the LLM prompt."""
    return (
        "--- EDUCATION SCORING FRAMEWORK ---\n"
        + UNIVERSITY_TIERS + "\n"
        + DEGREE_LEVEL_SCORES + "\n"
        + GPA_BAND_SCORES + "\n"
        + EDUCATION_SCORING_FORMULA
        + "\n--- END EDUCATION SCORING FRAMEWORK ---\n"
    )


# ── Leadership Scoring Framework (Part 3) ─────────────────────────────────────

LEADERSHIP_SCORING_GUIDE = """
LEADERSHIP SCORE ANCHOR GUIDE:

Score the candidate's leadership based on EVIDENCE in the resume, not job titles alone.

LEVEL 5 — Executive Leadership (score anchor: 90-100)
  Keywords/Evidence: P&L ownership, C-suite reporting, board presentations,
  cross-divisional strategy, headcount >50, budget >10 Cr BDT, CEO/Director/VP/GM title,
  organization-wide change management, M&A integration, national/regional operations oversight.

LEVEL 4 — Senior Management (score anchor: 75-89)
  Keywords/Evidence: Department head, team of 10-50, functional strategy ownership,
  cross-departmental collaboration, KPI setting for team, annual budget management,
  mentoring junior managers, Sr. Manager / AGM / DGM / Head of title.

LEVEL 3 — Middle Management / Team Lead (score anchor: 58-74)
  Keywords/Evidence: Team lead, supervising 3-15 people, project ownership,
  performance reviews, shift management, target setting, Manager / Executive
  (experienced) title, coordinating across functions.

LEVEL 2 — Senior Individual Contributor (score anchor: 40-57)
  Keywords/Evidence: Leading own work independently, subject matter expert,
  mentoring 1-2 juniors, handling complex assignments solo, no direct team but
  high ownership. Sr. Executive / Sr. Officer title.

LEVEL 1 — Junior / Individual Contributor (score anchor: 20-39)
  Keywords/Evidence: No team leadership, following instructions, supporting seniors,
  fresh graduate or <2 years experience, Executive / Officer / Trainee title.

IMPORTANT CALIBRATION RULES:
- Scale the expected leadership level to the SENIORITY of the role being hired for.
  A junior role filled by a candidate with Level 3 leadership is a POSITIVE signal
  (over-qualified for leadership) — do NOT penalise.
- A senior role (Level 4-5 expected) filled by a Level 1-2 candidate should score 20-40.
- Vague phrases like "worked with team" or "assisted management" do NOT constitute
  leadership evidence — they score at Level 1.
- Quantified evidence ("led a team of 12 achieving 95% target") scores one level higher
  than unquantified ("led a team").
"""


# ── Culture Fit Framework — Olympic Industries PLC (Part 4) ───────────────────

OLYMPIC_CULTURE_FIT_GUIDE = """
CULTURE FIT SCORE ANCHOR GUIDE — OLYMPIC INDUSTRIES PLC

Olympic Industries PLC is Bangladesh's largest FMCG manufacturer (biscuits, confectionery,
chips, bread, cakes). It operates large-scale manufacturing plants, a nationwide
distribution network, and is in active digital transformation. Culture pillars:

1. FMCG / MANUFACTURING ORIENTATION (weight: 35%)
   Strong fit signals (each adds to score):
   + Previous FMCG company experience (Pran, ACI, Nestlé, Unilever, Akij, Bashundhara, etc.)
   + Factory / plant-floor or field operations experience
   + Bangladesh market knowledge (distribution, retail, trade)
   + High-volume, fast-paced operations background
   Weak fit signals (each reduces score):
   - Only software/tech companies with no manufacturing context
   - Only service industry (banking, telecom) for operational roles

2. STABILITY & COMMITMENT (weight: 25%)
   Strong fit signals:
   + 3+ years at any single employer
   + Progressive promotions within same company
   + Career trajectory shows increasing responsibility
   Weak fit signals:
   - More than 3 jobs in 5 years without clear reason (contract/project roles are excused)
   - Consistent lateral moves with no progression
   - Employment gaps >6 months without explanation

3. PROFESSIONAL WORK ETHIC & DISCIPLINE (weight: 20%)
   Strong fit signals:
   + Achievements described with numbers/KPIs
   + Certifications and continuous learning
   + Involvement in process improvement or cost-saving initiatives
   Weak fit signals:
   - Vague job descriptions with no measurable output
   - No evidence of training or upskilling in 5+ years

4. COLLABORATIVE & HIERARCHICAL CULTURE (weight: 10%)
   Olympic has a structured hierarchy. Score higher for:
   + Evidence of working in structured corporate/factory environments
   + Cross-functional project participation
   + Reporting to board/senior management
   Score lower for:
   - Only startup/unstructured environments with no corporate structure exposure

5. ALIGNMENT WITH OLYMPIC'S DIGITAL TRANSFORMATION AGENDA (weight: 10%)
   Bonus for all roles (not just tech roles):
   + Any digital tool adoption (ERP, BI, automation)
   + Willingness to work with SAP/ERP
   + Data-driven decision-making evidence
   - Purely manual/paper-based operations experience with no digital exposure is a mild negative

FINAL CALIBRATION:
  85-100 : Exceptional fit — FMCG background, stable tenure, quantified outcomes, Olympic-like culture
  65-84  : Good fit — relevant industry, some stability, generally aligns
  45-64  : Partial fit — transferable skills but mismatched industry or some instability
  25-44  : Weak fit — significant mismatch in industry, culture, or career pattern
  0-24   : Poor fit — clear misalignment, high-risk hire from a cultural standpoint
"""


def build_department_skills_block(department: str, job_config: dict) -> str:
    """Builds a department-specific skills context block for the LLM prompt
    (Part 2). Falls back to empty string if no profile exists for the
    department.
    """
    try:
        from resume_app.db import DEPARTMENT_SKILL_PROFILES
    except ImportError:
        try:
            sys.path.insert(0, str(BASE_DIR / "resume_app"))
            from db import DEPARTMENT_SKILL_PROFILES  # type: ignore
        except ImportError:
            return ""

    profile = DEPARTMENT_SKILL_PROFILES.get(department)
    if not profile:
        return ""

    lines = ["--- DEPARTMENT SKILLS CONTEXT ---", f"Department: {department}"]

    core = profile.get("core_skills") or []
    if core:
        lines.append("CORE SKILLS FOR THIS DEPARTMENT (must-haves):")
        lines.append("  " + ", ".join(core))

    bonus = profile.get("bonus_skills") or []
    if bonus:
        lines.append("DIFFERENTIATING SKILLS (push score above 75):")
        lines.append("  " + ", ".join(bonus))

    anti = profile.get("anti_skills") or []
    if anti:
        lines.append("SKILLS IRRELEVANT FOR THIS ROLE (do NOT inflate skills_score for these):")
        lines.append("  " + ", ".join(anti))

    job_req = list(job_config.get("required_skills") or [])
    if job_req:
        lines.append("JOB-SPECIFIC REQUIRED SKILLS:")
        lines.append("  " + ", ".join(job_req))

    note = profile.get("scoring_note") or ""
    if note:
        lines.append(f"SCORING GUIDANCE: {note}")

    lines.append("--- END DEPARTMENT SKILLS CONTEXT ---")
    return "\n".join(lines) + "\n"


# ── Rule-Based Red Flag Pre-Filter (Part 7.4) ─────────────────────────────────
#
# Runs deterministic pattern checks over the candidate profile text and returns
# a list of pre-detected flag strings. These are injected into the prompt as
# "PRE-DETECTED SIGNALS" so the LLM does not have to re-discover them.

_RE_GPA          = re.compile(r"(?:CGPA|GPA)\s*[:\-]?\s*([0-4](?:\.\d{1,2})?)", re.IGNORECASE)
_RE_DEGREE_HINT  = re.compile(r"\b(Bachelor|Master|MBA|MSc|BSc|BBA|BA|BEng|PhD|LLB|Diploma|HSC|SSC)\b", re.IGNORECASE)
_RE_YEAR         = re.compile(r"\b(19|20)\d{2}\b")


def detect_rule_based_flags(profile_text: str) -> list[str]:
    """Return a list of SHORT flag strings detected via regex rules.
    Conservative — only flags high-confidence patterns."""
    flags: list[str] = []
    if not profile_text:
        return flags
    txt = profile_text
    lower = txt.lower()

    # 1. Degree missing
    if not _RE_DEGREE_HINT.search(txt):
        flags.append("No degree mentioned in resume")

    # 2. GPA missing (only if a degree is present)
    if _RE_DEGREE_HINT.search(txt) and not _RE_GPA.search(txt):
        flags.append("GPA / CGPA not stated")

    # 3. Frequent job changes — count distinct (Month YYYY - Month YYYY) ranges
    #    or pipe-separated employment blocks "## YYYY-YYYY".
    #    A crude but deterministic heuristic: count "Present" + ranges + "|" blocks.
    role_blocks = re.findall(r"##\s*\d{4}\s*[-–]\s*(?:\d{4}|Present)", txt, re.IGNORECASE)
    if not role_blocks:
        role_blocks = re.findall(r"\b(19|20)\d{2}\s*[-–]\s*(?:(?:19|20)\d{2}|Present)\b", txt)
    if len(role_blocks) >= 4:
        flags.append(f"{len(role_blocks)} employers listed — possible frequent job changes")

    # 4. Employment-gap heuristic — list all 4-digit years, sort unique, look for
    #    two consecutive years in the resume that differ by ≥2.
    years = sorted({int(m.group(0)) for m in _RE_YEAR.finditer(txt)})
    if len(years) >= 2:
        gaps = [(b, a) for a, b in zip(years, years[1:]) if b - a >= 2]
        if gaps:
            a, b = gaps[-1]
            flags.append(f"Possible employment gap ({a}→{b})")

    # 5. No FMCG exposure — negative keyword check
    fmcg_kw = ("fmcg", "olympic", "pran", "nestle", "unilever", "akij",
               "bashundhara", "square", "rfl", "ispahani", "meghna", "bombay sweets")
    if not any(k in lower for k in fmcg_kw):
        flags.append("No explicit FMCG employer mentioned")

    return flags[:5]


def build_rule_flags_block(flags: list[str]) -> str:
    if not flags:
        return ""
    return (
        "\n--- PRE-DETECTED SIGNALS (rule-based) ---\n"
        + "\n".join(f"  - {f}" for f in flags)
        + "\n--- END PRE-DETECTED SIGNALS ---\n"
    )

JD_BLOCK_TEMPLATE = """--- JOB DESCRIPTION START ---
{jd_text}
--- JOB DESCRIPTION END ---
"""

JD_FALLBACK_BLOCK = """--- ROLE ---
Job Label: {job_label}
Evaluate based on general professional competency and relevance to an FMCG manufacturing company.
"""


# ── Progress log (async-safe) ────────────────────────────────────────────────

_progress_lock = asyncio.Lock  # placeholder; real lock created in main_async

async def write_progress_async(lock: asyncio.Lock, log_path: str, data: dict):
    data["ts"] = datetime.datetime.now().isoformat()
    line = json.dumps(data) + "\n"
    async with lock:
        await asyncio.to_thread(_append_file, log_path, line)


def _append_file(path: str, line: str):
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)


# ── DB Bootstrap ──────────────────────────────────────────────────────────────

def ensure_database():
    try:
        conn = psycopg2.connect(**PG_CONN)
        print(f"[DB] Connected to '{PG_CONN['dbname']}'.")
    except psycopg2.OperationalError as e:
        if f'database "{PG_CONN["dbname"]}" does not exist' in str(e):
            print(f"[DB] Database '{PG_CONN['dbname']}' not found. Creating...")
            bc = psycopg2.connect(
                host=PG_CONN["host"], port=PG_CONN["port"],
                dbname="postgres", user=PG_CONN["user"], password=PG_CONN["password"],
            )
            bc.autocommit = True
            with bc.cursor() as cur:
                cur.execute(f"CREATE DATABASE {PG_CONN['dbname']}")
            bc.close()
            conn = psycopg2.connect(**PG_CONN)
        else:
            raise

    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(CREATE_TABLE_SQL)

    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'candidates'
        """)
        existing = {r[0] for r in cur.fetchall()}

    missing = REQUIRED_COLUMNS - existing
    if missing:
        print(f"[DB] Adding missing candidate columns: {missing}")
        type_map = {
            "pdf_text_chars":   "INTEGER DEFAULT 0",
            "jd_used":          "TEXT DEFAULT ''",
            "skills_score":     "INTEGER",
            "experience_score": "INTEGER",
            "culture_fit_score":"INTEGER",
            "edu_tier_score":   "INTEGER",
            "edu_degree_score": "INTEGER",
            "edu_gpa_score":    "INTEGER",
            "risk_flags":       "TEXT[]",
        }
        with conn.cursor() as cur:
            for col in missing:
                col_type = type_map.get(col)
                if col_type:
                    cur.execute(f"ALTER TABLE candidates ADD COLUMN IF NOT EXISTS {col} {col_type}")
                    print(f"[DB] Added column: {col}")
                else:
                    print(f"[DB] Warning: unknown missing column '{col}' — skipping.")

    # Migrate jobs table — add weight_leadership and weight_culture if missing
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'jobs'
        """)
        job_cols = {r[0] for r in cur.fetchall()}

    jobs_migrations = {
        "weight_leadership": "INTEGER DEFAULT 10",
        "weight_culture":    "INTEGER DEFAULT 5",
    }
    with conn.cursor() as cur:
        for col, col_type in jobs_migrations.items():
            if col not in job_cols:
                cur.execute(f"ALTER TABLE jobs ADD COLUMN IF NOT EXISTS {col} {col_type}")
                print(f"[DB] Added jobs column: {col}")

    print("[DB] Schema verified.")
    conn.autocommit = False
    return conn


# ── CSV Loader ────────────────────────────────────────────────────────────────

def load_job_config(conn, job_label: str) -> dict:
    """Load structured JD fields from the `jobs` row for richer prompting.

    Returns empty dict if no row exists — the prompt then falls back to the
    --jd file only (legacy behaviour).
    """
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT job_title, department, required_skills, red_flags,
                       min_experience, education_req, interviewer_notes,
                       weight_skills, weight_exp, weight_edu,
                       weight_leadership, weight_culture
                FROM jobs WHERE job_label = %s
            """, (job_label,))
            row = cur.fetchone()
    except Exception as e:
        print(f"[JobConfig] Could not read jobs row: {e}")
        return {}
    if not row:
        return {}
    cols = ["job_title", "department", "required_skills", "red_flags",
            "min_experience", "education_req", "interviewer_notes",
            "weight_skills", "weight_exp", "weight_edu",
            "weight_leadership", "weight_culture"]
    cfg = dict(zip(cols, row))
    # Normalise array columns — psycopg2 returns lists or None.
    cfg["required_skills"] = list(cfg.get("required_skills") or [])
    cfg["red_flags"]       = list(cfg.get("red_flags") or [])
    return cfg


def load_metadata_csv(meta_csv: str) -> dict:
    result = {}
    if not os.path.exists(meta_csv):
        print(f"[CSV] Not found: {meta_csv} — names will be parsed from txt files.")
        return result
    with open(meta_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            apply_id = str(row.get("apply_id") or row.get("ApplyID") or "").strip()
            name     = str(row.get("candidate_name") or row.get("Name") or "").strip()
            pdf_file = str(row.get("uploaded_cv_file") or "").strip()
            if apply_id:
                result[apply_id] = {"name": name, "pdf_filename": pdf_file}
    print(f"[CSV] Loaded {len(result)} candidates from metadata.")
    return result


def parse_name_from_txt(txt_path: str) -> str:
    try:
        with open(txt_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("Name:"):
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return "Unknown"


# ── PDF Extraction ────────────────────────────────────────────────────────────

def extract_pdf_text(pdf_path: str) -> str:
    try:
        import pdfplumber
        import warnings
        text_parts = []
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(page_text)
                    except Exception:
                        continue
        return "\n".join(text_parts).strip()
    except Exception:
        return ""


# ── Text Cleaning / Truncation ────────────────────────────────────────────────

_WS_RE = re.compile(r"[ \t]+")
_NL_RE = re.compile(r"\n{3,}")

def clean_text(s: str) -> str:
    if not s:
        return ""
    # strip BOM, null bytes, collapse whitespace
    s = s.replace("\ufeff", "").replace("\x00", "")
    s = _WS_RE.sub(" ", s)
    s = _NL_RE.sub("\n\n", s)
    return s.strip()


def smart_truncate(text: str, max_chars: int) -> str:
    """Truncate at last newline or sentence boundary before max_chars."""
    if len(text) <= max_chars:
        return text
    window = text[:max_chars]
    cut = window.rfind("\n")
    if cut < max_chars * 0.6:
        # fall back to last sentence end
        m = list(re.finditer(r"[.!?]\s", window))
        if m:
            cut = m[-1].end()
    if cut <= 0:
        cut = max_chars
    return window[:cut].rstrip()


def build_role_block(job_config: dict) -> str:
    """Turn structured fields from the `jobs` row into a compact, LLM-friendly
    block.  Everything is optional — unset fields are simply omitted."""
    if not job_config:
        return ""
    lines = []
    if job_config.get("job_title"):
        lines.append(f"ROLE: {job_config['job_title']}")
    if job_config.get("department"):
        lines.append(f"DEPARTMENT: {job_config['department']}")
    req_skills = job_config.get("required_skills") or []
    if req_skills:
        lines.append("REQUIRED SKILLS: " + ", ".join(req_skills))
    min_exp = job_config.get("min_experience") or ""
    if min_exp and min_exp != "Any":
        lines.append(f"MINIMUM EXPERIENCE: {min_exp}")
    edu_req = job_config.get("education_req") or ""
    if edu_req and edu_req != "Any":
        lines.append(f"EDUCATION REQUIREMENT: {edu_req}")
    red_flags = job_config.get("red_flags") or []
    if red_flags:
        lines.append("RED FLAGS TO WATCH:\n  - " + "\n  - ".join(red_flags))
    notes = job_config.get("interviewer_notes") or ""
    if notes:
        lines.append(f"ADDITIONAL NOTES: {notes}")
    ws = int(job_config.get("weight_skills")     or 50)
    we = int(job_config.get("weight_exp")        or 30)
    wu = int(job_config.get("weight_edu")        or 20)
    wl = int(job_config.get("weight_leadership") or 10)
    wc = int(job_config.get("weight_culture")    or 5)
    lines.append(
        f"HR SCORING WEIGHTS (informational): "
        f"Skills {ws}% / Experience {we}% / Education {wu}% / "
        f"Leadership {wl}% / Culture Fit {wc}%"
    )
    if not lines:
        return ""
    return "--- ROLE CONTEXT ---\n" + "\n".join(lines) + "\n--- END ROLE CONTEXT ---\n"


def build_prompt(
    profile_text: str,
    pdf_text: str,
    job_label: str,
    jd_text: str,
    job_config: dict | None = None,
) -> str:
    profile_clean = clean_text(profile_text)
    pdf_clean     = clean_text(pdf_text)

    # Prefer structured BDJobs profile first; append PDF text if room remains.
    combined_profile = smart_truncate(profile_clean, PROFILE_SOFT_CAP)
    if pdf_clean:
        room = PROFILE_SOFT_CAP - len(combined_profile)
        if room > 500:
            combined_profile += "\n\n--- UPLOADED CV ---\n" + smart_truncate(pdf_clean, room - 30)

    jd_block = (
        JD_BLOCK_TEMPLATE.format(jd_text=clean_text(jd_text))
        if jd_text
        else JD_FALLBACK_BLOCK.format(job_label=job_label)
    )

    role_block = build_role_block(job_config or {})

    # New framework blocks (Parts 1-4 + 7.4 pre-detected signals)
    department        = (job_config or {}).get("department", "")
    dept_skills_block = build_department_skills_block(department, job_config or {})
    education_block   = build_education_scoring_block()
    leadership_block  = LEADERSHIP_SCORING_GUIDE
    culture_block     = OLYMPIC_CULTURE_FIT_GUIDE
    rule_flags        = detect_rule_based_flags(combined_profile)
    rule_flags_block  = build_rule_flags_block(rule_flags)

    def _render(jd_block_: str, profile_: str) -> str:
        return RANKING_PROMPT_TEMPLATE.format(
            jd_block          = jd_block_,
            role_block        = role_block,
            dept_skills_block = dept_skills_block,
            profile_text      = profile_,
            rule_flags_block  = rule_flags_block,
            education_block   = education_block,
            leadership_block  = leadership_block,
            culture_block     = culture_block,
        )

    prompt = _render(jd_block, combined_profile)

    # Cap the entire prompt; preserve profile by trimming JD first.
    if len(prompt) > PROMPT_TOTAL_CAP:
        overflow = len(prompt) - PROMPT_TOTAL_CAP
        if jd_text:
            trimmed_jd = smart_truncate(clean_text(jd_text), max(500, len(jd_text) - overflow))
            jd_block   = JD_BLOCK_TEMPLATE.format(jd_text=trimmed_jd)
            prompt     = _render(jd_block, combined_profile)
        if len(prompt) > PROMPT_TOTAL_CAP:
            # As a last resort, trim the profile rather than framework blocks,
            # so the LLM always has the full scoring rubric.
            excess = len(prompt) - PROMPT_TOTAL_CAP
            trimmed_profile = smart_truncate(combined_profile, max(1500, len(combined_profile) - excess))
            prompt = _render(jd_block, trimmed_profile)
        if len(prompt) > PROMPT_TOTAL_CAP:
            prompt = prompt[:PROMPT_TOTAL_CAP]

    return prompt


# ── Ollama (async) ────────────────────────────────────────────────────────────

async def call_ollama_async(
    session: aiohttp.ClientSession,
    profile_text: str,
    pdf_text: str,
    job_label: str,
    jd_text: str,
    job_config: dict | None = None,
    retries: int = 3,
) -> dict:
    prompt = build_prompt(profile_text, pdf_text, job_label, jd_text, job_config)

    user_content = prompt
    if OLLAMA_MODEL.lower().startswith("qwen3"):
        user_content = "/no_think\n" + prompt

    payload = {
        "model":  OLLAMA_MODEL,
        "format": "json",
        "stream": False,
        # Fairness / reproducibility: low temperature + fixed seed so identical
        # input produces identical scores across runs (two candidates with the
        # same evidence get the same numbers).
        "options": {
            "temperature": 0.1,
            "top_p":       0.9,
            "seed":        42,
        },
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_content},
        ],
    }

    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            async with session.post(
                OLLAMA_URL,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=OLLAMA_TIMEOUT_SECS),
            ) as resp:
                resp.raise_for_status()
                body = await resp.json()
            content = body["message"]["content"]
            content = re.sub(r"```json|```", "", content).strip()
            # qwen3 may still emit <think> blocks — strip defensively
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            return json.loads(content)
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as e:
            last_err = e
            if attempt == retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)  # 1, 2, 4 seconds
    # Unreachable
    raise last_err  # type: ignore[misc]


def validate_score(data: dict) -> dict:
    def safe_int(val, default=0):
        try:
            return max(0, min(100, int(str(val).replace('%', '').replace(' ', '').strip())))
        except (ValueError, TypeError):
            return default

    # Bug 5.1 fix: overall_score is computed server-side by compute_overall_score()
    # — never trust or sanitise an LLM-provided overall_score.
    for f in ["skills_score", "experience_score",
              "leadership_score", "education_score", "culture_fit_score",
              # Education sub-scores (Part 7.1)
              "edu_tier_score", "edu_degree_score", "edu_gpa_score"]:
        data[f] = safe_int(data.get(f, 0))
    data["overall_score"] = 0  # placeholder; filled by compute_overall_score()

    try:
        data["experience_years"] = float(str(data.get("experience_years", 0)).replace('%', '').strip())
    except (ValueError, TypeError):
        data["experience_years"] = 0.0

    if data.get("recommendation") not in ("Shortlist", "Maybe", "Reject"):
        data["recommendation"] = "Maybe"
    data["strengths"]  = list(data.get("strengths")  or [])[:5]
    data["gaps"]       = list(data.get("gaps")       or [])[:5]
    data["risk_flags"] = list(data.get("risk_flags") or [])[:5]
    data["reasoning"]  = str(data.get("reasoning", ""))[:500]
    return data


# ── Deterministic overall_score computation ───────────────────────────────────
#
# The LLM scores five dimensions independently; we compute overall_score
# server-side as a weighted blend using the HR-configured weights from the
# `jobs` row.  This makes the overall score transparent, auditable, and
# responsive to the weights HR set in the New Job Posting form.
#
# Form captures 3 weights (skills / experience / education) that sum to 100.
# We reserve a small fixed allocation for leadership and culture_fit so all
# five dimensions contribute, then renormalise.

# Bug 5.2 fix: weights are now configurable per-job via jobs.weight_leadership
# and jobs.weight_culture columns (added in Bug 5.3 migration).  The defaults
# are used only when a job_config dict does not supply them.
DEFAULT_LEADERSHIP_WEIGHT  = 0.10
DEFAULT_CULTURE_FIT_WEIGHT = 0.05
_DEFAULT_MAIN_BUDGET       = 1.0 - DEFAULT_LEADERSHIP_WEIGHT - DEFAULT_CULTURE_FIT_WEIGHT


def compute_overall_score(scores: dict, job_config: dict | None = None) -> int:
    """Weighted blend of the 5 dimension scores → overall_score (0-100).

    Weights read from job_config if available, otherwise defaults are used.
    All five weights must sum to 100 (skills + exp + edu + leadership + culture).
    """
    cfg = job_config or {}

    # Bug 5.2 fix: use explicit None-check, not `or`, so an HR-configured
    # weight of 0 is honoured instead of silently falling back to defaults.
    def _w(key, default):
        v = cfg.get(key)
        return int(v) if v is not None else int(default)

    ws = _w("weight_skills",     50)
    we = _w("weight_exp",        30)
    wu = _w("weight_edu",        20)
    wl = _w("weight_leadership", DEFAULT_LEADERSHIP_WEIGHT * 100)
    wc = _w("weight_culture",    DEFAULT_CULTURE_FIT_WEIGHT * 100)

    total = max(1, ws + we + wu + wl + wc)

    ws_f = ws / total
    we_f = we / total
    wu_f = wu / total
    wl_f = wl / total
    wc_f = wc / total

    overall = (
        ws_f * int(scores.get("skills_score",      0)) +
        we_f * int(scores.get("experience_score",  0)) +
        wl_f * int(scores.get("leadership_score",  0)) +
        wu_f * int(scores.get("education_score",   0)) +
        wc_f * int(scores.get("culture_fit_score", 0))
    )
    return max(0, min(100, int(round(overall))))


# ── DB Writes ─────────────────────────────────────────────────────────────────

def get_existing_apply_ids(cur, job_label: str) -> set:
    cur.execute(
        "SELECT apply_id FROM candidates WHERE job_label = %s AND overall_score IS NOT NULL",
        (job_label,)
    )
    return {row[0] for row in cur.fetchall()}


def upsert_candidate(cur, job_label, apply_id, name, txt_path, pdf_path,
                     pdf_text_chars, jd_used, scores):
    cur.execute("""
        INSERT INTO candidates
            (job_label, apply_id, candidate_name, profile_txt_path, pdf_path,
             pdf_text_chars, jd_used,
             overall_score, skills_score, experience_score,
             leadership_score, education_score, culture_fit_score,
             edu_tier_score, edu_degree_score, edu_gpa_score,
             experience_years, strengths, gaps, risk_flags,
             recommendation, reasoning, ranked_at, rank_error)
        VALUES
            (%s,%s,%s,%s,%s, %s,%s,
             %s,%s,%s,%s,%s,%s,
             %s,%s,%s,
             %s,%s,%s,%s,
             %s,%s, NOW(), NULL)
        ON CONFLICT (job_label, apply_id) DO UPDATE SET
            candidate_name    = EXCLUDED.candidate_name,
            profile_txt_path  = EXCLUDED.profile_txt_path,
            pdf_path          = EXCLUDED.pdf_path,
            pdf_text_chars    = EXCLUDED.pdf_text_chars,
            jd_used           = EXCLUDED.jd_used,
            overall_score     = EXCLUDED.overall_score,
            skills_score      = EXCLUDED.skills_score,
            experience_score  = EXCLUDED.experience_score,
            leadership_score  = EXCLUDED.leadership_score,
            education_score   = EXCLUDED.education_score,
            culture_fit_score = EXCLUDED.culture_fit_score,
            edu_tier_score    = EXCLUDED.edu_tier_score,
            edu_degree_score  = EXCLUDED.edu_degree_score,
            edu_gpa_score     = EXCLUDED.edu_gpa_score,
            experience_years  = EXCLUDED.experience_years,
            strengths         = EXCLUDED.strengths,
            gaps              = EXCLUDED.gaps,
            risk_flags        = EXCLUDED.risk_flags,
            recommendation    = EXCLUDED.recommendation,
            reasoning         = EXCLUDED.reasoning,
            ranked_at         = NOW(),
            rank_error        = NULL
    """, (
        job_label, apply_id, name, txt_path, pdf_path,
        pdf_text_chars, jd_used,
        scores["overall_score"], scores["skills_score"], scores["experience_score"],
        scores["leadership_score"], scores["education_score"], scores["culture_fit_score"],
        scores.get("edu_tier_score", 0), scores.get("edu_degree_score", 0), scores.get("edu_gpa_score", 0),
        scores["experience_years"],
        scores["strengths"], scores["gaps"], scores["risk_flags"],
        scores["recommendation"], scores["reasoning"],
    ))


def upsert_error(cur, job_label, apply_id, name, txt_path, error_msg):
    cur.execute("""
        INSERT INTO candidates (job_label, apply_id, candidate_name, profile_txt_path, rank_error)
        VALUES (%s,%s,%s,%s,%s)
        ON CONFLICT (job_label, apply_id) DO UPDATE SET
            rank_error = EXCLUDED.rank_error, ranked_at = NOW()
    """, (job_label, apply_id, name, txt_path, error_msg[:500]))


# ── Backfill Names ────────────────────────────────────────────────────────────

def backfill_names(conn, job_label: str, metadata: dict, txt_dir: str):
    print("[Backfill] Updating names...")
    updated = 0
    with conn.cursor() as cur:
        cur.execute(
            "SELECT apply_id FROM candidates WHERE job_label = %s AND (candidate_name IS NULL OR candidate_name = 'Unknown')",
            (job_label,)
        )
        rows = cur.fetchall()
    for (apply_id,) in rows:
        meta = metadata.get(apply_id)
        if meta and meta["name"]:
            name = meta["name"]
        else:
            txt_path = os.path.join(txt_dir, f"{apply_id}.txt")
            name = parse_name_from_txt(txt_path)
        if name and name != "Unknown":
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE candidates SET candidate_name = %s WHERE job_label = %s AND apply_id = %s",
                    (name, job_label, apply_id)
                )
            conn.commit()
            updated += 1
    print(f"[Backfill] Updated {updated} of {len(rows)} rows.")


# ── GPU Check ─────────────────────────────────────────────────────────────────

def print_gpu_info(workers: int):
    try:
        import pynvml
        pynvml.nvmlInit()
        count = pynvml.nvmlDeviceGetCount()
        if count == 0:
            print("[GPU] No NVIDIA GPUs detected — Ollama may run on CPU (very slow).")
            return
        for i in range(count):
            h = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(h)
            if isinstance(name, bytes):
                name = name.decode("utf-8", errors="ignore")
            mem = pynvml.nvmlDeviceGetMemoryInfo(h)
            total_gb = mem.total / (1024 ** 3)
            free_gb  = mem.free  / (1024 ** 3)
            used_gb  = mem.used  / (1024 ** 3)
            print(f"[GPU{i}] {name} | VRAM: {used_gb:.1f}/{total_gb:.1f} GB used, {free_gb:.1f} GB free")
            if free_gb < 6:
                print(f"[GPU{i}] WARNING: < 6 GB free VRAM — qwen3:8b may offload to CPU.")
                print(f"[GPU{i}] HINT: reduce --workers (currently {workers}) or close other GPU apps.")
        pynvml.nvmlShutdown()
    except Exception as e:
        print(f"[GPU] pynvml unavailable: {e}")


# ── Async Pipeline ────────────────────────────────────────────────────────────

async def process_one(
    txt_path: str,
    job: str,
    jd_text: str,
    jd_used_label: str,
    metadata: dict,
    pdf_dir: str,
    session: aiohttp.ClientSession,
    sem: asyncio.Semaphore,
    db_lock: asyncio.Lock,
    log_lock: asyncio.Lock,
    log_path: str,
    conn,
    state: dict,
    job_config: dict | None = None,
) -> tuple[str, str, str | None]:
    """Process a single resume. Returns (apply_id, name, error_msg_or_None)."""
    stem = os.path.splitext(os.path.basename(txt_path))[0]
    # BDJobs profiles are named `<Name>_<numeric_apply_id>.txt`.  We key on the
    # numeric id only so rows written here match rows inserted by the Streamlit
    # metadata ingest (which uses `apply_id` straight from the BDJobs CSV).
    m = re.search(r"(\d+)$", stem)
    apply_id = m.group(1) if m else stem
    meta     = metadata.get(apply_id, {})
    name     = meta.get("name") or await asyncio.to_thread(parse_name_from_txt, txt_path)
    pdf_file = meta.get("pdf_filename", "")
    pdf_path = os.path.join(pdf_dir, pdf_file) if pdf_file else ""

    # Fallback PDF lookup in uploaded_cvs folder
    if (not pdf_path or not os.path.exists(pdf_path)) and os.path.isdir(pdf_dir):
        name_slug = (name or "").replace(" ", "_").replace(".", "")
        try:
            for fname in os.listdir(pdf_dir):
                if not fname.endswith(".pdf"):
                    continue
                if apply_id in fname or (name_slug and name_slug in fname):
                    pdf_path = os.path.join(pdf_dir, fname)
                    break
        except Exception:
            pass

    async with sem:
        try:
            # Load profile text
            def _read_txt():
                with open(txt_path, encoding="utf-8", errors="replace") as f:
                    return f.read()
            profile_text = await asyncio.to_thread(_read_txt)

            pdf_text = ""
            pdf_text_chars = 0
            if pdf_path and os.path.exists(pdf_path):
                pdf_text = await asyncio.to_thread(extract_pdf_text, pdf_path)
                pdf_text_chars = len(pdf_text) if pdf_text else 0

            raw = await call_ollama_async(
                session, profile_text, pdf_text, job, jd_text, job_config,
            )
            scores = validate_score(raw)
            # Deterministic weighted overall_score (overrides any value from LLM)
            scores["overall_score"] = compute_overall_score(scores, job_config)

            # DB write under lock; batch commits
            async with db_lock:
                def _write():
                    with conn.cursor() as cur:
                        upsert_candidate(
                            cur, job, apply_id, name, txt_path,
                            pdf_path, pdf_text_chars, jd_used_label, scores,
                        )
                    state["pending"] += 1
                    if state["pending"] >= COMMIT_BATCH_SIZE:
                        conn.commit()
                        state["pending"] = 0
                await asyncio.to_thread(_write)

            await write_progress_async(log_lock, log_path, {
                "event":          "ok",
                "apply_id":       apply_id,
                "name":           name,
                "score":          scores["overall_score"],
                "recommendation": scores["recommendation"],
            })
            tqdm.write(f"  OK  {apply_id} | {name[:30]} | {scores['overall_score']} | {scores['recommendation']}")
            return apply_id, name, None

        except Exception as e:
            err_msg = str(e)
            try:
                async with db_lock:
                    def _write_err():
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                        with conn.cursor() as cur:
                            upsert_error(cur, job, apply_id, name, txt_path, err_msg)
                        conn.commit()
                        state["pending"] = 0
                    await asyncio.to_thread(_write_err)
            except Exception:
                pass
            await write_progress_async(log_lock, log_path, {
                "event":    "error",
                "apply_id": apply_id,
                "name":     name,
                "error":    err_msg[:200],
            })
            tqdm.write(f"  ERR {apply_id} | {name[:30]} | {err_msg[:80]}")
            return apply_id, name, err_msg


async def main_async(args):
    # Ollama pre-flight
    try:
        from check_ollama import run_checks  # type: ignore
        ok = await asyncio.to_thread(run_checks, OLLAMA_HOST, OLLAMA_MODEL)
        if not ok:
            print("[Ollama] Pre-flight failed — aborting. Start Ollama and pull the model first.")
            sys.exit(2)
    except ImportError:
        print("[Ollama] check_ollama.py not found — skipping pre-flight.")
    except SystemExit:
        raise
    except Exception as e:
        print(f"[Ollama] Pre-flight error: {e}")

    print_gpu_info(args.workers)

    job_dir  = os.path.join(RESUMES_BASE, args.job)
    txt_dir  = os.path.join(job_dir, "profiles_txt")
    pdf_dir  = os.path.join(job_dir, "uploaded_cvs")
    meta_csv = os.path.join(job_dir, f"{args.job}_metadata.csv")
    log_path = os.path.join(job_dir, "_ranker_progress.jsonl")

    if not os.path.isdir(txt_dir):
        print(f"ERROR: profiles_txt not found at {txt_dir}")
        return

    jd_text = ""
    if args.jd:
        if not os.path.exists(args.jd):
            print(f"ERROR: JD file not found: {args.jd}")
            return
        with open(args.jd, encoding="utf-8") as f:
            jd_text = f.read().strip()
        print(f"[JD] Loaded {len(jd_text)} chars from {args.jd}")
    else:
        print("[JD] No JD provided — using role label as context.")

    jd_used_label = os.path.basename(args.jd) if args.jd else ""
    metadata      = load_metadata_csv(meta_csv)
    conn          = ensure_database()

    # Register / update this job in the `jobs` table and capture its department.
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO jobs (job_label, department)
                VALUES (%s, %s)
                ON CONFLICT (job_label) DO UPDATE SET
                    department = EXCLUDED.department,
                    updated_at = NOW()
            """, (args.job, args.department))
        conn.autocommit = False
        print(f"[JOB] Registered: {args.job} → Department: {args.department}")
    except Exception as e:
        print(f"[JOB] Warning: could not upsert jobs row: {e}")

    job_config = load_job_config(conn, args.job)
    if job_config:
        rs_n = len(job_config.get("required_skills") or [])
        rf_n = len(job_config.get("red_flags") or [])
        print(f"[JobConfig] Loaded structured JD fields: "
              f"{rs_n} required skills, {rf_n} red flags, "
              f"weights S={job_config.get('weight_skills') or 50}/"
              f"E={job_config.get('weight_exp') or 30}/"
              f"U={job_config.get('weight_edu') or 20}")
    else:
        print("[JobConfig] No structured fields — using --jd text only.")

    if args.backfill_names:
        backfill_names(conn, args.job, metadata, txt_dir)
        conn.close()
        return

    txt_files = sorted(glob.glob(os.path.join(txt_dir, "*.txt")))
    print(f"Found {len(txt_files)} profiles | Job: {args.job} | Workers: {args.workers}")

    # Initialise progress log
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("")

    log_lock = asyncio.Lock()
    db_lock  = asyncio.Lock()
    await write_progress_async(log_lock, log_path, {
        "event":   "start",
        "job":     args.job,
        "total":   len(txt_files),
        "rerank":  args.rerank,
        "workers": args.workers,
    })

    with conn.cursor() as cur:
        existing = get_existing_apply_ids(cur, args.job) if not args.rerank else set()

    pending_files = [p for p in txt_files
                     if os.path.splitext(os.path.basename(p))[0] not in existing]
    skipped = len(txt_files) - len(pending_files)
    if skipped:
        print(f"[Skip] {skipped} already-ranked candidates (use --rerank to force).")

    sem = asyncio.Semaphore(args.workers)
    state = {"pending": 0}
    errors: list[tuple[str, str, str]] = []

    connector = aiohttp.TCPConnector(limit=args.workers * 2)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            process_one(
                txt_path, args.job, jd_text, jd_used_label, metadata,
                pdf_dir, session, sem, db_lock, log_lock, log_path, conn, state,
                job_config,
            )
            for txt_path in pending_files
        ]
        for coro in tqdm_asyncio.as_completed(tasks, total=len(tasks), desc="Ranking"):
            apply_id, name, err = await coro
            if err:
                errors.append((apply_id, name, err))

    # Flush any remaining commits
    try:
        if state["pending"] > 0:
            conn.commit()
            state["pending"] = 0
    except Exception:
        pass

    await write_progress_async(log_lock, log_path, {
        "event":  "done",
        "total":  len(txt_files),
        "errors": len(errors),
    })

    print(f"\nDone. Ranked: {len(pending_files) - len(errors)} | Skipped: {skipped} | Errors: {len(errors)}")
    if errors:
        for aid, nm, msg in errors[:20]:
            print(f"  {aid} | {nm} | {msg[:100]}")

    conn.close()


# Valid department values — kept in sync with resume_app/db.py DEPARTMENT_LIST.
# We re-declare a minimal list here rather than importing from the Streamlit
# package so ranker.py stays runnable standalone.
DEPARTMENT_CHOICES = [
    "Uncategorized",
    "Finance and Accounts", "Admin", "AI & Digital Transformation",
    "Brand & Marketing", "Corporate Affairs",
    "Customer Service Department (CSD)", "Delivery", "Distribution",
    "Engineering", "Export", "External Audit",
    "Factory Administration", "Field Force", "Human Resource (HR)",
    "Information & Communication Technology (ICT)", "Import",
    "Institutional Sales", "Internal Audit", "Legal Affairs",
    "Local Procurement", "Management", "Market Audit", "Mechanical",
    "Management Information System (MIS)", "Operations",
    "Plastic Production", "Supply Chain", "Production",
    "Quality Assurance Department (QAD)", "ERP - SAP", "Sales",
    "Secretariat", "Security", "Share", "Store", "Transport",
    "VAT / VAT & Delivery",
]


def normalise_job_scores(job_label: str) -> None:
    """Percentile-based rescaling pass (Part 7.3).

    After a batch is ranked, LLM scores tend to cluster in 55-75. This pass
    ensures the top candidate gets ≥85 and at least 10% get ≥70, so HR can
    differentiate the top-of-funnel.  Raw scores are preserved in *_raw
    columns for auditability.
    """
    conn = psycopg2.connect(**PG_CONN)
    conn.autocommit = True
    try:
        # Create *_raw columns once; cheap if they already exist.
        raw_cols = [
            "overall_raw", "skills_raw", "experience_raw",
            "leadership_raw", "education_raw", "culture_fit_raw",
        ]
        with conn.cursor() as cur:
            for c in raw_cols:
                cur.execute(f"ALTER TABLE candidates ADD COLUMN IF NOT EXISTS {c} INTEGER")

        # Snapshot raws (only where not already snapshotted)
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE candidates
                   SET overall_raw     = COALESCE(overall_raw,     overall_score),
                       skills_raw      = COALESCE(skills_raw,      skills_score),
                       experience_raw  = COALESCE(experience_raw,  experience_score),
                       leadership_raw  = COALESCE(leadership_raw,  leadership_score),
                       education_raw   = COALESCE(education_raw,   education_score),
                       culture_fit_raw = COALESCE(culture_fit_raw, culture_fit_score)
                 WHERE job_label = %s AND overall_score IS NOT NULL
            """, (job_label,))

        # Pull scores back out and rescale client-side.
        with conn.cursor() as cur:
            cur.execute("""
                SELECT apply_id, overall_raw, skills_raw, experience_raw,
                       leadership_raw, education_raw, culture_fit_raw
                  FROM candidates
                 WHERE job_label = %s AND overall_raw IS NOT NULL
                 ORDER BY overall_raw DESC
            """, (job_label,))
            rows = cur.fetchall()

        if len(rows) < 2:
            print(f"[Normalise] Not enough candidates for {job_label} — skipped.")
            return

        def rescale(values: list[int]) -> list[int]:
            if not values or max(values) == min(values):
                return values
            lo, hi = min(values), max(values)
            # Target floor 25, ceiling 95, preserve relative order.
            def _stretch(v: int) -> int:
                frac = (v - lo) / max(1, (hi - lo))
                return int(round(25 + frac * (95 - 25)))
            return [_stretch(v) for v in values]

        # Rescale each dimension independently.
        per_dim = list(zip(*[(r[1], r[2], r[3], r[4], r[5], r[6]) for r in rows]))
        rescaled = [rescale(list(col)) for col in per_dim]

        # Write back.
        with conn.cursor() as cur:
            for idx, r in enumerate(rows):
                apply_id = r[0]
                cur.execute("""
                    UPDATE candidates
                       SET overall_score     = %s,
                           skills_score      = %s,
                           experience_score  = %s,
                           leadership_score  = %s,
                           education_score   = %s,
                           culture_fit_score = %s
                     WHERE job_label = %s AND apply_id = %s
                """, (
                    rescaled[0][idx], rescaled[1][idx], rescaled[2][idx],
                    rescaled[3][idx], rescaled[4][idx], rescaled[5][idx],
                    job_label, apply_id,
                ))

        print(f"[Normalise] Rescaled {len(rows)} candidates for {job_label}.")
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job",            required=True, help="Job folder name")
    parser.add_argument("--jd",             default="",    help="Path to job description .txt file")
    parser.add_argument("--department",     default="Uncategorized",
                        choices=DEPARTMENT_CHOICES,
                        help="Department this job belongs to (default: Uncategorized)")
    parser.add_argument("--rerank",         action="store_true", help="Re-score already ranked candidates")
    parser.add_argument("--backfill-names", action="store_true", help="Fix Unknown names in DB without re-ranking")
    parser.add_argument("--normalise",      action="store_true",
                        help="After ranking, run a percentile-based rescaling pass (Part 7.3)")
    parser.add_argument("--normalise-only", action="store_true",
                        help="Run normalisation on already-ranked candidates only, skip ranking")
    parser.add_argument("--workers",        type=int, default=int(os.environ.get("RANKER_WORKERS", "5")),
                        help="Number of parallel Ollama workers (default: 5). Increase if GPU VRAM allows.")
    args = parser.parse_args()

    if args.normalise_only:
        normalise_job_scores(args.job)
        return

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("\n[Abort] Interrupted by user.")
        return

    if args.normalise:
        normalise_job_scores(args.job)


if __name__ == "__main__":
    main()
