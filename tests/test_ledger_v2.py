"""Comprehensive test suite for VAULT V2 Ground-Truth Ledger & Precedence Engine."""

import json
import pytest

from synth import ledger_v2
from synth.ledger_v2 import evaluate_single_experiment_v2, generate_summary_v2


@pytest.fixture
def base_catalogs():
    sops = [
        {
            "sop_id": "SOP-001",
            "sop_version": "1.0",
            "clause_id": "CLAUSE-001",
            "effective_date": "2024-01-01",
            "superseded_date": "2025-12-31",
            "minimum_value": 2.0,
            "maximum_value": 8.0,
            "canonical_unit": "mg/L",
            "measurement_precision": 2,
        }
    ]
    instruments = [
        {
            "instrument_id": "INST-001",
            "calibration_date": "2025-01-01",
            "validity_days": 180,  # Valid through 2025-06-30
            "calibration_status": "CALIBRATED",
        }
    ]
    lots = [
        {
            "lot_id": "LOT-001",
            "manufacture_date": "2024-06-01",
            "expiry_date": "2025-12-31",
        }
    ]
    samples = [
        {
            "sample_id": "SMP-001",
            "collected_at": "2025-03-01T08:00:00Z",
            "max_holding_hours": 24.0,
            "site_id": "SITE-BOS",
            "site_timezone": "America/New_York",
        }
    ]
    return {
        "sops": sops,
        "instruments": instruments,
        "lots": lots,
        "samples": samples,
    }


def test_all_pass_experiment_yields_valid(base_catalogs):
    exp = {
        "experiment_id": "EXP-0001",
        "run_date": "2025-03-01",
        "sop_id": "SOP-001",
        "sop_version": "1.0",
        "clause_id": "CLAUSE-001",
        "instrument_id": "INST-001",
        "lot_id": "LOT-001",
        "sample_id": "SMP-001",
        "measured_value": 5.0,
        "measurement_unit": "mg/L",
        "measurement_uncertainty": 0.2,
        "collected_at": "2025-03-01T08:00:00Z",
        "analyzed_at": "2025-03-01T14:00:00Z",
        "scenario_family": "Nominal valid",
    }
    rec = evaluate_single_experiment_v2(exp=exp, **base_catalogs)
    assert rec["final_verdict"] == "valid"
    assert rec["abstain"] is False
    assert rec["failure_reason_codes"] == []
    assert rec["review_reason_codes"] == []
    assert rec["all_reason_codes"] == []


def test_definite_failure_alone_yields_invalid(base_catalogs):
    # Expired instrument (run_date 2025-08-01 > cal expiry 2025-06-30)
    exp = {
        "experiment_id": "EXP-0002",
        "run_date": "2025-08-01",
        "sop_id": "SOP-001",
        "sop_version": "1.0",
        "clause_id": "CLAUSE-001",
        "instrument_id": "INST-001",
        "lot_id": "LOT-001",
        "sample_id": "SMP-001",
        "measured_value": 5.0,
        "measurement_unit": "mg/L",
        "measurement_uncertainty": 0.2,
        "collected_at": "2025-08-01T08:00:00Z",
        "analyzed_at": "2025-08-01T14:00:00Z",
        "scenario_family": "Calibration expiry invalid",
    }
    rec = evaluate_single_experiment_v2(exp=exp, **base_catalogs)
    assert rec["final_verdict"] == "invalid"
    assert rec["abstain"] is False
    assert "CALIBRATION_EXPIRED" in rec["failure_reason_codes"]
    assert rec["review_reason_codes"] == []


def test_review_alone_yields_needs_review(base_catalogs):
    # Measurement uncertainty crosses upper boundary (7.9 +- 0.3 crosses 8.0)
    exp = {
        "experiment_id": "EXP-0003",
        "run_date": "2025-03-01",
        "sop_id": "SOP-001",
        "sop_version": "1.0",
        "clause_id": "CLAUSE-001",
        "instrument_id": "INST-001",
        "lot_id": "LOT-001",
        "sample_id": "SMP-001",
        "measured_value": 7.9,
        "measurement_unit": "mg/L",
        "measurement_uncertainty": 0.3,
        "collected_at": "2025-03-01T08:00:00Z",
        "analyzed_at": "2025-03-01T14:00:00Z",
        "scenario_family": "Measurement boundary uncertainty review",
    }
    rec = evaluate_single_experiment_v2(exp=exp, **base_catalogs)
    assert rec["final_verdict"] == "needs_review"
    assert rec["abstain"] is True
    assert "UNCERTAINTY_CROSSES_BOUNDARY" in rec["review_reason_codes"]
    assert rec["failure_reason_codes"] == []


def test_failure_combined_with_review_yields_needs_review_and_preserves_both_reasons(base_catalogs):
    # Expired instrument (CALIBRATION_EXPIRED) AND boundary uncertainty (UNCERTAINTY_CROSSES_BOUNDARY)
    exp = {
        "experiment_id": "EXP-0004",
        "run_date": "2025-08-01",  # Expired calibration
        "sop_id": "SOP-001",
        "sop_version": "1.0",
        "clause_id": "CLAUSE-001",
        "instrument_id": "INST-001",
        "lot_id": "LOT-001",
        "sample_id": "SMP-001",
        "measured_value": 7.9,     # Crosses boundary
        "measurement_unit": "mg/L",
        "measurement_uncertainty": 0.3,
        "collected_at": "2025-08-01T08:00:00Z",
        "analyzed_at": "2025-08-01T14:00:00Z",
        "scenario_family": "Compound failure with review",
    }
    rec = evaluate_single_experiment_v2(exp=exp, **base_catalogs)
    assert rec["final_verdict"] == "needs_review"
    assert rec["abstain"] is True

    # Critical check: Definite failure reason must be preserved!
    assert "CALIBRATION_EXPIRED" in rec["failure_reason_codes"]
    assert "UNCERTAINTY_CROSSES_BOUNDARY" in rec["review_reason_codes"]
    assert "CALIBRATION_EXPIRED" in rec["all_reason_codes"]
    assert "UNCERTAINTY_CROSSES_BOUNDARY" in rec["all_reason_codes"]


def test_multiple_simultaneous_failures(base_catalogs):
    # Expired instrument AND holding time exceeded
    exp = {
        "experiment_id": "EXP-0005",
        "run_date": "2025-08-01",
        "sop_id": "SOP-001",
        "sop_version": "1.0",
        "clause_id": "CLAUSE-001",
        "instrument_id": "INST-001",
        "lot_id": "LOT-001",
        "sample_id": "SMP-001",
        "measured_value": 5.0,
        "measurement_unit": "mg/L",
        "measurement_uncertainty": 0.2,
        "collected_at": "2025-07-28T08:00:00Z",  # 4 days earlier!
        "analyzed_at": "2025-08-01T14:00:00Z",
        "scenario_family": "Compound dual failure invalid",
    }
    rec = evaluate_single_experiment_v2(exp=exp, **base_catalogs)
    assert rec["final_verdict"] == "invalid"
    assert rec["abstain"] is False
    assert "CALIBRATION_EXPIRED" in rec["failure_reason_codes"]
    assert "HOLDING_TIME_EXCEEDED" in rec["failure_reason_codes"]


def test_verdict_not_derived_from_scenario_family_label(base_catalogs):
    # An experiment with scenario_family = "Nominal valid" but containing a violation
    # must be evaluated by rules, NOT by the label!
    exp = {
        "experiment_id": "EXP-0006",
        "run_date": "2025-03-01",
        "sop_id": "SOP-001",
        "sop_version": "1.0",
        "clause_id": "CLAUSE-001",
        "instrument_id": "INST-001",
        "lot_id": "LOT-001",
        "sample_id": "SMP-001",
        "measured_value": 50.0,  # Clearly out of range (max is 8.0)
        "measurement_unit": "mg/L",
        "measurement_uncertainty": 0.2,
        "collected_at": "2025-03-01T08:00:00Z",
        "analyzed_at": "2025-03-01T14:00:00Z",
        "scenario_family": "Nominal valid",  # Mislabeled intentionally!
    }
    rec = evaluate_single_experiment_v2(exp=exp, **base_catalogs)
    assert rec["final_verdict"] == "invalid"
    assert "MEASUREMENT_OUT_OF_RANGE" in rec["failure_reason_codes"]


def test_summary_mathematics_and_metrics():
    ledger_records = [
        {"experiment_id": "E1", "final_verdict": "valid", "abstain": False, "scenario_family": "Valid",
         "rule_results": {"sop": {"status": "pass"}, "calibration": {"status": "pass"}, "lot": {"status": "pass"}, "holding_time": {"status": "pass"}, "measurement": {"status": "pass"}},
         "failure_reason_codes": [], "review_reason_codes": [], "all_reason_codes": []},
        {"experiment_id": "E2", "final_verdict": "invalid", "abstain": False, "scenario_family": "Invalid",
         "rule_results": {"sop": {"status": "pass"}, "calibration": {"status": "fail"}, "lot": {"status": "pass"}, "holding_time": {"status": "pass"}, "measurement": {"status": "pass"}},
         "failure_reason_codes": ["CALIBRATION_EXPIRED"], "review_reason_codes": [], "all_reason_codes": ["CALIBRATION_EXPIRED"]},
        {"experiment_id": "E3", "final_verdict": "needs_review", "abstain": True, "scenario_family": "Review",
         "rule_results": {"sop": {"status": "pass"}, "calibration": {"status": "fail"}, "lot": {"status": "pass"}, "holding_time": {"status": "pass"}, "measurement": {"status": "needs_review"}},
         "failure_reason_codes": ["CALIBRATION_EXPIRED"], "review_reason_codes": ["UNCERTAINTY_CROSSES_BOUNDARY"], "all_reason_codes": ["CALIBRATION_EXPIRED", "UNCERTAINTY_CROSSES_BOUNDARY"]},
    ]
    summary = generate_summary_v2(ledger_records)
    assert summary["total_experiments_processed"] == 3
    assert summary["verdict_distribution"]["valid"] == 1
    assert summary["verdict_distribution"]["invalid"] == 1
    assert summary["verdict_distribution"]["needs_review"] == 1
    assert summary["abstain_count"] == 1
    assert summary["verdict_percentages"]["valid_pct"] == 33.33
    assert summary["compound_scenarios"]["coexisting_fail_and_review_records"] == 1

