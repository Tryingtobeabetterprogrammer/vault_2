"""Worker routines for cross-process multiprocessing tests of ScientificMemory.

These functions must reside at module top-level to support Windows 'spawn' mode pickling.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import time
from typing import Any, Dict, List

from vault.memory import ScientificMemory


def worker_write_assessments(
    storage_dir: str,
    worker_id: int,
    writes_per_proc: int,
    record_prefix: str = "EXP-MP"
) -> List[str]:
    """Independent process worker that creates and writes unique assessments."""
    mem = ScientificMemory(storage_dir=storage_dir)
    written_ids = []
    for i in range(writes_per_proc):
        rec_id = f"{record_prefix}-{worker_id % 3}"
        asm_id = f"ASM-P{worker_id}-I{i}"
        assessment = {
            "assessment_id": asm_id,
            "record_id": rec_id,
            "status": "checks_passed",
            "verdict": "valid",
            "abstain": False,
            "issues": [],
            "evidence": [{"rule": "test", "worker": worker_id, "iter": i}],
            "derived": {"val": float(worker_id * 100 + i)},
            "engine_version": "2.0.0"
        }
        mem.record_assessment(assessment)
        written_ids.append(asm_id)
        time.sleep(0.005)  # slight stagger to increase concurrency interleaving
    return written_ids


def worker_idempotent_retries(
    storage_dir: str,
    shared_asm_templates: List[Dict[str, Any]]
) -> int:
    """Independent process worker that repeatedly records the same assessment IDs."""
    mem = ScientificMemory(storage_dir=storage_dir)
    recorded_count = 0
    for asm in shared_asm_templates:
        res = mem.record_assessment(asm)
        if res["assessment_id"] == asm["assessment_id"]:
            recorded_count += 1
    return recorded_count


def worker_register_sources(
    storage_dir: str,
    worker_id: int,
    sources_to_register: List[Dict[str, Any]]
) -> List[str]:
    """Independent process worker registering sources concurrently."""
    mem = ScientificMemory(storage_dir=storage_dir)
    registered_hashes = []
    for s in sources_to_register:
        res = mem.register_source(
            source_id=s["source_id"],
            payload=s["payload"]
        )
        registered_hashes.append(res["source_hash"])
        time.sleep(0.005)
    return registered_hashes


def worker_simultaneous_writer(
    storage_dir: str,
    worker_id: int,
    num_writes: int,
    record_id: str
) -> None:
    """Worker writing continuously to a shared record."""
    mem = ScientificMemory(storage_dir=storage_dir)
    for i in range(num_writes):
        asm = {
            "assessment_id": f"ASM-BURST-W{worker_id}-{i}",
            "record_id": record_id,
            "status": "checks_passed",
            "verdict": "valid",
            "abstain": False,
            "issues": [],
            "evidence": [],
            "derived": {"seq": i},
            "engine_version": "2.0.0"
        }
        mem.record_assessment(asm)
        time.sleep(0.002)


def worker_simultaneous_reader(
    storage_dir: str,
    record_id: str,
    num_reads: int
) -> List[int]:
    """Worker reading continuously while writers are actively appending."""
    mem = ScientificMemory(storage_dir=storage_dir)
    history_lengths = []
    for _ in range(num_reads):
        hist = mem.get_history(record_id)
        latest = mem.get_latest_assessment(record_id)
        if latest is not None:
            assert isinstance(latest, dict)
            assert "assessment_id" in latest
        if hist:
            assert isinstance(hist, list)
            assert all("assessment_id" in h for h in hist)
        history_lengths.append(len(hist))
        time.sleep(0.003)
    return history_lengths


def worker_exception_under_lock(storage_dir: str) -> None:
    """Worker that raises an intentional exception while holding memory locks."""
    mem = ScientificMemory(storage_dir=storage_dir)
    with mem._acquire_locks():
        # Intentionally raise exception while holding lock
        raise RuntimeError("Intentional error under lock")
