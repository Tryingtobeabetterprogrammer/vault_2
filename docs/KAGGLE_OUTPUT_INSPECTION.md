# VAULT — Kaggle External Validation Output Inspection

**Inspection Target:** Air Quality Data in India (2015–2020) (`city_day.csv`)  
**Inspector:** Vijay (Scientific Data Engineer & Evidence Verification Lead)  
**Execution Runtime:** Python 3.11.9, pytest 9.2.0, CuratorKIT v0.1.21  
**Audit Status:** Complete Read-Only Verification  
**Inspection Date:** 2026-11-09  

---

## 1. Inspected Files & Provenance

This inspection is strictly read-only and draws directly from the following persisted files in the repository:

1. [`data/kaggle_validation/validation_summary.json`](file:///c:/VAULT/data/kaggle_validation/validation_summary.json)
2. [`data/kaggle_validation/verification_results.json`](file:///c:/VAULT/data/kaggle_validation/verification_results.json)
3. [`data/kaggle_validation/dataset_profile.json`](file:///c:/VAULT/data/kaggle_validation/dataset_profile.json)
4. [`docs/KAGGLE_EXTERNAL_VALIDATION_REPORT.md`](file:///c:/VAULT/docs/KAGGLE_EXTERNAL_VALIDATION_REPORT.md)

---

## 2. Cardinality, Completeness & Overlap Verification

### 2.1 Were all 29,531 records processed exactly once?
**YES.**
- The input dataset `data/kaggle_raw/city_day.csv` contains exactly **29,531 data rows** (29,532 total lines including the single CSV header row).
- SHA-256 fingerprint of `city_day.csv`: `0d84b21c3e4878bbad8df362f2ab05f61ad959538dddf5918e714077ed3c1847`.
- The streaming pipeline ingested and verified all 29,531 records in 1.06 seconds with zero dropped records and zero duplicate executions:
  - **`needs_review` records:** 28,108 (95.18%)
  - **`flagged` records:** 1,423 (4.82%)
  - **`checks_passed` records:** 0 (0.00%)
  - **Total:** $28,108 + 1,423 + 0 = 29,531$ ($100.00\%$).

### 2.2 Do the 1,423 flagged records overlap with any other category?
**NO.**
- The VAULT status assignment logic is strictly partitioning and mutually exclusive.
- A record with any hard defect (such as `INSUFFICIENT_POLLUTANT_DATA` where all pollutant fields are empty) is routed directly to `status = "flagged"` (`verdict = "invalid"`).
- Only records with zero hard defects are routed to `status = "needs_review"` (`verdict = "unverified"`).
- Consequently, the intersection between `flagged` and `needs_review` is **0 records**.

### 2.3 Do missing AQI records overlap with needs_review records?
**YES.**
- In `city_day.csv`, exactly **4,681 records** (15.85%) have missing AQI and AQI_Bucket values (`AQI == ""` and `AQI_Bucket == ""`).
- These 4,681 records are partitioned across two categories based on pollutant telemetry presence:
  1. **3,307 records overlap with `needs_review`:** These records contain at least one valid pollutant reading (e.g., non-null concentrations for PM2.5, NO2, CO, etc.). Because the physical measurements are plausible and free of hard defects, the records are classified as `needs_review` (`verdict: unverified`, `abstain: true`) and assigned reason code `MISSING_AQI_EVIDENCE` along with standard missing laboratory metadata codes.
  2. **1,374 records overlap with `flagged`:** In these records, all 12 pollutant columns are also blank. Because no data exists to substantiate an environmental observation, they trigger the hard defect `INSUFFICIENT_POLLUTANT_DATA` and are classified as `flagged` (`verdict: invalid`).
- Check: $3,307 + 1,374 = 4,681$.

---

## 3. Exact Logic Used to Compare AQI and AQI_Bucket

The mathematical consistency check is defined in [`data_engine/kaggle_adapter.py`](file:///c:/VAULT/data_engine/kaggle_adapter.py#L18-L25) and executed in [`data_engine/kaggle_verifier.py`](file:///c:/VAULT/data_engine/kaggle_verifier.py#L111-L141).

### 3.1 CPCB National Air Quality Index (NAQI) Breakpoint Intervals
```python
AQI_BUCKET_LIMITS: Dict[str, Tuple[float, float]] = {
    "Good": (0.0, 50.0),
    "Satisfactory": (51.0, 100.0),
    "Moderate": (101.0, 200.0),
    "Poor": (201.0, 300.0),
    "Very Poor": (301.0, 400.0),
    "Severe": (401.0, 5000.0),
}
```

### 3.2 Python Implementation in `verify_kaggle_record()`
```python
# 3. AQI and AQI_Bucket Mathematical Consistency Check
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
                "details": f"Mathematical contradiction: AQI {aqi} falls outside CPCB '{aqi_bucket}' limits [{min_lim}, {max_lim}].",
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
elif aqi is None and aqi_bucket is None:
    issues.append(REASON_MISSING_AQI_AND_BUCKET)
    evidence.append({
        "check": "aqi_presence",
        "status": "needs_review",
        "details": "AQI and AQI Bucket are both absent.",
    })
```

**Verification Finding:** Across all 24,850 records with non-null AQI and Bucket values in `city_day.csv`, there were **0 contradictions** detected.

---

## 4. Five Randomly Selected `needs_review` Records

These records contain plausible, non-negative pollutant measurements, but are correctly routed to `needs_review` (`verdict: unverified`, `abstain: true`) due to the absence of certified laboratory calibration and SOP metadata.

### Record 1
- **Row Number:** 14441
- **Record ID:** `KAG-CITY-GUW-2020-02-12-14441`
- **City:** Guwahati
- **Date:** 2020-02-12
- **VAULT Status:** `needs_review`
- **Scientific Verdict:** `unverified`
- **Reason Codes:**
  - `MISSING_LABORATORY_CALIBRATION_EVIDENCE`
  - `MISSING_SOP_GOVERNANCE_EVIDENCE`
  - `MISSING_MEASUREMENT_UNCERTAINTY`
- **Original Raw Payload:**
  ```json
  {
    "City": "Guwahati",
    "Date": "2020-02-12",
    "PM2.5": "119.47",
    "PM10": "225.18",
    "NO": "84.67",
    "NO2": "24.27",
    "NOx": "165.0",
    "NH3": "19.25",
    "CO": "1.19",
    "SO2": "13.81",
    "O3": "18.35",
    "Benzene": "0.95",
    "Toluene": "",
    "Xylene": "",
    "AQI": "267.0",
    "AQI_Bucket": "Poor"
  }
  ```

### Record 2
- **Row Number:** 25227
- **Record ID:** `KAG-CITY-PAT-2019-02-22-25227`
- **City:** Patna
- **Date:** 2019-02-22
- **VAULT Status:** `needs_review`
- **Scientific Verdict:** `unverified`
- **Reason Codes:**
  - `MISSING_LABORATORY_CALIBRATION_EVIDENCE`
  - `MISSING_SOP_GOVERNANCE_EVIDENCE`
  - `MISSING_MEASUREMENT_UNCERTAINTY`
- **Original Raw Payload:**
  ```json
  {
    "City": "Patna",
    "Date": "2019-02-22",
    "PM2.5": "160.57",
    "PM10": "",
    "NO": "18.53",
    "NO2": "28.96",
    "NOx": "18.75",
    "NH3": "",
    "CO": "2.34",
    "SO2": "29.32",
    "O3": "53.33",
    "Benzene": "2.75",
    "Toluene": "21.95",
    "Xylene": "9.74",
    "AQI": "331.0",
    "AQI_Bucket": "Very Poor"
  }
  ```

### Record 3
- **Row Number:** 572
- **Record ID:** `KAG-CITY-AHM-2016-07-25-00572`
- **City:** Ahmedabad
- **Date:** 2016-07-25
- **VAULT Status:** `needs_review`
- **Scientific Verdict:** `unverified`
- **Reason Codes:**
  - `MISSING_LABORATORY_CALIBRATION_EVIDENCE`
  - `MISSING_SOP_GOVERNANCE_EVIDENCE`
  - `MISSING_MEASUREMENT_UNCERTAINTY`
- **Original Raw Payload:**
  ```json
  {
    "City": "Ahmedabad",
    "Date": "2016-07-25",
    "PM2.5": "43.71",
    "PM10": "",
    "NO": "8.85",
    "NO2": "39.95",
    "NOx": "40.31",
    "NH3": "",
    "CO": "8.85",
    "SO2": "15.37",
    "O3": "",
    "Benzene": "0.0",
    "Toluene": "0.0",
    "Xylene": "0.0",
    "AQI": "275.0",
    "AQI_Bucket": "Poor"
  }
  ```

### Record 4
- **Row Number:** 28268
- **Record ID:** `KAG-CITY-VIS-2017-01-15-28268`
- **City:** Visakhapatnam
- **Date:** 2017-01-15
- **VAULT Status:** `needs_review`
- **Scientific Verdict:** `unverified`
- **Reason Codes:**
  - `MISSING_LABORATORY_CALIBRATION_EVIDENCE`
  - `MISSING_SOP_GOVERNANCE_EVIDENCE`
  - `MISSING_MEASUREMENT_UNCERTAINTY`
- **Original Raw Payload:**
  ```json
  {
    "City": "Visakhapatnam",
    "Date": "2017-01-15",
    "PM2.5": "76.86",
    "PM10": "123.73",
    "NO": "3.89",
    "NO2": "23.54",
    "NOx": "15.42",
    "NH3": "13.1",
    "CO": "0.98",
    "SO2": "4.77",
    "O3": "105.22",
    "Benzene": "3.72",
    "Toluene": "5.78",
    "Xylene": "1.95",
    "AQI": "148.0",
    "AQI_Bucket": "Moderate"
  }
  ```

### Record 5
- **Row Number:** 28434
- **Record ID:** `KAG-CITY-VIS-2017-06-30-28434`
- **City:** Visakhapatnam
- **Date:** 2017-06-30
- **VAULT Status:** `needs_review`
- **Scientific Verdict:** `unverified`
- **Reason Codes:**
  - `MISSING_AQI_EVIDENCE`
  - `MISSING_LABORATORY_CALIBRATION_EVIDENCE`
  - `MISSING_SOP_GOVERNANCE_EVIDENCE`
  - `MISSING_MEASUREMENT_UNCERTAINTY`
- **Original Raw Payload:**
  ```json
  {
    "City": "Visakhapatnam",
    "Date": "2017-06-30",
    "PM2.5": "",
    "PM10": "",
    "NO": "",
    "NO2": "",
    "NOx": "0.0",
    "NH3": "",
    "CO": "0.0",
    "SO2": "",
    "O3": "",
    "Benzene": "0.0",
    "Toluene": "0.0",
    "Xylene": "0.0",
    "AQI": "",
    "AQI_Bucket": ""
  }
  ```

---

## 5. Five `flagged` Records

All 1,423 flagged records failed due to `INSUFFICIENT_POLLUTANT_DATA` (every pollutant measurement was empty).

### Record 1
- **Row Number:** 6885
- **Record ID:** `KAG-CITY-BRA-2018-09-25-06885`
- **City:** Brajrajnagar
- **Date:** 2018-09-25
- **VAULT Status:** `flagged`
- **Scientific Verdict:** `invalid`
- **Reason Codes:**
  - `INSUFFICIENT_POLLUTANT_DATA`
  - `MISSING_AQI_EVIDENCE`
- **Original Raw Payload:**
  ```json
  {
    "City": "Brajrajnagar",
    "Date": "2018-09-25",
    "PM2.5": "",
    "PM10": "",
    "NO": "",
    "NO2": "",
    "NOx": "",
    "NH3": "",
    "CO": "",
    "SO2": "",
    "O3": "",
    "Benzene": "",
    "Toluene": "",
    "Xylene": "",
    "AQI": "",
    "AQI_Bucket": ""
  }
  ```

### Record 2
- **Row Number:** 12500
- **Record ID:** `KAG-CITY-GUR-2016-03-05-12500`
- **City:** Gurugram
- **Date:** 2016-03-05
- **VAULT Status:** `flagged`
- **Scientific Verdict:** `invalid`
- **Reason Codes:**
  - `INSUFFICIENT_POLLUTANT_DATA`
  - `MISSING_AQI_EVIDENCE`
- **Original Raw Payload:**
  ```json
  {
    "City": "Gurugram",
    "Date": "2016-03-05",
    "PM2.5": "",
    "PM10": "",
    "NO": "",
    "NO2": "",
    "NOx": "",
    "NH3": "",
    "CO": "",
    "SO2": "",
    "O3": "",
    "Benzene": "",
    "Toluene": "",
    "Xylene": "",
    "AQI": "",
    "AQI_Bucket": ""
  }
  ```

### Record 3
- **Row Number:** 966
- **Record ID:** `KAG-CITY-AHM-2017-08-23-00966`
- **City:** Ahmedabad
- **Date:** 2017-08-23
- **VAULT Status:** `flagged`
- **Scientific Verdict:** `invalid`
- **Reason Codes:**
  - `INSUFFICIENT_POLLUTANT_DATA`
  - `MISSING_AQI_EVIDENCE`
- **Original Raw Payload:**
  ```json
  {
    "City": "Ahmedabad",
    "Date": "2017-08-23",
    "PM2.5": "",
    "PM10": "",
    "NO": "",
    "NO2": "",
    "NOx": "",
    "NH3": "",
    "CO": "",
    "SO2": "",
    "O3": "",
    "Benzene": "",
    "Toluene": "",
    "Xylene": "",
    "AQI": "",
    "AQI_Bucket": ""
  }
  ```

### Record 4
- **Row Number:** 6610
- **Record ID:** `KAG-CITY-BRA-2017-12-24-06610`
- **City:** Brajrajnagar
- **Date:** 2017-12-24
- **VAULT Status:** `flagged`
- **Scientific Verdict:** `invalid`
- **Reason Codes:**
  - `INSUFFICIENT_POLLUTANT_DATA`
  - `MISSING_AQI_EVIDENCE`
- **Original Raw Payload:**
  ```json
  {
    "City": "Brajrajnagar",
    "Date": "2017-12-24",
    "PM2.5": "",
    "PM10": "",
    "NO": "",
    "NO2": "",
    "NOx": "",
    "NH3": "",
    "CO": "",
    "SO2": "",
    "O3": "",
    "Benzene": "",
    "Toluene": "",
    "Xylene": "",
    "AQI": "",
    "AQI_Bucket": ""
  }
  ```

### Record 5
- **Row Number:** 24636
- **Record ID:** `KAG-CITY-PAT-2017-07-11-24636`
- **City:** Patna
- **Date:** 2017-07-11
- **VAULT Status:** `flagged`
- **Scientific Verdict:** `invalid`
- **Reason Codes:**
  - `INSUFFICIENT_POLLUTANT_DATA`
  - `MISSING_AQI_EVIDENCE`
- **Original Raw Payload:**
  ```json
  {
    "City": "Patna",
    "Date": "2017-07-11",
    "PM2.5": "",
    "PM10": "",
    "NO": "",
    "NO2": "",
    "NOx": "",
    "NH3": "",
    "CO": "",
    "SO2": "",
    "O3": "",
    "Benzene": "",
    "Toluene": "",
    "Xylene": "",
    "AQI": "",
    "AQI_Bucket": ""
  }
  ```

---

## 6. Five Records Missing AQI Values

This section showcases both subclasses of missing AQI records: those with valid pollutant readings (which land in `needs_review`) and those where all pollutant columns are also absent (which land in `flagged`).

### Record 1 (Missing AQI, Flagged due to empty telemetry)
- **Row Number:** 23064
- **Record ID:** `KAG-CITY-MUM-2018-04-23-23064`
- **City:** Mumbai
- **Date:** 2018-04-23
- **VAULT Status:** `flagged`
- **Scientific Verdict:** `invalid`
- **Reason Codes:**
  - `INSUFFICIENT_POLLUTANT_DATA`
  - `MISSING_AQI_EVIDENCE`
- **Original Raw Payload:**
  ```json
  {
    "City": "Mumbai",
    "Date": "2018-04-23",
    "PM2.5": "",
    "PM10": "",
    "NO": "",
    "NO2": "",
    "NOx": "",
    "NH3": "",
    "CO": "",
    "SO2": "",
    "O3": "",
    "Benzene": "",
    "Toluene": "",
    "Xylene": "",
    "AQI": "",
    "AQI_Bucket": ""
  }
  ```

### Record 2 (Missing AQI, Plausible telemetry -> Needs Review)
- **Row Number:** 8403
- **Record ID:** `KAG-CITY-CHE-2016-07-22-08403`
- **City:** Chennai
- **Date:** 2016-07-22
- **VAULT Status:** `needs_review`
- **Scientific Verdict:** `unverified`
- **Reason Codes:**
  - `MISSING_AQI_EVIDENCE`
  - `MISSING_LABORATORY_CALIBRATION_EVIDENCE`
  - `MISSING_SOP_GOVERNANCE_EVIDENCE`
  - `MISSING_MEASUREMENT_UNCERTAINTY`
- **Original Raw Payload:**
  ```json
  {
    "City": "Chennai",
    "Date": "2016-07-22",
    "PM2.5": "21.38",
    "PM10": "",
    "NO": "7.13",
    "NO2": "15.05",
    "NOx": "16.48",
    "NH3": "95.12",
    "CO": "1.17",
    "SO2": "4.81",
    "O3": "12.6",
    "Benzene": "2.44",
    "Toluene": "3.76",
    "Xylene": "",
    "AQI": "",
    "AQI_Bucket": ""
  }
  ```

### Record 3 (Missing AQI, Plausible telemetry -> Needs Review)
- **Row Number:** 22547
- **Record ID:** `KAG-CITY-MUM-2016-11-22-22547`
- **City:** Mumbai
- **Date:** 2016-11-22
- **VAULT Status:** `needs_review`
- **Scientific Verdict:** `unverified`
- **Reason Codes:**
  - `MISSING_AQI_EVIDENCE`
  - `MISSING_LABORATORY_CALIBRATION_EVIDENCE`
  - `MISSING_SOP_GOVERNANCE_EVIDENCE`
  - `MISSING_MEASUREMENT_UNCERTAINTY`
- **Original Raw Payload:**
  ```json
  {
    "City": "Mumbai",
    "Date": "2016-11-22",
    "PM2.5": "",
    "PM10": "",
    "NO": "",
    "NO2": "",
    "NOx": "",
    "NH3": "",
    "CO": "0.0",
    "SO2": "",
    "O3": "",
    "Benzene": "",
    "Toluene": "",
    "Xylene": "",
    "AQI": "",
    "AQI_Bucket": ""
  }
  ```

### Record 4 (Missing AQI, Plausible telemetry -> Needs Review)
- **Row Number:** 6628
- **Record ID:** `KAG-CITY-BRA-2018-01-11-06628`
- **City:** Brajrajnagar
- **Date:** 2018-01-11
- **VAULT Status:** `needs_review`
- **Scientific Verdict:** `unverified`
- **Reason Codes:**
  - `MISSING_AQI_EVIDENCE`
  - `MISSING_LABORATORY_CALIBRATION_EVIDENCE`
  - `MISSING_SOP_GOVERNANCE_EVIDENCE`
  - `MISSING_MEASUREMENT_UNCERTAINTY`
- **Original Raw Payload:**
  ```json
  {
    "City": "Brajrajnagar",
    "Date": "2018-01-11",
    "PM2.5": "",
    "PM10": "",
    "NO": "0.02",
    "NO2": "0.02",
    "NOx": "0.04",
    "NH3": "",
    "CO": "4.15",
    "SO2": "0.86",
    "O3": "",
    "Benzene": "",
    "Toluene": "",
    "Xylene": "",
    "AQI": "",
    "AQI_Bucket": ""
  }
  ```

### Record 5 (Missing AQI, Plausible telemetry -> Needs Review)
- **Row Number:** 23037
- **Record ID:** `KAG-CITY-MUM-2018-03-27-23037`
- **City:** Mumbai
- **Date:** 2018-03-27
- **VAULT Status:** `needs_review`
- **Scientific Verdict:** `unverified`
- **Reason Codes:**
  - `MISSING_AQI_EVIDENCE`
  - `MISSING_LABORATORY_CALIBRATION_EVIDENCE`
  - `MISSING_SOP_GOVERNANCE_EVIDENCE`
  - `MISSING_MEASUREMENT_UNCERTAINTY`
- **Original Raw Payload:**
  ```json
  {
    "City": "Mumbai",
    "Date": "2018-03-27",
    "PM2.5": "",
    "PM10": "",
    "NO": "",
    "NO2": "",
    "NOx": "38.38",
    "NH3": "",
    "CO": "1.05",
    "SO2": "",
    "O3": "",
    "Benzene": "0.0",
    "Toluene": "0.0",
    "Xylene": "0.0",
    "AQI": "",
    "AQI_Bucket": ""
  }
  ```

---

## 7. Five Records with Valid AQI and AQI_Bucket Values

In each record below, the numeric AQI falls strictly within the prescribed CPCB breakpoint interval. Because laboratory evidence is absent, these records are appropriately placed in `needs_review` (`verdict: unverified`).

### Record 1 (Satisfactory: $[51, 100]$)
- **Row Number:** 9909
- **Record ID:** `KAG-CITY-COI-2019-08-16-09909`
- **City:** Coimbatore
- **Date:** 2019-08-16
- **AQI Value:** `75.0`
- **AQI Bucket:** `Satisfactory` (Interval: $[51.0, 100.0]$ — **Pass**)
- **VAULT Status:** `needs_review`
- **Scientific Verdict:** `unverified`
- **Reason Codes:**
  - `MISSING_LABORATORY_CALIBRATION_EVIDENCE`
  - `MISSING_SOP_GOVERNANCE_EVIDENCE`
  - `MISSING_MEASUREMENT_UNCERTAINTY`
- **Original Raw Payload:**
  ```json
  {
    "City": "Coimbatore",
    "Date": "2019-08-16",
    "PM2.5": "22.4",
    "PM10": "28.27",
    "NO": "9.13",
    "NO2": "7.83",
    "NOx": "16.96",
    "NH3": "25.25",
    "CO": "1.37",
    "SO2": "8.48",
    "O3": "18.16",
    "Benzene": "0.02",
    "Toluene": "0.0",
    "Xylene": "",
    "AQI": "75.0",
    "AQI_Bucket": "Satisfactory"
  }
  ```

### Record 2 (Satisfactory: $[51, 100]$)
- **Row Number:** 20784
- **Record ID:** `KAG-CITY-LUC-2017-07-26-20784`
- **City:** Lucknow
- **Date:** 2017-07-26
- **AQI Value:** `66.0`
- **AQI Bucket:** `Satisfactory` (Interval: $[51.0, 100.0]$ — **Pass**)
- **VAULT Status:** `needs_review`
- **Scientific Verdict:** `unverified`
- **Reason Codes:**
  - `MISSING_LABORATORY_CALIBRATION_EVIDENCE`
  - `MISSING_SOP_GOVERNANCE_EVIDENCE`
  - `MISSING_MEASUREMENT_UNCERTAINTY`
- **Original Raw Payload:**
  ```json
  {
    "City": "Lucknow",
    "Date": "2017-07-26",
    "PM2.5": "46.49",
    "PM10": "",
    "NO": "12.49",
    "NO2": "31.82",
    "NOx": "",
    "NH3": "",
    "CO": "1.13",
    "SO2": "4.31",
    "O3": "10.83",
    "Benzene": "0.83",
    "Toluene": "2.03",
    "Xylene": "",
    "AQI": "66.0",
    "AQI_Bucket": "Satisfactory"
  }
  ```

### Record 3 (Moderate: $[101, 200]$)
- **Row Number:** 24311
- **Record ID:** `KAG-CITY-PAT-2016-08-20-24311`
- **City:** Patna
- **Date:** 2016-08-20
- **AQI Value:** `124.0`
- **AQI Bucket:** `Moderate` (Interval: $[101.0, 200.0]$ — **Pass**)
- **VAULT Status:** `needs_review`
- **Scientific Verdict:** `unverified`
- **Reason Codes:**
  - `MISSING_LABORATORY_CALIBRATION_EVIDENCE`
  - `MISSING_SOP_GOVERNANCE_EVIDENCE`
  - `MISSING_MEASUREMENT_UNCERTAINTY`
- **Original Raw Payload:**
  ```json
  {
    "City": "Patna",
    "Date": "2016-08-20",
    "PM2.5": "55.21",
    "PM10": "",
    "NO": "12.14",
    "NO2": "17.58",
    "NOx": "29.72",
    "NH3": "",
    "CO": "1.18",
    "SO2": "1.89",
    "O3": "13.93",
    "Benzene": "0.13",
    "Toluene": "0.67",
    "Xylene": "0.3",
    "AQI": "124.0",
    "AQI_Bucket": "Moderate"
  }
  ```

### Record 4 (Moderate: $[101, 200]$)
- **Row Number:** 6753
- **Record ID:** `KAG-CITY-BRA-2018-05-16-06753`
- **City:** Brajrajnagar
- **Date:** 2018-05-16
- **AQI Value:** `116.0`
- **AQI Bucket:** `Moderate` (Interval: $[101.0, 200.0]$ — **Pass**)
- **VAULT Status:** `needs_review`
- **Scientific Verdict:** `unverified`
- **Reason Codes:**
  - `MISSING_LABORATORY_CALIBRATION_EVIDENCE`
  - `MISSING_SOP_GOVERNANCE_EVIDENCE`
  - `MISSING_MEASUREMENT_UNCERTAINTY`
- **Original Raw Payload:**
  ```json
  {
    "City": "Brajrajnagar",
    "Date": "2018-05-16",
    "PM2.5": "53.9",
    "PM10": "107.07",
    "NO": "3.86",
    "NO2": "19.28",
    "NOx": "23.14",
    "NH3": "7.53",
    "CO": "3.14",
    "SO2": "12.71",
    "O3": "28.91",
    "Benzene": "0.0",
    "Toluene": "",
    "Xylene": "",
    "AQI": "116.0",
    "AQI_Bucket": "Moderate"
  }
  ```

### Record 5 (Moderate: $[101, 200]$)
- **Row Number:** 23646
- **Record ID:** `KAG-CITY-MUM-2019-11-26-23646`
- **City:** Mumbai
- **Date:** 2019-11-26
- **AQI Value:** `193.0`
- **AQI Bucket:** `Moderate` (Interval: $[101.0, 200.0]$ — **Pass**)
- **VAULT Status:** `needs_review`
- **Scientific Verdict:** `unverified`
- **Reason Codes:**
  - `MISSING_LABORATORY_CALIBRATION_EVIDENCE`
  - `MISSING_SOP_GOVERNANCE_EVIDENCE`
  - `MISSING_MEASUREMENT_UNCERTAINTY`
- **Original Raw Payload:**
  ```json
  {
    "City": "Mumbai",
    "Date": "2019-11-26",
    "PM2.5": "83.45",
    "PM10": "158.37",
    "NO": "28.52",
    "NO2": "47.23",
    "NOx": "75.75",
    "NH3": "16.93",
    "CO": "1.07",
    "SO2": "17.3",
    "O3": "39.16",
    "Benzene": "9.84",
    "Toluene": "",
    "Xylene": "",
    "AQI": "193.0",
    "AQI_Bucket": "Moderate"
  }
  ```

---

## 8. Summary of Findings

1. **Processing Completeness:** All 29,531 records were ingested, validated, and accounted for without omission or duplicate processing.
2. **Category Independence:** The 1,423 `flagged` records and 28,108 `needs_review` records are disjoint sets (0 overlap).
3. **Missing AQI Partitioning:** The 4,681 missing AQI records cleanly split between `needs_review` (3,307 records with valid pollutant readings) and `flagged` (1,374 records with zero pollutant readings).
4. **CPCB Breakpoint Compliance:** 100% of reported AQI/Bucket pairs conform to official NAQI intervals.
5. **Epistemic Discipline:** VAULT refused to mark any ambient telemetry as `checks_passed`, correctly preserving the distinction between environmental sensor monitoring and certified analytical laboratory science.

