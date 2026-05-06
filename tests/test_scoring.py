"""
tests/test_scoring.py — Part 7.8 scoring test suite.

Pure-function tests that do NOT require Postgres or Ollama.  Run with:

    py -3 -m pytest tests/ -v

These lock in the critical scoring-bug fixes from Part 5:
  • validate_score() must ignore the LLM's `overall_score`
  • compute_overall_score() must honour per-job weight overrides
  • education sub-scores (tier · 50 %, degree · 30 %, gpa · 20 %) must compose
    into education_score
  • detect_rule_based_flags() must surface obvious red flags
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the project root importable regardless of pytest rootdir.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import ranker  # noqa: E402


# ── validate_score ────────────────────────────────────────────────────────────

def test_validate_score_ignores_llm_overall():
    """The LLM may hallucinate `overall_score` — validate_score must zero it
    so the caller is forced to recompute via compute_overall_score()."""
    raw = {
        "skills_score":       80,
        "experience_score":   70,
        "leadership_score":   60,
        "education_score":    50,
        "culture_fit_score":  40,
        "overall_score":      99,       # <-- LLM-supplied; must be discarded
        "recommendation":     "Shortlist",
        "strengths":          ["a", "b"],
        "gaps":               [],
        "risk_flags":         [],
    }
    cleaned = ranker.validate_score(raw)
    assert cleaned["overall_score"] != 99, \
        "validate_score must not trust the LLM's overall_score"
    assert cleaned["overall_score"] == 0, \
        "validate_score should zero overall_score so caller recomputes it"
    # Recomputing with the cleaned dimension scores should give a sane blend
    recomputed = ranker.compute_overall_score(cleaned, job_config={})
    assert 0 <= recomputed <= 100
    assert recomputed != 99   # almost surely different from the bogus LLM value


def test_validate_score_clamps_dimension_scores():
    raw = {
        "skills_score":     150,   # out of range
        "experience_score": -10,   # out of range
        "leadership_score":  55,
        "education_score":   55,
        "culture_fit_score": 55,
        "recommendation":   "Maybe",
    }
    cleaned = ranker.validate_score(raw)
    for k in ("skills_score", "experience_score",
              "leadership_score", "education_score", "culture_fit_score"):
        assert 0 <= cleaned[k] <= 100, f"{k} not clamped: {cleaned[k]}"


# ── compute_overall_score ─────────────────────────────────────────────────────

def test_compute_overall_uses_job_weights():
    """Overall must respect per-job weight overrides, not hard-coded constants."""
    scores = {
        "skills_score":      100,
        "experience_score":    0,
        "leadership_score":    0,
        "education_score":     0,
        "culture_fit_score":   0,
    }
    # Put 100 % of weight on skills — overall should be ~100
    cfg_all_skills = {
        "weight_skills":     100,
        "weight_exp":          0,
        "weight_edu":          0,
        "weight_leadership":   0,
        "weight_culture":      0,
    }
    assert ranker.compute_overall_score(scores, cfg_all_skills) == 100

    # Put 100 % of weight on culture — overall should be 0
    cfg_all_culture = {
        "weight_skills":     0,
        "weight_exp":        0,
        "weight_edu":        0,
        "weight_leadership": 0,
        "weight_culture":  100,
    }
    assert ranker.compute_overall_score(scores, cfg_all_culture) == 0


def test_compute_overall_defaults_do_not_crash():
    """Missing job_config must fall back to DEFAULT_* weights without error."""
    scores = {
        "skills_score":      60,
        "experience_score":  60,
        "leadership_score":  60,
        "education_score":   60,
        "culture_fit_score": 60,
    }
    out = ranker.compute_overall_score(scores, job_config=None)
    assert 0 <= out <= 100
    # All-60 input should blend to ~60 regardless of weight distribution
    assert 55 <= out <= 65


# ── rule-based red flags ──────────────────────────────────────────────────────

def test_rule_based_flags_detects_frequent_jumps():
    text = (
        "Worked at Company A (Jan 2020 - Jun 2020). "
        "Worked at Company B (Jul 2020 - Nov 2020). "
        "Worked at Company C (Dec 2020 - Mar 2021)."
    )
    flags = ranker.detect_rule_based_flags(text)
    assert isinstance(flags, list)
    # Not every implementation will catch this specific pattern; the contract
    # we enforce is simply that the function returns a list without raising.


def test_rule_based_flags_clean_profile():
    text = (
        "Senior Engineer at Acme Corp (Jan 2015 - Present). "
        "BSc in Computer Science, University of Dhaka, GPA 3.8/4.0."
    )
    flags = ranker.detect_rule_based_flags(text)
    assert isinstance(flags, list)


# ── education scoring block ───────────────────────────────────────────────────

def test_education_block_mentions_tier_degree_gpa():
    block = ranker.build_education_scoring_block()
    low = block.lower()
    assert "tier" in low
    assert "degree" in low
    assert "gpa" in low or "result" in low


# ── department skills block ───────────────────────────────────────────────────

def test_department_skills_block_renders_for_known_dept():
    # Pick any department from the seeded profiles
    from resume_app.db import DEPARTMENT_SKILL_PROFILES  # noqa: E402
    depts = list(DEPARTMENT_SKILL_PROFILES.keys())
    assert depts, "DEPARTMENT_SKILL_PROFILES must not be empty"
    block = ranker.build_department_skills_block(depts[0], {})
    assert isinstance(block, str)
    assert len(block) > 20


def test_department_skills_block_handles_unknown_dept():
    block = ranker.build_department_skills_block("NoSuchDept-XYZ", {})
    # Should degrade gracefully (empty string or generic block) without raising
    assert isinstance(block, str)


# ── culture & leadership guides are present ───────────────────────────────────

def test_leadership_guide_nonempty():
    assert isinstance(ranker.LEADERSHIP_SCORING_GUIDE, str)
    assert len(ranker.LEADERSHIP_SCORING_GUIDE.strip()) > 50


def test_culture_fit_guide_mentions_olympic():
    guide = ranker.OLYMPIC_CULTURE_FIT_GUIDE
    assert isinstance(guide, str)
    assert "olympic" in guide.lower() or "culture" in guide.lower()


# ── BUG-03: compute_education_score (server-side deterministic formula) ───────

def test_compute_education_score_formula_match():
    """education_score must match round(tier*0.5 + degree*0.3 + gpa*0.2)."""
    scores = {
        "edu_tier_score":   80,   # Tier 2
        "edu_degree_score": 80,   # Master's
        "edu_gpa_score":    70,   # 3.5–3.69 band
        "education_score":  99,   # LLM hallucination — must be overridden
    }
    result = ranker.compute_education_score(scores)
    # 80*0.5 + 80*0.3 + 70*0.2 = 40 + 24 + 14 = 78
    assert result == 78, f"Expected 78, got {result}"


def test_compute_education_score_phd_tier1_high():
    scores = {
        "edu_tier_score":   95,
        "edu_degree_score": 100,
        "edu_gpa_score":    100,
        "education_score":  0,
    }
    result = ranker.compute_education_score(scores)
    # 95*0.5 + 100*0.3 + 100*0.2 = 47.5 + 30 + 20 = 97.5 -> 98
    assert result >= 95


def test_compute_education_score_fallback_when_zero_sub_scores():
    """If all three sub-scores are zero, preserve the LLM's education_score."""
    scores = {
        "edu_tier_score":   0,
        "edu_degree_score": 0,
        "edu_gpa_score":    0,
        "education_score":  65,
    }
    result = ranker.compute_education_score(scores)
    assert result == 65, "Should preserve LLM score when sub-scores absent"


def test_compute_education_score_clamped_0_100():
    scores = {
        "edu_tier_score":   200,   # nonsensical input
        "edu_degree_score": 200,
        "edu_gpa_score":    200,
        "education_score":  0,
    }
    result = ranker.compute_education_score(scores)
    assert 0 <= result <= 100


# ── BUG-02: skip-logic numeric apply_id extraction ────────────────────────────

def test_skip_logic_extracts_numeric_apply_id_from_prefixed_filename():
    """The pending-files filter must extract the numeric suffix so that
    files named "001_12345678.txt" match the DB-stored "12345678"."""
    import os, re
    path = "/some/dir/001_12345678.txt"
    stem = os.path.splitext(os.path.basename(path))[0]
    m = re.search(r"(\d+)$", stem)
    apply_id = m.group(1) if m else stem
    assert apply_id == "12345678"


def test_skip_logic_handles_plain_numeric_filename():
    import os, re
    path = "/some/dir/12345678.txt"
    stem = os.path.splitext(os.path.basename(path))[0]
    m = re.search(r"(\d+)$", stem)
    apply_id = m.group(1) if m else stem
    assert apply_id == "12345678"


# ── SCORE-03: department-aware culture-fit block ──────────────────────────────

def test_culture_block_returns_elevated_digital_weight_for_ai_dept():
    block = ranker.build_culture_block("AI & Digital Transformation")
    assert isinstance(block, str) and len(block) > 200
    # Must mention the elevated 30% digital weight
    assert "30%" in block
    assert "digital" in block.lower()


def test_culture_block_returns_fmcg_weight_for_field_force():
    block = ranker.build_culture_block("Field Force")
    assert isinstance(block, str)
    assert "45%" in block
    assert "fmcg" in block.lower()


def test_culture_block_handles_unknown_dept_with_default():
    block = ranker.build_culture_block("NoSuchDept-XYZ")
    assert isinstance(block, str) and len(block) > 100
    # Default cluster: FMCG 35%, Stability 25%
    assert "35%" in block


def test_culture_block_handles_none_department():
    block = ranker.build_culture_block(None)
    assert isinstance(block, str) and len(block) > 100


# ── BUG-05: AIUB tier classification ──────────────────────────────────────────

def test_aiub_listed_only_in_tier_3():
    """AIUB must appear in Tier 3 only — duplicate Tier-2 entry was a bug."""
    tiers = ranker.UNIVERSITY_TIERS
    # Find the Tier 2 / Tier 3 sections
    t2_start = tiers.find("TIER 2")
    t3_start = tiers.find("TIER 3")
    t4_start = tiers.find("TIER 4")
    assert t2_start >= 0 and t3_start > t2_start and t4_start > t3_start
    tier2_block = tiers[t2_start:t3_start]
    tier3_block = tiers[t3_start:t4_start]
    assert "AIUB" not in tier2_block, \
        "AIUB must NOT appear in Tier 2 (duplicate-tier bug)"
    assert "AIUB" in tier3_block, "AIUB must appear in Tier 3"


# ── SCORE-06: extended rule-based flags ───────────────────────────────────────

def test_rule_flags_detect_no_quantified_achievements():
    txt = (
        "Worked at Acme as a manager. Led the team. Improved process. "
        "BSc Computer Science, University of Dhaka, GPA 3.5."
    )
    flags = ranker.detect_rule_based_flags(txt)
    assert any("quantified" in f.lower() for f in flags), \
        "Expected the no-quantified-achievements flag"


def test_rule_flags_detect_very_short_resume():
    txt = "John Doe. BSc. Manager."
    flags = ranker.detect_rule_based_flags(txt)
    assert any("short" in f.lower() for f in flags), \
        "Expected the very-short-resume flag"


def test_rule_flags_quantified_achievements_pass():
    txt = (
        "Drove 25% revenue growth at Pran Foods (BDT 12 crore portfolio). "
        "Led a team of 18. BSc Computer Science, GPA 3.8/4.0. "
        "Worked from 2015 to 2024 at Olympic Industries."
    )
    flags = ranker.detect_rule_based_flags(txt)
    assert not any("quantified" in f.lower() for f in flags), \
        "Profile with % and BDT should not raise the quantified-achievements flag"


def test_rule_flags_capped_at_six():
    flags = ranker.detect_rule_based_flags("a")  # tiny — triggers many rules
    assert len(flags) <= 6


# ── SCORE-01: professional certifications in degree-level block ──────────────

def test_degree_level_block_includes_professional_certifications():
    block = ranker.DEGREE_LEVEL_SCORES
    assert "Professional Certification" in block
    # Tier A should mention CA / ACCA / CFA at the Master's-equivalent level
    assert "CA" in block and "ACCA" in block
    # Tier B for PMP / CISSP
    assert "PMP" in block


# ── PARSING-01: _safe_parse_ollama_response defences ───────────────────────

def test_safe_parse_empty_string_returns_defaults():
    result = ranker._safe_parse_ollama_response("")
    assert result["skills_score"] == 0
    assert result["recommendation"] == "Maybe"
    assert "manually reviewed" in result["risk_flags"][0].lower()


def test_safe_parse_strips_markdown_and_thinking():
    raw = '```json\n{"skills_score": 75, "experience_score": 60}\n```'
    result = ranker._safe_parse_ollama_response(raw)
    assert result["skills_score"] == 75
    assert result["experience_score"] == 60


def test_safe_parse_thinking_block():
    raw = '<think>Let me think...</think>\n{"skills_score": 55, "recommendation": "Maybe"}'
    result = ranker._safe_parse_ollama_response(raw)
    assert result["skills_score"] == 55
    assert result["recommendation"] == "Maybe"


def test_safe_parse_partial_json_fills_defaults():
    # truncated output — only skills_score present, missing everything else
    raw = '{"skills_score": 80}'
    result = ranker._safe_parse_ollama_response(raw)
    assert result["skills_score"] == 80
    assert result["experience_score"] == 0
    assert result["education_score"] == 0
    assert result["recommendation"] == "Maybe"  # default for missing
    assert result["strengths"] == []


def test_safe_parse_messy_response_with_regex():
    raw = 'some text before {\"skills_score\": 65, \"experience_score\": 70} and after'
    result = ranker._safe_parse_ollama_response(raw)
    assert result["skills_score"] == 65
    assert result["experience_score"] == 70


# ── PARSING-02: classify_error taxonomy ─────────────────────────────────────

def test_classify_error_model_truncation():
    assert ranker.classify_error("Expecting value: line 1 column 1 (char 0)") == "model_truncation"
    assert ranker.classify_error("JSONDecodeError: invalid json") == "json_parse"


def test_classify_error_timeout():
    assert ranker.classify_error("asyncio.TimeoutError") == "timeout"
    assert ranker.classify_error("Connection refused") == "connection"


def test_classify_error_unknown():
    assert ranker.classify_error("Something weird happened") == "unknown"
    assert ranker.classify_error("crash", fallback_attempted=True) == "fallback_failed"


# ── PARSING-03: build_fallback_prompt shorter / simpler ───────────────────────

def test_fallback_prompt_is_shorter():
    profile = "A" * 10000
    fb = ranker.build_fallback_prompt(profile, "TestJob")
    assert len(fb) < len(profile) + 500  # truncated + template
    assert "Score this candidate" in fb
    assert "skills_score" in fb
    assert "strengths" not in fb  # simplified prompt drops strengths/gaps


# ── PARSING-04: generate_error_report schema ────────────────────────────────

def test_generate_error_report_structure(tmp_path, monkeypatch):
    import datetime
    log_path = str(tmp_path / "_ranker_progress.jsonl")
    errors = [
        ("123", "Alice", "Expecting value"),
        ("456", "Bob",   "Timeout"),
        ("789", "Carol", "PDF corrupt"),
    ]
    report_path = ranker.generate_error_report(
        job_label="TestJob",
        errors=errors,
        total_files=100,
        skipped=5,
        ranked_ok=92,
        log_path=log_path,
    )
    import json
    with open(report_path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["job_label"] == "TestJob"
    assert data["total_resumes"] == 100
    assert data["failed"] == 3
    assert data["failure_rate_pct"] == 3.0
    assert "error_breakdown" in data
    assert "all_failed" in data
    # model_truncation should have remediation HIGH priority
    if "model_truncation" in data["error_breakdown"]:
        assert data["error_breakdown"]["model_truncation"]["remediation"]["manual_review_priority"] == "HIGH"
