"""Multiprocessing Test Suite for Cross-Process-Safe ScientificMemory.

Validates multi-process safety on Windows AMD64 using multiprocessing spawn mode:
1. Ten processes writing 50 unique assessments.
2. All 50 assessments must be persisted.
3. No lost or overwritten assessments.
4. No duplicate assessment IDs.
5. Concurrent retries with identical IDs must remain idempotent.
6. Concurrent source registration must preserve source hashes.
7. Assessment history must remain append-only.
8. Latest assessment must be correct.
9. Simultaneous reads and writes must not produce corrupted JSON.
10. Exceptions must release locks correctly.
"""

from __future__ import annotations

import concurrent.futures
import json
import multiprocessing as mp
from pathlib import Path
import pytest

from vault.memory import ScientificMemory
from tests.mp_memory_workers import (
    worker_write_assessments,
    worker_idempotent_retries,
    worker_register_sources,
    worker_simultaneous_writer,
    worker_simultaneous_reader,
    worker_exception_under_lock,
)


@pytest.fixture
def mp_ctx():
    """Return explicit spawn multiprocessing context for Windows compatibility."""
    return mp.get_context("spawn")


def test_ten_processes_fifty_unique_assessments(tmp_path, mp_ctx):
    """Scenarios 1-4 & 7-8: Ten processes write 50 unique assessments across shared records.
    
    Verifies:
    1. 10 processes writing 50 unique assessments.
    2. All 50 assessments persisted.
    3. No lost or overwritten assessments.
    4. No duplicate assessment IDs.
    7. Assessment history remains append-only.
    8. Latest assessment is correct.
    """
    storage_dir = str(tmp_path / "mp_memory_1")
    num_procs = 10
    writes_per_proc = 5
    total_expected = num_procs * writes_per_proc

    # Execute 10 separate processes using ProcessPoolExecutor with spawn context
    with concurrent.futures.ProcessPoolExecutor(max_workers=num_procs, mp_context=mp_ctx) as executor:
        futures = [
            executor.submit(worker_write_assessments, storage_dir, pid, writes_per_proc)
            for pid in range(num_procs)
        ]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    # Collect written IDs reported by workers
    all_written_ids = [asm_id for sublist in results for asm_id in sublist]
    assert len(all_written_ids) == total_expected
    assert len(set(all_written_ids)) == total_expected

    # Verify on-disk persistence
    mem = ScientificMemory(storage_dir=storage_dir)
    with open(mem.assessments_file, "r", encoding="utf-8") as f:
        stored_lines = [json.loads(line) for line in f if line.strip()]

    assert len(stored_lines) == total_expected, f"Expected {total_expected} persisted lines, found {len(stored_lines)}"
    stored_ids = {line["assessment_id"] for line in stored_lines}
    assert stored_ids == set(all_written_ids)
    assert len(stored_ids) == total_expected

    # Verify history integrity across all records
    total_history_count = 0
    for i in range(3):
        rec_id = f"EXP-MP-{i}"
        hist = mem.get_history(rec_id)
        assert len(hist) > 0
        total_history_count += len(hist)

        # Check latest assessment consistency
        latest = mem.get_latest_assessment(rec_id)
        assert latest is not None
        assert latest["assessment_id"] == hist[-1]["assessment_id"]

        # Check append-only chronological timestamps
        timestamps = [h.get("recorded_at") for h in hist]
        assert timestamps == sorted(timestamps)

    assert total_history_count == total_expected


def test_concurrent_idempotent_retries(tmp_path, mp_ctx):
    """Scenario 5: Concurrent retries with identical assessment IDs remain idempotent across processes."""
    storage_dir = str(tmp_path / "mp_memory_2")
    mem = ScientificMemory(storage_dir=storage_dir)

    # Prepare 5 shared assessment definitions
    shared_asms = [
        {
            "assessment_id": f"ASM-IDEM-00{i}",
            "record_id": "EXP-SHARED-IDEM",
            "status": "checks_passed",
            "verdict": "valid",
            "abstain": False,
            "issues": [],
            "evidence": [],
            "derived": {"item": i},
            "engine_version": "2.0.0"
        }
        for i in range(5)
    ]

    # Spawn 6 processes, each attempting to record all 5 shared assessments
    num_procs = 6
    with concurrent.futures.ProcessPoolExecutor(max_workers=num_procs, mp_context=mp_ctx) as executor:
        futures = [
            executor.submit(worker_idempotent_retries, storage_dir, shared_asms)
            for _ in range(num_procs)
        ]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(results) == num_procs
    # In disk ledger, exactly 5 unique entries must exist
    with open(mem.assessments_file, "r", encoding="utf-8") as f:
        stored = [json.loads(line) for line in f if line.strip()]

    assert len(stored) == 5
    assert {s["assessment_id"] for s in stored} == {f"ASM-IDEM-00{i}" for i in range(5)}
    hist = mem.get_history("EXP-SHARED-IDEM")
    assert len(hist) == 5


def test_concurrent_source_registration_preserves_hashes(tmp_path, mp_ctx):
    """Scenario 6: Concurrent source registration preserves source hashes and immutability."""
    storage_dir = str(tmp_path / "mp_memory_3")
    mem = ScientificMemory(storage_dir=storage_dir)

    # Each process registers 5 unique sources and 1 common source
    num_procs = 5
    common_source = {
        "source_id": "SRC-COMMON-01",
        "payload": {"parameter": "Copper", "spec": 1.3}
    }
    expected_common_hash = mem.compute_sha256(common_source["payload"])

    with concurrent.futures.ProcessPoolExecutor(max_workers=num_procs, mp_context=mp_ctx) as executor:
        futures = []
        for pid in range(num_procs):
            sources = [
                {
                    "source_id": f"SRC-P{pid}-S{s}",
                    "payload": {"worker": pid, "seq": s, "val": pid * 10 + s}
                }
                for s in range(4)
            ]
            sources.append(common_source)
            futures.append(executor.submit(worker_register_sources, storage_dir, pid, sources))

        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(results) == num_procs

    # Verify sources registry file
    with open(mem.sources_file, "r", encoding="utf-8") as f:
        stored_sources = [json.loads(line) for line in f if line.strip()]

    # 5 workers * 4 unique + 1 common = 21 total unique sources
    assert len(stored_sources) == 21
    source_map = {s["source_id"]: s for s in stored_sources}
    assert source_map["SRC-COMMON-01"]["source_hash"] == expected_common_hash

    # Check via instance retrieval
    retrieved_common = mem.get_source("SRC-COMMON-01")
    assert retrieved_common is not None
    assert retrieved_common["source_hash"] == expected_common_hash


def test_simultaneous_reads_and_writes(tmp_path, mp_ctx):
    """Scenario 9: Simultaneous reads and writes do not produce corrupted JSON or lock contention crash."""
    storage_dir = str(tmp_path / "mp_memory_4")
    record_id = "EXP-SIMULTANEOUS"
    num_writers = 4
    writes_per_worker = 10
    num_readers = 3
    reads_per_worker = 15

    with concurrent.futures.ProcessPoolExecutor(max_workers=num_writers + num_readers, mp_context=mp_ctx) as executor:
        # Launch writers
        writer_futures = [
            executor.submit(worker_simultaneous_writer, storage_dir, wid, writes_per_worker, record_id)
            for wid in range(num_writers)
        ]
        # Launch readers concurrently
        reader_futures = [
            executor.submit(worker_simultaneous_reader, storage_dir, record_id, reads_per_worker)
            for _ in range(num_readers)
        ]

        # Wait for all to complete
        for f in concurrent.futures.as_completed(writer_futures + reader_futures):
            f.result()

    # Verify final state
    mem = ScientificMemory(storage_dir=storage_dir)
    hist = mem.get_history(record_id)
    total_expected = num_writers * writes_per_worker
    assert len(hist) == total_expected

    # Verify no corrupted lines in JSONL file
    with open(mem.assessments_file, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if line.strip():
                try:
                    obj = json.loads(line)
                    assert "assessment_id" in obj
                except Exception as e:
                    pytest.fail(f"Corrupted JSON detected on line {idx + 1}: {e}")


def test_exception_releases_locks_correctly(tmp_path, mp_ctx):
    """Scenario 10: Process exceptions release locks cleanly and allow subsequent processes to proceed."""
    storage_dir = str(tmp_path / "mp_memory_5")

    # Process 1 raises exception while holding lock
    with pytest.raises(Exception):
        with concurrent.futures.ProcessPoolExecutor(max_workers=1, mp_context=mp_ctx) as executor:
            fut = executor.submit(worker_exception_under_lock, storage_dir)
            fut.result()

    # Process 2 must immediately be able to acquire lock and write normally
    with concurrent.futures.ProcessPoolExecutor(max_workers=1, mp_context=mp_ctx) as executor:
        fut = executor.submit(worker_write_assessments, storage_dir, 99, 1, "EXP-RECOVERED")
        res = fut.result()

    assert res == ["ASM-P99-I0"]
    mem = ScientificMemory(storage_dir=storage_dir)
    latest = mem.get_latest_assessment("EXP-RECOVERED-0")
    assert latest is not None
    assert latest["assessment_id"] == "ASM-P99-I0"

