"""Comprehensive unit test suite for VAULT V2 Deterministic Rules Engine."""

from datetime import date, datetime, timezone
import pytest

from synth import rules_v2
from synth.rules_v2 import (
    validate_sop_v2,
    validate_calibration_v2,
    validate_lot_v2,
    validate_holding_time_v2,
    validate_measurement_v2,
    REASON_SOP_VERSION_INVALID,
    REASON_SOP_VERSION_CONFLICT,
    REASON_MISSING_SOP_EVIDENCE,
    REASON_MISSING_SOP_VERSION,
    REASON_CALIBRATION_EXPIRED,
    REASON_CALIBRATION_NOT_YET_VALID,
    REASON_MISSING_INSTRUMENT_EVIDENCE,
    REASON_LOT_EXPIRED,
    REASON_LOT_NOT_YET_VALID,
    REASON_MISSING_REAGENT_EVIDENCE,
    REASON_HOLDING_TIME_EXCEEDED,
    REASON_INVALID_TIMESTAMP_ORDER,
    REASON_MISSING_SAMPLE_EVIDENCE,
    REASON_AMBIGUOUS_TIMEZONE,
    REASON_MEASUREMENT_OUT_OF_RANGE,
    REASON_UNCERTAINTY_CROSSES_BOUNDARY,
    REASON_UNSUPPORTED_UNIT,
    REASON_FOREIGN_KEY_NOT_FOUND,
)

# ------------------------------------------------------------------------------
# Fixtures & Sample Catalogs
# ------------------------------------------------------------------------------

@pytest.fixture
def sample_sops_catalog():
    return [
        {
            "sop_id": "SOP-001",
            "sop_version": "1.0",
            "clause_id": "CLAUSE-001",
            "effective_date": "2024-01-01",
            "superseded_date": "2025-04-30",
            "minimum_value": 1.0,
            "maximum_value": 10.0,
            "canonical_unit": "mg/L",
        },
        {
            "sop_id": "SOP-001",
            "sop_version": "2.0",
            "clause_id": "CLAUSE-001",
            "effective_date": "2025-05-01",
            "superseded_date": None,
            "minimum_value": 2.0,
            "maximum_value": 8.0,
            "canonical_unit": "mg/L",
        },
        # SOP-003 with intentional overlap window: 2025-05-15 to 2025-05-31
        {
            "sop_id": "SOP-003",
            "sop_version": "1.0",
            "clause_id": "CLAUSE-016",
            "effective_date": "2024-01-01",
            "superseded_date": "2025-05-31",
            "minimum_value": 5.0,
            "maximum_value": 15.0,
            "canonical_unit": "mg/L",
        },
        {
            "sop_id": "SOP-003",
            "sop_version": "2.0",
            "clause_id": "CLAUSE-016",
            "effective_date": "2025-05-15",
            "superseded_date": None,
            "minimum_value": 6.0,
            "maximum_value": 14.0,
            "canonical_unit": "mg/L",
        },
        # SOP-004 with overlap but IDENTICAL specification limits
        {
            "sop_id": "SOP-004",
            "sop_version": "1.0",
            "clause_id": "CLAUSE-020",
            "effective_date": "2024-01-01",
            "superseded_date": "2025-06-30",
            "minimum_value": 0.5,
            "maximum_value": 2.5,
            "canonical_unit": "mg/L",
        },
        {
            "sop_id": "SOP-004",
            "sop_version": "2.0",
            "clause_id": "CLAUSE-020",
            "effective_date": "2025-06-01",
            "superseded_date": None,
            "minimum_value": 0.5,
            "maximum_value": 2.5,
            "canonical_unit": "mg/L",
        },
    ]


@pytest.fixture
def sample_instruments_catalog():
    return [
        {
            "instrument_id": "INST-001",
            "calibration_date": "2025-01-01",
            "validity_days": 90,  # Expires 2025-04-01 inclusive
        }
    ]


@pytest.fixture
def sample_lots_catalog():
    return [
        {
            "lot_id": "LOT-001",
            "manufacture_date": "2024-06-01",
            "expiry_date": "2025-06-01",  # Expires 2025-06-01 inclusive
        }
    ]


@pytest.fixture
def sample_samples_catalog():
    return [
        {
            "sample_id": "SMP-001",
            "collected_at": "2025-05-01T08:00:00Z",
            "max_holding_hours": 24.0,
            "site_id": "SITE-BOS",
        }
    ]


# ==============================================================================
# Rule 1: SOP Validation Tests
# ==============================================================================

def test_sop_normal_pass_v2(sample_sops_catalog):
    res = validate_sop_v2(
        sop_id="SOP-001",
        sop_version="1.0",
        clause_id="CLAUSE-001",
        run_date="2025-02-15",
        sops=sample_sops_catalog,
    )
    assert res["status"] == "pass"
    assert res["reason_codes"] == []
    assert res["rule_name"] == "sop"


def test_sop_premature_version_fails(sample_sops_catalog):
    # v2.0 effective 2025-05-01, run date is 2025-04-20
    res = validate_sop_v2(
        sop_id="SOP-001",
        sop_version="2.0",
        clause_id="CLAUSE-001",
        run_date="2025-04-20",
        sops=sample_sops_catalog,
    )
    assert res["status"] == "fail"
    assert REASON_SOP_VERSION_INVALID in res["reason_codes"]


def test_sop_superseded_version_fails(sample_sops_catalog):
    # v1.0 superseded 2025-04-30, run date is 2025-05-01
    res = validate_sop_v2(
        sop_id="SOP-001",
        sop_version="1.0",
        clause_id="CLAUSE-001",
        run_date="2025-05-01",
        sops=sample_sops_catalog,
    )
    assert res["status"] == "fail"
    assert REASON_SOP_VERSION_INVALID in res["reason_codes"]


def test_sop_explicit_version_in_authorized_overlap(sample_sops_catalog):
    # SOP-003 overlap window: 2025-05-15 to 2025-05-31
    # Run date 2025-05-20 explicitly cites v1.0 (grandfathered)
    res = validate_sop_v2(
        sop_id="SOP-003",
        sop_version="1.0",
        clause_id="CLAUSE-016",
        run_date="2025-05-20",
        sops=sample_sops_catalog,
    )
    assert res["status"] == "pass"
    assert res["reason_codes"] == []


def test_sop_explicit_v2_in_overlap(sample_sops_catalog):
    # Run date 2025-05-20 explicitly cites v2.0 (new version active)
    res = validate_sop_v2(
        sop_id="SOP-003",
        sop_version="2.0",
        clause_id="CLAUSE-016",
        run_date="2025-05-20",
        sops=sample_sops_catalog,
    )
    assert res["status"] == "pass"
    assert res["reason_codes"] == []


def test_sop_omitted_version_with_divergent_specs_triggers_conflict(sample_sops_catalog):
    # In overlap window on 2025-05-20, version is omitted/None
    # SOP-003 v1.0 has limits [5, 15], v2.0 has limits [6, 14] -> DIVERGENT!
    res = validate_sop_v2(
        sop_id="SOP-003",
        sop_version=None,
        clause_id="CLAUSE-016",
        run_date="2025-05-20",
        sops=sample_sops_catalog,
    )
    assert res["status"] == "needs_review"
    assert REASON_SOP_VERSION_CONFLICT in res["reason_codes"]


def test_sop_omitted_version_with_identical_specs_triggers_missing_version(sample_sops_catalog):
    # SOP-004 overlap window: 2025-06-01 to 2025-06-30
    # Both v1.0 and v2.0 have identical limits [0.5, 2.5]
    # Version omitted -> MISSING_SOP_VERSION (not conflict!)
    res = validate_sop_v2(
        sop_id="SOP-004",
        sop_version=None,
        clause_id="CLAUSE-020",
        run_date="2025-06-15",
        sops=sample_sops_catalog,
    )
    assert res["status"] == "needs_review"
    assert REASON_MISSING_SOP_VERSION in res["reason_codes"]


def test_sop_broken_foreign_key_returns_foreign_key_not_found(sample_sops_catalog):
    res = validate_sop_v2(
        sop_id="SOP-999",
        sop_version="1.0",
        clause_id="CLAUSE-001",
        run_date="2025-02-15",
        sops=sample_sops_catalog,
    )
    assert res["status"] == "needs_review"
    assert REASON_FOREIGN_KEY_NOT_FOUND in res["reason_codes"]


def test_sop_missing_id_returns_missing_sop_evidence(sample_sops_catalog):
    res = validate_sop_v2(
        sop_id=None,
        sop_version="1.0",
        clause_id="CLAUSE-001",
        run_date="2025-02-15",
        sops=sample_sops_catalog,
    )
    assert res["status"] == "needs_review"
    assert REASON_MISSING_SOP_EVIDENCE in res["reason_codes"]


# ==============================================================================
# Rule 2: Calibration Validation Tests
# ==============================================================================

def test_calibration_normal_pass_v2(sample_instruments_catalog):
    res = validate_calibration_v2(
        instrument_id="INST-001",
        run_date="2025-02-15",
        instruments=sample_instruments_catalog,
    )
    assert res["status"] == "pass"
    assert res["reason_codes"] == []
    assert res["rule_name"] == "calibration"


def test_calibration_inclusive_expiry_boundary(sample_instruments_catalog):
    # Calibrated 2025-01-01 + 90 days = 2025-04-01 (inclusive)
    res = validate_calibration_v2(
        instrument_id="INST-001",
        run_date="2025-04-01",
        instruments=sample_instruments_catalog,
    )
    assert res["status"] == "pass"
    assert res["calculated_values"]["days_remaining"] == 0


def test_calibration_expired_one_day_past_expiry(sample_instruments_catalog):
    # 2025-04-02 is 1 day overdue
    res = validate_calibration_v2(
        instrument_id="INST-001",
        run_date="2025-04-02",
        instruments=sample_instruments_catalog,
    )
    assert res["status"] == "fail"
    assert REASON_CALIBRATION_EXPIRED in res["reason_codes"]
    assert res["calculated_values"]["days_expired"] == 1


def test_calibration_precedes_calibration_date(sample_instruments_catalog):
    res = validate_calibration_v2(
        instrument_id="INST-001",
        run_date="2024-12-31",
        instruments=sample_instruments_catalog,
    )
    assert res["status"] == "fail"
    assert REASON_CALIBRATION_NOT_YET_VALID in res["reason_codes"]


def test_calibration_missing_id():
    res = validate_calibration_v2(instrument_id=None, run_date="2025-02-15")
    assert res["status"] == "needs_review"
    assert REASON_MISSING_INSTRUMENT_EVIDENCE in res["reason_codes"]


def test_calibration_broken_foreign_key(sample_instruments_catalog):
    res = validate_calibration_v2(
        instrument_id="INST-999",
        run_date="2025-02-15",
        instruments=sample_instruments_catalog,
    )
    assert res["status"] == "needs_review"
    assert REASON_FOREIGN_KEY_NOT_FOUND in res["reason_codes"]


# ==============================================================================
# Rule 3: Reagent Lot Validation Tests
# ==============================================================================

def test_lot_normal_pass_v2(sample_lots_catalog):
    res = validate_lot_v2(
        lot_id="LOT-001",
        run_date="2025-01-15",
        lots=sample_lots_catalog,
    )
    assert res["status"] == "pass"
    assert res["reason_codes"] == []
    assert res["rule_name"] == "lot"


def test_lot_inclusive_expiry_boundary(sample_lots_catalog):
    res = validate_lot_v2(
        lot_id="LOT-001",
        run_date="2025-06-01",  # Exactly expiry date
        lots=sample_lots_catalog,
    )
    assert res["status"] == "pass"
    assert res["calculated_values"]["days_to_expiry"] == 0


def test_lot_expired_one_day_past_expiry(sample_lots_catalog):
    res = validate_lot_v2(
        lot_id="LOT-001",
        run_date="2025-06-02",
        lots=sample_lots_catalog,
    )
    assert res["status"] == "fail"
    assert REASON_LOT_EXPIRED in res["reason_codes"]


def test_lot_precedes_manufacture_date(sample_lots_catalog):
    res = validate_lot_v2(
        lot_id="LOT-001",
        run_date="2024-05-31",
        lots=sample_lots_catalog,
    )
    assert res["status"] == "fail"
    assert REASON_LOT_NOT_YET_VALID in res["reason_codes"]


def test_lot_missing_id():
    res = validate_lot_v2(lot_id=None, run_date="2025-01-15")
    assert res["status"] == "needs_review"
    assert REASON_MISSING_REAGENT_EVIDENCE in res["reason_codes"]


def test_lot_broken_foreign_key(sample_lots_catalog):
    res = validate_lot_v2(
        lot_id="LOT-999",
        run_date="2025-01-15",
        lots=sample_lots_catalog,
    )
    assert res["status"] == "needs_review"
    assert REASON_FOREIGN_KEY_NOT_FOUND in res["reason_codes"]


# ==============================================================================
# Rule 4: Holding-Time Validation Tests
# ==============================================================================

def test_holding_time_normal_pass_v2(sample_samples_catalog):
    res = validate_holding_time_v2(
        sample_id="SMP-001",
        collected_at="2025-05-01T08:00:00Z",
        analyzed_at="2025-05-01T16:00:00Z",  # 8 hours elapsed
        max_holding_hours=24.0,
    )
    assert res["status"] == "pass"
    assert res["calculated_values"]["elapsed_hours"] == 8.0
    assert res["calculated_values"]["margin_hours"] == 16.0


def test_holding_time_exact_boundary(sample_samples_catalog):
    res = validate_holding_time_v2(
        sample_id="SMP-001",
        collected_at="2025-05-01T08:00:00Z",
        analyzed_at="2025-05-02T08:00:00Z",  # Exactly 24.0 hours elapsed
        max_holding_hours=24.0,
    )
    assert res["status"] == "pass"
    assert res["calculated_values"]["elapsed_hours"] == 24.0
    assert res["calculated_values"]["margin_hours"] == 0.0


def test_holding_time_exceeded_fails():
    res = validate_holding_time_v2(
        sample_id="SMP-001",
        collected_at="2025-05-01T08:00:00Z",
        analyzed_at="2025-05-02T09:00:00Z",  # 25.0 hours
        max_holding_hours=24.0,
    )
    assert res["status"] == "fail"
    assert REASON_HOLDING_TIME_EXCEEDED in res["reason_codes"]


def test_holding_time_chronological_inversion_fails():
    # Analysis 3 hours BEFORE collection
    res = validate_holding_time_v2(
        sample_id="SMP-001",
        collected_at="2025-05-01T12:00:00Z",
        analyzed_at="2025-05-01T09:00:00Z",
        max_holding_hours=24.0,
    )
    assert res["status"] == "fail"
    assert REASON_INVALID_TIMESTAMP_ORDER in res["reason_codes"]


def test_holding_time_timezone_offset_normalized():
    # Collection at 14:00+02:00 (12:00 UTC), analysis at 15:00Z (15:00 UTC)
    # Elapsed = 3 hours
    res = validate_holding_time_v2(
        sample_id="SMP-001",
        collected_at="2025-05-01T14:00:00+02:00",
        analyzed_at="2025-05-01T15:00:00Z",
        max_holding_hours=10.0,
    )
    assert res["status"] == "pass"
    assert res["calculated_values"]["elapsed_hours"] == 3.0


def test_holding_time_naive_with_site_timezone_localized():
    # Site is SITE-BOS (America/New_York, EDT is UTC-4 in May)
    # 10:00 local EDT -> 14:00 UTC. Analysis at 18:00 UTC -> 4 hours elapsed.
    res = validate_holding_time_v2(
        sample_id="SMP-001",
        collected_at="2025-05-01T10:00:00",  # naive
        analyzed_at="2025-05-01T18:00:00Z",   # aware
        max_holding_hours=12.0,
        site_id="SITE-BOS",
    )
    assert res["status"] == "pass"
    assert res["calculated_values"]["elapsed_hours"] == 4.0


def test_holding_time_naive_without_site_timezone_returns_ambiguous():
    # Naive timestamp with no site_id / site_timezone
    res = validate_holding_time_v2(
        sample_id="SMP-001",
        collected_at="2025-05-01T10:00:00",
        analyzed_at="2025-05-01T18:00:00",
        max_holding_hours=12.0,
        site_id=None,
        site_timezone=None,
    )
    assert res["status"] == "needs_review"
    assert REASON_AMBIGUOUS_TIMEZONE in res["reason_codes"]


def test_holding_time_dst_spring_forward_gap_returns_ambiguous():
    # In America/New_York, 2025-03-09 spring forward jumps from 02:00 to 03:00.
    # 02:30:00 does not exist!
    res = validate_holding_time_v2(
        sample_id="SMP-001",
        collected_at="2025-03-09T02:30:00",
        analyzed_at="2025-03-09T10:00:00Z",
        max_holding_hours=24.0,
        site_timezone="America/New_York",
    )
    assert res["status"] == "needs_review"
    assert REASON_AMBIGUOUS_TIMEZONE in res["reason_codes"]


def test_holding_time_broken_foreign_key(sample_samples_catalog):
    res = validate_holding_time_v2(
        sample_id="SMP-999",
        collected_at="2025-05-01T08:00:00Z",
        analyzed_at="2025-05-01T16:00:00Z",
        max_holding_hours=24.0,
        samples=sample_samples_catalog,
    )
    assert res["status"] == "needs_review"
    assert REASON_FOREIGN_KEY_NOT_FOUND in res["reason_codes"]


# ==============================================================================
# Rule 5: Measurement Validation Tests
# ==============================================================================

def test_measurement_normal_pass_v2():
    res = validate_measurement_v2(
        measured_value=5.0,
        measurement_unit="mg/L",
        measurement_uncertainty=0.2,
        sop_minimum=2.0,
        sop_maximum=8.0,
        canonical_unit="mg/L",
    )
    assert res["status"] == "pass"
    assert res["reason_codes"] == []
    assert res["rule_name"] == "measurement"


def test_measurement_strictly_outside_fails():
    res = validate_measurement_v2(
        measured_value=12.0,
        measurement_unit="mg/L",
        measurement_uncertainty=0.5,
        sop_minimum=2.0,
        sop_maximum=8.0,
        canonical_unit="mg/L",
    )
    assert res["status"] == "fail"
    assert REASON_MEASUREMENT_OUT_OF_RANGE in res["reason_codes"]


def test_measurement_crossing_upper_boundary():
    res = validate_measurement_v2(
        measured_value=7.9,
        measurement_unit="mg/L",
        measurement_uncertainty=0.3,  # interval [7.6, 8.2] crosses 8.0!
        sop_minimum=2.0,
        sop_maximum=8.0,
        canonical_unit="mg/L",
    )
    assert res["status"] == "needs_review"
    assert REASON_UNCERTAINTY_CROSSES_BOUNDARY in res["reason_codes"]


def test_measurement_crossing_lower_boundary():
    res = validate_measurement_v2(
        measured_value=2.1,
        measurement_unit="mg/L",
        measurement_uncertainty=0.3,  # interval [1.8, 2.4] crosses 2.0!
        sop_minimum=2.0,
        sop_maximum=8.0,
        canonical_unit="mg/L",
    )
    assert res["status"] == "needs_review"
    assert REASON_UNCERTAINTY_CROSSES_BOUNDARY in res["reason_codes"]


def test_measurement_crossing_both_boundaries():
    # Value 5.0, but large uncertainty 4.0 -> interval [1.0, 9.0]
    # Straddles both min=2.0 and max=8.0!
    res = validate_measurement_v2(
        measured_value=5.0,
        measurement_unit="mg/L",
        measurement_uncertainty=4.0,
        sop_minimum=2.0,
        sop_maximum=8.0,
        canonical_unit="mg/L",
    )
    assert res["status"] == "needs_review"
    assert REASON_UNCERTAINTY_CROSSES_BOUNDARY in res["reason_codes"]


def test_measurement_unicode_unit_normalized():
    # 5000 \u03bcg/L (Greek mu) -> 5.0 mg/L +- 0.2 mg/L
    res = validate_measurement_v2(
        measured_value=5000,
        measurement_unit="\u03bcg/L",
        measurement_uncertainty=200,
        sop_minimum=2.0,
        sop_maximum=8.0,
        canonical_unit="mg/L",
    )
    assert res["status"] == "pass"
    assert res["calculated_values"]["normalized_value"] == 5.0


def test_measurement_incompatible_unit_yields_needs_review():
    res = validate_measurement_v2(
        measured_value=7.4,
        measurement_unit="pH",
        measurement_uncertainty=0.1,
        sop_minimum=2.0,
        sop_maximum=8.0,
        canonical_unit="mg/L",
    )
    assert res["status"] == "needs_review"
    assert REASON_UNSUPPORTED_UNIT in res["reason_codes"]


def test_measurement_broken_clause_foreign_key(sample_sops_catalog):
    res = validate_measurement_v2(
        measured_value=5.0,
        measurement_unit="mg/L",
        measurement_uncertainty=0.2,
        clause_id="CLAUSE-999",
        sops=sample_sops_catalog,
    )
    assert res["status"] == "needs_review"
    assert REASON_FOREIGN_KEY_NOT_FOUND in res["reason_codes"]


# ==============================================================================
# Standard Contract Output Verification
# ==============================================================================

def test_all_rules_adhere_to_standard_contract(sample_sops_catalog):
    results = [
        validate_sop_v2(sop_id="SOP-001", sop_version="1.0", clause_id="CLAUSE-001", run_date="2025-02-15", sops=sample_sops_catalog),
        validate_calibration_v2(instrument_id="INST-001", calibration_date="2025-01-01", validity_days=90, run_date="2025-02-15"),
        validate_lot_v2(lot_id="LOT-001", manufacture_date="2024-06-01", expiry_date="2025-06-01", run_date="2025-02-15"),
        validate_holding_time_v2(sample_id="SMP-001", collected_at="2025-05-01T08:00:00Z", analyzed_at="2025-05-01T12:00:00Z", max_holding_hours=24.0),
        validate_measurement_v2(measured_value=5.0, measurement_unit="mg/L", measurement_uncertainty=0.1, sop_minimum=2.0, sop_maximum=8.0, canonical_unit="mg/L"),
    ]

    for r in results:
        assert isinstance(r, dict)
        assert "rule_name" in r
        assert "status" in r
        assert r["status"] in ("pass", "fail", "needs_review")
        assert "reason_codes" in r
        assert isinstance(r["reason_codes"], list)
        assert "details" in r
        assert isinstance(r["details"], str)
        assert "source_ids" in r
        assert isinstance(r["source_ids"], list)
        assert "calculated_values" in r
        assert isinstance(r["calculated_values"], dict)

