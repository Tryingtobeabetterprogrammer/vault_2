"""Test Suite for V4 Teacher-Text Round-Trip Verification Engine.

Tests:
1. Verification of 100% compliant teacher text.
2. Rejection of altered/wrong numerical values.
3. Rejection of incompatible units.
4. Acceptance of valid equivalent units via metric conversion.
5. Rejection of incorrect execution dates.
6. Rejection of omitted critical context.
7. Rejection of unsupported compliance claims on defective truth records.
8. Routing of ambiguous or ID-lacking text to needs_review.
9. Gatekeeper function blocking unverified candidates from training sets.
10. Precision and recall evaluation on benchmark fixtures.
"""

from pathlib import Path
import pytest

from data_engine.roundtrip import (
    TeacherTextVerifier,
    gate_teacher_candidate,
    extract_teacher_claims,
    REASON_NUMERICAL_MISMATCH,
    REASON_UNIT_MISMATCH,
    REASON_DATE_MISMATCH,
    REASON_MISSING_CRITICAL_FIELD,
    REASON_UNSUPPORTED_COMPLIANCE_CLAIM,
    REASON_VERDICT_MISMATCH,
    REASON_MISSING_EXPERIMENT_ID,
)
from data_engine.fixtures_roundtrip import get_roundtrip_fixtures


@pytest.fixture(scope="module")
def verifier():
    return TeacherTextVerifier(truth_ledger_path="data/synthetic/truth_ledger.jsonl")


@pytest.fixture(scope="module")
def fixtures():
    return get_roundtrip_fixtures()


def test_correct_compliant_explanation_passes(verifier, fixtures):
    """Scenario 1: Verified compliant explanation passes with 0 reason codes."""
    f = fixtures["correct_compliant"]
    res = verifier.verify_explanation(f["text"])

    assert res.status == "passed"
    assert res.passed is True
    assert res.quarantined is False
    assert res.reason_codes == []
    assert res.experiment_id == "EXP-0046"


def test_wrong_numerical_value_rejected(verifier, fixtures):
    """Scenario 2: Altered numerical values are detected and rejected."""
    f = fixtures["wrong_numerical_value"]
    res = verifier.verify_explanation(f["text"])

    assert res.status == "rejected"
    assert res.passed is False
    assert res.quarantined is True
    assert REASON_NUMERICAL_MISMATCH in res.reason_codes
    assert len(res.discrepancies) > 0


def test_wrong_units_rejected(verifier, fixtures):
    """Scenario 3: Incompatible measurement units are detected and rejected."""
    f = fixtures["wrong_units"]
    res = verifier.verify_explanation(f["text"])

    assert res.status == "rejected"
    assert res.passed is False
    assert res.quarantined is True
    assert REASON_UNIT_MISMATCH in res.reason_codes


def test_equivalent_valid_units_accepted(verifier, fixtures):
    """Scenario 4: Equivalent valid units (ug/L -> mg/L) convert and pass."""
    f = fixtures["equivalent_valid_units"]
    res = verifier.verify_explanation(f["text"])

    assert res.status == "passed"
    assert res.passed is True
    assert res.quarantined is False
    assert res.reason_codes == []


def test_incorrect_date_rejected(verifier, fixtures):
    """Scenario 5: Contradictory execution dates trigger date mismatch rejection."""
    f = fixtures["incorrect_date"]
    res = verifier.verify_explanation(f["text"])

    assert res.status == "rejected"
    assert res.passed is False
    assert res.quarantined is True
    assert REASON_DATE_MISMATCH in res.reason_codes


def test_missing_context_rejected(verifier, fixtures):
    """Scenario 6: Omission of required validation dimensions is quarantined."""
    f = fixtures["missing_context"]
    res = verifier.verify_explanation(f["text"])

    assert res.status == "rejected"
    assert res.passed is False
    assert res.quarantined is True
    assert REASON_MISSING_CRITICAL_FIELD in res.reason_codes


def test_unsupported_compliance_claim_rejected(verifier, fixtures):
    """Scenario 7: Hallucinated compliance on defective records is rejected."""
    f = fixtures["unsupported_claim"]
    res = verifier.verify_explanation(f["text"])

    assert res.status == "rejected"
    assert res.passed is False
    assert res.quarantined is True
    assert REASON_VERDICT_MISMATCH in res.reason_codes or REASON_UNSUPPORTED_COMPLIANCE_CLAIM in res.reason_codes


def test_ambiguous_text_needs_review(verifier, fixtures):
    """Scenario 8: Ambiguous text lacking record ID routes to needs_review."""
    f = fixtures["ambiguous_text"]
    res = verifier.verify_explanation(f["text"])

    assert res.status == "needs_review"
    assert res.passed is False
    assert res.quarantined is True
    assert REASON_MISSING_EXPERIMENT_ID in res.reason_codes


def test_gatekeeper_prevents_unverified_training_admission(fixtures):
    """Scenario 9: Gatekeeper blocks defective or ambiguous candidate explanations."""
    # Compliant fixture passes gate
    pass_ok, pass_res = gate_teacher_candidate(fixtures["correct_compliant"]["text"])
    assert pass_ok is True
    assert pass_res.status == "passed"

    # Equivalent unit fixture passes gate
    eq_ok, eq_res = gate_teacher_candidate(fixtures["equivalent_valid_units"]["text"])
    assert eq_ok is True
    assert eq_res.status == "passed"

    # Defective fixtures fail gate
    for key in ["wrong_numerical_value", "wrong_units", "incorrect_date", "missing_context", "unsupported_claim", "ambiguous_text"]:
        gate_ok, gate_res = gate_teacher_candidate(fixtures[key]["text"])
        assert gate_ok is False, f"Fixture '{key}' was incorrectly admitted through gate!"
        assert gate_res.quarantined is True


def test_roundtrip_precision_and_recall(verifier, fixtures):
    """Scenario 10: Calculate precision and recall across all synthetic fixtures."""
    tp, fp, tn, fn = 0, 0, 0, 0

    for name, fix in fixtures.items():
        res = verifier.verify_explanation(fix["text"])
        is_actually_valid = fix["expected_passed"]
        predicted_valid = res.passed

        if is_actually_valid and predicted_valid:
            tp += 1
        elif not is_actually_valid and not predicted_valid:
            tn += 1
        elif not is_actually_valid and predicted_valid:
            fp += 1
        elif is_actually_valid and not predicted_valid:
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0

    assert precision == 1.0, f"Precision fell below 100%: {precision}"
    assert recall == 1.0, f"Recall fell below 100%: {recall}"
    assert fp == 0
    assert fn == 0

