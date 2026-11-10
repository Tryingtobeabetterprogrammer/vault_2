#!/usr/bin/env python3
"""Phase 1: Dataset Inspection & Profiling for Kaggle Air Quality Data in India (2015-2020)."""

import csv
import hashlib
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent

# CPCB Standard Documented Units
CPCB_UNITS = {
    "PM2.5": "ug/m3",
    "PM10": "ug/m3",
    "NO": "ug/m3",
    "NO2": "ug/m3",
    "NOx": "ppb",
    "NH3": "ug/m3",
    "CO": "mg/m3",
    "SO2": "ug/m3",
    "O3": "ug/m3",
    "Benzene": "ug/m3",
    "Toluene": "ug/m3",
    "Xylene": "ug/m3",
    "AQI": "dimensionless",
    "AQI_Bucket": "categorical",
}

def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def infer_type(val: str) -> str:
    if val is None or val == "":
        return "empty"
    try:
        int(val)
        return "int"
    except ValueError:
        pass
    try:
        float(val)
        return "float"
    except ValueError:
        pass
    return "string"

def profile_csv(file_path: Path) -> dict:
    file_size = file_path.stat().st_size
    file_sha256 = compute_sha256(file_path)

    total_rows = 0
    column_stats = {}

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        header = next(reader)
        # Normalize BOM if present
        header = [col.lstrip("\ufeff") for col in header]

        for col in header:
            column_stats[col] = {
                "missing_count": 0,
                "present_count": 0,
                "types_seen": set(),
                "unit": CPCB_UNITS.get(col, "documented_metadata" if col in ["City", "Date", "Datetime", "StationId", "StationName", "State", "Status"] else "unknown"),
            }

        for row in reader:
            if not row:
                continue
            total_rows += 1
            for col, val in zip(header, row):
                val_clean = val.strip()
                if val_clean == "":
                    column_stats[col]["missing_count"] += 1
                else:
                    column_stats[col]["present_count"] += 1
                    t = infer_type(val_clean)
                    column_stats[col]["types_seen"].add(t)

    # Format column statistics
    cols_summary = {}
    for col, st in column_stats.items():
        missing = st["missing_count"]
        present = st["present_count"]
        pct_missing = (missing / total_rows * 100.0) if total_rows > 0 else 0.0
        cols_summary[col] = {
            "missing_count": missing,
            "present_count": present,
            "missing_percentage": round(pct_missing, 2),
            "inferred_data_types": list(st["types_seen"]),
            "documented_unit": st["unit"],
        }

    return {
        "file_name": file_path.name,
        "file_size_bytes": file_size,
        "sha256_hash": file_sha256,
        "total_rows": total_rows,
        "total_columns": len(header),
        "column_names": header,
        "columns_profile": cols_summary,
        "provenance": "Central Pollution Control Board (CPCB) India via Kaggle (Rohan Rao / Vopani)",
    }

def main():
    print("=" * 76)
    print(" VAULT — Kaggle Dataset Profiling & Verification")
    print("=" * 76)

    raw_dir = REPO_ROOT / "data" / "kaggle_raw"
    out_dir = REPO_ROOT / "data" / "kaggle_validation"
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_files = sorted(raw_dir.glob("*.csv"))
    assert csv_files, f"No CSV files found in {raw_dir}"

    profile = {}
    checksum_lines = []

    for f in csv_files:
        print(f"Profiling {f.name} ({f.stat().st_size:,} bytes)...")
        res = profile_csv(f)
        profile[f.name] = res
        checksum_lines.append(f"{res['sha256_hash']}  {f.name}")
        print(f"  • Rows: {res['total_rows']:,} | Cols: {res['total_columns']}")
        print(f"  • SHA-256: {res['sha256_hash']}")

    # Save dataset profile JSON
    profile_path = out_dir / "dataset_profile.json"
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)
    print(f"\n[OK] Saved dataset profile to {profile_path.name}")

    # Save checksums.txt
    checksums_path = out_dir / "checksums.txt"
    with open(checksums_path, "w", encoding="utf-8") as f:
        f.write("\n".join(checksum_lines) + "\n")
    print(f"[OK] Saved checksums to {checksums_path.name}")

if __name__ == "__main__":
    main()

