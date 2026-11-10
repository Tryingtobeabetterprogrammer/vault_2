"""Unit tests for VAULT V4 Corruption Benchmark Suite."""

import copy
import json
from pathlib import Path
import pytest

from data_engine.curation import (
    inject_corruption,
    build_corruption_dataset,
    run_full_corruption_benchmark,
    CORRUPTION_TYPES,
)
from vault.verification import verify_record, get_default_catalogs


@pytest.fixture(scope="module")
def sample_valid_record():
    """A clean, known valid experiment record."""
    return {
        "experiment_id": "EXP-TEST-001",
        "record_id": "EXP-TEST-001",
        "run_date": "2025-01-15",
        "sop_id": "SOP-001",
        "sop_version": "1.0",
        "clause_id": "CLAUSE-005",
        "instrument_id": "INST-026",
        "lot_id": "LOT-045",
        "sample_id": "SMP-0001",
        "site_id": "SITE-BOS",
        "site_timezone": "America/New_York",
        "parameter": "Chloride Concentration",
        "measured_value": 25.0,
        "measurement_unit": "mg/L",
        "measurement_uncertainty": 0.5,
        "collected_at": "2025-01-15T08:00:00Z",
        "analyzed_at": "2025-01-15T12:00:00Z",
        "max_holding_hours": 48.0,
        "scenario_family": "Nominal valid",
        "original_verdict": "PASS"
    }


@pytest.fixture(scope="module")
def catalogs():
    return get_default_catalogs()


def test_corruption_immutability(sample_valid_record):
    """Assert original records are never modified in-place during corruption injection."""
    original_copy = copy.deepcopy(sample_valid_record)
    for c_type in CORRUPTION_TYPES:
        corr_rec, meta = inject_corruption(sample_valid_record, c_type)
        assert sample_valid_record == original_copy, f"Original record was mutated during {c_type}"
        assert corr_rec["experiment_id"] != sample_valid_record["experiment_id"]
        assert meta["is_corrupted"] is True
        assert meta["corruption_type"] == c_type


def test_all_five_corruption_types_detected_by_vault(sample_valid_record, catalogs):
    """Assert that VAULT's deterministic verifier detects all 5 mandatory corruption types."""
    expected_reasons = {
        "wrong_arithmetic": "ARITHMETIC_CONTRADICTION",
        "missing_context": ["MISSING_REQUIRED_EVIDENCE", "MISSING_SAMPLE_EVIDENCE", "MISSING_SOP_EVIDENCE", "MISSING_INSTRUMENT_EVIDENCE"],
        "wrong_sop_version": "SOP_VERSION_INVALID",
        "false_verdict": "MEASUREMENT_OUT_OF_RANGE",
        "unsupported_claim": "NOVEL_METHOD_UNVALIDATED",
    }

    for c_type, expected_code in expected_reasons.items():
        corr_rec, _ = inject_corruption(sample_valid_record, c_type)
        res = verify_record(corr_rec, catalogs)

        assert res["status"] in ("flagged", "needs_review"), f"Corruption {c_type} passed unexpectedly!"
        assert res["verdict"] in ("invalid", "needs_review")

        if isinstance(expected_code, list):
            assert any(code in res["issues"] for code in expected_code), (
                f"None of {expected_code} found in {res['issues']} for {c_type}"
            )
        else:
            assert expected_code in res["issues"], f"Expected {expected_code} in {res['issues']} for {c_type}"


def test_clean_control_never_triggers_false_positive(sample_valid_record, catalogs):
    """Assert clean valid controls are never flagged (0% False Positive Rate)."""
    res = verify_record(sample_valid_record, catalogs)
    assert res["status"] == "checks_passed"
    assert res["verdict"] == "valid"
    assert res["abstain"] is False
    assert len(res["issues"]) == 0


def test_full_benchmark_execution(tmp_path):
    """Execute full corruption benchmark and verify output metrics."""
    out_dir = tmp_path / "benchmark"
    rep_dir = tmp_path / "reports"

    report = run_full_corruption_benchmark(
        output_dir=out_dir,
        reports_dir=rep_dir,
        seed=42,
    )

    # Validate output files exist
    assert (rep_dir / "corruption_benchmark_report.json").exists()
    assert (rep_dir / "corruption_benchmark_summary.md").exists()
    assert (out_dir / "corrupted_benchmark_records.jsonl").exists()

    # Validate metrics
    summary = report["benchmark_summary"]
    assert summary["total_records_evaluated"] > 100
    assert summary["coverage_pct"] == 100.0

    vg = report["vault_verification_gate"]
    assert vg["precision"] == 1.0  # 100% precision
    assert vg["recall"] >= 0.95    # >= 95% recall
    assert vg["false_positive_rate"] == 0.0  # 0% FPR

