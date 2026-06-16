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
                     "Present", "Continuing", "Till now", "Current" all mean TODAY.
                     Calculate from actual employment date ranges, not from resume header.
                     Merge overlapping periods — do not double-count.

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
            United International University (UIU), SUST (Shahjalal University),
            CUET (Chittagong University of Engineering & Technology),
            Jahangirnagar University, University of Chittagong (for top programs),
            any QS Asia Top 200 or nationally ranked top university in South/Southeast Asia.

TIER 3 — Mid-Tier Asia / Bangladesh (score anchor: 45-65)
  Examples: AIUB (American International University Bangladesh),
            Daffodil International University, East West University,
            Independent University Bangladesh (IUB), ULAB, IUBAT,
            other mid-ranked Indian/Pakistani private universities,
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

  PhD / Doctorate                                          → 100
  Master's (MSc, MBA, MA, MEng, MPhil)                     → 80
  Professional Certification — Tier A                       → 80
    (CA, ACCA, CFA, CMA, CIA, CGMA, CISA, FCMA, FCA, ACS, FCS)
  Bachelor's (BSc, BBA, BA, BEng, LLB)                     → 60
  Professional Certification — Tier B                       → 55
    (CIPS, PMP, Six Sigma Black Belt, CISSP, CCNA, SAP Certified)
  Diploma (3-year polytechnic / HND / PGDHRM)              → 40
  Professional Certification — Tier C                       → 35
    (Short courses, vendor certifications, BCS, short diplomas)
  HSC / A-Level / Higher Secondary                         → 25
  SSC / O-Level / Secondary                                → 10

  NOTES:
  - Score the HIGHEST credential completed.
  - A CA/ACCA without a Bachelor's still scores 80 on degree_level.
  - For Finance, Audit, and Accounting roles: CA/ACCA = Master's equivalence.
  - For Engineering roles: BEng from Tier 1/2 university outweighs MBA from Tier 3.
  - Ongoing enrollment (Part 1 / Part 2) scores one level below the full credential.
  - A Bachelor's from Tier 1 may outperform a Master's from Tier 4 —
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
  cross-divisional strategy, headcount >50, budget >10 Cr BDT,
  organization-wide change management, M&A integration, national/regional operations oversight.
  Bangladesh Titles: MD (Managing Director), DMD (Deputy MD), AMD, ED (Executive Director),
  Director, VP (Vice President), GM (General Manager),
  National Sales Manager (if leading >50 FTEs),
  CEO, COO, CFO, CTO, CISO, Factory Director.

LEVEL 4 — Senior Management (score anchor: 75-89)
  Keywords/Evidence: Department head, team of 10-50, functional strategy ownership,
  cross-departmental collaboration, KPI setting for team, annual budget management,
  mentoring junior managers.
  Bangladesh Titles: Sr. Manager, AGM (Assistant General Manager), DGM (Deputy General Manager),
  Head of [Department], Regional Sales Manager (RSM), National Key Account Manager,
  Factory Manager, Plant Manager, Senior Controller.

LEVEL 3 — Middle Management / Team Lead (score anchor: 58-74)
  Keywords/Evidence: Team lead, supervising 3-15 people, project ownership,
  performance reviews, shift management, target setting, coordinating across functions.
  Bangladesh Titles: Manager, Sr. Executive (experienced, 5+ yrs),
  Area Sales Manager (ASM), Territory Sales Manager,
  Assistant Manager (AM), Section Head, Shift-in-Charge,
  Production Supervisor (if managing >5 staff).

LEVEL 2 — Senior Individual Contributor (score anchor: 40-57)
  Keywords/Evidence: Leading own work independently, subject matter expert,
  mentoring 1-2 juniors, handling complex assignments solo, no direct team but high ownership.
  Bangladesh Titles: Sr. Executive, Sr. Officer, Sr. Sales Executive,
  Territory Sales Officer (TSO) — experienced, Principal Engineer.

LEVEL 1 — Junior / Individual Contributor (score anchor: 20-39)
  Keywords/Evidence: No team leadership, following instructions, supporting seniors,
  fresh graduate or <2 years experience.
  Bangladesh Titles: Executive, Officer, Sales Executive, Trainee Officer,
  Management Trainee (MT), Graduate Trainee (GT), Junior Executive.

IMPORTANT CALIBRATION RULES:
- Scale the expected leadership level to the SENIORITY of the role being hired for.
  A junior role filled by a candidate with Level 3 leadership is a POSITIVE signal
  (over-qualified for leadership) — do NOT penalise.
- A senior role (Level 4-5 expected) filled by a Level 1-2 candidate should score 20-40.
- Vague phrases like "worked with team" or "assisted management" = Level 1 only.
- Quantified evidence ("led a team of 12 achieving 95% of target") scores one level higher
  than unquantified ("led a team").
- For field sales roles: "TSO managing 3 DSRs" = Level 2, not Level 1.
- Titles with "National" scope (National Sales Manager, National Distribution Manager)
  always score Level 4-5 regardless of team size stated.
"""


# ── Culture Fit Framework — Olympic Industries PLC (Part 4) ───────────────────

# SCORE-03: department-aware culture fit. Different departments need different
# pillar weights. Digital/Tech roles should weight digital alignment heavily;
# Field/Sales roles need FMCG market knowledge above all; Finance roles weight
# stability + ethic; etc. The pillars themselves don't change -- only the
# proportions, surfaced explicitly in the prompt so the LLM scores accordingly.

_CULTURE_DIGITAL_DEPTS = {
    "AI & Digital Transformation",
    "Information & Communication Technology (ICT)",
    "Management Information System (MIS)",
    "ERP - SAP",
}
_CULTURE_FIELD_DEPTS = {
    "Sales", "Distribution", "Field Force", "Delivery", "Transport",
    "Institutional Sales",
}
_CULTURE_FACTORY_DEPTS = {
    "Production", "Engineering", "Quality Assurance Department (QAD)",
    "Plastic Production", "Mechanical",
}
_CULTURE_FINANCE_DEPTS = {
    "Finance and Accounts", "Internal Audit", "External Audit",
    "VAT / VAT & Delivery", "Market Audit",
}


def build_culture_block(department: str | None) -> str:
    """Return a culture-fit guide whose pillar weights are calibrated to the
    department's nature.

    All five pillars remain identical; only their relative weights shift.
    The prompt explicitly states the weights so the LLM can score accordingly.
    """
    dept = (department or "").strip()

    if dept in _CULTURE_DIGITAL_DEPTS:
        w_fmcg, w_stability, w_ethic, w_collab, w_digital = 20, 20, 20, 10, 30
        dept_note = (
            "For Digital/Tech roles: the digital transformation pillar is ELEVATED (30%). "
            "Candidates from pure tech backgrounds (no FMCG) are acceptable IF they show "
            "strong digital execution evidence. Weight FMCG experience lower for tech specialists."
        )
    elif dept in _CULTURE_FIELD_DEPTS:
        w_fmcg, w_stability, w_ethic, w_collab, w_digital = 45, 25, 20, 5, 5
        dept_note = (
            "For Field/Sales roles: FMCG and Bangladesh market experience are paramount (45%). "
            "District/upazilla-level channel knowledge is a strong positive. "
            "Digital tool use (CRM, order apps) is a mild bonus but not required."
        )
    elif dept in _CULTURE_FACTORY_DEPTS:
        w_fmcg, w_stability, w_ethic, w_collab, w_digital = 45, 25, 20, 5, 5
        dept_note = (
            "For Factory/Production roles: hands-on manufacturing floor experience is paramount. "
            "Multi-shift management and high-volume line experience are critical signals."
        )
    elif dept in _CULTURE_FINANCE_DEPTS:
        w_fmcg, w_stability, w_ethic, w_collab, w_digital = 25, 30, 25, 10, 10
        dept_note = (
            "For Finance/Audit roles: stability and professional work ethic are highest priority. "
            "CA/ACCA qualification and clean audit track record are strong culture signals. "
            "SAP/ERP exposure is valued given Olympic's digital transformation agenda."
        )
    else:
        # Default cluster (Brand & Marketing, HR, Supply Chain, Admin, etc.)
        w_fmcg, w_stability, w_ethic, w_collab, w_digital = 35, 25, 20, 10, 10
        dept_note = (
            "FMCG background, stability, and professional work ethic are the primary culture signals."
        )

    return f"""
--- OLYMPIC INDUSTRIES CULTURE FIT GUIDE ---

Olympic Industries PLC is Bangladesh's largest FMCG manufacturer (biscuits, confectionery,
chips, bread, cakes). It operates large-scale manufacturing plants, a nationwide
distribution network, and is in active digital transformation.

DEPARTMENT: {dept or "General"}

PILLAR WEIGHTS FOR THIS DEPARTMENT:
  1. FMCG / Manufacturing Orientation  : {w_fmcg}%
  2. Stability & Commitment            : {w_stability}%
  3. Professional Work Ethic           : {w_ethic}%
  4. Collaborative & Hierarchical      : {w_collab}%
  5. Digital Transformation Alignment  : {w_digital}%

DEPARTMENT CALIBRATION NOTE: {dept_note}

1. FMCG / MANUFACTURING ORIENTATION (weight: {w_fmcg}%)
   Strong fit: FMCG employer (Pran, ACI, Nestle, Unilever, Akij, Bashundhara, Square, RFL,
               Ispahani, Meghna, Bombay Sweets, Partex, Globe Pharma, Abul Khair),
               factory/plant-floor or field operations experience,
               Bangladesh market knowledge (distribution, retail, trade),
               high-volume fast-paced operations background.
   Weak fit:   Only software/tech companies with no manufacturing context (for non-tech roles),
               only service industry (banking, telecom) for operational roles.

2. STABILITY & COMMITMENT (weight: {w_stability}%)
   Strong fit: 3+ years at any single employer, progressive promotions within same company,
               career trajectory shows increasing responsibility.
   Weak fit:   More than 3 jobs in 5 years without clear reason (contract/project roles excused),
               consistent lateral moves with no progression,
               employment gaps >6 months without explanation.

3. PROFESSIONAL WORK ETHIC & DISCIPLINE (weight: {w_ethic}%)
   Strong fit: Achievements described with numbers/KPIs, certifications and continuous learning,
               involvement in process improvement or cost-saving initiatives.
   Weak fit:   Vague job descriptions with no measurable output,
               no evidence of training or upskilling in 5+ years.

4. COLLABORATIVE & HIERARCHICAL CULTURE (weight: {w_collab}%)
   Olympic has a structured hierarchy (Executive > Sr. Executive > Manager > AGM > DGM > GM > Director).
   Strong fit: Evidence of working in structured corporate/factory environments,
               cross-functional project participation, reporting to board/senior management.
   Weak fit:   Only startup/unstructured environments with no corporate structure exposure.

5. ALIGNMENT WITH OLYMPIC'S DIGITAL TRANSFORMATION AGENDA (weight: {w_digital}%)
   Strong fit: ERP/SAP adoption, BI tool use (Power BI, Tableau), automation projects,
               data-driven decision-making evidence, AI/ML exposure.
   Weak fit:   Purely manual/paper-based operations with no digital exposure (mild negative).

FINAL CALIBRATION:
  85-100 : Exceptional fit -- FMCG background, stable tenure, quantified outcomes
  65-84  : Good fit -- relevant industry, some stability, generally aligns
  45-64  : Partial fit -- transferable skills but mismatched industry or instability
  25-44  : Weak fit -- significant mismatch in industry, culture, or career pattern
  0-24   : Poor fit -- clear misalignment, high-risk hire

--- END CULTURE FIT GUIDE ---
"""


# Legacy constant retained for backwards-compat. New code uses build_culture_block().
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

# ── Employment Date Parsing Utilities ─────────────────────────────────────────
#
# Properly parses date ranges from the Employment History section of BDJobs
# profiles.  Handles "Present", "Continuing", "Till now", "Current", "Till Date",
# "Ongoing" as today's date.

_PRESENT_TOKENS = {
    "present", "continuing", "continued", "till now", "till date",
    "current", "currently", "ongoing", "now", "to date", "today",
    "running", "till today",
}

_MONTH_MAP = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6,
    "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

# Matches date ranges like "(11 Nov 2024 - Continuing)" or "(1 Jan 2021 - 30 Jun 2024)"
_RE_DATE_RANGE = re.compile(
    r"\(\s*"
    r"(\d{1,2}\s+\w+\s+\d{4})"          # start date: "11 Nov 2024"
    r"\s*[-–—]\s*"                         # separator
    r"([^)]+)"                             # end date or "Continuing"/"Present"
    r"\s*\)",
    re.IGNORECASE,
)


def _parse_date_token(token: str) -> "datetime.date | None":
    """Parse a date string like '11 Nov 2024' or 'Continuing' into a date."""
    from datetime import date
    token = token.strip()
    if token.lower() in _PRESENT_TOKENS:
        return date.today()
    # Try "DD Month YYYY" format
    m = re.match(r"(\d{1,2})\s+(\w+)\s+(\d{4})", token)
    if m:
        day, month_str, year = int(m.group(1)), m.group(2).lower(), int(m.group(3))
        month = _MONTH_MAP.get(month_str[:3])
        if month:
            try:
                return date(year, month, min(day, 28))
            except ValueError:
                return date(year, month, 1)
    # Try "Month YYYY" format
    m = re.match(r"(\w+)\s+(\d{4})", token)
    if m:
        month_str, year = m.group(1).lower(), int(m.group(2))
        month = _MONTH_MAP.get(month_str[:3])
        if month:
            return date(year, month, 1)
    # Try "YYYY" only
    m = re.match(r"(\d{4})$", token)
    if m:
        return date(int(m.group(1)), 1, 1)
    return None


def _extract_employment_section(txt: str) -> str:
    """Extract just the Employment History section from profile text."""
    lower = txt.lower()
    start_markers = ["employment history:", "work experience:", "professional experience:"]
    end_markers = ["academic qualification:", "education:", "training summary:",
                   "professional qualification:", "career and application",
                   "skill:", "language proficiency:", "personal details:",
                   "extra curricular", "reference"]
    start_idx = -1
    for marker in start_markers:
        idx = lower.find(marker)
        if idx != -1:
            start_idx = idx
            break
    if start_idx == -1:
        return txt  # fallback to full text

    section = txt[start_idx:]
    end_idx = len(section)
    for marker in end_markers:
        idx = section.lower().find(marker, 50)  # skip past the header
        if idx != -1 and idx < end_idx:
            end_idx = idx
    return section[:end_idx]


def parse_employment_periods(profile_text: str) -> list[tuple]:
    """Parse employment date ranges from the Employment History section.
    Returns a sorted list of (start_date, end_date) tuples."""
    from datetime import date
    emp_section = _extract_employment_section(profile_text)
    periods = []
    for m in _RE_DATE_RANGE.finditer(emp_section):
        start_str, end_str = m.group(1), m.group(2)
        start_dt = _parse_date_token(start_str)
        end_dt = _parse_date_token(end_str)
        if start_dt and end_dt and start_dt <= end_dt:
            periods.append((start_dt, end_dt))
    # Sort by start date
    periods.sort(key=lambda p: p[0])
    return periods


def compute_experience_years_from_dates(profile_text: str) -> float:
    """Compute total work experience in years from parsed employment periods.
    Overlapping periods are merged to avoid double-counting."""
    periods = parse_employment_periods(profile_text)
    if not periods:
        return 0.0
    # Merge overlapping periods
    merged = [periods[0]]
    for start, end in periods[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    total_days = sum((end - start).days for start, end in merged)
    return round(total_days / 365.25, 1)


def detect_employment_gaps(profile_text: str, min_gap_months: int = 6) -> list[str]:
    """Detect genuine employment gaps by parsing actual date ranges.
    Only flags gaps >= min_gap_months between consecutive job periods."""
    periods = parse_employment_periods(profile_text)
    if len(periods) < 2:
        return []
    # Merge overlapping periods first
    merged = [periods[0]]
    for start, end in periods[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    gaps = []
    for i in range(len(merged) - 1):
        gap_start = merged[i][1]
        gap_end = merged[i + 1][0]
        gap_days = (gap_end - gap_start).days
        gap_months = gap_days / 30.44
        if gap_months >= min_gap_months:
            gap_years = round(gap_months / 12, 1)
            start_str = gap_start.strftime("%b %Y")
            end_str = gap_end.strftime("%b %Y")
            gaps.append(f"Employment gap ~{gap_years}yr ({start_str} → {end_str})")
    return gaps


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

    # 3. Frequent job changes — count distinct employment periods
    emp_periods = parse_employment_periods(txt)
    if len(emp_periods) >= 4:
        flags.append(f"{len(emp_periods)} employers listed — possible frequent job changes")
    elif not emp_periods:
        # Fallback: count from header line patterns
        role_blocks = re.findall(r"##\s*\d{4}\s*[-–]\s*(?:\d{4}|Present)", txt, re.IGNORECASE)
        if not role_blocks:
            role_blocks = re.findall(r"\b(19|20)\d{2}\s*[-–]\s*(?:(?:19|20)\d{2}|Present)\b", txt)
        if len(role_blocks) >= 4:
            flags.append(f"{len(role_blocks)} employers listed — possible frequent job changes")

    # 4. Employment-gap heuristic — parse actual date ranges and find real gaps
    gap_flags = detect_employment_gaps(txt, min_gap_months=6)
    flags.extend(gap_flags)

    # 5. No FMCG exposure — negative keyword check
    fmcg_kw = (
        "fmcg", "olympic", "pran", "nestle", "unilever", "akij",
        "bashundhara", "square", "rfl", "ispahani", "meghna", "bombay sweets",
        "partex", "abul khair", "globe pharma", "marico", "reckitt",
        "procter", "danone", "bata", "beximco consumer",
    )
    if not any(k in lower for k in fmcg_kw):
        flags.append("No explicit FMCG employer mentioned")

    # 6. SCORE-06: No quantified achievements -- pure narrative CV.
    _RE_NUMBER = re.compile(
        r"\b\d+[\.,]?\d*\s*(?:%|percent|crore|lakh|bdt|usd|taka|tk)\b",
        re.IGNORECASE,
    )
    if not _RE_NUMBER.search(txt):
        flags.append("No quantified achievements (no % / BDT / numbers found)")

    # 7. SCORE-06: Very short resume -- likely incomplete.
    if len(txt.strip()) < 600:
        flags.append("Very short profile text — resume may be incomplete")

    return flags[:6]   # SCORE-06: cap raised from 5 to 6 to surface the new signals.


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

# NOTE: the progress lock is created inside main_async() as `log_lock = asyncio.Lock()`
# and passed explicitly to write_progress_async(). Do NOT add a module-level placeholder
# here -- assigning the asyncio.Lock CLASS (rather than an instance) silently breaks
# any caller that uses it as a context manager.

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
    # SCORE-03: department-aware culture-fit weights (was OLYMPIC_CULTURE_FIT_GUIDE).
    culture_block     = build_culture_block(department)
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

# ── Robust response parsing & error taxonomy ──────────────────────────────────
# These helpers eliminate the 54% failure rate by (a) extracting JSON from
# truncated / noisy responses instead of crashing, (b) filling missing fields
# with safe defaults, (c) providing a stripped-down fallback prompt for
# resumes that consistently fail the full scoring framework.

SUGGESTED_FAST_MODEL = "qwen2.5:7b"  # non-reasoning, 2-3x faster, no thinking block


def _safe_parse_ollama_response(content: str) -> dict:
    """Parse an Ollama response body into a scores dict.  Defensive against:
    * empty / whitespace-only string  → returns default dict
    * JSON embedded inside markdown   → strips fences
    * truncated / partial JSON        → regex-extracts the object body
    * missing required fields           → fills with 0 / [] / ""
    """
    if not content or not content.strip():
        return _default_scores_dict()

    # Strip markdown fences and thinking blocks
    raw = re.sub(r"```json|```", "", content).strip()
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    raw = raw.strip()

    # Fast path: clean JSON
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return _fill_missing_fields(parsed)
    except (json.JSONDecodeError, ValueError):
        pass

    # Slow path: regex-extract a JSON object from the mess.
    # Truncated qwen3 output often ends with `"reasoning": "some text...` (no closing brace).
    m = re.search(r"\{.*\"skills_score\".*\}", raw, re.DOTALL)
    if m:
        try:
            parsed = json.loads(m.group(0))
            if isinstance(parsed, dict):
                return _fill_missing_fields(parsed)
        except (json.JSONDecodeError, ValueError):
            pass

    # Last resort: look for ANY JSON object, even without skills_score
    m = re.search(r"(\{.*\})", raw, re.DOTALL)
    if m:
        try:
            parsed = json.loads(m.group(1))
            if isinstance(parsed, dict):
                return _fill_missing_fields(parsed)
        except (json.JSONDecodeError, ValueError):
            pass

    # Nothing salvageable — return defaults so the resume is not dropped
    return _default_scores_dict()


def _default_scores_dict() -> dict:
    """Safe defaults for a candidate when the LLM returns nothing parseable."""
    return {
        "skills_score": 0,
        "experience_score": 0,
        "leadership_score": 0,
        "education_score": 0,
        "culture_fit_score": 0,
        "edu_tier_score": 0,
        "edu_degree_score": 0,
        "edu_gpa_score": 0,
        "experience_years": 0.0,
        "recommendation": "Maybe",
        "strengths": [],
        "gaps": ["Could not evaluate — model returned empty or malformed output"],
        "risk_flags": ["Scoring failed — candidate manually reviewed"],
        "reasoning": "The scoring model produced no valid JSON. This can happen when the resume text is extremely long, the model context was exhausted, or the model is under heavy load. Scores default to 0 and the candidate is flagged for manual review.",
    }


def _fill_missing_fields(parsed: dict) -> dict:
    """Ensure every expected key exists with a safe default."""
    defaults = _default_scores_dict()
    out = dict(defaults)
    for k in defaults:
        if k in parsed:
            out[k] = parsed[k]
    # Coerce types
    for k in ["skills_score", "experience_score", "leadership_score",
              "education_score", "culture_fit_score",
              "edu_tier_score", "edu_degree_score", "edu_gpa_score"]:
        try:
            out[k] = max(0, min(100, int(str(out[k]).replace("%", "").replace(" ", "").strip())))
        except (ValueError, TypeError):
            out[k] = 0
    try:
        out["experience_years"] = float(str(out.get("experience_years", 0)).replace("%", "").strip())
    except (ValueError, TypeError):
        out["experience_years"] = 0.0
    if out.get("recommendation") not in ("Shortlist", "Maybe", "Reject"):
        out["recommendation"] = "Maybe"
    for list_key in ("strengths", "gaps", "risk_flags"):
        v = out.get(list_key)
        if isinstance(v, str):
            out[list_key] = [v]
        elif not isinstance(v, list):
            out[list_key] = list(v) if v else []
        out[list_key] = out[list_key][:5]
    out["reasoning"] = str(out.get("reasoning", ""))[:500]

    # Sanity check: if all 5 dimension scores are identical and non-zero,
    # this is likely a degenerate LLM output — flag it
    dim_scores = [out.get(k, 0) for k in ["skills_score", "experience_score",
                  "leadership_score", "education_score", "culture_fit_score"]]
    if len(set(dim_scores)) == 1 and dim_scores[0] > 0:
        out["risk_flags"] = out.get("risk_flags", []) + ["Suspect scoring: all dimensions identical — may need re-ranking"]

    return out


def build_fallback_prompt(profile_text: str, job_label: str) -> str:
    """Stripped-down prompt for the fallback path (no PDF, no JD, no
    education sub-scores, no strengths/gaps — just the 5 dimension scores).
    This is used when the full prompt consistently fails (usually because
    the combined text exceeds the model's context window).
    """
    trunc = smart_truncate(profile_text, 4000)
    return (
        "Score this candidate on a 0-100 scale for 5 dimensions ONLY. "
        "Return valid JSON with these exact keys and no other text:\n\n"
        "{\n"
        '  "skills_score": int,\n'
        '  "experience_score": int,\n'
        '  "leadership_score": int,\n'
        '  "education_score": int,\n'
        '  "culture_fit_score": int,\n'
        '  "experience_years": float,\n'
        '  "recommendation": "Shortlist" | "Maybe" | "Reject",\n'
        '  "reasoning": "string"\n'
        "}\n\n"
        "Candidate profile (truncated):\n"
        f"{trunc}\n\n"
        f"Job: {job_label}"
    )


def classify_error(err_msg: str, fallback_attempted: bool = False) -> str:
    """Map a free-form error message to a structured taxonomy.
    This replaces the current 191× "Expecting value: line 1 column 1 (char 0)"
    with actionable categories: model_truncation, json_parse, timeout, etc."""
    m = err_msg.lower()
    if "expecting value" in m or "json" in m or "decode" in m:
        if "column 1" in m or "char 0" in m:
            return "model_truncation"
        return "json_parse"
    if "timeout" in m or "timed out" in m or "clientconnector" in m:
        return "timeout"
    if "connection" in m or "refused" in m or "reset" in m:
        return "connection"
    if "rate" in m or "429" in m or "too many" in m:
        return "rate_limit"
    if "pdf" in m or "extract" in m or "corrupt" in m or "empty" in m:
        return "parse_error"
    if "unicode" in m or "utf-8" in m or "codec" in m:
        return "encoding"
    if "key" in m or "missing" in m or "validation" in m:
        return "schema_missing"
    if fallback_attempted:
        return "fallback_failed"
    return "unknown"


def normalize_verdict(verdict: str | None) -> str:
    """Collapse free-text LLM outputs to canonical ternary recommendation.
    
    LLMs may return variations like 'Strong Hire', 'Consider', 'Pass',
    'Yes', 'No', 'Maybe - interview', etc. We normalize these to the
    three canonical values expected by the database and UI.
    
    Returns:
        'Shortlist' | 'Maybe' | 'Reject'
    """
    if not verdict:
        return "Maybe"
    
    v = str(verdict).lower().strip()
    
    # Check for explicit multi-word phrases first (more specific)
    if 'not recommended' in v or 'do not hire' in v:
        return "Reject"
    if 'strongly recommend' in v or 'highly recommend' in v:
        return "Shortlist"
    
    # Map positive indicators to Shortlist
    positive = ['shortlist', 'hire', 'yes', 'strong', 'recommend', 'accept', 
                'top', 'excellent', 'good fit', 'proceed', 'advance', 'select']
    if any(p in v for p in positive):
        return "Shortlist"
    
    # Map negative indicators to Reject
    negative = ['reject', 'pass', 'decline', 'poor', 'weak',
                'skip', 'drop', 'unsuitable']
    # Also check for standalone 'no' (not part of 'not')
    if any(n in v for n in negative):
        return "Reject"
    # Check for standalone 'no' word
    if v == 'no' or ' no ' in v or v.startswith('no '):
        return "Reject"
    # Check for 'not ' at start (not recommended handled above)
    if v.startswith('not '):
        return "Reject"
    
    # Everything else maps to Maybe (including 'maybe', 'consider', 'neutral', etc.)
    return "Maybe"


async def call_ollama_async(
    session: aiohttp.ClientSession,
    profile_text: str,
    pdf_text: str,
    job_label: str,
    jd_text: str,
    job_config: dict | None = None,
    retries: int = 3,
    use_fallback: bool = False,
) -> dict:
    """Call Ollama with retry + exponential backoff.

    If use_fallback=True, sends a drastically shorter prompt that drops
    the PDF text, education sub-scores, and strengths/gaps — only the 5
    dimension scores + recommendation.  Used as a last resort when the
    full prompt repeatedly fails (usually context-window overflow).
    """
    if use_fallback:
        user_content = build_fallback_prompt(profile_text, job_label)
    else:
        prompt = build_prompt(profile_text, pdf_text, job_label, jd_text, job_config)
        user_content = prompt
        if OLLAMA_MODEL.lower().startswith("qwen3"):
            user_content = "/no_think\n" + prompt

    payload = {
        "model":  OLLAMA_MODEL,
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0.1,
            "top_p":       0.9,
            "seed":        42,
            "num_ctx":     int(os.environ.get("OLLAMA_NUM_CTX",     "8192")),
            # PERFORMANCE FIX: raised from 1024 → 2048.
            # qwen3:8b emits a thinking block (300-800 tokens) before the JSON.
            # With num_predict=1024 the JSON was truncated mid-object, producing
            # 191 "Expecting value: line 1 column 1 (char 0)" errors (empty body)
            # and 66 KeyError 'skills_score' errors (partial JSON missing fields).
            # Each truncation triggered a retry, doubling per-resume wall time.
            # 2048 gives ~1.2 k tokens of headroom for the JSON payload after
            # reasoning, eliminating most truncation failures.
            "num_predict": int(os.environ.get("OLLAMA_NUM_PREDICT", "2048")),
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
                if resp.status == 504:
                    raise aiohttp.ClientResponseError(
                        resp.request_info, resp.history,
                        status=504, message="Gateway Timeout — VM Ollama unreachable via Tailscale funnel. Check VM power, Tailscale status, and ollama serve."
                    )
                resp.raise_for_status()
                body = await resp.json()
            content = body["message"]["content"]
            parsed = _safe_parse_ollama_response(content)
            # Verify we got at least one non-zero score or a non-empty reasoning
            # to avoid accepting pure-default placeholders when the model
            # genuinely returned nothing useful.
            has_data = (
                any(parsed.get(k, 0) > 0 for k in [
                    "skills_score", "experience_score", "leadership_score",
                    "education_score", "culture_fit_score"])
                or (parsed.get("reasoning") or "").strip()
            )
            if has_data:
                return parsed
            # If all scores are 0 and reasoning is the default, treat as a
            # failed attempt (model may have returned empty thinking block)
            last_err = ValueError("Ollama returned empty/default content")
            if attempt == retries - 1:
                raise last_err
            await asyncio.sleep(2 ** attempt)
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError, ValueError) as e:
            last_err = e
            if attempt == retries - 1:
                raise
            # Longer backoff for gateway timeouts (VM may need time to wake up)
            delay = 5 * (2 ** attempt) if "504" in str(e) or "Gateway Timeout" in str(e) else 2 ** attempt
            await asyncio.sleep(delay)
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


def _score_to_recommendation(overall_score: int) -> str:
    """Map computed overall_score to canonical ternary recommendation.

    This ensures consistency across all candidates — the LLM's subjective
    verdict is overridden by the objective weighted score.  Prevents the
    model from being overly conservative (e.g. 0 Shortlist across 200+
    ranked candidates because it never outputs the exact word "Shortlist").
    """
    if overall_score >= 70:
        return "Shortlist"
    elif overall_score >= 50:
        return "Maybe"
    else:
        return "Reject"


def compute_education_score(scores: dict) -> int:
    """Compute education_score deterministically from the three sub-scores.

    Formula (matches the EDUCATION SCORING FORMULA injected into the LLM prompt):
        education_score = round(tier * 0.50 + degree * 0.30 + gpa * 0.20)

    BUG-03 fix: previously education_score was fully LLM-generated and could
    drift from its own sub-scores (LLM hallucination). Now it is recomputed
    server-side from edu_tier_score / edu_degree_score / edu_gpa_score.

    Falls back to the LLM's education_score if all three sub-scores are zero
    (i.e. the LLM did not emit them) so we never zero a legitimate score.
    """
    tier   = int(scores.get("edu_tier_score",   0) or 0)
    degree = int(scores.get("edu_degree_score", 0) or 0)
    gpa    = int(scores.get("edu_gpa_score",    0) or 0)

    if tier == 0 and degree == 0 and gpa == 0:
        return max(0, min(100, int(scores.get("education_score", 0) or 0)))

    computed = round(tier * 0.50 + degree * 0.30 + gpa * 0.20)
    return max(0, min(100, int(computed)))


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
    """, (job_label, apply_id, name, txt_path, error_msg[:1000]))


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

    # ── PREPARE: read files outside semaphore so GPU never waits on I/O ───
    try:
        def _read_txt():
            with open(txt_path, encoding="utf-8", errors="replace") as f:
                return f.read()
        profile_text = await asyncio.to_thread(_read_txt)

        _profile_stripped = profile_text.strip() if profile_text else ""
        if len(_profile_stripped) < 150:
            raise ValueError(
                f"EMPTY_PROFILE: Profile text is only {len(_profile_stripped)} chars "
                f"(minimum 150 required). "
                f"The resume text file may be empty, corrupted, or from a scanned PDF. "
                f"File: {txt_path}"
            )
        profile_text = _profile_stripped   # use stripped version

        pdf_text = ""
        pdf_text_chars = 0
        if pdf_path and os.path.exists(pdf_path):
            pdf_text = await asyncio.to_thread(extract_pdf_text, pdf_path)
            pdf_text_chars = len(pdf_text) if pdf_text else 0
    except Exception as e:
        err_msg = str(e)
        err_type = classify_error(err_msg, fallback_attempted=False)
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
            "error_type": err_type,
            "fallback": False,
        })
        tqdm.write(f"  ERR {apply_id} | {name[:30]} | {err_type} | {err_msg[:60]}")
        return apply_id, name, err_msg

    # ── OLLAMA: semaphore only guards the GPU call ─────────────────────────
    try:
        async with sem:
            raw = await call_ollama_async(
                session, profile_text, pdf_text, job, jd_text, job_config,
            )
    except Exception as e:
        err_msg = str(e)
        err_type = classify_error(err_msg, fallback_attempted=False)
        fallback_used = False

        # Fallback path
        if "timeout" not in err_msg.lower() and "connection" not in err_msg.lower():
            try:
                tqdm.write(f"  RTRY {apply_id} | {name[:30]} | fallback prompt")
                async with sem:
                    raw_fb = await call_ollama_async(
                        session, profile_text, "", job, "", job_config,
                        retries=2, use_fallback=True,
                    )
                scores = validate_score(raw_fb)
                scores["recommendation"] = normalize_verdict(scores.get("recommendation"))
                scores["education_score"] = compute_education_score(scores)
                scores["overall_score"]   = compute_overall_score(scores, job_config)
                scores["recommendation"]  = _score_to_recommendation(scores["overall_score"])
                async with db_lock:
                    def _write_fb():
                        with conn.cursor() as cur:
                            upsert_candidate(
                                cur, job, apply_id, name, txt_path,
                                pdf_path, pdf_text_chars, jd_used_label, scores,
                            )
                        state["pending"] += 1
                        if state["pending"] >= COMMIT_BATCH_SIZE:
                            conn.commit()
                            state["pending"] = 0
                    await asyncio.to_thread(_write_fb)
                    if state.get("force_commit"):
                        conn.commit()
                        state["pending"] = 0
                await write_progress_async(log_lock, log_path, {
                    "event":          "ok_fallback",
                    "apply_id":       apply_id,
                    "name":           name,
                    "score":          scores["overall_score"],
                    "recommendation": scores["recommendation"],
                })
                tqdm.write(f"  OK* {apply_id} | {name[:30]} | {scores['overall_score']} | fallback")
                return apply_id, name, None
            except Exception as e2:
                err_msg = str(e2)
                err_type = classify_error(err_msg, fallback_attempted=True)
                fallback_used = True

        # Permanent failure
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
            "error_type": err_type,
            "fallback": fallback_used,
        })
        tqdm.write(f"  ERR {apply_id} | {name[:30]} | {err_type} | {err_msg[:60]}")
        return apply_id, name, err_msg

    # ── POST-PROCESS: validation & DB write outside semaphore ─────────────
    scores = validate_score(raw)
    scores["recommendation"] = normalize_verdict(scores.get("recommendation"))
    scores["education_score"] = compute_education_score(scores)
    scores["overall_score"]   = compute_overall_score(scores, job_config)
    scores["recommendation"]  = _score_to_recommendation(scores["overall_score"])

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
        if state.get("force_commit"):
            conn.commit()
            state["pending"] = 0

    await write_progress_async(log_lock, log_path, {
        "event":          "ok",
        "apply_id":       apply_id,
        "name":           name,
        "score":          scores["overall_score"],
        "recommendation": scores["recommendation"],
    })
    tqdm.write(f"  OK  {apply_id} | {name[:30]} | {scores['overall_score']} | {scores['recommendation']}")
    return apply_id, name, None


def generate_error_report(
    job_label: str,
    errors: list[tuple[str, str, str]],
    total_files: int,
    skipped: int,
    ranked_ok: int,
    log_path: str,
) -> str:
    """Generate a structured JSON error report after a ranking run.

    The report classifies each failed resume by error taxonomy, counts
    failures by category, and produces a remediation plan so HR can
    decide which candidates are worth manual review vs. being permanently
    unrankable.
    """
    error_types: dict[str, list[dict]] = {}
    for apply_id, name, err_msg in errors:
        err_type = classify_error(err_msg, fallback_attempted="fallback" in err_msg.lower())
        entry = {
            "apply_id": apply_id,
            "name": name,
            "error": err_msg[:250],
            "error_type": err_type,
        }
        error_types.setdefault(err_type, []).append(entry)

    # Build per-type remediation actions
    remediation = {
        "model_truncation": {
            "action": "Re-run with larger num_predict (e.g. OLLAMA_NUM_PREDICT=4096) or switch to a non-reasoning model (qwen2.5:7b). The resume likely exceeds context window.",
            "manual_review_priority": "HIGH",
        },
        "json_parse": {
            "action": "Re-run once with the updated code (regex JSON extraction now handles partial output). If still failing, manual review.",
            "manual_review_priority": "MEDIUM",
        },
        "timeout": {
            "action": "Re-run with fewer workers or increase OLLAMA_TIMEOUT_SECS. The Ollama GPU queue is saturated.",
            "manual_review_priority": "LOW",
        },
        "connection": {
            "action": "Verify Ollama is running and reachable. Re-run when service is healthy.",
            "manual_review_priority": "LOW",
        },
        "rate_limit": {
            "action": "Reduce --workers or upgrade Ollama hardware. Retry after a short cooldown.",
            "manual_review_priority": "LOW",
        },
        "parse_error": {
            "action": "Resume PDF is corrupt or unreadable. Try manual extraction or ask candidate to re-submit.",
            "manual_review_priority": "MEDIUM",
        },
        "encoding": {
            "action": "Resume text has encoding issues. Try converting to UTF-8 or manual review.",
            "manual_review_priority": "MEDIUM",
        },
        "schema_missing": {
            "action": "Re-run with the updated code (missing keys now filled with safe defaults).",
            "manual_review_priority": "LOW",
        },
        "fallback_failed": {
            "action": "Candidate profile is too large even for the fallback prompt. Consider manual review or splitting the profile.",
            "manual_review_priority": "HIGH",
        },
        "unknown": {
            "action": "Investigate the specific error message. If persistent, escalate to engineering.",
            "manual_review_priority": "MEDIUM",
        },
    }

    summary = {
        "job_label": job_label,
        "generated_at": datetime.datetime.now().isoformat(),
        "total_resumes": total_files,
        "skipped_already_ranked": skipped,
        "ranked_successfully": ranked_ok,
        "failed": len(errors),
        "failure_rate_pct": round(len(errors) / max(total_files, 1) * 100, 2),
        "error_breakdown": {
            k: {
                "count": len(v),
                "examples": v[:5],
                "remediation": remediation.get(k, remediation["unknown"]),
            }
            for k, v in sorted(error_types.items(), key=lambda x: -len(x[1]))
        },
        "all_failed": error_types,
    }

    report_path = os.path.join(
        os.path.dirname(log_path),
        f"_error_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
    )
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"[Report] Error report written to: {report_path}")
    return report_path


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

    # PERFORMANCE HINT: if qwen3 is loaded, suggest switching to a non-reasoning
    # model for 2-3x throughput. The reasoning block in qwen3:8b consumes
    # 300-800 tokens of the num_predict budget before emitting JSON, which
    # is the root cause of most truncation failures.
    if "qwen3" in OLLAMA_MODEL.lower():
        print(f"\n[MODEL] Current model is {OLLAMA_MODEL}.")
        print(f"[MODEL] Recommendation: switch to {SUGGESTED_FAST_MODEL} for 2-3x speed")
        print(f"[MODEL] and fewer truncation errors (no reasoning/thinking block).")
        print(f"[MODEL] Run:  ollama pull {SUGGESTED_FAST_MODEL}")
        print(f"[MODEL] Then: set OLLAMA_MODEL={SUGGESTED_FAST_MODEL}  (or export in .env)\n")

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

    with conn.cursor() as cur:
        existing = get_existing_apply_ids(cur, args.job) if not args.rerank else set()

    # BUG-02 fix: get_existing_apply_ids returns numeric apply_ids (e.g. "12345678"),
    # but the txt files may be named "001_12345678.txt" -- the full stem would never
    # match, so every candidate was re-ranked on every run. Extract the trailing
    # numeric run the same way process_one() does.
    def _extract_apply_id_from_path(path: str) -> str:
        stem = os.path.splitext(os.path.basename(path))[0]
        m = re.search(r"(\d+)$", stem)
        return m.group(1) if m else stem

    # If --rerank-id is specified, only process that single candidate
    if getattr(args, "rerank_id", ""):
        target_id = args.rerank_id
        pending_files = [p for p in txt_files
                         if _extract_apply_id_from_path(p) == target_id]
        if not pending_files:
            print(f"[Error] Could not find profile text for apply_id={target_id}")
            return
        print(f"[Re-rank] Single candidate: {target_id}")
    else:
        pending_files = [p for p in txt_files
                         if _extract_apply_id_from_path(p) not in existing]
    skipped = len(txt_files) - len(pending_files)
    if skipped:
        print(f"[Skip] {skipped} already-ranked candidates (use --rerank to force).")

    # Write start event AFTER we know how many are actually pending
    await write_progress_async(log_lock, log_path, {
        "event":          "start",
        "job":            args.job,
        "total":          len(txt_files),
        "pending":        len(pending_files),
        "already_ranked": skipped,
        "rerank":         args.rerank,
        "workers":        args.workers,
    })

    sem = asyncio.Semaphore(args.workers)
    state = {"pending": 0}
    # Force immediate commit for single-candidate re-ranks
    if getattr(args, "rerank_id", ""):
        state["force_commit"] = True
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
        completed = 0
        for coro in tqdm_asyncio.as_completed(tasks, total=len(tasks), desc="Ranking"):
            apply_id, name, err = await coro
            completed += 1
            if err:
                errors.append((apply_id, name, err))
                # CIRCUIT BREAKER: if first 5 all fail with gateway/connection errors,
                # abort early — the VM is likely down or unreachable.
                if completed <= 5 and len(errors) == completed:
                    if all("504" in e or "Gateway" in e or "connection" in e.lower() or "Cannot connect" in e for _, _, e in errors):
                        print(f"\n[CIRCUIT BREAKER] First {completed} candidates all failed with gateway/connection errors.")
                        print(f"                  VM Ollama appears unreachable. Aborting remaining {len(tasks) - completed} candidates.")
                        print("                  Check: VM power, Tailscale status, ollama serve on the VM.")
                        # Cancel remaining tasks
                        for t in tasks:
                            if not t.done():
                                t.cancel()
                        break

    # Flush any remaining commits
    try:
        pending_count = state["pending"]
        if pending_count > 0:
            conn.commit()
            state["pending"] = 0
            print(f"[DB] Final commit: {pending_count} pending writes flushed.")
        else:
            print("[DB] No pending writes to flush.")
    except Exception as commit_err:
        print(f"[DB] ERROR: Final commit failed — {commit_err}")
        try:
            conn.rollback()
        except Exception:
            pass

    await write_progress_async(log_lock, log_path, {
        "event":          "done",
        "total":          len(txt_files),
        "pending":        len(pending_files),
        "already_ranked": skipped,
        "errors":         len(errors),
    })

    print(f"\nDone. Ranked: {len(pending_files) - len(errors)} | Skipped: {skipped} | Errors: {len(errors)}")
    if errors:
        for aid, nm, msg in errors[:20]:
            print(f"  {aid} | {nm} | {msg[:100]}")

    # ── Structured error report (JSON) ──────────────────────────────────────
    generate_error_report(
        job_label=args.job,
        errors=errors,
        total_files=len(txt_files),
        skipped=skipped,
        ranked_ok=len(pending_files) - len(errors),
        log_path=log_path,
    )

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

        # BUG-04 fix: rescale ONLY the five dimension scores; recompute
        # overall_score from the rescaled dimensions using the job's weights.
        # Previously overall_score was rescaled independently, which made it
        # inconsistent with the weighted formula -- a candidate's overall rank
        # could shift without any dimension shifting proportionally.
        per_dim_dimensions_only = list(zip(*[
            (r[2], r[3], r[4], r[5], r[6]) for r in rows  # skip r[1] (overall_raw)
        ]))
        rescaled_dims = [rescale(list(col)) for col in per_dim_dimensions_only]
        # Index map: 0=skills, 1=experience, 2=leadership, 3=education, 4=culture_fit

        # Load the job's weights so we can recompute overall_score consistently.
        with conn.cursor() as cur:
            cur.execute("""
                SELECT weight_skills, weight_exp, weight_edu,
                       weight_leadership, weight_culture
                  FROM jobs WHERE job_label = %s
            """, (job_label,))
            weight_row = cur.fetchone()

        job_config_norm: dict = {}
        if weight_row:
            for key, val in zip(
                ["weight_skills", "weight_exp", "weight_edu",
                 "weight_leadership", "weight_culture"],
                weight_row,
            ):
                if val is not None:
                    job_config_norm[key] = val

        # Write back.
        with conn.cursor() as cur:
            for idx, r in enumerate(rows):
                apply_id = r[0]
                dim_scores = {
                    "skills_score":      rescaled_dims[0][idx],
                    "experience_score":  rescaled_dims[1][idx],
                    "leadership_score":  rescaled_dims[2][idx],
                    "education_score":   rescaled_dims[3][idx],
                    "culture_fit_score": rescaled_dims[4][idx],
                }
                new_overall = compute_overall_score(dim_scores, job_config_norm)
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
                    new_overall,
                    dim_scores["skills_score"],
                    dim_scores["experience_score"],
                    dim_scores["leadership_score"],
                    dim_scores["education_score"],
                    dim_scores["culture_fit_score"],
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
    parser.add_argument("--rerank-id",      default="", help="Re-rank a single candidate by apply_id")
    parser.add_argument("--backfill-names", action="store_true", help="Fix Unknown names in DB without re-ranking")
    parser.add_argument("--normalise",      action="store_true",
                        help="After ranking, run a percentile-based rescaling pass (Part 7.3)")
    parser.add_argument("--normalise-only", action="store_true",
                        help="Run normalisation on already-ranked candidates only, skip ranking")
    parser.add_argument("--workers",        type=int, default=int(os.environ.get("RANKER_WORKERS", "2")),
                        help="Number of parallel Ollama workers (default: 2). Recommended: 2 for 8GB VRAM, 3-4 for 12GB+.")
    args = parser.parse_args()

    # If --rerank-id is provided, set rerank=True so it doesn't skip existing
    if args.rerank_id:
        args.rerank = True

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
