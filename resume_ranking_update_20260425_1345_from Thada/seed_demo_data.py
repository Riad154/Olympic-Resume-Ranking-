"""
seed_demo_data.py — Populates the resume_ranking database with three sample
job postings and a spread of candidates so every Streamlit page can be
exercised end-to-end without running the actual Ollama ranker.

Run once:
    python seed_demo_data.py
"""
from __future__ import annotations

import os
import random
import sys
from pathlib import Path

# Make db.py importable
sys.path.insert(0, str(Path(__file__).resolve().parent / "resume_app"))

from db import _new_conn  # noqa: E402


JOBS = [
    {
        "job_label": "AIDigital_Transformation-SrExecutive",
        "job_title": "Sr. Executive — AI & Digital Transformation",
        "department": "AI & Digital Transformation",
        "jd_text": (
            "Drive AI/automation initiatives across Olympic Industries. "
            "Own SAP integrations, Power BI dashboards, and Python-based "
            "process automation."
        ),
        "required_skills": ["Python", "SAP", "Power BI", "Machine Learning", "Process Automation"],
        "red_flags": ["No FMCG experience", "No SAP/ERP exposure"],
        "min_experience": "5 years",
        "education_req": "Bachelor's",
        "weight_skills": 50, "weight_exp": 30, "weight_edu": 20,
        "interviewer_notes": "Must be comfortable owning stakeholder conversations.",
        "status": "Complete",
    },
    {
        "job_label": "Finance-AsstManager-Audit",
        "job_title": "Assistant Manager — Internal Audit",
        "department": "Finance and Accounts",
        "jd_text": (
            "Lead internal audit cycles, process reviews, and compliance "
            "checks across manufacturing plants."
        ),
        "required_skills": ["Internal Audit", "SAP FICO", "Risk Assessment", "Financial Controls"],
        "red_flags": ["Employment gaps", "No measurable achievements"],
        "min_experience": "5 years",
        "education_req": "Master's",
        "weight_skills": 40, "weight_exp": 40, "weight_edu": 20,
        "interviewer_notes": "CA (CC) or ACCA partially qualified preferred.",
        "status": "Complete",
    },
    {
        "job_label": "Sales-TerritoryManager-Chittagong",
        "job_title": "Territory Manager — Chittagong",
        "department": "Sales",
        "jd_text": (
            "Own secondary sales, distributor management, and coverage "
            "expansion across Chittagong division."
        ),
        "required_skills": ["Territory Management", "Distribution Management", "FMCG Experience"],
        "red_flags": ["Frequent job changes", "Limited local market knowledge"],
        "min_experience": "7 years",
        "education_req": "Bachelor's",
        "weight_skills": 35, "weight_exp": 50, "weight_edu": 15,
        "interviewer_notes": "Knowledge of Chittagong sub-districts essential.",
        "status": "Processing",
    },
]

FIRST_NAMES = [
    "Rakib", "Sadia", "Tanvir", "Nusrat", "Mehedi", "Shahriar", "Afsana",
    "Imran", "Tasnim", "Rubel", "Sumaiya", "Fahim", "Nazmul", "Farzana",
    "Arif", "Tahsin", "Moinul", "Sharmin", "Kamrul", "Mahbub",
]
LAST_NAMES = [
    "Hossain", "Rahman", "Islam", "Akter", "Ahmed", "Chowdhury",
    "Khan", "Siddique", "Bhuiyan", "Karim",
]

DEGREES = ["Bachelor's in CSE", "Bachelor's in EEE", "BBA", "MBA",
           "Master's in Statistics", "BSc in IPE"]
UNIS = ["BUET", "DU", "NSU", "BRAC University", "IUT", "AIUB", "CUET"]
LOCATIONS = ["Dhaka", "Chittagong", "Sylhet", "Rajshahi", "Khulna"]


def _score_band(base: int, jitter: int = 8) -> int:
    return max(0, min(100, base + random.randint(-jitter, jitter)))


def seed_candidates_for(cur, job_label: str, n: int = 18):
    random.seed(hash(job_label) & 0xFFFFFFFF)
    for i in range(1, n + 1):
        apply_id = f"{job_label[:4].upper()}-{1000 + i}"
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        email = f"{name.lower().replace(' ', '.')}.{i}@example.com"
        mobile = f"01{random.randint(3,9)}{random.randint(10000000, 99999999)}"

        # Spread: top 25% shortlist (75-95), next 40% maybe (55-74), rest reject
        if i <= max(1, n // 4):
            rec = "Shortlist"; base = 82
        elif i <= max(2, int(n * 0.65)):
            rec = "Maybe";     base = 62
        else:
            rec = "Reject";    base = 38

        overall = _score_band(base)
        cur.execute(
            """
            INSERT INTO candidates
                (job_label, apply_id, candidate_name, email, mobile, location,
                 degree, university, experience_detail, age,
                 expected_salary, current_salary, application_date,
                 bdjobs_score, has_uploaded_cv, pdf_path, pdf_text_chars,
                 jd_used,
                 overall_score, skills_score, experience_score,
                 leadership_score, education_score, culture_fit_score,
                 experience_years, strengths, gaps, risk_flags,
                 recommendation, reasoning)
            VALUES
                (%s, %s, %s, %s, %s, %s,
                 %s, %s, %s, %s,
                 %s, %s, %s,
                 %s, %s, %s, %s,
                 %s,
                 %s, %s, %s,
                 %s, %s, %s,
                 %s, %s, %s, %s,
                 %s, %s)
            ON CONFLICT (job_label, apply_id) DO UPDATE SET
                candidate_name    = EXCLUDED.candidate_name,
                overall_score     = EXCLUDED.overall_score,
                skills_score      = EXCLUDED.skills_score,
                experience_score  = EXCLUDED.experience_score,
                leadership_score  = EXCLUDED.leadership_score,
                education_score   = EXCLUDED.education_score,
                culture_fit_score = EXCLUDED.culture_fit_score,
                experience_years  = EXCLUDED.experience_years,
                strengths         = EXCLUDED.strengths,
                gaps              = EXCLUDED.gaps,
                risk_flags        = EXCLUDED.risk_flags,
                recommendation    = EXCLUDED.recommendation,
                reasoning         = EXCLUDED.reasoning
            """,
            (
                job_label, apply_id, name, email, mobile,
                random.choice(LOCATIONS),
                random.choice(DEGREES), random.choice(UNIS),
                "Sr. Executive @ XYZ ## 2021-Present | Executive @ ABC ## 2018-2021",
                round(random.uniform(24, 42), 1),
                str(random.randint(60000, 180000)),
                str(random.randint(45000, 160000)),
                "2026-04-15",
                str(random.randint(40, 90)),
                random.choice([True, True, False]),
                "",   # no actual PDF on disk
                random.randint(2000, 9000),
                "seed",
                overall,
                _score_band(base + 3),
                _score_band(base - 2),
                _score_band(base - 5),
                _score_band(base + 1),
                _score_band(base - 1),
                round(random.uniform(2, 15), 1),
                ["Strong SAP exposure", "Team leadership", "FMCG depth"][: random.randint(1, 3)],
                ["Limited Python", "No BI certification"][: random.randint(0, 2)],
                ["Frequent job changes"] if random.random() < 0.2 else [],
                rec,
                "Candidate shows a solid mix of domain exposure and "
                "cross-functional delivery. Flag highlighted for HR review.",
            ),
        )


def main():
    conn = _new_conn()
    with conn.cursor() as cur:
        for j in JOBS:
            cur.execute(
                """
                INSERT INTO jobs
                    (job_label, job_title, department, jd_text, required_skills,
                     red_flags, min_experience, education_req,
                     weight_skills, weight_exp, weight_edu,
                     interviewer_notes, status, last_ranked_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, NOW())
                ON CONFLICT (job_label) DO UPDATE SET
                    job_title        = EXCLUDED.job_title,
                    department       = EXCLUDED.department,
                    jd_text          = EXCLUDED.jd_text,
                    required_skills  = EXCLUDED.required_skills,
                    red_flags        = EXCLUDED.red_flags,
                    min_experience   = EXCLUDED.min_experience,
                    education_req    = EXCLUDED.education_req,
                    weight_skills    = EXCLUDED.weight_skills,
                    weight_exp       = EXCLUDED.weight_exp,
                    weight_edu       = EXCLUDED.weight_edu,
                    interviewer_notes= EXCLUDED.interviewer_notes,
                    status           = EXCLUDED.status,
                    last_ranked_at   = NOW()
                """,
                (
                    j["job_label"], j["job_title"], j["department"], j["jd_text"],
                    j["required_skills"], j["red_flags"],
                    j["min_experience"], j["education_req"],
                    j["weight_skills"], j["weight_exp"], j["weight_edu"],
                    j["interviewer_notes"], j["status"],
                ),
            )
            n = 20 if j["status"] == "Complete" else 12
            seed_candidates_for(cur, j["job_label"], n=n)
            print(f"  seeded {n:3d} candidates for {j['job_label']}")

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
