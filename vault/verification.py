"""VAULT Core Deterministic Verifier.

Provides independent, auditable verification of scientific laboratory experiment
records with explicit reason codes, recalculation evidence, and provenance.
Adheres to contracts/assessment.schema.json and contracts/record.schema.json.
"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import uuid

from synth.rules_v2 import (
    validate_sop_v2,
    validate_calibration_v2,
    validate_lot_v2,
    validate_holding_time_v2,
    validate_measurement_v2,
)
from synth.units_v2 import (
    normalize_unit_string,
    convert_and_normalize,
    compare_measurement_uncertainty_v2,
    CANONICAL_UNITS,
)

ENGINE_VERSION = "2.0.0"

# Default catalog cache
_CATALOG_CACHE: Optional[Dict[str, Any]] = None


def get_default_catalogs() -> Dict[str, Any]:
    """Load default catalogs from data/raw_v2 or data/raw if available."""
    global _CATALOG_CACHE
    if _CATALOG_CACHE is not None:
        return _CATALOG_CACHE

    catalogs: Dict[str, Any] = {
        "sops": {},
        "instruments": {},
        "lots": {},
        "samples": {},
    }

    base_v2 = Path("data/raw_v2")
    base_v1 = Path("data/raw")
    target_base = base_v2 if base_v2.exists() else base_v1

    # Load SOPs
    sop_file = target_base / ("sops_v2.jsonl" if target_base == base_v2 else "sops_v1.jsonl")
    if sop_file.exists():
        with open(sop_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    c = json.loads(line)
                    catalogs["sops"][(c["clause_id"], c.get("sop_version"))] = c
                    # Also map clause_id alone for fallback
                    if c["clause_id"] not in catalogs["sops"]:
                        catalogs["sops"][c["clause_id"]] = c

    # Load Instruments
    inst_file = target_base / ("instruments_v2.jsonl" if target_base == base_v2 else "instruments_v1.jsonl")
    if inst_file.exists():
        with open(inst_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    catalogs["instruments"][item["instrument_id"]] = item

    # Load Lots
    lot_file = target_base / ("lots_v2.jsonl" if target_base == base_v2 else "lots_v1.jsonl")
    if lot_file.exists():
        with open(lot_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    catalogs["lots"][item["lot_id"]] = item

    # Load Samples
    samp_file = target_base / ("samples_v2.jsonl" if target_base == base_v2 else "samples_v1.jsonl")
    if samp_file.exists():
        with open(samp_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    catalogs["samples"][item["sample_id"]] = item

    _CATALOG_CACHE = catalogs
    return catalogs


def verify_arithmetic(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Check explicit arithmetic consistency when components (e.g. mass, volume) are supplied.
    
    Example: 15 mg in 0.5 L reported as 3 mg/L -> recomputed is 30 mg/L -> flag contradiction.
    """
    mass = record.get("reported_mass") or record.get("mass_mg")
    volume = record.get("reported_volume") or record.get("volume_L")
    measured = record.get("measured_value")

    if mass is not None and volume is not None and measured is not None:
        try:
            m_dec = Decimal(str(mass))
            v_dec = Decimal(str(volume))
            meas_dec = Decimal(str(measured))

            if v_dec == Decimal("0"):
                return {
                    "rule_name": "arithmetic_verification",
                    "status": "needs_review",
                    "reason": "DIVISION_BY_ZERO",
                    "details": {"mass": str(m_dec), "volume": str(v_dec)},
                    "evidence_refs": ["reported_mass", "reported_volume"]
                }

            expected_conc = m_dec / v_dec
            diff = abs(meas_dec - expected_conc)
            rel_tol = Decimal("0.001")

            if diff > (expected_conc * rel_tol):
                return {
                    "rule_name": "arithmetic_verification",
                    "status": "fail",
                    "reason": "ARITHMETIC_CONTRADICTION",
                    "details": {
                        "mass_mg": float(m_dec),
                        "volume_L": float(v_dec),
                        "expected_concentration_mg_L": float(expected_conc),
                        "reported_concentration": float(meas_dec),
                        "formula": "concentration = mass / volume"
                    },
                    "evidence_refs": ["reported_mass", "reported_volume", "measured_value"]
                }
            else:
                return {
                    "rule_name": "arithmetic_verification",
                    "status": "pass",
                    "reason": None,
                    "details": {
                        "expected_concentration": float(expected_conc),
                        "reported_concentration": float(meas_dec),
                    },
                    "evidence_refs": ["reported_mass", "reported_volume", "measured_value"]
                }
        except (InvalidOperation, TypeError, ValueError) as err:
            return {
                "rule_name": "arithmetic_verification",
                "status": "needs_review",
                "reason": "UNPARSEABLE_ARITHMETIC_INPUT",
                "details": {"error": str(err)},
                "evidence_refs": ["reported_mass", "reported_volume"]
            }
    return None


def verify_method_adherence(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Evaluate method adherence, distinguishing standard, alternative, and novel methods.
    
    - Standard method: validated normally against standard measurand threshold.
    - Valid alternative method (e.g. measuring available rather than total): evaluates distinct measurand.
    - Unfamiliar/novel method: lacking validated reference -> needs_review (NOT proof of error).
    """
    method_id = record.get("method_id")
    if not method_id:
        return None

    # Recognized standard and validated alternative methods
    validated_methods = {
        "STD-001": {"type": "standard", "measurand": "total_concentration"},
        "STD-002": {"type": "standard", "measurand": "turbidity"},
        "ALT-AVAIL-01": {
            "type": "alternative",
            "measurand": "bioavailable_concentration",
            "availability_factor": Decimal("0.75"),
            "target_threshold_mg_L": Decimal("150.0")
        }
    }

    if method_id in validated_methods:
        method_meta = validated_methods[method_id]
        if method_meta["type"] == "alternative":
            # Documented alternative method estimates a distinct quantity
            meas = record.get("measured_value")
            if meas is not None:
                try:
                    m_dec = Decimal(str(meas))
                    factor = method_meta["availability_factor"]
                    available_conc = m_dec * factor
                    threshold = method_meta["target_threshold_mg_L"]

                    if available_conc <= threshold:
                        return {
                            "rule_name": "method_verification",
                            "status": "pass",
                            "reason": None,
                            "details": {
                                "method_id": method_id,
                                "method_type": "validated_alternative",
                                "measurand": method_meta["measurand"],
                                "availability_factor": float(factor),
                                "calculated_available_concentration": float(available_conc),
                                "threshold": float(threshold)
                            },
                            "evidence_refs": [f"method_id:{method_id}"]
                        }
                    else:
                        return {
                            "rule_name": "method_verification",
                            "status": "fail",
                            "reason": "ALTERNATIVE_METHOD_EXCEEDED_THRESHOLD",
                            "details": {
                                "method_id": method_id,
                                "calculated_available_concentration": float(available_conc),
                                "threshold": float(threshold)
                            },
                            "evidence_refs": [f"method_id:{method_id}"]
                        }
                except (InvalidOperation, TypeError):
                    pass
        return {
            "rule_name": "method_verification",
            "status": "pass",
            "reason": None,
            "details": {"method_id": method_id, "method_type": method_meta["type"]},
            "evidence_refs": [f"method_id:{method_id}"]
        }
    else:
        # Novel / unfamiliar method without validated reference
        return {
            "rule_name": "method_verification",
            "status": "needs_review",
            "reason": "NOVEL_METHOD_UNVALIDATED",
            "details": {
                "method_id": method_id,
                "note": "Unfamiliar analytical formula lacks validated reference or assumptions; requires expert scientific review."
            },
            "evidence_refs": [f"method_id:{method_id}"]
        }


def verify_record(
    record: Dict[str, Any],
    catalogs: Optional[Dict[str, Any]] = None,
    assessment_id: Optional[str] = None
) -> Dict[str, Any]:
    """Verify an individual laboratory experiment record deterministically.
    
    Args:
        record: Raw experiment record dictionary conforming to contracts/record.schema.json.
        catalogs: Optional catalog dictionaries for SOPs, instruments, lots, samples.
        assessment_id: Optional unique identifier for this assessment (UUID generated if None).
        
    Returns:
        Assessment dictionary conforming to contracts/assessment.schema.json.
    """
    if catalogs is None:
        catalogs = get_default_catalogs()

    record_id = record.get("record_id") or record.get("experiment_id") or "UNKNOWN"
    created_at = datetime.now(timezone.utc).isoformat()
    asm_id = assessment_id or f"ASM-{uuid.uuid4().hex[:12].upper()}"

    evidence_list: List[Dict[str, Any]] = []
    issues_set: List[str] = []

    # Helper to extract primary reason and append all reason codes
    def add_rule_evidence(rule_name: str, r_out: Dict[str, Any], refs: List[str]) -> None:
        codes = r_out.get("reason_codes", [])
        primary = codes[0] if codes else r_out.get("reason")
        evidence_list.append({
            "rule_name": rule_name,
            "status": r_out["status"],
            "reason": primary,
            "details": r_out.get("details", {}),
            "evidence_refs": refs
        })
        for c in codes:
            issues_set.append(c)
        if r_out.get("reason") and r_out.get("reason") not in codes:
            issues_set.append(r_out["reason"])

    # 1. SOP Validation
    r_sop = validate_sop_v2(record, catalogs.get("sops", {}))
    add_rule_evidence("sop_validation", r_sop, [f"sop_id:{record.get('sop_id')}", f"clause_id:{record.get('clause_id')}"])

    # 2. Calibration Validation
    r_cal = validate_calibration_v2(record, catalogs.get("instruments", {}))
    add_rule_evidence("calibration_validation", r_cal, [f"instrument_id:{record.get('instrument_id')}"])

    # 3. Lot Validation
    r_lot = validate_lot_v2(record, catalogs.get("lots", {}))
    add_rule_evidence("lot_validation", r_lot, [f"lot_id:{record.get('lot_id')}"])

    # 4. Holding Time & Timestamp Validation
    r_hold = validate_holding_time_v2(record, catalogs.get("samples", {}))
    add_rule_evidence("holding_time_validation", r_hold, [f"sample_id:{record.get('sample_id')}"])

    # 5. Measurement Validation
    r_meas = validate_measurement_v2(record, catalogs.get("sops", {}))
    add_rule_evidence("measurement_validation", r_meas, [f"clause_id:{record.get('clause_id')}"])

    # 6. Explicit Arithmetic Check (if mass/volume present)
    r_arith = verify_arithmetic(record)
    if r_arith is not None:
        evidence_list.append(r_arith)
        if r_arith.get("reason"):
            issues_set.append(r_arith["reason"])

    # 7. Method / Measurand Adherence Check (if method_id present)
    r_method = verify_method_adherence(record)
    if r_method is not None:
        evidence_list.append(r_method)
        if r_method.get("reason"):
            issues_set.append(r_method["reason"])

    # Derived measurements compilation from calculated_values
    m_calc = r_meas.get("calculated_values", {})
    h_calc = r_hold.get("calculated_values", {})
    derived = {
        "normalized_value": m_calc.get("normalized_value"),
        "canonical_unit": m_calc.get("canonical_unit"),
        "specification_limits": {
            "min": m_calc.get("minimum_value"),
            "max": m_calc.get("maximum_value"),
            "unit": m_calc.get("canonical_unit")
        },
        "holding_time_hours": h_calc.get("elapsed_hours"),
        "max_holding_hours": h_calc.get("max_holding_hours"),
        "instrument_status": r_cal["status"],
        "lot_status": r_lot["status"],
        "sop_status": r_sop["status"]
    }

    # Precedence & Final Verdict Resolution
    has_review = any(e["status"] == "needs_review" for e in evidence_list)
    has_failure = any(e["status"] == "fail" for e in evidence_list)

    if has_review:
        status = "needs_review"
        verdict = "needs_review"
        abstain = True
    elif has_failure:
        status = "flagged"
        verdict = "invalid"
        abstain = False
    else:
        status = "checks_passed"
        verdict = "valid"
        abstain = False

    # Deduplicate issues while preserving insertion order
    deduped_issues = list(dict.fromkeys(issues_set))

    assessment: Dict[str, Any] = {
        "assessment_id": asm_id,
        "record_id": record_id,
        "supersedes_id": record.get("supersedes_assessment_id"),
        "status": status,
        "verdict": verdict,
        "abstain": abstain,
        "original_verdict": record.get("original_verdict"),
        "issues": deduped_issues,
        "evidence": evidence_list,
        "derived": derived,
        "engine_version": ENGINE_VERSION,
        "created_at": created_at,
        "reviewer_state": "automated"
    }

    return assessment
