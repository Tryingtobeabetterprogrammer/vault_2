# VAULT — Kaggle Validation Correction & Regression Report

**Target:** Air Quality Data in India (2015–2020) (`city_day.csv`)  
**Lead Investigator:** Vijay (Scientific Data Engineer & Evidence Verification Lead)  
**Execution Environment:** Windows 11 AMD64, Python 3.11.9, pytest 9.2.0, CuratorKIT v0.1.21  
**Audit Date:** 2026-11-09  
**Status:** **CORRECTIONS APPLIED & REGRESSION COMPLETE — PASS**  

---

## 1. Executive Summary & Scope

Following the external Kaggle validation output inspection, this report documents targeted corrections applied strictly to the Kaggle validation implementation (`data_engine/kaggle_adapter.py`, `data_engine/kaggle_verifier.py`, and `tests/test_kaggle_validation.py`).

### Non-Negotiable Boundaries Maintained:
1. **Raw Dataset Immutability:** Original Kaggle CSVs in `data/kaggle_raw/` were not altered.
2. **Synthetic Memory & Training Isolation:** Synthetic datasets (`records.jsonl`, `truth_ledger.jsonl`), V1 baseline files, and V5 training exports were preserved with 100% byte-level immutability.
3. **Historical Report Preservation:** The original report [`docs/KAGGLE_EXTERNAL_VALIDATION_REPORT.md`](file:///c:/VAULT/docs/KAGGLE_EXTERNAL_VALIDATION_REPORT.md) is preserved untouched as the historical benchmark record.
4. **Git State:** No git commits or push operations were executed.

---

## 2. Correction 1: CPCB Severe Boundary Correction

### 2.1 Problem Analysis
In the preliminary implementation, the upper bound for the `Severe` category in `AQI_BUCKET_LIMITS` was set to `(401, 5000)`. This allowed ambient telemetry records reporting anomalous or unbounded AQI values (reaching up to 2049.0 in the raw dataset) to pass bucket consistency checks.

Under the official **CPCB National Air Quality Index (NAQI)** guidelines (2014–2015), the official index is defined strictly across the range **[0, 500]** partitioned into six categories:
- **Good:** [0, 50]
- **Satisfactory:** [51, 100]
- **Moderate:** [101, 200]
- **Poor:** [201, 300]
- **Very Poor:** [301, 400]
- **Severe:** [401, 500]

Any reported AQI value exceeding 500 falls outside the official national index scale and violates the mathematical definition of the Severe category.

### 2.2 Implementation Changes
- **[`data_engine/kaggle_adapter.py`](file:///c:/VAULT/data_engine/kaggle_adapter.py):** Corrected `AQI_BUCKET_LIMITS["Severe"]` from `(401, 5000)` to `(401, 500)`.
- **[`data_engine/kaggle_verifier.py`](file:///c:/VAULT/data_engine/kaggle_verifier.py):** Updated bucket verification to enforce the upper ceiling of 500 and added an explicit scale range check flag (`AQI_BUCKET_CONTRADICTION`) for values exceeding 500.

### 2.3 Boundary Test Evidence
Four targeted automated test cases were added to [`tests/test_kaggle_validation.py`](file:///c:/VAULT/tests/test_kaggle_validation.py#L173-L208) (`test_cpcb_severe_boundary_values`):

| Test Condition | Reported AQI | Reported Bucket | Expected Status | Result | Details |
|---|---|---|---|---|---|
| Lower Boundary | `400.0` | `Very Poor` | `needs_review` | **PASS** | Valid upper limit of Very Poor $[301, 400]$ |
| Lower Severe | `401.0` | `Severe` | `needs_review` | **PASS** | Valid lower limit of Severe $[401, 500]$ |
| Upper Severe | `500.0` | `Severe` | `needs_review` | **PASS** | Valid upper limit of Severe $[401, 500]$ |
| Out of Scale | `501.0` | `Severe` | `flagged` | **PASS** | Triggers `AQI_BUCKET_CONTRADICTION` (hard defect) |

---

## 3. Correction 2: Clarification of AQI Validation Scope

We explicitly decoupled and clarified two distinct validation checks in the architecture:

1. **Check 1 — AQI Numerical Value vs. Categorical Bucket Consistency (Implemented):**
   - Validates whether the reported numerical AQI falls strictly within the CPCB NAQI breakpoint interval for the reported categorical bucket.
   - Evaluated across all records containing reported AQI and Bucket labels.
2. **Check 2 — Independent AQI Recalculation from Raw Concentrations (Explicitly Outside Scope):**
   - Calculating an independent CPCB AQI from scratch requires complete sub-index piecewise linear interpolation for individual pollutants:
     $$I_p = \frac{I_{HI} - I_{LO}}{B_{HI} - B_{LO}} (C_p - B_{LO}) + I_{LO}$$
     requiring a minimum of 3 valid pollutant sub-indices (including at least one particulate: $\text{PM}_{2.5}$ or $\text{PM}_{10}$), 24-hour continuous telemetry averaging, and truncated integer conversions.
   - **Scope Statement:** Independent AQI recalculation is **NOT** performed and is explicitly declared outside the current experiment scope.
   - Added an explicit evidence entry to every verified record in [`data_engine/kaggle_verifier.py`](file:///c:/VAULT/data_engine/kaggle_verifier.py#L171-L182):
     ```json
     {
       "check": "aqi_independent_recalculation",
       "status": "outside_scope",
       "details": "Independent AQI recalculation from raw pollutant concentrations requires complete CPCB sub-index linear interpolation (minimum 3 pollutants with at least one PM2.5 or PM10, 24-hr averaging periods, and truncated integer conversions). Independent recalculation is not implemented and is outside the current experiment scope."
     }
     ```

---

## 4. Verification 3: Data Classification Audit

We conducted an architectural audit of telemetry parsing and status routing:

1. **Zero Pollutant Values are Real Measurements:**
   - In `KaggleAirQualityAdapter.parse_city_day_record`, `"0"` and `"0.0"` are parsed as `float(0.0)`.
   - In `verify_kaggle_record`, `val is not None and not math.isnan(val)` evaluates to `True` for `0.0`.
   - `0.0` increments `valid_meas_count` and is never treated as missing.
   - Verified by test `test_zero_pollutant_values_distinguished_from_blanks`: a record with `PM2.5: "0.0"` and all other pollutants blank is recognized as valid telemetry and does **not** trigger `INSUFFICIENT_POLLUTANT_DATA`.
2. **Blanks and Zeros are Distinguished:**
   - Blank strings (`""`) parse to `None` in `measurements` and are registered in `metadata_audit["missing_fields"]`.
   - Numerical zeros (`"0.0"`) parse to `0.0` and are registered in `metadata_audit["available_fields"]`.
3. **Missing AQI Values Separated from Missing Pollutant Data:**
   - Missing AQI triggers `REASON_MISSING_AQI_AND_BUCKET = "MISSING_AQI_EVIDENCE"`. Because pollutant readings exist, the record is routed to `needs_review` (`verdict: unverified`).
   - Missing pollutant readings triggers `REASON_INSUFFICIENT_POLLUTANT_DATA = "INSUFFICIENT_POLLUTANT_DATA"`, which is a hard defect routing directly to `flagged` (`verdict: invalid`).
   - Verified by test `test_missing_aqi_classified_separately_from_missing_pollutants`.
4. **Exactly One Primary Status per Record:**
   - The status determination logic in `verify_kaggle_record` evaluates `has_hard_defects`. If any hard defect exists, `status = "flagged"`; otherwise `status = "needs_review"`. Every record receives exactly one primary status in `{"checks_passed", "needs_review", "flagged"}`.
   - Verified by test `test_every_record_receives_exactly_one_primary_status`.

---

## 5. Old versus Corrected Results Comparison

Re-evaluating all **29,531 records** in `data/kaggle_raw/city_day.csv` under the corrected CPCB NAQI boundary yields the following comparison:

### 5.1 Verification Breakdown Table

| Metric | Preliminary / Old Result (`Severe`: 401–5000) | Corrected Result (`Severe`: 401–500) | Delta | Explanation |
|---|---|---|---|---|
| **Total Records Ingested** | 29,531 | 29,531 | 0 | 100% of rows evaluated |
| **`checks_passed`** | 0 (0.00%) | 0 (0.00%) | 0 | Ambient telemetry lacks accredited laboratory metadata |
| **`needs_review`** | 28,108 (95.18%) | **27,565 (93.34%)** | **-543** | Records exceeding official AQI scale reclassified to `flagged` |
| **`flagged`** | 1,423 (4.82%) | **1,966 (6.66%)** | **+543** | Correctly catches 543 out-of-scale AQI values ($>500$) |
| **`INSUFFICIENT_POLLUTANT_DATA`** | 1,423 | 1,423 | 0 | Records with all pollutant columns blank |
| **`AQI_BUCKET_CONTRADICTION`** | 0 | **543** | **+543** | Records with reported AQI $>500$ labelled "Severe" |
| **`MISSING_AQI_EVIDENCE`** | 4,681 | 4,681 | 0 | Records lacking AQI and Bucket labels |
| **Missing Lab Evidence Codes** | 28,108 | 27,565 | -543 | Only applied to `needs_review` records |

### 5.2 Analysis of the 543 Reclassified Records
- In `city_day.csv`, exactly 543 records have reported AQI values strictly greater than 500.0 (maximum observed AQI is **2049.0** in Ahmedabad on 2015-05-20).
- These 543 records were previously placed in `needs_review` because `(401, 5000)` masked their scale violation.
- Under the corrected CPCB NAQI standard scale $[401, 500]$, these 543 records violate the official index maximum, triggering `AQI_BUCKET_CONTRADICTION`.
- Because `AQI_BUCKET_CONTRADICTION` is a hard defect, these 543 records now transition to `flagged` (`verdict: invalid`).
- **Disjointness Confirmed:** None of these 543 records had missing pollutants (`INSUFFICIENT_POLLUTANT_DATA`). The flagged total is exactly $1,423 + 543 = 1,966$.

---

## 6. Investigation of Test Commands Exiting with Code 1

During the regression check, two test commands exited with code 1. A rigorous root cause analysis was conducted:

### Incident 1: `pytest -q`
- **Observed Output / Traceback:**
  ```text
  pytest : The term 'pytest' is not recognized as the name of a cmdlet, function, script file, or operable program. 
  Check the spelling of the name, or if a path was included, verify that the path is correct and try again.
  ```
- **Root Cause:**
  In this PowerShell session, the virtual environment is located locally at `c:\VAULT\.venv\Scripts\`. The global system `$PATH` does not include `.venv\Scripts\`, meaning the bare command `pytest` is not found on PATH.
- **Resolution:**
  Invoke pytest directly via the project virtual environment binary: `.venv\Scripts\pytest.exe`.

### Incident 2: `.venv\Scripts\pytest.exe` inside Standard Sandbox Mode
- **Observed Output / Traceback:**
  ```text
  No Python at '"C:\Users\vijay\AppData\Local\Python\pythoncore-3.11-64\python.exe'
  Command exited with code 1.
  ```
- **Root Cause Analysis:**
  Inspection of `c:\VAULT\.venv\pyvenv.cfg` revealed:
  ```ini
  home = C:\Users\vijay\AppData\Local\Python\pythoncore-3.11-64
  include-system-site-packages = false
  version = 3.11.9
  executable = C:\Users\vijay\AppData\Local\Python\pythoncore-3.11-64\python.exe
  ```
  The virtual environment is a shim environment that delegates to the base Python installation at `C:\Users\vijay\AppData\Local\Python\pythoncore-3.11-64\`.
  Under Standard Sandbox Mode (`BypassSandbox: false`), file system read access outside the workspace (`c:\VAULT`) and the agent app data directory (`.gemini\antigravity\`) is blocked by default. When the `.venv\Scripts\python.exe` shim executes inside the sandbox, Windows restricts access to `AppData\Local\Python\pythoncore-3.11-64\`, raising `No Python at '...'` and terminating with code 1.
- **Resolution & Verification:**
  Running the test suite with `BypassSandbox: true` grants access to the base Python runtime DLLs on Windows. When executed with bypass, `.venv\Scripts\pytest.exe` executes cleanly without errors: **210 passed in 6.00s**.

---

## 7. Full Regression Results

All regression suites were executed and verified:

| Test Suite / Script | Command | Tests Run | Result | Duration | Notes |
|---|---|---|---|---|---|
| **Kaggle Validation Suite** | `.venv\Scripts\pytest.exe tests/test_kaggle_validation.py -v` | 13 | **PASS (100%)** | 0.18s | Includes new Severe boundary and classification tests |
| **Round-Trip Teacher Tests** | `.venv\Scripts\pytest.exe tests/test_roundtrip.py -v` | 10 | **PASS (100%)** | 0.44s | Validates round-trip extraction and truth-ledger gate |
| **Multiprocess Memory Tests** | `.venv\Scripts\pytest.exe tests/test_memory_multiprocess.py -v` | 5 | **PASS (100%)** | 3.57s | Cross-process concurrency and file locking |
| **Full Pytest Suite** | `.venv\Scripts\pytest.exe -v` | 210 | **PASS (100%)** | 6.00s | All core VAULT V1–V5 automated tests passing |
| **V1 Baseline Immutability** | `.venv\Scripts\python scripts/verify_v1_baseline.py` | 11 files | **PASS (100%)** | 0.15s | All V1 baseline files 100% identical to baseline manifest |
| **V5 Export Audit** | `.venv\Scripts\python scripts/audit_v5_final.py` | 10 points | **PASS (100%)** | 0.22s | Zero leakage, 720 accepted / 480 quarantined disjoint |

---

## 8. Summary of Completed Actions

1. **CPCB Severe Boundary Corrected:** `(401, 500)` strictly enforced in `data_engine/kaggle_adapter.py` and `data_engine/kaggle_verifier.py`.
2. **Boundary Unit Tests Added:** Boundary conditions (400, 401, 500, 501) tested and passing.
3. **AQI Scope Clarified:** Consistency checks vs. independent recalculation separated; independent recalculation formally documented as outside scope.
4. **Data Classification Verified:** Zeros, blanks, missing AQI, and primary status handling audited and verified.
5. **Full Regression Validated:** 210 pytest tests, V1 baseline, and V5 export audit pass with zero failures.
6. **Report Archived:** Preserved in [`docs/KAGGLE_VALIDATION_CORRECTION_REPORT.md`](file:///c:/VAULT/docs/KAGGLE_VALIDATION_CORRECTION_REPORT.md); original validation report kept intact.

