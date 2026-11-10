"""Automated Test Suite for VAULT Kaggle External Dataset Validation."""

from pathlib import Path
import pytest

from data_engine.kaggle_adapter import KaggleAirQualityAdapter
from data_engine.kaggle_verifier import (
    verify_kaggle_record,
    REASON_NEGATIVE_POLLUTANT_VALUE,
    REASON_AQI_BUCKET_CONTRADICTION,
    REASON_DATE_OUT_OF_RANGE,
    REASON_INSUFFICIENT_POLLUTANT_DATA,
    REASON_MISSING_CALIBRATION_EVIDENCE,
    REASON_MISSING_SOP_EVIDENCE,
    REASON_MISSING_UNCERTAINTY,
)
from vault.memory import ScientificMemory
from data_engine.roundtrip import gate_teacher_candidate


@pytest.fixture
def sample_kaggle_row():
    return {
        "City": "Bengaluru",
        "Date": "2018-05-15",
        "PM2.5": "35.5",
        "PM10": "65.2",
        "NO": "8.1",
        "NO2": "22.4",
        "NOx": "18.3",
        "NH3": "10.0",
        "CO": "0.75",
        "SO2": "6.2",
        "O3": "28.4",
        "Benzene": "0.5",
        "Toluene": "2.1",
        "Xylene": "0.1",
        "AQI": "75.0",
        "AQI_Bucket": "Satisfactory",
    }


def test_kaggle_adapter_field_mapping(sample_kaggle_row):
    """Verify KaggleAirQualityAdapter maps fields cleanly preserving original payload."""
    rec = KaggleAirQualityAdapter.parse_city_day_record(sample_kaggle_row, 1)

    assert rec["city"] == "Bengaluru"
    assert rec["site_id"] == "CITY-BENGALURU"
    assert rec["run_date"] == "2018-05-15"
    assert rec["aqi"] == 75.0
    assert rec["aqi_bucket"] == "Satisfactory"
    assert rec["measurements"]["PM2.5"] == 35.5
    assert rec["measurements"]["CO"] == 0.75

    # Check that SHA-256 matches raw payload
    assert rec["payload_sha256"] == KaggleAirQualityAdapter.compute_sha256(sample_kaggle_row)

    # Check metadata audit identifies missing lab dimensions
    missing_lab = rec["metadata_audit"]["laboratory_metadata_missing"]
    assert "sop_id" in missing_lab
    assert "instrument_id" in missing_lab
    assert "calibration_window" in missing_lab


def test_plausible_telemetry_routes_to_needs_review(sample_kaggle_row):
    """Plausible environmental telemetry without laboratory calibration must route to needs_review."""
    rec = KaggleAirQualityAdapter.parse_city_day_record(sample_kaggle_row, 1)
    ass = verify_kaggle_record(rec)

    assert ass["status"] == "needs_review"
    assert ass["verdict"] == "unverified"
    assert ass["abstain"] is True

    # Must explicitly state why: lack of laboratory accreditation evidence
    assert REASON_MISSING_CALIBRATION_EVIDENCE in ass["issues"]
    assert REASON_MISSING_SOP_EVIDENCE in ass["issues"]
    assert REASON_MISSING_UNCERTAINTY in ass["issues"]


def test_negative_pollutant_concentration_flagged(sample_kaggle_row):
    """Physical impossibility (negative concentration) must be flagged as invalid."""
    bad_row = dict(sample_kaggle_row)
    bad_row["PM2.5"] = "-15.0"

    rec = KaggleAirQualityAdapter.parse_city_day_record(bad_row, 2)
    ass = verify_kaggle_record(rec)

    assert ass["status"] == "flagged"
    assert ass["verdict"] == "invalid"
    assert ass["abstain"] is False
    assert REASON_NEGATIVE_POLLUTANT_VALUE in ass["issues"]


def test_aqi_bucket_contradiction_flagged(sample_kaggle_row):
    """Mathematical contradiction between AQI and AQI_Bucket must be flagged as invalid."""
    bad_row = dict(sample_kaggle_row)
    bad_row["AQI"] = "350.0"  # Very Poor range
    bad_row["AQI_Bucket"] = "Good"  # Contradicts AQI

    rec = KaggleAirQualityAdapter.parse_city_day_record(bad_row, 3)
    ass = verify_kaggle_record(rec)

    assert ass["status"] == "flagged"
    assert ass["verdict"] == "invalid"
    assert REASON_AQI_BUCKET_CONTRADICTION in ass["issues"]


def test_missing_all_pollutants_flagged(sample_kaggle_row):
    """Row with zero valid pollutant measurements must be flagged as insufficient data."""
    empty_row = {k: "" for k in sample_kaggle_row}
    empty_row["City"] = "Delhi"
    empty_row["Date"] = "2019-01-01"

    rec = KaggleAirQualityAdapter.parse_city_day_record(empty_row, 4)
    ass = verify_kaggle_record(rec)

    assert ass["status"] == "flagged"
    assert ass["verdict"] == "invalid"
    assert REASON_INSUFFICIENT_POLLUTANT_DATA in ass["issues"]


def test_date_out_of_range_flagged(sample_kaggle_row):
    """Date outside 2015-2020 CPCB study range must be flagged."""
    future_row = dict(sample_kaggle_row)
    future_row["Date"] = "2029-01-01"

    rec = KaggleAirQualityAdapter.parse_city_day_record(future_row, 5)
    ass = verify_kaggle_record(rec)

    assert ass["status"] == "flagged"
    assert REASON_DATE_OUT_OF_RANGE in ass["issues"]


def test_isolated_scientific_memory(tmp_path, sample_kaggle_row):
    """ScientificMemory must store and retrieve Kaggle records in an isolated directory."""
    mem_dir = str(tmp_path / "kaggle_mem")
    memory = ScientificMemory(storage_dir=mem_dir)

    rec = KaggleAirQualityAdapter.parse_city_day_record(sample_kaggle_row, 1)
    src = memory.register_source(rec["record_id"], rec["raw_payload"])
    assert src["source_hash"] == rec["payload_sha256"]

    ass = verify_kaggle_record(rec)
    saved = memory.record_assessment(ass)
    assert saved["assessment_id"] == ass["assessment_id"]

    # Test idempotency
    saved2 = memory.record_assessment(ass)
    assert saved2["assessment_id"] == ass["assessment_id"]
    assert len(memory.get_history(rec["record_id"])) == 1


def test_roundtrip_blocks_unverified_kaggle_claims():
    """Unverified teacher explanations citing Kaggle records must be blocked by gatekeeper."""
    teacher_text = (
        "Scientific Compliance Verification for KAG-CITY-BLR-2018-05-15-00001 (PM2.5):\n"
        "Verdict: COMPLIANT (PASS) under CPCB Ambient Guidelines.\n"
        "Evidence Breakdown:\n"
        "1. Standard Operating Procedure: CPCB 2015 protocol active.\n"
        "2. Equipment Calibration: Valid on run date.\n"
        "3. Measurement: Reported value 35.5 ug/m3.\n"
        "Conclusion: Approved compliance."
    )
    is_accepted, result = gate_teacher_candidate(teacher_text)

    # Must be blocked from training candidates
    assert is_accepted is False
    assert result.passed is False
    assert result.quarantined is True


def test_cpcb_severe_boundary_values(sample_kaggle_row):
    """Test CPCB NAQI Severe boundary limits: 400 (Very Poor), 401 (Severe), 500 (Severe), 501 (Contradiction)."""
    # 1. 400 = Very Poor (valid boundary)
    row_400 = dict(sample_kaggle_row)
    row_400["AQI"] = "400.0"
    row_400["AQI_Bucket"] = "Very Poor"
    rec_400 = KaggleAirQualityAdapter.parse_city_day_record(row_400, 101)
    ass_400 = verify_kaggle_record(rec_400)
    assert REASON_AQI_BUCKET_CONTRADICTION not in ass_400["issues"]
    assert ass_400["status"] == "needs_review"

    # 2. 401 = Severe (valid boundary)
    row_401 = dict(sample_kaggle_row)
    row_401["AQI"] = "401.0"
    row_401["AQI_Bucket"] = "Severe"
    rec_401 = KaggleAirQualityAdapter.parse_city_day_record(row_401, 102)
    ass_401 = verify_kaggle_record(rec_401)
    assert REASON_AQI_BUCKET_CONTRADICTION not in ass_401["issues"]
    assert ass_401["status"] == "needs_review"

    # 3. 500 = Severe (valid upper scale boundary)
    row_500 = dict(sample_kaggle_row)
    row_500["AQI"] = "500.0"
    row_500["AQI_Bucket"] = "Severe"
    rec_500 = KaggleAirQualityAdapter.parse_city_day_record(row_500, 103)
    ass_500 = verify_kaggle_record(rec_500)
    assert REASON_AQI_BUCKET_CONTRADICTION not in ass_500["issues"]
    assert ass_500["status"] == "needs_review"

    # 4. 501 = Contradiction / outside official AQI scale (must be flagged)
    row_501 = dict(sample_kaggle_row)
    row_501["AQI"] = "501.0"
    row_501["AQI_Bucket"] = "Severe"
    rec_501 = KaggleAirQualityAdapter.parse_city_day_record(row_501, 104)
    ass_501 = verify_kaggle_record(rec_501)
    assert REASON_AQI_BUCKET_CONTRADICTION in ass_501["issues"]
    assert ass_501["status"] == "flagged"
    assert ass_501["verdict"] == "invalid"


def test_zero_pollutant_values_distinguished_from_blanks(sample_kaggle_row):
    """Zero concentration (0.0) is a valid physical measurement and must not be treated as missing."""
    row_with_zero = {k: "" for k in sample_kaggle_row}
    row_with_zero["City"] = "Delhi"
    row_with_zero["Date"] = "2019-01-01"
    row_with_zero["PM2.5"] = "0.0"  # Zero measurement
    row_with_zero["AQI"] = "25.0"
    row_with_zero["AQI_Bucket"] = "Good"

    rec = KaggleAirQualityAdapter.parse_city_day_record(row_with_zero, 105)
    # 0.0 must be parsed as a float, not None
    assert rec["measurements"]["PM2.5"] == 0.0
    assert rec["measurements"]["PM10"] is None

    ass = verify_kaggle_record(rec)
    # Zero is valid data, so it must NOT trigger INSUFFICIENT_POLLUTANT_DATA
    assert REASON_INSUFFICIENT_POLLUTANT_DATA not in ass["issues"]
    assert ass["status"] == "needs_review"


def test_missing_aqi_classified_separately_from_missing_pollutants(sample_kaggle_row):
    """Missing AQI must route to needs_review when pollutants exist, not flagged as hard defect."""
    row_missing_aqi = dict(sample_kaggle_row)
    row_missing_aqi["AQI"] = ""
    row_missing_aqi["AQI_Bucket"] = ""

    rec = KaggleAirQualityAdapter.parse_city_day_record(row_missing_aqi, 106)
    ass = verify_kaggle_record(rec)

    # Missing AQI is an unverified evidence issue, not a hard invalidation
    assert "MISSING_AQI_EVIDENCE" in ass["issues"]
    assert REASON_INSUFFICIENT_POLLUTANT_DATA not in ass["issues"]
    assert ass["status"] == "needs_review"
    assert ass["verdict"] == "unverified"


def test_every_record_receives_exactly_one_primary_status(sample_kaggle_row):
    """Every record must resolve to exactly one primary status in {checks_passed, needs_review, flagged}."""
    test_cases = [
        sample_kaggle_row,
        {**sample_kaggle_row, "PM2.5": "-5.0"},  # hard negative defect -> flagged
        {**sample_kaggle_row, "AQI": "", "AQI_Bucket": ""},  # missing AQI -> needs_review
        {k: "" for k in sample_kaggle_row},  # all empty -> flagged
        {**sample_kaggle_row, "AQI": "501.0", "AQI_Bucket": "Severe"},  # out of scale -> flagged
    ]
    valid_statuses = {"checks_passed", "needs_review", "flagged"}
    for idx, case in enumerate(test_cases, start=200):
        rec = KaggleAirQualityAdapter.parse_city_day_record(case, idx)
        ass = verify_kaggle_record(rec)
        assert ass["status"] in valid_statuses
        assert isinstance(ass["status"], str)


def test_aqi_independent_recalculation_scope_explicitly_separated(sample_kaggle_row):
    """Verification must explicitly decouple bucket consistency from independent recalculation."""
    rec = KaggleAirQualityAdapter.parse_city_day_record(sample_kaggle_row, 301)
    ass = verify_kaggle_record(rec)

    checks = {e["check"]: e for e in ass["evidence"]}
    assert "aqi_bucket_consistency" in checks
    assert checks["aqi_bucket_consistency"]["status"] == "pass"

    assert "aqi_independent_recalculation" in checks
    assert checks["aqi_independent_recalculation"]["status"] == "outside_scope"
    assert "sub-index linear interpolation" in checks["aqi_independent_recalculation"]["details"]


