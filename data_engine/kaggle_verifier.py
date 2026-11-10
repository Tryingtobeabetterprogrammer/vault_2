"""VAULT Deterministic Verifier for Kaggle Environmental Telemetry.

Applies deterministic physical plausibility, CPCB NAQI bucket consistency,
chronological validation, and laboratory evidence completeness checks.
"""

from __future__ import annotations

from datetime import datetime
import math
from typing import Any, Dict, List, Optional, Tuple

from data_engine.kaggle_adapter import AQI_BUCKET_LIMITS, KAGGLE_MEASURAND_UNITS

# Standard Reason Codes for Kaggle Environmental Verification
REASON_NEGATIVE_POLLUTANT_VALUE = "PHYSICAL_IMPOSSIBILITY_NEGATIVE_VALUE"
REASON_AQI_BUCKET_CONTRADICTION = "AQI_BUCKET_CONTRADICTION"
REASON_MISSING_AQI_AND_BUCKET = "MISSING_AQI_EVIDENCE"
REASON_INSUFFICIENT_POLLUTANT_DATA = "INSUFFICIENT_POLLUTANT_DATA"
REASON_EXTREME_OUTLIER = "EXTREME_OUTLIER_UNVERIFIED"
REASON_DATE_OUT_OF_RANGE = "DATE_OUT_OF_STUDY_RANGE"
REASON_MISSING_CALIBRATION_EVIDENCE = "MISSING_LABORATORY_CALIBRATION_EVIDENCE"
REASON_MISSING_SOP_EVIDENCE = "MISSING_SOP_GOVERNANCE_EVIDENCE"
REASON_MISSING_UNCERTAINTY = "MISSING_MEASUREMENT_UNCERTAINTY"

# Documented Plausibility Upper Bounds (ug/m3, CO in mg/m3)
PLAUSIBLE_UPPER_BOUNDS = {
    "PM2.5": 2000.0,
    "PM10": 3000.0,
    "NO": 1000.0,
    "NO2": 1000.0,
    "NOx": 1000.0,
    "NH3": 1500.0,
    "CO": 200.0,
    "SO2": 1000.0,
    "O3": 1000.0,
    "Benzene": 500.0,
    "Toluene": 1000.0,
    "Xylene": 1000.0,
}


def verify_kaggle_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Execute deterministic physical, mathematical, and evidence verification on a Kaggle record."""
    record_id = record["record_id"]
    measurements = record.get("measurements", {})
    aqi = record.get("aqi")
    aqi_bucket = record.get("aqi_bucket")
    run_date_str = record.get("run_date", "")

    issues: List[str] = []
    evidence: List[Dict[str, Any]] = []

    # 1. Date Plausibility Check (2015-01-01 to 2020-12-31)
    try:
        run_date = datetime.strptime(run_date_str, "%Y-%m-%d").date()
        if run_date.year < 2015 or run_date.year > 2020:
            issues.append(REASON_DATE_OUT_OF_RANGE)
            evidence.append({
                "check": "date_plausibility",
                "status": "fail",
                "details": f"Date {run_date_str} lies outside the 2015-2020 CPCB study epoch.",
            })
        else:
            evidence.append({
                "check": "date_plausibility",
                "status": "pass",
                "details": f"Date {run_date_str} is within valid study window.",
            })
    except ValueError:
        issues.append(REASON_DATE_OUT_OF_RANGE)
        evidence.append({
            "check": "date_plausibility",
            "status": "fail",
            "details": f"Unparseable date string '{run_date_str}'.",
        })

    # 2. Physical Concentration Checks (Non-negativity and Plausible Bounds)
    valid_meas_count = 0
    for param, val in measurements.items():
        if val is not None and not math.isnan(val):
            valid_meas_count += 1
            if val < 0.0:
                issues.append(REASON_NEGATIVE_POLLUTANT_VALUE)
                evidence.append({
                    "check": "physical_plausibility",
                    "status": "fail",
                    "parameter": param,
                    "value": val,
                    "unit": KAGGLE_MEASURAND_UNITS.get(param, "unknown"),
                    "details": f"Physical impossibility: Negative concentration {val} reported for {param}.",
                })
            elif val > PLAUSIBLE_UPPER_BOUNDS.get(param, 5000.0):
                issues.append(REASON_EXTREME_OUTLIER)
                evidence.append({
                    "check": "physical_plausibility",
                    "status": "fail",
                    "parameter": param,
                    "value": val,
                    "details": f"Extreme outlier concentration {val} exceeds plausible ambient ceiling {PLAUSIBLE_UPPER_BOUNDS[param]}.",
                })

    if valid_meas_count == 0:
        issues.append(REASON_INSUFFICIENT_POLLUTANT_DATA)
        evidence.append({
            "check": "pollutant_completeness",
            "status": "fail",
            "details": "Zero valid pollutant concentration measurements reported.",
        })

    # 3. AQI and AQI_Bucket Mathematical Consistency Check (Official CPCB NAQI Scale: 0 to 500)
    # Note: This checks reported AQI versus reported AQI_Bucket consistency.
    # Independent AQI recalculation from raw pollutant concentrations is a separate capability (documented below).
    if aqi is not None and aqi_bucket:
        expected_limits = AQI_BUCKET_LIMITS.get(aqi_bucket)
        if expected_limits:
            min_lim, max_lim = expected_limits
            if not (min_lim <= aqi <= max_lim):
                issues.append(REASON_AQI_BUCKET_CONTRADICTION)
                evidence.append({
                    "check": "aqi_bucket_consistency",
                    "status": "fail",
                    "reported_aqi": aqi,
                    "reported_bucket": aqi_bucket,
                    "expected_interval": [min_lim, max_lim],
                    "details": f"Mathematical contradiction: AQI {aqi} falls outside CPCB '{aqi_bucket}' limits [{min_lim}, {max_lim}] (official NAQI scale max is 500).",
                })
            else:
                evidence.append({
                    "check": "aqi_bucket_consistency",
                    "status": "pass",
                    "reported_aqi": aqi,
                    "reported_bucket": aqi_bucket,
                    "expected_interval": [min_lim, max_lim],
                    "details": f"AQI {aqi} conforms strictly to '{aqi_bucket}' interval [{min_lim}, {max_lim}].",
                })
        else:
            issues.append(REASON_AQI_BUCKET_CONTRADICTION)
            evidence.append({
                "check": "aqi_bucket_consistency",
                "status": "fail",
                "details": f"Unrecognized CPCB AQI Bucket '{aqi_bucket}'.",
            })
    elif aqi is None and (aqi_bucket is None or aqi_bucket == ""):
        issues.append(REASON_MISSING_AQI_AND_BUCKET)
        evidence.append({
            "check": "aqi_presence",
            "status": "needs_review",
            "details": "AQI and AQI Bucket are both absent.",
        })
    else:
        # Partial AQI information: one present, other missing
        issues.append(REASON_AQI_BUCKET_CONTRADICTION)
        evidence.append({
            "check": "aqi_bucket_consistency",
            "status": "fail",
            "reported_aqi": aqi,
            "reported_bucket": aqi_bucket,
            "details": "Inconsistency: AQI numerical value and categorical bucket must be provided together.",
        })

    # Explicit Scale Boundary Check (0 to 500)
    if aqi is not None and (aqi < 0.0 or aqi > 500.0):
        if REASON_AQI_BUCKET_CONTRADICTION not in issues:
            issues.append(REASON_AQI_BUCKET_CONTRADICTION)
        evidence.append({
            "check": "aqi_scale_range",
            "status": "fail",
            "reported_aqi": aqi,
            "details": f"Out of scale: Reported AQI {aqi} exceeds the official CPCB NAQI scale maximum of 500.",
        })

    # Independent AQI Recalculation Check (Explicitly Decoupled and Documented Scope)
    evidence.append({
        "check": "aqi_independent_recalculation",
        "status": "outside_scope",
        "details": (
            "Independent AQI recalculation from raw pollutant concentrations requires "
            "complete CPCB sub-index linear interpolation (minimum 3 pollutants with at least "
            "one PM2.5 or PM10, 24-hr averaging periods, and truncated integer conversions). "
            "Independent recalculation is not implemented and is outside the current experiment scope."
        ),
    })

    # 4. Laboratory Evidence Completeness Checks (VAULT Core Doctrine)
    # Kaggle ambient records NEVER contain calibration or SOP metadata
    evidence.append({
        "check": "laboratory_calibration_evidence",
        "status": "needs_review",
        "reason": REASON_MISSING_CALIBRATION_EVIDENCE,
        "details": "Absence of certified laboratory calibration window or sensor maintenance ledger.",
    })
    evidence.append({
        "check": "sop_governance_evidence",
        "status": "needs_review",
        "reason": REASON_MISSING_SOP_EVIDENCE,
        "details": "Absence of formalized standard operating procedure (SOP) clause or accreditation standard.",
    })
    evidence.append({
        "check": "measurement_uncertainty_evidence",
        "status": "needs_review",
        "reason": REASON_MISSING_UNCERTAINTY,
        "details": "Absence of expanded measurement uncertainty (k=2, 95% confidence margin).",
    })

    # Deduplicate issues
    deduped_issues = list(dict.fromkeys(issues))

    # 5. Determine VAULT Status & Verdict
    # Hard failures (negatives, contradictions, unparseable dates, zero pollutants) -> FLAGGED / INVALID
    hard_defect_reasons = {
        REASON_NEGATIVE_POLLUTANT_VALUE,
        REASON_AQI_BUCKET_CONTRADICTION,
        REASON_DATE_OUT_OF_RANGE,
        REASON_INSUFFICIENT_POLLUTANT_DATA,
        REASON_EXTREME_OUTLIER,
    }
    has_hard_defects = any(r in hard_defect_reasons for r in deduped_issues)

    if has_hard_defects:
        status = "flagged"
        verdict = "invalid"
        abstain = False
    else:
        # No hard defects, but laboratory evidence is completely missing -> NEEDS_REVIEW / UNVERIFIED
        # In strict adherence to VAULT non-negotiable principles:
        # "Do not infer laboratory compliance from AQI classifications."
        status = "needs_review"
        verdict = "unverified"
        abstain = True
        deduped_issues.extend([
            REASON_MISSING_CALIBRATION_EVIDENCE,
            REASON_MISSING_SOP_EVIDENCE,
            REASON_MISSING_UNCERTAINTY,
        ])
        if REASON_MISSING_AQI_AND_BUCKET in issues and REASON_MISSING_AQI_AND_BUCKET not in deduped_issues:
            deduped_issues.append(REASON_MISSING_AQI_AND_BUCKET)

    return {
        "assessment_id": f"ASM-KAG-{hash(record_id) & 0xFFFFFFFF:08X}",
        "record_id": record_id,
        "status": status,
        "verdict": verdict,
        "abstain": abstain,
        "issues": deduped_issues,
        "evidence": evidence,
        "derived": {
            "city": record.get("city"),
            "run_date": run_date_str,
            "valid_pollutants_count": valid_meas_count,
            "aqi": aqi,
            "aqi_bucket": aqi_bucket,
        },
        "engine_version": "2.0.0-kaggle-adapter",
        "reviewer_state": "automated_kaggle_validator",
    }

