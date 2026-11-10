"""Unit and Integration Tests for VAULT V5 Training Data Export."""

import json
from pathlib import Path
import pytest

from data_engine.export import (
    convert_record_to_curator_sample,
    format_scientific_explanation,
    export_training_dataset,
)
from vault.verification import verify_record, get_default_catalogs


@pytest.fixture(scope="module")
def catalogs():
    return get_default_catalogs()


@pytest.fixture(scope="module")
def sample_valid_record():
    return {
        "experiment_id": "EXP-V5-TEST",
        "record_id": "EXP-V5-TEST",
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


def test_format_scientific_explanation(sample_valid_record, catalogs):
    """Verify that assistant response includes all 5 deterministic rule checks."""
    asm = verify_record(sample_valid_record, catalogs)
    assert asm["status"] == "checks_passed"

    explanation = format_scientific_explanation(sample_valid_record, asm)
    assert "Scientific Compliance Verification for EXP-V5-TEST" in explanation
    assert "1. Standard Operating Procedure:" in explanation
    assert "2. Equipment Calibration" in explanation
    assert "3. Reagent Quality" in explanation
    assert "4. Sample Integrity" in explanation
    assert "5. Measurement & Uncertainty:" in explanation
    assert "COMPLIANT (PASS)" in explanation


def test_sample_conversion_chatml_structure(sample_valid_record, catalogs):
    """Verify prompt formatting for Tiny Aya ChatML."""
    asm = verify_record(sample_valid_record, catalogs)
    sample = convert_record_to_curator_sample(sample_valid_record, asm, catalogs)

    assert "instruction" in sample
    assert "input" in sample
    assert "output" in sample
    assert "EXP-V5-TEST" in sample["input"]
    assert "Chloride Concentration" in sample["instruction"]

    # Assert ground truth isolation
    for forbidden in ["truth_ledger", "expected_defect", "is_corrupted"]:
        assert forbidden not in sample["input"]
        assert forbidden not in sample["output"]


def test_export_pipeline_execution(tmp_path):
    """Verify complete export pipeline writes all 5 expected artifacts."""
    out_dir = tmp_path / "v5_export_test"
    records_file = Path("data/synthetic/records.jsonl")

    res = export_training_dataset(
        records_path=records_file,
        output_dir=out_dir,
    )

    assert res["total_source_records"] == 1200
    assert res["accepted_candidates_count"] == 720
    assert res["quarantined_count"] == 480
    assert res["curator_passed_count"] == 720

    # Check generated files exist and are non-empty
    for fname in ["train_candidates.jsonl", "accepted_manifest.json", "quarantine.jsonl", "dataset_card.md", "checksums.txt"]:
        fpath = out_dir / fname
        assert fpath.exists(), f"Missing artifact: {fname}"
        assert fpath.stat().st_size > 0, f"Empty artifact: {fname}"

    # Verify train_candidates has exactly 720 records
    with open(out_dir / "train_candidates.jsonl", "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]
    assert len(lines) == 720

    # Verify quarantine has exactly 480 records
    with open(out_dir / "quarantine.jsonl", "r", encoding="utf-8") as f:
        quarantine = [json.loads(line) for line in f if line.strip()]
    assert len(quarantine) == 480

