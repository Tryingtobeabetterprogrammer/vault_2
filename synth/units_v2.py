"""VAULT V2 Unit Normalization and Precision Measurement Evaluation Module.

Provides:
- Unicode NFKC normalization and alias resolution for laboratory units.
- High-precision Decimal conversion to canonical units (mg/L for concentration,
  µS/cm for conductivity).
- Strict dimensional separation preventing invalid cross-dimensional conversions
  (e.g., pH, NTU, %, or conductivity into concentration).
- Precision evaluation of measurement uncertainty intervals against SOP limits
  without float arithmetic drift.
"""

from __future__ import annotations

import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Canonical unit definitions per physical dimension
CANONICAL_MASS_CONCENTRATION = "mg/L"
CANONICAL_CONDUCTIVITY = "µS/cm"
CANONICAL_PH = "pH"
CANONICAL_TURBIDITY = "NTU"
CANONICAL_PERCENTAGE = "%"
CANONICAL_BIOBURDEN = "CFU/g"
CANONICAL_PARTICULATE_COUNT = "particles/mL"
CANONICAL_ENDOTOXIN = "EU/mL"

CANONICAL_UNITS: Dict[str, str] = {
    "concentration": CANONICAL_MASS_CONCENTRATION,
    "conductivity": CANONICAL_CONDUCTIVITY,
    "ph": CANONICAL_PH,
    "turbidity": CANONICAL_TURBIDITY,
    "percentage": CANONICAL_PERCENTAGE,
    "bioburden": CANONICAL_BIOBURDEN,
    "particulate_count": CANONICAL_PARTICULATE_COUNT,
    "endotoxin": CANONICAL_ENDOTOXIN,
}

# Reason codes for unit conversion and measurement outcomes
REASON_UNSUPPORTED_UNIT = "UNSUPPORTED_UNIT"
REASON_INCOMPATIBLE_DIMENSION = "INCOMPATIBLE_DIMENSION"
REASON_MISSING_MEASUREMENT_EVIDENCE = "MISSING_REQUIRED_EVIDENCE"
REASON_MEASUREMENT_OUT_OF_RANGE = "MEASUREMENT_OUT_OF_RANGE"
REASON_UNCERTAINTY_CROSSES_BOUNDARY = "UNCERTAINTY_CROSSES_BOUNDARY"

# Conversion factors to canonical unit (Decimal arithmetic only)
# Concentration -> canonical 'mg/L'
CONCENTRATION_FACTORS_DECIMAL: Dict[str, Decimal] = {
    "g/L": Decimal("1000"),
    "mg/L": Decimal("1"),
    "µg/L": Decimal("0.001"),
}

# Conductivity -> canonical 'µS/cm'
CONDUCTIVITY_FACTORS_DECIMAL: Dict[str, Decimal] = {
    "mS/cm": Decimal("1000"),
    "µS/cm": Decimal("1"),
}

# Explicit alias table mapping normalized strings to internal standard keys
# Note: unicodedata.normalize('NFKC', '\u00b5') yields '\u03bc' (GREEK SMALL LETTER MU)
# We support ASCII, Greek mu (\u03bc), and micro sign (\u00b5) inputs.
UNIT_ALIAS_MAP: Dict[str, Tuple[str, str]] = {
    # Concentration aliases -> (standard_key, dimension)
    "g/l": ("g/L", "concentration"),
    "mg/l": ("mg/L", "concentration"),
    "\u03bcg/l": ("µg/L", "concentration"),  # NFKC Greek mu: μg/L
    "\u00b5g/l": ("µg/L", "concentration"),  # Native micro sign: µg/L
    "ug/l": ("µg/L", "concentration"),       # ASCII fallback
    "mcg/l": ("µg/L", "concentration"),      # Pharmaceutical fallback

    # Conductivity aliases -> (standard_key, dimension)
    "ms/cm": ("mS/cm", "conductivity"),
    "\u03bcs/cm": ("µS/cm", "conductivity"),  # NFKC Greek mu: μS/cm
    "\u00b5s/cm": ("µS/cm", "conductivity"),  # Native micro sign: µS/cm
    "us/cm": ("µS/cm", "conductivity"),       # ASCII fallback

    # Single-unit / non-scaled dimensions -> (standard_key, dimension)
    "ph": ("pH", "ph"),
    "ntu": ("NTU", "turbidity"),
    "%": ("%", "percentage"),
    "cfu/g": ("CFU/g", "bioburden"),
    "cfu/ml": ("CFU/mL", "bioburden"),
    "particles/ml": ("particles/mL", "particulate_count"),
    "particles/l": ("particles/L", "particulate_count"),
    "eu/ml": ("EU/mL", "endotoxin"),
}


def to_decimal(val: Any) -> Optional[Decimal]:
    """Safely convert numeric, string, or float input to Decimal without float drift."""
    if val is None:
        return None
    if isinstance(val, Decimal):
        return val
    try:
        val_str = str(val).strip()
        if not val_str or val_str.lower() in ("none", "null", "nan", "inf", "-inf"):
            return None
        return Decimal(val_str)
    except (InvalidOperation, ValueError, TypeError):
        return None


def normalize_unit_string(raw_unit: Any) -> Optional[Tuple[str, str]]:
    """Normalize a unit string using Unicode NFKC and return (standard_key, dimension).

    Returns None if raw_unit is empty, whitespace, or unrecognized.
    """
    if raw_unit is None:
        return None
    s = str(raw_unit).strip()
    if not s:
        return None

    # Step 1: Unicode NFKC decomposition & composition
    # (maps U+00B5 to U+03BC, standardizes combined characters)
    s_nfkc = unicodedata.normalize("NFKC", s)
    lookup_key = s_nfkc.lower()

    if lookup_key in UNIT_ALIAS_MAP:
        return UNIT_ALIAS_MAP[lookup_key]

    # Step 2: Direct lookup before lowercasing (for symbols like %)
    s_raw_lower = s.lower()
    if s_raw_lower in UNIT_ALIAS_MAP:
        return UNIT_ALIAS_MAP[s_raw_lower]

    return None


def convert_and_normalize(
    value: Any,
    unit: Any,
    target_canonical_unit: Optional[str] = None,
    target_dimension: Optional[str] = None,
) -> Dict[str, Any]:
    """Normalize a measurement value and unit, and convert to canonical if compatible.

    Args:
        value: The measured numerical value (float, int, Decimal, or str).
        unit: The unit string (e.g. 'ug/L', 'µg/L', 'mg/L', 'g/L', 'pH', 'µS/cm').
        target_canonical_unit: Optional expected canonical unit (e.g. 'mg/L').
        target_dimension: Optional expected dimension (e.g. 'concentration').

    Returns:
        Structured dict with conversion details:
        - normalized_value: Decimal or None
        - canonical_unit: str or None
        - conversion_status: 'success' | 'unsupported_unit' | 'incompatible_dimension' | 'missing_value' | 'invalid_value'
        - reason_code: REASON_* or None
        - details: str explanation
        - original_value: Decimal or None
        - original_unit: str or None
        - dimension: str or None
    """
    # 1. Parse original numerical value
    d_val = to_decimal(value)
    if value is None or str(value).strip() == "":
        return {
            "normalized_value": None,
            "canonical_unit": None,
            "conversion_status": "missing_value",
            "reason_code": REASON_MISSING_MEASUREMENT_EVIDENCE,
            "details": "Measurement value is missing (null or empty).",
            "original_value": None,
            "original_unit": str(unit) if unit is not None else None,
            "dimension": None,
        }

    if d_val is None:
        return {
            "normalized_value": None,
            "canonical_unit": None,
            "conversion_status": "invalid_value",
            "reason_code": REASON_MISSING_MEASUREMENT_EVIDENCE,
            "details": f"Unparseable measurement value: '{value}'.",
            "original_value": None,
            "original_unit": str(unit) if unit is not None else None,
            "dimension": None,
        }

    # 2. Check for missing unit
    if unit is None or str(unit).strip() == "":
        return {
            "normalized_value": None,
            "canonical_unit": None,
            "conversion_status": "missing_unit",
            "reason_code": REASON_MISSING_MEASUREMENT_EVIDENCE,
            "details": "Measurement unit is missing (null or empty).",
            "original_value": d_val,
            "original_unit": None,
            "dimension": None,
        }

    # 3. Normalize unit string
    normalized_meta = normalize_unit_string(unit)
    if normalized_meta is None:
        return {
            "normalized_value": None,
            "canonical_unit": None,
            "conversion_status": "unsupported_unit",
            "reason_code": REASON_UNSUPPORTED_UNIT,
            "details": f"Unsupported or unrecognized measurement unit: '{unit}'.",
            "original_value": d_val,
            "original_unit": str(unit),
            "dimension": None,
        }

    std_unit, dimension = normalized_meta

    # 4. Infer target dimension if canonical target provided
    if target_canonical_unit is not None:
        target_norm = normalize_unit_string(target_canonical_unit)
        if target_norm:
            target_dimension = target_norm[1]

    # 5. Check dimensional compatibility if a target is requested
    if target_dimension is not None and dimension != target_dimension:
        return {
            "normalized_value": None,
            "canonical_unit": target_canonical_unit or CANONICAL_UNITS.get(target_dimension),
            "conversion_status": "incompatible_dimension",
            "reason_code": REASON_UNSUPPORTED_UNIT,
            "details": (
                f"Incompatible measurement dimension: '{unit}' is a {dimension} unit, "
                f"which cannot be converted to {target_dimension} ('{target_canonical_unit}')."
            ),
            "original_value": d_val,
            "original_unit": str(unit),
            "dimension": dimension,
        }

    # 6. Apply Decimal conversion based on dimension
    if dimension == "concentration":
        factor = CONCENTRATION_FACTORS_DECIMAL[std_unit]
        norm_val = d_val * factor
        canon_unit = CANONICAL_MASS_CONCENTRATION
    elif dimension == "conductivity":
        factor = CONDUCTIVITY_FACTORS_DECIMAL[std_unit]
        norm_val = d_val * factor
        canon_unit = CANONICAL_CONDUCTIVITY
    elif dimension in ("ph", "turbidity", "percentage", "bioburden", "particulate_count", "endotoxin"):
        # Single-unit dimensions: canonical unit is standard key, factor is 1
        norm_val = d_val
        canon_unit = std_unit
    else:
        return {
            "normalized_value": None,
            "canonical_unit": None,
            "conversion_status": "unsupported_unit",
            "reason_code": REASON_UNSUPPORTED_UNIT,
            "details": f"Dimension '{dimension}' has no defined canonical conversion.",
            "original_value": d_val,
            "original_unit": str(unit),
            "dimension": dimension,
        }

    return {
        "normalized_value": norm_val,
        "canonical_unit": canon_unit,
        "conversion_status": "success",
        "reason_code": None,
        "details": f"Normalized {d_val} {unit} -> {norm_val} {canon_unit}.",
        "original_value": d_val,
        "original_unit": str(unit),
        "dimension": dimension,
    }


def compare_measurement_uncertainty_v2(
    measured_value: Any,
    measurement_unit: Any,
    measurement_uncertainty: Any,
    sop_minimum: Any,
    sop_maximum: Any,
    canonical_unit: Any,
) -> Dict[str, Any]:
    """Evaluate measurement and uncertainty interval against SOP specification limits.

    Follows rigorous Decimal interval comparison:
    1. Normalizes value and uncertainty to canonical unit using Decimal.
    2. Constructs expanded interval [lower_bound, upper_bound] = [v - u, v + u].
    3. Compares interval against [sop_minimum, sop_maximum]:
       - pass: lower_bound >= sop_min and upper_bound <= sop_max (entire interval inside).
       - fail: upper_bound < sop_min or lower_bound > sop_max (entire interval outside).
       - needs_review (UNCERTAINTY_CROSSES_BOUNDARY): interval straddles boundary.

    Returns structured dictionary with complete mathematical audit trail.
    """
    # 1. Convert measured value
    conv_val = convert_and_normalize(
        value=measured_value,
        unit=measurement_unit,
        target_canonical_unit=str(canonical_unit) if canonical_unit else None,
    )
    if conv_val["conversion_status"] != "success":
        return {
            "status": "needs_review",
            "reason_code": conv_val["reason_code"],
            "details": conv_val["details"],
            "original_value": float(conv_val["original_value"]) if conv_val["original_value"] is not None else None,
            "original_unit": conv_val["original_unit"],
            "normalized_value": None,
            "canonical_unit": str(canonical_unit) if canonical_unit else None,
            "normalized_uncertainty": None,
            "lower_bound": None,
            "upper_bound": None,
            "sop_minimum": float(to_decimal(sop_minimum)) if to_decimal(sop_minimum) is not None else None,
            "sop_maximum": float(to_decimal(sop_maximum)) if to_decimal(sop_maximum) is not None else None,
        }

    norm_val: Decimal = conv_val["normalized_value"]
    canon_u: str = conv_val["canonical_unit"]

    # 2. Parse SOP limits
    d_min = to_decimal(sop_minimum)
    d_max = to_decimal(sop_maximum)
    if d_min is None or d_max is None:
        return {
            "status": "needs_review",
            "reason_code": REASON_MISSING_MEASUREMENT_EVIDENCE,
            "details": f"Missing or unparseable SOP limits: min={sop_minimum}, max={sop_maximum}.",
            "original_value": float(conv_val["original_value"]),
            "original_unit": conv_val["original_unit"],
            "normalized_value": float(norm_val),
            "canonical_unit": canon_u,
            "normalized_uncertainty": None,
            "lower_bound": None,
            "upper_bound": None,
            "sop_minimum": float(d_min) if d_min is not None else None,
            "sop_maximum": float(d_max) if d_max is not None else None,
        }

    # 3. Convert uncertainty (must be in same unit as measurement)
    d_unc_raw = to_decimal(measurement_uncertainty)
    if d_unc_raw is None or d_unc_raw < 0:
        return {
            "status": "needs_review",
            "reason_code": REASON_MISSING_MEASUREMENT_EVIDENCE,
            "details": f"Missing or invalid negative measurement uncertainty: '{measurement_uncertainty}'.",
            "original_value": float(conv_val["original_value"]),
            "original_unit": conv_val["original_unit"],
            "normalized_value": float(norm_val),
            "canonical_unit": canon_u,
            "normalized_uncertainty": None,
            "lower_bound": None,
            "upper_bound": None,
            "sop_minimum": float(d_min),
            "sop_maximum": float(d_max),
        }

    # Scale uncertainty with same factor as value
    norm_meta = normalize_unit_string(measurement_unit)
    assert norm_meta is not None
    std_unit, dimension = norm_meta
    if dimension == "concentration":
        factor = CONCENTRATION_FACTORS_DECIMAL[std_unit]
        norm_unc = d_unc_raw * factor
    elif dimension == "conductivity":
        factor = CONDUCTIVITY_FACTORS_DECIMAL[std_unit]
        norm_unc = d_unc_raw * factor
    else:
        norm_unc = d_unc_raw

    # 4. Construct expanded interval
    lower_bound = norm_val - norm_unc
    upper_bound = norm_val + norm_unc

    # 5. Evaluate interval against [d_min, d_max]
    # Case 1: Clearly within range (closed interval)
    if lower_bound >= d_min and upper_bound <= d_max:
        return {
            "status": "pass",
            "reason_code": None,
            "details": (
                f"Uncertainty interval [{lower_bound}, {upper_bound}] {canon_u} is within or "
                f"on the inclusive specification boundaries [{d_min}, {d_max}] {canon_u}."
            ),
            "original_value": float(conv_val["original_value"]),
            "original_unit": conv_val["original_unit"],
            "normalized_value": float(norm_val),
            "canonical_unit": canon_u,
            "normalized_uncertainty": float(norm_unc),
            "lower_bound": float(lower_bound),
            "upper_bound": float(upper_bound),
            "sop_minimum": float(d_min),
            "sop_maximum": float(d_max),
        }

    # Case 2: Clearly outside range (entire interval strictly outside)
    if upper_bound < d_min or lower_bound > d_max:
        return {
            "status": "fail",
            "reason_code": REASON_MEASUREMENT_OUT_OF_RANGE,
            "details": (
                f"Measurement interval [{lower_bound}, {upper_bound}] {canon_u} is strictly "
                f"outside SOP specification limits [{d_min}, {d_max}] {canon_u}."
            ),
            "original_value": float(conv_val["original_value"]),
            "original_unit": conv_val["original_unit"],
            "normalized_value": float(norm_val),
            "canonical_unit": canon_u,
            "normalized_uncertainty": float(norm_unc),
            "lower_bound": float(lower_bound),
            "upper_bound": float(upper_bound),
            "sop_minimum": float(d_min),
            "sop_maximum": float(d_max),
        }

    # Case 3: Boundary uncertainty (interval overlaps or crosses specification boundary)
    return {
        "status": "needs_review",
        "reason_code": REASON_UNCERTAINTY_CROSSES_BOUNDARY,
        "details": (
            f"Uncertainty interval [{lower_bound}, {upper_bound}] {canon_u} overlaps or crosses "
            f"SOP specification boundary [{d_min}, {d_max}] {canon_u}."
        ),
        "original_value": float(conv_val["original_value"]),
        "original_unit": conv_val["original_unit"],
        "normalized_value": float(norm_val),
        "canonical_unit": canon_u,
        "normalized_uncertainty": float(norm_unc),
        "lower_bound": float(lower_bound),
        "upper_bound": float(upper_bound),
        "sop_minimum": float(d_min),
        "sop_maximum": float(d_max),
    }

