"""VAULT Kaggle Adapter for Air Quality Data in India (2015-2020).

Maps real-world Kaggle environmental telemetry into VAULT-compatible record structures
without inventing missing laboratory evidence, preserving original columns and values.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

# CPCB Documented Measurands and Units
KAGGLE_MEASURAND_UNITS = {
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
}

# CPCB NAQI Documented Breakpoints (2014-2015 Guidelines)
# Official scale spans 0 to 500 across six categories.
AQI_BUCKET_LIMITS = {
    "Good": (0, 50),
    "Satisfactory": (51, 100),
    "Moderate": (101, 200),
    "Poor": (201, 300),
    "Very Poor": (301, 400),
    "Severe": (401, 500),
}


class KaggleAirQualityAdapter:
    """Adapts raw Kaggle CSV records to VAULT-compatible envelopes with explicit evidence tracking."""

    @staticmethod
    def compute_sha256(payload: Dict[str, Any]) -> str:
        s = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(s).hexdigest()

    @classmethod
    def parse_city_day_record(cls, row: Dict[str, str], row_index: int) -> Dict[str, Any]:
        """Convert a city_day.csv row into a VAULT-compatible record envelope."""
        city = row.get("City", "").strip()
        date_str = row.get("Date", "").strip()
        record_id = f"KAG-CITY-{city[:3].upper()}-{date_str}-{row_index:05d}"

        # Parse numerical pollutant readings
        measurements: Dict[str, Optional[float]] = {}
        for param in KAGGLE_MEASURAND_UNITS:
            raw_val = row.get(param, "").strip()
            if raw_val != "":
                try:
                    measurements[param] = float(raw_val)
                except ValueError:
                    measurements[param] = None
            else:
                measurements[param] = None

        raw_aqi = row.get("AQI", "").strip()
        aqi_val = float(raw_aqi) if raw_aqi != "" else None
        aqi_bucket = row.get("AQI_Bucket", "").strip() or None

        return {
            "record_id": record_id,
            "source_type": "kaggle_environmental_telemetry",
            "dataset_origin": "rohanrao/air-quality-data-in-india/city_day.csv",
            "city": city,
            "site_id": f"CITY-{city.upper()}",
            "run_date": date_str,
            "measurements": measurements,
            "aqi": aqi_val,
            "aqi_bucket": aqi_bucket,
            "raw_payload": dict(row),
            "payload_sha256": cls.compute_sha256(row),
            # Explicit evidence categorization
            "metadata_audit": {
                "available_fields": [k for k, v in row.items() if v.strip() != ""],
                "missing_fields": [k for k, v in row.items() if v.strip() == ""],
                "laboratory_metadata_missing": [
                    "sop_id", "sop_version", "clause_id",
                    "instrument_id", "calibration_window",
                    "reagent_lot_id", "collection_timestamp",
                    "analysis_timestamp", "measurement_uncertainty"
                ],
                "unsupported_fields": ["Xylene", "Toluene", "Benzene"] if any(row.get(k) for k in ["Xylene", "Toluene", "Benzene"]) else [],
                "requires_human_review": aqi_val is None or aqi_bucket is None,
            }
        }

    @classmethod
    def stream_city_day_records(cls, csv_path: Path) -> Generator[Dict[str, Any], None, None]:
        with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader, start=1):
                yield cls.parse_city_day_record(row, idx)

