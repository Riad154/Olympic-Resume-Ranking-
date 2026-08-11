"""
bdjobs_features.py — Structured feature extraction for BDJobs "Online Talent
Search" CVs.

BDJobs profile PDFs always print sections in a fixed order. The ranking system
was misreading them (dropping experience totals, the language table, GPA/CGPA,
certifications, and most of the employment history), producing scores that
contradicted the source document.

This module parses a BDJobs CV by its canonical section order and returns a
flat feature dict that the scoring layer consumes. It is intentionally
dependency-free (stdlib only) so it can be unit-tested in isolation.

Implements the plan in fix_bdjobs_cv_extraction.md (Tasks 1-7).
"""

from __future__ import annotations

import html
import re

# ── Task 1: canonical BDJobs section order ───────────────────────────────────

# Order matters: each header acts as the terminator for the previous section.
BDJOBS_HEADERS = [
    "Job Title",
    "Career Objective",
    "Career Summary",
    "Special Qualification",
    "Employment History",
    "Academic Qualification",
    "Training Summary",
    "Professional Qualification",
    "Career and Application Information",
    "Skills",
    "Extra Curricular Activities",
    "Language Proficiency",
    "Personal Details",
    "Reference",  # matches "Reference (s):" and "Reference:"
]

# A header at line start, optional "(s)" suffix, optional trailing colon.
_HEADER_RE = re.compile(
    r"^\s*(" + "|".join(re.escape(h) for h in BDJOBS_HEADERS) + r")\s*\(?\s*s?\s*\)?\s*:",
    re.IGNORECASE | re.MULTILINE,
)


def _canonical(found: str) -> str:
    found_low = found.strip().lower()
    for h in BDJOBS_HEADERS:
        if h.lower() == found_low:
            return h
    if found_low.startswith("reference"):
        return "Reference"
    return found.strip()


def split_bdjobs_sections(raw_text: str) -> dict:
    """Return {canonical header -> raw section body}.

    Body runs from just after the header line to just before the next
    recognized header. Headers match case-insensitively with an optional
    trailing colon and "(s)" suffix.
    """
    if not raw_text:
        return {}
    text = html.unescape(raw_text)
    matches = list(_HEADER_RE.finditer(text))
    sections: dict = {}
    for i, m in enumerate(matches):
        header_key = _canonical(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        # If a header appears twice (rare), keep the longest body.
        if header_key not in sections or len(body) > len(sections[header_key]):
            sections[header_key] = body
    return sections


# ── Task 2: Employment History (total experience + jobs) ─────────────────────

_TOTAL_EXP_RE = re.compile(r"Total\s+year\s+of\s+experience\s*:\s*([\d.]+)\s*yrs?", re.IGNORECASE)
_JOB_HEADER_RE = re.compile(r"^\s*\d+\.\s*(.+?)\s*\(([\d.]+)\s*yrs?\)\s*$", re.MULTILINE)
_DATE_RANGE_RE = re.compile(r"\(([^)]*?)-\s*([^)]*?)\)")


def _first_company_line(seg: str) -> str | None:
    for line in seg.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("(") or s.lower().startswith("area of expertise"):
            continue
        return s
    return None


def parse_employment(emp_body: str) -> dict:
    """Extract total_years_experience and a list of jobs from the
    Employment History section body."""
    if not emp_body:
        return {"total_years_experience": None, "jobs": []}

    total = None
    m = _TOTAL_EXP_RE.search(emp_body)
    if m:
        try:
            total = float(m.group(1))
        except ValueError:
            total = None

    jobs = []
    job_marks = list(_JOB_HEADER_RE.finditer(emp_body))
    for i, jm in enumerate(job_marks):
        title = jm.group(1).strip()
        try:
            tenure = float(jm.group(2))
        except ValueError:
            tenure = 0.0
        seg_start = jm.end()
        seg_end = job_marks[i + 1].start() if i + 1 < len(job_marks) else len(emp_body)
        seg = emp_body[seg_start:seg_end]
        dm = _DATE_RANGE_RE.search(seg)
        start_date = dm.group(1).strip() if dm else None
        end_date = dm.group(2).strip() if dm else None
        company = _first_company_line(seg)
        jobs.append({
            "title": title,
            "tenure_years": tenure,
            "company": company,
            "start_date": start_date,
            "end_date": end_date,
            "body": seg.strip(),
        })

    # Fallback: if the "Total year" line was missing, sum the job tenures.
    if total is None and jobs:
        total = round(sum(j["tenure_years"] for j in jobs), 1)

    return {"total_years_experience": total, "jobs": jobs}


# ── Task 3: Academic Qualification (degree, GPA, university) ──────────────────

DEGREE_RANK = {
    "bachelor": 4, "bsc": 4, "b.sc": 4, "bba": 4, "b.a": 4, "beng": 4,
    "b.eng": 4, "llb": 4, "engineering (bsc)": 4,
    "master": 4, "msc": 4, "m.sc": 4, "mba": 4, "phd": 4, "doctor": 4,
    "diploma": 3,
    "hsc": 2, "a-level": 2, "higher secondary": 2,
    "ssc": 1, "o-level": 1, "secondary": 1,
}

# "X (out of Y)" allowing the figure to wrap across whitespace/newlines.
_CGPA_RE = re.compile(r"([\d.]+)\s*\(\s*out\s*of\s*([\d.]+)\s*\)", re.IGNORECASE)
_MARKS_RE = re.compile(r"Marks?\s*:?\s*([\d.]+)\s*%", re.IGNORECASE)
_UNI_RE = re.compile(
    r"([A-Z][A-Za-z.&'-]*(?:\s+[A-Za-z.&'-]+){0,4}\s+"
    r"(?:University|Institute|College|Collage|Polytechnic|School))",
)


def parse_academics(acad_body: str) -> dict:
    """Extract the highest degree level, a GPA figure, and a university name."""
    if not acad_body:
        return {"degree_level": 0, "degree_label": None,
                "gpa_value": None, "gpa_scale": None, "university_raw": None}

    # Collapse whitespace so wrapped table cells like "3.37 (out\nof 4)" reunite.
    flat = re.sub(r"\s+", " ", acad_body)

    rows = []  # (kind, value, scale)
    for m in _CGPA_RE.finditer(flat):
        try:
            rows.append(("cgpa", float(m.group(1)), float(m.group(2))))
        except ValueError:
            continue
    for m in _MARKS_RE.finditer(flat):
        try:
            rows.append(("marks", float(m.group(1)), None))
        except ValueError:
            continue

    body_low = flat.lower()
    degree_level = 0
    degree_label = None
    for key, rank in DEGREE_RANK.items():
        if key in body_low and rank > degree_level:
            degree_level = rank
            degree_label = key

    # Pick the GPA tied to the top degree: prefer a 4.0-scale CGPA.
    gpa_value = None
    gpa_scale = None
    for kind, val, scale in rows:
        if kind == "cgpa" and scale == 4.0:
            gpa_value, gpa_scale = val, scale
            break
    if gpa_value is None:
        for kind, val, scale in rows:
            if kind == "cgpa":
                gpa_value, gpa_scale = val, scale
                break
    if gpa_value is None and rows:
        # Fall back to a marks figure (BDJobs sometimes prints a CGPA as "3.7%").
        gpa_value = rows[0][1]
        gpa_scale = 4.0

    uni = None
    um = _UNI_RE.search(flat)
    if um:
        uni = um.group(1).strip()

    return {
        "degree_level": degree_level,
        "degree_label": degree_label,
        "gpa_value": gpa_value,
        "gpa_scale": gpa_scale,
        "university_raw": uni,
    }


def normalize_gpa(gpa_value, gpa_scale=None):
    """Normalize a GPA/marks figure to a 0-1 fraction.

    BDJobs sometimes prints a 4.0-scale CGPA as "Marks: 3.7%". When the figure
    is <= 4.0 it is a 4.0-scale CGPA, not a 4% score.
    """
    if gpa_value is None:
        return None
    try:
        v = float(gpa_value)
    except (ValueError, TypeError):
        return None
    if v <= 4.0:
        return round(v / 4.0, 4)
    if v <= 5.0:
        return round(v / 5.0, 4)
    if v <= 100.0:
        return round(v / 100.0, 4)
    return None


# ── Task 4: Language Proficiency (English evidence) ──────────────────────────

_LEVELS = {"high", "medium", "low"}


def parse_languages(lang_body: str) -> dict:
    langs = {}
    if lang_body:
        for line in lang_body.splitlines():
            parts = line.split()
            if len(parts) >= 4:
                name = parts[0].lower()
                levels = [p.lower() for p in parts[1:4]]
                if all(l in _LEVELS for l in levels):
                    langs[name] = {
                        "reading": levels[0],
                        "writing": levels[1],
                        "speaking": levels[2],
                    }
    english = langs.get("english")
    return {
        "languages": langs,
        "english": english,
        "has_english_evidence": english is not None,
    }


def english_proficiency_score(english: dict | None) -> int | None:
    """Map English reading/writing/speaking levels to a 0-100 score.
    High=3, Medium=2, Low=1, averaged, then scaled to 100."""
    if not english:
        return None
    rank = {"high": 3, "medium": 2, "low": 1}
    vals = [rank.get(english.get(k, "").lower()) for k in ("reading", "writing", "speaking")]
    vals = [v for v in vals if v]
    if not vals:
        return None
    return int(round(sum(vals) / len(vals) / 3 * 100))


# ── Task 5: certifications + leadership signals ──────────────────────────────

LEADERSHIP_TERMS = [
    "lead", "led", "manage", "managed", "managing", "supervise", "supervised",
    "team lead", "leadership", "coordinate", "coordinated", "mentor",
    "head of", "in charge", "oversee", "oversaw", "strategic planning",
]


def leadership_signal(sections: dict) -> dict:
    haystack = " ".join([
        sections.get("Career Objective", ""),
        sections.get("Career Summary", ""),
        sections.get("Special Qualification", ""),
        sections.get("Employment History", ""),
        sections.get("Extra Curricular Activities", ""),
    ]).lower()
    hits = sorted({t for t in LEADERSHIP_TERMS if re.search(r"\b" + re.escape(t) + r"\b", haystack)})
    return {"has_leadership_evidence": bool(hits), "leadership_terms": hits}


KNOWN_CERTS = [
    "CCNA", "CCNP", "CCIE", "MCSA", "MCSE", "MCITP", "MTCNA", "MTCRE",
    "MikroTik", "Fortinet", "FortiGate", "Cisco", "RHCE", "RHCSA",
    "Linux", "CompTIA", "ITIL", "PMP", "Six Sigma", "PRINCE2",
    "CISSP", "CISA", "CEH", "AWS Certified", "Azure", "CKA",
]


def parse_certifications(sections: dict, full_text: str = "") -> list:
    """Extract named certifications. Certifications can appear in several
    sections (and in employment duties), so the full CV text is scanned when
    provided, in addition to the credential-bearing sections."""
    blob = " ".join([
        sections.get("Special Qualification", ""),
        sections.get("Professional Qualification", ""),
        sections.get("Training Summary", ""),
        sections.get("Skills", ""),
        full_text or "",
    ])
    found = sorted({c for c in KNOWN_CERTS if re.search(r"\b" + re.escape(c) + r"\b", blob, re.IGNORECASE)})
    return found


# ── Task 7: assemble the scoring feature object ──────────────────────────────

def looks_like_bdjobs_cv(text: str) -> bool:
    """True if the text contains enough BDJobs section headers to parse."""
    if not text:
        return False
    if _TOTAL_EXP_RE.search(text):
        return True
    return len(_HEADER_RE.findall(text)) >= 3


def build_experience_detail(jobs: list) -> str:
    """Human-readable employment summary rebuilt from parsed jobs, showing
    every job with its real tenure (not a truncated 2-job metadata string)."""
    parts = []
    for j in jobs:
        title = j.get("title") or "Role"
        company = j.get("company") or ""
        yrs = j.get("tenure_years") or 0
        if company:
            parts.append(f"{title} @ {company} ({yrs:g} yr)")
        else:
            parts.append(f"{title} ({yrs:g} yr)")
    return "; ".join(parts)


def build_candidate_features(raw_text: str, uploaded_cv: bool = False) -> dict:
    """Parse a BDJobs CV into the structured feature object consumed by scoring."""
    sections = split_bdjobs_sections(raw_text)
    emp = parse_employment(sections.get("Employment History", ""))
    acad = parse_academics(sections.get("Academic Qualification", ""))
    langs = parse_languages(sections.get("Language Proficiency", ""))
    lead = leadership_signal(sections)
    certs = parse_certifications(sections, full_text=raw_text)

    return {
        "sections_found": sorted(sections.keys()),
        "total_years_experience": emp["total_years_experience"],
        "jobs": emp["jobs"],
        "experience_detail": build_experience_detail(emp["jobs"]),
        "degree_level": acad["degree_level"],
        "degree_label": acad["degree_label"],
        "gpa_value": acad["gpa_value"],
        "gpa_scale": acad["gpa_scale"],
        "gpa_normalized": normalize_gpa(acad["gpa_value"], acad["gpa_scale"]),
        "university": acad["university_raw"],
        "languages": langs["languages"],
        "english": langs["english"],
        "has_english_evidence": langs["has_english_evidence"],
        "english_score": english_proficiency_score(langs["english"]),
        "has_leadership_evidence": lead["has_leadership_evidence"],
        "leadership_terms": lead["leadership_terms"],
        "certifications": certs,
        "uploaded_cv": bool(uploaded_cv),
    }


# ── Deterministic education sub-scores (anchored to ranker.py guides) ─────────

def degree_level_to_score(degree_label: str | None, degree_level: int = 0) -> int:
    """Map a parsed degree to the 0-100 degree_level component used by
    compute_education_score(). Anchored to DEGREE_LEVEL_SCORES in ranker.py."""
    label = (degree_label or "").lower()
    if any(k in label for k in ("phd", "doctor")):
        return 100
    if any(k in label for k in ("master", "msc", "m.sc", "mba", "ma", "meng", "mphil")):
        return 80
    if any(k in label for k in ("bachelor", "bsc", "b.sc", "bba", "b.a", "beng", "b.eng", "llb", "engineering (bsc)")):
        return 60
    if "diploma" in label:
        return 40
    if any(k in label for k in ("hsc", "a-level", "higher secondary")):
        return 25
    if any(k in label for k in ("ssc", "o-level", "secondary")):
        return 10
    # Fall back to the numeric rank if the label was generic.
    return {4: 60, 3: 40, 2: 25, 1: 10}.get(degree_level, 0)


# ── Deterministic leadership score estimator ──────────────────────────────────

# Maps parsed job titles to leadership-level anchors (see LEADERSHIP_SCORING_GUIDE
# in ranker.py). Used when the LLM returns leadership_score = 0.

_TITLE_LEADERSHIP_LEVEL = {
    # Level 5 — Executive (90-100)
    "managing director": 5, "md": 5, "director": 5, "ceo": 5, "coo": 5,
    "cto": 5, "cfo": 5, "ciso": 5, "vp": 5, "vice president": 5,
    "gm": 5, "general manager": 5, "factory director": 5,
    # Level 4 — Senior Management (75-89)
    "agm": 4, "dgm": 4, "senior manager": 4, "sr. manager": 4,
    "head of": 4, "plant manager": 4, "factory manager": 4,
    "regional sales manager": 4, "rsm": 4,
    # Level 3 — Middle Management (58-74)
    "manager": 3, "assistant manager": 3, "am": 3, "team lead": 3,
    "section head": 3, "shift-in-charge": 3, "shift in charge": 3,
    "area sales manager": 3, "asm": 3, "supervisor": 3,
    "production supervisor": 3,
    # Level 2 — Senior IC (40-57)
    "sr. executive": 2, "senior executive": 2, "sr. officer": 2,
    "senior officer": 2, "principal engineer": 2, "lead engineer": 2,
    "sr. engineer": 2, "senior engineer": 2,
    # Level 1 — Junior IC (20-39)
    "executive": 1, "officer": 1, "trainee": 1, "management trainee": 1,
    "junior": 1, "intern": 1, "graduate trainee": 1,
    "engineer": 1, "technician": 1, "developer": 1, "programmer": 1,
    "analyst": 1, "consultant": 1, "specialist": 1, "associate": 1,
}

_LEVEL_SCORE_ANCHOR = {5: 95, 4: 82, 3: 66, 2: 48, 1: 30}


def estimate_leadership_score(features: dict, cv_text: str = "") -> int:
    """Deterministic leadership score from parsed job titles and leadership
    signals. Falls back to scanning raw CV text when structured features
    have no jobs (e.g. metadata-only stubs). Returns 0 only if absolutely
    no evidence is available."""
    jobs = features.get("jobs") or []
    has_lead = features.get("has_leadership_evidence", False)
    lead_terms = features.get("leadership_terms") or []
    total_exp = features.get("total_years_experience") or 0

    # Determine the highest leadership level from job titles
    max_level = 0
    for job in jobs:
        title = (job.get("title") or "").lower().strip()
        for pattern, level in _TITLE_LEADERSHIP_LEVEL.items():
            if pattern in title:
                max_level = max(max_level, level)
                break

    # Fallback: scan raw text for title patterns when no structured jobs
    if max_level == 0 and cv_text:
        txt_low = cv_text.lower()
        for pattern, level in _TITLE_LEADERSHIP_LEVEL.items():
            if re.search(r"\b" + re.escape(pattern) + r"\b", txt_low):
                max_level = max(max_level, level)

    # Also scan raw text for leadership verbs if features didn't find any
    if not has_lead and cv_text:
        txt_low = cv_text.lower()
        verb_hits = [t for t in LEADERSHIP_TERMS if re.search(r"\b" + re.escape(t) + r"\b", txt_low)]
        if verb_hits:
            has_lead = True
            lead_terms = verb_hits

    # Bump by 1 level if leadership evidence (verbs like "managed", "led") found
    if has_lead and len(lead_terms) >= 2 and max_level < 5:
        max_level = max(max_level + 1, 2)

    # Soft-skill signals that indicate leadership potential
    if cv_text:
        txt_low = cv_text.lower() if not cv_text.islower() else cv_text
        _LEAD_SOFT = [
            "problem.solving", "troubleshoot", "collaborat", "team.?work",
            "independent", "self.?start", "communicat", "coordinat",
            "mentor", "train", "project.?manage", "cross.?functional",
        ]
        soft_hits = sum(1 for p in _LEAD_SOFT if re.search(p, txt_low))
        if soft_hits >= 3 and max_level < 2:
            max_level = max(max_level, 2)  # evidence of collaborative/leading skills
        elif soft_hits >= 1 and max_level < 1:
            max_level = 1

    if max_level == 0:
        if has_lead:
            max_level = 1  # at least some leadership keywords
        elif total_exp and total_exp >= 5:
            max_level = 1  # experienced but no title evidence
        else:
            return 0  # genuinely no evidence

    base = _LEVEL_SCORE_ANCHOR.get(max_level, 30)

    # Bonus for quantified experience
    if total_exp and total_exp >= 8:
        base = min(100, base + 5)
    elif total_exp and total_exp >= 5:
        base = min(100, base + 3)

    return base


# ── Deterministic culture fit score estimator ─────────────────────────────────

# Soft skills / attributes that indicate good culture fit for technical roles.
# These are scanned in the CV text. Each match contributes to the score.
_CULTURE_SOFT_SKILLS = [
    ("problem.solving", 12),
    ("troubleshoot", 10),
    ("diagnos", 8),       # diagnose, diagnosing, diagnostic
    ("detail.oriented", 8),
    ("documentation", 7),
    ("testing", 6),
    ("collaborat", 8),    # collaborate, collaboration, collaborative
    ("team.?work|team.player|cross.?functional", 8),
    ("independent", 6),   # independently, independent
    ("self.?start|self.?motivated|minimal supervision", 7),
    ("communicat", 8),    # communicate, communication
    ("stakeholder", 6),
    ("field.?site|commissioning|installation", 7),
    ("travel", 4),
    ("pressure|deadline", 5),
    ("process.?improvement|continuous.?improvement", 6),
    ("quality.?assurance|qa|qc", 5),
]


def estimate_culture_fit_score(features: dict, cv_text: str = "") -> int:
    """Deterministic culture fit score from CV text analysis.

    Evaluates:
    1. Soft skill keywords (problem-solving, collaboration, etc.)
    2. Stability signals (tenure, number of jobs)
    3. Professional development (certifications, training)
    4. Communication evidence (English proficiency)

    Returns 0 only if absolutely no evidence is available.
    """
    txt = (cv_text or "").lower()
    if not txt:
        return 0

    score = 0
    max_possible = 0

    # 1. Soft skill signals (up to ~50 points)
    for pattern, weight in _CULTURE_SOFT_SKILLS:
        max_possible += weight
        if re.search(pattern, txt, re.IGNORECASE):
            score += weight

    # Normalize soft skills to 0-50 range
    soft_score = int(50 * score / max(1, max_possible)) if max_possible > 0 else 0

    # 2. Stability (up to 20 points)
    stability = 0
    jobs = features.get("jobs") or []
    total_exp = features.get("total_years_experience") or 0
    if jobs:
        max_tenure = max((j.get("tenure_years") or 0) for j in jobs)
        if max_tenure >= 3:
            stability += 12
        elif max_tenure >= 2:
            stability += 8
        elif max_tenure >= 1:
            stability += 4
        # Penalize excessive job-hopping
        if len(jobs) >= 5 and total_exp and total_exp < 8:
            stability = max(0, stability - 5)
    if total_exp and total_exp >= 5:
        stability += 8
    elif total_exp and total_exp >= 3:
        stability += 5
    elif total_exp and total_exp >= 1:
        stability += 2
    stability = min(20, stability)

    # 3. Professional development (up to 15 points)
    prof_dev = 0
    certs = features.get("certifications") or []
    if len(certs) >= 3:
        prof_dev += 12
    elif len(certs) >= 1:
        prof_dev += 8
    if features.get("degree_level", 0) >= 4:
        prof_dev += 3
    prof_dev = min(15, prof_dev)

    # 4. Communication / English (up to 15 points)
    comm = 0
    if features.get("has_english_evidence"):
        eng = features.get("english") or {}
        eng_score = features.get("english_score") or 0
        if eng_score and eng_score >= 80:
            comm = 15
        elif eng_score and eng_score >= 60:
            comm = 10
        elif eng_score:
            comm = 6
        else:
            comm = 8  # evidence but no numeric score
    elif "english" in txt:
        comm = 5
    comm = min(15, comm)

    total = soft_score + stability + prof_dev + comm

    # Minimum baseline: if candidate has professional experience but the text
    # is too short for meaningful keyword matching (metadata stubs), avoid 0
    # which implies "clear mismatch". 20 = "insufficient data for assessment".
    if total < 20 and (features.get("total_years_experience") or len(txt) > 200):
        total = max(total, 20)

    # Scale to 0-100
    return max(0, min(100, total))


def gpa_to_score(gpa_value, gpa_scale=None) -> int:
    """Map a GPA/marks figure to the 0-100 GPA component. Anchored to
    GPA_BAND_SCORES in ranker.py. Returns 50 (neutral) when unknown."""
    frac = normalize_gpa(gpa_value, gpa_scale)
    if frac is None:
        return 50  # neutral — no penalty when GPA absent
    pct = frac  # 0-1
    if pct >= 1.0:
        return 100
    if pct >= 0.925:   # 3.7+/4.0
        return 85
    if pct >= 0.875:   # 3.5-3.69/4.0
        return 70
    if pct >= 0.75:    # 3.0-3.49/4.0
        return 55
    if pct >= 0.625:   # 2.5-2.99/4.0
        return 35
    return 15
