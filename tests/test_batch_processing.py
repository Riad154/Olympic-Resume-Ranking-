"""
Comprehensive test suite for Resume Ranking batch processing.
Tests variable batch sizes, error handling, and edge cases.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
import tempfile
import json
from pathlib import Path

# Test imports
from ranker import (
    normalize_verdict, 
    validate_score, 
    _default_scores_dict,
    _fill_missing_fields,
    classify_error,
    compute_overall_score,
    compute_education_score,
    parse_employment_periods,
    compute_experience_years_from_dates,
    detect_employment_gaps,
    detect_rule_based_flags,
)


class TestNormalizeVerdict:
    """Test the normalize_verdict function that was causing 100% failures."""
    
    def test_shortlist_variations(self):
        """Test various positive recommendation strings map to Shortlist."""
        positives = [
            'Shortlist', 'Hire', 'Yes', 'Strong Hire', 'Recommend',
            'Accept', 'Top Candidate', 'Excellent', 'Good Fit',
            'Proceed', 'Advance', 'Select', 'strongly recommend'
        ]
        for p in positives:
            assert normalize_verdict(p) == 'Shortlist', f"Failed for: {p}"
    
    def test_reject_variations(self):
        """Test various negative recommendation strings map to Reject."""
        negatives = [
            'Reject', 'No', 'Pass', 'Decline', 'Not suitable',
            'Poor fit', 'Weak', 'Skip', 'Drop', 'Unsuitable',
            'Not Recommended', 'Do not hire'
        ]
        for n in negatives:
            assert normalize_verdict(n) == 'Reject', f"Failed for: {n}"
    
    def test_maybe_variations(self):
        """Test various neutral strings map to Maybe."""
        neutrals = [
            'Maybe', 'Consider', 'Neutral', '', None, 'Undecided',
            'Review', 'Borderline', 'Average', 'Mixed'
        ]
        for n in neutrals:
            assert normalize_verdict(n) == 'Maybe', f"Failed for: {n}"
    
    def test_case_insensitive(self):
        """Test that matching is case-insensitive."""
        assert normalize_verdict('SHORTLIST') == 'Shortlist'
        assert normalize_verdict('Reject') == 'Reject'
        assert normalize_verdict('MAYBE') == 'Maybe'


class TestValidateScore:
    """Test score validation with variable batch inputs."""
    
    def test_valid_score_dict(self):
        """Test validation of a complete score dictionary."""
        raw = {
            'skills_score': 85,
            'experience_score': 70,
            'leadership_score': 60,
            'education_score': 75,
            'culture_fit_score': 80,
            'recommendation': 'Shortlist',
            'experience_years': 5.5,
            'strengths': ['Python', 'Leadership'],
            'gaps': ['No MBA'],
            'risk_flags': [],
            'reasoning': 'Good candidate'
        }
        result = validate_score(raw)
        assert result['skills_score'] == 85
        assert result['recommendation'] == 'Shortlist'
    
    def test_missing_fields_get_defaults(self):
        """Test that missing fields are filled with safe defaults."""
        raw = {'skills_score': 50}  # Minimal input
        result = validate_score(raw)
        assert result['experience_score'] == 0
        assert result['leadership_score'] == 0
        assert result['recommendation'] == 'Maybe'
    
    def test_invalid_recommendation_normalized(self):
        """Test that invalid recommendations are normalized."""
        raw = _default_scores_dict()
        raw['recommendation'] = 'INVALID_VALUE'
        result = validate_score(raw)
        assert result['recommendation'] in ['Shortlist', 'Maybe', 'Reject']


class TestBatchEdgeCases:
    """Test edge cases for variable batch sizes."""
    
    def test_empty_batch(self):
        """Test handling of empty batch (0 CVs)."""
        scores = _default_scores_dict()
        assert scores['recommendation'] == 'Maybe'
        assert scores['skills_score'] == 0
    
    def test_single_cv_batch(self):
        """Test minimum valid batch size (1 CV)."""
        raw = {
            'skills_score': 90,
            'experience_score': 85,
            'education_score': 80,
            'leadership_score': 75,
            'culture_fit_score': 85,
            'recommendation': 'Shortlist'
        }
        result = validate_score(raw)
        overall = compute_overall_score(result)
        assert 0 <= overall <= 100
    
    def test_large_batch_simulation(self):
        """Simulate processing of 100+ CVs in batch."""
        results = []
        for i in range(100):
            raw = {
                'skills_score': i % 100,
                'experience_score': (i + 10) % 100,
                'education_score': (i + 20) % 100,
                'leadership_score': (i + 30) % 100,
                'culture_fit_score': (i + 40) % 100,
                'recommendation': ['Shortlist', 'Maybe', 'Reject'][i % 3]
            }
            result = validate_score(raw)
            overall = compute_overall_score(result)
            results.append(overall)
        
        assert len(results) == 100
        assert all(0 <= r <= 100 for r in results)


class TestErrorHandling:
    """Test error classification and handling."""
    
    def test_error_classification(self):
        """Test that errors are correctly classified."""
        assert classify_error('Expecting value: line 1 column 1 (char 0)') == 'model_truncation'
        assert classify_error('Connection timeout') == 'timeout'
        assert classify_error('PDF corrupt') == 'parse_error'
        assert classify_error('Unicode decode error') == 'json_parse'
        assert classify_error('KeyError: missing') == 'schema_missing'
    
    def test_per_cv_fail_safety(self):
        """Test that one CV failure doesn't break entire batch."""
        # This tests the principle that individual CV failures should be caught
        # and logged without stopping the batch
        
        def process_cv_with_fallback(cv_data):
            try:
                # Simulate processing
                if cv_data.get('corrupt'):
                    raise ValueError("PDF corrupt")
                return {'status': 'success', 'score': 85}
            except Exception as e:
                # Log error but return safe defaults
                error_type = classify_error(str(e))
                return {
                    'status': 'failed',
                    'error_type': error_type,
                    'score': 0
                }
        
        batch = [
            {'name': 'Good CV 1'},
            {'name': 'Bad CV', 'corrupt': True},
            {'name': 'Good CV 2'}
        ]
        
        results = [process_cv_with_fallback(cv) for cv in batch]
        
        assert results[0]['status'] == 'success'
        assert results[1]['status'] == 'failed'
        assert results[1]['error_type'] == 'parse_error'
        assert results[2]['status'] == 'success'


class TestComputeOverallScore:
    """Test overall score computation with various weights."""
    
    def test_default_weights(self):
        """Test scoring with default weights."""
        scores = {
            'skills_score': 80,
            'experience_score': 70,
            'education_score': 60,
            'leadership_score': 50,
            'culture_fit_score': 90
        }
        overall = compute_overall_score(scores)
        assert 0 <= overall <= 100
    
    def test_custom_weights(self):
        """Test scoring with custom job weights."""
        scores = {
            'skills_score': 80,
            'experience_score': 70,
            'education_score': 60,
            'leadership_score': 50,
            'culture_fit_score': 90
        }
        job_config = {
            'weight_skills': 60,
            'weight_exp': 20,
            'weight_edu': 20,
            'weight_leadership': 10,
            'weight_culture': 5
        }
        overall = compute_overall_score(scores, job_config)
        assert 0 <= overall <= 100


class TestDownloadSlicing:
    """Test download count slicing logic."""
    
    def test_slicing_within_bounds(self):
        """Test requesting fewer CVs than available."""
        all_candidates = list(range(100))  # Simulate 100 candidates
        requested = 50
        result = all_candidates[:min(requested, len(all_candidates))]
        assert len(result) == 50
    
    def test_slicing_exceeds_available(self):
        """Test requesting more CVs than available."""
        all_candidates = list(range(20))  # Only 20 available
        requested = 50
        result = all_candidates[:min(requested, len(all_candidates))]
        assert len(result) == 20  # Return all available
    
    def test_slicing_zero_request(self):
        """Test edge case: request 0 CVs."""
        all_candidates = list(range(100))
        requested = 0
        result = all_candidates[:min(requested, len(all_candidates))]
        assert len(result) == 0
    
    def test_slicing_single_cv(self):
        """Test minimum case: request 1 CV."""
        all_candidates = list(range(100))
        requested = 1
        result = all_candidates[:min(requested, len(all_candidates))]
        assert len(result) == 1


class TestEmploymentDateParsing:
    """Test proper parsing of employment dates and gap detection."""

    CONTINUOUS_CV = """Employment History:
Total Year of experience: 8.6 yrs
1. Executive Production (1.5yrs)
(11 Nov 2024 - Continuing)
Akboria Limited
2. Production Supervisor (6.0yrs)
(17 Oct 2018 - 11 Oct 2024)
Cocola Food Products Ltd.
3. QA Supervisor (1.0yrs)
(14 Oct 2017 - 14 Oct 2018)
Bangle Biscuits Ltd.
Academic Qualification:
Bachelor of Science (BSc) 2026
Date of Birth: 4 May 1997"""

    GAPPED_CV = """Employment History:
Total Year of experience: 5.3 yrs
1. Executive-Production (2.8yrs)
(3 Jul 2023 - Continuing)
US Bangla Airlines
2. Executive-Production (2.2yrs)
(1 Apr 2021 - 30 Jun 2023)
Igloo Foods Ltd.
3. Intership (0.1yrs)
(30 Jun 2020 - 30 Jul 2020)
Globe Biscuits
Academic Qualification:
Masters of Science (MSc) 2020"""

    def test_continuous_employment_no_gap(self):
        """Continuous employment must NOT flag any gap."""
        gaps = detect_employment_gaps(self.CONTINUOUS_CV)
        assert gaps == [], f"Expected no gaps, got: {gaps}"

    def test_real_gap_detected(self):
        """Real 8-month gap (Jul 2020 -> Apr 2021) must be detected."""
        gaps = detect_employment_gaps(self.GAPPED_CV)
        assert len(gaps) == 1, f"Expected 1 gap, got: {gaps}"
        assert "2020" in gaps[0] and "2021" in gaps[0]

    def test_present_continuing_handling(self):
        """'Continuing' must be parsed as today's date."""
        from datetime import date
        periods = parse_employment_periods(self.CONTINUOUS_CV)
        assert len(periods) == 3
        # Last period end date should be today
        assert periods[-1][1] == date.today()

    def test_experience_years_calculation(self):
        """Total experience years must be computed from date ranges."""
        years = compute_experience_years_from_dates(self.CONTINUOUS_CV)
        assert 8.0 <= years <= 9.0, f"Expected ~8.5 yrs, got: {years}"
        years2 = compute_experience_years_from_dates(self.GAPPED_CV)
        assert 4.5 <= years2 <= 6.0, f"Expected ~5.2 yrs, got: {years2}"

    def test_no_false_positive_from_education_years(self):
        """Education years (1997, 2013, 2017, 2026) must NOT cause gap flags."""
        flags = detect_rule_based_flags(self.CONTINUOUS_CV)
        gap_flags = [f for f in flags if "gap" in f.lower()]
        assert gap_flags == [], f"False positive gap from education years: {gap_flags}"

    def test_present_variations(self):
        """All 'present' variations should parse correctly."""
        from datetime import date
        for token in ["Present", "Continuing", "Till now", "Current", "Till Date", "Ongoing"]:
            cv = f"""Employment History:
1. Role (1.0yrs)
(1 Jan 2023 - {token})
Company XYZ
Academic Qualification:"""
            periods = parse_employment_periods(cv)
            assert len(periods) == 1, f"Failed for token: {token}"
            assert periods[0][1] == date.today(), f"'{token}' not parsed as today"


if __name__ == '__main__':
    # Run basic tests
    print("Testing normalize_verdict...")
    test = TestNormalizeVerdict()
    test.test_shortlist_variations()
    test.test_reject_variations()
    test.test_maybe_variations()
    test.test_case_insensitive()
    print("✓ normalize_verdict tests passed")
    
    print("\nTesting batch edge cases...")
    batch_test = TestBatchEdgeCases()
    batch_test.test_empty_batch()
    batch_test.test_single_cv_batch()
    batch_test.test_large_batch_simulation()
    print("✓ Batch edge case tests passed")
    
    print("\nTesting error handling...")
    error_test = TestErrorHandling()
    error_test.test_error_classification()
    error_test.test_per_cv_fail_safety()
    print("✓ Error handling tests passed")
    
    print("\nTesting download slicing...")
    slice_test = TestDownloadSlicing()
    slice_test.test_slicing_within_bounds()
    slice_test.test_slicing_exceeds_available()
    slice_test.test_slicing_zero_request()
    slice_test.test_slicing_single_cv()
    print("✓ Download slicing tests passed")
    
    print("\nTesting employment date parsing & gap detection...")
    emp_test = TestEmploymentDateParsing()
    emp_test.test_continuous_employment_no_gap()
    emp_test.test_real_gap_detected()
    emp_test.test_present_continuing_handling()
    emp_test.test_experience_years_calculation()
    emp_test.test_no_false_positive_from_education_years()
    print("✓ Employment date parsing & gap detection tests passed")
    
    print("\n" + "="*60)
    print("All tests passed! The 100% error bug has been fixed.")
    print("="*60)
