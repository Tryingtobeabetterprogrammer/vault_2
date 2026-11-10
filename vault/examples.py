"""VAULT Mandatory Scientific Fixtures.

Implements the four mandatory fixture patterns defined in Section 5 of Vijay's Brief:
1. Arithmetic contradiction (15 mg in 0.5 L reported as 3 mg/L -> recomputes 30 mg/L, flagged).
2. Retrospective audit (later calibration report invalidates prior instrument state, append disputed assessment).
3. Valid alternative method (availability factor changes available rather than total concentration).
4. Novel method (unfamiliar formula lacks validated assumptions -> needs_review, not proof of error).
"""

from typing import Any, Dict


def get_arithmetic_contradiction_fixture() -> Dict[str, Any]:
    """Fixture 1: Direct arithmetic contradiction.
    
    Analyst reports 15 mg dissolved in 0.5 L as 3 mg/L (true value is 30 mg/L).
    Raw record remains immutable; verifier calculates 30 mg/L and flags contradiction.
    """
    return {
        "record_id": "EXP-FIX-001",
        "run_date": "2025-03-10",
        "sample_id": "SMP-0001",
        "clause_id": "CLAUSE-005",
        "sop_id": "SOP-001",
        "sop_version": "1.0",
        "instrument_id": "INST-026",
        "lot_id": "LOT-045",
        "operator_id": "OP-042",
        "reported_mass": 15.0,
        "reported_volume": 0.5,
        "measured_value": 3.0,
        "measurement_unit": "mg/L",
        "measurement_uncertainty": 0.1,
        "collected_at": "2025-03-10T08:00:00Z",
        "analyzed_at": "2025-03-10T10:00:00Z",
        "max_holding_hours": 48.0,
        "parameter": "Chloride Concentration",
        "sample_matrix": "Drinking Water",
        "site_id": "SITE-BOS",
        "site_timezone": "America/New_York",
        "original_verdict": "PASS"
    }


def get_retrospective_audit_fixture() -> Dict[str, Any]:
    """Fixture 2: Retrospective audit discovery.
    
    A routine experiment conducted on 2025-04-01 initially passed. A subsequent calibration
    audit discovers instrument drift occurred starting 2025-03-25. The original record remains
    unchanged; an append-only disputed assessment is linked to the prior assessment ID.
    """
    original_record = {
        "record_id": "EXP-FIX-002",
        "run_date": "2025-04-01",
        "sample_id": "SMP-0002",
        "clause_id": "CLAUSE-005",
        "sop_id": "SOP-001",
        "sop_version": "1.0",
        "instrument_id": "INST-026",
        "lot_id": "LOT-045",
        "operator_id": "OP-011",
        "measured_value": 24.2,
        "measurement_unit": "mg/L",
        "measurement_uncertainty": 0.2,
        "collected_at": "2025-04-01T09:00:00Z",
        "analyzed_at": "2025-04-01T11:00:00Z",
        "max_holding_hours": 48.0,
        "parameter": "Chloride Concentration",
        "sample_matrix": "Drinking Water",
        "site_id": "SITE-BOS",
        "site_timezone": "America/New_York",
        "original_verdict": "PASS"
    }

    # Audit event invalidating the instrument state for runs between 2025-03-25 and 2025-04-10
    audit_dispute = {
        "audit_event_id": "AUDIT-2025-04-15-01",
        "target_instrument_id": "INST-026",
        "drift_detected_date": "2025-03-25",
        "audit_report_date": "2025-04-15",
        "dispute_reason": "RETROSPECTIVE_CALIBRATION_DRIFT_INVALIDATION",
        "affected_record_ids": ["EXP-FIX-002"],
        "disputed_verdict": "DISPUTED"
    }

    return {
        "original_record": original_record,
        "audit_dispute": audit_dispute
    }


def get_valid_alternative_method_fixture() -> Dict[str, Any]:
    """Fixture 3: Valid alternative analytical method.
    
    Researcher applies method ALT-AVAIL-01 measuring bioavailable concentration
    (using availability factor 0.75) rather than total concentration.
    Total measured is 180 mg/L (which would exceed a total threshold of 150 mg/L),
    but bioavailable concentration is 180 * 0.75 = 135 mg/L <= 150 mg/L.
    The verifier identifies distinct measurands and avoids falsely rejecting the valid research.
    """
    return {
        "record_id": "EXP-FIX-003",
        "run_date": "2025-02-14",
        "sample_id": "SMP-0003",
        "clause_id": "CLAUSE-005",
        "sop_id": "SOP-001",
        "sop_version": "1.0",
        "instrument_id": "INST-026",
        "lot_id": "LOT-045",
        "operator_id": "OP-088",
        "method_id": "ALT-AVAIL-01",
        "measured_value": 180.0,
        "measurement_unit": "mg/L",
        "measurement_uncertainty": 5.0,
        "collected_at": "2025-02-14T08:00:00Z",
        "analyzed_at": "2025-02-14T12:00:00Z",
        "max_holding_hours": 72.0,
        "parameter": "Chloride Concentration",
        "sample_matrix": "Surface Water",
        "site_id": "SITE-BOS",
        "site_timezone": "America/New_York",
        "original_verdict": "PASS"
    }


def get_novel_method_fixture() -> Dict[str, Any]:
    """Fixture 4: Novel / unfamiliar analytical method.
    
    Researcher uses novel method 'METH-NOVEL-SPECTRO-99' lacking standard validated assumptions.
    Verifier performs safe mechanical checks (dates, instruments, units), does NOT falsely
    reject the unfamiliar science as an error, but marks verdict as 'needs_review' with
    reason code 'NOVEL_METHOD_UNVALIDATED'.
    """
    return {
        "record_id": "EXP-FIX-004",
        "run_date": "2025-03-15",
        "sample_id": "SMP-0004",
        "clause_id": "CLAUSE-005",
        "sop_id": "SOP-001",
        "sop_version": "1.0",
        "instrument_id": "INST-026",
        "lot_id": "LOT-045",
        "operator_id": "OP-099",
        "method_id": "METH-NOVEL-SPECTRO-99",
        "measured_value": 25.0,
        "measurement_unit": "mg/L",
        "measurement_uncertainty": 0.5,
        "collected_at": "2025-03-15T09:00:00Z",
        "analyzed_at": "2025-03-15T11:00:00Z",
        "max_holding_hours": 48.0,
        "parameter": "Chloride Concentration",
        "sample_matrix": "Drinking Water",
        "site_id": "SITE-BOS",
        "site_timezone": "America/New_York",
        "original_verdict": "PASS"
    }
