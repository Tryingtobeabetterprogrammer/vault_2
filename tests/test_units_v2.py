"""Comprehensive test suite for VAULT V2 Unit Normalization & Precision Measurement."""

from decimal import Decimal
import pytest

from synth import units_v2
from synth.units_v2 import (
    convert_and_normalize,
    compare_measurement_uncertainty_v2,
    normalize_unit_string,
    to_decimal,
    REASON_UNSUPPORTED_UNIT,
    REASON_MEASUREMENT_OUT_OF_RANGE,
    REASON_UNCERTAINTY_CROSSES_BOUNDARY,
    REASON_MISSING_MEASUREMENT_EVIDENCE,
)


# ==============================================================================
# 1. Supported Unit Conversions & Decimal Precision
# ==============================================================================

def test_gl_to_mgl_conversion_v2():
    res = convert_and_normalize(value="2.5", unit="g/L", target_canonical_unit="mg/L")
    assert res["conversion_status"] == "success"
    assert res["canonical_unit"] == "mg/L"
    assert res["normalized_value"] == Decimal("2500")


def test_mgl_to_mgl_identity_v2():
    res = convert_and_normalize(value="45.123", unit="mg/L", target_canonical_unit="mg/L")
    assert res["conversion_status"] == "success"
    assert res["canonical_unit"] == "mg/L"
    assert res["normalized_value"] == Decimal("45.123")


def test_ugl_to_mgl_conversion_v2():
    res = convert_and_normalize(value="1500", unit="µg/L", target_canonical_unit="mg/L")
    assert res["conversion_status"] == "success"
    assert res["canonical_unit"] == "mg/L"
    assert res["normalized_value"] == Decimal("1.500")


def test_decimal_precision_no_float_drift():
    # 0.1 + 0.2 in float is 0.30000000000000004
    # With Decimal, conversion of 0.0001 g/L must be exactly 0.1 mg/L
    res = convert_and_normalize(value="0.0001", unit="g/L", target_canonical_unit="mg/L")
    assert res["normalized_value"] == Decimal("0.1000")


# ==============================================================================
# 2. Unicode Normalization: Micro Sign (U+00B5) and Greek Mu (U+03BC)
# ==============================================================================

def test_unicode_micro_sign_u00b5():
    unit_micro = "\u00b5g/L"  # µg/L
    res = convert_and_normalize(value="500", unit=unit_micro, target_canonical_unit="mg/L")
    assert res["conversion_status"] == "success"
    assert res["normalized_value"] == Decimal("0.500")
    assert res["canonical_unit"] == "mg/L"


def test_unicode_greek_mu_u03bc():
    unit_greek = "\u03bcg/L"  # μg/L (Greek small letter mu)
    res = convert_and_normalize(value="500", unit=unit_greek, target_canonical_unit="mg/L")
    assert res["conversion_status"] == "success"
    assert res["normalized_value"] == Decimal("0.500")
    assert res["canonical_unit"] == "mg/L"


def test_ascii_ug_l_fallback():
    res = convert_and_normalize(value="250", unit="ug/L", target_canonical_unit="mg/L")
    assert res["conversion_status"] == "success"
    assert res["normalized_value"] == Decimal("0.250")


def test_mcg_l_fallback():
    res = convert_and_normalize(value="1000", unit="mcg/L", target_canonical_unit="mg/L")
    assert res["conversion_status"] == "success"
    assert res["normalized_value"] == Decimal("1.000")


# ==============================================================================
# 3. Conductivity Handling (Separate Dimension)
# ==============================================================================

def test_conductivity_us_cm_identity():
    res = convert_and_normalize(value="250.5", unit="µS/cm", target_canonical_unit="µS/cm")
    assert res["conversion_status"] == "success"
    assert res["canonical_unit"] == "µS/cm"
    assert res["normalized_value"] == Decimal("250.5")


def test_conductivity_ms_cm_to_us_cm():
    res = convert_and_normalize(value="1.25", unit="mS/cm", target_canonical_unit="µS/cm")
    assert res["conversion_status"] == "success"
    assert res["canonical_unit"] == "µS/cm"
    assert res["normalized_value"] == Decimal("1250.00")


def test_conductivity_ascii_fallback():
    res = convert_and_normalize(value="100", unit="us/cm", target_canonical_unit="µS/cm")
    assert res["conversion_status"] == "success"
    assert res["canonical_unit"] == "µS/cm"
    assert res["normalized_value"] == Decimal("100")


# ==============================================================================
# 4. Incompatible Dimensions & Unsupported Units
# ==============================================================================

def test_incompatible_dimension_ph_to_concentration():
    # Attempting to convert pH against a canonical concentration target (mg/L)
    res = convert_and_normalize(value="7.2", unit="pH", target_canonical_unit="mg/L")
    assert res["conversion_status"] == "incompatible_dimension"
    assert res["reason_code"] == REASON_UNSUPPORTED_UNIT
    assert res["normalized_value"] is None
    assert "Incompatible measurement dimension" in res["details"]


def test_incompatible_dimension_ntu_to_concentration():
    res = convert_and_normalize(value="1.5", unit="NTU", target_canonical_unit="mg/L")
    assert res["conversion_status"] == "incompatible_dimension"
    assert res["reason_code"] == REASON_UNSUPPORTED_UNIT
    assert res["normalized_value"] is None


def test_incompatible_dimension_conductivity_to_concentration():
    res = convert_and_normalize(value="500", unit="µS/cm", target_canonical_unit="mg/L")
    assert res["conversion_status"] == "incompatible_dimension"
    assert res["reason_code"] == REASON_UNSUPPORTED_UNIT
    assert res["normalized_value"] is None


def test_incompatible_dimension_percentage_to_concentration():
    res = convert_and_normalize(value="99.5", unit="%", target_canonical_unit="mg/L")
    assert res["conversion_status"] == "incompatible_dimension"
    assert res["reason_code"] == REASON_UNSUPPORTED_UNIT


def test_unsupported_unit_string():
    res = convert_and_normalize(value="100", unit="kg/acre")
    assert res["conversion_status"] == "unsupported_unit"
    assert res["reason_code"] == REASON_UNSUPPORTED_UNIT
    assert res["normalized_value"] is None


# ==============================================================================
# 5. Missing and Malformed Input Handling
# ==============================================================================

def test_missing_value():
    res = convert_and_normalize(value=None, unit="mg/L")
    assert res["conversion_status"] == "missing_value"
    assert res["reason_code"] == REASON_MISSING_MEASUREMENT_EVIDENCE


def test_empty_string_value():
    res = convert_and_normalize(value="   ", unit="mg/L")
    assert res["conversion_status"] == "missing_value"
    assert res["reason_code"] == REASON_MISSING_MEASUREMENT_EVIDENCE


def test_malformed_string_value():
    res = convert_and_normalize(value="not_a_number", unit="mg/L")
    assert res["conversion_status"] == "invalid_value"
    assert res["reason_code"] == REASON_MISSING_MEASUREMENT_EVIDENCE


def test_missing_unit():
    res = convert_and_normalize(value=10.5, unit=None)
    assert res["conversion_status"] == "missing_unit"
    assert res["reason_code"] == REASON_MISSING_MEASUREMENT_EVIDENCE


# ==============================================================================
# 6. Uncertainty Interval Evaluation against SOP Limits
# ==============================================================================

def test_uncertainty_strictly_within_range():
    # Value 5.0 mg/L +- 0.2 -> interval [4.8, 5.2]. Limits [4.0, 6.0].
    eval_res = compare_measurement_uncertainty_v2(
        measured_value=5.0,
        measurement_unit="mg/L",
        measurement_uncertainty=0.2,
        sop_minimum=4.0,
        sop_maximum=6.0,
        canonical_unit="mg/L",
    )
    assert eval_res["status"] == "pass"
    assert eval_res["reason_code"] is None
    assert eval_res["lower_bound"] == 4.8
    assert eval_res["upper_bound"] == 5.2


def test_uncertainty_strictly_outside_range():
    # Value 10.0 mg/L +- 0.5 -> interval [9.5, 10.5]. Limits [4.0, 6.0].
    eval_res = compare_measurement_uncertainty_v2(
        measured_value=10.0,
        measurement_unit="mg/L",
        measurement_uncertainty=0.5,
        sop_minimum=4.0,
        sop_maximum=6.0,
        canonical_unit="mg/L",
    )
    assert eval_res["status"] == "fail"
    assert eval_res["reason_code"] == REASON_MEASUREMENT_OUT_OF_RANGE


def test_uncertainty_crossing_upper_boundary():
    # Value 5.9 mg/L +- 0.3 -> interval [5.6, 6.2]. Limits [4.0, 6.0].
    # Overlaps upper limit 6.0!
    eval_res = compare_measurement_uncertainty_v2(
        measured_value=5.9,
        measurement_unit="mg/L",
        measurement_uncertainty=0.3,
        sop_minimum=4.0,
        sop_maximum=6.0,
        canonical_unit="mg/L",
    )
    assert eval_res["status"] == "needs_review"
    assert eval_res["reason_code"] == REASON_UNCERTAINTY_CROSSES_BOUNDARY


def test_uncertainty_crossing_lower_boundary():
    # Value 4.1 mg/L +- 0.3 -> interval [3.8, 4.4]. Limits [4.0, 6.0].
    # Overlaps lower limit 4.0!
    eval_res = compare_measurement_uncertainty_v2(
        measured_value=4.1,
        measurement_unit="mg/L",
        measurement_uncertainty=0.3,
        sop_minimum=4.0,
        sop_maximum=6.0,
        canonical_unit="mg/L",
    )
    assert eval_res["status"] == "needs_review"
    assert eval_res["reason_code"] == REASON_UNCERTAINTY_CROSSES_BOUNDARY


def test_uncertainty_with_unit_conversion():
    # Value 5000 µg/L +- 200 µg/L -> 5.0 mg/L +- 0.2 mg/L. Limits [4.0, 6.0] mg/L.
    eval_res = compare_measurement_uncertainty_v2(
        measured_value=5000,
        measurement_unit="µg/L",
        measurement_uncertainty=200,
        sop_minimum=4.0,
        sop_maximum=6.0,
        canonical_unit="mg/L",
    )
    assert eval_res["status"] == "pass"
    assert eval_res["normalized_value"] == 5.0
    assert eval_res["normalized_uncertainty"] == 0.2
    assert eval_res["lower_bound"] == 4.8
    assert eval_res["upper_bound"] == 5.2


def test_uncertainty_incompatible_unit_yields_needs_review():
    eval_res = compare_measurement_uncertainty_v2(
        measured_value=7.0,
        measurement_unit="pH",
        measurement_uncertainty=0.1,
        sop_minimum=10.0,
        sop_maximum=20.0,
        canonical_unit="mg/L",
    )
    assert eval_res["status"] == "needs_review"
    assert eval_res["reason_code"] == REASON_UNSUPPORTED_UNIT

