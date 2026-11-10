"""VAULT V2 Deterministic Laboratory Validation Rules Engine.

Implements five rigorous, deterministic validation rules:
1. validate_sop_v2(): SOP version, validity windows, grandfathering, and conflict detection.
2. validate_calibration_v2(): Instrument calibration date and inclusive expiration.
3. validate_lot_v2(): Reagent lot manufacture date and inclusive expiration.
4. validate_holding_time_v2(): ISO 8601 timezone-aware & site-localized holding time.
5. validate_measurement_v2(): Decimal unit normalization & uncertainty interval evaluation.

Standard output contract for every rule:
{
    "rule_name": str,
    "status": "pass" | "fail" | "needs_review",
    "reason_codes": List[str],
    "details": str,
    "source_ids": List[str],
    "calculated_values": Dict[str, Any]
}
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import zoneinfo

from synth import units_v2

# ------------------------------------------------------------------------------
# Configuration Loader
# ------------------------------------------------------------------------------

_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "simulator_config_v2.json",
)

_CACHED_CONFIG: Optional[Dict[str, Any]] = None


def get_v2_config() -> Dict[str, Any]:
    """Load and cache simulator_config_v2.json."""
    global _CACHED_CONFIG
    if _CACHED_CONFIG is None:
        if os.path.exists(_CONFIG_PATH):
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                _CACHED_CONFIG = json.load(f)
        else:
            _CACHED_CONFIG = {}
    return _CACHED_CONFIG


# ------------------------------------------------------------------------------
# Standard Reason Codes for V2
# ------------------------------------------------------------------------------

REASON_SOP_VERSION_INVALID = "SOP_VERSION_INVALID"
REASON_SOP_VERSION_CONFLICT = "SOP_VERSION_CONFLICT"
REASON_MISSING_SOP_EVIDENCE = "MISSING_SOP_EVIDENCE"
REASON_MISSING_SOP_VERSION = "MISSING_SOP_VERSION"

REASON_CALIBRATION_EXPIRED = "CALIBRATION_EXPIRED"
REASON_CALIBRATION_NOT_YET_VALID = "CALIBRATION_NOT_YET_VALID"
REASON_MISSING_INSTRUMENT_EVIDENCE = "MISSING_INSTRUMENT_EVIDENCE"

REASON_LOT_EXPIRED = "LOT_EXPIRED"
REASON_LOT_NOT_YET_VALID = "LOT_NOT_YET_VALID"
REASON_MISSING_REAGENT_EVIDENCE = "MISSING_REAGENT_EVIDENCE"

REASON_HOLDING_TIME_EXCEEDED = "HOLDING_TIME_EXCEEDED"
REASON_INVALID_TIMESTAMP_ORDER = "INVALID_TIMESTAMP_ORDER"
REASON_MISSING_SAMPLE_EVIDENCE = "MISSING_SAMPLE_EVIDENCE"
REASON_AMBIGUOUS_TIMEZONE = "AMBIGUOUS_TIMEZONE"
REASON_UNPARSEABLE_TIMESTAMP = "UNPARSEABLE_TIMESTAMP"

REASON_MEASUREMENT_OUT_OF_RANGE = units_v2.REASON_MEASUREMENT_OUT_OF_RANGE
REASON_UNCERTAINTY_CROSSES_BOUNDARY = units_v2.REASON_UNCERTAINTY_CROSSES_BOUNDARY
REASON_UNSUPPORTED_UNIT = units_v2.REASON_UNSUPPORTED_UNIT
REASON_MISSING_MEASUREMENT_EVIDENCE = units_v2.REASON_MISSING_MEASUREMENT_EVIDENCE

REASON_FOREIGN_KEY_NOT_FOUND = "FOREIGN_KEY_NOT_FOUND"


# ------------------------------------------------------------------------------
# Helper Utilities
# ------------------------------------------------------------------------------

def _format_rule_result(
    rule_name: str,
    status: str,
    reason_codes: List[str],
    details: str,
    source_ids: Optional[List[str]] = None,
    calculated_values: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Format standard output dictionary adhering strictly to the V2 contract."""
    assert status in ("pass", "fail", "needs_review"), f"Invalid rule status: {status}"
    return {
        "rule_name": rule_name,
        "status": status,
        "reason_codes": list(dict.fromkeys(reason_codes)),  # preserve order, unique
        "details": details,
        "source_ids": source_ids or [],
        "calculated_values": calculated_values or {},
    }


def _parse_date(val: Any) -> Optional[date]:
    """Parse a date from string, date, or datetime object."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        val_clean = val.strip()
        if not val_clean:
            return None
        # Handle ISO strings with time component
        if "T" in val_clean:
            val_clean = val_clean.split("T")[0]
        try:
            return date.fromisoformat(val_clean)
        except ValueError:
            return None
    return None


def _resolve_datetime_v2(
    ts_val: Any,
    site_id: Optional[str] = None,
    site_timezone: Optional[str] = None,
    site_catalog: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[datetime], Optional[str]]:
    """Parse and normalize timestamp to UTC with strict timezone resolution.

    Returns:
        (utc_datetime, error_reason_code)
        If parsing succeeds, error_reason_code is None.
        If timezone is naive and unresolvable, returns (None, REASON_AMBIGUOUS_TIMEZONE).
        If string is malformed or unparseable, returns (None, REASON_UNPARSEABLE_TIMESTAMP).
    """
    if ts_val is None:
        return None, None

    dt_obj: Optional[datetime] = None
    if isinstance(ts_val, datetime):
        dt_obj = ts_val
    elif isinstance(ts_val, str):
        s = ts_val.strip()
        if not s:
            return None, None
        # Handle trailing Z
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            dt_obj = datetime.fromisoformat(s)
        except ValueError:
            return None, REASON_UNPARSEABLE_TIMESTAMP
    else:
        return None, REASON_UNPARSEABLE_TIMESTAMP

    # Case A: Timestamp has an explicit timezone offset
    if dt_obj.tzinfo is not None:
        try:
            return dt_obj.astimezone(timezone.utc), None
        except Exception:
            return None, REASON_AMBIGUOUS_TIMEZONE

    # Case B: Timestamp is naive. Resolve via documented site timezone
    resolved_tz_name: Optional[str] = site_timezone

    if not resolved_tz_name and site_id:
        # Lookup in provided catalog or global config
        catalog = site_catalog
        if catalog is None:
            cfg = get_v2_config()
            catalog = cfg.get("site_timezones", {}).get("sites", {})
        if site_id in catalog:
            site_info = catalog[site_id]
            resolved_tz_name = site_info.get("timezone")

    if not resolved_tz_name:
        # Strict policy: Never silently assume UTC for naive timestamps!
        return None, REASON_AMBIGUOUS_TIMEZONE

    try:
        tz = zoneinfo.ZoneInfo(resolved_tz_name)
    except Exception:
        return None, REASON_AMBIGUOUS_TIMEZONE

    # Check for DST nonexistent or ambiguous times
    # In zoneinfo, attaching tzinfo=tz on naive datetime can encounter fold ambiguity or gap
    try:
        # Standard localization with fold=0
        dt_localized = dt_obj.replace(tzinfo=tz)
        # Verify round-trip conversion to detect nonexistent spring-forward gaps
        # If in a gap, converting to UTC and back changes the local representation
        dt_utc = dt_localized.astimezone(timezone.utc)
        dt_back = dt_utc.astimezone(tz)
        if dt_back.replace(tzinfo=None) != dt_obj:
            # Timestamp lands in a nonexistent DST spring-forward gap!
            return None, REASON_AMBIGUOUS_TIMEZONE

        return dt_utc, None
    except Exception:
        return None, REASON_AMBIGUOUS_TIMEZONE


# ------------------------------------------------------------------------------
# Rule 1: SOP Validation
# ------------------------------------------------------------------------------

def validate_sop_v2(
    experiment: Optional[Dict[str, Any]] = None,
    sops: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None,
    *,
    sop_id: Optional[str] = None,
    sop_version: Optional[str] = None,
    clause_id: Optional[str] = None,
    run_date: Optional[Union[str, date, datetime]] = None,
    config: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Validate whether an SOP version is applicable on the experiment run date.

    Conditions:
    - Checks effective_date and superseded_date.
    - Check whether selected SOP version is explicitly recorded.
    - An explicitly selected version can be evaluated during an overlap only if the
      configured laboratory transition policy authorizes it.
    - Unauthorized, premature, or superseded version -> fail, SOP_VERSION_INVALID.
    - Missing SOP reference -> needs_review, MISSING_SOP_EVIDENCE.
    - Broken foreign key -> needs_review, FOREIGN_KEY_NOT_FOUND.
    - Missing version with multiple active versions having divergent requirements ->
      needs_review, SOP_VERSION_CONFLICT.
    - Missing version with multiple active versions having identical requirements ->
      needs_review, MISSING_SOP_VERSION.
    - Do not treat every date overlap as a conflict automatically.
    """
    cfg = config or get_v2_config()
    trans_policy = cfg.get("sop_transition_policy", {})
    allow_grandfathered = trans_policy.get(
        "allow_explicit_grandfathered_version_until_superseded", True
    )

    if experiment:
        sop_id = sop_id or experiment.get("sop_id")
        sop_version = sop_version if sop_version is not None else experiment.get("sop_version")
        clause_id = clause_id or experiment.get("clause_id")
        run_date = run_date or experiment.get("run_date")

    source_ids: List[str] = []
    if sop_id:
        source_ids.append(str(sop_id))
    if clause_id and clause_id not in source_ids:
        source_ids.append(str(clause_id))

    # 1. Check for missing SOP identifier
    if not sop_id or str(sop_id).strip() == "":
        return _format_rule_result(
            rule_name="sop",
            status="needs_review",
            reason_codes=[REASON_MISSING_SOP_EVIDENCE],
            details="Missing SOP identifier (sop_id is null or empty).",
            source_ids=source_ids,
        )

    # 2. Check for missing run date
    run_dt = _parse_date(run_date)
    if run_dt is None:
        return _format_rule_result(
            rule_name="sop",
            status="needs_review",
            reason_codes=[REASON_MISSING_SOP_EVIDENCE],
            details="Missing or unparseable experiment run_date.",
            source_ids=source_ids,
            calculated_values={"sop_id": str(sop_id)},
        )

    # 3. Lookup SOP in catalog if provided
    if sops is None:
        # Fallback evaluation when catalog is not passed directly
        return _format_rule_result(
            rule_name="sop",
            status="needs_review",
            reason_codes=[REASON_MISSING_SOP_EVIDENCE],
            details="SOP catalog not provided for validation.",
            source_ids=source_ids,
        )

    sop_list = sops if isinstance(sops, list) else (list(sops.values()) if isinstance(sops, dict) else [sops])
    matching_sop_records = [r for r in sop_list if str(r.get("sop_id")) == str(sop_id)]
    if not matching_sop_records:
        return _format_rule_result(
            rule_name="sop",
            status="needs_review",
            reason_codes=[REASON_FOREIGN_KEY_NOT_FOUND],
            details=f"SOP identifier '{sop_id}' not found in SOP catalog.",
            source_ids=source_ids,
            calculated_values={"sop_id": str(sop_id), "run_date": run_dt.isoformat()},
        )

    # Filter to matching clause if clause_id is provided
    target_clause_records = matching_sop_records
    if clause_id:
        target_clause_records = [
            r for r in matching_sop_records if str(r.get("clause_id")) == str(clause_id)
        ]
        if not target_clause_records:
            return _format_rule_result(
                rule_name="sop",
                status="needs_review",
                reason_codes=[REASON_FOREIGN_KEY_NOT_FOUND],
                details=f"Clause '{clause_id}' does not belong to SOP '{sop_id}'.",
                source_ids=source_ids,
                calculated_values={
                    "sop_id": str(sop_id),
                    "clause_id": str(clause_id),
                    "run_date": run_dt.isoformat(),
                },
            )

    # Aggregate active versions on run_date for the relevant clauses
    # Structure: version_str -> {record, effective_date, superseded_date, specs}
    active_versions: Dict[str, Dict[str, Any]] = {}
    all_version_records: Dict[str, List[Dict[str, Any]]] = {}

    for rec in target_clause_records:
        v_str = str(rec.get("sop_version", "")).strip()
        if not v_str:
            continue
        all_version_records.setdefault(v_str, []).append(rec)
        eff = _parse_date(rec.get("effective_date"))
        sup = _parse_date(rec.get("superseded_date"))

        # Active check: effective_date <= run_date and (superseded_date is None or run_date < superseded_date)
        if eff is not None and eff <= run_dt:
            if sup is None or run_dt < sup:
                active_versions[v_str] = {
                    "effective_date": eff,
                    "superseded_date": sup,
                    "record": rec,
                    "min": rec.get("minimum_value"),
                    "max": rec.get("maximum_value"),
                    "unit": rec.get("canonical_unit"),
                }

    has_explicit_version = sop_version is not None and str(sop_version).strip() != ""
    explicit_v_str = str(sop_version).strip() if has_explicit_version else None

    # Case A: Explicit Version Provided
    if has_explicit_version and explicit_v_str is not None:
        if explicit_v_str not in all_version_records:
            return _format_rule_result(
                rule_name="sop",
                status="fail",
                reason_codes=[REASON_SOP_VERSION_INVALID],
                details=f"SOP version '{explicit_v_str}' is not defined for SOP '{sop_id}'.",
                source_ids=source_ids,
                calculated_values={
                    "sop_id": str(sop_id),
                    "sop_version": explicit_v_str,
                    "run_date": run_dt.isoformat(),
                },
            )

        v_recs = all_version_records[explicit_v_str]
        v_eff = _parse_date(v_recs[0].get("effective_date"))
        v_sup = _parse_date(v_recs[0].get("superseded_date"))

        # Check if version is superseded on run_date
        if v_sup is not None and run_dt >= v_sup:
            return _format_rule_result(
                rule_name="sop",
                status="fail",
                reason_codes=[REASON_SOP_VERSION_INVALID],
                details=(
                    f"SOP version '{explicit_v_str}' was superseded on {v_sup.isoformat()}, "
                    f"prior to experiment run_date {run_dt.isoformat()}."
                ),
                source_ids=source_ids,
                calculated_values={
                    "sop_id": str(sop_id),
                    "sop_version": explicit_v_str,
                    "run_date": run_dt.isoformat(),
                    "superseded_date": v_sup.isoformat(),
                },
            )

        # Check if version is premature (not yet effective)
        if v_eff is not None and run_dt < v_eff:
            return _format_rule_result(
                rule_name="sop",
                status="fail",
                reason_codes=[REASON_SOP_VERSION_INVALID],
                details=(
                    f"SOP version '{explicit_v_str}' is premature: effective date {v_eff.isoformat()} "
                    f"is after experiment run_date {run_dt.isoformat()}."
                ),
                source_ids=source_ids,
                calculated_values={
                    "sop_id": str(sop_id),
                    "sop_version": explicit_v_str,
                    "run_date": run_dt.isoformat(),
                    "effective_date": v_eff.isoformat(),
                },
            )

        # Version is currently valid on run_date.
        # Now check if it's evaluated during an overlap window:
        if len(active_versions) > 1 and not allow_grandfathered:
            # Policy explicitly disallows parallel version evaluation
            return _format_rule_result(
                rule_name="sop",
                status="needs_review",
                reason_codes=[REASON_SOP_VERSION_CONFLICT],
                details=(
                    f"Multiple SOP versions {sorted(list(active_versions.keys()))} active on {run_dt.isoformat()} "
                    f"and laboratory transition policy disallows parallel version usage."
                ),
                source_ids=source_ids,
                calculated_values={
                    "sop_id": str(sop_id),
                    "sop_version": explicit_v_str,
                    "active_versions": sorted(list(active_versions.keys())),
                },
            )

        # Authorized explicit version evaluation
        return _format_rule_result(
            rule_name="sop",
            status="pass",
            reason_codes=[],
            details=(
                f"SOP version '{explicit_v_str}' is valid and authorized on {run_dt.isoformat()}."
            ),
            source_ids=source_ids,
            calculated_values={
                "sop_id": str(sop_id),
                "sop_version": explicit_v_str,
                "run_date": run_dt.isoformat(),
                "effective_date": v_eff.isoformat() if v_eff else None,
                "superseded_date": v_sup.isoformat() if v_sup else None,
            },
        )

    # Case B: Version is OMITTED (null or empty)
    if not has_explicit_version:
        if not active_versions:
            return _format_rule_result(
                rule_name="sop",
                status="needs_review",
                reason_codes=[REASON_MISSING_SOP_VERSION],
                details=f"No active SOP version exists on {run_dt.isoformat()} and version was omitted.",
                source_ids=source_ids,
                calculated_values={"sop_id": str(sop_id), "run_date": run_dt.isoformat()},
            )

        if len(active_versions) == 1:
            # Exactly one active version exists, but record omitted version field
            v_sole = list(active_versions.keys())[0]
            return _format_rule_result(
                rule_name="sop",
                status="needs_review",
                reason_codes=[REASON_MISSING_SOP_VERSION],
                details=(
                    f"SOP version omitted from experiment record (active version on "
                    f"{run_dt.isoformat()} is '{v_sole}')."
                ),
                source_ids=source_ids,
                calculated_values={
                    "sop_id": str(sop_id),
                    "run_date": run_dt.isoformat(),
                    "inferred_version": v_sole,
                },
            )

        # Multiple active versions exist on run_date and version was omitted.
        # Check if active versions have divergent specifications!
        first_v = list(active_versions.values())[0]
        specs_divergent = False
        for v_data in list(active_versions.values())[1:]:
            if (
                v_data["min"] != first_v["min"]
                or v_data["max"] != first_v["max"]
                or v_data["unit"] != first_v["unit"]
            ):
                specs_divergent = True
                break

        if specs_divergent:
            return _format_rule_result(
                rule_name="sop",
                status="needs_review",
                reason_codes=[REASON_SOP_VERSION_CONFLICT],
                details=(
                    f"Multiple SOP versions {sorted(list(active_versions.keys()))} active on {run_dt.isoformat()} "
                    f"with divergent acceptance criteria, and experiment omitted version reference."
                ),
                source_ids=source_ids,
                calculated_values={
                    "sop_id": str(sop_id),
                    "run_date": run_dt.isoformat(),
                    "active_versions": sorted(list(active_versions.keys())),
                },
            )
        else:
            return _format_rule_result(
                rule_name="sop",
                status="needs_review",
                reason_codes=[REASON_MISSING_SOP_VERSION],
                details=(
                    f"Multiple SOP versions {sorted(list(active_versions.keys()))} active on {run_dt.isoformat()} "
                    f"with identical criteria, but version reference was omitted."
                ),
                source_ids=source_ids,
                calculated_values={
                    "sop_id": str(sop_id),
                    "run_date": run_dt.isoformat(),
                    "active_versions": sorted(list(active_versions.keys())),
                },
            )

    return _format_rule_result(
        rule_name="sop",
        status="needs_review",
        reason_codes=[REASON_MISSING_SOP_EVIDENCE],
        details="Unhandled SOP validation branch.",
        source_ids=source_ids,
    )


# ------------------------------------------------------------------------------
# Rule 2: Instrument Calibration Validation
# ------------------------------------------------------------------------------

def validate_calibration_v2(
    experiment: Optional[Dict[str, Any]] = None,
    instruments: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None,
    *,
    instrument_id: Optional[str] = None,
    run_date: Optional[Union[str, date, datetime]] = None,
    calibration_date: Optional[Union[str, date]] = None,
    validity_days: Optional[int] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Validate instrument calibration status on the experiment run date.

    Conditions:
    - Calibration date <= run_date <= calibration_date + validity_days (inclusive).
    - Missing instrument_id -> needs_review, MISSING_INSTRUMENT_EVIDENCE.
    - Broken foreign key (not in catalog) -> needs_review, FOREIGN_KEY_NOT_FOUND.
    - Confirmed expired calibration -> fail, CALIBRATION_EXPIRED.
    """
    if experiment:
        instrument_id = instrument_id or experiment.get("instrument_id")
        run_date = run_date or experiment.get("run_date") or experiment.get("analyzed_at")

    source_ids: List[str] = [str(instrument_id)] if instrument_id else []

    if not instrument_id or str(instrument_id).strip() == "":
        return _format_rule_result(
            rule_name="calibration",
            status="needs_review",
            reason_codes=[REASON_MISSING_INSTRUMENT_EVIDENCE],
            details="Missing instrument identifier (instrument_id is null or empty).",
            source_ids=source_ids,
        )

    # Catalog lookup if catalog provided
    if instruments is not None:
        inst_list = instruments if isinstance(instruments, list) else (list(instruments.values()) if isinstance(instruments, dict) else [instruments])
        matching = [i for i in inst_list if str(i.get("instrument_id")) == str(instrument_id)]
        if not matching:
            return _format_rule_result(
                rule_name="calibration",
                status="needs_review",
                reason_codes=[REASON_FOREIGN_KEY_NOT_FOUND],
                details=f"Instrument '{instrument_id}' not found in instruments catalog.",
                source_ids=source_ids,
                calculated_values={"instrument_id": str(instrument_id)},
            )
        inst_rec = matching[0]
        if calibration_date is None:
            calibration_date = inst_rec.get("calibration_date")
        if validity_days is None:
            validity_days = inst_rec.get("validity_days")

    run_dt = _parse_date(run_date)
    cal_dt = _parse_date(calibration_date)

    if run_dt is None:
        return _format_rule_result(
            rule_name="calibration",
            status="needs_review",
            reason_codes=[REASON_MISSING_INSTRUMENT_EVIDENCE],
            details="Missing or unparseable experiment run_date.",
            source_ids=source_ids,
            calculated_values={"instrument_id": str(instrument_id)},
        )

    if cal_dt is None or validity_days is None:
        return _format_rule_result(
            rule_name="calibration",
            status="needs_review",
            reason_codes=[REASON_MISSING_INSTRUMENT_EVIDENCE],
            details=f"Missing calibration records for instrument '{instrument_id}'.",
            source_ids=source_ids,
            calculated_values={"instrument_id": str(instrument_id), "run_date": run_dt.isoformat()},
        )

    try:
        val_days = int(validity_days)
    except (ValueError, TypeError):
        return _format_rule_result(
            rule_name="calibration",
            status="needs_review",
            reason_codes=[REASON_MISSING_INSTRUMENT_EVIDENCE],
            details=f"Invalid validity_days: {validity_days}.",
            source_ids=source_ids,
        )

    # Calculate expiration date (inclusive)
    from datetime import timedelta
    expiration_dt = cal_dt + timedelta(days=val_days)

    if run_dt < cal_dt:
        return _format_rule_result(
            rule_name="calibration",
            status="fail",
            reason_codes=[REASON_CALIBRATION_NOT_YET_VALID],
            details=(
                f"Experiment run date ({run_dt.isoformat()}) precedes instrument "
                f"calibration date ({cal_dt.isoformat()})."
            ),
            source_ids=source_ids,
            calculated_values={
                "instrument_id": str(instrument_id),
                "calibration_date": cal_dt.isoformat(),
                "run_date": run_dt.isoformat(),
            },
        )

    if run_dt > expiration_dt:
        days_expired = (run_dt - expiration_dt).days
        return _format_rule_result(
            rule_name="calibration",
            status="fail",
            reason_codes=[REASON_CALIBRATION_EXPIRED],
            details=(
                f"Instrument calibration expired on {expiration_dt.isoformat()} (inclusive). "
                f"Run date {run_dt.isoformat()} is {days_expired} days overdue."
            ),
            source_ids=source_ids,
            calculated_values={
                "instrument_id": str(instrument_id),
                "calibration_date": cal_dt.isoformat(),
                "expiration_date": expiration_dt.isoformat(),
                "run_date": run_dt.isoformat(),
                "days_expired": days_expired,
            },
        )

    # Valid calibration (inclusive)
    days_remaining = (expiration_dt - run_dt).days
    return _format_rule_result(
        rule_name="calibration",
        status="pass",
        reason_codes=[],
        details=f"Instrument calibration is valid through {expiration_dt.isoformat()} (inclusive).",
        source_ids=source_ids,
        calculated_values={
            "instrument_id": str(instrument_id),
            "calibration_date": cal_dt.isoformat(),
            "validity_days": val_days,
            "expiration_date": expiration_dt.isoformat(),
            "run_date": run_dt.isoformat(),
            "days_remaining": days_remaining,
        },
    )


# ------------------------------------------------------------------------------
# Rule 3: Reagent Lot Validation
# ------------------------------------------------------------------------------

def validate_lot_v2(
    experiment: Optional[Dict[str, Any]] = None,
    lots: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None,
    *,
    lot_id: Optional[str] = None,
    run_date: Optional[Union[str, date, datetime]] = None,
    manufacture_date: Optional[Union[str, date]] = None,
    expiry_date: Optional[Union[str, date]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Validate reagent lot validity on the experiment run date.

    Conditions:
    - manufacture_date <= run_date <= expiry_date (inclusive).
    - Missing lot_id -> needs_review, MISSING_REAGENT_EVIDENCE.
    - Broken foreign key (not in catalog) -> needs_review, FOREIGN_KEY_NOT_FOUND.
    - Confirmed expired lot -> fail, LOT_EXPIRED.
    """
    if experiment:
        lot_id = lot_id or experiment.get("lot_id")
        run_date = run_date or experiment.get("run_date") or experiment.get("analyzed_at")

    source_ids: List[str] = [str(lot_id)] if lot_id else []

    if not lot_id or str(lot_id).strip() == "":
        return _format_rule_result(
            rule_name="lot",
            status="needs_review",
            reason_codes=[REASON_MISSING_REAGENT_EVIDENCE],
            details="Missing reagent lot identifier (lot_id is null or empty).",
            source_ids=source_ids,
        )

    # Catalog lookup if catalog provided
    if lots is not None:
        lot_list = lots if isinstance(lots, list) else (list(lots.values()) if isinstance(lots, dict) else [lots])
        matching = [l for l in lot_list if str(l.get("lot_id")) == str(lot_id)]
        if not matching:
            return _format_rule_result(
                rule_name="lot",
                status="needs_review",
                reason_codes=[REASON_FOREIGN_KEY_NOT_FOUND],
                details=f"Reagent lot '{lot_id}' not found in lots catalog.",
                source_ids=source_ids,
                calculated_values={"lot_id": str(lot_id)},
            )
        lot_rec = matching[0]
        if manufacture_date is None:
            manufacture_date = lot_rec.get("manufacture_date")
        if expiry_date is None:
            expiry_date = lot_rec.get("expiry_date")

    run_dt = _parse_date(run_date)
    mfg_dt = _parse_date(manufacture_date)
    exp_dt = _parse_date(expiry_date)

    if run_dt is None:
        return _format_rule_result(
            rule_name="lot",
            status="needs_review",
            reason_codes=[REASON_MISSING_REAGENT_EVIDENCE],
            details="Missing or unparseable experiment run_date.",
            source_ids=source_ids,
            calculated_values={"lot_id": str(lot_id)},
        )

    if mfg_dt is None or exp_dt is None:
        return _format_rule_result(
            rule_name="lot",
            status="needs_review",
            reason_codes=[REASON_MISSING_REAGENT_EVIDENCE],
            details=f"Missing manufacture or expiry date for reagent lot '{lot_id}'.",
            source_ids=source_ids,
            calculated_values={"lot_id": str(lot_id), "run_date": run_dt.isoformat()},
        )

    if run_dt < mfg_dt:
        return _format_rule_result(
            rule_name="lot",
            status="fail",
            reason_codes=[REASON_LOT_NOT_YET_VALID],
            details=(
                f"Experiment run date ({run_dt.isoformat()}) precedes reagent lot "
                f"manufacture date ({mfg_dt.isoformat()})."
            ),
            source_ids=source_ids,
            calculated_values={
                "lot_id": str(lot_id),
                "manufacture_date": mfg_dt.isoformat(),
                "run_date": run_dt.isoformat(),
            },
        )

    if run_dt > exp_dt:
        days_expired = (run_dt - exp_dt).days
        return _format_rule_result(
            rule_name="lot",
            status="fail",
            reason_codes=[REASON_LOT_EXPIRED],
            details=(
                f"Reagent lot expired on {exp_dt.isoformat()} (inclusive). "
                f"Run date {run_dt.isoformat()} is {days_expired} days overdue."
            ),
            source_ids=source_ids,
            calculated_values={
                "lot_id": str(lot_id),
                "manufacture_date": mfg_dt.isoformat(),
                "expiry_date": exp_dt.isoformat(),
                "run_date": run_dt.isoformat(),
                "days_expired": days_expired,
            },
        )

    # Valid lot
    days_to_expiry = (exp_dt - run_dt).days
    return _format_rule_result(
        rule_name="lot",
        status="pass",
        reason_codes=[],
        details=f"Reagent lot is valid through {exp_dt.isoformat()} (inclusive).",
        source_ids=source_ids,
        calculated_values={
            "lot_id": str(lot_id),
            "manufacture_date": mfg_dt.isoformat(),
            "expiry_date": exp_dt.isoformat(),
            "run_date": run_dt.isoformat(),
            "days_to_expiry": days_to_expiry,
        },
    )


# ------------------------------------------------------------------------------
# Rule 4: Holding-Time Validation
# ------------------------------------------------------------------------------

def validate_holding_time_v2(
    experiment: Optional[Dict[str, Any]] = None,
    samples: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None,
    *,
    sample_id: Optional[str] = None,
    collected_at: Optional[Any] = None,
    analyzed_at: Optional[Any] = None,
    max_holding_hours: Optional[Any] = None,
    site_id: Optional[str] = None,
    site_timezone: Optional[str] = None,
    site_catalog: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Validate sample holding time with strict ISO 8601 timezone normalization.

    Conditions:
    - Normalizes offset-aware timestamps to UTC.
    - Resolves naive timestamps using documented site timezone.
    - Confirmed analyzed_at < collected_at -> fail, INVALID_TIMESTAMP_ORDER.
    - Elapsed time <= max_holding_hours -> pass; otherwise fail, HOLDING_TIME_EXCEEDED.
    - Missing sample/timestamps -> needs_review, MISSING_SAMPLE_EVIDENCE.
    - Unresolvable naive timestamp or unparseable string -> needs_review, AMBIGUOUS_TIMEZONE.
    """
    if experiment:
        sample_id = sample_id or experiment.get("sample_id")
        collected_at = collected_at or experiment.get("collected_at")
        analyzed_at = analyzed_at or experiment.get("analyzed_at")
        site_id = site_id or experiment.get("site_id")
        site_timezone = site_timezone or experiment.get("site_timezone")

    source_ids: List[str] = [str(sample_id)] if sample_id else []

    if not sample_id or str(sample_id).strip() == "":
        return _format_rule_result(
            rule_name="holding_time",
            status="needs_review",
            reason_codes=[REASON_MISSING_SAMPLE_EVIDENCE],
            details="Missing sample identifier (sample_id is null or empty).",
            source_ids=source_ids,
        )

    # Catalog lookup if catalog provided
    if samples is not None:
        sample_list = samples if isinstance(samples, list) else (list(samples.values()) if isinstance(samples, dict) else [samples])
        matching = [s for s in sample_list if str(s.get("sample_id")) == str(sample_id)]
        if not matching:
            return _format_rule_result(
                rule_name="holding_time",
                status="needs_review",
                reason_codes=[REASON_FOREIGN_KEY_NOT_FOUND],
                details=f"Sample '{sample_id}' not found in samples catalog.",
                source_ids=source_ids,
                calculated_values={"sample_id": str(sample_id)},
            )
        sample_rec = matching[0]
        if collected_at is None:
            collected_at = sample_rec.get("collected_at")
        if max_holding_hours is None:
            max_holding_hours = sample_rec.get("max_holding_hours")
        if site_id is None:
            site_id = sample_rec.get("site_id")
        if site_timezone is None:
            site_timezone = sample_rec.get("site_timezone")

    if collected_at is None or str(collected_at).strip() == "":
        return _format_rule_result(
            rule_name="holding_time",
            status="needs_review",
            reason_codes=[REASON_MISSING_SAMPLE_EVIDENCE],
            details="Missing collection timestamp (collected_at is null or empty).",
            source_ids=source_ids,
            calculated_values={"sample_id": str(sample_id)},
        )

    if analyzed_at is None or str(analyzed_at).strip() == "":
        return _format_rule_result(
            rule_name="holding_time",
            status="needs_review",
            reason_codes=[REASON_MISSING_SAMPLE_EVIDENCE],
            details="Missing analysis timestamp (analyzed_at is null or empty).",
            source_ids=source_ids,
            calculated_values={"sample_id": str(sample_id)},
        )

    if max_holding_hours is None:
        return _format_rule_result(
            rule_name="holding_time",
            status="needs_review",
            reason_codes=[REASON_MISSING_SAMPLE_EVIDENCE],
            details="Missing maximum holding hours threshold (max_holding_hours).",
            source_ids=source_ids,
            calculated_values={"sample_id": str(sample_id)},
        )

    # Resolve timestamps to UTC
    col_utc, col_err = _resolve_datetime_v2(
        collected_at, site_id=site_id, site_timezone=site_timezone, site_catalog=site_catalog
    )
    if col_err:
        return _format_rule_result(
            rule_name="holding_time",
            status="needs_review",
            reason_codes=[col_err],
            details=f"Collection timestamp cannot be resolved unambiguously: '{collected_at}' ({col_err}).",
            source_ids=source_ids,
            calculated_values={"sample_id": str(sample_id), "site_id": site_id},
        )

    ana_utc, ana_err = _resolve_datetime_v2(
        analyzed_at, site_id=site_id, site_timezone=site_timezone, site_catalog=site_catalog
    )
    if ana_err:
        return _format_rule_result(
            rule_name="holding_time",
            status="needs_review",
            reason_codes=[ana_err],
            details=f"Analysis timestamp cannot be resolved unambiguously: '{analyzed_at}' ({ana_err}).",
            source_ids=source_ids,
            calculated_values={"sample_id": str(sample_id), "site_id": site_id},
        )

    assert col_utc is not None and ana_utc is not None

    try:
        max_h = Decimal(str(max_holding_hours))
        if max_h <= 0:
            return _format_rule_result(
                rule_name="holding_time",
                status="needs_review",
                reason_codes=[REASON_MISSING_SAMPLE_EVIDENCE],
                details=f"Invalid non-positive max_holding_hours: {max_holding_hours}.",
                source_ids=source_ids,
            )
    except (InvalidOperation, ValueError, TypeError):
        return _format_rule_result(
            rule_name="holding_time",
            status="needs_review",
            reason_codes=[REASON_MISSING_SAMPLE_EVIDENCE],
            details=f"Unparseable max_holding_hours: '{max_holding_hours}'.",
            source_ids=source_ids,
        )

    # Chronological Inversion Check (Confirmed failure)
    if ana_utc < col_utc:
        diff_sec = (ana_utc - col_utc).total_seconds()
        elapsed_h = Decimal(str(diff_sec)) / Decimal("3600")
        return _format_rule_result(
            rule_name="holding_time",
            status="fail",
            reason_codes=[REASON_INVALID_TIMESTAMP_ORDER],
            details=(
                f"Chronological inversion: analysis timestamp ({ana_utc.isoformat()}) "
                f"precedes collection timestamp ({col_utc.isoformat()}) by {abs(float(elapsed_h)):.2f} hours."
            ),
            source_ids=source_ids,
            calculated_values={
                "sample_id": str(sample_id),
                "collected_at_utc": col_utc.isoformat(),
                "analyzed_at_utc": ana_utc.isoformat(),
                "elapsed_hours": float(elapsed_h),
                "max_holding_hours": float(max_h),
            },
        )

    diff_seconds = Decimal(str((ana_utc - col_utc).total_seconds()))
    elapsed_hours = diff_seconds / Decimal("3600")
    margin_hours = max_h - elapsed_hours

    if elapsed_hours > max_h:
        excess = elapsed_hours - max_h
        return _format_rule_result(
            rule_name="holding_time",
            status="fail",
            reason_codes=[REASON_HOLDING_TIME_EXCEEDED],
            details=(
                f"Sample holding time exceeded: {float(elapsed_hours):.2f} hours > limit "
                f"{float(max_h):.2f} hours (excess {float(excess):.2f} hours)."
            ),
            source_ids=source_ids,
            calculated_values={
                "sample_id": str(sample_id),
                "collected_at_utc": col_utc.isoformat(),
                "analyzed_at_utc": ana_utc.isoformat(),
                "elapsed_hours": float(elapsed_hours),
                "max_holding_hours": float(max_h),
                "margin_hours": float(margin_hours),
            },
        )

    # Valid holding time
    return _format_rule_result(
        rule_name="holding_time",
        status="pass",
        reason_codes=[],
        details=(
            f"Sample analyzed within holding time: {float(elapsed_hours):.2f} hours <= limit "
            f"{float(max_h):.2f} hours."
        ),
        source_ids=source_ids,
        calculated_values={
            "sample_id": str(sample_id),
            "collected_at_utc": col_utc.isoformat(),
            "analyzed_at_utc": ana_utc.isoformat(),
            "elapsed_hours": float(elapsed_hours),
            "max_holding_hours": float(max_h),
            "margin_hours": float(margin_hours),
        },
    )


# ------------------------------------------------------------------------------
# Rule 5: Measurement Validation
# ------------------------------------------------------------------------------

def validate_measurement_v2(
    experiment: Optional[Dict[str, Any]] = None,
    sops: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None,
    *,
    measured_value: Optional[Any] = None,
    measurement_unit: Optional[Any] = None,
    measurement_uncertainty: Optional[Any] = None,
    sop_id: Optional[str] = None,
    sop_version: Optional[str] = None,
    clause_id: Optional[str] = None,
    sop_minimum: Optional[Any] = None,
    sop_maximum: Optional[Any] = None,
    canonical_unit: Optional[Any] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Validate measurement value and uncertainty interval against SOP specification limits.

    Reuses units_v2.compare_measurement_uncertainty_v2 with Decimal arithmetic.
    Retrieves version-specific specification limits matching both clause_id and sop_version.
    """
    if experiment:
        measured_value = (
            measured_value if measured_value is not None else experiment.get("measured_value")
        )
        measurement_unit = measurement_unit or experiment.get("measurement_unit")
        measurement_uncertainty = (
            measurement_uncertainty
            if measurement_uncertainty is not None
            else experiment.get("measurement_uncertainty")
        )
        sop_id = sop_id or experiment.get("sop_id")
        sop_version = (
            sop_version if sop_version is not None else experiment.get("sop_version")
        )
        clause_id = clause_id or experiment.get("clause_id")

    source_ids: List[str] = []
    if clause_id:
        source_ids.append(str(clause_id))
    elif sop_id:
        source_ids.append(str(sop_id))

    # Lookup clause in sops catalog if limits not provided directly
    if (sop_minimum is None or sop_maximum is None or canonical_unit is None) and sops is not None:
        sop_list = sops if isinstance(sops, list) else (list(sops.values()) if isinstance(sops, dict) else [sops])
        # Match both clause_id and sop_version (and sop_id if provided)
        matching = [c for c in sop_list if str(c.get("clause_id")) == str(clause_id)]
        if sop_id:
            matching = [c for c in matching if str(c.get("sop_id")) == str(sop_id)]
        if sop_version is not None and str(sop_version).strip() != "":
            v_match = [c for c in matching if str(c.get("sop_version", "")).strip() == str(sop_version).strip()]
            if v_match:
                matching = v_match

        if not matching:
            return _format_rule_result(
                rule_name="measurement",
                status="needs_review",
                reason_codes=[REASON_FOREIGN_KEY_NOT_FOUND],
                details=f"Clause '{clause_id}' (version '{sop_version}') not found in SOP catalog.",
                source_ids=source_ids,
                calculated_values={"clause_id": str(clause_id), "sop_version": str(sop_version)},
            )
        c_rec = matching[0]
        if sop_minimum is None:
            sop_minimum = c_rec.get("minimum_value")
        if sop_maximum is None:
            sop_maximum = c_rec.get("maximum_value")
        if canonical_unit is None:
            canonical_unit = c_rec.get("canonical_unit")

    # Evaluate via units_v2 engine
    res = units_v2.compare_measurement_uncertainty_v2(
        measured_value=measured_value,
        measurement_unit=measurement_unit,
        measurement_uncertainty=measurement_uncertainty,
        sop_minimum=sop_minimum,
        sop_maximum=sop_maximum,
        canonical_unit=canonical_unit,
    )

    reason_codes = [res["reason_code"]] if res["reason_code"] else []

    calc_vals = {
        "original_value": res["original_value"],
        "original_unit": res["original_unit"],
        "normalized_value": res["normalized_value"],
        "canonical_unit": res["canonical_unit"],
        "normalized_uncertainty": res["normalized_uncertainty"],
        "lower_bound": res["lower_bound"],
        "upper_bound": res["upper_bound"],
        "sop_minimum": res["sop_minimum"],
        "sop_maximum": res["sop_maximum"],
    }

    return _format_rule_result(
        rule_name="measurement",
        status=res["status"],
        reason_codes=reason_codes,
        details=res["details"],
        source_ids=source_ids,
        calculated_values=calc_vals,
    )

