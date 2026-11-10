# VAULT V3 — Multi-Process Safe ScientificMemory Verification Report

**Milestone:** V3 Multi-Process Safe Persistence & Concurrency  
**Owner:** Vijay (Scientific Data Engineer & Evidence Verification Lead)  
**Branch:** `feat/data-verifier`  
**Execution Runtime:** Windows 11 AMD64 (Intel i3, 8 GB RAM), Python 3.11.9, pytest 9.2.0, `filelock` 4.2.9  
**Audit Date:** 2026-11-09  
**Status:** **APPROVED & FULLY VERIFIED**  

---

## 1. Executive Summary

This report documents the resolution of the outstanding V3 concurrency issue in Project VAULT. Previously, `vault.memory.ScientificMemory` was thread-safe within a single operating system process via Python's `threading.RLock()`, but was not safe when accessed concurrently by multiple independent operating system processes (e.g. multi-worker API deployments or concurrent batch pipelines).

We implemented cross-process locking and atomic persistence:
1. Integrated the Python `filelock` library (`filelock.FileLock`) with a stable lock file (`.memory.lock`).
2. Retained re-entrant in-process `threading.RLock()` to prevent thread contention.
3. Implemented cache invalidation via file modification and size detection (`st_mtime_ns`, `st_size`) to guarantee real-time cross-process index freshness.
4. Implemented atomic persistence for JSONL updates using temporary files and atomic `os.replace()` in the same storage directory.
5. Added a dedicated multiprocessing test suite (`tests/test_memory_multiprocess.py` and `tests/mp_memory_workers.py`) validating all 10 required cross-process scenarios under Windows `spawn` mode.
6. Executed all regression suites: 187/187 pytest tests passed, all 4 mandatory V2 fixtures passed, 11/11 V1 baseline files verified bit-identical, and V5 training export 10-point audit passed with 0 errors.

---

## 2. Previous Limitation & Problem Statement

In the initial V3 implementation:
- **Locking Scope:** Concurrency control relied exclusively on `self._lock = threading.RLock()`.
- **Limitation:** In-process re-entrant locks are invisible to other OS processes. When multiple Python processes (such as Uvicorn/Gunicorn multi-process workers or parallel CLI jobs) appended to `sources_registry.jsonl`, `assessments_ledger.jsonl`, or `retrospective_disputes.jsonl`:
  1. *File Append Collisions:* Simultaneous writes could interleave partial bytes or overwrite file pointers.
  2. *Stale In-Memory Caches:* Process A would update its internal `self._assessments_by_id` without Process B reloading from disk, causing broken idempotency and missed latest assessments.
  3. *Partial Read Exposure:* A reader process could inspect a file during a write, encountering invalid or incomplete JSON.

---

## 3. Chosen Locking and Atomic Persistence Architecture

### 3.1 Dual-Locking Mechanism (`_acquire_locks`)
To ensure complete safety across both threads and processes without deadlocks:
```python
@contextmanager
def _acquire_locks(self):
    """Acquire thread lock, then cross-process file lock."""
    with self._lock:
        with self._flock:
            yield
```
- **Thread Lock:** `threading.RLock()` (re-entrant within thread).
- **Process Lock:** `filelock.FileLock(str(self.storage_dir / ".memory.lock"), timeout=60.0)` (re-entrant within thread/process).
- **Ordering:** Thread lock is acquired first, then file lock. Both context managers guarantee deterministic release upon completion or unhandled exceptions.

### 3.2 Cross-Process Cache Synchronization (`_refresh_sources`, `_refresh_assessments`)
Under the acquired lock, before any read, idempotency check, or write:
- The engine inspects `(stat.st_mtime_ns, stat.st_size)`.
- If on-disk state differs from the cached snapshot (indicating another process wrote to the file), the in-memory indexes (`_sources`, `_assessments_by_record`, `_assessments_by_id`) are refreshed from disk.

### 3.3 Atomic Persistence (`_atomic_append_jsonl`)
For append-only JSONL ledgers:
1. A temporary file is created in the same storage directory (`tempfile.NamedTemporaryFile(dir=self.storage_dir, delete=False)`).
2. Existing file contents are copied to the temporary file.
3. The new JSON entry is appended.
4. The temporary file is flushed (`f.flush()`) and committed to disk platters via `os.fsync(f.fileno())`.
5. The temporary file is closed and atomically moved into place using `os.replace(temp_path, target_file)`.
6. On any exception, the temporary file is unlinked before the exception propagates.

---

## 4. Files Modified & Dependency Changes

### 4.1 Dependency Changes
- Added `filelock` (version 4.2.9 installed in `.venv`).
- Updated [`requirements.txt`](file:///c:/VAULT/requirements.txt):
  ```text
  pytest
  jsonschema
  filelock
  ```

### 4.2 Codebase Modifications
- [`vault/memory.py`](file:///c:/VAULT/vault/memory.py):
  - Added `import filelock`, `tempfile`, `shutil`, `contextmanager`.
  - Added `self.lock_file = self.storage_dir / ".memory.lock"` and `self._flock`.
  - Implemented `_acquire_locks()`, `_refresh_sources()`, `_refresh_assessments()`, `_atomic_append_jsonl()`.
  - Wrapped `register_source()`, `record_assessment()`, `record_retrospective_dispute()`, `get_history()`, `get_latest_assessment()`, `get_source()`, and `get_full_event_timeline()` with cross-process locks and cache refresh.
- [`tests/mp_memory_workers.py`](file:///c:/VAULT/tests/mp_memory_workers.py):
  - Top-level picklable multiprocessing worker routines for Windows `spawn` mode.
- [`tests/test_memory_multiprocess.py`](file:///c:/VAULT/tests/test_memory_multiprocess.py):
  - Comprehensive 5-test suite covering all 10 multiprocessing scenarios.

---

## 5. Multiprocessing Test Suite Execution

Executed command: `.venv\Scripts\python -m pytest tests/test_memory_multiprocess.py -v`

```text
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.2.0, pluggy-1.7.0 -- C:\VAULT\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\VAULT
configfile: pytest.ini
plugins: anyio-4.16.0
collecting ... collected 5 items

tests/test_memory_multiprocess.py::test_ten_processes_fifty_unique_assessments PASSED [ 20%]
tests/test_memory_multiprocess.py::test_concurrent_idempotent_retries PASSED [ 40%]
tests/test_memory_multiprocess.py::test_concurrent_source_registration_preserves_hashes PASSED [ 60%]
tests/test_memory_multiprocess.py::test_simultaneous_reads_and_writes PASSED [ 80%]
tests/test_memory_multiprocess.py::test_exception_releases_locks_correctly PASSED [100%]

============================== 5 passed in 4.71s ==============================
```

### Detailed Scenario Validation Matrix

| # | Scenario | Verification Method | Outcome |
|---|---|---|---|
| **1** | Ten processes writing 50 unique assessments | 10 spawned processes running concurrently writing 5 assessments each | **PASS** |
| **2** | All 50 assessments persisted | Validated disk ledger line count == 50 | **PASS** |
| **3** | No lost or overwritten assessments | Validated every process's written IDs exist on disk | **PASS** |
| **4** | No duplicate assessment IDs | Validated set length == 50 with 0 duplicates | **PASS** |
| **5** | Concurrent retries remain idempotent | 6 processes simultaneously recording 5 shared assessment IDs | **PASS** (exactly 5 persisted) |
| **6** | Concurrent source registration preserves hashes | 5 processes registering 20 unique + 1 shared source | **PASS** (SHA-256 verified) |
| **7** | Assessment history remains append-only | Retrieved chronological timeline across all records | **PASS** (timestamps monotonically ordered) |
| **8** | Latest assessment is correct | Asserted `get_latest_assessment(rec_id) == history[-1]` | **PASS** |
| **9** | Simultaneous reads and writes do not corrupt JSON | 4 writer processes + 3 continuous reader processes | **PASS** (0 corrupted JSON lines) |
| **10** | Exceptions release locks correctly | Process raises unhandled exception inside lock; next process acquires immediately | **PASS** |

---

## 6. Windows Compatibility Verification

- **Operating System:** Windows 11 Home 64-bit (build 26100), Intel Core i3-1115G4 @ 3.00GHz, 8 GB RAM.
- **Multiprocessing Context:** `multiprocessing.get_context("spawn")`.
- **Pickling & Spawning:** Worker routines were defined at module top-level in `tests/mp_memory_workers.py`. Child processes spawned without pickling or module-import failures.
- **File Locking on Windows:** `filelock` implements kernel-level locking (`msvcrt.locking`) under Windows, preventing access collisions while ensuring re-entrant acquisition within the holding thread.
- **Atomic Replacement on Windows:** Atomic `os.replace()` succeeded across all tests because the cross-process lock guarantees no concurrent handles remain open during replacement.

---

## 7. Full Regression Results

### 7.1 Existing Memory Unit Tests
Command: `.venv\Scripts\python -m pytest tests/test_memory.py -v`
```text
tests/test_memory.py::test_original_source_hash_unchanged_after_correction PASSED [ 11%]
tests/test_memory.py::test_assessments_are_append_only PASSED            [ 22%]
tests/test_memory.py::test_retrospective_calibration_audit_preserves_original_pass PASSED [ 33%]
tests/test_memory.py::test_supersession_relationship PASSED              [ 44%]
tests/test_memory.py::test_assessment_metadata_preservation PASSED       [ 55%]
tests/test_memory.py::test_history_retrieval_chronological PASSED        [ 66%]
tests/test_memory.py::test_duplicate_ingestion_idempotent PASSED         [ 77%]
tests/test_memory.py::test_assessment_retry_idempotent PASSED            [ 88%]
tests/test_memory.py::test_concurrent_assessment_writes PASSED           [100%]

============================== 9 passed in 0.77s ==============================
```

### 7.2 Four Mandatory V2 Fixtures
Command: `.venv\Scripts\python -m scripts.run_demo`
```text
========================================================================
 VAULT — Evidence-Gated Laboratory Verification Demo (Tiny Aya RC)
 Fictional Scintest Research Labs | Scientific Data Substrate
========================================================================

[FIXTURE 1: Arithmetic Contradiction]
Record: EXP-FIX-001 | Reported: 15.0 mg / 0.5 L as 3.0 mg/L
Verdict: INVALID | Status: flagged | Abstain: False
Issues:  ['ARITHMETIC_CONTRADICTION']
Evidence: {'mass_mg': 15.0, 'volume_L': 0.5, 'expected_concentration_mg_L': 30.0, 'reported_concentration': 3.0, 'formula': 'concentration = mass / volume'}

[FIXTURE 2: Retrospective Audit Invalidation]
Initial Verdict: VALID | Status: checks_passed
Audit event AUDIT-2025-04-15-01 detects drift on 2025-03-25.
Updated Verdict: INVALID | Status: flagged | Supersedes: ASM-5723CCE166ED
Source hash immutable: 80e4fe7e7a7888ed...

[FIXTURE 3: Valid Alternative Analytical Method]
Record: EXP-FIX-003 | Method: ALT-AVAIL-01 (measuring bioavailable concentration)
Verdict: VALID | Status: checks_passed | Abstain: False
Evidence: {'method_id': 'ALT-AVAIL-01', 'method_type': 'validated_alternative', 'measurand': 'bioavailable_concentration', 'availability_factor': 0.75, 'calculated_available_concentration': 135.0, 'threshold': 150.0}

[FIXTURE 4: Novel Analytical Method (Safe Mechanical Check)]
Record: EXP-FIX-004 | Method: METH-NOVEL-SPECTRO-99 (unvalidated research formula)
Verdict: NEEDS_REVIEW | Status: needs_review | Abstain: True
Issues:  ['NOVEL_METHOD_UNVALIDATED']
Action: Preserved for expert human review; NOT falsely rejected as error.

========================================================================
 Demo complete: All 4 fixtures processed with deterministic audit trails.
========================================================================
```

### 7.3 Full VAULT Test Suite
Command: `.venv\Scripts\python -m pytest`
```text
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.2.0, pluggy-1.7.0
rootdir: C:\VAULT
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.16.0
collected 187 items

tests\test_calibration_rules.py ...........                              [  5%]
tests\test_curation.py ....                                              [  8%]
tests\test_curatorkit_integration.py .....                               [ 10%]
tests\test_export.py ...                                                 [ 12%]
tests\test_generate_v2.py ..........                                     [ 17%]
tests\test_holding_time_rules.py ...........                             [ 23%]
tests\test_ledger_v2.py .......                                          [ 27%]
tests\test_lot_rules.py ...........                                      [ 33%]
tests\test_measurement_rules.py ...............                          [ 41%]
tests\test_memory.py .........                                           [ 45%]
tests\test_memory_multiprocess.py .....                                  [ 48%]
tests\test_reproducibility.py .........                                  [ 53%]
tests\test_rules_v2.py .......................................           [ 74%]
tests\test_sop_rules.py .............                                    [ 81%]
tests\test_splits.py ....                                                [ 83%]
tests\test_units_v2.py ..........................                        [ 97%]
tests\test_verification.py .....                                         [100%]

============================= 187 passed in 8.12s =============================
```

### 7.4 V1 Baseline Immutability
Command: `.venv\Scripts\python scripts/verify_v1_baseline.py`
```text
=== VAULT V1 Baseline Immutability Verification ===
Manifest Version: 1.0
Verifying 11 files...

  [PASS] config/simulator_config.json (316 bytes)
  [PASS] data/raw/sops_v1.jsonl (10498 bytes)
  [PASS] data/raw/instruments_v1.jsonl (3974 bytes)
  [PASS] data/raw/lots_v1.jsonl (5166 bytes)
  [PASS] data/raw/samples_v1.jsonl (19675 bytes)
  [PASS] data/raw/experiments_v1.jsonl (324430 bytes)
  [PASS] data/raw/runs_v1.csv (115760 bytes)
  [PASS] data/raw/metadata.json (1459 bytes)
  [PASS] data/ground_truth/ground_truth_ledger.jsonl (2333454 bytes)
  [PASS] data/reports/ground_truth_summary.json (1721 bytes)
  [PASS] data/reports/vijay_handover_report.json (9273 bytes)

RESULT: ALL V1 FILES ARE 100% IDENTICAL TO BASELINE.
```

### 7.5 V5 Training Export & Audit
Command: `.venv\Scripts\python scripts/audit_v5_final.py`
```text
============================================================================
 VAULT V5 — Comprehensive 10-Point Training Export Audit
============================================================================
[POINT 1 PASS] All 720 accepted candidates trace to verified source records.
[POINT 2 PASS] 100% of accepted candidates independently verify as 'checks_passed' with 0 issues.
[POINT 3 PASS] Exactly 0 flagged or needs_review records exist in training candidates.
[POINT 4 PASS] Train (720) and Quarantine (480) are 100% disjoint.
[POINT 5 PASS] Exactly 720 unique experiment IDs (0 duplicates).
[POINT 6 PASS] 100% of assistant responses use inclusive boundary wording.
[POINT 7 PASS] EXP-0359 / CLAUSE-020 correctly bound to v1.0 limits [0.1, 2.0] mg/L on 2025-03-26.
[POINT 8 PASS] Zero truth-ledger or evaluation tokens leaked into model-facing training text.
[POINT 9 PASS] All 4 checksums in checksums.txt match disk bytes exactly.
[POINT 10 PASS] Machine-readable export summary written to export_summary.json.

[AUDIT COMPLETE] ALL 10 AUDIT CHECKS PASSED WITH ZERO ERRORS.
```

---

## 8. Remaining Limitations & Scaling Architecture

While `filelock` and atomic `os.replace()` fully resolve cross-process safety on a single machine or network-mounted storage volume:
1. **Network File Systems (NFS/SMB):** Some network file systems may experience latency or locking quirks if file lock leases expire. For multi-node cluster deployments, a distributed lock manager (e.g. Redis Redlock) or database locking should be used.
2. **High-Throughput Scaling (10,000+ writes/sec):** Atomic whole-file replacement (`os.replace` of JSONL) has $O(N)$ I/O cost as file size grows. For massive write throughput, the backend storage can be migrated to an embedded SQLite database in WAL mode (`PRAGMA journal_mode=WAL;`) with $O(1)$ page writes while maintaining the exact same public API signatures.

