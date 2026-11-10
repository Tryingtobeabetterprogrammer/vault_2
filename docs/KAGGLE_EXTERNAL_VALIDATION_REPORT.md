# VAULT — External Kaggle Dataset Validation Report

**Dataset:** [Air Quality Data in India (2015–2020)](https://www.kaggle.com/datasets/rohanrao/air-quality-data-in-india)  
**Curator / Origin:** Rohan Rao (Vopani) / Central Pollution Control Board (CPCB) India  
**Lead Investigator:** Vijay (Scientific Data Engineer & Evidence Verification Lead)  
**Execution Runtime:** Windows 11 AMD64 (Intel i3, 8 GB RAM), Python 3.11.9, pytest 9.2.0, CuratorKIT v0.1.21  
**Audit Date:** 2026-11-09  
**Status:** **EXPERIMENT COMPLETED — EXTERNAL VALIDATION ARCHIVED**  

---

## 1. Executive Summary & Epistemic Boundaries

This report evaluates the complete **VAULT V1–V5 evidence-verification architecture** against a real-world, public dataset: the *Air Quality Data in India (2015–2020)* dataset curated by Rohan Rao from the Central Pollution Control Board (CPCB).

### Non-Negotiable Operational Principles:
1. **No Data Fabrication:** We did **not** invent synthetic SOPs, instrument calibration certificates, reagent lot numbers, or sample holding times for Kaggle telemetry.
2. **No False Equivalence:** Ambient environmental sensor telemetry was **not** treated as certified analytical laboratory truth.
3. **No Automatic Acceptance:** Records were **not** marked as `checks_passed` simply because an AQI value or pollutant measurement was present.
4. **Strict Isolation:** Existing synthetic datasets (`records.jsonl`, `truth_ledger.jsonl`), V1 baseline files, and V5 training exports were preserved with 100% byte-level immutability.
5. **Epistemic Modesty:** This experiment evaluates architectural robustness and failure modes under incomplete external data; it does **not** claim that VAULT is "scientifically validated" merely because it ingested Kaggle CSVs.

---

## 2. Phase 1 — Dataset Inspection, Profiling & Provenance

All 5 CSV files from the Kaggle dataset were inspected, profiled, and cryptographically fingerprinted in [`data/kaggle_validation/dataset_profile.json`](file:///c:/VAULT/data/kaggle_validation/dataset_profile.json). The original files are preserved unchanged in `data/kaggle_raw/`.

| File Name | Size (Bytes) | Row Count | Column Count | SHA-256 Checksum |
|---|---|---|---|---|
| `city_day.csv` | 2,574,056 | 29,531 | 16 | `0d84b21c3e4878bbad8df362f2ab05f61ad959538dddf5918e714077ed3c1847` |
| `city_hour.csv` | 65,648,581 | 707,875 | 16 | `fae474062ec6b10af7c5b2ac4e32f5c240a0ef80835ee3a50332fec06e2190a4` |
| `station_day.csv` | 8,634,105 | 108,035 | 16 | `f07787eb4c36c53b07763f591ee29fa01fbaa4d18df1a470447d04def79677b9` |
| `station_hour.csv` | 219,675,434 | 2,589,083 | 16 | `26a423c66fe9763064d580ffb007150375cfa2056e62b29d52b1b7857af54fde` |
| `stations.csv` | 14,467 | 230 | 5 | `ce2b7081c3e3c89145613eb724d7d2149ef79c6e16f36bb8a835747a673ed410` |
| **Total** | **296,546,643** | **3,434,754** | — | Recorded in [`data/kaggle_validation/checksums.txt`](file:///c:/VAULT/data/kaggle_validation/checksums.txt) |

### Documented Measurement Units (CPCB Standards):
- **Particulates:** $\text{PM}_{2.5}$ ($\mu\text{g/m}^3$), $\text{PM}_{10}$ ($\mu\text{g/m}^3$).
- **Gases:** $\text{NO}$ ($\mu\text{g/m}^3$), $\text{NO}_2$ ($\mu\text{g/m}^3$), $\text{NO}_x$ ($\text{ppb}$), $\text{NH}_3$ ($\mu\text{g/m}^3$), $\text{CO}$ ($\text{mg/m}^3$), $\text{SO}_2$ ($\mu\text{g/m}^3$), $\text{O}_3$ ($\mu\text{g/m}^3$).
- **Volatile Organics:** Benzene ($\mu\text{g/m}^3$), Toluene ($\mu\text{g/m}^3$), Xylene ($\mu\text{g/m}^3$).
- **Indices:** $\text{AQI}$ (dimensionless sub-index), $\text{AQI\_Bucket}$ (categorical: 'Good', 'Satisfactory', 'Moderate', 'Poor', 'Very Poor', 'Severe').

---

## 3. Phase 2 — VAULT Data Compatibility & Adapter Mapping

We implemented a dedicated adapter ([`data_engine/kaggle_adapter.py`](file:///c:/VAULT/data_engine/kaggle_adapter.py)) that converts raw tabular telemetry into VAULT record envelopes while preserving all raw fields in `raw_payload`:

### Field Categorization Audit:
1. **Available Fields (Mapped):**
   - `City` $\to$ `site_id` / `location`
   - `Date` $\to$ `run_date`
   - Pollutant concentrations $\to$ `measurements`
   - `AQI` and `AQI_Bucket` $\to$ `aqi`, `aqi_bucket`
2. **Missing Laboratory Evidence (Un-mapped):**
   - `sop_id`, `sop_version`, `clause_id`: Entirely absent.
   - `instrument_id` (optical chamber / sensor serial number): Absent.
   - `calibration_window` & `calibration_date`: Absent.
   - `reagent_lot_id`: Absent.
   - `collected_at` & `analyzed_at` (holding time): Absent (only daily date is known).
   - `measurement_uncertainty`: Absent ($k=2, 95\%$ confidence margins omitted).
3. **Unsupported Fields:**
   - Xylene, Toluene, Benzene cross-sensitivities without declared sensor selectivity matrix.
4. **Fields Requiring Human Review:**
   - All records with missing AQI (4,681 records in `city_day.csv`) or uncalibrated raw telemetry.

---

## 4. Phase 3 — Deterministic Verification Results

The deterministic verifier ([`data_engine/kaggle_verifier.py`](file:///c:/VAULT/data_engine/kaggle_verifier.py)) evaluated all **29,531 records** in `city_day.csv`:

```text
Total Records Evaluated: 29,531 (across 26 Indian cities)
Verification Execution Time: 1.06 seconds (27,762.6 records/sec)
```

### 4.1 Verification Status Breakdown

| VAULT Status | Scientific Verdict | Record Count | Percentage | Epistemic Justification |
|---|---|---|---|---|
| **`checks_passed`** | `valid` | **0** | **0.00%** | **Correctly Zero.** Ambient telemetry lacking certified calibration, SOP governance, and uncertainty cannot be certified as compliant laboratory science. |
| **`flagged`** | `invalid` | **1,423** | **4.82%** | **Hard Defects.** 1,423 records contained zero valid pollutant readings (all pollutant fields completely blank). |
| **`needs_review`** | `unverified` | **28,108** | **95.18%** | **Plausible but Unverified.** Contain valid, non-negative pollutant measurements conforming to CPCB limits, but lack laboratory accreditation evidence. |

### 4.2 Issue Frequency Analysis

| Issue Reason Code | Category | Count | % of Dataset |
|---|---|---|---|
| `MISSING_LABORATORY_CALIBRATION_EVIDENCE` | Metrology | 28,108 | 95.18% |
| `MISSING_SOP_GOVERNANCE_EVIDENCE` | Regulatory | 28,108 | 95.18% |
| `MISSING_MEASUREMENT_UNCERTAINTY` | Metrology | 28,108 | 95.18% |
| `MISSING_AQI_EVIDENCE` | Incompleteness | 4,681 | 15.85% |
| `INSUFFICIENT_POLLUTANT_DATA` | Hard Failure | 1,423 | 4.82% |
| `PHYSICAL_IMPOSSIBILITY_NEGATIVE_VALUE` | Hard Failure | 0 | 0.00% |
| `AQI_BUCKET_CONTRADICTION` | Hard Failure | 0 | 0.00% |

### 4.3 CPCB NAQI Mathematical Breakpoint Verification
We tested mathematical consistency between `AQI` and `AQI_Bucket` against the official CPCB 2014–2015 NAQI guidelines:
- Good: $[0, 50]$
- Satisfactory: $[51, 100]$
- Moderate: $[101, 200]$
- Poor: $[201, 300]$
- Very Poor: $[301, 400]$
- Severe: $[401, 500+]$

**Finding:** In `city_day.csv` and `station_day.csv`, exactly **0 mathematical contradictions** were observed between reported AQI numbers and reported bucket labels. The external curator (Rohan Rao) computed these bucket labels with 100% mathematical consistency.

---

## 5. Phase 4 — Scientific Memory in Isolated Storage

To test immutable audit logging on real data without contaminating VAULT's synthetic laboratory memory:
- **Storage Directory:** [`data/kaggle_validation/memory/`](file:///c:/VAULT/data/kaggle_validation/memory/)
- **Source Registration:** 50 unique Kaggle records were registered into `sources_registry.jsonl`. All SHA-256 hashes matched raw payloads.
- **Append-Only Ledger:** 50 assessment findings were appended into `assessments_ledger.jsonl`.
- **Idempotency:** Re-recording an identical Kaggle assessment yielded the existing assessment without duplicate writes.
- **Cross-Process Concurrency:** Dual-lock (`threading.RLock` + `filelock.FileLock`) and atomic `os.replace()` operated cleanly.

---

## 6. Phase 5 — CuratorKIT Hygiene Pipeline

We evaluated the official `curatorkit` v0.1.21 library on converted Kaggle samples:
- **Staging:** Converted 200 Kaggle records into instruction-input-output pairs, intentionally injecting 2 exact duplicates (202 total samples).
- **`SchemaGate`:** Validated required fields (`instruction`, `input`, `output`, `record_id`) and token lengths (202 passed).
- **`ExactDeduplicator`:** Successfully identified and pruned the 2 duplicate entries, preserving exactly 200 unique records.
- **`TextCleaner`:** Executed whitespace and Unicode normalization.
- **Artifacts Emitted:** `sft_messages.jsonl`, `manifest.json`, `dataset_card.md`, `checksums.txt`.

---

## 7. Phase 6 — Round-Trip Verification & Truth Ledger Isolation

To test gatekeeping on external data:
- We synthesized an untrusted teacher explanation asserting certified laboratory compliance for a Kaggle record (`KAG-CITY-DEL-...`).
- The explanation was fed to `data_engine.roundtrip.gate_teacher_candidate()`.
- **Outcome:** **REJECTED / BLOCKED (Status: `needs_review`)**.
- **Reason:** `TEACHER_RECORD_NOT_FOUND` / `TEACHER_MISSING_EXPERIMENT_ID`.
- **Gatekeeper Integrity:** Because Kaggle records do not belong to the locked synthetic laboratory truth ledger, the round-trip engine prevented external unverified claims from entering the fine-tuning candidate pool.

---

## 8. Comparison: Kaggle Telemetry vs Synthetic Scintest Laboratory Data

| Dimension | Synthetic Scintest Lab Data (V1–V5) | External Kaggle Air Quality Telemetry |
|---|---|---|
| **Domain Nature** | Controlled analytical laboratory chemistry | Ambient municipal sensor telemetry |
| **Ground Truth Authority** | Formal synthetic truth ledger (`truth_ledger.jsonl`) | Unverified third-party web dataset |
| **SOP & Clause Governance** | 100% documented (`SOP-001` through `SOP-008`) | **0% documented (Missing)** |
| **Instrument Calibration** | Certified calibration dates & windows | **0% documented (Missing)** |
| **Reagent Lots** | Qualification dates & expiration dates | **Not applicable / Missing** |
| **Holding Time Compliance** | Explicit sample collection & analysis timestamps | **0% documented (Missing)** |
| **Measurement Uncertainty** | Rigorous expanded uncertainty margins ($k=2$) | **0% documented (Missing)** |
| **VAULT Acceptance Rate** | **60.0% (`checks_passed`)** | **0.0% (`checks_passed`)** |
| **VAULT Quarantine Rate** | **40.0% (`flagged` / `needs_review`)** | **100.0% (`flagged` / `needs_review`)** |

---

## 9. Comprehensive Classification of Findings

### 1. What Passed
- **High-Throughput Ingestion:** Streamed and processed 29,531 records in 1.06 seconds.
- **Physical Feasibility Check:** Verified that all reported pollutant values were non-negative ($0\text{ negative values}$).
- **Mathematical Consistency:** Verified that 100% of non-empty AQI numbers matched their official CPCB category buckets ($0\text{ bucket contradictions}$).
- **Scientific Memory:** Verified source immutability, SHA-256 preservation, and append-only idempotency.
- **CuratorKIT:** Successfully executed format detection, schema validation, exact deduplication, and manifest generation.
- **Gatekeeper Defense:** Prevented untrusted external claims from leaking into model post-training candidate sets.

### 2. What Could Not Be Tested
- **Calibration Expiry Rules:** No calibration logs exist in ambient sensor datasets.
- **Reagent Lot Expiry Rules:** Telemetry monitors physical air; no wet chemistry consumable lots are recorded.
- **Sample Holding Time Violations:** Continuous sensors do not track collection-to-analysis transportation time.
- **Measurement Uncertainty Boundaries:** Scalar numbers contain no expanded error bars.

### 3. What Failed (Hard Defects Detected in Kaggle Data)
- **1,423 Empty Telemetry Records:** Complete rows in `city_day.csv` where every pollutant column was blank, flagged as `INSUFFICIENT_POLLUTANT_DATA`.
- **4,681 Incomplete Records:** Rows with missing AQI and AQI Bucket values, flagged as `MISSING_AQI_EVIDENCE`.

### 4. What Needs Human Review
- **28,108 Plausible Records:** Ambient telemetry readings that are physically plausible and mathematically consistent, but lack laboratory accreditation evidence. Under VAULT's safety doctrine, these are quarantined as `needs_review` (`verdict: "unverified"`, `abstain: True`).

---

## 10. Regression Test Suite & Immutability Verification

All existing VAULT test suites were executed to verify zero regression:

| Test Suite | Command | Result |
|---|---|---|
| Kaggle External Validation Tests | `pytest tests/test_kaggle_validation.py` | **8 / 8 passed** (0.16s) |
| Teacher Round-Trip Tests | `pytest tests/test_roundtrip.py` | **10 / 10 passed** (1.18s) |
| Memory Multiprocessing Tests | `pytest tests/test_memory_multiprocess.py` | **5 / 5 passed** (4.71s) |
| Memory Unit Tests | `pytest tests/test_memory.py` | **9 / 9 passed** (0.77s) |
| Full Test Suite | `pytest` | **205 / 205 passed** (22.84s) |
| V1 Baseline Immutability | `python scripts/verify_v1_baseline.py` | **11 / 11 files 100% bit-identical** |
| V5 Training Export Audit | `python scripts/audit_v5_final.py` | **10 / 10 audit gates passed** |

*No code changes were made to existing V1–V5 modules. Zero git commits were made.*

