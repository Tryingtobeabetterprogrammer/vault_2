"""VAULT V2 Synthetic Laboratory Data Generator (Calibrated Engine).

Generates realistic, deterministic laboratory records for V2:
- 43 SOP clauses with versioning and controlled overlap windows.
- 30 instruments with diverse calibration windows (guaranteeing valid active coverage throughout 2025).
- 50 reagent lots with expiration timelines (guaranteeing valid active stock throughout 2025).
- 200 samples with multi-site timezone metadata (ISO 8601 offsets & IANA site timezones).
- 1,200 experiments covering 14 balanced scenario families.

Remediation Highlights:
- Active SOP version dynamically matched to experiment run date (eff <= run_date < sup).
- Analysis timestamps scheduled relative to normalized collection UTC, preventing timezone inversions.
- Precision preserved during unit conversions (no rounding underflow to 0.0 for small g/L values).
- Missing evidence properly represented as None.
- Specialized units (CFU/g, particles/mL, EU/mL) aligned with units_v2 dimensions.
- Guarded uncertainty margins for valid experiments ensuring interval stays inside limits.
- Deterministic reproducibility using random seed 42.
"""

from __future__ import annotations

import csv
import json
import os
import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_V2_DIR = os.path.join(REPO_ROOT, "data", "raw_v2")

EXPERIMENT_FIELDNAMES_V2 = [
    "experiment_id",
    "run_date",
    "sop_id",
    "sop_version",
    "clause_id",
    "instrument_id",
    "lot_id",
    "sample_id",
    "site_id",
    "site_timezone",
    "parameter",
    "measured_value",
    "measurement_unit",
    "measurement_uncertainty",
    "collected_at",
    "analyzed_at",
    "scenario_family",
]

PARAMETER_INSTRUMENT_MAP = {
    "Total Dissolved Solids": ["Conductivity Meter", "TDS Meter"],
    "Electrical Conductivity": ["Conductivity Meter"],
    "pH Value": ["pH Meter"],
    "Turbidity Level": ["Turbidimeter"],
    "Dissolved Lead": ["AAS", "ICP-MS"],
    "Dissolved Cadmium": ["AAS", "ICP-MS"],
    "Dissolved Arsenic": ["ICP-MS"],
    "Dissolved Chromium": ["AAS", "ICP-MS"],
    "Dissolved Copper": ["AAS", "ICP-MS"],
    "Dissolved Zinc": ["AAS", "ICP-MS"],
    "Assay Purity": ["HPLC"],
    "Related Substances": ["HPLC"],
    "Chloride Concentration": ["Ion Chromatograph", "Titrator"],
    "Sulfate Concentration": ["Ion Chromatograph", "Spectrophotometer"],
    "Nitrate Nitrogen": ["Spectrophotometer", "Ion Chromatograph"],
    "Fluoride Content": ["Ion Chromatograph", "ISE Meter"],
    "Residual Solvents": ["GC-FID", "GC-MS"],
    "Ethanol Content": ["GC-FID"],
    "Total Aerobic Microbial Count": ["Incubator / Colony Counter"],
    "Yeast and Mold Count": ["Incubator / Colony Counter"],
    "Endotoxin Concentration": ["Microplate Reader / LAL"],
    "Particulate Matter (>= 10 um)": ["Light Obscuration Particle Counter"],
    "Particulate Matter (>= 25 um)": ["Light Obscuration Particle Counter"],
    "Dissolution Rate (Q at 45 min)": ["Dissolution Tester"],
    "Heavy Metals (General)": ["ICP-MS", "AAS"],
    "Moisture Content": ["Karl Fischer Titrator", "Loss on Drying Oven"],
}

PARAMETER_REAGENT_KEYWORDS = {
    "Assay Purity": ["Mobile Phase", "Acetonitrile", "Buffer"],
    "Related Substances": ["Mobile Phase", "Methanol", "Phosphoric Acid"],
    "pH Value": ["Buffer 4.01", "Buffer 7.00", "Buffer 10.01"],
    "Turbidity Level": ["Formazin Standard", "AMCO Clear"],
    "Dissolved Lead": ["Lead Calibration Standard", "Nitric Acid Matrix"],
    "Dissolved Cadmium": ["Cadmium Calibration Standard", "Nitric Acid Matrix"],
    "Dissolved Arsenic": ["Arsenic Calibration Standard", "Matrix Modifier"],
    "Dissolved Chromium": ["Chromium Calibration Standard", "Nitric Acid Matrix"],
    "Dissolved Copper": ["Copper Calibration Standard", "Nitric Acid Matrix"],
    "Dissolved Zinc": ["Zinc Calibration Standard", "Nitric Acid Matrix"],
    "Chloride Concentration": ["Silver Nitrate Titrant", "Chloride Standard"],
    "Sulfate Concentration": ["Barium Chloride Reagent", "Sulfate Standard"],
    "Nitrate Nitrogen": ["Nitrate Standard", "Cadmium Reduction Reagent"],
    "Fluoride Content": ["TISAB Buffer", "Fluoride Standard"],
    "Endotoxin Concentration": ["LAL Reagent", "Control Standard Endotoxin"],
    "Moisture Content": ["Karl Fischer Titrant", "Hydranal Composite"],
    "Total Dissolved Solids": ["NaCl Reference Solution", "TDS Calibration Standard"],
    "Electrical Conductivity": ["KCl Conductivity Standard 1413 uS/cm", "KCl Standard 12.88 mS/cm"],
    "Total Aerobic Microbial Count": ["Agar Growth Medium", "Sterile Diluent"],
    "Yeast and Mold Count": ["Sabouraud Dextrose Agar", "Sterile Diluent"],
    "Particulate Matter (>= 10 um)": ["Particle Count Reference Suspension"],
    "Particulate Matter (>= 25 um)": ["Particle Count Reference Suspension"],
    "Dissolution Rate (Q at 45 min)": ["Dissolution Medium Degassed", "USP Reference Standard"],
    "Ethanol Content": ["Ethanol Internal Standard Solution", "USP Reference Standard"],
    "Heavy Metals (General)": ["Lead Calibration Standard", "Nitric Acid Matrix"],
}

_SENTINEL = object()


def _iso_date(d: date) -> str:
    return d.isoformat()


def _iso_dt(dt: datetime) -> str:
    return dt.isoformat()


def generate_sops_v2() -> List[Dict[str, Any]]:
    """Generate 43 SOP clause records across 8 SOPs with version transitions."""
    clauses: List[Dict[str, Any]] = []

    # SOP-001: General Water Quality
    # v1.0 (2024-01-01 to 2025-04-30), v2.0 (2025-05-01 onwards)
    sop1_specs = [
        ("CLAUSE-001", "pH Value", 6.5, 8.5, 6.8, 8.2, "pH", 2),
        ("CLAUSE-002", "Electrical Conductivity", 50.0, 500.0, 50.0, 450.0, "µS/cm", 1),
        ("CLAUSE-003", "Total Dissolved Solids", 50.0, 1000.0, 50.0, 800.0, "mg/L", 1),
        ("CLAUSE-004", "Turbidity Level", 0.1, 5.0, 0.1, 3.0, "NTU", 2),
        ("CLAUSE-005", "Chloride Concentration", 1.0, 250.0, 1.0, 200.0, "mg/L", 1),
        ("CLAUSE-006", "Sulfate Concentration", 1.0, 250.0, 1.0, 200.0, "mg/L", 1),
    ]
    for cid, param, v1_min, v1_max, v2_min, v2_max, unit, prec in sop1_specs:
        clauses.append({
            "sop_id": "SOP-001", "clause_id": cid, "sop_version": "1.0",
            "effective_date": "2024-01-01", "superseded_date": "2025-04-30",
            "parameter": param, "minimum_value": v1_min, "maximum_value": v1_max,
            "canonical_unit": unit, "measurement_precision": prec,
        })
        clauses.append({
            "sop_id": "SOP-001", "clause_id": cid, "sop_version": "2.0",
            "effective_date": "2025-05-01", "superseded_date": None,
            "parameter": param, "minimum_value": v2_min, "maximum_value": v2_max,
            "canonical_unit": unit, "measurement_precision": prec,
        })

    # SOP-002: HPLC Assay & Impurities
    # v1.0 (2024-02-01 to 2025-06-30), v2.0 (2025-07-01 onwards)
    sop2_specs = [
        ("CLAUSE-007", "Assay Purity", 98.0, 102.0, 98.5, 101.5, "%", 2),
        ("CLAUSE-008", "Related Substances", 0.0, 0.50, 0.0, 0.30, "%", 3),
        ("CLAUSE-009", "Residual Solvents", 0.0, 500.0, 0.0, 400.0, "mg/L", 1),
    ]
    for cid, param, v1_min, v1_max, v2_min, v2_max, unit, prec in sop2_specs:
        clauses.append({
            "sop_id": "SOP-002", "clause_id": cid, "sop_version": "1.0",
            "effective_date": "2024-02-01", "superseded_date": "2025-06-30",
            "parameter": param, "minimum_value": v1_min, "maximum_value": v1_max,
            "canonical_unit": unit, "measurement_precision": prec,
        })
        clauses.append({
            "sop_id": "SOP-002", "clause_id": cid, "sop_version": "2.0",
            "effective_date": "2025-07-01", "superseded_date": None,
            "parameter": param, "minimum_value": v2_min, "maximum_value": v2_max,
            "canonical_unit": unit, "measurement_precision": prec,
        })

    # SOP-003: Dissolved Heavy Metals (OVERLAPPING WINDOW: 2025-05-15 to 2025-05-31)
    # Both v1.0 and v2.0 active with divergent limits during May 15-31, 2025!
    sop3_specs = [
        ("CLAUSE-013", "Dissolved Lead", 0.001, 0.050, 0.001, 0.030, "mg/L", 4),
        ("CLAUSE-014", "Dissolved Cadmium", 0.0005, 0.0100, 0.0005, 0.0050, "mg/L", 4),
        ("CLAUSE-015", "Dissolved Arsenic", 0.001, 0.020, 0.001, 0.010, "mg/L", 4),
        ("CLAUSE-016", "Dissolved Chromium", 0.005, 0.100, 0.005, 0.050, "mg/L", 3),
        ("CLAUSE-017", "Dissolved Copper", 0.01, 1.50, 0.01, 1.00, "mg/L", 2),
        ("CLAUSE-018", "Dissolved Zinc", 0.01, 5.00, 0.01, 3.00, "mg/L", 2),
    ]
    for cid, param, v1_min, v1_max, v2_min, v2_max, unit, prec in sop3_specs:
        clauses.append({
            "sop_id": "SOP-003", "clause_id": cid, "sop_version": "1.0",
            "effective_date": "2024-01-01", "superseded_date": "2025-05-31",
            "parameter": param, "minimum_value": v1_min, "maximum_value": v1_max,
            "canonical_unit": unit, "measurement_precision": prec,
        })
        clauses.append({
            "sop_id": "SOP-003", "clause_id": cid, "sop_version": "2.0",
            "effective_date": "2025-05-15", "superseded_date": None,
            "parameter": param, "minimum_value": v2_min, "maximum_value": v2_max,
            "canonical_unit": unit, "measurement_precision": prec,
        })

    # SOP-004: Nutrients & Anions (v1.0 2024-01-01 to 2025-03-31, v2.0 2025-04-01 onwards)
    sop4_specs = [
        ("CLAUSE-019", "Nitrate Nitrogen", 0.1, 50.0, 0.1, 40.0, "mg/L", 2),
        ("CLAUSE-020", "Fluoride Content", 0.1, 2.0, 0.1, 1.5, "mg/L", 2),
    ]
    for cid, param, v1_min, v1_max, v2_min, v2_max, unit, prec in sop4_specs:
        clauses.append({
            "sop_id": "SOP-004", "clause_id": cid, "sop_version": "1.0",
            "effective_date": "2024-01-01", "superseded_date": "2025-03-31",
            "parameter": param, "minimum_value": v1_min, "maximum_value": v1_max,
            "canonical_unit": unit, "measurement_precision": prec,
        })
        clauses.append({
            "sop_id": "SOP-004", "clause_id": cid, "sop_version": "2.0",
            "effective_date": "2025-04-01", "superseded_date": None,
            "parameter": param, "minimum_value": v2_min, "maximum_value": v2_max,
            "canonical_unit": unit, "measurement_precision": prec,
        })

    # SOP-005 to SOP-008: Single version (v1.0 from 2024-01-01, open-ended)
    single_specs = [
        ("SOP-005", "CLAUSE-025", "Ethanol Content", 0.0, 100.0, "%", 2),
        ("SOP-005", "CLAUSE-026", "Total Aerobic Microbial Count", 0.0, 500.0, "CFU/g", 0),
        ("SOP-005", "CLAUSE-027", "Yeast and Mold Count", 0.0, 50.0, "CFU/g", 0),
        ("SOP-006", "CLAUSE-028", "Endotoxin Concentration", 0.005, 0.500, "EU/mL", 3),
        ("SOP-006", "CLAUSE-029", "Particulate Matter (>= 10 um)", 0.0, 600.0, "particles/mL", 0),
        ("SOP-006", "CLAUSE-030", "Particulate Matter (>= 25 um)", 0.0, 60.0, "particles/mL", 0),
        ("SOP-007", "CLAUSE-031", "Dissolution Rate (Q at 45 min)", 70.0, 100.0, "%", 1),
        ("SOP-007", "CLAUSE-032", "Moisture Content", 0.0, 5.0, "%", 2),
        ("SOP-008", "CLAUSE-033", "Heavy Metals (General)", 0.001, 20.0, "mg/L", 3),
    ]
    for sop_id, cid, param, v_min, v_max, unit, prec in single_specs:
        clauses.append({
            "sop_id": sop_id, "clause_id": cid, "sop_version": "1.0",
            "effective_date": "2024-01-01", "superseded_date": None,
            "parameter": param, "minimum_value": v_min, "maximum_value": v_max,
            "canonical_unit": unit, "measurement_precision": prec,
        })

    return clauses


def generate_instruments_v2(rng: random.Random) -> List[Dict[str, Any]]:
    """Generate 30 instruments: 10 expired early, 20 valid throughout 2025 and 2026."""
    instruments: List[Dict[str, Any]] = []
    types = [
        "HPLC", "pH Meter", "Conductivity Meter", "Turbidimeter", "AAS", "ICP-MS",
        "Ion Chromatograph", "Spectrophotometer", "GC-FID", "Dissolution Tester",
        "Karl Fischer Titrator", "ISE Meter", "Microplate Reader / LAL",
        "Incubator / Colony Counter", "Light Obscuration Particle Counter",
    ]

    for i in range(1, 31):
        inst_id = f"INST-{i:03d}"
        itype = types[(i - 1) % len(types)]

        if i <= 10:
            # Expired early: calibrated late 2024 with 90-day validity, expired by early 2025
            cal_date = date(2024, 10, 1) + timedelta(days=(i * 7) % 45)
            val_days = 90
            status = "EXPIRED"
        else:
            # Valid throughout 2025 and into 2026: calibrated early Jan 2025 with 365 or 730 days validity
            cal_date = date(2025, 1, 2)
            val_days = 500 + (i * 15) % 100  # valid through mid 2026
            status = "CALIBRATED"

        instruments.append({
            "instrument_id": inst_id,
            "instrument_type": itype,
            "calibration_date": _iso_date(cal_date),
            "validity_days": val_days,
            "calibration_status": status,
        })

    return instruments


def generate_lots_v2(rng: random.Random) -> List[Dict[str, Any]]:
    """Generate 50 reagent lots with expiration timelines (ensuring ample valid inventory throughout 2025)."""
    lots: List[Dict[str, Any]] = []
    reagents = [
        "HPLC Mobile Phase Acetonitrile", "HPLC Mobile Phase Methanol",
        "pH Buffer 4.01", "pH Buffer 7.00", "pH Buffer 10.01",
        "Lead Calibration Standard", "Cadmium Calibration Standard",
        "Arsenic Calibration Standard", "Chromium Calibration Standard",
        "Copper Calibration Standard", "Zinc Calibration Standard",
        "Conductivity Standard 1413 uS/cm", "Silver Nitrate Titrant 0.1M",
        "Karl Fischer Titrant 5mg/mL", "Nitrate Standard 1000 mg/L",
        "Fluoride Standard 100 mg/L", "Formazin Turbidity Standard",
        "Agar Growth Medium", "Sterile Diluent", "LAL Reagent",
        "Particle Count Reference Suspension", "Dissolution Medium Degassed",
        "Ethanol Internal Standard Solution",
    ]

    for i in range(1, 51):
        lot_id = f"LOT-{i:03d}"
        rname = reagents[(i - 1) % len(reagents)]

        if i <= 15:
            # Expired early: mfg late 2023 / early 2024, expired by March/April 2025
            mfg_date = date(2024, 1, 1) + timedelta(days=(i * 6) % 30)
            exp_date = mfg_date + timedelta(days=240 + (i * 5) % 60)
        else:
            # Valid throughout all of 2025 and into 2026
            mfg_date = date(2025, 1, 2)
            exp_date = date(2026, 6, 1) + timedelta(days=(i * 10) % 90)

        lots.append({
            "lot_id": lot_id,
            "reagent_name": rname,
            "manufacture_date": _iso_date(mfg_date),
            "expiry_date": _iso_date(exp_date),
        })

    return lots


def generate_samples_v2(rng: random.Random) -> List[Dict[str, Any]]:
    """Generate 200 samples across 4 facilities with multi-site timezone metadata."""
    samples: List[Dict[str, Any]] = []
    sites = [
        ("SITE-BOS", "America/New_York", "-04:00"),
        ("SITE-BER", "Europe/Berlin", "+02:00"),
        ("SITE-SFO", "America/Los_Angeles", "-07:00"),
        ("SITE-LON", "Europe/London", "+01:00"),
    ]

    start_date = date(2025, 1, 15)
    for i in range(1, 201):
        sid = f"SMP-{i:04d}"
        site_id, site_tz, site_offset = sites[(i - 1) % len(sites)]
        day_offset = (i - 1) * 1.35  # spread Jan - Oct 2025
        col_date = start_date + timedelta(days=int(day_offset))
        col_time = datetime(col_date.year, col_date.month, col_date.day, 8, 30)

        fmt_choice = i % 10
        if fmt_choice < 5:
            col_iso = col_time.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
        elif fmt_choice < 8:
            col_iso = f"{col_time.isoformat()}{site_offset}"
        else:
            col_iso = col_time.isoformat()

        holding_hours = [24.0, 48.0, 72.0][(i - 1) % 3]

        samples.append({
            "sample_id": sid,
            "sample_matrix": ["Purified Water", "Surface Water", "Active Pharmaceutical Ingredient", "Wastewater Effluent"][(i - 1) % 4],
            "collected_at": col_iso,
            "max_holding_hours": holding_hours,
            "site_id": site_id,
            "site_timezone": site_tz,
        })

    return samples


def generate_experiments_v2(
    sops: List[Dict[str, Any]],
    instruments: List[Dict[str, Any]],
    lots: List[Dict[str, Any]],
    samples: List[Dict[str, Any]],
    rng: random.Random,
    total_experiments: int = 1200,
) -> List[Dict[str, Any]]:
    """Generate 1,200 experiments covering all 14 balanced scenario families."""
    experiments: List[Dict[str, Any]] = []

    # Helpers
    def find_inst_for_param(param: str, req_calibrated_on: Optional[date] = None) -> Dict[str, Any]:
        types = PARAMETER_INSTRUMENT_MAP.get(param, ["Conductivity Meter", "HPLC"])
        cands = [i for i in instruments if i["instrument_type"] in types]
        if req_calibrated_on:
            valid = []
            for c in cands:
                cd = date.fromisoformat(c["calibration_date"])
                ed = cd + timedelta(days=c["validity_days"])
                if cd <= req_calibrated_on <= ed:
                    valid.append(c)
            if valid:
                return valid[0]
            # Search all calibrated instruments in the catalog if none in cands
            all_cal = []
            for c in instruments:
                cd = date.fromisoformat(c["calibration_date"])
                ed = cd + timedelta(days=c["validity_days"])
                if cd <= req_calibrated_on <= ed:
                    all_cal.append(c)
            if all_cal:
                return all_cal[0]
        return cands[0] if cands else instruments[0]

    def find_lot_for_param(param: str, req_valid_on: Optional[date] = None) -> Dict[str, Any]:
        kws = PARAMETER_REAGENT_KEYWORDS.get(param, ["Standard", "Buffer"])
        cands = [l for l in lots if any(kw.lower() in l["reagent_name"].lower() for kw in kws)]
        if req_valid_on:
            valid = []
            for c in cands:
                md = date.fromisoformat(c["manufacture_date"])
                ed = date.fromisoformat(c["expiry_date"])
                if md <= req_valid_on <= ed:
                    valid.append(c)
            if valid:
                return valid[0]
            # Search all valid lots in catalog if none in cands
            all_val = []
            for c in lots:
                md = date.fromisoformat(c["manufacture_date"])
                ed = date.fromisoformat(c["expiry_date"])
                if md <= req_valid_on <= ed:
                    all_val.append(c)
            if all_val:
                return all_val[0]
        return cands[0] if cands else lots[0]

    def find_active_clause(run_d: date, index: int, filter_canonical_unit: Optional[str] = None) -> Dict[str, Any]:
        """Find an SOP clause that is ACTUALLY active and valid on run_d."""
        active = []
        for c in sops:
            eff = date.fromisoformat(c["effective_date"])
            sup = date.fromisoformat(c["superseded_date"]) if c.get("superseded_date") else None
            if eff <= run_d and (sup is None or run_d < sup):
                if filter_canonical_unit is None or c["canonical_unit"] == filter_canonical_unit:
                    active.append(c)
        if not active:
            return sops[index % len(sops)]
        return active[index % len(active)]

    overlap_sop3_clauses = [
        c for c in sops if c["sop_id"] == "SOP-003" and c["sop_version"] == "1.0"
    ]
    expired_insts = [inst for inst in instruments if inst["calibration_status"] == "EXPIRED"]
    expired_lots = [l for l in lots if date.fromisoformat(l["expiry_date"]) < date(2025, 5, 1)]

    exp_counter = 1

    def make_exp_record(
        scenario_fam: str,
        clause: Dict[str, Any],
        sample: Dict[str, Any],
        run_d: date,
        col_iso: str,
        ana_iso: str,
        inst_id: Optional[str],
        lot_id: Optional[str],
        val: Any,
        unit: Any,
        unc: Any,
        sop_v: Any = _SENTINEL,
        sop_override_id: Any = _SENTINEL,
        clause_override_id: Any = _SENTINEL,
        sample_override_id: Any = _SENTINEL,
        precision_override: Optional[int] = None,
    ) -> Dict[str, Any]:
        nonlocal exp_counter
        eid = f"EXP-{exp_counter:04d}"
        exp_counter += 1

        final_sop_id = sop_override_id if sop_override_id is not _SENTINEL else clause["sop_id"]
        final_clause_id = clause_override_id if clause_override_id is not _SENTINEL else clause["clause_id"]
        final_sample_id = sample_override_id if sample_override_id is not _SENTINEL else sample["sample_id"]
        final_v = sop_v if sop_v is not _SENTINEL else clause["sop_version"]

        prec = precision_override if precision_override is not None else clause["measurement_precision"]
        m_val = round(float(val), prec) if isinstance(val, (int, float, Decimal)) else val
        m_unc = round(float(unc), prec) if isinstance(unc, (int, float, Decimal)) else unc

        return {
            "experiment_id": eid,
            "run_date": _iso_date(run_d),
            "sop_id": final_sop_id,
            "sop_version": final_v,
            "clause_id": final_clause_id,
            "instrument_id": inst_id,
            "lot_id": lot_id,
            "sample_id": final_sample_id,
            "site_id": sample.get("site_id", "SITE-BOS"),
            "site_timezone": sample.get("site_timezone", "America/New_York"),
            "parameter": clause["parameter"],
            "measured_value": m_val,
            "measurement_unit": unit,
            "measurement_uncertainty": m_unc,
            "collected_at": col_iso,
            "analyzed_at": ana_iso,
            "scenario_family": scenario_fam,
        }

    def get_col_utc(s: Dict[str, Any]) -> datetime:
        col_str = s["collected_at"]
        if col_str.endswith("Z"):
            return datetime.fromisoformat(col_str[:-1] + "+00:00")
        try:
            dt = datetime.fromisoformat(col_str)
            if dt.tzinfo is not None:
                return dt.astimezone(timezone.utc)
            import zoneinfo
            tz = zoneinfo.ZoneInfo(s.get("site_timezone", "America/New_York"))
            return dt.replace(tzinfo=tz).astimezone(timezone.utc)
        except Exception:
            return datetime(2025, 3, 1, 8, 30, tzinfo=timezone.utc)

    # --------------------------------------------------------------------------
    # 1. Nominal Valid (520 experiments)
    # --------------------------------------------------------------------------
    for i in range(520):
        s = samples[i % len(samples)]
        col_utc = get_col_utc(s)
        # Schedule analysis 4 to 12 hours after collection in UTC
        hold_h = min(s["max_holding_hours"] - 2.0, 4.0 + (i % 8))
        ana_utc = col_utc + timedelta(hours=hold_h)
        run_d = ana_utc.date()

        # Dynamically find clause active on run_d!
        c = find_active_clause(run_d, i)

        inst = find_inst_for_param(c["parameter"], req_calibrated_on=run_d)
        lot = find_lot_for_param(c["parameter"], req_valid_on=run_d)

        s_min = float(c["minimum_value"])
        s_max = float(c["maximum_value"])
        span = s_max - s_min
        val = s_min + span * rng.uniform(0.35, 0.65)
        # Guarded uncertainty margin: stays strictly inside [s_min, s_max]
        unc = min((val - s_min) / 4.0, (s_max - val) / 4.0, val * 0.015, 0.05)
        unc = max(unc, 0.001)

        ana_iso = ana_utc.isoformat().replace("+00:00", "Z")

        experiments.append(make_exp_record(
            scenario_fam="Nominal valid",
            clause=c,
            sample=s,
            run_d=run_d,
            col_iso=s["collected_at"],
            ana_iso=ana_iso,
            inst_id=inst["instrument_id"],
            lot_id=lot["lot_id"],
            val=val,
            unit=c["canonical_unit"],
            unc=unc,
        ))

    # --------------------------------------------------------------------------
    # 2. Unit Conversion Valid (120 experiments)
    # --------------------------------------------------------------------------
    for i in range(120):
        s = samples[(i + 15) % len(samples)]
        col_utc = get_col_utc(s)
        ana_utc = col_utc + timedelta(hours=6.0)
        run_d = ana_utc.date()

        # Find active concentration clause on run_d
        c = find_active_clause(run_d, i, filter_canonical_unit="mg/L")

        inst = find_inst_for_param(c["parameter"], req_calibrated_on=run_d)
        lot = find_lot_for_param(c["parameter"], req_valid_on=run_d)

        s_min = float(c["minimum_value"])
        s_max = float(c["maximum_value"])
        span = s_max - s_min
        nom_val = s_min + span * rng.uniform(0.35, 0.65)
        nom_unc = min((nom_val - s_min) / 4.0, (s_max - nom_val) / 4.0, 0.02)

        alt_choice = i % 4
        prec_override = None
        if alt_choice == 0:
            # g/L: divide by 1000, preserve decimal precision!
            val = nom_val / 1000.0
            unc = nom_unc / 1000.0
            unit = "g/L"
            prec_override = max(c["measurement_precision"] + 4, 6)
        elif alt_choice == 1:
            val = nom_val * 1000.0
            unc = nom_unc * 1000.0
            unit = "\u00b5g/L"
        elif alt_choice == 2:
            val = nom_val * 1000.0
            unc = nom_unc * 1000.0
            unit = "\u03bcg/L"
        else:
            val = nom_val * 1000.0
            unc = nom_unc * 1000.0
            unit = "ug/L"

        ana_iso = ana_utc.isoformat().replace("+00:00", "Z")

        experiments.append(make_exp_record(
            scenario_fam="Unit conversion valid",
            clause=c,
            sample=s,
            run_d=run_d,
            col_iso=s["collected_at"],
            ana_iso=ana_iso,
            inst_id=inst["instrument_id"],
            lot_id=lot["lot_id"],
            val=val,
            unit=unit,
            unc=unc,
            precision_override=prec_override,
        ))

    # --------------------------------------------------------------------------
    # 3. Timezone Valid (80 experiments)
    # --------------------------------------------------------------------------
    for i in range(80):
        col_d = date(2025, 4, 1) + timedelta(days=i)
        offset_str = ["+02:00", "-04:00", "-07:00", "+01:00"][i % 4]
        col_iso = f"{col_d.isoformat()}T09:00:00{offset_str}"
        # Parse collection directly to UTC
        col_dt_utc = datetime.fromisoformat(col_iso).astimezone(timezone.utc)
        # Schedule analysis strictly 4 hours later in UTC!
        ana_dt_utc = col_dt_utc + timedelta(hours=4.0)
        ana_iso = ana_dt_utc.isoformat().replace("+00:00", "Z")
        run_d = ana_dt_utc.date()

        s = samples[(i + 50) % len(samples)]
        c = find_active_clause(run_d, i + 30)

        inst = find_inst_for_param(c["parameter"], req_calibrated_on=run_d)
        lot = find_lot_for_param(c["parameter"], req_valid_on=run_d)

        s_min = float(c["minimum_value"])
        s_max = float(c["maximum_value"])
        val = s_min + (s_max - s_min) * 0.5
        unc = min((val - s_min) / 4.0, 0.05)

        experiments.append(make_exp_record(
            scenario_fam="Timezone valid",
            clause=c,
            sample=s,
            run_d=run_d,
            col_iso=col_iso,
            ana_iso=ana_iso,
            inst_id=inst["instrument_id"],
            lot_id=lot["lot_id"],
            val=val,
            unit=c["canonical_unit"],
            unc=unc,
        ))

    # --------------------------------------------------------------------------
    # 4. Calibration Expiry Invalid (45 experiments)
    # --------------------------------------------------------------------------
    for i in range(45):
        s = samples[(i + 20) % len(samples)]
        inst = expired_insts[i % len(expired_insts)]
        cal_d = date.fromisoformat(inst["calibration_date"])
        exp_d = cal_d + timedelta(days=inst["validity_days"])
        run_d = exp_d + timedelta(days=15 + (i % 30))
        c = find_active_clause(run_d, i + 5)

        col_dt = datetime(run_d.year, run_d.month, run_d.day, 6, 0, tzinfo=timezone.utc)
        ana_dt = datetime(run_d.year, run_d.month, run_d.day, 10, 0, tzinfo=timezone.utc)

        lot = find_lot_for_param(c["parameter"], req_valid_on=run_d)
        s_min = float(c["minimum_value"])
        s_max = float(c["maximum_value"])
        val = s_min + (s_max - s_min) * 0.5
        unc = min((val - s_min) / 4.0, 0.05)

        experiments.append(make_exp_record(
            scenario_fam="Calibration expiry invalid",
            clause=c,
            sample=s,
            run_d=run_d,
            col_iso=_iso_dt(col_dt),
            ana_iso=_iso_dt(ana_dt),
            inst_id=inst["instrument_id"],
            lot_id=lot["lot_id"],
            val=val,
            unit=c["canonical_unit"],
            unc=unc,
        ))

    # --------------------------------------------------------------------------
    # 5. Lot Expiry Invalid (45 experiments)
    # --------------------------------------------------------------------------
    for i in range(45):
        s = samples[(i + 40) % len(samples)]
        lot = expired_lots[i % len(expired_lots)]
        lot_exp_d = date.fromisoformat(lot["expiry_date"])
        run_d = lot_exp_d + timedelta(days=10 + (i % 25))
        c = find_active_clause(run_d, i + 10)

        col_dt = datetime(run_d.year, run_d.month, run_d.day, 7, 0, tzinfo=timezone.utc)
        ana_dt = datetime(run_d.year, run_d.month, run_d.day, 11, 0, tzinfo=timezone.utc)

        inst = find_inst_for_param(c["parameter"], req_calibrated_on=run_d)
        s_min = float(c["minimum_value"])
        s_max = float(c["maximum_value"])
        val = s_min + (s_max - s_min) * 0.5
        unc = min((val - s_min) / 4.0, 0.05)

        experiments.append(make_exp_record(
            scenario_fam="Lot expiry invalid",
            clause=c,
            sample=s,
            run_d=run_d,
            col_iso=_iso_dt(col_dt),
            ana_iso=_iso_dt(ana_dt),
            inst_id=inst["instrument_id"],
            lot_id=lot["lot_id"],
            val=val,
            unit=c["canonical_unit"],
            unc=unc,
        ))

    # --------------------------------------------------------------------------
    # 6. Holding Time Exceeded Invalid (45 experiments)
    # --------------------------------------------------------------------------
    for i in range(45):
        s = samples[(i + 60) % len(samples)]
        col_utc = get_col_utc(s)
        excess_h = s["max_holding_hours"] + 12.0 + (i % 24)
        ana_utc = col_utc + timedelta(hours=excess_h)
        run_d = ana_utc.date()
        c = find_active_clause(run_d, i + 12)

        inst = find_inst_for_param(c["parameter"], req_calibrated_on=run_d)
        lot = find_lot_for_param(c["parameter"], req_valid_on=run_d)
        s_min = float(c["minimum_value"])
        s_max = float(c["maximum_value"])
        val = s_min + (s_max - s_min) * 0.5
        unc = min((val - s_min) / 4.0, 0.05)

        ana_iso = ana_utc.isoformat().replace("+00:00", "Z")

        experiments.append(make_exp_record(
            scenario_fam="Holding time exceeded invalid",
            clause=c,
            sample=s,
            run_d=run_d,
            col_iso=s["collected_at"],
            ana_iso=ana_iso,
            inst_id=inst["instrument_id"],
            lot_id=lot["lot_id"],
            val=val,
            unit=c["canonical_unit"],
            unc=unc,
        ))

    # --------------------------------------------------------------------------
    # 7. Measurement Out of Range Invalid (45 experiments)
    # --------------------------------------------------------------------------
    for i in range(45):
        s = samples[(i + 80) % len(samples)]
        col_utc = get_col_utc(s)
        ana_utc = col_utc + timedelta(hours=4.0)
        run_d = ana_utc.date()
        c = find_active_clause(run_d, i + 18)

        inst = find_inst_for_param(c["parameter"], req_calibrated_on=run_d)
        lot = find_lot_for_param(c["parameter"], req_valid_on=run_d)

        s_min = float(c["minimum_value"])
        s_max = float(c["maximum_value"])
        span = s_max - s_min
        if i % 2 == 0:
            val = s_max + span * 0.35 + 1.0  # Above max
        else:
            val = max(0.0, s_min - span * 0.35 - 1.0) if s_min > 0 else s_min - 2.0  # Below min
        unc = span * 0.02

        ana_iso = ana_utc.isoformat().replace("+00:00", "Z")

        experiments.append(make_exp_record(
            scenario_fam="Measurement out of range invalid",
            clause=c,
            sample=s,
            run_d=run_d,
            col_iso=s["collected_at"],
            ana_iso=ana_iso,
            inst_id=inst["instrument_id"],
            lot_id=lot["lot_id"],
            val=val,
            unit=c["canonical_unit"],
            unc=unc,
        ))

    # --------------------------------------------------------------------------
    # 8. Timestamp Inversion Invalid (25 experiments)
    # --------------------------------------------------------------------------
    for i in range(25):
        s = samples[(i + 95) % len(samples)]
        col_utc = get_col_utc(s)
        # Analysis timestamp 2 - 5 hours BEFORE collection in UTC!
        ana_utc = col_utc - timedelta(hours=2.0 + (i % 4))
        run_d = col_utc.date()
        c = find_active_clause(run_d, i + 22)

        inst = find_inst_for_param(c["parameter"], req_calibrated_on=run_d)
        lot = find_lot_for_param(c["parameter"], req_valid_on=run_d)
        s_min = float(c["minimum_value"])
        s_max = float(c["maximum_value"])
        val = s_min + (s_max - s_min) * 0.5
        unc = min((val - s_min) / 4.0, 0.05)

        ana_iso = ana_utc.isoformat().replace("+00:00", "Z")

        experiments.append(make_exp_record(
            scenario_fam="Timestamp inversion invalid",
            clause=c,
            sample=s,
            run_d=run_d,
            col_iso=s["collected_at"],
            ana_iso=ana_iso,
            inst_id=inst["instrument_id"],
            lot_id=lot["lot_id"],
            val=val,
            unit=c["canonical_unit"],
            unc=unc,
        ))

    # --------------------------------------------------------------------------
    # 9. Compound Dual Failure Invalid (35 experiments)
    # --------------------------------------------------------------------------
    for i in range(35):
        s = samples[(i + 110) % len(samples)]
        inst = expired_insts[i % len(expired_insts)]
        cal_d = date.fromisoformat(inst["calibration_date"])
        exp_d = cal_d + timedelta(days=inst["validity_days"])
        run_d = exp_d + timedelta(days=20)
        c = find_active_clause(run_d, i + 25)

        col_dt = datetime(run_d.year, run_d.month, run_d.day, 8, 0, tzinfo=timezone.utc) - timedelta(hours=s["max_holding_hours"] + 24)
        ana_dt = datetime(run_d.year, run_d.month, run_d.day, 10, 0, tzinfo=timezone.utc)

        lot = find_lot_for_param(c["parameter"], req_valid_on=run_d)
        s_min = float(c["minimum_value"])
        s_max = float(c["maximum_value"])
        val = s_min + (s_max - s_min) * 0.5
        unc = min((val - s_min) / 4.0, 0.05)

        experiments.append(make_exp_record(
            scenario_fam="Compound dual failure invalid",
            clause=c,
            sample=s,
            run_d=run_d,
            col_iso=_iso_dt(col_dt),
            ana_iso=_iso_dt(ana_dt),
            inst_id=inst["instrument_id"],
            lot_id=lot["lot_id"],
            val=val,
            unit=c["canonical_unit"],
            unc=unc,
        ))

    # --------------------------------------------------------------------------
    # 10. SOP Overlap Conflict Review (40 experiments)
    # --------------------------------------------------------------------------
    for i in range(40):
        c = overlap_sop3_clauses[i % len(overlap_sop3_clauses)]
        s = samples[(i + 120) % len(samples)]
        run_d = date(2025, 5, 16) + timedelta(days=i % 14)  # Strictly in overlap window!
        col_dt = datetime(run_d.year, run_d.month, run_d.day, 8, 0, tzinfo=timezone.utc)
        ana_dt = col_dt + timedelta(hours=4.0)

        inst = find_inst_for_param(c["parameter"], req_calibrated_on=run_d)
        lot = find_lot_for_param(c["parameter"], req_valid_on=run_d)
        s_min = float(c["minimum_value"])
        s_max = float(c["maximum_value"])
        val = s_min + (s_max - s_min) * 0.5
        unc = min((val - s_min) / 4.0, 0.05)

        experiments.append(make_exp_record(
            scenario_fam="SOP overlap conflict review",
            clause=c,
            sample=s,
            run_d=run_d,
            col_iso=_iso_dt(col_dt),
            ana_iso=_iso_dt(ana_dt),
            inst_id=inst["instrument_id"],
            lot_id=lot["lot_id"],
            val=val,
            unit=c["canonical_unit"],
            unc=unc,
            sop_v=None,  # Intentionally None!
        ))

    # --------------------------------------------------------------------------
    # 11. Measurement Boundary Uncertainty Review (70 experiments)
    # --------------------------------------------------------------------------
    for i in range(70):
        s = samples[(i + 130) % len(samples)]
        col_utc = get_col_utc(s)
        ana_utc = col_utc + timedelta(hours=4.0)
        run_d = ana_utc.date()
        c = find_active_clause(run_d, i + 4)

        inst = find_inst_for_param(c["parameter"], req_calibrated_on=run_d)
        lot = find_lot_for_param(c["parameter"], req_valid_on=run_d)

        s_min = float(c["minimum_value"])
        s_max = float(c["maximum_value"])
        span = s_max - s_min

        # Straddle boundary:
        if i % 2 == 0:
            val = s_max - span * 0.03
            unc = span * 0.06  # upper bound is s_max + 0.03*span -> crosses!
        else:
            val = s_min + span * 0.03
            unc = span * 0.06  # lower bound is s_min - 0.03*span -> crosses!

        ana_iso = ana_utc.isoformat().replace("+00:00", "Z")

        experiments.append(make_exp_record(
            scenario_fam="Measurement boundary uncertainty review",
            clause=c,
            sample=s,
            run_d=run_d,
            col_iso=s["collected_at"],
            ana_iso=ana_iso,
            inst_id=inst["instrument_id"],
            lot_id=lot["lot_id"],
            val=val,
            unit=c["canonical_unit"],
            unc=unc,
        ))

    # --------------------------------------------------------------------------
    # 12. Missing Evidence Review (55 experiments)
    # --------------------------------------------------------------------------
    for i in range(55):
        s = samples[(i + 140) % len(samples)]
        col_utc = get_col_utc(s)
        ana_utc = col_utc + timedelta(hours=4.0)
        run_d = ana_utc.date()
        c = find_active_clause(run_d, i + 8)

        inst = find_inst_for_param(c["parameter"], req_calibrated_on=run_d)
        lot = find_lot_for_param(c["parameter"], req_valid_on=run_d)
        s_min = float(c["minimum_value"])
        s_max = float(c["maximum_value"])
        val = s_min + (s_max - s_min) * 0.5
        unc = min((val - s_min) / 4.0, 0.05)

        inst_id = inst["instrument_id"]
        lot_id = lot["lot_id"]
        samp_override = _SENTINEL
        sop_override = _SENTINEL

        mod = i % 4
        if mod == 0:
            inst_id = None
        elif mod == 1:
            lot_id = None
        elif mod == 2:
            samp_override = None  # None!
        else:
            sop_override = None  # None!

        ana_iso = ana_utc.isoformat().replace("+00:00", "Z")

        experiments.append(make_exp_record(
            scenario_fam="Missing evidence review",
            clause=c,
            sample=s,
            run_d=run_d,
            col_iso=s["collected_at"],
            ana_iso=ana_iso,
            inst_id=inst_id,
            lot_id=lot_id,
            val=val,
            unit=c["canonical_unit"],
            unc=unc,
            sop_override_id=sop_override,
            sample_override_id=samp_override,
        ))

    # --------------------------------------------------------------------------
    # 13. Broken Foreign Key Review (35 experiments)
    # --------------------------------------------------------------------------
    for i in range(35):
        s = samples[(i + 160) % len(samples)]
        col_utc = get_col_utc(s)
        ana_utc = col_utc + timedelta(hours=4.0)
        run_d = ana_utc.date()
        c = find_active_clause(run_d, i + 14)

        inst = find_inst_for_param(c["parameter"], req_calibrated_on=run_d)
        lot = find_lot_for_param(c["parameter"], req_valid_on=run_d)
        s_min = float(c["minimum_value"])
        s_max = float(c["maximum_value"])
        val = s_min + (s_max - s_min) * 0.5
        unc = min((val - s_min) / 4.0, 0.05)

        inst_id = inst["instrument_id"]
        lot_id = lot["lot_id"]
        clause_id = _SENTINEL
        sample_id = _SENTINEL

        mod = i % 4
        if mod == 0:
            inst_id = "INST-999"
        elif mod == 1:
            lot_id = "LOT-999"
        elif mod == 2:
            sample_id = "SMP-9999"
        else:
            clause_id = "CLAUSE-999"

        ana_iso = ana_utc.isoformat().replace("+00:00", "Z")

        experiments.append(make_exp_record(
            scenario_fam="Broken foreign key review",
            clause=c,
            sample=s,
            run_d=run_d,
            col_iso=s["collected_at"],
            ana_iso=ana_iso,
            inst_id=inst_id,
            lot_id=lot_id,
            val=val,
            unit=c["canonical_unit"],
            unc=unc,
            clause_override_id=clause_id,
            sample_override_id=sample_id,
        ))

    # --------------------------------------------------------------------------
    # 14. Compound Failure with Review (40 experiments)
    # --------------------------------------------------------------------------
    for i in range(40):
        s = samples[(i + 175) % len(samples)]
        inst = expired_insts[i % len(expired_insts)]
        cal_d = date.fromisoformat(inst["calibration_date"])
        exp_d = cal_d + timedelta(days=inst["validity_days"])
        run_d = exp_d + timedelta(days=15)
        c = find_active_clause(run_d, i + 16)

        col_dt = datetime(run_d.year, run_d.month, run_d.day, 8, 0, tzinfo=timezone.utc)
        ana_dt = col_dt + timedelta(hours=4.0)

        lot = find_lot_for_param(c["parameter"], req_valid_on=run_d)
        s_min = float(c["minimum_value"])
        s_max = float(c["maximum_value"])
        span = s_max - s_min
        val = s_max - span * 0.03
        unc = span * 0.06  # straddles upper boundary

        experiments.append(make_exp_record(
            scenario_fam="Compound failure with review",
            clause=c,
            sample=s,
            run_d=run_d,
            col_iso=_iso_dt(col_dt),
            ana_iso=_iso_dt(ana_dt),
            inst_id=inst["instrument_id"],
            lot_id=lot["lot_id"],
            val=val,
            unit=c["canonical_unit"],
            unc=unc,
        ))

    assert len(experiments) == total_experiments, f"Expected {total_experiments}, got {len(experiments)}"

    experiments.sort(key=lambda x: (x["run_date"], x["analyzed_at"], x["scenario_family"], x["clause_id"]))
    for idx, e in enumerate(experiments, start=1):
        e["experiment_id"] = f"EXP-{idx:04d}"

    return experiments


def generate_all_v2(seed: int = 42, output_dir: Optional[str] = None) -> Dict[str, Any]:
    """Generate all V2 raw datasets and write to disk."""
    out_dir = output_dir or RAW_V2_DIR
    os.makedirs(out_dir, exist_ok=True)
    rng = random.Random(seed)

    sops = generate_sops_v2()
    instruments = generate_instruments_v2(rng)
    lots = generate_lots_v2(rng)
    samples = generate_samples_v2(rng)
    experiments = generate_experiments_v2(sops, instruments, lots, samples, rng, total_experiments=1200)

    def write_jsonl(filename: str, records: List[Dict[str, Any]]) -> str:
        p = os.path.join(out_dir, filename)
        with open(p, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        return p

    write_jsonl("sops_v2.jsonl", sops)
    write_jsonl("instruments_v2.jsonl", instruments)
    write_jsonl("lots_v2.jsonl", lots)
    write_jsonl("samples_v2.jsonl", samples)
    write_jsonl("experiments_v2.jsonl", experiments)

    csv_path = os.path.join(out_dir, "runs_v2.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=EXPERIMENT_FIELDNAMES_V2)
        writer.writeheader()
        writer.writerows(experiments)

    fam_counts: Dict[str, int] = {}
    for e in experiments:
        fam = e.get("scenario_family", "UNKNOWN")
        fam_counts[fam] = fam_counts.get(fam, 0) + 1

    metadata = {
        "version": "2.0.0",
        "seed": seed,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "sops": len(sops),
            "instruments": len(instruments),
            "lots": len(lots),
            "samples": len(samples),
            "experiments": len(experiments),
        },
        "scenario_family_distribution": fam_counts,
    }

    meta_path = os.path.join(out_dir, "metadata_v2.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return metadata
