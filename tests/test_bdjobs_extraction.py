"""Regression tests for the BDJobs CV feature extraction fix.

Verifies that the three known mis-scored CVs are parsed correctly:
- Tanvir Ahmed
- Nasir Uddin Tushar
- Sohag Hosen

All tests run against the real PDF files that the downloader produced; no LLM
or database is involved, so this is fast and deterministic.
"""

import os
import sys
from pathlib import Path

import pytest

# Ensure the project root is importable.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from bdjobs_features import build_candidate_features
from ranker import extract_pdf_text


JOB_DIR = (
    PROJECT_ROOT
    / "downloaded_resumes"
    / "Hardware_Engineer_IT_Hardware_AI_Systems_Integration_1497237"
    / "uploaded_cvs"
)


def _load_pdf(name_slug: str) -> str:
    if not JOB_DIR.exists():
        raise FileNotFoundError(f"Downloaded job directory not found: {JOB_DIR}")
    candidates = [f for f in os.listdir(JOB_DIR) if f.endswith(".pdf") and name_slug in f]
    if not candidates:
        raise FileNotFoundError(f"No PDF matching {name_slug!r} in {JOB_DIR}")
    path = JOB_DIR / candidates[0]
    text = extract_pdf_text(str(path))
    assert text and len(text) > 500, f"PDF text extraction failed for {path}"
    return text


def test_tanvir():
    text = _load_pdf("Tanvir_Ahmed")
    f = build_candidate_features(text, uploaded_cv=True)
    assert f["total_years_experience"] is not None and f["total_years_experience"] >= 4.5
    assert len(f["jobs"]) >= 3
    assert f["degree_level"] == 4
    assert f["gpa_normalized"] is not None and f["gpa_normalized"] > 0
    assert f["has_english_evidence"] is True
    assert f["has_leadership_evidence"] is True
    assert "CCNA" in f["certifications"]
    assert f["uploaded_cv"] is True


def test_nasir():
    text = _load_pdf("Nasir_Uddin_Tushar")
    f = build_candidate_features(text, uploaded_cv=True)
    assert f["total_years_experience"] is not None and f["total_years_experience"] >= 9.0
    assert len(f["jobs"]) >= 3
    assert f["degree_level"] == 4
    assert f["gpa_normalized"] is not None and f["gpa_normalized"] > 0
    assert f["has_english_evidence"] is True
    assert f["uploaded_cv"] is True


def test_sohag():
    text = _load_pdf("Sohag")
    f = build_candidate_features(text, uploaded_cv=True)
    assert f["total_years_experience"] is not None and f["total_years_experience"] >= 3.0
    assert len(f["jobs"]) >= 2
    assert f["degree_level"] == 4
    assert f["has_english_evidence"] is True
    assert f["has_leadership_evidence"] is True
    assert "CCNA" in f["certifications"]
    assert f["uploaded_cv"] is True


if __name__ == "__main__":
    test_tanvir()
    test_nasir()
    test_sohag()
    print("All BDJobs extraction regression tests passed.")
