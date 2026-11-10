"""Tests for the integrated CuratorKIT library and VAULT pipeline."""

import json
from pathlib import Path
import pytest

from data_engine.curation import (
    convert_record_to_curator_sample,
    detect_and_read_curatorkit_dataset,
    run_curatorkit_curation_pipeline,
    execute_integrated_vault_curator_pipeline,
    check_optional_hygiene_availability,
)
from vault.verification import verify_record, get_default_catalogs


@pytest.fixture(scope="module")
def catalogs():
    return get_default_catalogs()


@pytest.fixture(scope="module")
def sample_valid_record():
    return {
        "experiment_id": "EXP-INT-001",
        "record_id": "EXP-INT-001",
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


def test_curatorkit_library_imports():
    """Verify official CuratorKIT package imports cleanly without errors."""
    import curatorkit
    from curatorkit import Curator, CuratorConfig, CuratorResult
    from curatorkit.detection.detector import FormatDetector
    from curatorkit.connectors.jsonl import JSONLReader
    from curatorkit.gates.schema import SchemaGate
    from curatorkit.normalizers.clean import TextCleaner
    from curatorkit.normalizers.dedup import ExactDeduplicator, MinHashDeduplicator
    from curatorkit.exporters.messages import MessagesExporter
    from curatorkit.manifest import ProvenanceManifest

    assert curatorkit.__version__ == "0.1.21"
    assert Curator is not None
    assert FormatDetector is not None


def test_optional_hygiene_dependency_detection():
    """Verify clean reporting of optional hygiene packages on 8GB CPU environment."""
    avail = check_optional_hygiene_availability()
    assert isinstance(avail, dict)
    assert "secrets_gate" in avail
    assert "pii_pseudonymizer" in avail


def test_record_to_curatorkit_sample_conversion(sample_valid_record):
    """Verify that lab records convert to instruction-following samples without truth labels."""
    sample = convert_record_to_curator_sample(sample_valid_record)
    assert "instruction" in sample
    assert "input" in sample
    assert "output" in sample
    assert "EXP-INT-001" in sample["input"]
    # Verify ground-truth ledger fields are NOT present
    assert "truth_ledger" not in sample
    assert "expected_verdict" not in sample
    assert "expected_defect" not in sample


def test_format_detector_and_reader(tmp_path, sample_valid_record):
    """Verify CuratorKIT FormatDetector and JSONLReader on converted sample data."""
    sample_file = tmp_path / "test_samples.jsonl"
    sample = convert_record_to_curator_sample(sample_valid_record)
    with open(sample_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(sample) + "\n")

    samples, rejections = detect_and_read_curatorkit_dataset(sample_file)
    assert len(samples) == 1
    assert len(rejections) == 0
    assert samples[0].task_type == "instruction_following"


def test_integrated_pipeline_execution(tmp_path, catalogs, sample_valid_record):
    """Verify the integrated pipeline runs end-to-end and produces all required artifacts."""
    records = [sample_valid_record]
    output_dir = tmp_path / "pipeline_out"

    summary = execute_integrated_vault_curator_pipeline(
        records=records,
        output_base_dir=output_dir,
        catalogs=catalogs,
        enable_minhash=False,
    )

    assert summary["input_record_count"] == 1
    assert summary["vault_verification"]["accepted_count"] == 1
    assert summary["curatorkit_curation"]["curator_passed_count"] == 1

    # Verify artifacts exist
    assert Path(summary["artifacts"]["trainer_ready_dataset"]).exists()
    assert Path(summary["artifacts"]["curator_manifest"]).exists()
    assert Path(summary["artifacts"]["curator_checksums"]).exists()
    assert Path(summary["artifacts"]["curator_dataset_card"]).exists()
    assert Path(summary["artifacts"]["quarantine_ledger"]).exists()

