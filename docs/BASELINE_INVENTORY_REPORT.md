# VAULT V0 Baseline Inventory and Verification Gap Report

**Date:** November 9, 2026  
**Owner:** Vijay (Scientific data engineer and evidence-verification lead)  
**Branch:** `feat/data-verifier`  
**Base Commit:** `175c8eb` (Initial commit - VAULT V1 simulator and ground truth)  
**Python Runtime:** Python 3.11.9 (Windows AMD64, Intel i3, 8 GB RAM)

---

## 1. Executive Summary

This report establishes the baseline inventory, test execution state, schema contracts, and verification gaps for VAULT in accordance with the *Vijay Antigravity Engineering Brief*. 

All existing V1 baseline records, simulator scripts, and deterministic ground-truth ledgers have been preserved with 100% SHA-256 byte-level fidelity. The starter test suite of 70 unit tests executes cleanly in 0.82s. Gaps between the raw simulator scripts and the required production runtime modules (`vault/verification.py`, `vault/memory.py`, CuratorKIT integration, and shared REST API handoffs) have been identified, and schema contracts (`contracts/record.schema.json` and `contracts/assessment.schema.json`) have been drafted.

---

## 2. Git Status and Branch Inventory

- **Current Branch:** `feat/data-verifier`
- **Upstream / Target:** `origin/main` (commit `175c8eb`)
- **Untracked V2 Files:**
  - `config/simulator_config_v2.json`
  - `data/ground_truth_v2/`
  - `data/raw_v2/`
  - `data/reports/v1_baseline_hashes.json`
  - `data/reports_v2/`
  - `scripts/run_rules_v2.py`
  - `scripts/run_simulator_v2.py`
  - `scripts/verify_v1_baseline.py`
  - `synth/generate_v2.py`
  - `synth/ledger_v2.py`
  - `synth/rules_v2.py`
  - `synth/units_v2.py`
  - `tests/test_generate_v2.py`
  - `tests/test_ledger_v2.py`
  - `tests/test_rules_v2.py`
  - `tests/test_units_v2.py`

---

## 3. Baseline Verification and Test Execution

### 3.1 V1 Baseline Immutability Check
Running `python scripts/verify_v1_baseline.py`:
- 11 of 11 files verified against SHA-256 baseline manifest: **100% PASS**.
- Zero modification to V1 raw data, rules, units, or ground truth.

### 3.2 V1 Test Suite Results
Command: `pytest tests/test_calibration_rules.py tests/test_holding_time_rules.py tests/test_lot_rules.py tests/test_measurement_rules.py tests/test_reproducibility.py tests/test_sop_rules.py -v`
- `tests/test_calibration_rules.py`: 11 passed
- `tests/test_holding_time_rules.py`: 11 passed
- `tests/test_lot_rules.py`: 11 passed
- `tests/test_measurement_rules.py`: 15 passed
- `tests/test_reproducibility.py`: 9 passed
- `tests/test_sop_rules.py`: 13 passed
- **Total:** 70 passed in 0.82 seconds (0 failures, 0 warnings).

### 3.3 Demo Script Status
Command: `python -m scripts.run_demo`
- **Result:** FAILED (`No module named scripts.run_demo`).
- **Gap Identified:** No standardized demo runner exists yet for Scintest record verification. To be created in V1/V2.

### 3.4 Tooling and Environment Constraints
- **Operating System:** Windows 11 on Intel i3, 8 GB RAM, CPU-only.
- **Python Environment:** `.venv` (Python 3.11.9).
- **CuratorKIT Status:** Not installed in `.venv`. System Application Control policy blocks `pip.exe` direct invocation; package additions must run via python module or be documented as external/offline.
- **`docs/TEAM_PLAYBOOK.md`:** Missing in repository root. Team brief utilized as primary operational guide.

---

## 4. Stable Sample Fields and Evidence Pointers

For inter-team integration with Pawan (Harness/UI Lead) and Model Training Lead:

### 4.1 Ingested Record Fields (`contracts/record.schema.json`)
| Field Name | Type | Stability | Description |
|---|---|---|---|
| `record_id` | string | Stable | Unique experiment run ID (e.g., `EXP-0001`) |
| `run_date` | string (YYYY-MM-DD) | Stable | Date of experiment execution |
| `sample_id` | string | Stable | Foreign key to `samples.jsonl` |
| `clause_id` | string | Stable | Specific clause in governing SOP |
| `sop_id` | string | Stable | Foreign key to `sops.jsonl` |
| `sop_version` | string \| null | Stable | Explicit version recorded by analyst |
| `instrument_id` | string | Stable | Foreign key to `instruments.jsonl` |
| `lot_id` | string | Stable | Foreign key to `lots.jsonl` |
| `operator_id` | string | Stable | Operator identifier |
| `measured_value` | number \| string | Stable | Analytical measurement |
| `measurement_unit`| string | Stable | Unit (e.g., `mg/L`, `ug/L`, `CFU/g`) |
| `measurement_uncertainty` | number \| string | Stable | Expanded uncertainty margin |
| `collected_at` | string (ISO-8601) | Stable | Sample collection timestamp |
| `analyzed_at` | string (ISO-8601) | Stable | Sample analysis timestamp |
| `max_holding_hours` | number | Stable | Holding time limit |
| `parameter` | string | Stable | Measurand name (e.g. Copper, pH) |
| `sample_matrix` | string | Stable | Matrix (e.g. Drinking Water) |
| `site_id` | string | Stable (V2) | Facility identifier |
| `site_timezone` | string | Stable (V2) | Facility IANA timezone |
| `method_id` | string \| null | Stable (V2) | Documented analytical method ID |
| `original_verdict`| string \| null | Stable (V2) | Analyst claimed verdict (PASS/FAIL) |

### 4.2 Assessment Findings Fields (`contracts/assessment.schema.json`)
- `assessment_id`: UUID/identifier of verification run.
- `record_id`: Target record.
- `status`: High-level outcome (`checks_passed`, `flagged`, `needs_review`).
- `verdict`: Ground-truth scientific verdict (`valid`, `invalid`, `needs_review`).
- `abstain`: Boolean indicating if review condition was triggered.
- `issues`: Explicit reason codes (e.g. `CALIBRATION_EXPIRED`, `SOP_VERSION_INVALID`, `MEASUREMENT_OUT_OF_RANGE`, `HOLDING_TIME_EXCEEDED`).
- `evidence`: Audit trace for each rule recomputed independently with details and references.
- `derived`: Recomputed normalized values, canonical units, and evaluated limits.

---

## 5. Next Planned Tasks

1. **V1 Deterministic Scintest Simulator:** Implement family-separated train/dev/sealed-test splits, `split_manifest.json`, and ensure zero data leakage between splits.
2. **V2 Core Deterministic Verifier:** Implement production `vault/verification.py` providing `verify_record(record)` with full audit provenance.
3. **V3 Immutable Scientific Memory:** Implement `vault/memory.py` append-only event ledger and retrospective audit support.
