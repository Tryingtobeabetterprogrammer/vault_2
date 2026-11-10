"""VAULT Immutable Scientific Memory System.

Maintains an append-only registry of original sources, assessment findings,
retrospective corrections, and supersession lineages without mutating historical facts.
Provides thread-safe and cross-process-safe operations with deterministic locking,
atomic persistence, and audit logging.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
from typing import Any, Dict, List, Optional, Tuple

import filelock


class ScientificMemory:
    """Thread-safe and multi-process-safe append-only scientific registry and history ledger."""

    def __init__(self, storage_dir: Optional[str] = None, lock_timeout: float = 60.0):
        self.storage_dir = Path(storage_dir) if storage_dir else Path("data/memory")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.sources_file = self.storage_dir / "sources_registry.jsonl"
        self.assessments_file = self.storage_dir / "assessments_ledger.jsonl"
        self.disputes_file = self.storage_dir / "retrospective_disputes.jsonl"
        self.lock_file = self.storage_dir / ".memory.lock"

        # Re-entrant thread lock and cross-process file lock
        self._lock = threading.RLock()
        self._flock = filelock.FileLock(str(self.lock_file), timeout=lock_timeout)

        # In-memory index for fast lookup
        self._sources: Dict[str, Dict[str, Any]] = {}
        self._assessments_by_record: Dict[str, List[Dict[str, Any]]] = {}
        self._assessments_by_id: Dict[str, Dict[str, Any]] = {}

        # Cache invalidation tracking across processes (mtime_ns, size)
        self._sources_stat: Optional[Tuple[int, int]] = None
        self._assessments_stat: Optional[Tuple[int, int]] = None

        self._load_existing()

    @contextmanager
    def _acquire_locks(self):
        """Acquire in-process thread lock and cross-process file lock."""
        with self._lock:
            with self._flock:
                yield

    def _refresh_sources(self) -> None:
        """Reload sources from disk if modified by another process or thread."""
        if not self.sources_file.exists():
            self._sources_stat = None
            return
        stat = self.sources_file.stat()
        current_stat = (stat.st_mtime_ns, stat.st_size)
        if current_stat != self._sources_stat:
            sources: Dict[str, Dict[str, Any]] = {}
            with open(self.sources_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        item = json.loads(line)
                        sources[item["source_id"]] = item
            self._sources = sources
            self._sources_stat = current_stat

    def _refresh_assessments(self) -> None:
        """Reload assessments from disk if modified by another process or thread."""
        if not self.assessments_file.exists():
            self._assessments_stat = None
            return
        stat = self.assessments_file.stat()
        current_stat = (stat.st_mtime_ns, stat.st_size)
        if current_stat != self._assessments_stat:
            by_rec: Dict[str, List[Dict[str, Any]]] = {}
            by_id: Dict[str, Dict[str, Any]] = {}
            with open(self.assessments_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        item = json.loads(line)
                        rec_id = item["record_id"]
                        by_rec.setdefault(rec_id, []).append(item)
                        by_id[item["assessment_id"]] = item
            self._assessments_by_record = by_rec
            self._assessments_by_id = by_id
            self._assessments_stat = current_stat

    def _atomic_append_jsonl(self, target_file: Path, entry: Dict[str, Any]) -> None:
        """Atomically append a JSON entry to a JSONL file using a temporary file in the same directory.
        
        Ensures partial writes are never exposed to another process and disk buffers are flushed.
        """
        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=self.storage_dir,
            delete=False,
            prefix=f"tmp_{target_file.stem}_",
            suffix=".tmp",
        )
        temp_path = Path(temp_file.name)
        try:
            if target_file.exists():
                with open(target_file, "r", encoding="utf-8") as src:
                    shutil.copyfileobj(src, temp_file)
            temp_file.write(json.dumps(entry) + "\n")
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_file.close()
            os.replace(temp_path, target_file)
        except Exception:
            try:
                temp_file.close()
            except Exception:
                pass
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            raise

    def _load_existing(self) -> None:
        """Load append-only historical records into index under locks."""
        with self._acquire_locks():
            self._refresh_sources()
            self._refresh_assessments()

    @staticmethod
    def compute_sha256(payload: Any) -> str:
        """Compute deterministic SHA-256 hash of a dictionary payload or string."""
        if isinstance(payload, dict):
            content = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        elif isinstance(payload, str):
            content = payload.encode("utf-8")
        elif isinstance(payload, bytes):
            content = payload
        else:
            content = str(payload).encode("utf-8")
        return hashlib.sha256(content).hexdigest()

    def register_source(
        self,
        source_id: str,
        payload: Dict[str, Any],
        source_uri: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Register an original immutable scientific record or document.
        
        Idempotent: if source_id already registered with matching hash, returns existing.
        Fails if hash mismatch on duplicate ID.
        Cross-process safe and atomic.
        """
        payload_hash = self.compute_sha256(payload)
        now_utc = datetime.now(timezone.utc).isoformat()

        with self._acquire_locks():
            self._refresh_sources()
            if source_id in self._sources:
                existing = self._sources[source_id]
                if existing["source_hash"] == payload_hash:
                    return existing
                raise ValueError(
                    f"Source immutability violation: ID {source_id} already exists with different hash {existing['source_hash']} vs {payload_hash}"
                )

            entry = {
                "source_id": source_id,
                "source_hash": payload_hash,
                "source_uri": source_uri or f"memory://sources/{source_id}",
                "registered_at": now_utc,
                "metadata": metadata or {},
                "raw_payload": payload
            }

            self._atomic_append_jsonl(self.sources_file, entry)
            self._sources[source_id] = entry
            stat = self.sources_file.stat()
            self._sources_stat = (stat.st_mtime_ns, stat.st_size)
            return entry

    def record_assessment(self, assessment: Dict[str, Any]) -> Dict[str, Any]:
        """Append a verification assessment finding to the ledger.
        
        Preserves original records; updates index and links supersession if present.
        Thread-safe, multi-process safe, and idempotent for duplicate identical assessment IDs.
        """
        asm_id = assessment["assessment_id"]
        rec_id = assessment["record_id"]

        with self._acquire_locks():
            self._refresh_assessments()
            # Prevent duplicate identical assessment writes (idempotency)
            if asm_id in self._assessments_by_id:
                return self._assessments_by_id[asm_id]

            entry = dict(assessment)
            if "recorded_at" not in entry:
                entry["recorded_at"] = datetime.now(timezone.utc).isoformat()

            self._atomic_append_jsonl(self.assessments_file, entry)
            self._assessments_by_id[asm_id] = entry
            self._assessments_by_record.setdefault(rec_id, []).append(entry)
            stat = self.assessments_file.stat()
            self._assessments_stat = (stat.st_mtime_ns, stat.st_size)
            return entry

    def record_retrospective_dispute(
        self,
        record_id: str,
        prior_assessment_id: str,
        dispute_reason: str,
        audit_event_id: str,
        evidence: Optional[Dict[str, Any]] = None,
        reviewer: Optional[str] = None
    ) -> Dict[str, Any]:
        """Record an evidence-backed retrospective dispute of a prior assessment.
        
        Crucial requirement: The original source record and prior assessment remain untouched.
        A new superseding assessment is appended with status 'flagged' or 'needs_review'.
        """
        with self._acquire_locks():
            self._refresh_assessments()
            if prior_assessment_id not in self._assessments_by_id:
                raise KeyError(f"Prior assessment {prior_assessment_id} not found in ledger.")

            prior = self._assessments_by_id[prior_assessment_id]
            now_utc = datetime.now(timezone.utc).isoformat()
            new_asm_id = f"ASM-DISP-{hashlib.sha256(f'{prior_assessment_id}:{audit_event_id}'.encode()).hexdigest()[:12].upper()}"

            dispute_assessment = {
                "assessment_id": new_asm_id,
                "record_id": record_id,
                "supersedes_id": prior_assessment_id,
                "status": "flagged",
                "verdict": "invalid",
                "abstain": False,
                "original_verdict": prior.get("original_verdict"),
                "issues": [dispute_reason],
                "evidence": prior.get("evidence", []) + [{
                    "rule_name": "retrospective_calibration_audit",
                    "status": "fail",
                    "reason": dispute_reason,
                    "details": {
                        "audit_event_id": audit_event_id,
                        "dispute_timestamp": now_utc,
                        "audit_evidence": evidence or {}
                    },
                    "evidence_refs": [f"audit_event:{audit_event_id}"]
                }],
                "derived": prior.get("derived", {}),
                "engine_version": prior.get("engine_version", "2.0.0"),
                "created_at": now_utc,
                "reviewer_state": "human_disputed" if reviewer else "automated_audit_disputed"
            }

            # Append new assessment without touching prior
            self.record_assessment(dispute_assessment)

            # Log audit dispute event
            audit_log_entry = {
                "audit_event_id": audit_event_id,
                "target_record_id": record_id,
                "prior_assessment_id": prior_assessment_id,
                "new_assessment_id": new_asm_id,
                "dispute_reason": dispute_reason,
                "timestamp": now_utc,
                "reviewer": reviewer
            }
            self._atomic_append_jsonl(self.disputes_file, audit_log_entry)
            return dispute_assessment

    def get_history(self, record_id: str) -> List[Dict[str, Any]]:
        """Retrieve complete chronological assessment history for a record ID."""
        with self._acquire_locks():
            self._refresh_assessments()
            history = list(self._assessments_by_record.get(record_id, []))
            return sorted(history, key=lambda x: x.get("recorded_at") or x.get("created_at") or "")

    def get_full_event_timeline(self, record_id: str) -> List[Dict[str, Any]]:
        """Retrieve full chronological unified timeline of sources, assessments, and disputes."""
        with self._acquire_locks():
            self._refresh_sources()
            self._refresh_assessments()
            events: List[Dict[str, Any]] = []

            # 1. Source ingestion event
            if record_id in self._sources:
                src = self._sources[record_id]
                events.append({
                    "event_type": "source_registered",
                    "event_id": f"EVT-SRC-{src['source_id']}",
                    "record_id": src["source_id"],
                    "timestamp": src["registered_at"],
                    "source_hash": src["source_hash"],
                    "source_uri": src["source_uri"],
                })

            # 2. Assessment findings
            for asm in self._assessments_by_record.get(record_id, []):
                events.append({
                    "event_type": "assessment_recorded",
                    "event_id": f"EVT-ASM-{asm['assessment_id']}",
                    "assessment_id": asm["assessment_id"],
                    "record_id": record_id,
                    "supersedes_id": asm.get("supersedes_id"),
                    "status": asm.get("status"),
                    "verdict": asm.get("verdict"),
                    "timestamp": asm.get("recorded_at") or asm.get("created_at"),
                    "issues": asm.get("issues", []),
                    "evidence_refs": [ref for ev in asm.get("evidence", []) for ref in ev.get("evidence_refs", [])],
                })

            # Sort timeline chronologically
            return sorted(events, key=lambda x: x.get("timestamp") or "")

    def get_latest_assessment(self, record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the latest assessment in the supersession lineage."""
        with self._acquire_locks():
            self._refresh_assessments()
            history = self.get_history(record_id)
            if not history:
                return None
            return history[-1]

    def get_source(self, source_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve registered source record and verified SHA-256 hash."""
        with self._acquire_locks():
            self._refresh_sources()
            return self._sources.get(source_id)
