"""Dedicated Regression and Verification Test Suite for VAULT V3 Immutable Scientific Memory.

Tests cover all 8 mandatory verification areas:
1. test_original_source_hash_unchanged_after_correction
2. test_assessments_are_append_only
3. test_retrospective_calibration_audit_preserves_original_pass
4. test_supersession_relationship
5. test_assessment_metadata_preservation
6. test_history_retrieval_chronological
7. test_duplicate_ingestion_idempotent
8. test_assessment_retry_idempotent
9. test_concurrent_assessment_writes
"""

import concurrent.futures
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import pytest
from jsonschema import validate

from vault.memory import ScientificMemory
from vault.verification import verify_record, get_default_catalogs
from vault.examples import (
    get_arithmetic_contradiction_fixture,
    get_retrospective_audit_fixture,
    get_valid_alternative_method_fixture,
    get_novel_method_fixture,
)


@pytest.fixture(scope="module")
def catalogs():
    return get_default_catalogs()


@pytest.fixture(scope="module")
def assessment_schema():
    schema_path = Path("contracts/assessment.schema.json")
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def sample_record():
    return {
        "record_id": "EXP-MEM-001",
        "run_date": "2025-01-15",
        "sample_id": "SMP-0001",
        "clause_id": "CLAUSE-005",
        "sop_id": "SOP-001",
        "sop_version": "1.0",
        "instrument_id": "INST-026",
        "lot_id": "LOT-045",
        "operator_id": "OP-042",
        "measured_value": 25.0,
        "measurement_unit": "mg/L",
        "measurement_uncertainty": 0.5,
        "collected_at": "2025-01-15T08:00:00Z",
        "analyzed_at": "2025-01-15T12:00:00Z",
        "max_holding_hours": 48.0,
        "parameter": "Chloride Concentration",
        "sample_matrix": "Drinking Water",
        "site_id": "SITE-BOS",
        "site_timezone": "America/New_York",
        "original_verdict": "PASS"
    }


def test_original_source_hash_unchanged_after_correction(tmp_path, sample_record, catalogs, assessment_schema):
    """Step 2: Verify original source immutability across subsequent audits and corrections."""
    memory = ScientificMemory(storage_dir=str(tmp_path / "memory"))

    # 1. Ingest scientific record
    initial_payload = copy.deepcopy(sample_record)
    source_entry = memory.register_source(sample_record["record_id"], initial_payload)
    original_sha256 = source_entry["source_hash"]

    # 2. Run verifier and create initial assessment
    initial_assessment = verify_record(sample_record, catalogs)
    validate(instance=initial_assessment, schema=assessment_schema)
    memory.record_assessment(initial_assessment)

    # 3. Perform subsequent audit/dispute correction
    dispute_asm = memory.record_retrospective_dispute(
        record_id=sample_record["record_id"],
        prior_assessment_id=initial_assessment["assessment_id"],
        dispute_reason="RETROSPECTIVE_CALIBRATION_DRIFT_INVALIDATION",
        audit_event_id="AUDIT-2025-01-99",
        reviewer="Audit-Lead-001"
    )
    validate(instance=dispute_asm, schema=assessment_schema)

    # 4. Retrieve original record from memory
    retrieved_source = memory.get_source(sample_record["record_id"])
    assert retrieved_source is not None

    # 5. Recompute SHA-256 and assert exact byte/payload identity
    recomputed_sha256 = memory.compute_sha256(retrieved_source["raw_payload"])
    assert recomputed_sha256 == original_sha256
    assert retrieved_source["raw_payload"] == initial_payload

    # 6. Verify that mutation attempt on source raises an error
    tampered_payload = copy.deepcopy(initial_payload)
    tampered_payload["measured_value"] = 9999.0
    with pytest.raises(ValueError, match="Source immutability violation"):
        memory.register_source(sample_record["record_id"], tampered_payload)


def test_assessments_are_append_only(tmp_path, sample_record, catalogs, assessment_schema):
    """Step 3: Verify append-only assessment history without destructive overwrites."""
    memory = ScientificMemory(storage_dir=str(tmp_path / "memory"))

    # Initial PASS assessment
    init_asm = verify_record(sample_record, catalogs)
    assert init_asm["status"] == "checks_passed"
    memory.record_assessment(init_asm)

    # Subsequent dispute assessment
    dispute_asm = memory.record_retrospective_dispute(
        record_id=sample_record["record_id"],
        prior_assessment_id=init_asm["assessment_id"],
        dispute_reason="AUDIT_INSTRUMENT_DISCREPANCY",
        audit_event_id="AUDIT-2025-DISP-01"
    )

    history = memory.get_history(sample_record["record_id"])
    assert len(history) == 2

    # Original PASS assessment remains stored and unchanged
    assert history[0]["assessment_id"] == init_asm["assessment_id"]
    assert history[0]["status"] == "checks_passed"
    assert history[0]["verdict"] == "valid"

    # New assessment has its own unique ID and supersedes the prior
    assert history[1]["assessment_id"] == dispute_asm["assessment_id"]
    assert history[1]["assessment_id"] != init_asm["assessment_id"]
    assert history[1]["supersedes_id"] == init_asm["assessment_id"]
    assert history[1]["status"] == "flagged"
    assert history[1]["verdict"] == "invalid"


def test_retrospective_calibration_audit_preserves_original_pass(tmp_path, catalogs, assessment_schema):
    """Step 4: Mandatory retrospective calibration audit scenario."""
    memory = ScientificMemory(storage_dir=str(tmp_path / "memory"))
    fixture_data = get_retrospective_audit_fixture()
    orig_record = fixture_data["original_record"]
    audit_dispute = fixture_data["audit_dispute"]

    # 1. Store source and initial pass
    memory.register_source(orig_record["record_id"], orig_record)
    init_asm = verify_record(orig_record, catalogs)
    assert init_asm["status"] == "checks_passed"
    memory.record_assessment(init_asm)

    # 2. Retrospective calibration audit occurs
    disp_asm = memory.record_retrospective_dispute(
        record_id=orig_record["record_id"],
        prior_assessment_id=init_asm["assessment_id"],
        dispute_reason=audit_dispute["dispute_reason"],
        audit_event_id=audit_dispute["audit_event_id"],
        reviewer="Lead-Auditor"
    )

    # 3. Retrieve history and assert complete preservation
    history = memory.get_history(orig_record["record_id"])
    assert len(history) == 2

    # Original PASS is intact
    assert history[0]["assessment_id"] == init_asm["assessment_id"]
    assert history[0]["verdict"] == "valid"

    # New dispute assessment cites calibration audit
    assert history[1]["supersedes_id"] == init_asm["assessment_id"]
    assert history[1]["verdict"] == "invalid"
    audit_ev = [e for e in history[1]["evidence"] if e["rule_name"] == "retrospective_calibration_audit"][0]
    assert audit_ev["status"] == "fail"
    assert audit_ev["details"]["audit_event_id"] == audit_dispute["audit_event_id"]
    assert f"audit_event:{audit_dispute['audit_event_id']}" in audit_ev["evidence_refs"]


def test_supersession_relationship(tmp_path, sample_record, catalogs):
    """Verify clean single-link and multi-link supersession chains."""
    memory = ScientificMemory(storage_dir=str(tmp_path / "memory"))
    rec_id = sample_record["record_id"]

    # Assessment 1: initial pass
    asm1 = verify_record(sample_record, catalogs, assessment_id="ASM-CHAIN-001")
    memory.record_assessment(asm1)

    # Assessment 2: audit dispute 1 supersedes 1
    asm2 = memory.record_retrospective_dispute(
        record_id=rec_id,
        prior_assessment_id="ASM-CHAIN-001",
        dispute_reason="RECALIBRATION_DRIFT",
        audit_event_id="AUDIT-CHAIN-01"
    )
    assert asm2["supersedes_id"] == "ASM-CHAIN-001"

    # Assessment 3: secondary review supersedes 2
    asm3 = memory.record_retrospective_dispute(
        record_id=rec_id,
        prior_assessment_id=asm2["assessment_id"],
        dispute_reason="SECONDARY_ARBITRATION",
        audit_event_id="AUDIT-CHAIN-02"
    )
    assert asm3["supersedes_id"] == asm2["assessment_id"]

    history = memory.get_history(rec_id)
    assert len(history) == 3
    assert history[0]["assessment_id"] == "ASM-CHAIN-001"
    assert history[1]["assessment_id"] == asm2["assessment_id"]
    assert history[2]["assessment_id"] == asm3["assessment_id"]
    assert memory.get_latest_assessment(rec_id)["assessment_id"] == asm3["assessment_id"]


def test_assessment_metadata_preservation(tmp_path, sample_record, catalogs, assessment_schema):
    """Step 5: Verify all assessment metadata fields are preserved upon retrieval."""
    memory = ScientificMemory(storage_dir=str(tmp_path / "memory"))

    asm = verify_record(sample_record, catalogs)
    memory.record_assessment(asm)

    retrieved = memory.get_latest_assessment(sample_record["record_id"])
    assert retrieved is not None

    # Required fields per assessment.schema.json
    required_fields = [
        "assessment_id",
        "record_id",
        "status",
        "abstain",
        "issues",
        "evidence",
        "derived",
        "engine_version",
        "created_at",
    ]
    for rf in required_fields:
        assert rf in retrieved, f"Missing required metadata field: {rf}"

    # Verify schema compliance
    validate(instance=retrieved, schema=assessment_schema)


def test_history_retrieval_chronological(tmp_path, sample_record, catalogs):
    """Step 6: Verify chronological ordering and unified event timeline."""
    memory = ScientificMemory(storage_dir=str(tmp_path / "memory"))
    rec_id = sample_record["record_id"]

    # Event 1: Source registration
    memory.register_source(rec_id, sample_record)

    # Event 2: Initial assessment
    asm1 = verify_record(sample_record, catalogs, assessment_id="ASM-CHRONO-1")
    memory.record_assessment(asm1)

    # Event 3: Retrospective dispute
    asm2 = memory.record_retrospective_dispute(
        record_id=rec_id,
        prior_assessment_id="ASM-CHRONO-1",
        dispute_reason="AUDIT_DISPUTE_EVENT",
        audit_event_id="AUDIT-CHRONO-99"
    )

    # Retrieve unified timeline
    timeline = memory.get_full_event_timeline(rec_id)
    assert len(timeline) == 3
    assert timeline[0]["event_type"] == "source_registered"
    assert timeline[1]["event_type"] == "assessment_recorded"
    assert timeline[2]["event_type"] == "assessment_recorded"

    # Verify chronological order
    t0 = timeline[0]["timestamp"]
    t1 = timeline[1]["timestamp"]
    t2 = timeline[2]["timestamp"]
    assert t0 <= t1 <= t2


def test_duplicate_ingestion_idempotent(tmp_path, sample_record):
    """Step 7a: Verify source registration idempotency on identical payload."""
    memory = ScientificMemory(storage_dir=str(tmp_path / "memory"))
    rec_id = sample_record["record_id"]

    s1 = memory.register_source(rec_id, sample_record)
    s2 = memory.register_source(rec_id, sample_record)

    assert s1["source_hash"] == s2["source_hash"]
    assert s1["registered_at"] == s2["registered_at"]

    # Verify persistence file only contains 1 entry
    with open(memory.sources_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    assert len(lines) == 1


def test_assessment_retry_idempotent(tmp_path, sample_record, catalogs):
    """Step 7b: Verify assessment recording retry idempotency."""
    memory = ScientificMemory(storage_dir=str(tmp_path / "memory"))
    asm = verify_record(sample_record, catalogs, assessment_id="ASM-RETRY-001")

    # Record twice
    r1 = memory.record_assessment(asm)
    r2 = memory.record_assessment(asm)

    assert r1["assessment_id"] == r2["assessment_id"]
    history = memory.get_history(sample_record["record_id"])
    assert len(history) == 1


def test_concurrent_assessment_writes(tmp_path, catalogs):
    """Step 8: Verify thread safety and concurrent write integrity."""
    memory = ScientificMemory(storage_dir=str(tmp_path / "memory"))
    num_threads = 10
    writes_per_thread = 5

    def worker(worker_id: int):
        results = []
        for i in range(writes_per_thread):
            rec_id = f"EXP-CONCUR-{worker_id % 3}"  # Multiple writes across shared record IDs
            asm_id = f"ASM-W{worker_id}-I{i}"
            record = {
                "record_id": rec_id,
                "measured_value": 10.0 + i,
                "measurement_unit": "mg/L",
                "run_date": "2025-01-15",
                "clause_id": "CLAUSE-005",
                "sop_id": "SOP-001",
                "sop_version": "1.0",
                "instrument_id": "INST-026",
                "lot_id": "LOT-045",
                "sample_id": "SMP-0001",
                "operator_id": "OP-CONCUR",
                "collected_at": "2025-01-15T08:00:00Z",
                "analyzed_at": "2025-01-15T10:00:00Z",
            }
            asm = verify_record(record, catalogs, assessment_id=asm_id)
            res = memory.record_assessment(asm)
            results.append(res)
        return results

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, wid) for wid in range(num_threads)]
        all_results = [f.result() for f in concurrent.futures.as_completed(futures)]

    total_expected_writes = num_threads * writes_per_thread

    # Check persistence file contains all written entries without corruption
    with open(memory.assessments_file, "r", encoding="utf-8") as f:
        stored_lines = [json.loads(line) for line in f if line.strip()]

    assert len(stored_lines) == total_expected_writes
    all_stored_ids = {item["assessment_id"] for item in stored_lines}
    assert len(all_stored_ids) == total_expected_writes  # Every assessment ID is unique and accounted for

    # Check that each record's history is cleanly retrievable
    for rid in ["EXP-CONCUR-0", "EXP-CONCUR-1", "EXP-CONCUR-2"]:
        hist = memory.get_history(rid)
        assert len(hist) > 0
        # Assert strictly sorted chronologically
        timestamps = [h.get("recorded_at") for h in hist]
        assert timestamps == sorted(timestamps)

