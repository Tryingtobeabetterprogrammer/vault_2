"""Unit tests for VAULT Core Deterministic Verifier and Immutable Scientific Memory."""

from datetime import datetime, timezone
import json
from pathlib import Path
import pytest
from jsonschema import validate

from vault.verification import verify_record, get_default_catalogs
from vault.memory import ScientificMemory
from vault.examples import (
    get_arithmetic_contradiction_fixture,
    get_retrospective_audit_fixture,
    get_valid_alternative_method_fixture,
    get_novel_method_fixture,
)


@pytest.fixture(scope="module")
def assessment_schema():
    """Load formal assessment JSON schema for validation."""
    schema_path = Path("contracts/assessment.schema.json")
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def catalogs():
    """Load default laboratory catalogs."""
    return get_default_catalogs()


def test_fixture_1_arithmetic_contradiction(catalogs, assessment_schema):
    """Case 1: 15 mg / 0.5 L reported as 3 mg/L -> recomputes 30 mg/L, flagged."""
    record = get_arithmetic_contradiction_fixture()
    assessment = verify_record(record, catalogs)

    # Validate against JSON schema
    validate(instance=assessment, schema=assessment_schema)

    assert assessment["record_id"] == "EXP-FIX-001"
    assert assessment["status"] == "flagged"
    assert assessment["verdict"] == "invalid"
    assert "ARITHMETIC_CONTRADICTION" in assessment["issues"]

    # Verify arithmetic calculation evidence
    arith_ev = [e for e in assessment["evidence"] if e["rule_name"] == "arithmetic_verification"][0]
    assert arith_ev["status"] == "fail"
    assert arith_ev["details"]["expected_concentration_mg_L"] == 30.0
    assert arith_ev["details"]["reported_concentration"] == 3.0

    # Ensure raw record remains unchanged
    assert record["measured_value"] == 3.0
    assert record["reported_mass"] == 15.0
    assert record["reported_volume"] == 0.5


def test_fixture_2_retrospective_audit(tmp_path, catalogs, assessment_schema):
    """Case 2: Subsequent calibration audit invalidates prior instrument state."""
    memory = ScientificMemory(storage_dir=str(tmp_path / "memory"))
    fixture_data = get_retrospective_audit_fixture()
    original_record = fixture_data["original_record"]
    audit_dispute = fixture_data["audit_dispute"]

    # 1. Initial ingestion & verification: experiment passes
    source_entry = memory.register_source(original_record["record_id"], original_record)
    init_hash = source_entry["source_hash"]

    initial_assessment = verify_record(original_record, catalogs)
    validate(instance=initial_assessment, schema=assessment_schema)
    assert initial_assessment["status"] == "checks_passed"
    assert initial_assessment["verdict"] == "valid"

    memory.record_assessment(initial_assessment)

    # 2. Retrospective calibration audit occurs weeks later
    disputed_assessment = memory.record_retrospective_dispute(
        record_id=original_record["record_id"],
        prior_assessment_id=initial_assessment["assessment_id"],
        dispute_reason="RETROSPECTIVE_CALIBRATION_DRIFT_INVALIDATION",
        audit_event_id=audit_dispute["audit_event_id"],
        reviewer="Auditor-Lead-007"
    )
    validate(instance=disputed_assessment, schema=assessment_schema)

    # 3. Assert provenance & immutability guarantees
    # Prior assessment remains unchanged in memory
    history = memory.get_history(original_record["record_id"])
    assert len(history) == 2
    assert history[0]["assessment_id"] == initial_assessment["assessment_id"]
    assert history[0]["status"] == "checks_passed"
    assert history[0]["verdict"] == "valid"

    # Disputed assessment supersedes prior assessment
    assert history[1]["assessment_id"] == disputed_assessment["assessment_id"]
    assert history[1]["supersedes_id"] == initial_assessment["assessment_id"]
    assert history[1]["status"] == "flagged"
    assert history[1]["verdict"] == "invalid"
    assert "RETROSPECTIVE_CALIBRATION_DRIFT_INVALIDATION" in history[1]["issues"]

    # Original raw record source hash is strictly unchanged
    refetched_source = memory.get_source(original_record["record_id"])
    assert refetched_source["source_hash"] == init_hash
    assert refetched_source["raw_payload"]["measured_value"] == 24.2


def test_fixture_3_valid_alternative_method(catalogs, assessment_schema):
    """Case 3: Alternative method measures bioavailable concentration (distinct measurand)."""
    record = get_valid_alternative_method_fixture()
    assessment = verify_record(record, catalogs)
    validate(instance=assessment, schema=assessment_schema)

    # Must NOT falsely reject valid alternative research
    assert assessment["record_id"] == "EXP-FIX-003"
    assert assessment["status"] == "checks_passed"
    assert assessment["verdict"] == "valid"
    assert assessment["abstain"] is False

    method_ev = [e for e in assessment["evidence"] if e["rule_name"] == "method_verification"][0]
    assert method_ev["status"] == "pass"
    assert method_ev["details"]["measurand"] == "bioavailable_concentration"
    assert method_ev["details"]["calculated_available_concentration"] == 135.0


def test_fixture_4_novel_method(catalogs, assessment_schema):
    """Case 4: Novel method without validated assumptions -> needs_review, not proof of error."""
    record = get_novel_method_fixture()
    assessment = verify_record(record, catalogs)
    validate(instance=assessment, schema=assessment_schema)

    assert assessment["record_id"] == "EXP-FIX-004"
    assert assessment["status"] == "needs_review"
    assert assessment["verdict"] == "needs_review"
    assert assessment["abstain"] is True
    assert "NOVEL_METHOD_UNVALIDATED" in assessment["issues"]

    method_ev = [e for e in assessment["evidence"] if e["rule_name"] == "method_verification"][0]
    assert method_ev["status"] == "needs_review"
    assert method_ev["reason"] == "NOVEL_METHOD_UNVALIDATED"


def test_memory_idempotency_and_immutability(tmp_path):
    """Test idempotent writes and immutability enforcement in ScientificMemory."""
    memory = ScientificMemory(storage_dir=str(tmp_path / "mem"))
    doc = {"sample_id": "SMP-001", "concentration": 12.5}

    # First registration
    s1 = memory.register_source("DOC-1", doc)
    assert s1["source_id"] == "DOC-1"

    # Idempotent re-registration of identical content returns existing
    s2 = memory.register_source("DOC-1", doc)
    assert s2["source_hash"] == s1["source_hash"]

    # Mutation attempt raises error
    mutated = {"sample_id": "SMP-001", "concentration": 999.9}
    with pytest.raises(ValueError, match="Source immutability violation"):
        memory.register_source("DOC-1", mutated)
